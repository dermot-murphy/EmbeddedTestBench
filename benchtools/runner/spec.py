"""Declarative test specifications.

A specification says *what* to do and *what counts as a pass*. It is data, not
code, so the limits and the intent stay reviewable by a test engineer and trace
directly to a requirement - which is the whole reason for not writing bench
tests as scripts.

Example (YAML)::

    name: Clock distribution timing
    description: Verify the clock fan-out skew across four loads.
    requirements: [SYS-REQ-042]

    setup:
      - do: scope.configure_channel
        with: {channel: 1, volts_per_div: 1.0, position_div: -4.0}
      - do: scope.set_time_per_div
        with: {seconds_per_div: 200.0e-9}
      - do: scope.configure_edge_trigger
        with: {source: 1, level: 1.65}

    tests:
      - name: Rising-edge spread within 20 ns
        requirement: SYS-REQ-042
        steps:
          - do: scope.measure_channel_spread
            with: {channels: [1, 2, 3, 4], direction: RISE}
            expect:
              - name: rising_spread
                measure: "1.spread"
                unit: s
                scale: 1.0e9
                display_unit: ns
                max: 20.0

JSON is accepted with the same structure, so a specification can be written and
loaded with no third-party package. YAML needs ``pyyaml``, which is an optional
extra.

Traces to: RUN-FR-010 .. RUN-FR-014, RUN-DD-SPEC.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..core.errors import OptionalDependencyError, SpecError
from .limits import Limit

__all__ = ["Expectation", "Step", "TestCase", "TestSpec", "load_spec", "load_mapping"]

#: Keys accepted on an expectation but consumed by the limit, not the expectation.
_LIMIT_KEYS = ("min", "max", "minimum", "maximum", "equals", "nominal",
               "tolerance", "tolerance_percent")


def _require_mapping(value, what: str) -> dict:
    if not isinstance(value, dict):
        raise SpecError("%s must be a mapping, got %s" % (what, type(value).__name__))
    return value


def _require_sequence(value, what: str) -> list:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise SpecError("%s must be a list, got %s" % (what, type(value).__name__))
    return list(value)


@dataclass(frozen=True)
class Expectation:
    """One measured value and the limit it must satisfy.

    :param name: Name reported for this measurement.
    :param measure: Path into the step's result; empty means the whole result.
    :param limit: The pass/fail bound.
    :param unit: Unit of the raw value, for the record.
    :param scale: Multiplier applied before the limit is checked, so a spec can
        state a limit in convenient units (nanoseconds, millivolts).
    :param display_unit: Unit the scaled value is reported in.
    """

    name: str
    measure: str
    limit: Limit
    unit: str = ""
    scale: float = 1.0
    display_unit: str = ""

    @classmethod
    def from_mapping(cls, data, index: int) -> "Expectation":
        data = _require_mapping(data, "expectation %d" % index)
        measure = str(data.get("measure", ""))
        name = str(data.get("name") or measure or "value")
        limit_source = {key: data[key] for key in _LIMIT_KEYS if key in data}
        if not limit_source:
            raise SpecError(
                "expectation %r declares no limit; add min, max or equals" % name
            )
        try:
            scale = float(data.get("scale", 1.0))
        except (TypeError, ValueError) as exc:
            raise SpecError("expectation %r has a non-numeric scale" % name) from exc
        if scale == 0.0:
            raise SpecError("expectation %r has a scale of zero" % name)
        unit = str(data.get("unit", ""))
        return cls(
            name=name,
            measure=measure,
            limit=Limit.from_mapping(limit_source),
            unit=unit,
            scale=scale,
            display_unit=str(data.get("display_unit", "")) or unit,
        )


@dataclass(frozen=True)
class Step:
    """One action performed on the bench.

    :param action: ``"<instrument>.<method>"``, or a built-in action name.
    :param arguments: Keyword arguments for the call.
    :param expectations: Values to extract from the result and check.
    :param save: Name under which to keep the result for a later step.
    :param description: Optional note shown in the report.
    """

    action: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    expectations: Sequence[Expectation] = ()
    save: Optional[str] = None
    description: str = ""

    @classmethod
    def from_mapping(cls, data, index: int) -> "Step":
        data = _require_mapping(data, "step %d" % index)
        action = data.get("do") or data.get("action")
        if not action:
            raise SpecError("step %d has no 'do' action" % index)
        arguments = data.get("with", data.get("args", {})) or {}
        arguments = _require_mapping(arguments, "step %d arguments" % index)
        raw = data.get("expect", []) or []
        if isinstance(raw, dict):          # allow a single expectation inline
            raw = [raw]
        expectations = tuple(
            Expectation.from_mapping(item, position)
            for position, item in enumerate(_require_sequence(raw, "step %d expectations" % index))
        )
        return cls(
            action=str(action),
            arguments=dict(arguments),
            expectations=expectations,
            save=data.get("save"),
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True)
class TestCase:
    """One named test: a sequence of steps and their expectations.

    :param name: Test name, used as the report identifier.
    :param steps: Steps executed in order. A step that raises fails the test.
    :param requirement: Requirement identifier this test verifies.
    """

    # Not a pytest test class, despite the name.
    __test__ = False

    name: str
    steps: Sequence[Step]
    requirement: str = ""
    description: str = ""
    skip: bool = False
    skip_reason: str = ""

    @classmethod
    def from_mapping(cls, data, index: int) -> "TestCase":
        data = _require_mapping(data, "test %d" % index)
        name = data.get("name")
        if not name:
            raise SpecError("test %d has no name" % index)
        steps = _require_sequence(data.get("steps", []), "test %r steps" % name)
        if not steps:
            raise SpecError("test %r has no steps" % name)
        requirement = data.get("requirement") or data.get("requirements") or ""
        if isinstance(requirement, (list, tuple)):
            requirement = ", ".join(str(item) for item in requirement)
        return cls(
            name=str(name),
            steps=tuple(Step.from_mapping(item, position) for position, item in enumerate(steps)),
            requirement=str(requirement),
            description=str(data.get("description", "")),
            skip=bool(data.get("skip", False)),
            skip_reason=str(data.get("skip_reason", "")),
        )


@dataclass(frozen=True)
class TestSpec:
    """A suite of tests, with shared setup and teardown.

    :param setup: Steps run once before the tests. A failure here aborts the
        suite, because every test would otherwise run against an unknown setup.
    :param teardown: Steps run once after the tests, whatever the outcome.
    """

    # Not a pytest test class, despite the name.
    __test__ = False

    name: str
    tests: Sequence[TestCase]
    description: str = ""
    requirements: Sequence[str] = ()
    setup: Sequence[Step] = ()
    teardown: Sequence[Step] = ()
    source: str = ""

    @classmethod
    def from_mapping(cls, data, source: str = "") -> "TestSpec":
        data = _require_mapping(data, "specification")
        name = data.get("name")
        if not name:
            raise SpecError("specification has no name")
        tests = _require_sequence(data.get("tests", []), "tests")
        if not tests:
            raise SpecError("specification %r contains no tests" % name)
        requirements = data.get("requirements", []) or []
        if isinstance(requirements, str):
            requirements = [requirements]
        return cls(
            name=str(name),
            description=str(data.get("description", "")),
            requirements=tuple(str(item) for item in requirements),
            setup=tuple(
                Step.from_mapping(item, i)
                for i, item in enumerate(_require_sequence(data.get("setup", []) or [], "setup"))
            ),
            teardown=tuple(
                Step.from_mapping(item, i)
                for i, item in enumerate(_require_sequence(data.get("teardown", []) or [], "teardown"))
            ),
            tests=tuple(TestCase.from_mapping(item, i) for i, item in enumerate(tests)),
            source=source,
        )

    @property
    def instruments_used(self) -> List[str]:
        """Instrument aliases referenced anywhere in the specification.

        Lets the runner verify the bench provides everything the suite needs
        before it starts, rather than failing halfway through.
        """
        aliases = set()
        for step in list(self.setup) + list(self.teardown) + [
            step for case in self.tests for step in case.steps
        ]:
            alias, separator, _ = step.action.partition(".")
            if separator:
                aliases.add(alias)
        return sorted(aliases)


def load_mapping(path: str) -> dict:
    """Load a JSON or YAML document into a dictionary.

    JSON needs nothing beyond the standard library. YAML needs ``pyyaml``; the
    error names the extra if it is missing.
    """
    if not os.path.exists(path):
        raise SpecError("no such specification file: %s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    suffix = os.path.splitext(path)[1].lower()
    if suffix in (".json",):
        try:
            return json.loads(text)
        except ValueError as exc:
            raise SpecError("%s is not valid JSON: %s" % (path, exc)) from exc

    try:
        import yaml
    except ImportError as exc:
        raise OptionalDependencyError(
            "reading %s needs pyyaml (pip install benchtools[spec]). "
            "Specifications can also be written as JSON, which needs nothing extra."
            % path
        ) from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError("%s is not valid YAML: %s" % (path, exc)) from exc


def load_spec(path: str) -> TestSpec:
    """Load and validate a test specification from *path*."""
    return TestSpec.from_mapping(load_mapping(path), source=path)
