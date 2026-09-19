"""Measuring the time between two points in target code.

Four methods, because they answer subtly different questions and differ in
accuracy by orders of magnitude. Choosing wrongly produces a number that looks
authoritative and is not, so each result records *how* it was obtained and what
that implies.

=================== ============ ================== =================================
Method              Resolution   Halts the target?  Needs
=================== ============ ================== =================================
``CYCLE_COUNTER``   1 core cycle yes                Cortex-M DWT; core clock known
``HOST_CLOCK``      ~1 ms        yes                nothing
``SWO_ITM``         1 core cycle no                 SWO wired; ITM instrumentation
``TARGET_TIMER``    target timer no                 firmware writes its own timer
=================== ============ ================== =================================

The two halting methods measure *stop-to-stop* time, which is not the same as
the time the code takes when running freely: reaching a breakpoint stops the
core, and the interval excludes whatever the debugger did in between but
includes nothing of the pipeline state. For an interval that must reflect real
execution, ``SWO_ITM`` or ``TARGET_TIMER`` are the honest choices, and the
docstrings say so rather than leaving it to be discovered.

Traces to: JLINK-FR-060 .. JLINK-FR-065, JLINK-DD-TIMING.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from ...core.errors import MeasurementError
from .constants import TimingMethod

__all__ = ["TimingSample", "TimingResult"]


@dataclass(frozen=True)
class TimingSample:
    """One measured interval.

    :param seconds: Interval in seconds.
    :param cycles: Interval in core cycles, when the method counts cycles.
    :param start_raw: Raw counter or clock value at the start point.
    :param end_raw: Raw counter or clock value at the end point.
    """

    seconds: float
    cycles: Optional[int] = None
    start_raw: Optional[float] = None
    end_raw: Optional[float] = None


@dataclass
class TimingResult:
    """Statistics over repeated measurements of one interval.

    :param method: How the interval was measured.
    :param samples: The individual measurements.
    :param start: Start location, as given.
    :param end: End location, as given.
    :param core_clock_hz: Clock used to convert cycles to seconds, when relevant.
    :param halts_target: Whether the method stopped the core to measure.
    """

    method: TimingMethod
    samples: List[TimingSample] = field(default_factory=list)
    start: str = ""
    end: str = ""
    core_clock_hz: Optional[float] = None
    halts_target: bool = True

    # ------------------------------------------------------------------
    def _require(self) -> None:
        if not self.samples:
            raise MeasurementError(
                "no timing samples were collected between %r and %r; check that "
                "both locations were reached" % (self.start, self.end)
            )

    @property
    def count(self) -> int:
        """Number of samples."""
        return len(self.samples)

    @property
    def seconds(self) -> float:
        """Mean interval in seconds. The headline number."""
        self._require()
        return statistics.fmean(sample.seconds for sample in self.samples)

    @property
    def microseconds(self) -> float:
        """Mean interval in microseconds."""
        return self.seconds * 1e6

    @property
    def milliseconds(self) -> float:
        """Mean interval in milliseconds."""
        return self.seconds * 1e3

    @property
    def cycles(self) -> Optional[float]:
        """Mean interval in core cycles, or ``None`` if the method has none."""
        self._require()
        values = [s.cycles for s in self.samples if s.cycles is not None]
        return statistics.fmean(values) if values else None

    @property
    def minimum(self) -> float:
        """Shortest interval measured, in seconds."""
        self._require()
        return min(sample.seconds for sample in self.samples)

    @property
    def maximum(self) -> float:
        """Longest interval measured, in seconds."""
        self._require()
        return max(sample.seconds for sample in self.samples)

    @property
    def spread(self) -> float:
        """Difference between the longest and shortest interval, in seconds."""
        return self.maximum - self.minimum

    @property
    def standard_deviation(self) -> float:
        """Sample standard deviation in seconds; ``0.0`` for a single sample."""
        self._require()
        values = [sample.seconds for sample in self.samples]
        return statistics.stdev(values) if len(values) > 1 else 0.0

    @property
    def resolution_seconds(self) -> Optional[float]:
        """Quantisation of this method, so a reader can judge the figure.

        A 12 µs interval reported by :attr:`TimingMethod.HOST_CLOCK`, whose
        resolution is around a millisecond, is noise presented as a measurement.

        ``None`` only when the rate of the counter is not known, which for a
        counting method means the caller did not supply one. That is treated as
        untrustworthy rather than as unlimited precision.
        """
        if self.method is TimingMethod.HOST_CLOCK:
            return 1.0e-3
        # The counting methods resolve one tick of their counter. For the target
        # timer that counter is the firmware's timer, whose rate was passed as
        # ``timer_hz`` and is held here, not necessarily the core clock.
        if self.method in (
            TimingMethod.CYCLE_COUNTER, TimingMethod.SWO_ITM, TimingMethod.TARGET_TIMER,
        ):
            return (1.0 / self.core_clock_hz) if self.core_clock_hz else None
        return None

    @property
    def is_trustworthy(self) -> bool:
        """``False`` when the interval is close to the method's resolution.

        A convenience for a test that should refuse to assert on a figure its
        method cannot actually resolve. Ten times the quantisation is the
        threshold; below that, change method rather than tightening the limit.

        An unknown resolution is not a licence to trust the figure: it means
        nothing is known about the quantisation, so the answer is ``False``.
        """
        resolution = self.resolution_seconds
        if resolution is None:
            return False
        try:
            return self.seconds >= resolution * 10.0
        except MeasurementError:
            return False

    def as_dict(self) -> dict:
        """Flat mapping for reports and JSON output."""
        summary = {
            "method": self.method.value,
            "start": self.start,
            "end": self.end,
            "count": self.count,
            "halts_target": self.halts_target,
            "seconds": self.seconds,
            "microseconds": self.microseconds,
            "min_seconds": self.minimum,
            "max_seconds": self.maximum,
            "spread_seconds": self.spread,
            "stdev_seconds": self.standard_deviation,
            "resolution_seconds": self.resolution_seconds,
            "trustworthy": self.is_trustworthy,
        }
        cycles = self.cycles
        if cycles is not None:
            summary["cycles"] = cycles
            summary["core_clock_hz"] = self.core_clock_hz
        return summary

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        try:
            return "<TimingResult %s %.3f us over %d sample(s)>" % (
                self.method.value, self.microseconds, self.count,
            )
        except MeasurementError:
            return "<TimingResult %s, no samples>" % self.method.value
