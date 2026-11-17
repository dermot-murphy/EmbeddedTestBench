"""What a test reads from a PPK2 measurement: averages, charge and pulses.

Traces to: PPK-FR-006, PPK-FR-008, SWE4-UT-PPKMEAS.
"""

from __future__ import annotations

from array import array

import pytest

from benchtools.instruments.ppk2.measurement import Measurement, find_pulses


def record(values, logic=None, **options):
    """A measurement of *values* amps, one sample per 10 us."""
    result = Measurement(**options)
    result.amps = array("d", values)
    result.logic = array("B", logic if logic is not None else [0] * len(values))
    return result


class TestFigures:
    def test_average_peak_minimum_charge(self):
        result = record([1e-3, 3e-3, 2e-3, 2e-3])
        assert result.samples == 4
        assert result.duration == pytest.approx(40e-6)
        assert result.average == pytest.approx(2e-3)
        assert result.peak == 3e-3 and result.minimum == 1e-3
        assert result.charge == pytest.approx(8e-3 * 10e-6)

    def test_no_samples(self):
        result = record([])
        assert result.average is None and result.peak is None
        assert result.charge == 0.0
        assert result.summary() == "no samples"

    def test_bits(self):
        result = record([0, 0, 0], logic=[0b01, 0b10, 0b11])
        assert result.bits(0) == [1, 0, 1]
        assert result.bits(1) == [0, 1, 1]
        with pytest.raises(ValueError):
            result.bits(8)

    def test_summary_and_dict(self):
        result = record([1e-3] * 10, threshold=0.5e-3)
        result.lost = 2
        assert "average 1.000 mA" in result.summary()
        assert "2 samples lost" in result.summary()
        figures = result.as_dict()
        assert figures["pulses"]["incomplete"] == 1 and "amps" not in figures
        assert result.as_dict(with_samples=True)["amps"] == [1e-3] * 10


class TestPulses:
    def test_whole_pulses_above_a_threshold(self):
        values = [0, 5, 5, 0, 0, 5, 5, 5, 0]
        result = record([v * 1e-3 for v in values], threshold=1e-3)
        pulses = result.pulses
        assert pulses.count == 2 and pulses.incomplete == 0
        assert pulses.widths == pytest.approx((20e-6, 30e-6))
        assert pulses.pulses[0].start == pytest.approx(10e-6)
        assert pulses.charges == pytest.approx((10e-3 * 10e-6, 15e-3 * 10e-6))
        assert pulses.mean_interval == pytest.approx(40e-6)
        assert pulses.pulses[1].average == pytest.approx(5e-3)

    def test_pulses_cut_by_the_ends_are_incomplete(self):
        result = record([5e-3, 0, 5e-3, 0, 5e-3], threshold=1e-3)
        assert result.pulses.count == 1 and result.pulses.incomplete == 2

    def test_release_keeps_a_noisy_top_whole(self):
        values = [0, 5, 0.8, 5, 0]
        assert record([v * 1e-3 for v in values], threshold=1e-3).pulses.count == 2
        held = record([v * 1e-3 for v in values], threshold=1e-3, release=0.5e-3)
        assert held.pulses.count == 1
        assert "until < 0.0005 A" in held.pulses.source

    def test_pulses_marked_by_a_logic_input(self):
        result = record([1, 2, 3, 4, 5], logic=[0, 4, 4, 0, 0], line=2)
        assert result.pulses.source == "D2"
        assert result.pulses.count == 1
        assert result.pulses.pulses[0].charge == pytest.approx(5 * 10e-6)

    def test_no_pulses(self):
        pulses = record([0.0] * 5, threshold=1.0).pulses
        assert pulses.count == 0
        assert pulses.min_width is None and pulses.mean_width is None
        assert pulses.mean_charge is None and pulses.mean_interval is None
        assert pulses.total_charge == 0
        assert record([0.0]).pulses is None

    def test_pulses_above_with_another_threshold(self):
        result = record([0, 2e-3, 0, 6e-3, 0], threshold=1e-3)
        assert result.pulses.count == 2
        assert result.pulses_above(5e-3).count == 1

    def test_find_pulses_directly(self):
        pulses = find_pulses([1.0, 1.0, 1.0], [False, True, False], 1.0, "x")
        assert pulses.count == 1 and pulses.pulses[0].peak == 1.0


@pytest.mark.parametrize("options", [
    {"threshold": 1e-3, "line": 0},
    {"line": 8},
    {"release": 1e-3},
    {"threshold": 1e-3, "release": 2e-3},
])
def test_inconsistent_options_are_refused(options):
    with pytest.raises(ValueError):
        Measurement(**options)
