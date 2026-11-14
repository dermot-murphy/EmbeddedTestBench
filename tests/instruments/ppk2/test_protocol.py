"""The PPK2's wire format: metadata, calibration, samples and commands.

The metadata text below is what the bench's PPK2 (USB serial number
D527E1DA8DBA) sent on 2026-11-14 (#342).

Traces to: PPK-FR-002 .. PPK-FR-004, SWE4-UT-PPKPROTO.
"""

from __future__ import annotations

import struct

import pytest

from benchtools.instruments.ppk2.constants import ADC_MULT, DEFAULT_MODIFIERS
from benchtools.instruments.ppk2.protocol import (
    Calibration,
    SampleDecoder,
    metadata_command,
    mode_command,
    parse_metadata,
    regulator_command,
    running_command,
    split_word,
    start_command,
    stop_command,
)

BENCH_METADATA = (
    "Calibrated: 0\nR0: 1004.8547\nR1: 102.5943\nR2: 10.4701\nR3: 0.9865\nR4: 0.0566\n"
    "GS0: 0.0000\nGS1: 179.2937\nGS2: 28.0154\nGS3: 3.8656\nGS4: 0.1159\nGI0: 1.0000\n"
    "GI1: 0.9499\nGI2: 0.9411\nGI3: 0.9257\nGI4: 0.9358\nO0: 172.5869\nO1: 122.6466\n"
    "O2: 101.9233\nO3: 79.7622\nO4: 138.2979\nVDD: 4000\nHW: 59726\nmode: 2\n"
    "S0: -0.000000155\nS1: -0.000001307\nS2: -0.000013108\nS3: -0.000150009\n"
    "S4: -0.000290115\nI0: 0.000000429\nI1: 0.000003400\nI2: 0.000113989\n"
    "I3: 0.000036334\nI4: -0.001048059\nUG0: 1.00\nUG1: 1.00\nUG2: 1.00\nUG3: 1.00\n"
    "UG4: 1.00\nIA: 56\nEND\n")


def word(adc, current_range, counter, logic=0):
    """A streamed sample, built the way the kit packs one."""
    return struct.pack("<I", adc | (current_range << 14) | (counter << 18) | (logic << 24))


def bench_calibration():
    """The bench kit's calibration."""
    return Calibration.from_metadata(parse_metadata(BENCH_METADATA))


class TestMetadata:
    def test_the_bench_kit_s_text(self):
        meta = parse_metadata(BENCH_METADATA)
        assert meta["vdd"] == 4000 and meta["mode"] == 2 and meta["hw"] == 59726
        assert meta["r0"] == pytest.approx(1004.8547)
        assert meta["s4"] == pytest.approx(-0.000290115)
        assert "end" not in meta

    def test_nan_is_none_and_text_is_kept(self):
        meta = parse_metadata("GS0: -nan\nNote: hello\r\nbroken line\n")
        assert meta == {"gs0": None, "note": "hello"}

    def test_calibration_takes_the_kit_s_values(self):
        calibration = bench_calibration()
        assert calibration.r[4] == pytest.approx(0.0566)
        assert calibration.o[0] == pytest.approx(172.5869)
        assert calibration.ug == (1.0,) * 5

    def test_zero_and_missing_keep_nordic_s_defaults(self):
        # GS0 is 0.0000 on the bench kit; Nordic's app keeps its default, 1.
        assert bench_calibration().gs[0] == DEFAULT_MODIFIERS["gs"][0]
        assert Calibration.from_metadata({}) == Calibration()

    def test_a_value_that_is_not_a_number_keeps_the_default(self):
        calibration = Calibration.from_metadata({"r0": "garbled", "r1": None, "r2": True})
        assert calibration.r[:3] == DEFAULT_MODIFIERS["r"][:3]


