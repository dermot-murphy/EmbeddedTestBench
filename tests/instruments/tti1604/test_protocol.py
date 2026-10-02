"""Decoding a 1604 measurement frame.

The tests are organised around the ways this meter can make a test lie: a
frame decoded from the wrong offset, a digit pattern read as the wrong figure,
an ohms reading off by a factor of a thousand, a held display recorded as a
live measurement, and an overrange treated as a number.

Traces to: DMM-FR-010 .. DMM-FR-028, SWE4-UT-DMM.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ProtocolError
from benchtools.instruments.tti1604 import (
    FrameAssembler,
    SimulatedTti1604,
    decode,
    digits_text,
    unit_and_scale,
)
from benchtools.instruments.tti1604.constants import (
    FRAME_LENGTH,
    FRAME_START,
    SEGMENT_PATTERNS,
)


def frame_for(**kwargs) -> bytes:
    return SimulatedTti1604(**kwargs).frame()


class TestSegmentDecoding:
    """The display digits are a segment bitmap, not a character code."""

    def test_eight_is_every_segment_and_zero_is_that_less_the_middle(self):
        # This relationship is what identifies the bit layout: if it holds,
        # bit 1 is the middle segment and bit 0 is not a segment at all.
        assert SEGMENT_PATTERNS[0xFE] == "8"
        assert SEGMENT_PATTERNS[0xFE & ~0x02] == "0"

    @pytest.mark.parametrize(
        "pattern,expected",
        [(0xFC, "0"), (0x60, "1"), (0xDA, "2"), (0xF2, "3"), (0x66, "4"),
         (0xB6, "5"), (0xBE, "6"), (0xE0, "7"), (0xFE, "8"), (0xE6, "9")],
    )
    def test_every_digit_decodes(self, pattern, expected):
        assert SEGMENT_PATTERNS[pattern] == expected

    def test_decimal_point_is_bit_zero_of_the_digit_it_follows(self):
        frame = bytearray(frame_for(value=1.2345, measurement_type=2, range_index=1))
        assert digits_text(bytes(frame)) == "1.2345"

    def test_an_unknown_pattern_is_marked_not_dropped(self):
        # Dropping it would turn 1.234 into 1234 - a plausible wrong number
        # rather than an obvious failure.
        frame = bytearray(frame_for(value=1.0))
        frame[4] = 0x55                                  # not a real segment pattern
        assert "?" in digits_text(bytes(frame))


class TestFraming:
    """A frame means nothing unless it is read from its start."""

    def test_a_frame_starts_with_a_carriage_return(self):
        assert frame_for(value=1.0)[0] == FRAME_START

    def test_decoding_from_the_wrong_offset_is_refused(self):
        stream = frame_for(value=1.0) + frame_for(value=2.0)
        with pytest.raises(ProtocolError) as excinfo:
            decode(stream[3 : 3 + FRAME_LENGTH])
        assert "starts with" in str(excinfo.value)

    def test_a_short_frame_is_refused(self):
        with pytest.raises(ProtocolError):
            decode(frame_for(value=1.0)[:-1])


class TestFrameAssembler:
    """Frames and echoes share one link and must be told apart by structure."""

    def test_complete_frames_are_recovered_from_a_stream(self):
        assembler = FrameAssembler()
        assembler.feed(frame_for(value=1.0) + frame_for(value=2.0))
        assert len(assembler.frames()) == 2

    def test_a_partial_frame_is_held_until_the_rest_arrives(self):
        assembler = FrameAssembler()
        whole = frame_for(value=1.0)
        assembler.feed(whole[:6])
        assert not assembler.frames()
        assembler.feed(whole[6:])
        assert assembler.frames() == [whole]

    def test_an_echo_is_recovered_as_residue(self):
        assembler = FrameAssembler()
        assembler.feed(b"u" + frame_for(value=1.0))
        assembler.frames()
        assert assembler.residue() == b"u"

    def test_a_digit_byte_equal_to_a_key_character_is_not_mistaken_for_an_echo(self):
        # 0x61 is the pattern for "1." and is also 'a', the Up key. Scanning
        # the stream for the character would find one inside an ordinary
        # reading; taking frames out first cannot.
        frame = frame_for(value=1.2345, measurement_type=2, range_index=1)
        assert 0x61 in frame
        assembler = FrameAssembler()
        assembler.feed(frame)
        assembler.frames()
        assert assembler.residue() == b""


class TestScaling:
    """Reported values are SI units, whatever the display shows."""

    @pytest.mark.parametrize(
        "measurement_type,expected_unit",
        [(1, "V"), (2, "V"), (3, "A"), (4, "A"), (5, "ohm")],
    )
    def test_units(self, measurement_type, expected_unit):
        unit, _scale = unit_and_scale(measurement_type, 1, hertz=False)
        assert unit == expected_unit

    def test_hertz_wins_over_the_measurement_type(self):
        # With Hz selected the display reads frequency whatever jack is in use.
        unit, scale = unit_and_scale(2, 1, hertz=True)
        assert (unit, scale) == ("Hz", 1.0)

    def test_millivolts_are_reported_in_volts(self):
        reading = decode(frame_for(value=0.25, measurement_type=1, range_index=3))
        assert reading.value == pytest.approx(0.25)
        assert reading.unit == "V"

    def test_the_four_hundred_ohm_range_is_not_scaled(self):
        reading = decode(frame_for(value=390.0, measurement_type=5, range_index=0))
        assert reading.value == pytest.approx(390.0)

    @pytest.mark.parametrize("range_index,ohms", [(1, 3900.0), (3, 390000.0), (5, 39000000.0)])
    def test_every_other_ohms_range_displays_kilohms(self, range_index, ohms):
        # Including the top range: 40 Mohm reads 40 000 kohm because the
        # display has 40 000 counts, so one factor of 1000 covers them all.
        reading = decode(frame_for(value=ohms, measurement_type=5, range_index=range_index))
        assert reading.value == pytest.approx(ohms, rel=1e-4)


class TestReadingSemantics:
    """A number is not automatically a measurement."""

    def test_a_negative_reading_carries_its_sign(self):
        reading = decode(frame_for(value=-1.5, measurement_type=2, range_index=1))
        assert reading.value == pytest.approx(-1.5)

    def test_overrange_is_not_a_number(self):
        reading = decode(frame_for(value=1e9, measurement_type=2, range_index=1))
        assert reading.overrange is True
        assert reading.value is None

    def test_ac_is_reported(self):
        assert decode(frame_for(value=1.0, ac=True)).ac is True
        assert decode(frame_for(value=1.0, ac=False)).ac is False

    def test_a_held_display_is_flagged(self):
        sim = SimulatedTti1604(value=1.0)
        sim.status["hold"] = True
        assert decode(sim.frame()).held is True

    def test_a_reviewed_minimum_is_also_held(self):
        # Min-Max review shows a stored reading. It is real, but it is not now.
        sim = SimulatedTti1604(value=1.0)
        sim.status["showing_minimum"] = True
        assert decode(sim.frame()).held is True

    def test_a_live_reading_is_not_held(self):
        assert decode(frame_for(value=1.0)).held is False

    def test_the_raw_frame_is_kept_as_evidence(self):
        frame = frame_for(value=1.0)
        assert decode(frame).raw == frame


#: Seven-segment patterns, for building frames by hand from the published
#: format rather than from the simulator.
_P = {"0": 0xFC, "1": 0x60, "2": 0xDA, "3": 0xF2, "4": 0x66, "5": 0xB6, " ": 0x00}


def hand_frame(units, range_code, text, function=0x40, status=0x02, sign=0):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """A frame built byte by byte: *text* is five glyphs with at most one point."""
    digits = []
    for glyph in text:
        if glyph == ".":
            digits[-1] |= 1
        else:
            digits.append(_P[glyph])
    assert len(digits) == 5
    return bytes([FRAME_START, units | (range_code << 4), function, sign] + digits + [status])


class TestTheManufacturersNote:
    """#115: bit positions as the 1604 remote-control note gives them."""

    def test_the_note_s_worked_example(self):
        # "if the display reads 12.345, characters 4 through 8 will be
        # 96 219 242 102 182"
        frame = bytes([FRAME_START, 2 | (2 << 4), 0x40, 0, 96, 219, 242, 102, 182, 0])
        assert decode(frame).value == pytest.approx(12.345)

    def test_touch_hold_is_bit_one_of_the_function_byte(self):
        reading = decode(hand_frame(2, 1, "1.2345", function=0x02))
        assert reading.flags["touch_hold"] is True
        assert reading.held is True

    def test_bit_zero_of_the_function_byte_is_not_touch_hold(self):
        assert decode(hand_frame(2, 1, "1.2345", function=0x01)).flags["touch_hold"] is False

    def test_auto_range_set_is_bit_one_of_the_status_byte(self):
        assert decode(hand_frame(2, 1, "1.2345", status=0x02)).status["auto_range_set"] is True
        assert decode(hand_frame(2, 1, "1.2345", status=0x04)).status["auto_range_set"] is False


