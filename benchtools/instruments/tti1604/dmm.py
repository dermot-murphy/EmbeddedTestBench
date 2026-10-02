"""Driver for the TTi 1604 bench multimeter.

A 4-3/4 digit (40 000 count) true-RMS bench meter with an opto-isolated RS-232
interface. It is not a SCPI instrument and is not close to one: there is no
command language, no query, no ``*IDN?`` and no error queue. The link carries
single ASCII characters standing for front-panel key presses, and in remote
mode the meter streams a ten-byte binary frame after every measurement. This
driver therefore takes the transport and lifecycle from
:class:`~benchtools.core.scpi.ScpiInstrument` and replaces every SCPI-specific
part explicitly.

Six things about this meter shape the driver, and each is a way a naive
implementation reports a number that is not true - or none at all:

**The host powers the interface.** DTR must be asserted and RTS must not be;
the opto-isolated interface draws its power from them. Left at a serial
library's defaults, the meter is mute, and every obvious diagnosis is wrong.
See :data:`.constants.DTR_ASSERTED`.

**The link is a stream, not a conversation.** Nothing the meter sends ends a
message, so the driver reads whatever has arrived
(:meth:`~benchtools.core.transport.base.Transport.read_available`) rather than
waiting for an end-of-message a serial port never signals. Until #115 it did
the latter, and on a real port every read timed out with the bytes stranded
in the transport's buffer: connecting failed, and blamed DTR.

**Nothing arrives until the meter is put in remote mode.** Before ``u`` the
meter streams nothing whatsoever. :meth:`connect` enters remote mode by default
and :meth:`read` says which state it was in when it found nothing.

**The stream has no gaps to synchronise on.** Frames run back to back, so a
reader can land mid-frame. Frames are found by their leading carriage return
and *validated* - every display byte must be a pattern the meter draws - and
echoes are recovered as what is left over; see
:class:`~benchtools.instruments.tti1604.protocol.FrameAssembler`.

**A key press is not evidence.** Some keys toggle, and an echo can be lost
after the meter acted on the key, so a resend undoes it while the echo says all
is well. Every ``select_*`` and range call presses its key and then waits for a
reading that *shows* the requested state, and raises if none does
(DMM-FR-029). The readings carry the meter's whole state; they are the only
evidence the driver accepts.

**A held display is not a live measurement, and an old reading is not a new
one.** Hold, Touch-Hold and the Min-Max review freeze the display, and
:attr:`~.protocol.Reading.held` says so. Separately, the meter keeps streaming
while nobody reads and the operating system keeps what it sends, so
:meth:`measure` discards everything waiting before it takes a reading
(DMM-FR-031).

Traces to: DMM-FR-001 .. DMM-FR-033, DMM-FR-045, DMM-ARC-001, DMM-DD-DMM.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Callable, List, Optional, Tuple

from ...core.errors import (
    ConnectionFailedError,
    InstrumentError,
    TransportError,
)
from ...core.instrument import InstrumentIdentity
from ...core.scpi import ScpiInstrument
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    CONFIRM_TIMEOUT,
    DEFAULT_BAUDRATE,
    DTR_ASSERTED,
    ECHO_TIMEOUT,
    FREQUENCY_RANGES,
    GATE_TIME,
    KEYS,
    LOCAL,
    MANUFACTURER,
    MODEL,
    RANGES,
    READ_POLL,
    REMOTE,
    RTS_ASSERTED,
    SETTLING_TIME,
    MeterRange,
)
from .protocol import FrameAssembler, Reading, decode
from .simulator import SimulatedTti1604

__all__ = ["Tti1604"]

_LOG = logging.getLogger(__name__)

#: Measurement type selected by each ``select_*`` key, by key name.
_TYPE_OF_KEY = {"millivolts": 1, "volts": 2, "milliamps": 3, "amps": 4, "ohms": 5}
_TYPE_NAMES = {1: "millivolts", 2: "volts", 3: "milliamps", 4: "amps", 5: "ohms"}


class Tti1604(ScpiInstrument):  # pylint: disable=too-many-public-methods,too-many-instance-attributes
    """A TTi 1604 bench multimeter on a serial link.

    Example::

        with Tti1604.connect("/dev/ttyUSB0") as dmm:
            dmm.select_milliamps()
            dmm.select_dc()
            reading = dmm.measure()
            if not reading.is_live:
                raise SystemExit("overrange, or the display is frozen: not a reading")
            print(reading.value, reading.unit)

    :param clock: The clock every deadline is measured on. Real time on a
        port; a simulated meter's virtual clock when talking to one, so that a
        20 s wait for the 10 s frequency gate takes a test no time at all.
    """

    SIMULATOR_CLASS = SimulatedTti1604
    MODEL_NAME = MODEL

    def __init__(
        self,
        transport: Transport,
        auto_check_errors: bool = False,
        owns_transport: bool = True,
        enter_remote: bool = True,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        super().__init__(
            transport,
            auto_check_errors=auto_check_errors,
            owns_transport=owns_transport,
        )
        self._enter_remote = bool(enter_remote)
        self._frames = FrameAssembler()
        self._ready: List[Reading] = []
        self._echoes = bytearray()
        self._remote = False
        self._last: Optional[Reading] = None
        self._clock = clock if clock is not None else self._default_clock(transport)
        self._virtual = clock is None and self._clock is not time.monotonic

    @staticmethod
    def _default_clock(transport: Transport) -> Callable[[], float]:
        """The simulator's virtual clock for a simulated link; real time otherwise."""
        simulator = getattr(transport, "simulator", None)
        if isinstance(simulator, SimulatedTti1604):
            return lambda: simulator.clock
        return time.monotonic

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
    # The byte stream
    # ------------------------------------------------------------------
    def _receive(self, deadline: float) -> bool:
        """Wait, no later than *deadline*, for more bytes. ``False`` if none came.

        Reads whatever has arrived rather than waiting for an end-of-message
        the meter never sends (DMM-FR-027). Each read waits at most
        :data:`.constants.READ_POLL`, and the caller loops to its own deadline.
        The transport's timeout is set to that once and then left alone: on
        Windows, pyserial loses bytes in flight whenever it is changed
        (TB-SWE3-002 LL-07), so varying it per read would drop parts of frames.
        """
        remaining = deadline - self._clock()
        if remaining <= 0.0:
            return False
        if self._transport.timeout != READ_POLL:
            self._transport.timeout = READ_POLL
        started = self._clock()
        try:
            data = self._transport.read_available()
        except ConnectionFailedError:
            raise
        except TransportError:
            # Nothing within the poll: a timeout on a real port. A link that
            # answers "nothing" at once is paced here, so that a deadline on
            # real time is not reached by spinning.
            if not self._virtual and self._clock() - started < 0.001:
                time.sleep(min(0.005, remaining))
            return False
        self._frames.feed(data)
        for frame in self._frames.frames():
            self._ready.append(decode(frame))
        self._echoes.extend(self._frames.residue())
        return True

    def _drain(self) -> None:
        """Take in whatever the transport already holds, without waiting.

        :meth:`Transport.write` discards buffered input, which is right for
        SCPI and wrong here: those bytes may be half of a frame.
        """
        while self._transport.has_buffered_data:
            self._frames.feed(self._transport.read_available())
        for frame in self._frames.frames():
            self._ready.append(decode(frame))
        self._echoes.extend(self._frames.residue())

    def _next_frame(self, timeout: float) -> Optional[Reading]:
        """The next frame to arrive, whenever it was measured, or ``None``."""
        deadline = self._clock() + timeout
        while not self._ready:
            if not self._receive(deadline):
                if self._clock() >= deadline:
                    return None
        reading = self._ready.pop(0)
        self._last = reading
        return reading

    def _discard_input(self) -> None:
        """Forget everything received so far, however long it has waited."""
        dropped = self._transport.discard_input() + self._frames.pending()
        self._frames.clear()
        self._ready.clear()
        self._echoes.clear()
        if dropped:
            _LOG.debug("discarded %d byte(s) of stale readings", dropped)

    def _patience(self, gate_ten_seconds: Optional[bool] = None) -> float:
        """Seconds to wait for a reading, allowing for the frequency gate.

        Measuring frequency the meter reads once per gate - 1 s, or 10 s on the
        4 kHz range - not 2.5 times a second, so a wait sized for the second
        gives up on the first (DMM-FR-032). *gate_ten_seconds* names the gate
        to allow for; ``None`` takes it from the last reading.
        """
        if gate_ten_seconds is None:
            last = self._last
            if last is None or not last.flags.get("hertz"):
                return SETTLING_TIME
            gate_ten_seconds = bool(last.status.get("gate_ten_seconds"))
        return SETTLING_TIME + 2 * GATE_TIME[gate_ten_seconds]

    # ------------------------------------------------------------------
    # Key presses
    # ------------------------------------------------------------------
    def press(self, key: str, retries: int = 2) -> None:
        """Press a front-panel key by name and confirm the meter took it.

        The meter echoes each character it accepts. An unechoed command was
        dropped, so it is sent again: at 9600 baud with no flow control on the
        data path, a lost keystroke is silent, and the meter is then measuring
        something other than what the test asked for.

        This confirms only that the meter heard the key. The ``select_*`` and
        range methods also confirm that it did what the key means.

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
        wanted = ord(character)
        for attempt in range(retries + 1):
            self._drain()
            # Nothing received before this write can be its echo.
            self._echoes.clear()
            self._transport.write(character.encode("ascii"), append_terminator=False)
            deadline = self._clock() + ECHO_TIMEOUT
            while True:
                if wanted in self._echoes:
                    del self._echoes[: self._echoes.index(wanted) + 1]
                    if attempt:
                        _LOG.info("1604 echoed %r on attempt %d", character, attempt + 1)
                    return
                if not self._receive(deadline) and self._clock() >= deadline:
                    break
            _LOG.debug("1604 did not echo %r (attempt %d)", character, attempt + 1)
        raise InstrumentError(
            "the 1604 did not echo %r after %d attempts. The meter is not "
            "taking commands: check that DTR is asserted and RTS is not, since "
            "they power its interface, that the converter drives them to about "
            "+9 V and -9 V, and that the cable is a straight-through 9-way with "
            "every pin connected." % (character, retries + 1)
        )

    # ------------------------------------------------------------------
    # Confirmation from the readings
    # ------------------------------------------------------------------
    def current_state(self) -> Reading:
        """A reading received now: what the meter is set to, and showing."""
        self._discard_input()
        reading = self._next_frame(self._patience(gate_ten_seconds=True))
        if reading is None:
            raise self._silence(self._patience(gate_ten_seconds=True))
        return reading

    def _await(
        self,
        description: str,
        condition: Callable[[Reading], bool],
        timeout: Optional[float] = None,
    ) -> Reading:
        """Wait for a reading satisfying *condition*, or say what the meter shows.

        :raises InstrumentError: No reading showed the state asked for. A key
            may have been refused with a beep, lost after a resend undid it,
            or the front panel may be in use.
        """
        allowed = max(CONFIRM_TIMEOUT, self._patience()) if timeout is None else timeout
        deadline = self._clock() + allowed
        latest = self._last
        while self._clock() < deadline:
            reading = self._next_frame(deadline - self._clock())
            if reading is None:
                break
            latest = reading
            if condition(reading):
                return reading
        shown = "nothing" if latest is None else "%s on the %s range, %s" % (
            latest.function, latest.range_label or latest.range_description,
            "auto" if latest.flags.get("auto_range") else "manual")
        raise InstrumentError(
            "asked the 1604 for %s, but within %.1f s its readings show %s. A key "
            "may have been refused (the meter beeps) or the front panel may be "
            "in use." % (description, allowed, shown)
        )

    def _confirming(self) -> bool:
        """Whether readings are arriving to confirm a key by."""
        return self._remote

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

    # ------------------------------------------------------------------
    # Function
    # ------------------------------------------------------------------
    def _select_type(self, key: str) -> Reading:
        """Press a measurement key and confirm the meter changed to it."""
        wanted = _TYPE_OF_KEY[key]
        self.press(key)
        if not self._confirming():
            return self._last  # type: ignore[return-value]
        return self._await(
            _TYPE_NAMES[wanted],
            lambda reading: (reading.raw[1] & 0x07) == wanted and not reading.flags.get("hertz"),
        )

    def select_volts(self) -> Reading:
        """Measure volts, and confirm it from the readings."""
        return self._select_type("volts")

    def select_millivolts(self) -> Reading:
        """Measure millivolts (the 400 mV range)."""
        return self._select_type("millivolts")

    def select_amps(self) -> Reading:
        """Measure amps on the 10 A jack. Puts the shunt across the input."""
        return self._select_type("amps")

    def select_milliamps(self) -> Reading:
        """Measure milliamps on the mA jack. Puts the shunt across the input."""
        return self._select_type("milliamps")

    def select_ohms(self) -> Reading:
        """Measure resistance."""
        return self._select_type("ohms")

    def _select_coupling(self, ac: bool) -> Reading:
        if self._confirming():
            state = self._last if self._last is not None else self.current_state()
            if state.measurement in ("ohms", "continuity", "diode"):
                raise InstrumentError(
                    "the 1604 is measuring %s, which has no AC or DC; select volts "
                    "or amps first" % state.measurement
                )
        self.press("ac" if ac else "dc")
        if not self._confirming():
            return self._last  # type: ignore[return-value]
        return self._await(
            "AC" if ac else "DC",
            lambda reading: reading.ac is ac and not reading.flags.get("hertz"),
        )

    def select_ac(self) -> Reading:
        """Select AC coupling, and confirm it."""
        return self._select_coupling(True)

    def select_dc(self) -> Reading:
        """Select DC coupling, and confirm it."""
        return self._select_coupling(False)

    def select_hertz(self) -> Reading:
        """Measure frequency on the present AC function, and confirm it.

        The meter accepts Hz only on an AC range, and refuses it with a beep
        otherwise, so this checks first rather than wait for a change that
        will not come. Readings then arrive once per gate (DMM-FR-033).
        """
        state = self.current_state()
        if state.flags.get("hertz"):
            return state
        if not state.ac or state.measurement not in ("volts", "millivolts", "milliamps", "amps"):
            raise InstrumentError(
                "frequency is measured on an AC volts or AC current range; the 1604 "
                "is on %s" % state.function
            )
        self.press("hertz")
        return self._await(
            "frequency",
            lambda reading: bool(reading.flags.get("hertz")),
            timeout=CONFIRM_TIMEOUT + self._patience(gate_ten_seconds=False),
        )

    # ------------------------------------------------------------------
    # Range
    # ------------------------------------------------------------------
    def select_auto_range(self) -> Reading:
        """Turn auto-ranging on, and confirm it.

        Idempotent: nothing is pressed if the meter is already auto-ranging.
        Until #115 this pressed Auto/Man, which toggles, so the caller could not
        know which state the meter was left in.
        """
        state = self.current_state()
        if state.flags.get("hertz"):
            raise InstrumentError(
                "the frequency function has no auto range; use set_range(4000) or "
                "set_range(40000) to choose the gate"
            )
        if state.flags.get("auto_range"):
            return state
        self.press("auto")
        return self._await("auto ranging", lambda reading: bool(reading.flags.get("auto_range")))

    def set_range(self, full_scale: float) -> Reading:
        """Lock the meter on a range, named by its full scale in SI units.

        ``set_range(40)`` on DC volts selects the 40 V range; ``set_range(4e-3)``
        on DC milliamps the 4 mA range; ``set_range(4000)`` measuring frequency
        the 4 kHz range (10 s gate). Each step is confirmed from the readings
        (DMM-FR-030).

        :raises InstrumentError: for a full scale the function does not have,
            naming the ones it has.
        """
        state = self.current_state()
        choices = self._ranges(state)
        target = None
        for candidate in choices:
            if math.isclose(candidate.full_scale, float(full_scale), rel_tol=1e-6):
                target = candidate
        if target is None:
            raise InstrumentError(
                "%s has no %g range; its ranges are %s"
                % (state.function, full_scale,
                   ", ".join("%s (%g)" % (item.label, item.full_scale) for item in choices)
                   or "none the driver knows")
            )
        if state.flags.get("hertz"):
            ten_seconds = target is FREQUENCY_RANGES[True]
            if bool(state.status.get("gate_ten_seconds")) != ten_seconds:
                self.press("down" if ten_seconds else "up")
            return self._await(
                "the %s frequency range" % target.label,
                lambda reading: bool(reading.status.get("gate_ten_seconds")) == ten_seconds,
                timeout=CONFIRM_TIMEOUT + self._patience(gate_ten_seconds=True),
            )
        order = [candidate.code for candidate in choices]
        wanted = order.index(target.code)
        current = state
        # One step per pass, each confirmed; the bound stops a meter that
        # ignores its keys from holding the driver for ever.
        for _ in range(len(order) + 1):
            if current.range_index == target.code and not current.flags.get("auto_range"):
                return current
            here = order.index(current.range_index) if current.range_index in order else 0
            if here == wanted:
                # On the right range but auto-ranging: Auto/Man "locks the
                # meter in its present range".
                self.press("auto")
            else:
                self.press("up" if wanted > here else "down")
            before = (current.range_index, current.flags.get("auto_range"))
            current = self._await(
                "a range change",
                lambda reading, was=before: (
                    (reading.range_index, reading.flags.get("auto_range")) != was),
            )
        return self._await(
            "the %s range" % target.label,
            lambda reading: (reading.range_index == target.code
                             and not reading.flags.get("auto_range")),
        )

    @staticmethod
    def _ranges(state: Reading) -> Tuple[MeterRange, ...]:
        if state.flags.get("hertz"):
            return (FREQUENCY_RANGES[True], FREQUENCY_RANGES[False])
        measurement_type = state.raw[1] & 0x07 if state.raw else 0
        ac = state.ac and measurement_type != 5
        return RANGES.get((measurement_type, ac), ())

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def _silence(self, waited: float) -> InstrumentError:
        return InstrumentError(
            "no measurement from the 1604 within %.1f s. A healthy meter is "
            "silent in exactly two states: not in remote mode (this driver "
            "%s put it there), and switched off at the Operate key - which "
            "does not affect this interface, so the link looks the same "
            "either way."
            % (waited, "has" if self._remote else "has not")
        )

    def read(self, timeout: Optional[float] = None) -> Reading:
        """The next complete measurement frame, decoded.

        :param timeout: How long to wait. Defaults to the settling time, plus
            two gate times when the meter is measuring frequency.
        :raises InstrumentError: Nothing arrived. The message distinguishes
            the two states in which a healthy 1604 is silent - local mode, and
            measurement circuits switched off - because both look identical
            from here and neither is a fault.
        """
        limit = self._patience() if timeout is None else float(timeout)
        reading = self._next_frame(limit)
        if reading is None:
            raise self._silence(limit)
        return reading

    def read_many(self, count: int, timeout: Optional[float] = None) -> List[Reading]:
        """Collect *count* consecutive measurements."""
        return [self.read(timeout=timeout) for _ in range(max(0, int(count)))]

    def measure(self, settle: Optional[float] = None) -> Reading:
        """A reading measured wholly after this call.

        Everything already received is discarded - the operating system's
        buffer included, where a meter that streams while nobody reads leaves
        readings minutes old - and then the next complete frame too, because it
        may have been measured partly before the call, or under a setting just
        changed (DMM-FR-031). The one after that is returned.

        :param settle: Extra seconds to wait before discarding, for a circuit
            that needs time to settle. On a simulated meter this is not slept.
        """
        if settle and not self._virtual:
            time.sleep(max(0.0, float(settle)))
        self._discard_input()
        self.read()
        return self.read()

    @property
    def last_reading(self) -> Optional[Reading]:
        """The most recent reading received, whenever that was."""
        return self._last

    @property
    def resynchronised_bytes(self) -> int:
        """Carriage returns passed over because they did not start a frame."""
        return self._frames.resynchronised
