"""Round-trip timing, and the honesty rules around it.

Traces to: BLE-FR-050 .. BLE-FR-053, BLE-FR-118, SWE4-UT-BLELATENCY.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import MeasurementError
from benchtools.instruments.nordic_dongle.latency import (
    LatencySource,
    ResponseSample,
    ResponseTiming,
)


def timing(*microseconds, interval_us=30_000, source=LatencySource.DONGLE):
    return ResponseTiming(
        samples=[
            ResponseSample(request="version", response=b"1.4.2", dongle_us=value,
                           host_s=value / 1.0e6)
            for value in microseconds
        ],
        source=source,
        connection_interval_us=interval_us,
        request="version",
    )


class TestStatistics:
    def test_mean_of_one_sample(self):
        assert timing(95_000).milliseconds == pytest.approx(95.0)

    def test_statistics_over_several(self):
        result = timing(90_000, 100_000, 110_000)
        assert result.count == 3
        assert result.milliseconds == pytest.approx(100.0)
        assert result.minimum_s == pytest.approx(0.090)
        assert result.maximum_s == pytest.approx(0.110)
        assert result.spread_s == pytest.approx(0.020)
        assert result.standard_deviation_s == pytest.approx(0.01)

    def test_one_sample_has_no_deviation(self):
        assert timing(95_000).standard_deviation_s == 0.0

    def test_no_samples_is_an_error_not_a_zero(self):
        result = ResponseTiming(samples=[], request="version")
        with pytest.raises(MeasurementError, match="not zero latency"):
            _ = result.seconds

    def test_the_replies_are_available(self):
        assert timing(95_000).responses == ["1.4.2"]


class TestWhichClock:
    def test_the_dongle_clock_is_the_default(self):
        result = timing(95_000)
        assert result.source is LatencySource.DONGLE
        assert result.resolution_s == pytest.approx(1e-6)

    def test_the_host_clock_resolves_a_millisecond(self):
        """Not the microsecond perf_counter will happily print: the figure
        carries USB polling and OS scheduling."""
        result = timing(95_000, source=LatencySource.HOST)
        assert result.resolution_s == pytest.approx(1e-3)

    def test_the_host_figure_is_used_when_asked_for(self):
        result = ResponseTiming(
            samples=[ResponseSample(dongle_us=1_000, host_s=0.5)],
            source=LatencySource.HOST,
        )
        assert result.seconds == pytest.approx(0.5)

    def test_the_dongle_figure_falls_back_to_the_host(self):
        """Older firmware may not report dt_us; the figure is still honest,
        it is simply the other clock's."""
        result = ResponseTiming(samples=[ResponseSample(dongle_us=None, host_s=0.25)])
        assert result.seconds == pytest.approx(0.25)


class TestTrustworthiness:
    def test_a_latency_well_above_the_connection_interval_is_trusted(self):
        assert timing(95_000, interval_us=30_000).is_trustworthy is True

    def test_a_latency_inside_the_connection_interval_is_not(self):
        """A reply cannot arrive between connection events, so 12.5 ms on a
        30 ms link measures where the write landed, not the firmware."""
        assert timing(12_500, interval_us=30_000).is_trustworthy is False

    def test_a_latency_below_the_clock_resolution_is_not(self):
        result = timing(500, interval_us=0, source=LatencySource.HOST)
        assert result.is_trustworthy is False

    def test_without_a_connection_interval_only_resolution_matters(self):
        assert timing(95_000, interval_us=0).is_trustworthy is True

    def test_no_samples_is_not_trustworthy(self):
        assert ResponseTiming(samples=[]).is_trustworthy is False

    def test_the_quantisation_is_the_connection_interval(self):
        assert timing(95_000, interval_us=30_000).quantisation_s == pytest.approx(0.030)


class TestSerialisation:
    def test_as_dict_carries_the_figure_and_its_caveats(self):
        summary = timing(95_000).as_dict()
        assert summary["milliseconds"] == pytest.approx(95.0)
        assert summary["source"] == "DONGLE"
        assert summary["connection_interval_us"] == 30_000
        assert summary["trustworthy"] is True
        assert summary["responses"] == ["1.4.2"]

    def test_as_dict_survives_no_samples(self):
        summary = ResponseTiming(samples=[], request="version").as_dict()
        assert summary["count"] == 0
        assert summary["trustworthy"] is False
        assert "seconds" not in summary

    def test_a_sample_serialises_both_clocks(self):
        sample = ResponseSample(request="temp", response=b"23.5", dongle_us=95_000, host_s=0.1)
        summary = sample.as_dict()
        assert summary["response"] == "23.5"
        assert summary["response_hex"] == b"23.5".hex()
        assert summary["dongle_us"] == 95_000
        assert summary["host_us"] == pytest.approx(100_000.0)

    def test_text_decoding_survives_binary(self):
        assert ResponseSample(response=b"\xff\xfe").text != ""

    def test_repr_survives_no_samples(self):
        assert "no samples" in repr(ResponseTiming(samples=[], request="version"))


@pytest.mark.parametrize("reply, value", [
    (b"ACK RD SHA = a8e37e892", "a8e37e892"),
    (b"ACK RD VERSION = V11.00.0000-31-ga8e37e892\r\n", "V11.00.0000-31-ga8e37e892"),
    (b"ACK X = a = b", "a = b"),                 # only the first " = " separates
    (b"NACK Invalid Command", ""),
])
def test_the_value_a_reply_reports(reply, value):
    """#102: RD SHA's value is compared with a VERSION frame's SHA."""
    assert ResponseSample(request="RD", response=reply).value == value
