"""Advertising profile arithmetic.

The awkward parts of an advertising profile are not the averages: they are the
three-packet advertising event, the jitter the specification requires, and the
difference between a beacon the sensor did not send and one the link lost. Each
gets its own tests here, against hand-built event lists where the right answer
is known by construction.

Traces to: BLE-FR-030 .. BLE-FR-035, SWE4-UT-BLEPROFILE.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import MeasurementError
from benchtools.instruments.nordic_dongle.profile import (
    ADV_DELAY_MAX_S,
    COALESCE_WINDOW_S,
    AdvertisingEvent,
    AdvertisingProfile,
)

ADDRESS = "E4:1C:7B:02:9A:11"


def events(timestamps_us, address=ADDRESS, channel=37):
    return [
        AdvertisingEvent(timestamp_us=int(when), address=address, rssi=-60, channel=channel)
        for when in timestamps_us
    ]


def steady(count, interval_us=100_000, start_us=1_000_000):
    return events(start_us + index * interval_us for index in range(count))


class TestIntervals:
    def test_a_steady_sensor(self):
        profile = AdvertisingProfile(events=steady(11), address=ADDRESS, duration_s=1.0)
        assert profile.count == 11
        assert profile.mean_interval_s == pytest.approx(0.100)
        assert profile.jitter_s == pytest.approx(0.0)
        assert profile.rate_hz == pytest.approx(10.0)

    def test_minimum_maximum_and_spread(self):
        profile = AdvertisingProfile(
            events=events([0, 100_000, 205_000, 300_000]), duration_s=0.3
        )
        assert profile.minimum_interval_s == pytest.approx(0.095)
        assert profile.maximum_interval_s == pytest.approx(0.105)
        assert profile.spread_s == pytest.approx(0.010)

    def test_one_event_cannot_give_an_interval(self):
        """Reporting 0 s would be a measurement; this is the absence of one."""
        profile = AdvertisingProfile(events=steady(1), address=ADDRESS)
        with pytest.raises(MeasurementError, match="At least two advertising events"):
            _ = profile.mean_interval_s

    def test_no_events_at_all(self):
        profile = AdvertisingProfile(events=[], address=ADDRESS)
        assert profile.count == 0
        with pytest.raises(MeasurementError):
            _ = profile.mean_interval_s

    def test_events_out_of_order_are_sorted(self):
        """Nothing guarantees arrival order across a queue."""
        profile = AdvertisingProfile(events=events([200_000, 0, 100_000]))
        assert profile.intervals == pytest.approx([0.1, 0.1])


class TestCoalescing:
    def test_three_channels_are_one_advertising_event(self):
        """37, 38 and 39 within a few hundred microseconds is one beacon."""
        burst = events([0, 300, 700, 100_000, 100_400, 200_000])
        profile = AdvertisingProfile(events=burst, duration_s=0.2)
        assert profile.reports == 6
        assert profile.count == 3
        assert profile.intervals == pytest.approx([0.1, 0.1])

    def test_the_first_report_of_a_burst_is_kept(self):
        profile = AdvertisingProfile(events=events([0, 300, 700]))
        assert profile.advertising_events[0].timestamp_us == 0

    def test_a_gap_just_outside_the_window_is_two_events(self):
        gap = int((COALESCE_WINDOW_S * 1.01) * 1e6)
        assert AdvertisingProfile(events=events([0, gap])).count == 2


class TestJitter:
    def test_the_expected_jitter_is_the_specification_figure(self):
        """Uniform 0-10 ms has a standard deviation of 10/sqrt(12) ms."""
        profile = AdvertisingProfile(events=steady(5))
        assert profile.expected_jitter_s == pytest.approx(ADV_DELAY_MAX_S / (12 ** 0.5))
        assert profile.expected_jitter_s == pytest.approx(0.002887, abs=1e-6)

    def test_a_conforming_sensor_is_within_specification(self):
        """100 ms nominal with delays of 0 to 10 ms is correct behaviour.

        The last interval is exactly nominal, which is the case that a
        float-subtracted interval fails by 2e-17 (defect D-15).
        """
        times = [0, 100_000, 203_000, 310_000, 410_000]
        profile = AdvertisingProfile(events=events(times), duration_s=0.41)
        assert profile.within_specification(nominal_s=0.100) is True

    def test_a_sensor_advertising_too_slowly_is_not(self):
        times = [0, 130_000, 260_000]
        profile = AdvertisingProfile(events=events(times), duration_s=0.26)
        assert profile.within_specification(nominal_s=0.100) is False

    def test_a_sensor_advertising_too_fast_is_not(self):
        profile = AdvertisingProfile(events=events([0, 80_000, 160_000]), duration_s=0.16)
        assert profile.within_specification(nominal_s=0.100, tolerance_s=0.005) is False


class TestMissedEvents:
    def test_a_missing_beacon_is_found(self):
        profile = AdvertisingProfile(
            events=events([0, 100_000, 300_000, 400_000]),
            duration_s=0.4,
            expected_interval_s=0.1,
        )
        assert profile.missed_events == 1
        assert len(profile.gaps) == 1

    def test_several_missing_in_one_gap(self):
        profile = AdvertisingProfile(
            events=events([0, 100_000, 500_000]), duration_s=0.5, expected_interval_s=0.1
        )
        assert profile.missed_events == 3

    def test_advertising_delay_is_not_counted_as_a_miss(self):
        """A 110 ms interval on a 100 ms sensor is advDelay, not a dropout."""
        profile = AdvertisingProfile(
            events=events([0, 110_000, 220_000, 330_000]),
            duration_s=0.33,
            expected_interval_s=0.1,
        )
        assert profile.missed_events == 0

    def test_the_nominal_interval_can_be_inferred(self):
        """With no specification figure, the median less the mean advDelay."""
        profile = AdvertisingProfile(events=events([0, 105_000, 210_000, 315_000]))
        assert profile.interval_was_measured is True
        assert profile.nominal_interval_s == pytest.approx(0.100, abs=1e-6)

    def test_a_given_interval_is_used_as_given(self):
        profile = AdvertisingProfile(events=steady(4), expected_interval_s=0.02)
        assert profile.interval_was_measured is False
        assert profile.nominal_interval_s == 0.02


class TestDutyCycleAndCounts:
    def test_a_steady_sensor_has_full_duty(self):
        profile = AdvertisingProfile(
            events=steady(11), duration_s=1.0, expected_interval_s=0.1
        )
        assert profile.duty_cycle == pytest.approx(1.0)
        assert profile.reception_ratio == pytest.approx(1.0)

    def test_a_sensor_that_goes_quiet(self):
        """Ten beacons, then a second of silence, then ten more."""
        times = [index * 100_000 for index in range(10)]
        times += [1_900_000 + index * 100_000 for index in range(10)]
        profile = AdvertisingProfile(
            events=events(times), duration_s=2.8, expected_interval_s=0.1
        )
        assert profile.missed_events == 9
        assert 0.5 < profile.duty_cycle < 0.75
        assert profile.reception_ratio < 0.8

    def test_expected_events_over_the_window(self):
        profile = AdvertisingProfile(
            events=steady(11), duration_s=1.0, expected_interval_s=0.1
        )
        assert profile.expected_events == 11

    def test_duty_cycle_needs_two_events(self):
        assert AdvertisingProfile(events=steady(1)).duty_cycle == 0.0


class TestCompleteness:
    def test_a_lossless_capture(self):
        profile = AdvertisingProfile(events=steady(5), radio_events=5, dongle_dropped=0)
        assert profile.is_complete is True
        assert profile.lost_reports == 0

    def test_a_lossy_capture_is_declared(self):
        """The dongle saw eight, the host received five: the missing three are
        the link's, and the profile must not blame the sensor."""
        profile = AdvertisingProfile(events=steady(5), radio_events=8)
        assert profile.is_complete is False
        assert profile.lost_reports == 3

    def test_a_dongle_that_dropped_lines_is_not_complete(self):
        profile = AdvertisingProfile(events=steady(5), radio_events=5, dongle_dropped=2)
        assert profile.is_complete is False

    def test_without_counters_only_drops_are_known(self):
        assert AdvertisingProfile(events=steady(5)).is_complete is True


