"""The 1604's reading frame, decoded.

In remote mode the meter sends ten characters after every measurement:

====== ===================================================================
Char   Meaning
====== ===================================================================
0      Carriage return - the start of a frame
1      Range: bits 0-2 units, bit 3 AC, bits 4-6 range
2      Function: bit 1 T-Hold, 2 Min/Max, 4 Hz, 5 Null, 6 Auto
3      Bit 1 set: the reading is negative
4 - 8  The five display characters, as seven-segment patterns; bit 0 set on
       the character to the left of the decimal point
9      Status: bit 0 double beep, 1 auto range set, 3 continuity buzz,
       4 showing Min, 5 showing Max, 6 display hold, 7 10 s gate
====== ===================================================================

The frame is a picture of the display, not a number. Two consequences shape
this module:

**The value comes from the display, so the display's unit must be known.** For
volts and amps the range character says what the display unit is. For
resistance it does not: the display shows ``4.0000`` on the 4 kohm range and
the kilo is an annunciator the frame does not carry. The multiplier is
therefore *derived* - the range's resolution from the manual, divided by the
value of the last displayed digit - and a frame for which that is not a clean
1, 1 000 or 1 000 000 is refused rather than guessed at (DMM-FR-012).

**A frame can describe something that is not a live measurement.** Hold,
T-Hold and Min/Max freeze or replace the reading; Null subtracts a stored
one; OFL is not a number at all. Every one of those is decoded into a flag on
the :class:`Reading`, so that the driver can refuse to hand a test a number
that is not what the input is doing now.

Traces to: DMM-FR-010 .. DMM-FR-015, DMM-DD-FRAME.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

from ...core.errors import ProtocolError
from .constants import (
    DISPLAY_FACTOR,
    FRAME_LENGTH,
    FRAME_START,
    FREQUENCY_RANGES,
    FUNCTION_CODING,
    FUNCTION_UNIT,
    SEGMENTS,
    UNITS_CODES,
    Function,
    MeterRange,
    find_range,
)

__all__ = ["Reading", "decode_frame", "is_frame_candidate"]

# Function character.
_T_HOLD = 0x02
_MIN_MAX = 0x04
_HERTZ = 0x10
_NULL = 0x20
_AUTO = 0x40

# Sign character.
_MINUS = 0x02

# Status character.
_DOUBLE_BEEP = 0x01
_AUTO_RANGE_SET = 0x02
_CONTINUITY_BUZZ = 0x08
_SHOW_MIN = 0x10
_SHOW_MAX = 0x20
_DISPLAY_HOLD = 0x40
_GATE_10S = 0x80

#: Resistance display multipliers the meter can be showing: ohms, kilohms and
#: megohms.
_RESISTANCE_MULTIPLIERS = (1.0, 1e3, 1e6)


@dataclass(frozen=True)
class Reading:
    """One reading, as the meter reported it, with everything that qualifies it.

    ``value`` is in SI units - volts, amps, ohms, hertz - whatever the display
    showed it in. It is ``inf`` (signed) for an overload and ``nan`` for a
    display that is not a number at all; :attr:`is_live` and :attr:`overload`
    say which, so a caller never has to test a float for either.
    """

    function: str
    value: float
    unit: str
    display: str
    range_label: str
    range_code: int
    full_scale: float
    ac: bool
    auto_range: bool
    overload: bool
    numeric: bool
    relative: bool = False
    touch_hold: bool = False
    min_max: bool = False
    showing_min: bool = False
    showing_max: bool = False
    display_hold: bool = False
    gate_10s: bool = False
    auto_range_set: bool = False
    double_beep: bool = False
    continuity_buzz: bool = False
    raw: bytes = b""
    received_at: float = 0.0

    @property
    def frozen(self) -> bool:
        """``True`` when the display is not following the input.

        Hold and T-Hold freeze the reading; Min/Max recall shows a stored one.
        In none of those is the number what the input is doing now.
        """
        return self.display_hold or self.touch_hold or self.showing_min or self.showing_max

    @property
    def is_live(self) -> bool:
        """``True`` for a number that is the input's value at this moment.

        A relative (Null) reading is live - it is a measurement, offset by a
        stored one - and is flagged separately by :attr:`relative`.
        """
        return self.numeric and not self.overload and not self.frozen

    def as_dict(self) -> Dict[str, object]:
        return {
            "function": self.function,
            "value": self.value,
            "unit": self.unit,
            "display": self.display,
            "range": self.range_label,
            "range_code": self.range_code,
            "full_scale": self.full_scale,
            "ac": self.ac,
            "auto_range": self.auto_range,
            "overload": self.overload,
            "is_live": self.is_live,
            "relative": self.relative,
            "touch_hold": self.touch_hold,
            "min_max": self.min_max,
            "showing_min": self.showing_min,
            "showing_max": self.showing_max,
            "display_hold": self.display_hold,
            "gate_10s": self.gate_10s,
            "raw": self.raw.hex(),
        }


def is_frame_candidate(data: bytes) -> bool:
    """``True`` when *data* has the length and start byte of a frame."""
    return len(data) == FRAME_LENGTH and data[0] == FRAME_START


def _display(characters: bytes) -> "tuple[str, int]":
    """The display as text, and how many digits follow the decimal point.

    :raises ProtocolError: for a pattern the note does not list, or for more
        than one decimal point - either means this is not a frame.
    """
    text = []
    points = []
    for position, code in enumerate(characters):
        glyph = SEGMENTS.get(code & 0xFE)
        if glyph is None:
            raise ProtocolError(
                "display character %d is 0x%02X, which is not a seven-segment "
                "pattern the 1604 sends" % (position, code)
            )
        text.append(glyph)
        if code & 0x01:
            points.append(position)
    if len(points) > 1:
        raise ProtocolError("the display has %d decimal points" % len(points))
    if not points:
        return "".join(text), 0
    point = points[0]
    shown = "".join(text[: point + 1]) + "." + "".join(text[point + 1:])
    return shown, len(characters) - 1 - point


def _resistance_multiplier(meter_range: MeterRange, decimals: int, raw: bytes) -> float:
    """Kilohms or megohms: derived, because the frame does not say.

    The last displayed digit is worth ``10**-decimals`` display units, and the
    manual says what one count is worth in ohms on this range. Their ratio is
    the display multiplier.
    """
    ratio = meter_range.resolution / (10.0 ** -decimals)
    for multiplier in _RESISTANCE_MULTIPLIERS:
        if abs(ratio / multiplier - 1.0) < 1e-6:
            return multiplier
    raise ProtocolError(
        "a resistance display with %d decimal place(s) does not fit the %s range, "
        "whose resolution is %g ohm: the display multiplier cannot be derived "
        "(DMM-OPEN-02). Frame %s" % (decimals, meter_range.label, meter_range.resolution,
                                     raw.hex())
    )


def decode_frame(data: bytes, received_at: float = 0.0) -> Reading:
    """Decode one ten-character frame.

    :param received_at: When it arrived, on the driver's clock.
    :raises ProtocolError: if *data* is not a frame the 1604 would send. The
        driver uses this to resynchronise on a stream that it joined part-way
        through a frame.
    """
    raw = bytes(data)
    if not is_frame_candidate(raw):
        raise ProtocolError(
            "a frame is %d characters starting with CR; got %r" % (FRAME_LENGTH, raw)
        )
    range_char, function_char, sign_char = raw[1], raw[2], raw[3]
    status_char = raw[9]

    units = range_char & 0x07
    if units not in UNITS_CODES:
        raise ProtocolError("range character 0x%02X has no units" % range_char)
    ac = bool(range_char & 0x08)
    code = (range_char >> 4) & 0x07
    hertz = bool(function_char & _HERTZ)
    gate_10s = bool(status_char & _GATE_10S)

    if hertz:
        function = Function.FREQUENCY
        meter_range: Optional[MeterRange] = FREQUENCY_RANGES[gate_10s]
    else:
        function = FUNCTION_CODING[(units, ac)]
        meter_range = find_range(function, code)

    shown, decimals = _display(raw[4:9])
    negative = bool(sign_char & _MINUS)
    body = shown.strip()
    overload = "F" in body and "L" in body
    numeric = bool(body) and all(glyph.isdigit() or glyph == "." for glyph in body)

    value = math.nan
    if overload:
        value = -math.inf if negative else math.inf
    elif numeric:
        try:
            number = Decimal(body)
        except InvalidOperation as exc:          # pragma: no cover - guarded above
            raise ProtocolError("display %r is not a number" % shown) from exc
        if function in (Function.OHMS, Function.CONTINUITY):
            if meter_range is None:
                raise ProtocolError(
                    "range code %d is not a resistance range, so the display "
                    "multiplier cannot be derived. Frame %s" % (code, raw.hex())
                )
            factor = _resistance_multiplier(meter_range, decimals, raw)
        elif function == Function.FREQUENCY:
            factor = 1.0
        else:
            factor = DISPLAY_FACTOR[units]
        value = float(number * Decimal(repr(factor)))
        if negative:
            value = -value

    return Reading(
        function=function,
        value=value,
        unit=FUNCTION_UNIT[function],
        display=("-" if negative else "") + body,
        range_label=meter_range.label if meter_range else "code %d" % code,
        range_code=code,
        full_scale=meter_range.full_scale if meter_range else math.nan,
        ac=ac,
        auto_range=bool(function_char & _AUTO),
        overload=overload,
        numeric=numeric,
        relative=bool(function_char & _NULL),
        touch_hold=bool(function_char & _T_HOLD),
        min_max=bool(function_char & _MIN_MAX),
        showing_min=bool(status_char & _SHOW_MIN),
        showing_max=bool(status_char & _SHOW_MAX),
        display_hold=bool(status_char & _DISPLAY_HOLD),
        gate_10s=gate_10s,
        auto_range_set=bool(status_char & _AUTO_RANGE_SET),
        double_beep=bool(status_char & _DOUBLE_BEEP),
        continuity_buzz=bool(status_char & _CONTINUITY_BUZZ),
        raw=raw,
        received_at=received_at,
    )
