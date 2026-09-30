"""Decoding a 1604 measurement frame.

The tests are organised around the ways this meter can make a test lie: a
frame decoded from the wrong offset, a digit pattern read as the wrong figure,
an ohms reading off by a factor of a thousand, a held display recorded as a
live measurement, and an overrange treated as a number.

Traces to: DMM-FR-010 .. DMM-FR-032, SWE4-UT-DMM.
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
