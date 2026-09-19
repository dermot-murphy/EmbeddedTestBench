#!/usr/bin/env python3
"""Run a declarative bench test suite from Python.

The same thing the ``benchtools run`` command does, driven from code - useful
when a suite is one step in a larger sequence, or when the bench is assembled
programmatically.

    python examples/04_run_bench_suite.py                    # simulated
    python examples/04_run_bench_suite.py benches/lab1.yaml  # real hardware
"""

import os
import sys

from benchtools.runner import BenchConfig, BenchRunner, load_bench, load_spec
from benchtools.runner.report import format_markdown, summary_line

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(HERE, "specs", "clock_skew.yaml")


def main(bench_path: str = "") -> int:
    spec = load_spec(SPEC)
    print("Suite      :", spec.name)
    print("Instruments:", ", ".join(spec.instruments_used))
    print("Tests      :", len(spec.tests))
    print()

    if bench_path:
        config = load_bench(bench_path)
        simulate = False
    else:
        # No bench file: stand every instrument the suite needs up as a simulator.
        config = BenchConfig.simulated(spec.instruments_used)
        simulate = True

    with BenchRunner.from_config(config, simulate=simulate) as runner:
        run = runner.run(spec)

    print(summary_line(run))
    print()
    for case in run.cases:
        print("  %-7s %s" % (case.status.value, case.name))
        for measurement in case.measurements:
            print("            %-22s %-12s limit %s  %s" % (
                measurement.name,
                "%.6g %s" % (measurement.value, measurement.unit)
                if measurement.value is not None else "-",
                measurement.limit or "-",
                measurement.status.value,
            ))

    print()
    print("Requirements verified:")
    for requirement, status in run.requirements_verified.items():
        print("  %-14s %s" % (requirement, status))

    report = os.path.join(os.getcwd(), "bench_report.md")
    with open(report, "w", encoding="utf-8") as handle:
        handle.write(format_markdown(run))
    print("\nReport:", report)

    # Exit status mirrors the CLI, so this composes into a pipeline.
    return 1 if run.status.is_problem else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
