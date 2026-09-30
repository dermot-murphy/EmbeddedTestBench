"""Repeated readings of one quantity, and what a test asks of them.

A test that reads a temperature five times asks two things of the five: how far
apart they are, and where they sit, so they can be compared with another source
that read the same thing another way. :class:`SampleSet` keeps the readings and
answers both, so a specification can put a limit on ``spread`` and compare one
source's ``mean`` with another's (#95).

A set that got fewer readings than it asked for is still returned, with
``count`` saying so: a sensor that stopped answering is a result to report, not
a reason to lose the readings it did give. Its statistics are ``None`` only
when there are no readings at all.

Traces to: ANA-FR-022, ANA-DD-SAMPLES.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.errors import MeasurementError

#: A signed decimal number: what a reply or a log line most often carries.
NUMBER = r"(-?\d+(?:\.\d+)?)"


def extract_number(text: str, pattern: str = NUMBER) -> Optional[float]:
    """The number *pattern*'s first group matches in *text*, or ``None``.

    :raises MeasurementError: if *pattern* has no group to take the number from.
    """
    compiled = re.compile(pattern)
    if compiled.groups < 1:
        raise MeasurementError(
            "the pattern %r has no group; put the number in parentheses, "
            "e.g. r'= (-?\\d+)mC'" % pattern)
    match = compiled.search(text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        raise MeasurementError(
            "the pattern %r matched %r in %r, which is not a number"
            % (pattern, match.group(1), text)) from None


@dataclass
class SampleSet:
    """Readings of one quantity, in the order they were taken.

    :param name: What was read, for the report.
    :param unit: The unit of the values, after any scaling.
    :param requested: How many readings were asked for.
    """

    name: str = ""
    unit: str = ""
    requested: int = 0
    values: List[float] = field(default_factory=list)
    #: What each reading was taken from - a reply, a log line - kept beside it.
    sources: List[str] = field(default_factory=list)
    #: Seconds from the first reading to each reading.
    times: List[float] = field(default_factory=list)

    def add(self, value: float, source: str = "", at: float = 0.0) -> None:
        """Record one reading."""
        self.values.append(float(value))
        self.sources.append(source)
        self.times.append(float(at))

    @property
    def count(self) -> int:
        """How many readings were taken."""
        return len(self.values)

    @property
    def complete(self) -> bool:
        """``True`` when every requested reading was taken."""
        return self.count >= self.requested

    @property
    def minimum(self) -> Optional[float]:
        """The lowest reading."""
        return min(self.values) if self.values else None

    @property
    def maximum(self) -> Optional[float]:
        """The highest reading."""
        return max(self.values) if self.values else None

    @property
    def mean(self) -> Optional[float]:
        """The average reading."""
        return sum(self.values) / len(self.values) if self.values else None

    @property
    def spread(self) -> Optional[float]:
        """Highest reading less lowest: how far the readings moved."""
        return max(self.values) - min(self.values) if self.values else None

    def as_dict(self) -> Dict[str, Any]:
        """The readings and their statistics, for a record."""
        return {
            "name": self.name,
            "unit": self.unit,
            "requested": self.requested,
            "count": self.count,
            "complete": self.complete,
            "values": list(self.values),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
            "spread": self.spread,
            "times": list(self.times),
            "sources": list(self.sources),
        }
