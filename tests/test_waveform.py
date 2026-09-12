"""Waveform block parsing, scaling and export.

Traces to: SWE1-FR-050, SWE1-FR-051, SWE4-UT-WAVEFORM.
"""

from __future__ import annotations

import csv
import struct

import pytest

from tek3014b.errors import ProtocolError
from tek3014b.waveform import (
    Waveform,
    WaveformPreamble,
    decode_curve,
    parse_ieee_block,
    waveforms_to_csv,
)


class TestBlockParsing:
    def test_definite_length_block(self):
        assert parse_ieee_block(b"#41000" + b"x" * 1000) == b"x" * 1000

    def test_block_with_a_trailing_terminator(self):
        assert parse_ieee_block(b"#14abcd\n") == b"abcd"

    def test_indefinite_length_block(self):
        assert parse_ieee_block(b"#0abcd\n") == b"abcd"

    def test_payload_may_contain_the_terminator(self):
        assert parse_ieee_block(b"#13a\nb\n") == b"a\nb"

    def test_response_without_a_header_passes_through(self):
        assert parse_ieee_block(b"1.0,2.0,3.0") == b"1.0,2.0,3.0"

    def test_empty_response_is_rejected(self):
        with pytest.raises(ProtocolError, match="empty response"):
            parse_ieee_block(b"")

    def test_truncated_payload_is_detected(self):
        with pytest.raises(ProtocolError, match="truncated"):
            parse_ieee_block(b"#41000abc")

    def test_malformed_header_is_detected(self):
        with pytest.raises(ProtocolError, match="malformed"):
            parse_ieee_block(b"#xy1234")


class TestCurveDecoding:
    def test_signed_single_byte(self):
        assert decode_curve(b"\x00\x7f\x81", width=1, signed=True) == [0, 127, -127]

    def test_unsigned_single_byte(self):
        assert decode_curve(b"\x00\x7f\x81", width=1, signed=False) == [0, 127, 129]

    def test_signed_two_byte_is_big_endian(self):
        payload = struct.pack(">hhh", 1000, -1000, 32767)
        assert decode_curve(payload, width=2, signed=True) == [1000, -1000, 32767]

    def test_odd_payload_for_two_byte_points_is_rejected(self):
        with pytest.raises(ProtocolError, match="whole number"):
            decode_curve(b"\x01\x02\x03", width=2)

    def test_invalid_width_is_rejected(self):
        with pytest.raises(ValueError):
            decode_curve(b"\x01", width=4)


