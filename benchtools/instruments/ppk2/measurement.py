"""What a PPK2 measurement recorded, and what a test reads from it.

A :class:`Measurement` keeps every sample: the current in amps and the eight
logic inputs, one sample every 10 microseconds. A test reads the average, the
peak, the charge, and the pulses - the stretches where the current is above
a threshold, or where a logic input is high - each with its width and the
charge it drew.

Nothing here touches the kit, so it is the same for a simulated measurement
and a real one.

Traces to: PPK-FR-006, PPK-FR-008, PPK-DD-MEASUREMENT.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .constants import LINES, SAMPLE_PERIOD

__all__ = ["Measurement", "Pulse", "PulseResult", "find_pulses"]


@dataclass(frozen=True)
class Pulse:
    """One pulse: from a rising edge to the falling edge after it.

    :ivar start: Seconds from the start of the measurement to the rising edge.
    :ivar width: Seconds from the rising edge to the falling edge.
    :ivar charge: Coulombs drawn in that time.
    :ivar average: The average current in that time, in amps.
    :ivar peak: The highest current in that time, in amps.
    """

    start: float
    width: float
    charge: float
    average: float
    peak: float

    def as_dict(self) -> Dict[str, float]:
        """The pulse as a JSON-ready dictionary."""
        return {"start": self.start, "width": self.width, "charge": self.charge,
                "average": self.average, "peak": self.peak}


@dataclass(frozen=True)
class PulseResult:
    """The pulses a measurement holds, and figures across them.

    Only whole pulses count: one already high when the measurement started,
    or still high when it ended, is counted in :attr:`incomplete` instead,
    because its width and charge are not known.

    :ivar source: What marked the pulses: ``current >= 0.001 A`` or ``D0``.
    :ivar pulses: Each whole pulse, in order.
    :ivar incomplete: Pulses cut by the start or the end of the measurement.
    """

    source: str
    pulses: Tuple[Pulse, ...] = ()
    incomplete: int = 0

    @property
    def count(self) -> int:
        """Whole pulses."""
        return len(self.pulses)

    @property
    def widths(self) -> Tuple[float, ...]:
        """Each pulse's width, in seconds."""
        return tuple(pulse.width for pulse in self.pulses)

    @property
    def charges(self) -> Tuple[float, ...]:
        """Each pulse's charge, in coulombs."""
        return tuple(pulse.charge for pulse in self.pulses)

    @property
    def min_width(self) -> Optional[float]:
        """The narrowest pulse, in seconds; ``None`` with none."""
        return min(self.widths) if self.pulses else None

    @property
    def max_width(self) -> Optional[float]:
        """The widest pulse, in seconds; ``None`` with none."""
        return max(self.widths) if self.pulses else None

    @property
    def mean_width(self) -> Optional[float]:
        """The mean width, in seconds; ``None`` with none."""
        return sum(self.widths) / len(self.pulses) if self.pulses else None

    @property
    def total_charge(self) -> float:
        """The charge of every whole pulse together, in coulombs."""
        return sum(self.charges)

    @property
    def mean_charge(self) -> Optional[float]:
        """The mean charge of a pulse, in coulombs; ``None`` with none."""
        return self.total_charge / len(self.pulses) if self.pulses else None

    @property
    def mean_interval(self) -> Optional[float]:
        """Mean seconds from one rising edge to the next; ``None`` below two pulses."""
        if len(self.pulses) < 2:
            return None
        return (self.pulses[-1].start - self.pulses[0].start) / (len(self.pulses) - 1)

    def as_dict(self) -> Dict[str, Any]:
        """The figures, and each pulse, as a JSON-ready dictionary."""
        return {"source": self.source, "count": self.count, "incomplete": self.incomplete,
                "min_width": self.min_width, "max_width": self.max_width,
                "mean_width": self.mean_width, "total_charge": self.total_charge,
                "mean_charge": self.mean_charge, "mean_interval": self.mean_interval,
                "pulses": [pulse.as_dict() for pulse in self.pulses]}


def find_pulses(amps: Sequence[float], high: Sequence[bool], period: float,
                source: str) -> PulseResult:
    """The pulses in *amps* where *high* is true, sample by sample."""
    pulses: List[Pulse] = []
    incomplete = 0
    start: Optional[int] = None
    for index, state in enumerate(high):
        if state and start is None:
            start = index
        elif not state and start is not None:
            if start == 0 and high[0]:
                incomplete += 1
            else:
                pulses.append(_pulse(amps, start, index, period))
            start = None
    if start is not None:
        incomplete += 1
    return PulseResult(source=source, pulses=tuple(pulses), incomplete=incomplete)


def _pulse(amps: Sequence[float], begin: int, end: int, period: float) -> Pulse:
    part = amps[begin:end]
    total = sum(part)
    return Pulse(start=begin * period, width=(end - begin) * period, charge=total * period,
                 average=total / len(part), peak=max(part))


