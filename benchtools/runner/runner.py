"""Execution engine: run a specification against a bench.

The engine does four things and nothing else: resolve each step's action to a
bound method on a bench instrument, call it, extract the declared measurements
from the result, and check them against their limits. Everything it knows about
instruments it learns from the bench; everything it knows about intent it learns
from the specification.

Two distinctions are deliberate and worth stating, because reports are only
useful if they mean something:

* A **failure** is a measurement outside its limit. The bench worked; the thing
  under test did not meet its requirement.
* An **error** is a step that could not be executed - an instrument that would
  not connect, a misspelled action, a trigger that never arrived. The test told
  you nothing.

Conflating them turns a broken rig into a pile of apparent product defects.

Traces to: RUN-FR-008, RUN-FR-010 .. RUN-FR-037, RUN-ARC-001, RUN-DD-RUNNER.
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..core.errors import BenchToolsError, SpecError
from ..core.events import log_event
from ..core.paths import input_path_names, resolve_arguments
from .bench import Bench, BenchConfig
from .limits import Limit, TextLimit
from .resolve import resolve_path, resolve_references
from .results import CaseRecord, MeasurementRecord, RunRecord, Status, StepRecord
from .spec import Expectation, Step, TestSpec, render

__all__ = ["BenchRunner", "BUILTIN_ACTIONS", "NOT_SELECTED", "check_selection"]

_LOG = logging.getLogger(__name__)

#: The rationale recorded for a test case the run was not asked for (#134).
NOT_SELECTED = "not selected"

#: Where a step sits, as the event log names it (#135).
PHASE_SETUP = "setup"
PHASE_TEST = "test"
PHASE_TEARDOWN = "teardown"


def check_selection(specs: Sequence[TestSpec], selection: Sequence[str]) -> None:
    """Refuse a selection naming a test case that none of *specs* contains.

    Checked before the bench opens: a misspelt name would otherwise run
    nothing and report every test case as not selected.

    :raises SpecError: naming each unknown test case and the ones there are.
    """
    known = [case.name for spec in specs for case in spec.tests]
    unknown = [name for name in selection if name not in known]
    if unknown:
        raise SpecError(
            "no test case named %s; the specification%s contain%s: %s" % (
                ", ".join(repr(name) for name in unknown),
                "s" if len(specs) > 1 else "",
                "" if len(specs) > 1 else "s",
                ", ".join(repr(name) for name in known) or "none",
            )
        )


def _action_sleep(seconds: float = 0.1) -> float:
    """Wait, for a settling time a specification needs to state explicitly."""
    time.sleep(float(seconds))
    return float(seconds)


#: Actions that are not bound to an instrument.
BUILTIN_ACTIONS: Dict[str, Callable[..., Any]] = {
    "sleep": _action_sleep,
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class BenchRunner:
    """Runs test specifications against a bench.

    :param bench: The live bench. Instruments connect on first use.
    :param stop_on_error: Abandon the remaining tests after the first error.
        Failures never stop the run: the point of a suite is to learn everything
        that is out of limit in one pass.
    """

    def __init__(self, bench: Bench, stop_on_error: bool = False) -> None:
        self.bench = bench
        self.stop_on_error = bool(stop_on_error)
        self._saved: Dict[str, Any] = {}
        #: Directory of the specification being run: where a relative input
        #: path in one of its steps is looked for first.
        self._spec_directory: Optional[str] = None

    # ------------------------------------------------------------------
    @classmethod
    def from_config(
        cls,
        config: BenchConfig,
        simulate: bool = False,
        stop_on_error: bool = False,
    ) -> "BenchRunner":
        """Build a runner for *config*."""
        return cls(Bench(config, simulate=simulate), stop_on_error=stop_on_error)

    # ------------------------------------------------------------------
    # Action resolution
    # ------------------------------------------------------------------
    def _resolve_action(self, action: str) -> Callable[..., Any]:
        """Return the callable a step's ``do:`` names.

        Only public methods of bench instruments are reachable, so a
        specification - which is data, and may be authored by someone who is not
        reviewing the driver - cannot call private internals.
        """
        if action in BUILTIN_ACTIONS:
            return BUILTIN_ACTIONS[action]

        alias, separator, method_name = action.partition(".")
        if not separator:
            raise SpecError(
                "action %r must be '<instrument>.<method>' or one of the built-in "
                "actions (%s)" % (action, ", ".join(sorted(BUILTIN_ACTIONS)))
            )
        if method_name.startswith("_"):
            raise SpecError("action %r refers to a private method" % action)

        instrument = self.bench.get(alias)
        if not hasattr(instrument, method_name):
            available = sorted(
                name for name in dir(instrument) if not name.startswith("_")
            )
            raise SpecError(
                "instrument %r (%s) has no method or property %r. Available: %s"
                % (alias, type(instrument).__name__, method_name, ", ".join(available))
            )

        member = getattr(instrument, method_name)
        if callable(member):
            return member

        # A property is a reading with no arguments and no side effects, which
        # is exactly what a measurement step is. Refusing them would force a
        # driver to wrap `firmware_version` in `get_firmware_version()` for the
        # runner's benefit, which is the tail wagging the dog.
        def read_property(**arguments):
            if arguments:
                raise SpecError(
                    "%r is a property of %s and takes no arguments, but %s "
                    "%s given"
                    % (
                        action,
                        type(instrument).__name__,
                        ", ".join(sorted(arguments)),
                        "was" if len(arguments) == 1 else "were",
                    )
                )
            # Read now rather than at resolution time: a property read when the
            # step runs is the value at that moment, which is the point.
            return getattr(instrument, method_name)

        return read_property

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------
    def _check_expectation(self, result: Any, expectation: Expectation) -> MeasurementRecord:
        """Extract one value from *result* and check it against its limit."""
        limit_text = expectation.limit.text if expectation.limit else str(expectation.reference)

        def failed_to_resolve(reason: str) -> MeasurementRecord:
            return MeasurementRecord(
                name=expectation.name,
                value=None,
                unit=expectation.display_unit,
                limit=limit_text,
                status=Status.ERROR,
                reason=reason,
            )

        try:
            raw = resolve_path(result, expectation.measure)
        except SpecError as exc:
            return failed_to_resolve(str(exc))

        # A limit may be a value an earlier step saved, so it is built here
        # rather than when the specification was loaded.
        try:
            limit = expectation.limit_against(self._saved)
        except SpecError as exc:
            return failed_to_resolve(str(exc))
        limit_text = limit.text

        if isinstance(limit, TextLimit):
            # Compared as text: no scaling, and bytes are decoded so a reply
            # straight off a link compares against what the specification says.
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            outcome = limit.check(raw)
            return MeasurementRecord(
                name=expectation.name,
                value=None if raw is None else str(raw).strip(),
                unit=expectation.display_unit,
                limit=outcome.text,
                status=Status.PASS if outcome.passed else Status.FAIL,
                reason=outcome.reason,
            )

        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            return failed_to_resolve("measured value %r is not a number" % (raw,))

        scaled = numeric * expectation.scale
        outcome = limit.check(scaled)
        reported: Any = scaled
        limit_text = outcome.text
        if expectation.format:
            # Presentation only, and the number is kept in raw_value: an
            # identifier is unreadable in decimal, and a limit whose bounds
            # were still decimal beside a hex value would be worse than either.
            try:
                reported = render(expectation.format, scaled)
                limit_text = self._render_limit(limit, expectation.format)
            except SpecError as exc:
                return failed_to_resolve(str(exc))
        return MeasurementRecord(
            name=expectation.name,
            value=reported,
            unit=expectation.display_unit,
            limit=limit_text,
            status=Status.PASS if outcome.passed else Status.FAIL,
            reason=outcome.reason,
            raw_value=numeric,
        )

    @staticmethod
    def _render_limit(limit: Limit, template: str) -> str:
        """The limit's text with its bounds rendered as the value will be."""
        parts = []
        if limit.equals is not None:
            window = limit.window
            if window is None:
                parts.append("= %s" % render(template, limit.equals))
            else:
                parts.append(
                    "= %s +/- %s"
                    % (render(template, limit.equals), render(template, window))
                )
        if limit.minimum is not None:
            parts.append(">= %s" % render(template, limit.minimum))
        if limit.maximum is not None:
            parts.append("<= %s" % render(template, limit.maximum))
        return ", ".join(parts)

    def run_step(self, step: Step, phase: str = PHASE_TEST,
                 case_index: Optional[int] = None,
                 step_index: Optional[int] = None) -> StepRecord:
        """Execute one step and check its expectations.

        The step's start and end go to the event log as ``step_start`` and
        ``step_end`` (#135). *phase*, *case_index* and *step_index* say where
        it sits - ``setup``, ``test`` or ``teardown``, which test case, which
        step - so a reader can place it without counting.
        """
        where = {"phase": phase, "case": case_index, "step": step_index}
        log_event(_LOG, "step_start", "step %s starting" % step.action, dict(
            where, action=step.action, arguments=step.arguments,
            description=step.description, save=step.save,
        ), level=logging.DEBUG)
        record, arguments, result = self._execute_step(step)
        log_event(_LOG, "step_end", "step %s: %s%s" % (
            step.action, record.status.value, (" - " + record.error) if record.error else "",
        ), dict(
            where, action=step.action, arguments=arguments, result=result,
            save=step.save if record.status is not Status.ERROR else None,
            status=record.status.value, error=record.error,
            duration_s=round(record.duration_s, 6),
            measurements=[m.as_dict() for m in record.measurements],
        ), level=logging.DEBUG)
        return record

    def _execute_step(self, step: Step) -> Tuple[StepRecord, Any, Any]:
        """Run *step*: its record, the arguments it was called with, and its result."""
        started = time.monotonic()
        record = StepRecord(
            action=step.action,
            status=Status.PASS,
            description=step.description,
        )
        arguments: Any = step.arguments
        try:
            method = self._resolve_action(step.action)
            # Any argument may name a value an earlier step saved. Resolving
            # here rather than at load time is the point: the value does not
            # exist until that step has run.
            arguments = resolve_references(step.arguments, self._saved)
            # A file the driver will read is found beside the specification
            # that names it, not wherever the runner happened to be started.
            arguments = resolve_arguments(
                arguments,
                input_path_names(method),
                self._spec_directory,
                what=step.action,
            )
            _LOG.info("step %s(%s)", step.action, ", ".join(
                "%s=%r" % item for item in sorted(arguments.items())
            ))
            result = method(**arguments)
        except BenchToolsError as exc:
            record.status = Status.ERROR
            record.error = "%s: %s" % (type(exc).__name__, exc)
            record.duration_s = time.monotonic() - started
            return record, arguments, None
        except TypeError as exc:
            # Almost always a specification error: wrong or missing arguments.
            record.status = Status.ERROR
            record.error = "%s could not be called as specified: %s" % (step.action, exc)
            record.duration_s = time.monotonic() - started
            return record, arguments, None
        except Exception as exc:  # noqa: BLE001 - a driver may raise anything
            record.status = Status.ERROR
            record.error = "%s raised %s: %s" % (step.action, type(exc).__name__, exc)
            record.duration_s = time.monotonic() - started
            return record, arguments, None

        if step.save:
            self._saved[step.save] = result

        for expectation in step.expectations:
            record.measurements.append(self._check_expectation(result, expectation))
        record.status = Status.worst([m.status for m in record.measurements])
        record.duration_s = time.monotonic() - started
        return record, arguments, result

    def run_steps(self, steps: Sequence[Step], phase: str = PHASE_TEST,
                  case_index: Optional[int] = None) -> List[StepRecord]:
        """Execute *steps* in order, stopping at the first step that errors."""
        records: List[StepRecord] = []
        for index, step in enumerate(steps):
            record = self.run_step(step, phase, case_index, index)
            records.append(record)
            if record.status is Status.ERROR:
                break
        return records

    # ------------------------------------------------------------------
    # Case and suite execution
    # ------------------------------------------------------------------
    def run_case(self, case, index: Optional[int] = None) -> CaseRecord:
        """Execute one test case; *index* is its position in the specification."""
        log_event(_LOG, "case_start", "running test %r" % case.name, {
            "case": index, "name": case.name, "requirement": case.requirement,
        })
        record = self._execute_case(case, index)
        self._log_case_end(record, index)
        return record

    def _execute_case(self, case, index: Optional[int]) -> CaseRecord:
        if case.skip:
            return CaseRecord(
                name=case.name,
                status=Status.SKIP,
                requirement=case.requirement,
                skip_reason=case.skip_reason or "marked skip in the specification",
            )
        started = time.monotonic()
        steps = self.run_steps(case.steps, PHASE_TEST, index)
        record = CaseRecord(
            name=case.name,
            status=Status.worst([step.status for step in steps]),
            requirement=case.requirement,
            steps=steps,
            duration_s=time.monotonic() - started,
        )
        if record.status is Status.ERROR:
            record.error = next(
                (step.error for step in steps if step.error), "a step failed to execute"
            )
        return record

    @staticmethod
    def _log_case_end(record: CaseRecord, index: Optional[int]) -> None:
        reason = record.error or record.skip_reason
        log_event(_LOG, "case_end", "test %r: %s%s" % (
            record.name, record.status.value, (" - " + reason) if reason else "",
        ), {
            "case": index, "name": record.name, "status": record.status.value,
            "error": record.error, "skip_reason": record.skip_reason,
            "duration_s": round(record.duration_s, 6),
        })

    @staticmethod
    def _plan(spec: TestSpec, selection: Sequence[str]) -> Dict[str, Any]:
        """Everything the run will do, for ``run_start``.

        A reader can draw the whole tree before the first step, and one that
        attaches part-way through still can.
        """

        def steps(sequence):
            return [{"step": index, "action": step.action, "arguments": step.arguments,
                     "description": step.description, "save": step.save}
                    for index, step in enumerate(sequence)]

        return {
            "suite": spec.name,
            "spec_source": spec.source,
            "requirements": list(spec.requirements),
            "parameters": dict(spec.parameters),
            "selection": list(selection),
            "setup": steps(spec.setup),
            "teardown": steps(spec.teardown),
            "tests": [{
                "case": index, "name": case.name, "requirement": case.requirement,
                "description": case.description,
                "selected": not selection or case.name in selection,
                "skip": case.skip, "steps": steps(case.steps),
            } for index, case in enumerate(spec.tests)],
        }

    def run(self, spec: TestSpec, selection: Sequence[str] = ()) -> RunRecord:
        """Run a whole specification and return its result record.

        Setup failures abort the suite: every test after an unknown setup would
        report a number that means nothing. Teardown always runs.

        :param selection: Names of the test cases to run; empty runs them all.
            A test case left out is recorded as skipped, "not selected", so
            the record says what was not executed and why (#134).

        The run's start and end go to the event log as ``run_start``, carrying
        the whole plan, and ``run_end``, carrying the verdict (#135).
        """
        run = RunRecord(
            suite=spec.name,
            bench=self.bench.config.name,
            requirements=tuple(spec.requirements),
            spec_source=spec.source,
            parameters=dict(spec.parameters),
            simulated=self.bench.is_simulated,
            started=_now(),
            selection=tuple(selection),
        )
        started = time.monotonic()
        self._saved = {}
        self._spec_directory = (
            os.path.dirname(os.path.abspath(spec.source)) if spec.source else None
        )
        plan = self._plan(spec, selection)
        plan.update(bench=run.bench, simulated=run.simulated)
        log_event(_LOG, "run_start", "running %r" % spec.name, plan)
        try:
            self._run_body(spec, selection, run, started)
        finally:
            log_event(_LOG, "run_end", "%r: %s" % (spec.name, run.status.value), {
                "suite": spec.name, "status": run.status.value,
                "setup_error": run.setup_error,
                "duration_s": round(run.duration_s, 6),
                "totals": {"total": run.total, "passed": run.passed, "failed": run.failed,
                           "errored": run.errored, "skipped": run.skipped},
            })
        return run

    def _run_body(self, spec: TestSpec, selection: Sequence[str], run: RunRecord,
                  started: float) -> None:
        try:
            self.bench.require(spec.instruments_used)
            self.bench.check_drivers(spec.instrument_drivers)
            # Before anything connects: names are given at construction, and a
            # clash is refused rather than discovered in the log (#126).
            self.bench.name_events(spec.instrument_events)
            self.bench.check_event_sources(spec.instruments_used)
        except BenchToolsError as exc:
            run.setup_error = str(exc)
            run.instruments = self.bench.describe_instruments()
            run.finished = _now()
            run.duration_s = time.monotonic() - started
            return

        try:
            if spec.setup:
                _LOG.info("running suite setup (%d step(s))", len(spec.setup))
                setup_records = self.run_steps(spec.setup, PHASE_SETUP)
                broken = [record for record in setup_records if record.status is not Status.PASS]
                if broken:
                    run.setup_error = "setup step %r: %s" % (
                        broken[0].action,
                        broken[0].error or "an expectation was not met",
                    )
                    return

            for index, case in enumerate(spec.tests):
                if selection and case.name not in selection:
                    record = CaseRecord(
                        name=case.name,
                        status=Status.SKIP,
                        requirement=case.requirement,
                        skip_reason=NOT_SELECTED,
                    )
                    self._log_case_end(record, index)
                    run.cases.append(record)
                    continue
                record = self.run_case(case, index)
                run.cases.append(record)
                if record.status is Status.ERROR and self.stop_on_error:
                    _LOG.warning("stopping after an error in %r", case.name)
                    break
        finally:
            if spec.teardown:
                _LOG.info("running suite teardown (%d step(s))", len(spec.teardown))
                self.run_steps(spec.teardown, PHASE_TEARDOWN)
            # Recorded before closing, and after the run rather than before, so
            # an instrument the suite updated - a dongle reflashed in setup -
            # is recorded as what actually produced the measurements.
            run.instruments = self.bench.describe_instruments()
            run.finished = _now()
            run.duration_s = time.monotonic() - started

    def close(self) -> None:
        """Close every instrument the run opened."""
        self.bench.close()

    def __enter__(self) -> "BenchRunner":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False
