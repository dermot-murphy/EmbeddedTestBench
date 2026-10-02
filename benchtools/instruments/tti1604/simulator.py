"""A simulated TTi 1604.

The simulator models the meter's *behaviour*, not a canned set of replies: it
holds a front-panel state, changes it when a key character arrives, and streams
measurement frames only while it is in remote mode and switched on. A test that
passes against this simulator has exercised the same decoding path a real meter
drives.

Behaviours modelled because getting them wrong on the bench is expensive and
silent:

**Nothing is streamed in local mode.** The meter says nothing at all until it
is told to go remote. A driver that waits for a frame it will never receive
looks exactly like a broken cable.

**Nothing is streamed while the meter is off.** The Operate key switches the
measurement circuits, not the interface - so a meter that is "off" still has a
live RS-232 link, accepts key presses and echoes them, and simply never
produces a measurement.

**The display is drawn at the range's resolution, and auto-ranges.** A value is
shown with the digits the instruction manual gives that range - 4.0000 V on the
4 V range, 230.0 V on the 400 V AC range - and an input beyond the range shows
OFL. Changing function sets auto-ranging, as the front panel does. A decoder
that derives a multiplier from the decimal point is therefore tested against
the display a meter would draw, not one this module invented.

**Readings come at the meter's rate, on a virtual clock.** One every 0.4 s, or
one per gate - 1 s or 10 s - when measuring frequency; a key that changes what
is measured restarts the measurement. The mock transport asks for what is due
within its own timeout (``poll_within``, CORE-FR-062), so a driver that waits
less than the meter takes gets a timeout here, exactly as it would from a
serial port, while a 20 s wait costs a test microseconds (#115).

Fault injection: ``drop_keys`` loses keys before the meter sees them,
``ignore_keys`` echoes them without acting, ``garbage`` puts bytes in front of
the next frame, as if the reader joined the stream part-way through one.

Traces to: DMM-FR-045, DMM-FR-046, DMM-DD-SIM.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from ...core.errors import TransportTimeoutError
from .constants import (
    AC_BIT,
    DECIMAL_POINT_BIT,
    DIGIT_COUNT,
    FRAME_LENGTH,
    FRAME_START,
    FREQUENCY_RANGES,
    FUNCTION_BITS,
    GATE_TIME,
    KEYS,
    LOCAL,
    RANGES,
    READING_INTERVAL,
    REMOTE,
    SEGMENT_PATTERNS,
    SIGN_BIT,
    STATUS_BITS,
    MeterRange,
    find_range,
)
from .protocol import unit_and_scale

__all__ = ["SimulatedTti1604"]

#: Character to seven-segment pattern, built from the decoding table so the
#: two can never disagree.
_PATTERN_FOR: Dict[str, int] = {}
for _pattern, _character in SEGMENT_PATTERNS.items():
    if _character and _character not in _PATTERN_FOR:
        _PATTERN_FOR[_character] = _pattern

_BLANK = 0x00

#: Which measurement type each key selects.
_TYPE_KEYS = {
    KEYS["millivolts"]: 1,
    KEYS["volts"]: 2,
    KEYS["milliamps"]: 3,
    KEYS["amps"]: 4,
    KEYS["ohms"]: 5,
}

#: Measurement types that have an AC and a DC form.
_COUPLED = (1, 2, 3, 4)


class SimulatedTti1604:  # pylint: disable=too-many-instance-attributes
    """An in-process 1604.

    :param value: The measurement to report, in SI units for the selected
        function - volts, amps, ohms or hertz.
    :param measurement_type: 1 mV, 2 V, 3 mA, 4 A, 5 ohms.
    :param range_index: Range selection 0 to 5, locked as if chosen with the
        arrow keys. ``None``, the default, auto-ranges, as the meter does after
        any change of function.
    :param ac: Start in AC rather than DC.
    :param operating: Start with the measurement circuits switched on.
    """

    idn = "Thurlby Thandar Instruments,1604"

    def __init__(  # pylint: disable=too-many-arguments
        self,
        value: float = 1.0,
        measurement_type: int = 2,
        range_index: Optional[int] = None,
        ac: bool = False,
        operating: bool = True,
    ) -> None:
        self.value = float(value)
        self.measurement_type = int(measurement_type)
        self.ac = bool(ac)
        self.operating = bool(operating)
        self.remote = False
        self.shifted = False
        self.flags: Dict[str, bool] = {name: False for name in FUNCTION_BITS}
        self.status: Dict[str, bool] = {name: False for name in STATUS_BITS}
        self.received: List[str] = []
        self.flags["auto_range"] = range_index is None
        self.status["auto_range_set"] = range_index is None
        self.range_index = int(range_index) if range_index is not None else 1
        if range_index is None:
            self.range_index = self._auto_range_code()
        #: Virtual time, in seconds, and when the next reading is due.
        self.clock = 0.0
        self.next_reading_at = READING_INTERVAL
        #: Fault injection; see the module docstring.
        self.drop_keys = 0
        self.ignore_keys = False
        self.garbage = b""
        self.frames_sent = 0

    # ------------------------------------------------------------------
    def set_value(self, value: float) -> None:
        """Change what the meter is measuring."""
        self.value = float(value)

    @property
    def measurement_time(self) -> float:
        """Seconds per reading: 0.4, or the gate time measuring frequency."""
        if self.flags["hertz"]:
            return GATE_TIME[self.status["gate_ten_seconds"]]
        return READING_INTERVAL

    def respond(self, message: bytes) -> Optional[bytes]:
        """Act on key characters and echo them, as the meter does.

        The echo is what a driver uses to know the command was not dropped, so
        a simulator that acted on a command without echoing it would hide a
        real failure mode instead of reproducing it.
        """
        echo = bytearray()
        for character in message.decode("ascii", "ignore"):
            if character in ("\r", "\n"):
                continue
            if self.drop_keys > 0:
                self.drop_keys -= 1
                continue
            self.received.append(character)
            if not self.ignore_keys:
                before = self._measuring()
                self._apply(character)
                if self._measuring() != before:
                    # A new function, range or gate starts a new measurement.
                    self.next_reading_at = self.clock + self.measurement_time
            echo.append(ord(character))
        return bytes(echo) if echo else None

    def poll(self) -> bytes:
        """The next measurement, however long it takes to come.

        Empty unless the meter is in remote mode *and* switched on: those are
        the two states in which a real 1604 produces nothing, and both look
        like a dead link from the far end.
        """
        if not self.remote or not self.operating:
            return b""
        return self.poll_within(math.inf)

    def poll_within(self, timeout: float) -> bytes:
        """The next measurement, if it is due within *timeout* seconds.

        :raises TransportTimeoutError: when nothing is due in time - including
            in local mode or with Operate off, when nothing is ever due - as a
            serial read with that timeout would. The clock moves on by the
            time waited, so a driver waiting for something that will not come
            reaches its deadline.
        """
        sending = self.remote and self.operating
        if not sending or self.next_reading_at - self.clock > timeout:
            self.clock += timeout if math.isfinite(timeout) else READING_INTERVAL
            raise TransportTimeoutError(
                "the simulated 1604 sent nothing within %.3f s" % timeout
            )
        self.clock = max(self.clock, self.next_reading_at)
        self.next_reading_at = self.clock + self.measurement_time
        data = self.garbage + self.frame()
        self.garbage = b""
        self.frames_sent += 1
        return data

    # ------------------------------------------------------------------
    def _measuring(self) -> tuple:
        return (self.remote, self.measurement_type, self.ac, self.range_index,
                self.flags["hertz"], self.flags["auto_range"],
                self.status["gate_ten_seconds"])

    def _ranges(self) -> tuple:
        return RANGES.get((self.measurement_type, self.ac and self.measurement_type != 5), ())

    def _auto_range_code(self) -> int:
        """The lowest range the input fits, or the highest if none does."""
        ranges = self._ranges()
        if not ranges:
            return self.range_index
        for candidate in ranges:
            if abs(self.value) <= candidate.overload:
                return candidate.code
        return ranges[-1].code

    def _apply(self, character: str) -> None:  # pylint: disable=too-many-return-statements,too-many-branches
        if character == REMOTE:
            self.remote = True
            return
        if character == LOCAL:
            self.remote = False
            return
        if character == KEYS["operate"]:
            self.operating = not self.operating
            return
        if character == KEYS["shift"]:
            self.shifted = not self.shifted
            return
        if character in _TYPE_KEYS:
            self._select(_TYPE_KEYS[character], self.ac)
            return
        if character == KEYS["hertz"]:
            # "pressing Hz when an AC range is not selected ... such
            # keystrokes are not accepted."
            if self.ac and self.measurement_type in _COUPLED:
                self.flags["hertz"] = True
                self.status["gate_ten_seconds"] = False
            return
        if character in (KEYS["ac"], KEYS["dc"]):
            # AC/DC does nothing on resistance.
            if self.measurement_type in _COUPLED:
                self._select(self.measurement_type, character == KEYS["ac"])
            return
        if character == KEYS["auto"]:
            if not self.flags["hertz"]:
                self.flags["auto_range"] = not self.flags["auto_range"]
                self.status["auto_range_set"] = self.flags["auto_range"]
            return
        if character in (KEYS["up"], KEYS["down"]):
            self._step(+1 if character == KEYS["up"] else -1)

    def _select(self, measurement_type: int, ac: bool) -> None:
        """"Changing function sets autorange" - and leaves Hz."""
        self.measurement_type = measurement_type
        self.ac = bool(ac) and measurement_type in _COUPLED
        self.flags["hertz"] = False
        self.status["gate_ten_seconds"] = False
        self.flags["auto_range"] = True
        self.status["auto_range_set"] = True
        self.range_index = self._auto_range_code()

    def _step(self, step: int) -> None:
        if self.flags["hertz"]:
            # Down selects the 4 kHz range (10 s gate); Up the 40 kHz range.
            self.status["gate_ten_seconds"] = step < 0
            return
        self.flags["auto_range"] = False
        self.status["auto_range_set"] = False
        codes = [candidate.code for candidate in self._ranges()]
        if self.range_index not in codes:
            # A range the function does not have: the plain 0 to 5 span.
            self.range_index = max(0, min(5, self.range_index + step))
            return
        index = codes.index(self.range_index) + step
        self.range_index = codes[max(0, min(len(codes) - 1, index))]

    # ------------------------------------------------------------------
    def _meter_range(self) -> Optional[MeterRange]:
        if self.flags["hertz"]:
            return FREQUENCY_RANGES[self.status["gate_ten_seconds"]]
        return find_range(self.measurement_type, self.ac, self.range_index)

    def frame(self) -> bytes:
        """Build one measurement frame from the current state."""
        if self.flags["auto_range"] and not self.flags["hertz"]:
            self.range_index = self._auto_range_code()
        _unit, scale = unit_and_scale(self.measurement_type, self.range_index, self.flags["hertz"])
        displayed = self.value / scale if scale else self.value
        frame = bytearray(FRAME_LENGTH)
        frame[0] = FRAME_START
        frame[1] = (
            (self.measurement_type & 0x07)
            | (AC_BIT if self.ac else 0)
            | ((self.range_index & 0x07) << 4)
        )
        frame[2] = self._bits(self.flags, FUNCTION_BITS)
        frame[3] = SIGN_BIT if displayed < 0 else 0
        meter_range = self._meter_range()
        if meter_range is not None and abs(self.value) > meter_range.overload:
            digits = self._overrange()
        else:
            digits = self._digit_bytes(abs(displayed), self._decimals(meter_range, scale))
        for offset, byte in enumerate(digits):
            frame[4 + offset] = byte
        frame[9] = self._bits(self.status, STATUS_BITS)
        return bytes(frame)

    @staticmethod
    def _decimals(meter_range: Optional[MeterRange], scale: float) -> Optional[int]:
        """Digits after the point at this range's resolution, if it is known."""
        if meter_range is None or not scale:
            return None
        return max(0, int(round(-math.log10(meter_range.resolution / scale))))

    @staticmethod
    def _bits(values: Dict[str, bool], positions: Dict[str, int]) -> int:
        word = 0
        for name, bit in positions.items():
            if values.get(name):
                word |= 1 << bit
        return word

    @staticmethod
    def _overrange() -> List[int]:
        return [_BLANK, _BLANK, _PATTERN_FOR["0"], _PATTERN_FOR["F"], _PATTERN_FOR["L"]]

    @classmethod
    def _digit_bytes(cls, number: float, decimals: Optional[int] = None) -> List[int]:
        """Render *number* onto five seven-segment digits.

        At the range's resolution when it is known; otherwise with as many
        decimals as fit. Falls back to the overrange display when the number
        needs more digits than the meter has, which is what the instrument
        itself does.
        """
        choices = (decimals,) if decimals is not None else (4, 3, 2, 1, 0)
        for places in choices:
            text = "%.*f" % (places, number)
            digits = text.replace(".", "")
            if len(digits) <= DIGIT_COUNT and digits.isdigit():
                point_after = len(digits) - places - 1 if places else None
                pad = DIGIT_COUNT - len(digits)
                out = [_BLANK] * pad
                for index, character in enumerate(digits):
                    byte = _PATTERN_FOR[character]
                    if point_after is not None and index == point_after:
                        byte |= DECIMAL_POINT_BIT
                    out.append(byte)
                return out
        return cls._overrange()