class TestScaling:
    """The scaling must match the TDS3000 programmer manual exactly."""

    @pytest.fixture
    def preamble(self):
        return WaveformPreamble(
            x_increment=1.0e-9, x_zero=0.0, point_offset=2.0,
            y_multiplier=0.04, y_zero=0.5, y_offset=25.0, point_count=5,
        )

    def test_time_axis_is_referenced_to_the_trigger(self, preamble):
        # Xn = XZERO + XINCR * (n - PT_OFF), so index 2 is t = 0.
        assert preamble.time_at(0) == pytest.approx(-2.0e-9)
        assert preamble.time_at(2) == pytest.approx(0.0)
        assert preamble.time_at(4) == pytest.approx(2.0e-9)

    def test_start_index_offsets_the_time_axis(self):
        """A partial transfer must still report absolute record times."""
        preamble = WaveformPreamble(
            x_increment=1.0e-9, x_zero=0.0, point_offset=2.0,
            y_multiplier=1.0, y_zero=0.0, y_offset=0.0, start_index=10,
        )
        assert preamble.time_at(0) == pytest.approx(8.0e-9)

    def test_voltage_scaling(self, preamble):
        # Yn = YZERO + YMULT * (raw - YOFF)
        assert preamble.volts_at(25.0) == pytest.approx(0.5)
        assert preamble.volts_at(50.0) == pytest.approx(0.5 + 0.04 * 25)

    def test_sample_rate(self, preamble):
        assert preamble.sample_rate == pytest.approx(1.0e9)

    def test_non_positive_increment_is_rejected(self):
        bad = WaveformPreamble(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        with pytest.raises(ProtocolError):
            _ = bad.sample_rate

    def test_from_payload_does_not_re_parse_a_header(self, preamble):
        """A payload starting with 0x23 must be treated as data, not a header."""
        payload = bytes([35, 40, 45, 50, 0])       # b"#(-2\x00"
        waveform = Waveform.from_payload("CH1", payload, preamble, width=1)
        assert waveform.raw == [35, 40, 45, 50, 0]

    def test_from_block_and_from_payload_agree(self, preamble):
        payload = bytes([35, 40, 45, 50, 0])
        from_block = Waveform.from_block("CH1", b"#15" + payload, preamble)
        from_payload = Waveform.from_payload("CH1", payload, preamble)
        assert from_block.raw == from_payload.raw

    def test_from_ascii_decodes_comma_separated_codes(self, preamble):
        waveform = Waveform.from_ascii("CH1", b"0,25,50,25,0\n", preamble)
        assert waveform.raw == [0, 25, 50, 25, 0]
        assert waveform.volts[1] == pytest.approx(0.5)

    def test_from_ascii_tolerates_a_block_header(self, preamble):
        waveform = Waveform.from_ascii("CH1", b"#204" + b"1,2\n", preamble)
        assert waveform.raw == [1, 2]

    def test_from_ascii_rejects_rubbish(self, preamble):
        with pytest.raises(ProtocolError, match="unparsable ASCII"):
            Waveform.from_ascii("CH1", b"1,two,3", preamble)

    def test_from_codes_scales_directly(self, preamble):
        waveform = Waveform.from_codes("CH1", [0, 25, 50], preamble)
        assert waveform.volts[1] == pytest.approx(0.5)
        assert waveform.times[2] == pytest.approx(0.0)

    def test_from_block_round_trip(self, preamble):
        payload = struct.pack(">bbbbb", 0, 25, 50, 25, 0)
        waveform = Waveform.from_block("CH1", b"#15" + payload, preamble, width=1)
        assert len(waveform) == 5
        assert waveform.raw == [0, 25, 50, 25, 0]
        assert waveform.volts[1] == pytest.approx(0.5)
        assert waveform.times[2] == pytest.approx(0.0)


class TestWaveformStatistics:
    @pytest.fixture
    def waveform(self):
        times = [i * 1.0e-9 for i in range(5)]
        return Waveform("CH1", times, [0.0, 1.0, 2.0, 1.0, 0.0], raw=[0, 25, 50, 25, 0])

    def test_basic_statistics(self, waveform):
        assert waveform.minimum == 0.0
        assert waveform.maximum == 2.0
        assert waveform.peak_to_peak == 2.0
        assert waveform.mean == pytest.approx(0.8)
        assert waveform.duration == pytest.approx(4.0e-9)

    def test_interpolated_value(self, waveform):
        assert waveform.value_at(0.5e-9) == pytest.approx(0.5)
        assert waveform.value_at(-1.0e-9) == 0.0     # clamped to the first sample
        assert waveform.value_at(99.0) == 0.0        # clamped to the last sample

    def test_mismatched_axes_are_rejected(self):
        with pytest.raises(ValueError, match="same length"):
            Waveform("CH1", [0.0, 1.0], [0.0])

    def test_clipping_detection(self):
        clean = Waveform("CH1", [0.0, 1.0], [0.0, 1.0], raw=[10, 20])
        clipped = Waveform("CH2", [0.0, 1.0], [0.0, 1.0], raw=[127, -127])
        assert not clean.is_clipped
        assert clipped.is_clipped
        assert clipped.clipped_sample_count == 2

    def test_clipping_threshold_follows_the_transfer_width(self):
        preamble = WaveformPreamble(1e-9, 0.0, 0.0, 1.0, 0.0, 0.0)
        wide = Waveform.from_block("CH1", b"#14" + struct.pack(">hh", 127 * 256, 0),
                                   preamble, width=2)
        assert wide.full_scale_code == 127 * 256
        assert wide.clipped_sample_count == 1


class TestExport:
    def test_single_channel_csv(self, tmp_path):
        waveform = Waveform("CH1", [0.0, 1.0e-9], [0.0, 3.3], raw=[0, 82])
        path = waveform.to_csv(str(tmp_path / "one.csv"), include_raw=True)
        rows = list(csv.reader(open(path, encoding="utf-8")))
        assert rows[0] == ["time_s", "ch1_volts", "raw_code"]
        assert rows[2] == ["1e-09", "3.3", "82"]

    def test_multi_channel_csv_shares_a_time_column(self, tmp_path):
        waveforms = {
            1: Waveform("CH1", [0.0, 1.0e-9], [0.0, 3.3]),
            2: Waveform("CH2", [0.0, 1.0e-9], [1.0, 2.0]),
        }
        path = waveforms_to_csv(waveforms, str(tmp_path / "multi.csv"))
        rows = list(csv.reader(open(path, encoding="utf-8")))
        assert rows[0] == ["time_s", "ch1_volts", "ch2_volts"]
        assert rows[1] == ["0", "0", "1"]

    def test_mismatched_lengths_are_rejected(self, tmp_path):
        waveforms = {
            1: Waveform("CH1", [0.0], [0.0]),
            2: Waveform("CH2", [0.0, 1.0], [0.0, 1.0]),
        }
        with pytest.raises(ValueError, match="different record lengths"):
            waveforms_to_csv(waveforms, str(tmp_path / "bad.csv"))

    def test_empty_export_is_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="no waveforms"):
            waveforms_to_csv({}, str(tmp_path / "none.csv"))
