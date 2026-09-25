"""Driver for the TTi 1604 bench multimeter.

A 4-3/4 digit (40 000 count) true-RMS bench meter with an opto-isolated RS-232
interface. It is not a SCPI instrument and is not close to one: there is no
command language, no query, no ``*IDN?`` and no error queue. The link carries
single ASCII characters standing for front-panel key presses, and in remote
mode the meter streams a ten-byte binary frame after every measurement. This
driver therefore takes the transport and lifecycle from
:class:`~benchtools.core.scpi.ScpiInstrument` and replaces every SCPI-specific
part explicitly.

Four things about this meter shape the driver, and each is a way a naive
implementation reports a number that is not true:

**The host powers the interface.** DTR must be asserted and RTS must not be;
the opto-isolated interface draws its power from them. Left at a serial
library's defaults, the meter is mute, and every obvious diagnosis is wrong.
See :data:`.constants.DTR_ASSERTED`.

**Nothing arrives until the meter is put in remote mode.** Before ``u`` the
meter streams nothing whatsoever. A driver that connects and waits is
indistinguishable from one with a broken cable, so :meth:`connect` enters
remote mode by default and :meth:`read` says which state it was in when it
found nothing.

**The stream has no gaps to synchronise on.** Frames run back to back, so a
reader that takes the next ten bytes can land mid-frame and decode the display
digits against the wrong columns. That does not raise - it returns a plausible
wrong number. Frames are therefore found by their leading carriage return, and
echoes are recovered as what is left over; see
:class:`~benchtools.instruments.tti1604.protocol.FrameAssembler`.

**A held display is not a live measurement.** Hold, Touch-Hold and the Min-Max
review all freeze the display, and the frame says so. The reading is real but
it is not current, and :attr:`~.protocol.Reading.held` exists so a test can
refuse it rather than record the past as the present.

Traces to: DMM-FR-001 .. DMM-FR-060, DMM-ARC-001, DMM-DD-DMM.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from ...core.errors import InstrumentError, TransportError
from ...core.instrument import InstrumentIdentity
from ...core.scpi import ScpiInstrument
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    DEFAULT_BAUDRATE,
    DTR_ASSERTED,
    ECHO_TIMEOUT,
    KEYS,
    LOCAL,
    MANUFACTURER,
    MODEL,
    READING_INTERVAL,
    REMOTE,
    RTS_ASSERTED,
    SETTLING_TIME,
)
from .protocol import FrameAssembler, Reading, decode
from .simulator import SimulatedTti1604

__all__ = ["Tti1604"]

_LOG = logging.getLogger(__name__)


class Tti1604(ScpiInstrument):
    """A TTi 1604 bench multimeter on a serial link.

    Example::

        with Tti1604.connect("/dev/ttyUSB0") as dmm:
            dmm.select_milliamps()
            dmm.select_dc()
            reading = dmm.read()
            if reading.held:
                raise SystemExit("the display is frozen; that reading is not live")
            print(reading.value, reading.unit)
    """

    SIMULATOR_CLASS = SimulatedTti1604
    MODEL_NAME = MODEL

    def __init__(
        self,
        transport: Transport,
        auto_check_errors: bool = False,
        owns_transport: bool = True,
        enter_remote: bool = True,
    ) -> None:
        super().__init__(
            transport,
            auto_check_errors=auto_check_errors,
            owns_transport=owns_transport,
        )
        self._enter_remote = bool(enter_remote)
        self._frames = FrameAssembler()
        self._ready: List[bytes] = []
        self._echoes = bytearray()
        self._remote = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    # The base class takes a generic resource and backend; this meter has one
    # link type and two lines that must be driven, so its own parameters say
    # what can actually be varied.
    def connect(  # pylint: disable=arguments-differ,too-many-arguments
        cls,
        resource: str = "sim://",
        *,
        timeout: float = 5.0,
        baudrate: int = DEFAULT_BAUDRATE,
        initialise: bool = True,
        enter_remote: bool = True,
        simulated_value: Optional[float] = None,
        **kwargs,
    ) -> "Tti1604":
        """Open a meter.

        :param resource: ``/dev/ttyUSB0``, ``COM5``, ``serial://COM5`` or
            ``sim://``. A bare port name is taken as a serial port rather than
            as a host name.
        :param enter_remote: Put the meter into remote mode, without which it
            streams nothing. Turn this off only to observe a meter that
            another program is already driving.
        :param simulated_value: What the *simulated* meter should measure, in
            SI units. Ignored for a real meter. This is how a bench file says
            what the modelled instrument reads, so that a specification with
            real limits in it can be exercised with no hardware - the limits
            stay the test's, and the value stays the bench's.
        """
        target = cls._normalise_resource(resource)
        link_kwargs = {"responder_factory": cls.SIMULATOR_CLASS}
        if simulated_value is not None:
            link_kwargs["responder"] = cls.SIMULATOR_CLASS(value=float(simulated_value))
        if target.startswith("serial://"):
            # The handshake lines are interface power here, not flow control.
            link_kwargs.update(
                baudrate=baudrate, dtr=DTR_ASSERTED, rts=RTS_ASSERTED, dsrdtr=False
            )
        transport = open_transport(target, timeout=timeout, open_now=False, **link_kwargs)
        instrument = cls(transport, enter_remote=enter_remote, **kwargs)
        if initialise:
            try:
                instrument.initialise()
            except Exception:
                instrument.close()
                raise
        return instrument

    @staticmethod
    def _normalise_resource(resource: str) -> str:
        """Accept a bare port name as a serial port rather than a host name."""
        text = (resource or "").strip()
        if not text:
            return "sim://"
        if "://" in text or text.lower() in ("sim", "mock"):
            return text
        return "serial://%s" % text

    def _post_open(self) -> None:
        """Enter remote mode and change nothing else.

        Deliberately does not press Operate. That key toggles the measurement
        circuits, so a driver that pressed it to "make sure the meter is on"
        would switch off a meter that already was - and the interface stays
        powered either way, so the mistake would not even look like one.
        """
        if self._enter_remote:
            self.remote()

    def _read_identity(self) -> InstrumentIdentity:
        """What the meter is, from the driver rather than from the meter.

        The 1604 answers no identification query - there is no ``*IDN?`` and no
        equivalent. The identity is therefore the model this driver was written
        for, and it carries no serial number or firmware revision because the
        instrument offers none. A report that needs to tie a result to a
        particular meter must record that separately; see TB-RISK-002.
        """
        return InstrumentIdentity(
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number="",
            firmware="",
            raw="%s,%s" % (MANUFACTURER, MODEL),
        )

    def check_errors(self) -> None:
        """No-op: the meter has no error queue to read."""

    # ------------------------------------------------------------------
    # Key presses
    # ------------------------------------------------------------------
    def press(self, key: str, retries: int = 2) -> None:
        """Press a front-panel key by name and confirm the meter took it.

        The meter echoes each character it accepts. An unechoed command was
        dropped, so it is sent again: at 9600 baud with no flow control on the
        data path, a lost keystroke is silent, and the meter is then measuring
        something other than what the test asked for.

        :param key: A name from :data:`.constants.KEYS`, such as ``"volts"``.
        :raises InstrumentError: The meter did not echo after *retries* tries.
        """
        try:
            character = KEYS[key]
        except KeyError as exc:
            raise InstrumentError(
                "the 1604 has no %r key; it has %s"
                % (key, ", ".join(sorted(KEYS)))
            ) from exc
        self._send_character(character, retries=retries)

    def _send_character(self, character: str, retries: int = 2) -> None:
        for attempt in range(retries + 1):
            self._transport.write(character.encode("ascii"), append_terminator=False)
            if self._await_echo(character):
                return
            _LOG.debug("1604 did not echo %r (attempt %d)", character, attempt + 1)
        raise InstrumentError(
            "the 1604 did not echo %r after %d attempts. The meter is not "
            "taking commands: check that DTR is asserted and RTS is not, since "
            "they power its interface." % (character, retries + 1)
        )

    def _await_echo(self, character: str) -> bool:
        """Wait for the meter's echo, ignoring measurement frames.

        The echo shares the link with the measurement stream, and a frame byte
        can equal the echoed character exactly, so frames are taken out of the
        stream first and the echo is looked for in what remains.
        """
        wanted = ord(character)
        deadline = time.monotonic() + ECHO_TIMEOUT
        while True:
            self._drain()
            if wanted in self._echoes:
                del self._echoes[: self._echoes.index(wanted) + 1]
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------
    def remote(self) -> None:
        """Put the meter into remote mode, so that it streams measurements."""
        self._send_character(REMOTE)
        self._remote = True

    def local(self) -> None:
        """Return the meter to front-panel control. It then streams nothing."""
        self._send_character(LOCAL)
        self._remote = False

    @property
    def is_remote(self) -> bool:
        """True once this driver has put the meter into remote mode."""
        return self._remote

    def select_volts(self) -> None:
        """Measure volts."""
        self.press("volts")

    def select_millivolts(self) -> None:
        """Measure millivolts."""
        self.press("millivolts")

    def select_amps(self) -> None:
        """Measure amps on the 10 A jack."""
        self.press("amps")

    def select_milliamps(self) -> None:
        """Measure milliamps on the mA jack."""
        self.press("milliamps")

    def select_ohms(self) -> None:
        """Measure resistance."""
        self.press("ohms")

    def select_ac(self) -> None:
        """Select AC coupling."""
        self.press("ac")

    def select_dc(self) -> None:
        """Select DC coupling."""
        self.press("dc")

    def select_auto_range(self) -> None:
        """Toggle auto-ranging."""
        self.press("auto")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self, timeout: Optional[float] = None) -> Reading:
        """Wait for the next complete measurement frame and decode it.

        :param timeout: How long to wait. Defaults to enough time for several
            readings at the meter's published 2.5 per second.
        :raises InstrumentError: Nothing arrived. The message distinguishes
            the two states in which a healthy 1604 is silent - local mode, and
            measurement circuits switched off - because both look identical
            from here and neither is a fault.
        """
        limit = SETTLING_TIME if timeout is None else float(timeout)
        deadline = time.monotonic() + limit
        while True:
            self._drain()
            if self._ready:
                frame = self._ready.pop(0)
                return decode(frame)
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        raise InstrumentError(
            "no measurement from the 1604 within %.1f s. A healthy meter is "
            "silent in exactly two states: not in remote mode (this driver "
            "%s put it there), and switched off at the Operate key - which "
            "does not affect this interface, so the link looks the same "
            "either way."
            % (limit, "has" if self._remote else "has not")
        )

    def read_many(self, count: int, timeout: Optional[float] = None) -> List[Reading]:
        """Collect *count* consecutive measurements."""
        return [self.read(timeout=timeout) for _ in range(max(0, int(count)))]

    def measure(self, settle: Optional[float] = None) -> Reading:
        """Discard one reading, then return the next.

        After a range or function change the meter emits a measurement that
        was taken under the previous setting. Throwing one away is the cheapest
        way not to attribute it to the new one.
        """
        time.sleep(READING_INTERVAL if settle is None else max(0.0, float(settle)))
        self.read()
        return self.read()

    # ------------------------------------------------------------------
    def _drain(self) -> None:
        """Move whatever the link has into frames and echoes.

        Frames are separated first and echoes are what remains, so a digit byte
        that happens to equal a key character cannot be mistaken for one.
        """
        try:
            data = self._transport.read_raw()
        except TransportError:
            # Nothing to read: a timeout on a real port, or a simulated link
            # with no reply pending. Neither is a fault - the meter is simply
            # not saying anything at this instant.
            data = b""
        if data:
            self._frames.feed(data)
        self._ready.extend(self._frames.frames())
        self._echoes.extend(self._frames.residue())
