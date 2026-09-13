"""Declarative bench test runner.

A test specification says what to do and what counts as a pass; a bench
configuration says which instruments exist and where. Keeping them apart is what
lets the same suite run on the real rig, on a second rig, or entirely against
simulators.

::

    from benchtools.runner import BenchConfig, BenchRunner, load_spec

    spec = load_spec("tests/clock_skew.yaml")
    config = BenchConfig.simulated(spec.instruments_used)
    with BenchRunner.from_config(config) as runner:
        result = runner.run(spec)
    print(result.status, result.passed, "of", result.total)

Traces to: RUN-ARC-001.
"""

from .bench import (
    Bench,
    BenchConfig,
    InstrumentConfig,
    load_bench,
    register_driver,
    registered_drivers,
)
from .limits import Limit, LimitOutcome
from .report import format_markdown, summary_line, write_json, write_junit, write_markdown
from .resolve import resolve_path
from .results import CaseRecord, MeasurementRecord, RunRecord, Status, StepRecord
from .runner import BenchRunner
from .spec import Expectation, Step, TestCase, TestSpec, load_spec

__all__ = [
    "BenchRunner",
    "Bench",
    "BenchConfig",
    "InstrumentConfig",
    "load_bench",
    "register_driver",
    "registered_drivers",
    "TestSpec",
    "TestCase",
    "Step",
    "Expectation",
    "load_spec",
    "Limit",
    "LimitOutcome",
    "resolve_path",
    "Status",
    "RunRecord",
    "CaseRecord",
    "StepRecord",
    "MeasurementRecord",
    "write_json",
    "write_markdown",
    "write_junit",
    "format_markdown",
    "summary_line",
]
