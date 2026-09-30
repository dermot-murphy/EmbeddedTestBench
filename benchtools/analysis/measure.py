"""Host-side timing analysis of captured waveforms.

An oscilloscope's own measurement subsystem is fast and matches what the
operator sees on screen, but it takes at most two sources at a time. The
headline question - *the spread in time of a number of channels going high* -
is an N-channel one, so it is answered here, from one simultaneously acquired
set of records. Because every channel is digitised against the same time base,
their relative timing is directly comparable.

Nothing here is oscilloscope-specific: the same functions serve a logic
analyser capture, or any other instrument that yields time-aligned records.

Edge times are refined by linear interpolation between the two samples that
straddle the threshold, so timing resolution is not limited to one sample
interval. A hysteresis band prevents noise near the threshold from producing
duplicate edges.

Traces to: ANA-FR-010 .. ANA-FR-017, ANA-DD-MEASURE.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from ..core.enums import EdgeDirection
from ..core.errors import MeasurementError
from .waveform import Waveform

_LOG = logging.getLogger(__name__)

__all__ = [
    "EdgeCrossing",
    "SignalLevels",
    "PeriodResult",
    "SpreadResult",
    "estimate_levels",
    "threshold_for",
    "find_crossings",
    "measure_period",
    "measure_pulse_width",
    "measure_rise_time",
    "measure_channel_spread",
]


@dataclass(frozen=True)
class EdgeCrossing:
    """One threshold crossing located in a waveform.

    :param time: Interpolated crossing time in seconds, relative to the trigger.
    :param index: Index of the first sample at or beyond the threshold.
    :param threshold: Threshold voltage that was crossed.
    :param direction: Polarity of the crossing.
    """

    time: float
    index: int
    threshold: float
    direction: EdgeDirection


@dataclass(frozen=True)
class SignalLevels:
    """Estimated logic levels of a signal.

    :param low: Base level in volts.
    :param high: Top level in volts.
    """

    low: float
    high: float

    @property
    def amplitude(self) -> float:
        """Difference between the top and base levels."""
        return self.high - self.low

    def at_percent(self, percent: float) -> float:
        """Return the voltage *percent* of the way from base to top."""
        return self.low + self.amplitude * (percent / 100.0)


@dataclass
class PeriodResult:
    """Statistics over the periods found in one record.

    :param periods: Every period measured, in seconds.
    :param threshold: Threshold voltage used to locate the edges.
    :param direction: Edge polarity the periods were measured between.
    """

    periods: List[float]
    threshold: float
    direction: EdgeDirection = EdgeDirection.RISE
    source: str = ""

    @property
    def count(self) -> int:
        """Number of periods measured."""
        return len(self.periods)

    @property
    def mean(self) -> float:
        """Mean period in seconds."""
        self._require_data()
        return statistics.fmean(self.periods)

    @property
    def minimum(self) -> float:
        """Shortest period in seconds."""
        self._require_data()
        return min(self.periods)

    @property
    def maximum(self) -> float:
        """Longest period in seconds."""
        self._require_data()
        return max(self.periods)

    @property
    def peak_to_peak_jitter(self) -> float:
        """Difference between the longest and shortest period, in seconds."""
        return self.maximum - self.minimum

    @property
    def standard_deviation(self) -> float:
        """Sample standard deviation of the periods, in seconds.

        Returns ``0.0`` when fewer than two periods were measured.
        """
        self._require_data()
        return statistics.stdev(self.periods) if len(self.periods) > 1 else 0.0

    @property
    def frequency(self) -> float:
        """Mean frequency in hertz."""
        mean = self.mean
        if mean <= 0.0:
            raise MeasurementError("mean period is not positive")
        return 1.0 / mean

    def _require_data(self) -> None:
        if not self.periods:
            raise MeasurementError(
                "no complete period was found on %s; check the threshold, the "
                "time base, and that the channel is displayed" % (self.source or "the source")
            )

    def as_dict(self) -> Dict[str, float]:
        """Return the statistics as a flat dictionary, for reports and CSV."""
        return {
            "source": self.source,
            "count": self.count,
            "mean_s": self.mean,
            "min_s": self.minimum,
            "max_s": self.maximum,
            "stdev_s": self.standard_deviation,
            "pk_pk_jitter_s": self.peak_to_peak_jitter,
            "frequency_hz": self.frequency,
            "threshold_v": self.threshold,
        }


@dataclass
class SpreadResult:
    """Timing spread of several channels crossing a threshold.

    :param crossings: Mapping of channel number to the crossing that was used.
    :param reference: Channel the skews are measured against.
    :param edge_index: Which edge of each channel was used (0 = first).
    :param direction: Polarity of the edges.
    """

    crossings: Dict[int, EdgeCrossing]
    reference: int
    edge_index: int = 0
    direction: EdgeDirection = EdgeDirection.RISE

    def __post_init__(self) -> None:
        if not self.crossings:
            raise MeasurementError("spread requires at least one channel with an edge")
        if self.reference not in self.crossings:
            raise MeasurementError(
                "reference channel %d has no edge; available channels: %s"
                % (self.reference, sorted(self.crossings))
            )

    @property
    def times(self) -> Dict[int, float]:
        """Crossing time per channel, in seconds relative to the trigger."""
        return {channel: crossing.time for channel, crossing in self.crossings.items()}

    @property
    def earliest_channel(self) -> int:
        """Channel that crossed the threshold first."""
        return min(self.times, key=lambda channel: self.times[channel])

    @property
    def latest_channel(self) -> int:
        """Channel that crossed the threshold last."""
        return max(self.times, key=lambda channel: self.times[channel])

    @property
    def earliest(self) -> float:
        """Earliest crossing time in seconds."""
        return self.times[self.earliest_channel]

    @property
    def latest(self) -> float:
        """Latest crossing time in seconds."""
        return self.times[self.latest_channel]

    @property
    def spread(self) -> float:
        """Time between the first and last channel crossing, in seconds.

        This is the headline number: how far apart, in time, the selected
        channels changed state.
        """
        return self.latest - self.earliest

    @property
    def skews(self) -> Dict[int, float]:
        """Crossing time of each channel relative to the reference channel."""
        origin = self.times[self.reference]
        return {channel: time - origin for channel, time in self.times.items()}

    @property
    def mean(self) -> float:
        """Mean crossing time across the channels, in seconds."""
        return statistics.fmean(self.times.values())

    @property
    def standard_deviation(self) -> float:
        """Sample standard deviation of the crossing times, in seconds."""
        values = list(self.times.values())
        return statistics.stdev(values) if len(values) > 1 else 0.0

    def as_dict(self) -> Dict[str, object]:
        """Return the result as a flat dictionary, for reports and CSV."""
        return {
            "direction": self.direction.value,
            "edge_index": self.edge_index,
            "reference_channel": self.reference,
            "channel_times_s": dict(sorted(self.times.items())),
            "skews_s": dict(sorted(self.skews.items())),
            "earliest_channel": self.earliest_channel,
            "latest_channel": self.latest_channel,
            "spread_s": self.spread,
            "mean_s": self.mean,
            "stdev_s": self.standard_deviation,
        }


# ---------------------------------------------------------------------------
# Level and threshold estimation
# ---------------------------------------------------------------------------
def estimate_levels(waveform: Waveform, bins: int = 64) -> SignalLevels:
    """Estimate the base and top levels of a two-state signal.

    A histogram is built over the record and the most populated bin in each
    half is taken as that half's level. This is the same idea as the
    instrument's own high/low algorithm and is far more robust than min/max on
    a signal with overshoot or ringing.

    Falls back to the record's minimum and maximum when the histogram is
    degenerate, for example on a flat or single-edge record.

    :param bins: Number of histogram bins.
    :raises MeasurementError: if the record is empty.
    """
    if not waveform.volts:
        raise MeasurementError("cannot estimate levels of an empty record")
    if waveform.is_clipped:
        _LOG.warning(
            "%s is clipped (%d samples at the digitiser rail): level estimation "
            "and any threshold derived from it will be wrong. Reduce volts/div "
            "or change the channel position and capture again.",
            waveform.source or "the record", waveform.clipped_sample_count,
        )
    lowest = waveform.minimum
    highest = waveform.maximum
    span = highest - lowest
    if span <= 0.0 or bins < 4:
        return SignalLevels(low=lowest, high=highest)

    counts = [0] * bins
    width = span / bins
    for value in waveform.volts:
        index = int((value - lowest) / width)
        if index >= bins:
            index = bins - 1
        counts[index] += 1

    midpoint = bins // 2
    lower_bin = max(range(0, midpoint), key=lambda i: counts[i])
    upper_bin = max(range(midpoint, bins), key=lambda i: counts[i])

    # A bin is only credible as a level if it holds a meaningful share of the
    # record; otherwise the signal is not really bimodal.
    threshold_count = max(len(waveform.volts) // (bins * 4), 1)
    if counts[lower_bin] < threshold_count or counts[upper_bin] < threshold_count:
        return SignalLevels(low=lowest, high=highest)

    low = lowest + width * (lower_bin + 0.5)
    high = lowest + width * (upper_bin + 0.5)
    return SignalLevels(low=low, high=high)


def threshold_for(
    waveform: Waveform,
    percent: float = 50.0,
    absolute_threshold: Optional[float] = None,
    levels: Optional[SignalLevels] = None,
) -> Tuple[float, SignalLevels]:
    """Resolve the threshold voltage to use for *waveform*.

    :param percent: Percentage of the base-to-top amplitude, used when
        *absolute_threshold* is ``None``.
    :param absolute_threshold: Explicit threshold in volts, overriding *percent*.
    :param levels: Pre-computed levels, to avoid re-estimating them.
    :returns: ``(threshold_volts, levels)``.
    """
    resolved = levels if levels is not None else estimate_levels(waveform)
    if absolute_threshold is not None:
        return float(absolute_threshold), resolved
    if not 0.0 <= percent <= 100.0:
        raise ValueError("percent must be in 0..100, got %r" % (percent,))
    return resolved.at_percent(percent), resolved


# ---------------------------------------------------------------------------
# Edge detection
# ---------------------------------------------------------------------------
def find_crossings(
    waveform: Waveform,
    threshold: float,
    direction: EdgeDirection = EdgeDirection.RISE,
    hysteresis: float = 0.0,
    max_edges: Optional[int] = None,
) -> List[EdgeCrossing]:
    """Locate threshold crossings in *waveform*.

    The crossing time is interpolated linearly between the straddling samples,
    so resolution is finer than the sample interval.

    :param threshold: Threshold voltage.
    :param direction: ``RISE`` or ``FALL``.
    :param hysteresis: Volts by which the signal must retreat past the
        threshold before another crossing of the same polarity is accepted.
        Suppresses duplicate edges caused by noise.
    :param max_edges: Stop after this many crossings.
    :returns: Crossings in time order, possibly empty.
    """
    direction = EdgeDirection.coerce(direction)
    if hysteresis < 0.0:
        raise ValueError("hysteresis must not be negative, got %r" % (hysteresis,))

    volts = waveform.volts
    times = waveform.times
    if len(volts) < 2:
        return []

    rising = direction is EdgeDirection.RISE
    arm_level = threshold - hysteresis if rising else threshold + hysteresis

    def beyond(value: float) -> bool:
        return value >= threshold if rising else value <= threshold

    def retreated(value: float) -> bool:
        return value < arm_level if rising else value > arm_level

    crossings: List[EdgeCrossing] = []
    armed = retreated(volts[0]) or not beyond(volts[0])

    for index in range(1, len(volts)):
        previous = volts[index - 1]
        current = volts[index]
        if armed and not beyond(previous) and beyond(current):
            delta = current - previous
            if delta == 0.0:
                crossing_time = times[index]
            else:
                fraction = (threshold - previous) / delta
                crossing_time = times[index - 1] + fraction * (times[index] - times[index - 1])
            crossings.append(
                EdgeCrossing(
                    time=crossing_time,
                    index=index,
                    threshold=threshold,
                    direction=direction,
                )
            )
            armed = False
            if max_edges is not None and len(crossings) >= max_edges:
                break
        elif not armed and retreated(current):
            armed = True

    return crossings


# ---------------------------------------------------------------------------
# Derived measurements
# ---------------------------------------------------------------------------
def measure_period(
    waveform: Waveform,
    percent: float = 50.0,
    absolute_threshold: Optional[float] = None,
    direction: EdgeDirection = EdgeDirection.RISE,
    hysteresis_percent: float = 10.0,
) -> PeriodResult:
    """Measure every period in *waveform* from same-polarity crossings.

    :param percent: Threshold as a percentage of amplitude (mid-point by default).
    :param absolute_threshold: Explicit threshold in volts.
    :param direction: Edge polarity to measure between.
    :param hysteresis_percent: Hysteresis band as a percentage of amplitude.
    :raises MeasurementError: if fewer than two edges are present.
    """
    threshold, levels = threshold_for(waveform, percent, absolute_threshold)
    hysteresis = levels.amplitude * (hysteresis_percent / 100.0)
    crossings = find_crossings(waveform, threshold, direction, hysteresis)
    if len(crossings) < 2:
        raise MeasurementError(
            "need at least two %s edges on %s to measure a period, found %d; "
            "reduce the time base or check the threshold (%.4g V)"
            % (direction.value.lower(), waveform.source or "the record", len(crossings), threshold)
        )
    periods = [
        crossings[index + 1].time - crossings[index].time
        for index in range(len(crossings) - 1)
    ]
    return PeriodResult(
        periods=periods,
        threshold=threshold,
        direction=direction,
        source=waveform.source,
    )


def measure_pulse_width(
    waveform: Waveform,
    percent: float = 50.0,
    absolute_threshold: Optional[float] = None,
    positive: bool = True,
    hysteresis_percent: float = 10.0,
) -> List[float]:
    """Measure the width of each pulse in *waveform*, in seconds.

    :param positive: ``True`` for high-time (rise to fall), ``False`` for
        low-time (fall to rise).
    :returns: One width per complete pulse, in time order.
    """
    threshold, levels = threshold_for(waveform, percent, absolute_threshold)
    hysteresis = levels.amplitude * (hysteresis_percent / 100.0)
    opening = EdgeDirection.RISE if positive else EdgeDirection.FALL
    closing = EdgeDirection.FALL if positive else EdgeDirection.RISE
    starts = find_crossings(waveform, threshold, opening, hysteresis)
    ends = find_crossings(waveform, threshold, closing, hysteresis)

    widths: List[float] = []
    for start in starts:
        for end in ends:
            if end.time > start.time:
                widths.append(end.time - start.time)
                break
    return widths


def measure_rise_time(
    waveform: Waveform,
    low_percent: float = 10.0,
    high_percent: float = 90.0,
    edge_index: int = 0,
    falling: bool = False,
) -> float:
    """Measure a single transition time, by default 10% to 90%.

    :param edge_index: Which transition to measure, 0 for the first.
    :param falling: Measure a falling transition instead of a rising one.
    :raises MeasurementError: if the requested transition is not present.
    """
    if not 0.0 <= low_percent < high_percent <= 100.0:
        raise ValueError("require 0 <= low_percent < high_percent <= 100")
    levels = estimate_levels(waveform)
    direction = EdgeDirection.FALL if falling else EdgeDirection.RISE
    hysteresis = levels.amplitude * 0.05

    first_percent = high_percent if falling else low_percent
    second_percent = low_percent if falling else high_percent
    first = find_crossings(waveform, levels.at_percent(first_percent), direction, hysteresis)
    second = find_crossings(waveform, levels.at_percent(second_percent), direction, hysteresis)

    if len(first) <= edge_index or len(second) <= edge_index:
        raise MeasurementError(
            "transition %d not found on %s" % (edge_index, waveform.source or "the record")
        )
    interval = second[edge_index].time - first[edge_index].time
    if interval < 0.0:
        raise MeasurementError("transition end precedes its start; the record may be corrupt")
    return interval


def measure_channel_spread(
    waveforms: Mapping[int, Waveform],
    direction: EdgeDirection = EdgeDirection.RISE,
    percent: float = 50.0,
    absolute_threshold: Optional[float] = None,
    edge_index: int = 0,
    reference: Optional[int] = None,
    hysteresis_percent: float = 10.0,
    require_all: bool = True,
) -> SpreadResult:
    """Measure how far apart several channels cross a threshold.

    This answers "what is the spread in time of these channels going high".
    Each channel's threshold is derived from its own amplitude by default, so
    channels at different logic levels or different volts/div settings are
    compared at their own mid-points.

    :param waveforms: Channel number to :class:`Waveform`, all from one
        acquisition so that they share a time base.
    :param direction: ``RISE`` for going high, ``FALL`` for going low.
    :param percent: Threshold as a percentage of each channel's amplitude.
    :param absolute_threshold: Explicit threshold in volts, applied to every
        channel; overrides *percent*.
    :param edge_index: Which edge of each channel to use, 0 for the first.
    :param reference: Channel the skews are reported against; defaults to the
        earliest channel.
    :param hysteresis_percent: Hysteresis band as a percentage of amplitude.
    :param require_all: Raise if any channel lacks the requested edge, instead
        of silently reporting the spread of the remainder.
    :raises MeasurementError: if fewer than two channels yield an edge, or if
        *require_all* is set and a channel has no such edge.
    """
    if len(waveforms) < 2:
        raise MeasurementError(
            "a spread needs at least two channels, got %d" % len(waveforms)
        )
    direction = EdgeDirection.coerce(direction)
    if edge_index < 0:
        raise ValueError("edge_index must not be negative, got %r" % (edge_index,))

    crossings: Dict[int, EdgeCrossing] = {}
    missing: List[int] = []
    for channel in sorted(waveforms):
        waveform = waveforms[channel]
        threshold, levels = threshold_for(waveform, percent, absolute_threshold)
        hysteresis = levels.amplitude * (hysteresis_percent / 100.0)
        found = find_crossings(
            waveform, threshold, direction, hysteresis, max_edges=edge_index + 1
        )
        if len(found) <= edge_index:
            missing.append(channel)
            continue
        crossings[channel] = found[edge_index]

    if missing and require_all:
        raise MeasurementError(
            "no %s edge number %d on channel(s) %s; the channels may not all be "
            "switching within the captured window"
            % (direction.value.lower(), edge_index, ", ".join(str(c) for c in missing))
        )
    if len(crossings) < 2:
        raise MeasurementError(
            "found edges on fewer than two channels, so no spread can be reported"
        )

    if reference is None:
        reference = min(crossings, key=lambda channel: crossings[channel].time)
    elif reference not in crossings:
        raise MeasurementError("reference channel %d has no usable edge" % reference)

    return SpreadResult(
        crossings=crossings,
        reference=reference,
        edge_index=edge_index,
        direction=direction,
    )