class TestSerialisation:
    def test_as_dict_carries_the_assertable_figures(self):
        profile = AdvertisingProfile(
            events=steady(11), address=ADDRESS, duration_s=1.0, expected_interval_s=0.1,
            radio_events=11,
        )
        summary = profile.as_dict()
        assert summary["address"] == ADDRESS
        assert summary["count"] == 11
        assert summary["mean_interval_ms"] == pytest.approx(100.0)
        assert summary["missed_events"] == 0
        assert summary["is_complete"] is True

    def test_as_dict_survives_too_few_events(self):
        """A failing capture must still produce a report, not an exception."""
        summary = AdvertisingProfile(events=steady(1), address=ADDRESS).as_dict()
        assert summary["count"] == 1
        assert summary["nominal_interval_s"] is None
        assert "mean_interval_s" not in summary

    def test_an_event_serialises(self):
        event = AdvertisingEvent(
            timestamp_us=5, address=ADDRESS, rssi=-62, payload=b"\x02\x01\x06"
        )
        assert event.as_dict()["payload"] == "020106"
        assert event.timestamp_s == pytest.approx(5e-6)

    def test_exactly_nominal_intervals_are_exact(self):
        """Regression for D-15: 100 000 us must read as 0.1, not 0.099999..."""
        profile = AdvertisingProfile(events=steady(5))
        assert profile.intervals == [0.1, 0.1, 0.1, 0.1]
        assert all(interval >= 0.1 for interval in profile.intervals)

    def test_repr_survives_no_events(self):
        assert "report" in repr(AdvertisingProfile(events=[], address=ADDRESS))
