"""Declarative test specifications.

A specification says *what* to do and *what counts as a pass*. It is data, not
code, so the limits and the intent stay reviewable by a test engineer and trace
directly to a requirement - which is the whole reason for not writing bench
tests as scripts.

Example (YAML)::

    name: Clock distribution timing
    description: Verify the clock fan-out skew across four loads.
    requirements: [SYS-REQ-042]

    instruments:                 # optional: what kind each alias must be
      scope: tek3014b

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

A ``parameters`` block names the values a reader may want to change -
a tolerance, a count - once, at the top, and ``{param: <name>}`` stands for
one anywhere below: an argument, a bound, a tolerance::

    parameters:
      tolerance_c: 5.0
    tests:
      - name: Within tolerance
        steps:
          - do: probe.rtt_samples
            expect:
              - {name: mean, measure: mean, equals: {from: ble.mean},
                 tolerance: {param: tolerance_c}}

Traces to: RUN-FR-008, RUN-FR-010 .. RUN-FR-016, RUN-FR-058, RUN-FR-067 .. RUN-FR-069,
CORE-FR-069, RUN-DD-SPEC.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..core.errors import ConfigurationError, OptionalDependencyError, SpecError
from ..core.events import validate_source_name
from ..core.plugins import plugin_folders
from .limits import Limit, TextLimit
from .resolve import Reference, parse_references, resolve_references

__all__ = [
    "Expectation",
    "Step",
    "TestCase",
    "TestSpec",
    "load_spec",
    "load_mapping",
    "render",
]

#: Keys accepted on an expectation but consumed by the limit, not the expectation.
_LIMIT_KEYS = ("min", "max", "minimum", "maximum", "equals", "nominal",
               "tolerance", "tolerance_percent", "matches", "one_of", "ignore_case",
               "reason")

#: The keys that make a limit a text limit (#242).
_TEXT_KEYS = ("matches", "one_of")

#: Bound keys a value saved by an earlier step can stand for (#242).
_BOUND_KEYS = {"min": "minimum", "max": "maximum", "minimum": "minimum", "maximum": "maximum"}


def _require_mapping(value, what: str) -> dict:
    if not isinstance(value, dict):
        raise SpecError("%s must be a mapping, got %s" % (what, type(value).__name__))
    return value


def render(template: str, value: float) -> str:
    """Render *value* through *template*, as a specification asked for.

    An integral value is rendered as an integer, so ``"{:06X}"`` works: a hex
    format cannot be applied to a float, and a value read out of a part is a
    whole number that arithmetic has turned into one.

    :raises SpecError: if the template cannot be applied, naming both. Falling
        back to the number would hide a broken specification behind a result
        that looks right.
    """
    number = float(value)
    if number.is_integer():
        number = int(number)
    try:
        return template.format(number)
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise SpecError(
            "format %r cannot be applied to %r: %s" % (template, value, exc)
        ) from exc


def _optional_number(value, what: str) -> Optional[float]:
    """A number, or None when the key was absent."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SpecError("%s has a non-numeric tolerance %r" % (what, value)) from exc


def _is_parameter(value) -> bool:
    return isinstance(value, dict) and "param" in value and set(value) <= {"param", "format"}


