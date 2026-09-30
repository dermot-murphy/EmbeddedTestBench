"""A simulated TTi 1604.

The model is a *meter with something on its input*, not a byte replayer. A
test sets what the input is doing - 12 mA DC, 3.3 V, 4.7 kohm - and the
simulator auto-ranges onto it, formats the display as the meter would, and
encodes that display into the ten-character frame. The driver's decoder then
has to get back to 12 mA from seven-segment patterns, which is the path a
real reading takes.

What is modelled: the key characters and their echo, remote and local mode,
function and AC/DC selection, auto and manual ranging, overload (OFL), the Hz
function and its gate time, Operate (standby: the interface stays up and the
readings stop), and a reading every 0.4 s on a virtual clock. Fault injection:
keys lost before the meter sees them, and a stream joined part-way through a
frame.

What is not: SHIFT and the functions behind it (Null, Hold, T-Hold, Min/Max,
continuity, diode), which the published note does not map to keys - a test
sets their flags directly, as an operator would from the front panel;
accuracy and noise; and the meter's analogue settling.

**Time.** A reading every 0.4 s would make a test suite wait for the meter. The
simulator keeps its own clock, advanced by one reading interval each time the
link is read, and the driver waits on that clock when it is talking to the
simulator. A test that waits 4 s for a range change takes microseconds and
still exercises every timeout in the driver.

Traces to: DMM-FR-050, DMM-DD-SIM.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ...core.errors import TransportTimeoutError
from .constants import (
    CURRENT_FUNCTIONS,
    FRAME_START,
    FREQUENCY_RANGES,
    FUNCTION_CODING,
    READING_INTERVAL,
    RANGES,
    SEGMENTS,
    Function,
    Key,
    MeterRange,
)

__all__ = ["SimulatedTti1604"]

#: Seven-segment pattern for each glyph the simulator displays.
_PATTERN: Dict[str, int] = {}
for _code, _glyph in SEGMENTS.items():
    _PATTERN.setdefault(_glyph, _code)

#: Units code for each function the keys select.
_UNITS: Dict[str, Tuple[int, bool]] = {
    function: coding for coding, function in FUNCTION_CODING.items()
    if function not in (Function.OHMS, Function.CONTINUITY, Function.DIODE)
}
_UNITS[Function.OHMS] = (5, False)

#: Which input quantity each function reads.
_INPUT: Dict[str, str] = {
    Function.DC_VOLTS: "dc_volts",
    Function.DC_MILLIVOLTS: "dc_volts",
    Function.AC_VOLTS: "ac_volts",
    Function.AC_MILLIVOLTS: "ac_volts",
    Function.DC_MILLIAMPS: "dc_amps",
    Function.DC_AMPS: "dc_amps",
    Function.AC_MILLIAMPS: "ac_amps",
    Function.AC_AMPS: "ac_amps",
    Function.OHMS: "ohms",
}

#: Resistance display multiplier per range code: ohms on the 400 ohm range,
#: kilohms to 400 k, megohms above.
_OHMS_DISPLAY = {0: 1.0, 1: 1e3, 2: 1e3, 3: 1e3, 4: 1e6, 5: 1e6}

#: Display multiplier for functions whose display unit the range states.
_DISPLAY_UNIT = {
    Function.DC_MILLIVOLTS: 1e-3,
    Function.AC_MILLIVOLTS: 1e-3,
    Function.DC_MILLIAMPS: 1e-3,
    Function.AC_MILLIAMPS: 1e-3,
}


class SimulatedTti1604:
    """A 1604 with an input a test can set.

    Starts as a meter does after SHIFT + Reset: DC volts, auto-ranging, in
    local mode, with nothing on its input.
    """

    #: Identification, for the transport's description. The 1604 has no
    #: identification query; this string is never sent over the link.
    idn = "THURLBY THANDAR,1604,SIMULATED,"

    def __init__(self) -> None:
        #: Virtual time, in seconds. Advanced one reading interval per read.
        self.clock = 0.0
        #: Every key character received, in order, whether or not it was acted
        #: on. Tests assert on this.
        self.key_log: List[str] = []
        #: What the input is doing. Resistance is infinite with nothing
        #: connected, which the meter shows as OFL.
        self.inputs: Dict[str, float] = {
            "dc_volts": 0.0,
            "ac_volts": 0.0,
            "dc_amps": 0.0,
            "ac_amps": 0.0,
            "ohms": math.inf,
            "frequency": 0.0,
        }
        #: Keys to lose before the meter sees them, as a bad link would.
        self.drop_keys = 0
        #: Bytes to put in front of the next reading, as if the driver had
        #: joined the stream part-way through a frame.
        self.garbage = b""
        #: When set, the meter does not act on keys at all, but still echoes
        #: them - a meter whose keys are locked, or a key it rejects with a beep.
        self.ignore_keys = False
        #: Bits OR-ed into the function and status characters, standing for
        #: what an operator selected with SHIFT: Null (0x20 in function), Hold
        #: (0x40 in status), and so on. SHIFT itself is not modelled.
        self.panel_function_bits = 0
        self.panel_status_bits = 0
        #: Send a NUL after each frame, as the note's "null-terminated" may
        #: mean (DMM-OPEN-01).
        self.nul_terminated = False
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Power-on state: DC volts, auto range, local, operating."""
        self.remote = False
        self.operating = True
        self.function = Function.DC_VOLTS
        self.auto_range = True
        self.range_code = RANGES[Function.DC_VOLTS][0].code
        self.hertz = False
        self.gate_10s = False
        self.frames_sent = 0

    def set_input(self, quantity: str, value: float) -> None:
        """Apply *value* to the input: ``dc_volts``, ``ac_amps``, ``ohms``..."""
        if quantity not in self.inputs:
            raise KeyError("no input called %r; expected one of %s"
                           % (quantity, ", ".join(sorted(self.inputs))))
        self.inputs[quantity] = float(value)

    # ------------------------------------------------------------------
    # The link
    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Act on each key character and echo it."""
        echoed = bytearray()
        for value in bytes(message):
            character = chr(value)
            if character not in Key.ALL:
                continue
            if self.drop_keys > 0:
                self.drop_keys -= 1
                continue
            self.key_log.append(character)
            if not self.ignore_keys:
                self._press(character)
            echoed.append(value)
        return bytes(echoed) if echoed else None

    def poll(self) -> bytes:
        """The next reading, one reading interval later.

        :raises TransportTimeoutError: when the meter has nothing to say - in
            local mode, or in standby - exactly as a silent serial line times
            out. The clock still advances, so a driver waiting for an echo that
            will never come reaches its deadline.
        """
        self.clock += READING_INTERVAL
        if not (self.remote and self.operating):
            raise TransportTimeoutError("the simulated 1604 is not sending readings")
        frame = self.garbage + self.frame() + (b"\x00" if self.nul_terminated else b"")
        self.garbage = b""
        self.frames_sent += 1
        return frame

    # ------------------------------------------------------------------
    # Keys
    # ------------------------------------------------------------------
    def _press(self, key: str) -> None:
        if key == Key.REMOTE:
            self.remote = True
        elif key == Key.LOCAL:
            self.remote = False
        elif key == Key.OPERATE:
            self.operating = not self.operating
        elif key in (Key.VOLTS, Key.MILLIVOLTS, Key.MILLIAMPS, Key.AMPS):
            self._select_units(key)
        elif key == Key.OHMS:
            self._select(Function.OHMS)
        elif key in (Key.AC, Key.DC):
            self._select_coupling(key == Key.AC)
        elif key == Key.HERTZ:
            # "pressing Hz when an AC range is not selected ... such keystrokes
            # are not accepted."
            if self.function in (Function.AC_VOLTS, Function.AC_MILLIVOLTS,
                                 Function.AC_MILLIAMPS, Function.AC_AMPS):
                self.hertz = True
                self.gate_10s = False
        elif key == Key.AUTO:
            if not self.hertz:
                self.auto_range = not self.auto_range
        elif key in (Key.UP, Key.DOWN):
            self._step_range(+1 if key == Key.UP else -1)
        # SHIFT and anything behind it is not modelled.

    def _select_units(self, key: str) -> None:
        ac = self.function in (Function.AC_VOLTS, Function.AC_MILLIVOLTS,
                               Function.AC_MILLIAMPS, Function.AC_AMPS)
        choice = {
            Key.VOLTS: (Function.DC_VOLTS, Function.AC_VOLTS),
            Key.MILLIVOLTS: (Function.DC_MILLIVOLTS, Function.AC_MILLIVOLTS),
            Key.MILLIAMPS: (Function.DC_MILLIAMPS, Function.AC_MILLIAMPS),
            Key.AMPS: (Function.DC_AMPS, Function.AC_AMPS),
        }[key]
        self._select(choice[1] if ac else choice[0])

    def _select_coupling(self, ac: bool) -> None:
        pairs = (
            (Function.DC_VOLTS, Function.AC_VOLTS),
            (Function.DC_MILLIVOLTS, Function.AC_MILLIVOLTS),
            (Function.DC_MILLIAMPS, Function.AC_MILLIAMPS),
            (Function.DC_AMPS, Function.AC_AMPS),
        )
        for dc_function, ac_function in pairs:
            if self.function in (dc_function, ac_function):
                self._select(ac_function if ac else dc_function)
                return
        # AC/DC on resistance: not accepted.

    def _select(self, function: str) -> None:
        """"Changing function sets autorange" - and leaves Hz."""
        self.function = function
        self.hertz = False
        self.gate_10s = False
        self.auto_range = True
        self.range_code = self._auto_range().code

    def _step_range(self, step: int) -> None:
        if self.hertz:
            # Down selects the 4 kHz range (10 s gate), up the 40 kHz range.
            self.gate_10s = step < 0
            return
        ranges = RANGES[self.function]
        codes = [item.code for item in ranges]
        index = codes.index(self.range_code) + step
        self.auto_range = False
        self.range_code = codes[max(0, min(len(codes) - 1, index))]

    # ------------------------------------------------------------------
    # What the meter shows
    # ------------------------------------------------------------------
    def _range(self) -> MeterRange:
        for item in RANGES[self.function]:
            if item.code == self.range_code:
                return item
        raise AssertionError("no range %d for %s" % (self.range_code, self.function))

    def _auto_range(self) -> MeterRange:
        """The lowest range the input fits, or the highest if none does."""
        magnitude = abs(self.inputs[_INPUT[self.function]])
        ranges = RANGES[self.function]
        for item in ranges:
            if magnitude <= item.overload:
                return item
        return ranges[-1]

    def display(self) -> Tuple[str, bool]:
        """The five display characters, with a decimal point, and the sign.

        ``("12.345", False)``, ``(" 0FL ", False)``. The decimal point is not
        one of the five characters; :meth:`frame` folds it into the pattern of
        the character to its left.
        """
        if self.hertz:
            meter_range = FREQUENCY_RANGES[self.gate_10s]
            value = self.inputs["frequency"]
            unit = 1.0
        else:
            if self.auto_range:
                self.range_code = self._auto_range().code
            meter_range = self._range()
            value = self.inputs[_INPUT[self.function]]
            if self.function == Function.OHMS:
                unit = _OHMS_DISPLAY[meter_range.code]
            else:
                unit = _DISPLAY_UNIT.get(self.function, 1.0)
        negative = value < 0 and not self.function == Function.OHMS and not self.hertz
        magnitude = abs(value)
        if math.isinf(magnitude) or magnitude > meter_range.overload:
            return " 0FL ", negative
        decimals = int(round(-math.log10(meter_range.resolution / unit)))
        decimals = max(0, decimals)
        text = "%.*f" % (decimals, magnitude / unit)
        digits = text.replace(".", "")
        if len(digits) > 5:
            return " 0FL ", negative
        return text.rjust(5 + (1 if decimals else 0)), negative

    def frame(self) -> bytes:
        """The ten characters the meter sends after a measurement."""
        shown, negative = self.display()
        characters: List[int] = []
        for glyph in shown:
            if glyph == ".":
                characters[-1] |= 0x01
            else:
                characters.append(_PATTERN[glyph])
        units, ac = _UNITS[self.function]
        range_char = units | (0x08 if ac else 0) | ((self.range_code & 0x07) << 4)
        function_char = ((0x10 if self.hertz else 0) | (0x40 if self.auto_range else 0)
                         | self.panel_function_bits)
        sign_char = 0x02 if negative else 0x00
        status_char = ((0x80 if self.gate_10s else 0) | (0x02 if self.auto_range else 0)
                       | self.panel_status_bits)
        return bytes([FRAME_START, range_char, function_char, sign_char]
                     + characters + [status_char])

    # ------------------------------------------------------------------
    @property
    def in_current_function(self) -> bool:
        """``True`` when the meter's current shunt is across its input."""
        return self.function in CURRENT_FUNCTIONS