@dataclass
class Measurement:  # pylint: disable=too-many-instance-attributes
    """Every sample of one measurement.

    A specification reads its fields with ``measure``: ``average``, ``peak``,
    ``minimum``, ``charge``, ``duration``, ``samples``, ``lost``, and
    ``pulses.count``, ``pulses.mean_width`` and the rest when the
    measurement was asked for pulses.

    :ivar amps: The current, sample by sample, in amps.
    :ivar logic: The logic inputs, sample by sample: bit 0 is D0.
    :ivar mode: ``source`` or ``ammeter``.
    :ivar volts: The regulator voltage while it was taken.
    :ivar lost: Samples the kit's counter says never arrived: at least this
        many, because the counter is six bits and a gap of 64 reads as none.
    :ivar threshold: Amps a pulse rises above, or ``None``.
    :ivar release: Amps a pulse falls below; ``threshold`` when not given.
    :ivar line: The logic input that marks a pulse, or ``None``.
    :ivar period: Seconds between samples.
    """

    amps: array = field(default_factory=lambda: array("d"))
    logic: array = field(default_factory=lambda: array("B"))
    mode: str = ""
    volts: float = 0.0
    lost: int = 0
    threshold: Optional[float] = None
    release: Optional[float] = None
    line: Optional[int] = None
    period: float = SAMPLE_PERIOD

    def __post_init__(self) -> None:
        if self.threshold is not None and self.line is not None:
            raise ValueError("give a threshold or a line for pulses, not both")
        if self.line is not None and not 0 <= int(self.line) < LINES:
            raise ValueError("line must be 0 to %d, got %r" % (LINES - 1, self.line))
        if self.release is not None and self.threshold is None:
            raise ValueError("release needs a threshold")
        if (self.threshold is not None and self.release is not None
                and self.release > self.threshold):
            raise ValueError("release (%g A) must not be above threshold (%g A)"
                             % (self.release, self.threshold))
        self._pulses: Optional[PulseResult] = None

    @property
    def samples(self) -> int:
        """How many samples were kept."""
        return len(self.amps)

    @property
    def duration(self) -> float:
        """Seconds the samples span."""
        return self.samples * self.period

    @property
    def average(self) -> Optional[float]:
        """The mean current, in amps; ``None`` with no samples."""
        return sum(self.amps) / self.samples if self.samples else None

    @property
    def peak(self) -> Optional[float]:
        """The highest current, in amps; ``None`` with no samples."""
        return max(self.amps) if self.samples else None

    @property
    def minimum(self) -> Optional[float]:
        """The lowest current, in amps; ``None`` with no samples."""
        return min(self.amps) if self.samples else None

    @property
    def charge(self) -> float:
        """The charge drawn over the whole measurement, in coulombs."""
        return sum(self.amps) * self.period

    def bits(self, line: int) -> List[int]:
        """Logic input *line* (0 to 7), sample by sample, as 0 and 1."""
        if not 0 <= int(line) < LINES:
            raise ValueError("line must be 0 to %d, got %r" % (LINES - 1, line))
        return [(value >> int(line)) & 1 for value in self.logic]

    @property
    def pulses(self) -> Optional[PulseResult]:
        """The pulses, marked by the threshold or the line; ``None`` with neither."""
        if self._pulses is None:
            if self.line is not None:
                high = [bool(bit) for bit in self.bits(self.line)]
                self._pulses = find_pulses(self.amps, high, self.period, "D%d" % self.line)
            elif self.threshold is not None:
                self._pulses = self.pulses_above(self.threshold, self.release)
        return self._pulses

    def pulses_above(self, threshold: float, release: Optional[float] = None) -> PulseResult:
        """The pulses where the current rises to *threshold* amps or more.

        A pulse ends when the current falls below *release*, which defaults to
        *threshold*. A lower *release* keeps noise on a pulse's top from
        splitting it in two.
        """
        rise = float(threshold)
        fall = rise if release is None else float(release)
        high: List[bool] = []
        state = False
        for value in self.amps:
            state = value >= rise if not state else value >= fall
            high.append(state)
        source = "current >= %g A" % rise
        if fall != rise:
            source += ", until < %g A" % fall
        return find_pulses(self.amps, high, self.period, source)

    def summary(self) -> str:
        """One line: duration, average, peak, charge, and the pulses if any."""
        if not self.samples:
            return "no samples"
        text = "%.3f s, average %s, peak %s, charge %s" % (
            self.duration, _amps(self.average), _amps(self.peak), _coulombs(self.charge))
        if self.lost:
            text += ", %d samples lost" % self.lost
        pulses = self.pulses
        if pulses is not None:
            text += ", %d pulses (%s)" % (pulses.count, pulses.source)
        return text

    def as_dict(self, with_samples: bool = False) -> Dict[str, Any]:
        """The figures as a JSON-ready dictionary; the samples only if asked."""
        result: Dict[str, Any] = {
            "mode": self.mode, "volts": self.volts, "samples": self.samples,
            "duration": self.duration, "average": self.average, "peak": self.peak,
            "minimum": self.minimum, "charge": self.charge, "lost": self.lost,
            "pulses": self.pulses.as_dict() if self.pulses is not None else None,
        }
        if with_samples:
            result["amps"] = list(self.amps)
            result["logic"] = list(self.logic)
        return result


def _amps(value: Optional[float]) -> str:
    if value is None:
        return "-"
    for scale, unit in ((1.0, "A"), (1e-3, "mA"), (1e-6, "uA")):
        if abs(value) >= scale:
            return "%.3f %s" % (value / scale, unit)
    return "%.1f nA" % (value / 1e-9)


def _coulombs(value: float) -> str:
    for scale, unit in ((1.0, "C"), (1e-3, "mC"), (1e-6, "uC")):
        if abs(value) >= scale:
            return "%.3f %s" % (value / scale, unit)
    return "%.1f nC" % (value / 1e-9)
