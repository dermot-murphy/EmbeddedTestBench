"""A simulated TTi 1604.

The simulator models the meter's *behaviour*, not a canned set of replies: it
holds a front-panel state, changes it when a key character arrives, and streams
measurement frames only while it is in remote mode and switched on. A test that
passes against this simulator has exercised the same decoding path a real meter
drives.

Two behaviours are modelled because getting them wrong on the bench is
expensive and silent:

**Nothing is streamed in local mode.** The meter says nothing at all until it
is told to go remote. A driver that waits for a frame it will never receive
looks exactly like a broken cable.

**Nothing is streamed while the meter is off.** The Operate key switches the
measurement circuits, not the interface - so a meter that is "off" still has a
live RS-232 link, accepts key presses and echoes them, and simply never
produces a measurement.

Traces to: DMM-FR-040 .. DMM-FR-052, DMM-DD-SIM.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .constants import (
    AC_BIT,
    DECIMAL_POINT_BIT,
    DIGIT_COUNT,
    FRAME_LENGTH,
    FRAME_START,
    FUNCTION_BITS,
    KEYS,
    LOCAL,
    REMOTE,
    SEGMENT_PATTERNS,
    SIGN_BIT,
    STATUS_BITS,
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


class SimulatedTti1604:  # pylint: disable=too-many-instance-attributes
    """An in-process 1604.

    :param value: The measurement to report, in SI units for the selected
        function - volts, amps, ohms or hertz.
    :param measurement_type: 1 mV, 2 V, 3 mA, 4 A, 5 ohms.
    :param range_index: Range selection 0 to 5.
    :param ac: Start in AC rather than DC.
    :param operating: Start with the measurement circuits switched on.
    """

    idn = "Thurlby Thandar Instruments,1604"

    def __init__(
        self,
        value: float = 1.0,
        measurement_type: int = 2,
        range_index: int = 1,
        ac: bool = False,
        operating: bool = True,
    ) -> None:
        self.value = float(value)
        self.measurement_type = int(measurement_type)
        self.range_index = int(range_index)
        self.ac = bool(ac)
        self.operating = bool(operating)
        self.remote = False
        self.shifted = False
        self.flags: Dict[str, bool] = {name: False for name in FUNCTION_BITS}
        self.status: Dict[str, bool] = {name: False for name in STATUS_BITS}
        self.received: List[str] = []

    # ------------------------------------------------------------------
    def set_value(self, value: float) -> None:
        """Change what the meter is measuring."""
        self.value = float(value)

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
            self.received.append(character)
            self._apply(character)
            echo.append(ord(character))
        return bytes(echo) if echo else None

    def poll(self) -> bytes:
        """The unsolicited measurement stream.

        Empty unless the meter is in remote mode *and* switched on: those are
        the two states in which a real 1604 produces nothing, and both look
        like a dead link from the far end.
        """
        if not self.remote or not self.operating:
            return b""
        return self.frame()

    # ------------------------------------------------------------------
    def _apply(self, character: str) -> None:  # pylint: disable=too-many-return-statements
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
            self.measurement_type = _TYPE_KEYS[character]
            self.flags["hertz"] = False
            return
        if character == KEYS["hertz"]:
            self.flags["hertz"] = not self.flags["hertz"]
            return
        if character == KEYS["ac"]:
            self.ac = True
            return
        if character == KEYS["dc"]:
            self.ac = False
            return
        if character == KEYS["auto"]:
            self.flags["auto_range"] = not self.flags["auto_range"]
            self.status["auto_range_set"] = self.flags["auto_range"]
            return
        if character == KEYS["up"]:
            self.range_index = min(5, self.range_index + 1)
            return
        if character == KEYS["down"]:
            self.range_index = max(0, self.range_index - 1)

    # ------------------------------------------------------------------
    def frame(self) -> bytes:
        """Build one measurement frame from the current state."""
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
        for offset, byte in enumerate(self._digit_bytes(abs(displayed))):
            frame[4 + offset] = byte
        frame[9] = self._bits(self.status, STATUS_BITS)
        return bytes(frame)

    @staticmethod
    def _bits(values: Dict[str, bool], positions: Dict[str, int]) -> int:
        word = 0
        for name, bit in positions.items():
            if values.get(name):
                word |= 1 << bit
        return word

    @staticmethod
    def _digit_bytes(number: float) -> List[int]:
        """Render *number* onto five seven-segment digits.

        Falls back to the overrange display when the number needs more digits
        than the meter has, which is what the instrument itself does.
        """
        for decimals in (4, 3, 2, 1, 0):
            text = "%.*f" % (decimals, number)
            digits = text.replace(".", "")
            if len(digits) <= DIGIT_COUNT and digits.isdigit():
                point_after = len(digits) - decimals - 1 if decimals else None
                pad = DIGIT_COUNT - len(digits)
                out = [_BLANK] * pad
                for index, character in enumerate(digits):
                    byte = _PATTERN_FOR[character]
                    if point_after is not None and index == point_after:
                        byte |= DECIMAL_POINT_BIT
                    out.append(byte)
                return out
        return [_BLANK, _BLANK, _PATTERN_FOR["0"], _PATTERN_FOR["F"], _PATTERN_FOR["L"]]
