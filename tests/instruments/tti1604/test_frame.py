"""Decoding the 1604's ten-character reading frame.

The frames here are built by hand from the published data format, not by the
simulator, so the decoder is checked against the document rather than against
another piece of this repository's code.

Traces to: DMM-FR-010 .. DMM-FR-015, DMM-NFR-003, SWE4-UT-DMMFRAME.
"""

from __future__ import annotations

import math

import pytest

from benchtools.core.errors import ProtocolError
from benchtools.instruments.tti1604 import Function, decode_frame

#: The note's own example: "if the display reads 12.345, characters 4 through
#: 8 will be 96 219 242 102 182".
TWELVE_POINT_345 = [96, 219, 242, 102, 182]

#: Seven-segment patterns, for building other displays.
P = {"0": 252, "1": 96, "2": 218, "3": 242, "4": 102, "5": 182, "6": 190,
     "7": 224, "8": 254, "9": 230, "F": 142, "L": 28, " ": 0}


def frame(units, range_code=1, ac=False, function=0x40, sign=0, digits=None, status=0):
    """A frame from its fields. *digits* is the five display bytes."""
    range_char = units | (0x08 if ac else 0) | (range_code << 4)
    body = digits if digits is not None else TWELVE_POINT_345
    return bytes([0x0D, range_char, function, sign] + list(body) + [status])


def display(text):
    """Five display bytes for *text*, which may carry one decimal point."""
    out = []
    for glyph in text:
        if glyph == ".":
            out[-1] |= 1
        else:
            out.append(P[glyph])
    assert len(out) == 5
    return out


class TestThePublishedExample:
    def test_twelve_point_three_four_five_volts(self):
        reading = decode_frame(frame(units=2, range_code=2))
        assert reading.display == "12.345"
        assert reading.value == pytest.approx(12.345)
        assert reading.function == Function.DC_VOLTS
        assert reading.unit == "V"
        assert reading.range_label == "40 V"

    def test_the_raw_frame_is_kept(self):
        raw = frame(units=2, range_code=2)
        assert decode_frame(raw).raw == raw


class TestUnitsAndSign:
    @pytest.mark.parametrize(
        "units,ac,function,value",
        [
            (1, False, Function.DC_MILLIVOLTS, 0.012345),
            (1, True, Function.AC_MILLIVOLTS, 0.012345),
            (2, False, Function.DC_VOLTS, 12.345),
            (2, True, Function.AC_VOLTS, 12.345),
            (3, False, Function.DC_MILLIAMPS, 0.012345),
            (3, True, Function.AC_MILLIAMPS, 0.012345),
            (4, False, Function.DC_AMPS, 12.345),
            (4, True, Function.AC_AMPS, 12.345),
        ],
    )
    def test_each_function_is_reported_in_si_units(self, units, ac, function, value):
        reading = decode_frame(frame(units=units, ac=ac, range_code=3))
        assert reading.function == function
        assert reading.ac is ac
        assert reading.value == pytest.approx(value, rel=1e-12)

    def test_millivolts_are_not_left_in_millivolts(self):
        """The display unit is the meter's; the value is always SI."""
        assert decode_frame(frame(units=1, range_code=3)).unit == "V"

    def test_the_minus_sign_is_bit_one_of_character_three(self):
        reading = decode_frame(frame(units=2, range_code=2, sign=0x02))
        assert reading.value == pytest.approx(-12.345)
        assert reading.display == "-12.345"

    def test_a_display_with_no_decimal_point_is_an_integer(self):
        reading = decode_frame(frame(units=2, range_code=2, digits=display("12345")))
        assert reading.value == 12345.0


class TestResistance:
    """The frame does not carry the k or M annunciator: it is derived."""

    @pytest.mark.parametrize(
        "code,shown,ohms",
        [
            (0, "123.45", 123.45),        # 400 ohm range, displayed in ohms
            (1, "1.2345", 1234.5),        # 4 k range, 100 mohm per count: kilohms
            (1, "1234.5", 1234.5),        # the same range displayed in ohms
            (2, "12.345", 12345.0),       # 40 k range, 1 ohm per count
            (3, "123.45", 123450.0),      # 400 k range, 10 ohm per count
            (4, "1.2345", 1234500.0),     # 4 M range, 100 ohm per count
            (5, "12.345", 12345000.0),    # 40 M range, 1 k per count
        ],
    )
    def test_the_multiplier_follows_from_the_resolution(self, code, shown, ohms):
        reading = decode_frame(frame(units=5, range_code=code, digits=display(shown)))
        assert reading.function == Function.OHMS
        assert reading.unit == "ohm"
        assert reading.value == pytest.approx(ohms)

    def test_a_display_that_fits_no_multiplier_is_refused(self):
        """Two decimals on the 4 k range would be 10 mohm per count: wrong."""
        with pytest.raises(ProtocolError, match="DMM-OPEN-02"):
            decode_frame(frame(units=5, range_code=1, digits=display("123.45")))

    def test_an_unknown_resistance_range_is_refused(self):
        with pytest.raises(ProtocolError, match="not a resistance range"):
            decode_frame(frame(units=5, range_code=7, digits=display("123.45")))


