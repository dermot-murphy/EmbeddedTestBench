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
from ..core.events import start_event_log
from .bench import BenchConfig, load_bench, registered_drivers
from .report import summary_line, write_json, write_junit, write_markdown
from .results import RunRecord, Status
from .control import HOST, ControlServer, RunControl
from .runner import BenchRunner, check_selection
from .spec import load_spec

__all__ = ["main", "build_parser"]

_LOG = logging.getLogger("benchtools.runner")

_EXIT_OK = 0
_EXIT_PROBLEM = 1
_EXIT_USAGE = 2
_EXIT_NOT_ACKNOWLEDGED = 3


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
                        help="driver for simulated instruments whose alias the specification "
                             "does not declare (default: %(default)s)")
    parser.add_argument("--json", metavar="PATH", help="write the full result record as JSON")
    parser.add_argument("--markdown", metavar="PATH", help="write a markdown report")
    parser.add_argument("--event-log", metavar="PATH",
                        help="write every instrument's and the runner's log records to "
                             "PATH as JSON Lines while the run goes - what the Test "
                             "Bench monitor's Events page follows")
    parser.add_argument("--junit", metavar="PATH", help="write a JUnit XML report for CI")
    parser.add_argument("--test", action="append", default=[], metavar="NAME",
                        help="run only the test case with this exact name; repeat to run "
                             "several. Those left out are reported as skipped, 'not "
                             "selected'. Suite setup and teardown still run")
    parser.add_argument("--control", type=int, metavar="PORT",
                        help="serve a control channel on 127.0.0.1:PORT (0 picks a free "
                             "port) so the test run viewer can pause, resume, abort or "
                             "restart the run between steps")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="abandon the remaining tests after the first error")
    parser.add_argument("--acknowledge", action="store_true",
                        help="confirm a specification's safety warning without being asked; "
                             "needed to run a warned specification unattended on real hardware")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="increase logging (repeat for debug)")
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    return parser


def _warnings_of(specs) -> list:
    """The safety warnings the specifications about to run carry."""
    return [(spec.name, spec.warning) for spec in specs if spec.warning]


def _announce_warnings(warned) -> None:
    """Put the hazards on the console before anything is energised.

    Written to stderr so that a run whose stdout is being captured still puts
    the warning in front of whoever is standing at the bench.
    """
    for name, warning in warned:
        print("", file=sys.stderr)
        print("!" * 72, file=sys.stderr)
        print("SAFETY WARNING - %s" % name, file=sys.stderr)
        print("!" * 72, file=sys.stderr)
        for line in warning.splitlines():
            print(line, file=sys.stderr)
        print("!" * 72, file=sys.stderr)
        print("", file=sys.stderr)


def _acknowledged(warned, acknowledged: bool, simulated: bool) -> bool:
    """Whether a warned run may proceed.

    A simulated bench is never gated: nothing is energised, and CI has nobody
    to answer the question. On real hardware the run stops unless the operator
    says so - either beforehand with ``--acknowledge``, or by answering the
    prompt. Refusing an unattended run is deliberate: a warning that a script
    can skip by not reading it is not a control at all, and the thing it is
    protecting is something the operator cannot get back.
    """
    if not warned or simulated or acknowledged:
        return True
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        print(
            "error: this specification carries a safety warning and the bench is "
            "not simulated, but there is no terminal to confirm at. Re-run with "
            "--acknowledge once the warning above has been acted on.",
            file=sys.stderr,
        )
        return False
    try:
        answer = input("Type 'yes' to confirm the warning above has been acted on: ")
    except EOFError:
        answer = ""
    if answer.strip().lower() == "yes":
        return True
    print("error: not confirmed; nothing was energised.", file=sys.stderr)
    return False


def _load_bench_config(args: argparse.Namespace, aliases) -> BenchConfig:
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
    event_log = start_event_log(args.event_log) if args.event_log else None
    try:
        return _run(args)
    finally:
        if event_log is not None:
            logging.getLogger("benchtools").removeHandler(event_log)
            event_log.close()


def _run(args) -> int:
    """The run itself, once logging is set up."""
    try:
        specs = [load_spec(path) for path in args.specs]
        check_selection(specs, args.test)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_USAGE

    # Prefer each specification's declared driver per alias, so a suite spanning
    # an oscilloscope and a debug probe can be simulated without a bench file.
    aliases: dict = {}
    for spec in specs:
        for alias in spec.instruments_used:
            aliases.setdefault(alias, spec.instrument_drivers.get(alias, ""))
        for alias, driver in spec.instrument_drivers.items():
            if driver:
                aliases[alias] = driver
    try:
        config = _load_bench_config(args, aliases)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_USAGE

    # Before the bench is opened, let alone a setup step run: a warning that
    # arrives after the supply is on has warned nobody.
    warned = _warnings_of(specs)
    _announce_warnings(warned)

    control = RunControl() if args.control is not None else None
    server = None
    if control is not None:
        try:
            server = ControlServer(control, args.control).start()
        except OSError as exc:
            print("error: cannot serve the control channel on %s:%d: %s"
                  % (HOST, args.control, exc), file=sys.stderr)
            return _EXIT_USAGE
        print("control channel on %s:%d" % (HOST, server.port), file=sys.stderr)
    try:
        return _run_specs(args, specs, config, warned, control)
    finally:
        if server is not None:
            server.close()


def _run_specs(args, specs, config, warned, control) -> int:
    """Run each specification in turn on one bench."""
    runs: List[RunRecord] = []
    with BenchRunner.from_config(
        config, simulate=args.simulate, stop_on_error=args.stop_on_error, control=control
    ) as runner:
        if not _acknowledged(warned, args.acknowledge, runner.bench.is_simulated):
            return _EXIT_NOT_ACKNOWLEDGED
        for index, spec in enumerate(specs):
            run = runner.run(spec, args.test)
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
