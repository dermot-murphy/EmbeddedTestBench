"""Command line for the bench test runner.

::

    benchtools run tests/clock_skew.yaml --bench benches/lab1.yaml
    benchtools run tests/*.yaml --simulate --markdown report.md

Exit status is ``0`` when everything passed, ``1`` when a test failed or a step
could not be executed, and ``2`` for a usage or specification error. That makes
it usable directly as a CI step.

Traces to: RUN-FR-050 .. RUN-FR-053, RUN-DD-CLI.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional, Sequence

from .. import __version__
from ..core.errors import BenchToolsError
from .bench import BenchConfig, load_bench, registered_drivers
from .report import summary_line, write_json, write_junit, write_markdown
from .results import RunRecord, Status
from .runner import BenchRunner
from .spec import load_spec

__all__ = ["main", "build_parser"]

_LOG = logging.getLogger("benchtools.runner")

_EXIT_OK = 0
_EXIT_PROBLEM = 1
_EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for ``benchtools run``."""
    parser = argparse.ArgumentParser(
        prog="benchtools run",
        description="Run declarative bench test specifications against a bench.",
        epilog="Use --simulate to exercise a specification with no hardware.",
    )
    parser.add_argument("specs", nargs="+", metavar="SPEC",
                        help="test specification files (.yaml or .json)")
    parser.add_argument("-b", "--bench", metavar="PATH",
                        help="bench configuration file; omit with --simulate")
    parser.add_argument("--simulate", action="store_true",
                        help="replace every instrument with its simulator")
    parser.add_argument("--simulate-driver", default="tek3014b",
                        choices=registered_drivers(),
                        help="driver used for simulated instruments when no bench "
                             "configuration is given (default: %(default)s)")
    parser.add_argument("--json", metavar="PATH", help="write the full result record as JSON")
    parser.add_argument("--markdown", metavar="PATH", help="write a markdown report")
    parser.add_argument("--junit", metavar="PATH", help="write a JUnit XML report for CI")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="abandon the remaining tests after the first error")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="increase logging (repeat for debug)")
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    return parser


def _load_bench_config(args: argparse.Namespace, aliases: Sequence[str]) -> BenchConfig:
    """Resolve the bench configuration from the arguments."""
    if args.bench:
        config = load_bench(args.bench)
        if args.simulate:
            _LOG.info("--simulate: ignoring configured resources in %s", args.bench)
        return config
    if not args.simulate:
        raise BenchToolsError(
            "no bench configuration given. Pass --bench PATH for real hardware, "
            "or --simulate to run the specification against simulators."
        )
    return BenchConfig.simulated(aliases, driver=args.simulate_driver)


def _write_reports(run: RunRecord, args: argparse.Namespace, index: int, total: int) -> None:
    """Write whichever reports were requested, suffixing when there are several."""

    def target(path: str) -> str:
        if total == 1 or not path:
            return path
        root, _, suffix = path.rpartition(".")
        return "%s_%d.%s" % (root, index + 1, suffix) if root else "%s_%d" % (path, index + 1)

    if args.json:
        print("  JSON    : %s" % write_json(run, target(args.json)))
    if args.markdown:
        print("  Markdown: %s" % write_markdown(run, target(args.markdown)))
    if args.junit:
        print("  JUnit   : %s" % write_junit(run, target(args.junit)))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools run``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        specs = [load_spec(path) for path in args.specs]
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_USAGE

    aliases = sorted({alias for spec in specs for alias in spec.instruments_used})
    try:
        config = _load_bench_config(args, aliases)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_USAGE

    runs: List[RunRecord] = []
    with BenchRunner.from_config(
        config, simulate=args.simulate, stop_on_error=args.stop_on_error
    ) as runner:
        for index, spec in enumerate(specs):
            run = runner.run(spec)
            runs.append(run)
            print(summary_line(run))
            if run.setup_error:
                print("  setup failed: %s" % run.setup_error, file=sys.stderr)
            for case in run.cases:
                if case.status.is_problem:
                    print("  %-7s %s%s" % (
                        case.status.value,
                        case.name,
                        (" - " + case.error) if case.error else "",
                    ))
                    for measurement in case.measurements:
                        if measurement.status.is_problem:
                            print("            %s: %s" % (measurement.name, measurement.reason))
            _write_reports(run, args, index, len(specs))

    worst = Status.worst([run.status for run in runs])
    return _EXIT_PROBLEM if worst.is_problem else _EXIT_OK