class TestResistanceIsDerived:
    """DMM-FR-016: the k or M the frame does not carry, worked out from the range."""

    @pytest.mark.parametrize(
        "code,text,ohms",
        [
            (0, "123.45", 123.45),        # 400 ohm range, displayed in ohms
            (1, "1.2345", 1234.5),        # 4 k range, displayed in kilohms
            (1, "1234.5", 1234.5),        # the same range displayed in ohms
            (4, "1.2345", 1234500.0),     # 4 M range displayed in megohms
            (4, "1234.5", 1234500.0),     # ... or in kilohms
            (5, "12345", 12345000.0),     # 40 M range in kilohms, as develop assumed
            (5, "12.345", 12345000.0),    # ... or in megohms
        ],
    )
    def test_either_display_convention_reads_right(self, code, text, ohms):
        reading = decode(hand_frame(5, code, text))
        assert reading.value == pytest.approx(ohms)

    def test_a_display_that_fits_no_multiplier_is_not_a_number(self):
        # Two decimals on the 4 k range would be 10 mohm per count.
        reading = decode(hand_frame(5, 1, "123.45"))
        assert reading.value is None
        assert "DMM-OPEN-08" in reading.problem


class TestFrameValidation:
    """DMM-FR-028: a carriage return is not enough to make a frame."""

    def test_a_valid_frame_has_no_problem(self):
        from benchtools.instruments.tti1604.protocol import frame_problem

        assert frame_problem(hand_frame(2, 1, "1.2345")) == ""

    @pytest.mark.parametrize(
        "mutate,why",
        [
            (lambda f: f[:1] + bytes([0x00]) + f[2:], "names no measurement"),
            (lambda f: f[:8] + bytes([0x44]) + f[9:], "not a pattern"),
            (lambda f: f[:4] + bytes([f[4] | 1, f[5] | 1]) + f[6:], "decimal points"),
        ],
    )
    def test_what_is_not_a_frame(self, mutate, why):
        from benchtools.instruments.tti1604.protocol import frame_problem

        assert why in frame_problem(mutate(hand_frame(2, 1, "1.2345")))

    def test_the_assembler_resynchronises_past_a_false_start(self):
        good = hand_frame(2, 1, "1.2345")
        assembler = FrameAssembler()
        assembler.feed(b"\x0d\x21\x40" + good)
        assert assembler.frames() == [good]
        assert assembler.resynchronised == 1

    def test_the_reading_names_its_function_and_range(self):
        reading = decode(hand_frame(2, 2, "12.345"))
        assert reading.function == "dc_volts"
        assert reading.range_label == "40 V"
        assert reading.is_live is True
