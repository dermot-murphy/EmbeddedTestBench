"""Result records produced by a run.

These are plain data: the runner fills them in, the report writers read them.
Keeping them separate from both means a new output format needs no change to
the execution engine.

Traces to: RUN-FR-030, RUN-FR-037, RUN-DD-RESULTS.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

__all__ = ["Status", "MeasurementRecord", "StepRecord", "CaseRecord", "RunRecord"]


class Status(str, enum.Enum):
    """Outcome of a test, step or run."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"

    @property
    def is_problem(self) -> bool:
        """``True`` for outcomes that should fail a build."""
        return self in (Status.FAIL, Status.ERROR)

    @property
    def severity(self) -> int:
        """Ordering used to pick the worst of several outcomes."""
        return {Status.PASS: 0, Status.SKIP: 1, Status.FAIL: 2, Status.ERROR: 3}[self]

    @classmethod
    def worst(cls, statuses) -> "Status":
        """Return the most severe of *statuses*, or ``PASS`` if empty."""
        return max(statuses, key=lambda status: status.severity, default=cls.PASS)


@dataclass
class MeasurementRecord:
    """One measured value and whether it met its limit."""

    name: str
    #: The measured value: a number, or text where the limit is an exact match
    #: on text (a version, a device name). A report shows whichever it is.
    value: Union[float, str, None]
    unit: str
    limit: str
    status: Status
    reason: str = ""
    #: The unscaled number behind :attr:`value`; None for a text measurement.
    raw_value: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        record = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "limit": self.limit,
            "status": self.status.value,
            "reason": self.reason,
        }
        # The number behind a rendered value, so the record stays lossless when
        # a specification asked for the value to be reported as text
        # (RUN-FR-041): 0A1B2C is what a person compares with the board, and
        # 662316 is what anything downstream can compute with.
        if self.raw_value is not None and not isinstance(self.value, float):
            record["raw_value"] = self.raw_value
        return record


@dataclass
class StepRecord:
    """One executed step."""

    action: str
    status: Status
    duration_s: float = 0.0
    measurements: List[MeasurementRecord] = field(default_factory=list)
    error: str = ""
    description: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status.value,
            "duration_s": round(self.duration_s, 6),
            "error": self.error,
            "measurements": [m.as_dict() for m in self.measurements],
        }


@dataclass
class CaseRecord:
    """One executed test case."""

    name: str
    status: Status
    requirement: str = ""
    duration_s: float = 0.0
    steps: List[StepRecord] = field(default_factory=list)
    error: str = ""
    skip_reason: str = ""

    @property
    def measurements(self) -> List[MeasurementRecord]:
        """Every measurement taken across this case's steps."""
        return [m for step in self.steps for m in step.measurements]

    @property
    def failures(self) -> List[MeasurementRecord]:
        """Measurements that did not meet their limits."""
        return [m for m in self.measurements if m.status is Status.FAIL]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "requirement": self.requirement,
            "duration_s": round(self.duration_s, 6),
            "error": self.error,
            "skip_reason": self.skip_reason,
            "steps": [s.as_dict() for s in self.steps],
        }


@dataclass
class RunRecord:
    """The result of running one specification against one bench."""

    suite: str
    bench: str
    started: str = ""
    finished: str = ""
    duration_s: float = 0.0
    cases: List[CaseRecord] = field(default_factory=list)
    requirements: Sequence[str] = ()
    setup_error: str = ""
    spec_source: str = ""
    simulated: bool = False
    #: The specification's parameters, as this run used them.
    parameters: Dict[str, Any] = field(default_factory=dict)
    #: Alias to what the instrument said it was: driver, model, firmware,
    #: resource. Recorded because a measurement without the instrument that
    #: made it is not evidence - and firmware version in particular decides
    #: whether a result means what it appears to mean.
    instruments: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def count(self, status: Status) -> int:
        """Number of cases with the given outcome."""
        return sum(1 for case in self.cases if case.status is status)

    @property
    def passed(self) -> int:
        return self.count(Status.PASS)

    @property
    def failed(self) -> int:
        return self.count(Status.FAIL)

    @property
    def errored(self) -> int:
        return self.count(Status.ERROR)

    @property
    def skipped(self) -> int:
        return self.count(Status.SKIP)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def status(self) -> Status:
        """Worst outcome in the run.

        A setup failure is an ERROR for the whole run, because no test can be
        trusted after it.
        """
        if self.setup_error:
            return Status.ERROR
        if self.errored:
            return Status.ERROR
        if self.failed:
            return Status.FAIL
        if self.total and self.passed == 0 and self.skipped == self.total:
            return Status.SKIP
        return Status.PASS

    @property
    def requirements_verified(self) -> Dict[str, str]:
        """Requirement identifier to the worst outcome of its tests.

        This is the trace a reviewer actually wants: which requirements this run
        exercised, and whether they held.
        """
        grouped: Dict[str, List[Status]] = {}
        for case in self.cases:
            for requirement in [r.strip() for r in case.requirement.split(",") if r.strip()]:
                grouped.setdefault(requirement, []).append(case.status)
        return {
            requirement: Status.worst(statuses).value
            for requirement, statuses in sorted(grouped.items())
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            "suite": self.suite,
            "bench": self.bench,
            "spec_source": self.spec_source,
            "parameters": dict(self.parameters),
            "simulated": self.simulated,
            "status": self.status.value,
            "started": self.started,
            "finished": self.finished,
            "duration_s": round(self.duration_s, 6),
            "totals": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "errored": self.errored,
                "skipped": self.skipped,
            },
            "instruments": self.instruments,
            "requirements": list(self.requirements),
            "requirements_verified": self.requirements_verified,
            "setup_error": self.setup_error,
            "cases": [case.as_dict() for case in self.cases],
        }
