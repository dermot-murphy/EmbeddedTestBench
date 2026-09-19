"""Measuring the time between two code locations.

The simulated firmware puts the two locations exactly 64 000 cycles apart, which
is exactly 1.000 ms at 64 MHz. Three of the four methods should recover that
figure exactly; the fourth measures host latency and must say so.

Traces to: JLINK-FR-060 .. JLINK-FR-065, SWE4-UT-TIMING.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError, MeasurementError
from benchtools.instruments.jlink import ProbeLimits, TimingMethod
from benchtools.instruments.jlink.timing import TimingResult, TimingSample

from .conftest import END_LOCATION, INTERVAL_CYCLES, INTERVAL_SECONDS, START_LOCATION


class TestCycleCounter:
    def test_recovers_the_exact_interval(self, probe):
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION, method=TimingMethod.CYCLE_COUNTER
        )
        assert result.cycles == INTERVAL_CYCLES
        assert result.seconds == pytest.approx(INTERVAL_SECONDS)
        assert result.milliseconds == pytest.approx(1.0)

    def test_dwt_is_enabled_first(self, probe):
        """Without TRCENA and CYCCNTENA the counter reads zero and every
        measurement silently returns nothing."""
        probe.measure_time_between(START_LOCATION, END_LOCATION)
        log = probe.session.transport.responder.monitor_log
        assert any("trace register" in entry for entry in log)

    def test_repeat_gives_statistics(self, probe):
        result = probe.measure_time_between(START_LOCATION, END_LOCATION, repeat=3)
        assert result.count == 3
        assert result.minimum == pytest.approx(result.maximum)
        assert result.standard_deviation == pytest.approx(0.0)
        assert result.spread == pytest.approx(0.0)

    def test_breakpoints_are_cleaned_up(self, probe):
        before = len(probe.list_breakpoints())
        probe.measure_time_between(START_LOCATION, END_LOCATION)
        assert len(probe.list_breakpoints()) == before

    def test_result_records_the_method_and_clock(self, probe):
        result = probe.measure_time_between(START_LOCATION, END_LOCATION)
        assert result.method is TimingMethod.CYCLE_COUNTER
        assert result.core_clock_hz == 64.0e6
        assert result.halts_target is True

    def test_core_clock_scales_the_result(self, probe):
        """A wrong core clock makes every measurement wrong by that ratio, so it
        must be a deliberate setting rather than a guess."""
        probe._limits = ProbeLimits(core_clock_hz=32.0e6)
        result = probe.measure_time_between(START_LOCATION, END_LOCATION)
        assert result.cycles == INTERVAL_CYCLES
        assert result.seconds == pytest.approx(INTERVAL_CYCLES / 32.0e6)


class TestHostClock:
    def test_produces_a_figure(self, probe):
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION, method=TimingMethod.HOST_CLOCK
        )
        assert result.count == 1
        assert result.seconds > 0.0
        assert result.cycles is None

    def test_a_short_interval_is_flagged_untrustworthy(self, probe):
        """The method resolves about a millisecond. A microsecond figure from it
        is noise presented as a measurement, and a test should refuse it rather
        than tighten its limit."""
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION, method=TimingMethod.HOST_CLOCK
        )
        assert result.resolution_seconds == pytest.approx(1.0e-3)
        assert result.is_trustworthy is False


class TestTargetTimer:
    def test_from_two_variables_filled_in_by_the_firmware(self, probe):
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION,
            method=TimingMethod.TARGET_TIMER,
            start_variable="timer_start", end_variable="timer_end", timer_hz=64.0e6,
        )
        assert result.cycles == INTERVAL_CYCLES
        assert result.seconds == pytest.approx(INTERVAL_SECONDS)
        assert result.halts_target is True

    def test_reading_one_timer_at_both_points(self, probe):
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION,
            method=TimingMethod.TARGET_TIMER,
            timer_variable="sensor_count", timer_hz=1000.0,
        )
        assert result.count == 1

    def test_without_any_variable_is_rejected(self, probe):
        with pytest.raises(ConfigurationError, match="TARGET_TIMER needs"):
            probe.measure_time_between(
                START_LOCATION, END_LOCATION, method=TimingMethod.TARGET_TIMER
            )


class TestSwo:
    def test_recovers_the_interval_without_halting(self, probe):
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION, method=TimingMethod.SWO_ITM, itm_port=1
        )
        assert result.cycles == INTERVAL_CYCLES
        assert result.seconds == pytest.approx(INTERVAL_SECONDS)
        assert result.halts_target is False

    def test_a_port_with_no_instrumentation_is_reported(self, probe):
        with pytest.raises(MeasurementError, match="SWO produced"):
            probe.measure_time_between(
                START_LOCATION, END_LOCATION, method=TimingMethod.SWO_ITM, itm_port=9
            )


class TestValidationAndArithmetic:
    def test_repeat_must_be_positive(self, probe):
        with pytest.raises(ConfigurationError, match="repeat"):
            probe.measure_time_between(START_LOCATION, END_LOCATION, repeat=0)

    def test_counter_wrap_is_handled(self):
        """The DWT counter wraps every 67 s at 64 MHz; without this a wrapped
        interval reads as a huge negative number."""
        from benchtools.instruments.jlink.probe import JLinkProbe

        assert JLinkProbe._counter_delta(0xFFFFFF00, 0x00000100) == 0x200
        assert JLinkProbe._counter_delta(100, 200) == 100

    def test_method_accepts_a_string(self, probe):
        assert probe.measure_time_between(
            START_LOCATION, END_LOCATION, method="cycle_counter"
        ).method is TimingMethod.CYCLE_COUNTER

    def test_unreachable_location_is_reported(self, probe):
        with pytest.raises((MeasurementError, Exception)):
            probe.measure_time_between("nowhere.c:1", END_LOCATION, timeout=0.3)


class TestResolutionIsAlwaysReported:
    """JLINK-FR-065 and JLINK-NFR-004: a figure without its resolution is not a
    measurement. Regression tests for D-08, where the target timer reported no
    resolution and was therefore trusted unconditionally."""

    @pytest.mark.parametrize(
        "method", [TimingMethod.CYCLE_COUNTER, TimingMethod.SWO_ITM, TimingMethod.TARGET_TIMER]
    )
    def test_a_counting_method_resolves_one_tick(self, method):
        result = TimingResult(
            method=method, samples=[TimingSample(seconds=1.0e-3, cycles=64_000)],
            start="a", end="b", core_clock_hz=64.0e6,
        )
        assert result.resolution_seconds == pytest.approx(1.0 / 64.0e6)
        assert result.is_trustworthy is True

    def test_the_target_timer_resolves_its_own_rate_not_the_core_clock(self, probe):
        """A 32 kHz RTC resolves 30 us, whatever the core is doing."""
        result = probe.measure_time_between(
            START_LOCATION, END_LOCATION, method=TimingMethod.TARGET_TIMER,
            start_variable="timer_start", end_variable="timer_end", timer_hz=32_768,
        )
        assert result.resolution_seconds == pytest.approx(1.0 / 32_768)

    def test_a_short_interval_on_a_slow_timer_is_flagged(self):
        """64 000 ticks of a 32 kHz timer is 1.95 s; 5 ticks is not resolvable."""
        result = TimingResult(
            method=TimingMethod.TARGET_TIMER,
            samples=[TimingSample(seconds=5.0 / 32_768, cycles=5)],
            start="a", end="b", core_clock_hz=32_768.0,
        )
        assert result.is_trustworthy is False

    def test_an_unknown_resolution_is_not_trusted(self):
        """Nothing known about the quantisation is not the same as perfect."""
        result = TimingResult(
            method=TimingMethod.CYCLE_COUNTER,
            samples=[TimingSample(seconds=1.0e-3, cycles=64_000)],
            start="a", end="b", core_clock_hz=None,
        )
        assert result.resolution_seconds is None
        assert result.is_trustworthy is False

    def test_every_method_reports_a_resolution_through_the_probe(self, probe):
        """The property a report quotes must be populated on every path."""
        attempts = [
            (TimingMethod.CYCLE_COUNTER, {}),
            (TimingMethod.HOST_CLOCK, {}),
            (TimingMethod.SWO_ITM, {"itm_port": 1}),
            (TimingMethod.TARGET_TIMER,
             {"start_variable": "timer_start", "end_variable": "timer_end", "timer_hz": 64.0e6}),
        ]
        for method, options in attempts:
            result = probe.measure_time_between(START_LOCATION, END_LOCATION,
                                                method=method, **options)
            assert result.resolution_seconds is not None, method
            assert result.as_dict()["resolution_seconds"] is not None, method


class TestResultType:
    def test_no_samples_is_an_error_not_a_zero(self):
        """Reporting 0 s for a measurement that never happened would pass a
        limit of 'less than 1 ms'."""
        result = TimingResult(method=TimingMethod.CYCLE_COUNTER, start="a", end="b")
        with pytest.raises(MeasurementError, match="no timing samples"):
            _ = result.seconds

    def test_statistics_over_varying_samples(self):
        result = TimingResult(
            method=TimingMethod.CYCLE_COUNTER,
            core_clock_hz=64.0e6,
            samples=[
                TimingSample(seconds=1.0e-3, cycles=64_000),
                TimingSample(seconds=1.1e-3, cycles=70_400),
                TimingSample(seconds=0.9e-3, cycles=57_600),
            ],
        )
        assert result.seconds == pytest.approx(1.0e-3)
        assert result.minimum == pytest.approx(0.9e-3)
        assert result.maximum == pytest.approx(1.1e-3)
        assert result.spread == pytest.approx(0.2e-3)
        assert result.standard_deviation > 0.0
        assert result.cycles == pytest.approx(64_000)

    def test_serialises_for_a_report(self):
        result = TimingResult(
            method=TimingMethod.CYCLE_COUNTER, core_clock_hz=64.0e6,
            start="a", end="b", samples=[TimingSample(seconds=1.0e-3, cycles=64_000)],
        )
        summary = result.as_dict()
        assert summary["method"] == "CYCLE_COUNTER"
        assert summary["cycles"] == 64_000
        assert summary["microseconds"] == pytest.approx(1000.0)
        assert summary["trustworthy"] is True

    def test_methods_without_cycles_omit_them(self):
        result = TimingResult(
            method=TimingMethod.HOST_CLOCK, samples=[TimingSample(seconds=0.5)]
        )
        assert "cycles" not in result.as_dict()
        assert result.cycles is None

    def test_repr_survives_no_samples(self):
        assert "no samples" in repr(TimingResult(method=TimingMethod.HOST_CLOCK))