class TestOverload:
    def test_ofl_is_an_overload_and_not_a_number(self):
        reading = decode_frame(frame(units=2, range_code=1, digits=display(" 0FL ")))
        assert reading.overload is True
        assert reading.value == math.inf
        assert reading.is_live is False

    def test_a_negative_overload_is_negative_infinity(self):
        reading = decode_frame(frame(units=2, range_code=1, sign=0x02,
                                     digits=display(" 0FL ")))
        assert reading.value == -math.inf

    def test_a_blank_display_is_not_numeric(self):
        reading = decode_frame(frame(units=2, digits=display("     ")))
        assert reading.numeric is False
        assert math.isnan(reading.value)
        assert reading.is_live is False


class TestFlags:
    @pytest.mark.parametrize(
        "field,function_bits,status_bits",
        [
            ("touch_hold", 0x02, 0),
            ("min_max", 0x04, 0),
            ("relative", 0x20, 0),
            ("auto_range", 0x40, 0),
            ("double_beep", 0, 0x01),
            ("auto_range_set", 0, 0x02),
            ("continuity_buzz", 0, 0x08),
            ("showing_min", 0, 0x10),
            ("showing_max", 0, 0x20),
            ("display_hold", 0, 0x40),
        ],
    )
    def test_each_documented_bit(self, field, function_bits, status_bits):
        reading = decode_frame(frame(units=2, range_code=2, function=function_bits,
                                     status=status_bits))
        assert getattr(reading, field) is True

    @pytest.mark.parametrize(
        "function_bits,status_bits",
        [(0x02, 0), (0, 0x10), (0, 0x20), (0, 0x40)],
    )
    def test_a_held_or_recalled_reading_is_not_live(self, function_bits, status_bits):
        reading = decode_frame(frame(units=2, range_code=2, function=function_bits,
                                     status=status_bits))
        assert reading.frozen is True
        assert reading.is_live is False

    def test_a_relative_reading_is_live_and_flagged(self):
        reading = decode_frame(frame(units=2, range_code=2, function=0x20))
        assert reading.is_live is True
        assert reading.relative is True

    def test_auto_range_is_the_function_annunciator(self):
        assert decode_frame(frame(units=2, function=0x00)).auto_range is False


class TestFrequency:
    def test_the_hz_flag_makes_it_a_frequency_in_hertz(self):
        reading = decode_frame(frame(units=2, ac=True, range_code=1, function=0x10,
                                     digits=display(" 1234")))
        assert reading.function == Function.FREQUENCY
        assert reading.unit == "Hz"
        assert reading.value == 1234.0
        assert reading.range_label == "40 kHz"

    def test_the_ten_second_gate_is_the_4_khz_range(self):
        reading = decode_frame(frame(units=2, ac=True, function=0x10, status=0x80,
                                     digits=display("1234.5")))
        assert reading.gate_10s is True
        assert reading.range_label == "4 kHz"
        assert reading.value == pytest.approx(1234.5)


class TestValidation:
    def test_a_frame_must_start_with_carriage_return(self):
        with pytest.raises(ProtocolError, match="starting with CR"):
            decode_frame(b"\x0a" + frame(units=2)[1:])

    def test_a_frame_must_be_ten_characters(self):
        with pytest.raises(ProtocolError):
            decode_frame(frame(units=2)[:9])

    def test_a_pattern_the_meter_never_sends_is_refused(self):
        """This is what lets the driver resynchronise on a stream."""
        with pytest.raises(ProtocolError, match="seven-segment"):
            decode_frame(frame(units=2, digits=[96, 219, 242, 102, 0x44]))

    def test_units_code_zero_is_refused(self):
        with pytest.raises(ProtocolError, match="no units"):
            decode_frame(frame(units=0))

    def test_two_decimal_points_are_refused(self):
        with pytest.raises(ProtocolError, match="decimal points"):
            decode_frame(frame(units=2, digits=[97, 219, 242, 102, 182]))

    def test_an_unlisted_range_code_is_reported_not_refused(self):
        """Volts do not need the range to be scaled, so an unknown code is shown."""
        reading = decode_frame(frame(units=2, range_code=6))
        assert reading.range_label == "code 6"
        assert reading.value == pytest.approx(12.345)

    def test_as_dict_carries_the_qualifiers(self):
        data = decode_frame(frame(units=2, range_code=2)).as_dict()
        for key in ("value", "unit", "function", "range", "overload", "is_live",
                    "relative", "display_hold", "raw"):
            assert key in data
