"""Driver for the TTi (Thurlby Thandar) 1604 bench multimeter.

A 40,000-count mains bench meter with an opto-isolated RS-232 port on a
9-way D-type at the back. It is not a SCPI instrument, and not a
command/response one either:

* It is **driven by pretending to press its keys.** Each front-panel key has
  a character; the meter echoes it to acknowledge it, and the host must resend
  a key that is not echoed within 300 ms.
* It **reports by streaming.** In remote mode it sends a ten-character frame
  after every measurement, 2.5 times a second, whether anyone is reading or
  not. The frame is a picture of the display - seven-segment patterns and the
  annunciators - rather than a number.
* It **cannot be asked what it is.** There is no identification query.

So this driver subclasses :class:`~benchtools.core.instrument.Instrument`
directly, as the J-Link and BLE dongle drivers do, and builds three things on
top of the transport:

**A stream parser.** Echoes and frames arrive on the same line, in whatever
order the meter produces them. Frames are found by their leading carriage
return and *validated* - every display character must be a pattern the meter
sends - so a stream joined part-way through a frame resynchronises instead of
decoding garbage. An echo is any byte outside a frame; it is never searched
for inside one, because some display patterns are letters (the digit 4 is
``'f'``, which is also the Volts key).

**Closed-loop control.** Because keys toggle, a lost echo is ambiguous: the
meter may have acted on the key and only the echo was lost, and resending a
toggle undoes it. The driver therefore never trusts a key press. After
selecting a function or a range it waits for a frame showing the state it
asked for, and raises if one does not arrive. The frame is the only evidence
of what the meter is doing, so it is the only evidence the driver accepts.

**Fresh readings.** The meter keeps streaming while nobody reads, and the
operating system buffers what it sends: an unguarded read returns a reading
that may be minutes old. A measurement discards everything already received,
then discards the first complete frame as well - it may have been measured
before the request - and returns the one after.

Traces to: DMM-FR-001 .. DMM-FR-033, DMM-NFR-002, DMM-ARC-001, DMM-DD-DMM.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Callable, List, Optional, Tuple

from ...core.errors import (
    BenchToolsError,
    ConfigurationError,
    InstrumentError,
    MeasurementError,
    ProtocolError,
    TransportTimeoutError,
)
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    BAUDRATE,
    CURRENT_FUNCTIONS,
    DTR_LEVEL,
    ECHO_TIMEOUT,
    FRAME_LENGTH,
    FRAME_START,
    FREQUENCY_RANGES,
    FUNCTION_KEYS,
    MANUFACTURER,
    MODEL,
    RANGES,
    RTS_LEVEL,
    SELECTABLE_FUNCTIONS,
    SEND_ATTEMPTS,
    SETTLE_TIMEOUT,
    Function,
    Key,
    MeterRange,
)
from .frame import Reading, decode_frame
from .simulator import SimulatedTti1604

__all__ = ["Tti1604"]

_LOG = logging.getLogger(__name__)

#: AC functions the Hz key can be pressed from, and the one chosen when the
#: meter is on none of them.
_FREQUENCY_SOURCES: Tuple[str, ...] = (
    Function.AC_VOLTS,
    Function.AC_MILLIVOLTS,
    Function.AC_MILLIAMPS,
    Function.AC_AMPS,
)


class Tti1604(Instrument):
    """A TTi 1604 bench multimeter on a serial port.

    :param transport: A link to the meter: a serial port with DTR asserted and
        RTS negated (``connect`` arranges that), or a simulated one.
    :param echo_timeout: Seconds to wait for a key's echo before resending it.
    :param attempts: Times a key is sent before the driver gives up.
    :param settle_timeout: Seconds a function or range change may take to show
        in the readings.
    :param clock: The clock deadlines are measured on. ``connect`` passes the
        simulator's virtual clock for a ``sim://`` resource.
    :param owns_transport: Close the transport when the meter is closed.

    Example::

        from benchtools.instruments.tti1604 import Tti1604

        with Tti1604.connect("/dev/ttyUSB1") as dmm:
            amps = dmm.measure_dc_current()          # mA socket, autoranged
            print("%.4f mA" % (amps * 1e3))
    """

    SIMULATOR_CLASS = SimulatedTti1604
    MODEL_NAME = "TTi 1604"

    def __init__(
        self,
        transport: Transport,
        echo_timeout: float = ECHO_TIMEOUT,
        attempts: int = SEND_ATTEMPTS,
        settle_timeout: float = SETTLE_TIMEOUT,
        clock: Optional[Callable[[], float]] = None,
        owns_transport: bool = True,
        auto_check_errors: bool = False,
    ) -> None:
        super().__init__(auto_check_errors=auto_check_errors)
        if echo_timeout <= 0.0:
            raise ConfigurationError("echo_timeout must be positive, got %r" % (echo_timeout,))
        if attempts < 1:
            raise ConfigurationError("attempts must be at least 1, got %r" % (attempts,))
        self._transport = transport
        self._owns_transport = bool(owns_transport)
        self._echo_timeout = float(echo_timeout)
        self._attempts = int(attempts)
        self._settle_timeout = float(settle_timeout)
        self._clock = clock if clock is not None else self._default_clock(transport)
        #: Bytes received and not yet parsed into a frame or an echo.
        self._pending = bytearray()
        self._last: Optional[Reading] = None
        #: Bytes dropped while looking for a frame start - a count, for
        #: diagnosing a noisy link, not an error.
        self.resynchronised_bytes = 0

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
    def connect(
        cls,
        resource: str = "sim://",
        timeout: float = 5.0,
        echo_timeout: float = ECHO_TIMEOUT,
        attempts: int = SEND_ATTEMPTS,
        settle_timeout: float = SETTLE_TIMEOUT,
        initialise: bool = True,
        **_ignored,
    ) -> "Tti1604":
        """Open a meter.

        :param resource: ``/dev/ttyUSB1``, ``COM6``, ``serial://COM6``,
            ``serial://socket://bench-pc:4003`` for a port published over TCP,
            or ``sim://``. A bare port name is a serial port, not a host.
        :param timeout: Seconds to wait for a reading before giving up.
        :param echo_timeout: Seconds to wait for a key's echo before resending.
        :param attempts: Times a key is sent before the driver gives up.
        :param settle_timeout: Seconds a function or range change may take to
            show in the readings.

        Other keyword arguments are ignored, as a bench configuration may carry
        options meant for other drivers.

        The line settings are the meter's and are not configurable: 9600 baud,
        8 data bits, no parity, 1 stop bit, DTR asserted and RTS negated to
        power its interface.
        """
        target = cls._normalise_resource(resource)
        serial_settings = {}
        if target.startswith("serial://"):
            serial_settings = {
                "baudrate": BAUDRATE,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "dtr": DTR_LEVEL,
                "rts": RTS_LEVEL,
            }
        transport = open_transport(
            target,
            timeout=timeout,
            open_now=False,
            responder_factory=cls.SIMULATOR_CLASS,
            **serial_settings,
        )
        instrument = cls(
            transport,
            echo_timeout=echo_timeout,
            attempts=attempts,
            settle_timeout=settle_timeout,
        )
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
        lowered = text.lower()
        if "://" in text or lowered in ("sim", "mock"):
            return text
        return "serial://%s" % text

    @property
    def transport(self) -> Transport:
        """The link to the meter."""
        return self._transport

    @property
    def is_open(self) -> bool:
        return self._transport.is_open

    def _open(self) -> None:
        self._transport.open()
        self._pending.clear()

    def _close(self) -> None:
        """Hand the meter back to its front panel, then release the port.

        Best effort: a meter that has gone away must not turn closing into an
        error that hides whatever went wrong before it.
        """
        if self._transport.is_open:
            try:
                self._press(Key.LOCAL, attempts=2)
            except BenchToolsError:
                _LOG.debug("the meter did not acknowledge local mode", exc_info=True)
            if self._owns_transport:
                self._transport.close()

    def _post_open(self) -> None:
        """Put the meter in remote mode and wait for its first reading.

        Remote mode is what makes the meter send readings; it does not change
        the function, range or anything else on the front panel. A reading is
        waited for because an echo alone proves only that the interface is
        powered: a meter in standby echoes keys and measures nothing.
        """
        self._press(Key.REMOTE)
        # The meter may have been left on the 10 s frequency gate, when its
        # next reading can be ten seconds away.
        wait = self._patience(gate_10s=True)
        try:
            self._last = self._next_frame(wait)
        except MeasurementError as exc:
            raise InstrumentError(
                "the 1604 acknowledged remote mode but sent no reading within "
                "%.1f s. It is probably in standby: press Operate on the front "
                "panel." % wait
            ) from exc
        self._identity = self._read_identity()

    def _read_identity(self) -> InstrumentIdentity:
        """What the meter is - asserted, because it cannot be asked.

        The 1604 has no identification query. The identity is established by
        the meter behaving as a 1604 and nothing else does: echoing its key
        characters and sending frames that decode. It carries no serial number
        or firmware revision, and says so rather than inventing them.
        """
        return InstrumentIdentity(
            raw="%s,%s,," % (MANUFACTURER, MODEL),
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number="",
            firmware="",
        )

    # ------------------------------------------------------------------
    # The byte stream
    # ------------------------------------------------------------------
    def _drain_transport(self) -> None:
        """Move bytes the transport has buffered into the parser, without waiting.

        :meth:`Transport.write` discards buffered input, which is right for
        SCPI and wrong here: those bytes may be half of a frame.
        """
        while self._transport.has_buffered_data:
            self._pending += self._transport.read_available()

    def _receive(self, deadline: float) -> bool:
        """Wait, no later than *deadline*, for more bytes. ``False`` if none came."""
        remaining = deadline - self._clock()
        if remaining <= 0.0:
            return False
        previous = self._transport.timeout
        self._transport.timeout = max(remaining, 0.001)
        try:
            self._pending += self._transport.read_available()
        except TransportTimeoutError:
            return False
        finally:
            self._transport.timeout = previous
        return True

    def _parse(self) -> Optional[Tuple[str, object]]:
        """Take one event from the front of the received bytes.

        :returns: ``("frame", Reading)``, ``("byte", int)`` for a byte outside
            any frame - an echo, or line noise - or ``None`` when more bytes are
            needed.
        """
        buffer = self._pending
        while buffer:
            if buffer[0] == FRAME_START:
                if len(buffer) < FRAME_LENGTH:
                    return None
                try:
                    reading = decode_frame(bytes(buffer[:FRAME_LENGTH]), self._clock())
                except ProtocolError as exc:
                    # A carriage return that does not start a valid frame: a
                    # stream joined part-way through. Drop it and look again.
                    _LOG.debug("resynchronising: %s", exc)
                    del buffer[0]
                    self.resynchronised_bytes += 1
                    continue
                del buffer[:FRAME_LENGTH]
                return ("frame", reading)
            value = buffer.pop(0)
            if value == 0:
                continue                         # the frame's NUL terminator
            return ("byte", value)
        return None

    def _next_event(self, deadline: float) -> Optional[Tuple[str, object]]:
        while True:
            event = self._parse()
            if event is not None:
                if event[0] == "frame":
                    self._last = event[1]        # type: ignore[assignment]
                return event
            if not self._receive(deadline):
                return None

    def _discard_input(self) -> None:
        """Forget everything received so far, however long it has been waiting."""
        dropped = self._transport.discard_input() + len(self._pending)
        self._pending.clear()
        if dropped:
            _LOG.debug("discarded %d byte(s) of stale readings", dropped)

    def _next_frame(self, timeout: float) -> Reading:
        """The next complete frame, whenever it was measured."""
        deadline = self._clock() + timeout
        while True:
            event = self._next_event(deadline)
            if event is None:
                raise MeasurementError(
                    "no reading from the 1604 within %.1f s: is it in remote "
                    "mode, operating, and connected with DTR and RTS powering its "
                    "interface?" % timeout
                )
            if event[0] == "frame":
                return event[1]                  # type: ignore[return-value]
            _LOG.debug("byte 0x%02X outside a frame", event[1])

    # ------------------------------------------------------------------
    # Keys
    # ------------------------------------------------------------------
    def press(self, key: str) -> int:
        """Press one front-panel key, by its character; see :class:`.constants.Key`.

        Low-level: this does not check that the meter did what the key means.
        :meth:`select_function`, :meth:`set_range` and :meth:`set_auto_range`
        press keys *and* confirm the result from the readings.

        :returns: The attempt on which the echo arrived.
        """
        if key not in Key.ALL:
            raise ConfigurationError(
                "%r is not a 1604 key character; expected one of %s"
                % (key, " ".join(Key.ALL))
            )
        return self._press(key)

    def _press(self, key: str, attempts: Optional[int] = None) -> int:
        """Send *key* until it is echoed, resending after each silent 300 ms."""
        tries = self._attempts if attempts is None else attempts
        wanted = ord(key)
        for attempt in range(1, tries + 1):
            self._drain_transport()
            self._transport.write(key.encode("ascii"), append_terminator=False)
            deadline = self._clock() + self._echo_timeout
            while True:
                event = self._next_event(deadline)
                if event is None:
                    break
                if event[0] == "byte" and event[1] == wanted:
                    if attempt > 1:
                        _LOG.info("key %r acknowledged on attempt %d", key, attempt)
                    return attempt
            _LOG.debug("no echo of %r within %.3f s (attempt %d of %d)",
                       key, self._echo_timeout, attempt, tries)
        raise ProtocolError(
            "the 1604 did not echo key %r in %d attempt(s). Check that the cable is "
            "a straight 9-way with all pins connected, that the meter has mains "
            "power, and that the USB converter drives DTR to about +9 V and RTS to "
            "about -9 V - the meter's interface is powered from them, and some "
            "converters only reach +/-5 V." % (key, tries)
        )

    # ------------------------------------------------------------------
    # State, as the readings report it
    # ------------------------------------------------------------------
    @property
    def last_reading(self) -> Optional[Reading]:
        """The most recent frame received, whenever that was."""
        return self._last

    def _patience(self, gate_10s: Optional[bool] = None) -> float:
        """Seconds to wait for a frame, allowing for the frequency gate.

        On most functions the meter reads 2.5 times a second. Measuring
        frequency it reads once per gate - 1 s, or 10 s on the 4 kHz range - so
        a wait sized for the first would give up on the second. *gate_10s*
        names the gate to allow for; ``None`` takes it from the last reading.

        Traces to: DMM-FR-070.
        """
        if gate_10s is None:
            last = self._last
            if last is None or last.function != Function.FREQUENCY:
                return self._settle_timeout
            gate_10s = last.gate_10s
        return self._settle_timeout + 2 * (10.0 if gate_10s else 1.0)

    def current_state(self) -> Reading:
        """A frame received now: what the meter is set to, and showing."""
        self._discard_input()
        return self._next_frame(self._patience())

    def _await(
        self,
        description: str,
        condition: Callable[[Reading], bool],
        timeout: Optional[float] = None,
    ) -> Reading:
        """Wait for a frame satisfying *condition*, or say what the meter shows."""
        allowed = self._patience() if timeout is None else float(timeout)
        deadline = self._clock() + allowed
        latest = self._last
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0.0:
                break
            try:
                latest = self._next_frame(remaining)
            except MeasurementError:
                break
            if condition(latest):
                return latest
        shown = "nothing" if latest is None else "%s on the %s range%s" % (
            latest.function, latest.range_label,
            ", auto" if latest.auto_range else ", manual")
        raise ConfigurationError(
            "asked the 1604 for %s, but within %.1f s its readings show %s. A key "
            "may have been rejected (the meter beeps), or the front panel may be "
            "in use." % (description, allowed, shown)
        )

    # ------------------------------------------------------------------
    # Function and range
    # ------------------------------------------------------------------
    def select_function(self, function: str) -> Reading:
        """Select what the meter measures, and confirm it from the readings.

        :param function: One of :data:`.constants.SELECTABLE_FUNCTIONS`:
            ``dc_volts``, ``ac_volts``, ``dc_millivolts``, ``ac_millivolts``,
            ``dc_milliamps``, ``ac_milliamps``, ``dc_amps``, ``ac_amps``,
            ``ohms`` or ``frequency``.

        Changing function sets auto-ranging, as it does from the front panel.
        Nothing is pressed if the meter is already on *function*.

        **The current functions move the input to a different socket.** The
        driver cannot see where the leads are: ``dc_milliamps`` measures
        through the mA socket (to 400 mA), ``dc_amps`` through the 10 A
        socket. Selecting a current function with the leads across a voltage
        source puts the meter's shunt across that source.

        Frequency is measured on an AC range; if the meter is on none, AC volts
        is selected first. Use :meth:`measure_frequency` to choose the source.
        """
        if function not in SELECTABLE_FUNCTIONS:
            raise ConfigurationError(
                "the 1604 driver cannot select %r; it can select %s"
                % (function, ", ".join(SELECTABLE_FUNCTIONS))
            )
        state = self.current_state()
        if state.function == function:
            return state
        if function == Function.FREQUENCY:
            if state.function not in _FREQUENCY_SOURCES:
                self._select(Function.AC_VOLTS)
            self._press(Key.HERTZ)
            return self._await(
                "frequency",
                lambda reading: reading.function == Function.FREQUENCY,
                timeout=self._patience(gate_10s=False),
            )
        return self._select(function)

    def _select(self, function: str) -> Reading:
        for key in FUNCTION_KEYS[function]:
            self._press(key)
        return self._await(
            function.replace("_", " "),
            lambda reading: reading.function == function,
        )

    def set_auto_range(self) -> Reading:
        """Let the meter choose its range, and confirm it from the readings."""
        state = self.current_state()
        if state.function == Function.FREQUENCY:
            raise ConfigurationError(
                "the frequency function has no auto range; use set_range(4000) "
                "or set_range(40000) to choose the gate time"
            )
        if not state.auto_range:
            self._press(Key.AUTO)
        return self._await("auto ranging", lambda reading: reading.auto_range)

    def set_range(self, full_scale: float) -> Reading:
        """Lock the meter on a range, named by its full scale in SI units.

        ``set_range(40)`` on DC volts selects the 40 V range; ``set_range(4e-3)``
        on DC milliamps the 4 mA range; ``set_range(4000)`` on frequency the
        4 kHz range. Manual ranging stops the meter ranging back and forth
        between readings, at the cost of OFL if the input exceeds the range.

        :raises ConfigurationError: for a full scale the function does not
            have, naming the ones it does.
        """
        state = self.current_state()
        choices = self._ranges(state.function)
        target = None
        for candidate in choices:
            if math.isclose(candidate.full_scale, float(full_scale), rel_tol=1e-6):
                target = candidate
        if target is None:
            raise ConfigurationError(
                "%s has no %g range; its ranges are %s"
                % (state.function, full_scale,
                   ", ".join("%s (%g)" % (item.label, item.full_scale) for item in choices))
            )
        if state.function == Function.FREQUENCY:
            want_gate = target is FREQUENCY_RANGES[True]
            if state.gate_10s != want_gate:
                self._press(Key.DOWN if want_gate else Key.UP)
            return self._await(
                "the %s frequency range" % target.label,
                lambda reading: reading.gate_10s == want_gate,
                timeout=self._patience(gate_10s=True),
            )
        order = [item.code for item in choices]
        wanted = order.index(target.code)
        current = state
        # Each pass moves one step and confirms it from the readings; the bound
        # stops a meter that ignores its keys from holding the driver forever.
        for _ in range(len(order) + 1):
            if current.range_code == target.code and not current.auto_range:
                return current
            here = order.index(current.range_code) if current.range_code in order else 0
            if here == wanted:
                # On the right range but auto-ranging: Auto/Man "locks the
                # meter in its present range".
                self._press(Key.AUTO)
            else:
                self._press(Key.UP if wanted > here else Key.DOWN)
            current = self._await(
                "a range change",
                lambda reading, before=current: (reading.range_code != before.range_code
                                                 or reading.auto_range != before.auto_range),
            )
        return self._await(
            "the %s range" % target.label,
            lambda reading: reading.range_code == target.code and not reading.auto_range,
        )

    @staticmethod
    def _ranges(function: str) -> Tuple[MeterRange, ...]:
        if function == Function.FREQUENCY:
            return (FREQUENCY_RANGES[True], FREQUENCY_RANGES[False])
        return RANGES.get(function, ())

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self, fresh: bool = True, timeout: Optional[float] = None) -> Reading:
        """The next reading, with everything that qualifies it.

        :param fresh: Discard everything already received, then the first
            complete frame too, so that the reading returned was measured
            wholly after this call. ``False`` returns the next frame to
            arrive, which is quicker by one reading interval and may be up to
            one interval old.
        :param timeout: Seconds to wait; defaults to the settle timeout.
        """
        wait = self._patience() if timeout is None else float(timeout)
        if fresh:
            self._discard_input()
            self._next_frame(wait)
        return self._next_frame(wait)

    def read_many(self, count: int, timeout: Optional[float] = None) -> List[Reading]:
        """*count* consecutive readings, the first of them fresh - a data log."""
        if count < 1:
            raise ConfigurationError("count must be at least 1, got %r" % (count,))
        readings = [self.read(fresh=True, timeout=timeout)]
        wait = self._patience() if timeout is None else float(timeout)
        while len(readings) < count:
            readings.append(self._next_frame(wait))
        return readings

    def measure(
        self,
        function: Optional[str] = None,
        allow_relative: bool = False,
        timeout: Optional[float] = None,
    ) -> float:
        """One live measurement, in SI units.

        :param function: Select this first (see :meth:`select_function`);
            ``None`` measures whatever the meter is set to.
        :param allow_relative: Accept a reading taken with Null active, which
            is the input minus a stored value.

        :raises MeasurementError: if the meter shows OFL, or is holding or
            recalling a reading rather than following its input. Returning
            infinity for OFL would pass any lower limit, and a held reading is
            not a measurement of anything happening now.
        :raises ConfigurationError: for a Null reading without
            *allow_relative*, or a meter on another function than *function*.
        """
        if function is not None:
            self.select_function(function)
        wait = self._patience() if timeout is None else float(timeout)
        reading = self.read(fresh=True, timeout=wait)
        deadline = self._clock() + wait
        # A reading taken while the meter is still ranging is neither overload
        # nor held, but it may not be a number yet: give it a few frames.
        while not reading.numeric and not reading.overload and self._clock() < deadline:
            reading = self._next_frame(wait)
        if function is not None and reading.function != function:
            raise ConfigurationError(
                "the 1604 is measuring %s, not %s: its front panel was changed"
                % (reading.function, function)
            )
        if reading.overload:
            raise MeasurementError(
                "the 1604 shows overload (OFL) on its %s range measuring %s: the "
                "input exceeds the range" % (reading.range_label, reading.function)
            )
        if reading.frozen:
            raise MeasurementError(
                "the 1604 is showing a %s reading, not a live one: cancel Hold, "
                "T-Hold or Min/Max on the front panel"
                % ("held" if (reading.display_hold or reading.touch_hold) else "recalled")
            )
        if not reading.numeric:
            raise MeasurementError("the 1604 display %r is not a number" % reading.display)
        if reading.relative and not allow_relative:
            raise ConfigurationError(
                "Null is active, so the 1604 is showing the input minus a stored "
                "value. Cancel Null, or pass allow_relative=True if that is intended."
            )
        return reading.value

    # ------------------------------------------------------------------
    # Named measurements, for a test specification
    # ------------------------------------------------------------------
    def measure_dc_voltage(self) -> float:
        """DC volts on the V/ohm socket, autoranged to 1000 V."""
        return self.measure(Function.DC_VOLTS)

    def measure_ac_voltage(self) -> float:
        """True-RMS AC volts on the V/ohm socket, autoranged to 750 V."""
        return self.measure(Function.AC_VOLTS)

    def measure_dc_current(self, socket: str = "mA") -> float:
        """DC amps: ``socket="mA"`` to 400 mA, ``socket="10A"`` to 10 A."""
        return self.measure(self._current_function(socket, ac=False))

    def measure_ac_current(self, socket: str = "mA") -> float:
        """True-RMS AC amps, from the socket named as for :meth:`measure_dc_current`."""
        return self.measure(self._current_function(socket, ac=True))

    def measure_resistance(self) -> float:
        """Ohms on the V/ohm socket, autoranged to 40 Mohm."""
        return self.measure(Function.OHMS)

    def measure_frequency(self, source: str = Function.AC_VOLTS) -> float:
        """Hertz, measured on an AC function: *source* is the one to use.

        The manual asks for an input of at least 2,000 counts on the chosen AC
        range, so choose the source to suit the signal. Takes one or ten
        seconds per reading, by gate time; every wait allows for it.
        """
        if source not in _FREQUENCY_SOURCES:
            raise ConfigurationError(
                "frequency is measured on an AC function: one of %s, not %r"
                % (", ".join(_FREQUENCY_SOURCES), source)
            )
        state = self.current_state()
        if state.function != Function.FREQUENCY:
            if state.function != source:
                self._select(source)
            self._press(Key.HERTZ)
            self._await("frequency", lambda reading: reading.function == Function.FREQUENCY,
                        timeout=self._patience(gate_10s=False))
        return self.measure()

    @staticmethod
    def _current_function(socket: str, ac: bool) -> str:
        choice = str(socket).strip().lower().replace(" ", "")
        if choice in ("ma", "milliamps"):
            return Function.AC_MILLIAMPS if ac else Function.DC_MILLIAMPS
        if choice in ("10a", "a", "amps"):
            return Function.AC_AMPS if ac else Function.DC_AMPS
        raise ConfigurationError(
            "the 1604 measures current on its 'mA' socket (to 400 mA) or its "
            "'10A' socket; %r is neither" % (socket,)
        )

    # ------------------------------------------------------------------
    @property
    def function(self) -> str:
        """What the meter is measuring now."""
        return self.current_state().function

    @property
    def in_current_function(self) -> bool:
        """``True`` when the meter's shunt is across its input."""
        return self.function in CURRENT_FUNCTIONS

    def local(self) -> None:
        """Return the meter to its front panel. Readings stop."""
        self._press(Key.LOCAL)

    def remote(self) -> None:
        """Resume remote mode, and with it the readings."""
        self._press(Key.REMOTE)
        self._next_frame(self._patience(gate_10s=True))

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<Tti1604 %s>" % self._transport.description