class TestConversion:
    def test_the_formula(self):
        calibration = bench_calibration()
        adc, k, vdd = 4000, 1, 4000
        raw = (adc - calibration.o[k]) * (ADC_MULT / calibration.r[k])
        expected = calibration.ug[k] * (raw * (calibration.gs[k] * raw + calibration.gi[k])
                                        + calibration.s[k] * vdd / 1000 + calibration.i[k])
        assert calibration.amps(k, adc, vdd) == pytest.approx(expected)

    @pytest.mark.parametrize("amps", [2e-7, 15e-6, 4e-4, 8e-3, 0.3])
    def test_adc_inverts_amps_to_within_a_count(self, amps):
        calibration = bench_calibration()
        for k in range(5):
            adc = calibration.adc(k, amps, 3300)
            if 4 < adc < 0x3FFF * 4:
                step = calibration.amps(k, adc + 4, 3300) - calibration.amps(k, adc, 3300)
                assert calibration.amps(k, adc, 3300) == pytest.approx(amps, abs=abs(step))

    def test_split_word(self):
        (value,) = struct.unpack("<I", word(0x1234, 3, 0x2A, 0xA5))
        assert split_word(value) == (0x1234 * 4, 3, 0x2A, 0xA5)

    def test_a_range_above_four_is_read_as_four(self):
        (value,) = struct.unpack("<I", word(1, 7, 0))
        assert split_word(value)[1] == 4


class TestDecoder:
    def test_words_split_across_reads(self):
        decoder = SampleDecoder(Calibration(), 3300, spike_filter=False)
        data = b"".join(word(1000, 0, n, n & 1) for n in range(5))
        assert decoder.feed(data[:7]) == 1
        assert decoder.feed(data[7:]) == 4
        assert decoder.count == 5
        assert list(decoder.logic) == [0, 1, 0, 1, 0]
        assert decoder.amps[0] == pytest.approx(Calibration().amps(0, 4000, 3300))

    def test_lost_samples_are_counted_from_the_counter(self):
        decoder = SampleDecoder(Calibration(), 3300)
        decoder.feed(b"".join(word(100, 0, n) for n in (60, 61, 62, 63, 0, 5, 6)))
        assert decoder.lost == 4
        assert decoder.count == 7

    def test_the_spike_filter_smooths_three_samples_after_a_range_change(self):
        values = [(2000, 0)] * 5 + [(2000, 1)] * 6
        data = b"".join(word(adc, k, n) for n, (adc, k) in enumerate(values))
        raw = SampleDecoder(Calibration(), 3300, spike_filter=False)
        raw.feed(data)
        smooth = SampleDecoder(Calibration(), 3300)
        smooth.feed(data)
        changed = [n for n in range(len(values)) if raw.amps[n] != smooth.amps[n]]
        assert changed == [5, 6, 7]
        assert raw.amps[5] > smooth.amps[5] > raw.amps[4]

    def test_the_top_range_holds_the_previous_average_for_two_samples(self):
        values = [(2000, 3)] * 4 + [(2000, 4)] * 4
        data = b"".join(word(adc, k, n) for n, (adc, k) in enumerate(values))
        smooth = SampleDecoder(Calibration(), 3300)
        smooth.feed(data)
        assert smooth.amps[4] == pytest.approx(smooth.amps[3])


class TestCommands:
    def test_bytes(self):
        assert metadata_command() == b"\x19"
        assert start_command() == b"\x06"
        assert stop_command() == b"\x07"
        assert running_command(True) == b"\x0c\x01"
        assert running_command(False) == b"\x0c\x00"
        assert mode_command(1) == b"\x11\x01"
        assert mode_command(2) == b"\x11\x02"

    def test_the_regulator_takes_millivolts_high_byte_first(self):
        assert regulator_command(3.3) == bytes([0x0D, 0x0C, 0xE4])
        assert regulator_command(0.8) == bytes([0x0D, 0x03, 0x20])

    @pytest.mark.parametrize("volts", [0.7, 5.1, -1])
    def test_a_voltage_outside_the_range_is_refused(self, volts):
        with pytest.raises(ValueError, match="0.8 V to 5.0 V"):
            regulator_command(volts)

    def test_an_unknown_mode_is_refused(self):
        with pytest.raises(ValueError):
            mode_command(3)
