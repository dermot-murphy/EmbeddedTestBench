"""How long a sensor took to answer, and how much of that figure to believe.

Two clocks measure every command: the dongle's, which starts when the request
is handed to the SoftDevice and stops when the notification arrives, and the
host's, which starts and stops either side of a USB round trip. The first is
the measurement. The second is kept because the difference between them *is*
the overhead of the host link, and a bench that quotes host figures for a
link-layer latency will report milliseconds of USB scheduling as sensor
behaviour.

There is a floor below which no reply can arrive: a connection event happens
once per connection interval, so a sensor that answers instantly still answers
one interval later. :attr:`ResponseTiming.quantisation_s` reports that interval,
and :attr:`ResponseTiming.is_trustworthy` is false when the measured latency is
not large enough to be distinguished from it.

This is a sibling of ``jlink.timing`` rather than a shared type: the two
measure different things with different floors, and merging them would couple
two drivers for the sake of four common properties. If a third instrument needs
statistics of this shape, the place for them is ``benchtools.analysis``.

Traces to: BLE-FR-050 .. BLE-FR-053, BLE-DD-LATENCY.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ...core.errors import MeasurementError

__all__ = ["LatencySource", "ResponseSample", "ResponseTiming"]


class LatencySource(Enum):
    """Which clock produced a latency figure."""

    #: The dongle's 1 us clock, timestamped either side of the radio exchange.
    DONGLE = "DONGLE"
    #: The host's clock, around the whole USB round trip. Includes the link.
    HOST = "HOST"


@dataclass
class ResponseSample:
    """One command and its reply.

    :param request: What was sent, as text where it is text.
    :param response: What came back.
    :param dongle_us: Round trip measured by the dongle, in microseconds.
    :param host_s: Round trip measured by the host, in seconds.
    :param transmitted_us: Dongle timestamp when the request was handed over.
    :param received_us: Dongle timestamp when the reply arrived.
    :param extra_frames: Notifications after the reply, when they were listened
        for: a sensor that answers once sends none.
    """

    request: str = ""
    response: bytes = b""
    dongle_us: Optional[int] = None
    host_s: float = 0.0
    transmitted_us: Optional[int] = None
    received_us: Optional[int] = None
    extra_frames: Tuple[bytes, ...] = ()

    @property
    def frames(self) -> int:
        """How many notifications the command produced: the reply, and any after it."""
        return 1 + len(self.extra_frames)

    @property
    def text(self) -> str:
        """The reply decoded as text, for a console-style sensor."""
        return self.response.decode("utf-8", errors="replace")

    @property
    def seconds(self) -> float:
        """The dongle's figure in seconds, falling back to the host's."""
        if self.dongle_us is not None:
            return self.dongle_us / 1.0e6
        return self.host_s

    def as_dict(self) -> dict:
        return {
            "request": self.request,
            "response": self.text,
            "response_hex": self.response.hex(),
            "dongle_us": self.dongle_us,
            "host_us": self.host_s * 1.0e6,
            "transmitted_us": self.transmitted_us,
            "received_us": self.received_us,
        }


@dataclass
class ResponseTiming:
    """Round-trip statistics over one or more commands.

    :param samples: The exchanges measured.
    :param source: Which clock the statistics are taken from.
    :param connection_interval_us: The link's connection interval, the floor
        below which a reply cannot arrive.
    """

    samples: List[ResponseSample] = field(default_factory=list)
    source: LatencySource = LatencySource.DONGLE
    connection_interval_us: int = 0
    request: str = ""

    # ------------------------------------------------------------------
    def _values(self) -> List[float]:
        if not self.samples:
            raise MeasurementError(
                "no response was measured for %r. A timing result with no "
                "samples is not zero latency; it is no measurement."
                % (self.request or "the command")
            )
        if self.source is LatencySource.HOST:
            return [sample.host_s for sample in self.samples]
        return [
            sample.dongle_us / 1.0e6
            for sample in self.samples
            if sample.dongle_us is not None
        ] or [sample.host_s for sample in self.samples]

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def seconds(self) -> float:
        """Mean round trip in seconds."""
        return statistics.fmean(self._values())

    @property
    def milliseconds(self) -> float:
        return self.seconds * 1000.0

    @property
    def microseconds(self) -> float:
        return self.seconds * 1.0e6

    @property
    def minimum_s(self) -> float:
        return min(self._values())

    @property
    def maximum_s(self) -> float:
        return max(self._values())

    @property
    def spread_s(self) -> float:
        values = self._values()
        return max(values) - min(values)

    @property
    def standard_deviation_s(self) -> float:
        values = self._values()
        return statistics.stdev(values) if len(values) > 1 else 0.0

    # ------------------------------------------------------------------
    @property
    def resolution_s(self) -> float:
        """What the measuring clock resolves."""
        return 1.0e-6 if self.source is LatencySource.DONGLE else 1.0e-3

    @property
    def quantisation_s(self) -> float:
        """The connection interval: no reply can arrive between two of them."""
        return self.connection_interval_us / 1.0e6

    @property
    def is_trustworthy(self) -> bool:
        """False when the figure cannot be told apart from the link's own floor.

        A latency of one connection interval means "as fast as the link allows",
        not "0.5 ms of sensor processing". Tightening a limit on such a figure
        measures the connection parameters, not the firmware.
        """
        try:
            measured = self.seconds
        except MeasurementError:
            return False
        if measured < (self.resolution_s * 10.0):
            return False
        if self.quantisation_s > 0.0:
            return measured >= (self.quantisation_s * 1.5)
        return True

    @property
    def responses(self) -> List[str]:
        """The replies, as text."""
        return [sample.text for sample in self.samples]

    def as_dict(self) -> Dict[str, object]:
        """Flat mapping for a report, a JSON dump or a limit check."""
        summary: Dict[str, object] = {
            "request": self.request,
            "source": self.source.value,
            "count": self.count,
            "connection_interval_us": self.connection_interval_us,
            "resolution_s": self.resolution_s,
            "trustworthy": self.is_trustworthy,
        }
        try:
            summary.update(
                {
                    "seconds": self.seconds,
                    "milliseconds": self.milliseconds,
                    "microseconds": self.microseconds,
                    "min_s": self.minimum_s,
                    "max_s": self.maximum_s,
                    "spread_s": self.spread_s,
                    "stdev_s": self.standard_deviation_s,
                    "responses": self.responses,
                }
            )
        except MeasurementError:
            pass
        return summary

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        try:
            return "<ResponseTiming %r %.3f ms over %d sample(s)>" % (
                self.request, self.milliseconds, self.count
            )
        except MeasurementError:
            return "<ResponseTiming %r, no samples>" % self.request
