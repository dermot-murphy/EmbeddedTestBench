"""Advertising profile: what a sensor's beacon actually looks like on the air.

Three things make this less obvious than "subtract consecutive timestamps", and
each is handled here rather than left to whoever reads the numbers:

**One advertising event is up to three packets.** A sensor advertises on
channels 37, 38 and 39 within a few hundred microseconds. A scanner sitting on
one channel usually sees one of them, but not always, and counting all three as
separate events would report an interval of 200 us and a wildly wrong rate.
Reports closer together than :data:`COALESCE_WINDOW_S` are therefore treated as
one advertising event, and the first is kept.

**The Bluetooth specification requires jitter.** Every advertising interval
carries a random delay of 0 to 10 ms (Core spec, advDelay), so a perfectly
healthy sensor advertising at 100 ms shows a spread of 10 ms and a standard
deviation near 2.9 ms. A profile that reported that as instability would fail
every good sensor, so the expected contribution is stated and
:meth:`AdvertisingProfile.within_specification` allows for it.

**A missing event and a missing USB packet look identical.** If the host simply
counts what arrived, a dongle that dropped lines reports a sensor that skipped
beacons. The firmware therefore counts what the radio delivered, the host counts
what it received, and :attr:`AdvertisingProfile.is_complete` says whether the
two agree. A profile that is not complete is reported as such rather than
quietly averaged.

Traces to: BLE-FR-030 .. BLE-FR-035, BLE-DD-PROFILE.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ...core.errors import MeasurementError
from .constants import AddressType

__all__ = [
    "AdvertisingEvent",
    "AdvertisingProfile",
    "COALESCE_WINDOW_S",
    "ADV_DELAY_MAX_S",
]

#: Reports closer together than this belong to one advertising event, on
#: different channels. Well above the ~300 us it takes to advertise on three
#: channels, well below the 20 ms minimum advertising interval.
COALESCE_WINDOW_S = 0.005

#: The largest random delay the Core specification adds to each advertising
#: interval. Its standard deviation, for a uniform distribution, is
#: ``ADV_DELAY_MAX_S / sqrt(12)``, about 2.9 ms.
ADV_DELAY_MAX_S = 0.010


@dataclass
class AdvertisingEvent:
    """One advertising report, as the dongle saw it.

    :param timestamp_us: The dongle's microsecond timestamp. This is the
        measurement.
    :param host_time: The host's arrival time, from :func:`time.time`. A
        cross-check only: it carries USB and scheduling jitter of about a
        millisecond, which is the same order as the quantity being measured.
    :param channel: Primary advertising channel, 37 to 39, when the stack
        reports it.
    """

    timestamp_us: int
    address: str
    rssi: int
    address_type: AddressType = AddressType.RANDOM_STATIC
    channel: int = 0
    scan_response: bool = False
    name: str = ""
    payload: bytes = b""
    host_time: Optional[float] = None

    @property
    def timestamp_s(self) -> float:
        """The dongle timestamp in seconds."""
        return self.timestamp_us / 1.0e6

    def as_dict(self) -> dict:
        """Flat mapping for a report or a log line."""
        return {
            "timestamp_us": self.timestamp_us,
            "host_time": self.host_time,
            "address": self.address,
            "address_type": int(self.address_type),
            "rssi": self.rssi,
            "channel": self.channel,
            "scan_response": self.scan_response,
            "name": self.name,
            "payload": self.payload.hex(),
        }


@dataclass
class AdvertisingProfile:
    """Statistics over a capture of advertising events.

    :param events: Reports in arrival order.
    :param address: The address profiled.
    :param duration_s: Length of the capture window.
    :param expected_interval_s: The sensor's nominal advertising interval, when
        it is known. Given, not guessed, whenever the specification being
        verified names one; otherwise the median measured interval is used and
        :attr:`interval_was_measured` says so.
    :param radio_events: Reports the *dongle* counted, for reconciliation.
    :param dongle_dropped: Lines the dongle could not send to the host.
    """

    events: List[AdvertisingEvent] = field(default_factory=list)
    address: str = ""
    duration_s: float = 0.0
    expected_interval_s: Optional[float] = None
    radio_events: Optional[int] = None
    dongle_dropped: int = 0

    # ------------------------------------------------------------------
    @property
    def reports(self) -> int:
        """Advertising reports received, before coalescing."""
        return len(self.events)

    @property
    def advertising_events(self) -> List[AdvertisingEvent]:
        """Reports coalesced into advertising events, one per beacon.

        The first report of each group is kept: it is the earliest evidence of
        that advertising event, so the interval is measured from the same point
        each time even when a different channel is heard.
        """
        kept: List[AdvertisingEvent] = []
        for event in sorted(self.events, key=lambda item: item.timestamp_us):
            if kept and (event.timestamp_s - kept[-1].timestamp_s) < COALESCE_WINDOW_S:
                continue
            kept.append(event)
        return kept

    @property
    def count(self) -> int:
        """Advertising events, after coalescing. The figure to quote."""
        return len(self.advertising_events)

    @property
    def intervals(self) -> List[float]:
        """Seconds between consecutive advertising events.

        Subtracted as integer microseconds and converted once. Subtracting two
        floats instead puts an exactly nominal 100 ms interval at
        0.09999999999999998, which fails a limit written as ">= 0.1" - a sensor
        rejected by floating-point representation rather than by behaviour.
        """
        events = self.advertising_events
        return [
            (events[index + 1].timestamp_us - events[index].timestamp_us) / 1.0e6
            for index in range(len(events) - 1)
        ]

    def _require_intervals(self) -> List[float]:
        intervals = self.intervals
        if not intervals:
            raise MeasurementError(
                "no advertising interval could be measured from %d report(s) "
                "for %s. At least two advertising events are needed; check the "
                "sensor is advertising, the address filter is right, and the "
                "capture was long enough."
                % (self.reports, self.address or "the selected sensor")
            )
        return intervals

    # ------------------------------------------------------------------
    @property
    def mean_interval_s(self) -> float:
        """Mean advertising interval in seconds."""
        return statistics.fmean(self._require_intervals())

    @property
    def minimum_interval_s(self) -> float:
        return min(self._require_intervals())

    @property
    def maximum_interval_s(self) -> float:
        return max(self._require_intervals())

    @property
    def spread_s(self) -> float:
        """Longest interval minus shortest."""
        intervals = self._require_intervals()
        return max(intervals) - min(intervals)

    @property
    def jitter_s(self) -> float:
        """Standard deviation of the intervals.

        Compare against :attr:`expected_jitter_s`, not against zero: the
        specification requires a random delay, so some jitter is correct
        behaviour.
        """
        intervals = self._require_intervals()
        return statistics.stdev(intervals) if len(intervals) > 1 else 0.0

    @property
    def expected_jitter_s(self) -> float:
        """Jitter a conforming sensor shows from advDelay alone."""
        return ADV_DELAY_MAX_S / (12.0 ** 0.5)

    @property
    def nominal_interval_s(self) -> float:
        """The interval used for missed-event arithmetic.

        The caller's figure when given, otherwise the median measured interval
        less the mean advertising delay, since advDelay is added to every
        interval and would otherwise inflate the nominal rate by 5 ms.
        """
        if self.expected_interval_s is not None:
            return float(self.expected_interval_s)
        measured = statistics.median(self._require_intervals())
        return max(measured - (ADV_DELAY_MAX_S / 2.0), 1.0e-6)

    @property
    def interval_was_measured(self) -> bool:
        """True when the nominal interval was inferred rather than given."""
        return self.expected_interval_s is None

    # ------------------------------------------------------------------
    @property
    def gaps(self) -> List[Tuple[float, int]]:
        """Intervals long enough to contain a missed event.

        :returns: ``(interval_seconds, events_missed)`` for each such gap.
        """
        try:
            nominal = self.nominal_interval_s
        except MeasurementError:
            return []
        # Half a nominal interval of slack absorbs advDelay without admitting a
        # genuinely missing beacon.
        threshold = nominal * 1.5
        found = []
        for interval in self.intervals:
            if interval > threshold:
                missed = int(round(interval / nominal)) - 1
                if missed > 0:
                    found.append((interval, missed))
        return found

    @property
    def missed_events(self) -> int:
        """Advertising events the sensor should have sent and did not.

        Zero is not proof of a healthy sensor unless :attr:`is_complete` is
        true: a dropped USB line is indistinguishable from a missed beacon in
        the host's stream alone.
        """
        return sum(missed for _, missed in self.gaps)

    @property
    def expected_events(self) -> int:
        """Advertising events the capture window should have contained.

        Falls back to what was received when there is no interval to reason
        with: a capture too short for statistics must still produce a report.
        """
        if self.duration_s <= 0.0:
            return self.count
        try:
            nominal = self.nominal_interval_s
        except MeasurementError:
            return self.count
        return int(self.duration_s / nominal) + 1

    @property
    def reception_ratio(self) -> float:
        """Received events divided by expected events, 0.0 to 1.0 and beyond."""
        expected = self.expected_events
        return (self.count / expected) if expected else 0.0

    @property
    def duty_cycle(self) -> float:
        """Fraction of the capture in which the sensor kept to its rate.

        One minus the time lost to gaps, over the observed span. A sensor that
        advertises steadily scores 1.0; one that goes quiet for a third of the
        window scores about 0.67.
        """
        events = self.advertising_events
        if len(events) < 2:
            return 0.0
        span = events[-1].timestamp_s - events[0].timestamp_s
        if span <= 0.0:
            return 0.0
        nominal = self.nominal_interval_s
        lost = sum(interval - nominal for interval, _ in self.gaps)
        return max(0.0, min(1.0, (span - lost) / span))

    @property
    def rate_hz(self) -> float:
        """Advertising events per second, measured."""
        mean = self.mean_interval_s
        return (1.0 / mean) if mean > 0.0 else 0.0

    # ------------------------------------------------------------------
    @property
    def is_complete(self) -> bool:
        """True when the host received every report the dongle sent.

        False means the profile is computed from a lossy stream and its missed
        events cannot be attributed to the sensor.
        """
        if self.radio_events is None:
            return self.dongle_dropped == 0
        return (self.radio_events == self.reports) and (self.dongle_dropped == 0)

    @property
    def lost_reports(self) -> int:
        """Reports the dongle sent that the host did not receive."""
        if self.radio_events is None:
            return 0
        return max(0, self.radio_events - self.reports)

    def within_specification(
        self,
        nominal_s: Optional[float] = None,
        tolerance_s: float = 0.0,
    ) -> bool:
        """Whether every interval is within the specification.

        The allowance is *tolerance_s* plus the specification's own advertising
        delay, so a conforming sensor is not failed for behaviour the Core
        specification requires of it.

        :param nominal_s: Nominal interval; defaults to
            :attr:`nominal_interval_s`.
        :param tolerance_s: Additional allowance, for clock accuracy.
        """
        nominal = float(nominal_s) if nominal_s is not None else self.nominal_interval_s
        allowance = tolerance_s + ADV_DELAY_MAX_S
        intervals = self._require_intervals()
        return all(
            (nominal - tolerance_s) <= interval <= (nominal + allowance)
            for interval in intervals
        )

    def as_dict(self) -> Dict[str, object]:
        """Flat mapping for a report, a JSON dump or a limit check."""
        summary: Dict[str, object] = {
            "address": self.address,
            "duration_s": self.duration_s,
            "reports": self.reports,
            "count": self.count,
            "expected_events": self.expected_events,
            "missed_events": self.missed_events,
            "reception_ratio": self.reception_ratio,
            "duty_cycle": self.duty_cycle,
            "is_complete": self.is_complete,
            "lost_reports": self.lost_reports,
            "dongle_dropped": self.dongle_dropped,
            "nominal_interval_s": None,
            "interval_was_measured": self.interval_was_measured,
        }
        try:
            summary.update(
                {
                    "nominal_interval_s": self.nominal_interval_s,
                    "mean_interval_s": self.mean_interval_s,
                    "mean_interval_ms": self.mean_interval_s * 1000.0,
                    "min_interval_s": self.minimum_interval_s,
                    "max_interval_s": self.maximum_interval_s,
                    "spread_s": self.spread_s,
                    "spread_ms": self.spread_s * 1000.0,
                    "jitter_s": self.jitter_s,
                    "jitter_ms": self.jitter_s * 1000.0,
                    "expected_jitter_ms": self.expected_jitter_s * 1000.0,
                    "rate_hz": self.rate_hz,
                    "gaps": len(self.gaps),
                }
            )
        except MeasurementError:
            # Too few events for statistics. The counts above still describe
            # what happened, which is what a failing test needs to report.
            pass
        return summary

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        try:
            return "<AdvertisingProfile %s %d events, %.1f ms mean%s>" % (
                self.address or "?",
                self.count,
                self.mean_interval_s * 1000.0,
                "" if self.is_complete else ", INCOMPLETE",
            )
        except MeasurementError:
            return "<AdvertisingProfile %s, %d report(s)>" % (self.address or "?", self.reports)
