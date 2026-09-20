"""Host-side timing analysis.

The tests build waveforms with exactly known timing so the measured values can
be checked against ground truth rather than against the code's own output.

Traces to: SWE1-FR-060, SWE1-FR-061, SWE1-FR-062, SWE4-UT-MEASURE.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.tek3014b.constants import EdgeDirection
from benchtools.core.errors import MeasurementError
from benchtools.analysis.measure import (
    estimate_levels,
    find_crossings,
    measure_channel_spread,
    measure_period,
    measure_pulse_width,
    measure_rise_time,
    threshold_for,
)
from benchtools.analysis.waveform import Waveform

SAMPLE_INTERVAL = 100.0e-12   # 100 ps, 10 GSa/s
POINTS = 50000                # 5 us of record
PERIOD = 1.0e-6
AMPLITUDE = 3.3


def square_wave(source: str, delay: float = 0.0, rise_time: float = 0.0) -> Waveform:
    """Build a 1 MHz, 50% duty square wave delayed by *delay* seconds.

    The waveform starts low so that the first rising edge is unambiguous.
    """
    times = [index * SAMPLE_INTERVAL for index in range(POINTS)]
    volts = []
    for t in times:
        phase = (t - delay - 0.25 * PERIOD) % PERIOD
        if rise_time and phase < rise_time:
            volts.append(AMPLITUDE * (phase / rise_time))
        elif phase < 0.5 * PERIOD:
            volts.append(AMPLITUDE)
        elif rise_time and phase < 0.5 * PERIOD + rise_time:
            volts.append(AMPLITUDE * (1.0 - (phase - 0.5 * PERIOD) / rise_time))
        else:
            volts.append(0.0)
    return Waveform(source=source, times=times, volts=volts)


class TestLevelEstimation:
    def test_levels_of_a_clean_square_wave(self):
        levels = estimate_levels(square_wave("CH1"))
        assert levels.low == pytest.approx(0.0, abs=0.1)
        assert levels.high == pytest.approx(AMPLITUDE, abs=0.1)
        assert levels.amplitude == pytest.approx(AMPLITUDE, abs=0.2)

    def test_midpoint_threshold(self):
        levels = estimate_levels(square_wave("CH1"))
        assert levels.at_percent(50.0) == pytest.approx(AMPLITUDE / 2.0, abs=0.1)

    def test_flat_signal_falls_back_to_min_max(self):
        flat = Waveform("CH1", [0.0, 1.0e-9, 2.0e-9], [1.0, 1.0, 1.0])
        levels = estimate_levels(flat)
        assert levels.low == 1.0 and levels.high == 1.0

    def test_empty_record_is_rejected(self):
        with pytest.raises(MeasurementError, match="empty record"):
            estimate_levels(Waveform("CH1", [], []))

    def test_absolute_threshold_overrides_percent(self):
        threshold, _ = threshold_for(square_wave("CH1"), percent=50.0, absolute_threshold=None)
        assert threshold == pytest.approx(1.65, abs=0.1)
        fixed, _ = threshold_for(square_wave("CH1"), absolute_threshold=0.8)
        assert fixed == 0.8

    def test_percent_outside_the_range_is_rejected(self):
        with pytest.raises(ValueError):
            threshold_for(square_wave("CH1"), percent=150.0)


class TestEdgeDetection:
    def test_rising_edges_are_found_at_the_expected_times(self):
        waveform = square_wave("CH1")
        crossings = find_crossings(waveform, threshold=1.65, direction=EdgeDirection.RISE)
        assert len(crossings) == 5
        # First rising edge is a quarter period in, then every period after.
        for index, crossing in enumerate(crossings):
            assert crossing.time == pytest.approx(0.25 * PERIOD + index * PERIOD, abs=SAMPLE_INTERVAL)

    def test_falling_edges_are_found(self):
        crossings = find_crossings(square_wave("CH1"), 1.65, EdgeDirection.FALL)
        assert len(crossings) == 5
        assert crossings[0].time == pytest.approx(0.75 * PERIOD, abs=SAMPLE_INTERVAL)

    def test_interpolation_beats_the_sample_interval(self):
        """A 0.35-sample delay must be resolved, not rounded to a whole sample."""
        offset = 0.35 * SAMPLE_INTERVAL
        reference = find_crossings(square_wave("CH1", rise_time=2.0e-9), 1.65)[0]
        shifted = find_crossings(square_wave("CH1", delay=offset, rise_time=2.0e-9), 1.65)[0]
        assert (shifted.time - reference.time) == pytest.approx(offset, abs=5.0e-13)

    def test_hysteresis_suppresses_noise_retriggering(self):
        """A dip that does not clear the hysteresis band must not add an edge."""
        times = [index * SAMPLE_INTERVAL for index in range(9)]
        volts = [0.0, 0.0, 3.3, 3.3, 1.7, 3.3, 3.3, 3.3, 3.3]   # brief dip to just above mid
        waveform = Waveform("CH1", times, volts)
        assert len(find_crossings(waveform, 1.65, hysteresis=0.0)) == 1
        assert len(find_crossings(waveform, 1.65, hysteresis=1.0)) == 1

    def test_max_edges_limits_the_search(self):
        assert len(find_crossings(square_wave("CH1"), 1.65, max_edges=2)) == 2

    def test_negative_hysteresis_is_rejected(self):
        with pytest.raises(ValueError):
            find_crossings(square_wave("CH1"), 1.65, hysteresis=-0.1)

    def test_short_record_yields_no_edges(self):
        assert find_crossings(Waveform("CH1", [0.0], [0.0]), 1.0) == []


class TestPeriod:
    def test_period_matches_the_synthesised_signal(self):
        result = measure_period(square_wave("CH1"))
        assert result.mean == pytest.approx(PERIOD, rel=1e-6)
        assert result.frequency == pytest.approx(1.0e6, rel=1e-6)
        assert result.count == 4

    def test_jitter_of_an_ideal_signal_is_negligible(self):
        result = measure_period(square_wave("CH1"))
        assert result.peak_to_peak_jitter == pytest.approx(0.0, abs=1.0e-15)
        assert result.standard_deviation == pytest.approx(0.0, abs=1.0e-15)

    def test_statistics_are_exported_as_a_dict(self):
        summary = measure_period(square_wave("CH1")).as_dict()
        assert summary["source"] == "CH1"
        assert summary["mean_s"] == pytest.approx(PERIOD, rel=1e-6)

    def test_too_few_edges_is_reported_clearly(self):
        flat = Waveform("CH1", [i * SAMPLE_INTERVAL for i in range(100)], [0.0] * 100)
        with pytest.raises(MeasurementError, match="at least two"):
            measure_period(flat)

    def test_falling_edge_periods_agree(self):
        result = measure_period(square_wave("CH1"), direction=EdgeDirection.FALL)
        assert result.mean == pytest.approx(PERIOD, rel=1e-6)


class TestPulseWidthAndRiseTime:
    def test_positive_pulse_width_is_half_the_period(self):
        widths = measure_pulse_width(square_wave("CH1"), positive=True)
        assert widths[0] == pytest.approx(0.5 * PERIOD, rel=1e-6)

    def test_negative_pulse_width_is_half_the_period(self):
        widths = measure_pulse_width(square_wave("CH1"), positive=False)
        assert widths[0] == pytest.approx(0.5 * PERIOD, rel=1e-6)

    def test_rise_time_of_a_linear_ramp(self):
        """A 2 ns 0-100% ramp has a 10-90% rise time of 1.6 ns."""
        measured = measure_rise_time(square_wave("CH1", rise_time=2.0e-9))
        assert measured == pytest.approx(1.6e-9, rel=0.02)

    def test_missing_transition_is_reported(self):
        flat = Waveform("CH1", [i * SAMPLE_INTERVAL for i in range(100)], [0.0] * 100)
        with pytest.raises(MeasurementError, match="not found"):
            measure_rise_time(flat)

    def test_inverted_percentages_are_rejected(self):
        with pytest.raises(ValueError):
            measure_rise_time(square_wave("CH1"), low_percent=90.0, high_percent=10.0)


class TestChannelSpread:
    """The headline requirement: spread in time of N channels going high."""

    @pytest.fixture
    def skewed(self):
        skews = {1: 0.0, 2: 12.0e-9, 3: 25.0e-9, 4: 5.0e-9}
        return skews, {
            channel: square_wave("CH%d" % channel, delay=delay, rise_time=2.0e-9)
            for channel, delay in skews.items()
        }

    def test_spread_equals_the_injected_skew(self, skewed):
        skews, waveforms = skewed
        result = measure_channel_spread(waveforms)
        assert result.spread == pytest.approx(max(skews.values()) - min(skews.values()), abs=2.0e-12)

    def test_per_channel_skews_are_recovered(self, skewed):
        skews, waveforms = skewed
        result = measure_channel_spread(waveforms)
        for channel, expected in skews.items():
            assert result.skews[channel] == pytest.approx(expected, abs=2.0e-12)

    def test_first_and_last_channels_are_identified(self, skewed):
        _, waveforms = skewed
        result = measure_channel_spread(waveforms)
        assert result.earliest_channel == 1
        assert result.latest_channel == 3

    def test_reference_channel_can_be_chosen(self, skewed):
        _, waveforms = skewed
        result = measure_channel_spread(waveforms, reference=3)
        assert result.skews[3] == 0.0
        assert result.skews[1] == pytest.approx(-25.0e-9, abs=2.0e-12)
        assert result.spread == pytest.approx(25.0e-9, abs=2.0e-12)

    def test_falling_edge_spread(self, skewed):
        _skews, waveforms = skewed
        result = measure_channel_spread(waveforms, direction=EdgeDirection.FALL)
        assert result.spread == pytest.approx(25.0e-9, abs=2.0e-12)

    def test_absolute_threshold_is_applied_to_every_channel(self, skewed):
        _, waveforms = skewed
        result = measure_channel_spread(waveforms, absolute_threshold=1.65)
        assert all(c.threshold == 1.65 for c in result.crossings.values())

    def test_later_edge_can_be_selected(self, skewed):
        _, waveforms = skewed
        first = measure_channel_spread(waveforms, edge_index=0)
        second = measure_channel_spread(waveforms, edge_index=1)
        assert second.spread == pytest.approx(first.spread, abs=2.0e-12)
        assert second.earliest - first.earliest == pytest.approx(PERIOD, rel=1e-6)

    def test_statistics_are_exported(self, skewed):
        _, waveforms = skewed
        summary = measure_channel_spread(waveforms).as_dict()
        assert summary["earliest_channel"] == 1
        assert summary["spread_s"] == pytest.approx(25.0e-9, abs=2.0e-12)
        assert set(summary["skews_s"]) == {1, 2, 3, 4}

    def test_one_channel_is_rejected(self, skewed):
        _, waveforms = skewed
        with pytest.raises(MeasurementError, match="at least two channels"):
            measure_channel_spread({1: waveforms[1]})

    def test_a_channel_without_an_edge_is_reported(self, skewed):
        _, waveforms = skewed
        flat = Waveform("CH4", waveforms[4].times, [0.0] * len(waveforms[4]))
        with pytest.raises(MeasurementError, match="channel\\(s\\) 4"):
            measure_channel_spread({1: waveforms[1], 2: waveforms[2], 4: flat})

    def test_missing_channel_can_be_tolerated(self, skewed):
        _, waveforms = skewed
        flat = Waveform("CH4", waveforms[4].times, [0.0] * len(waveforms[4]))
        result = measure_channel_spread(
            {1: waveforms[1], 2: waveforms[2], 4: flat}, require_all=False
        )
        assert set(result.crossings) == {1, 2}

    def test_unusable_reference_is_reported(self, skewed):
        _, waveforms = skewed
        with pytest.raises(MeasurementError, match="reference channel"):
            measure_channel_spread(waveforms, reference=9)