def substitute_parameters(data, parameters: Dict[str, Any]):
    """*data* with every ``{param: <name>}`` replaced by that parameter's value,
    or with ``{param: <name>, format: "WR X {}"}`` by the value rendered into
    that text, for a command that carries it.

    Done on the raw mapping, before anything is parsed, so a parameter can
    stand anywhere a literal could and is checked by the same rules.

    :raises SpecError: naming the parameter and those defined, for a name the
        ``parameters`` block does not define.
    """
    if _is_parameter(data):
        name = str(data["param"])
        if name not in parameters:
            raise SpecError(
                "{param: %s} names no parameter; the parameters block defines %s"
                % (name, ", ".join(sorted(parameters)) or "none"))
        value = parameters[name]
        if "format" in data:
            try:
                return str(data["format"]).format(value)
            except (IndexError, KeyError, ValueError) as exc:
                raise SpecError(
                    "{param: %s} has a format %r that cannot take %r: %s"
                    % (name, data["format"], value, exc)) from exc
        return value
    if isinstance(data, dict):
        return {key: substitute_parameters(value, parameters) for key, value in data.items()}
    if isinstance(data, list):
        return [substitute_parameters(item, parameters) for item in data]
    return data


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
    :param format: Template the scaled value is rendered through for the record,
        e.g. ``"{:06X}"``. Presentation only - the limit is checked against the
        number either way.
    """

    name: str
    measure: str
    limit: Union[Limit, TextLimit, None]
    unit: str = ""
    scale: float = 1.0
    display_unit: str = ""
    #: How the value is rendered in the record. Presentation only: the limit is
    #: still checked against the number. An identifier read off a part is the
    #: case this exists for - 662316 and 0A1B2C are the same value, and only one
    #: of them can be compared with what is printed on the board.
    format: str = ""
    reference: Optional[Reference] = None
    tolerance: Optional[float] = None
    tolerance_percent: Optional[float] = None
    #: Compare text without regard to case, for a limit taken from a step (#242).
    ignore_case: bool = False
    #: A limit that names saved values in its bounds or its ``one_of`` items,
    #: as written, built when the steps have run (#242).
    deferred: Optional[Dict[str, Any]] = None

    @classmethod
    def from_mapping(cls, data, index: int) -> "Expectation":  # pylint: disable=too-many-locals
        data = _require_mapping(data, "expectation %d" % index)
        measure = str(data.get("measure", ""))
        name = str(data.get("name") or measure or "value")
        limit_source = {key: data[key] for key in _LIMIT_KEYS if key in data}
        if not limit_source:
            raise SpecError(
                "expectation %r declares no limit; add min, max or equals" % name
            )

        ignore_case = bool(limit_source.get("ignore_case", False))
        # A limit may name a value saved by an earlier step rather than state
        # one. It can only be built when that step has run, so the expectation
        # carries the reference and the runner resolves it.
        reference = None
        for key in ("equals", "nominal"):
            if Reference.is_reference(limit_source.get(key)):
                reference = Reference.from_mapping(limit_source.pop(key))
                break
        if reference is not None and any(
            key in limit_source for key in ("minimum", "maximum", "min", "max")
        ):
            raise SpecError(
                "expectation %r takes a value from an earlier step and also "
                "declares a bound; use one or the other" % name
            )
        try:
            scale = float(data.get("scale", 1.0))
        except (TypeError, ValueError) as exc:
            raise SpecError("expectation %r has a non-numeric scale" % name) from exc
        if scale == 0.0:
            raise SpecError("expectation %r has a scale of zero" % name)
        unit = str(data.get("unit", ""))
        tolerance = tolerance_percent = None
        if reference is not None:
            tolerance = _optional_number(limit_source.pop("tolerance", None), name)
            tolerance_percent = _optional_number(
                limit_source.pop("tolerance_percent", None), name
            )
            limit_source.pop("ignore_case", None)
            if limit_source:
                raise SpecError(
                    "expectation %r takes its value from an earlier step, so "
                    "%s has nothing to bound"
                    % (name, ", ".join(sorted(limit_source)))
                )
            limit = None
            deferred = None
        else:
            deferred = cls._deferred(name, limit_source)
            limit = None if deferred is not None else cls._limit_for(name, limit_source)
            text = isinstance(limit, TextLimit) or (
                deferred is not None and any(key in deferred for key in _TEXT_KEYS))
            if text and (scale != 1.0 or data.get("format")):
                raise SpecError("expectation %r compares text, so scale and format, which "
                                "apply to a number, do not apply" % name)
        return cls(
            name=name,
            measure=measure,
            limit=limit,
            unit=unit,
            scale=scale,
            display_unit=str(data.get("display_unit", "")) or unit,
            reference=reference,
            format=str(data.get("format", "")),
            tolerance=tolerance,
            tolerance_percent=tolerance_percent,
            ignore_case=ignore_case,
            deferred=deferred,
        )

    @classmethod
    def _deferred(cls, name, source) -> Optional[Dict[str, Any]]:
        """*source* with its saved-value references, if it names any; else None.

        A bound (``min: {from: unloaded}``) or a ``one_of`` item may name a
        value an earlier step saved; the limit is then built when the steps
        have run. It is checked now, with a stand-in for each saved value, so
        a malformed limit is still a load error.
        """
        parsed = parse_references(source)
        references = [key for key, value in parsed.items()
                      if isinstance(value, Reference) and key in _BOUND_KEYS]
        items = parsed.get("one_of")
        in_items = isinstance(items, list) and any(isinstance(item, Reference)
                                                   for item in items)
        stray = [key for key, value in parsed.items()
                 if isinstance(value, Reference) and key not in _BOUND_KEYS]
        if stray:
            raise SpecError("expectation %r: %s cannot take a value from an earlier step"
                            % (name, ", ".join(sorted(stray))))
        if not references and not in_items:
            return None
        # A saved bound stands in as the widest it could be, so the check does
        # not find a stated bound "inverted" against a value not known yet.
        stand_in = {key: ((-1e300 if _BOUND_KEYS[key] == "minimum" else 1e300)
                          if isinstance(value, Reference) else value)
                    for key, value in parsed.items()}
        if in_items:
            stand_in["one_of"] = ["x" if isinstance(item, Reference) else item
                                  for item in items]
        cls._limit_for(name, stand_in)
        return parsed

    @staticmethod
    def _limit_for(name, source):
        """The limit this expectation checks against."""
        if "equals" in source and "nominal" in source:
            raise SpecError("expectation %r sets both equals and nominal, which are one "
                            "key; keep one" % name)
        source = dict(source)
        ignore_case = bool(source.pop("ignore_case", False))
        reason = str(source.pop("reason", "") or "")
        wanted = source.get("equals", source.get("nominal"))
        if isinstance(wanted, str) or any(key in source for key in _TEXT_KEYS):
            numeric = sorted(set(source) - {"equals", "nominal"} - set(_TEXT_KEYS))
            if numeric:
                raise SpecError(
                    "expectation %r compares against text, so it cannot also "
                    "declare a tolerance or a bound (%s)" % (name, ", ".join(numeric))
                )
            items = source.get("one_of")
            if items is not None and (not isinstance(items, (list, tuple)) or not items):
                raise SpecError("expectation %r: one_of must be a list of values" % name)
            return TextLimit(
                equals=None if wanted is None else str(wanted).strip(),
                matches=None if source.get("matches") is None else str(source["matches"]),
                one_of=tuple(items or ()),
                ignore_case=ignore_case,
                reason=reason,
            )
        if ignore_case or reason:
            raise SpecError("expectation %r: ignore_case and reason apply only to a text "
                            "limit" % name)
        return Limit.from_mapping(source)

    def limit_against(self, saved) -> Union[Limit, TextLimit]:
        """The limit to apply, with any reference to an earlier step resolved.

        :raises SpecError: if the reference cannot be resolved, or resolves to
            text where a tolerance was declared.
        """
        if self.deferred is not None:
            resolved = resolve_references(self.deferred, saved)
            for key in [key for key in resolved if key in _BOUND_KEYS]:
                value = resolved[key]
                if isinstance(value, (bytes, bytearray)):
                    value = value.decode("utf-8", errors="replace")
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise SpecError(
                        "expectation %r cannot bound with %r taken from an earlier "
                        "step" % (self.name, resolved[key])) from exc
                if not math.isfinite(value):
                    raise SpecError("expectation %r: the bound taken from an earlier step "
                                    "is %r, not a finite number" % (self.name, value))
                resolved[key] = value
            if isinstance(resolved.get("one_of"), list):
                resolved["one_of"] = [
                    item.decode("utf-8", errors="replace")
                    if isinstance(item, (bytes, bytearray)) else item
                    for item in resolved["one_of"]]
            return self._limit_for(self.name, resolved)
        if self.reference is None:
            return self.limit
        wanted = self.reference.resolve(saved)
        if isinstance(wanted, (bytes, bytearray)):
            wanted = wanted.decode("utf-8", errors="replace")
        if isinstance(wanted, str):
            if self.tolerance is not None or self.tolerance_percent is not None:
                raise SpecError(
                    "expectation %r declares a tolerance, but %s is the text "
                    "%r" % (self.name, self.reference.path, wanted)
                )
            return TextLimit(wanted.strip(), ignore_case=self.ignore_case)
        try:
            numeric = float(wanted)
        except (TypeError, ValueError) as exc:
            raise SpecError(
                "expectation %r cannot compare against %r taken from %s"
                % (self.name, wanted, self.reference.path)
            ) from exc
        return Limit(
            equals=numeric,
            tolerance=self.tolerance,
            tolerance_percent=self.tolerance_percent,
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
            arguments=parse_references(dict(arguments)),
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


def _parse_instruments(declared) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Split ``instruments:`` into alias-to-driver and alias-to-event-name.

    An entry is a driver name (``temp: pico-sht30``) or a mapping
    (``temp: {driver: pico-sht30, event: TEMP}``) in which either key may be
    left out. An event name is checked here, and two aliases may not share one.
    """
    if not isinstance(declared, dict):
        raise SpecError(
            "'instruments' must be a mapping of alias to driver name, got %s"
            % type(declared).__name__
        )
    drivers: Dict[str, str] = {}
    events: Dict[str, str] = {}
    for alias, entry in declared.items():
        alias = str(alias)
        if isinstance(entry, dict):
            unknown = sorted(set(entry) - {"driver", "event"})
            if unknown:
                raise SpecError(
                    "instrument %r: unknown key(s) %s; an entry takes 'driver' and 'event'"
                    % (alias, ", ".join(unknown)))
            if entry.get("driver"):
                drivers[alias] = str(entry["driver"])
            if entry.get("event") is not None:
                try:
                    events[alias] = validate_source_name(
                        entry["event"], "instrument %r event name" % alias)
                except ConfigurationError as exc:
                    raise SpecError(str(exc)) from exc
        else:
            drivers[alias] = str(entry)
    seen: Dict[str, str] = {}
    for alias, event in sorted(events.items()):
        if event in seen:
            raise SpecError(
                "instruments %r and %r are both given event name %r; each "
                "instrument's records need a name of their own" % (seen[event], alias, event))
        seen[event] = alias
    return drivers, events


@dataclass(frozen=True)
class TestSpec:
    """A suite of tests, with shared setup and teardown.

    :param setup: Steps run once before the tests. A failure here aborts the
        suite, because every test would otherwise run against an unknown setup.
    :param teardown: Steps run once after the tests, whatever the outcome.
    :param instrument_drivers: Optional mapping of alias to the driver the
        specification expects there. Two things depend on it: ``--simulate`` can
        stand up the right simulator for each alias without a bench file, and the
        runner can reject a bench that provides the wrong *kind* of instrument
        rather than failing later on a missing method.
    :param instrument_events: Optional mapping of alias to the short name its
        event-log records carry (``TEMP``). It overrides any name the bench
        gives the instrument (RUN-FR-008, #126).
    """

    # Not a pytest test class, despite the name.
    __test__ = False

    name: str
    tests: Sequence[TestCase]
    description: str = ""
    #: A hazard the operator must know about *before* anything is energised.
    #: The runner prints it ahead of the first setup step and, on real
    #: hardware, refuses to start until it is acknowledged. A description
    #: would not do: it reaches the reader in the report, by which time the
    #: supply has been on for a while.
    warning: str = ""
    requirements: Sequence[str] = ()
    setup: Sequence[Step] = ()
    teardown: Sequence[Step] = ()
    instrument_drivers: Dict[str, str] = field(default_factory=dict)
    instrument_events: Dict[str, str] = field(default_factory=dict)
    source: str = ""
    #: The values the ``parameters`` block set, as used; for the record.
    parameters: Dict[str, Any] = field(default_factory=dict)
    #: Device plugin folders the specification needs (``plugins:``, #238),
    #: absolute: those whose decoders and register files its steps name.
    plugins: Sequence[str] = ()

    @classmethod
    def from_mapping(cls, data, source: str = "") -> "TestSpec":
        data = _require_mapping(data, "specification")
        parameters = data.get("parameters", {}) or {}
        if not isinstance(parameters, dict):
            raise SpecError(
                "'parameters' must be a mapping of name to value, got %s"
                % type(parameters).__name__)
        for key, value in parameters.items():
            if isinstance(value, (dict, list)):
                raise SpecError("parameter %r must be a single value, got %r" % (key, value))
        parameters = {str(key): value for key, value in parameters.items()}
        data = substitute_parameters(
            {key: value for key, value in data.items() if key != "parameters"}, parameters)
        name = data.get("name")
        if not name:
            raise SpecError("specification has no name")
        tests = _require_sequence(data.get("tests", []), "tests")
        if not tests:
            raise SpecError("specification %r contains no tests" % name)
        requirements = data.get("requirements", []) or []
        if isinstance(requirements, str):
            requirements = [requirements]
        drivers, events = _parse_instruments(data.get("instruments", {}) or {})
        return cls(
            instrument_drivers=drivers,
            instrument_events=events,
            name=str(name),
            description=str(data.get("description", "")),
            warning=str(data.get("warning", "")).strip(),
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
            parameters=parameters,
            plugins=plugin_folders(
                data.get("plugins"),
                os.path.dirname(os.path.abspath(source)) if source else None,
                source or str(name)),
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
