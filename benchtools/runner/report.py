"""Report writers.

Three formats, for three audiences:

``JSON``
    For a downstream tool. Lossless: everything in the result records.
``Markdown``
    For a person, and for attaching to a test report as evidence. Leads with the
    verdict, then the requirements verified, then per-test measurements.
``JUnit XML``
    For CI. A failure and an error are distinct elements, so a broken rig does
    not read as a product defect.

Writers only read :mod:`benchtools.runner.results`, so adding a format needs no
change to the execution engine.

Traces to: RUN-FR-040 .. RUN-FR-043, RUN-DD-REPORT.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ElementTree
from typing import List, Optional

from .results import CaseRecord, RunRecord, Status

__all__ = ["write_json", "write_markdown", "write_junit", "format_markdown", "summary_line"]

#: Marker shown against each outcome in the markdown report.
_MARKS = {
    Status.PASS: "PASS",
    Status.FAIL: "**FAIL**",
    Status.ERROR: "**ERROR**",
    Status.SKIP: "skip",
}


def _ensure_parent(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


def _format_value(value: Optional[float], unit: str) -> str:
    if value is None:
        return "-"
    return "%.6g%s" % (value, (" " + unit) if unit else "")


def summary_line(run: RunRecord) -> str:
    """One-line summary, for a console or a commit status."""
    return "%s: %s - %d passed, %d failed, %d errored, %d skipped in %.2f s" % (
        run.suite,
        run.status.value,
        run.passed,
        run.failed,
        run.errored,
        run.skipped,
        run.duration_s,
    )


# ---------------------------------------------------------------------------
def write_json(run: RunRecord, path: str) -> str:
    """Write the complete result record as JSON."""
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(run.as_dict(), handle, indent=2, sort_keys=False)
        handle.write("\n")
    return path


# ---------------------------------------------------------------------------
def format_markdown(run: RunRecord) -> str:
    """Render the run as a markdown report."""
    out: List[str] = []
    out.append("# Bench test report: %s" % run.suite)
    out.append("")
    out.append("| Field | Value |")
    out.append("|---|---|")
    out.append("| Result | **%s** |" % run.status.value)
    out.append("| Bench | %s%s |" % (run.bench, " (simulated)" if run.simulated else ""))
    out.append("| Specification | %s |" % (run.spec_source or "-"))
    out.append("| Started | %s |" % run.started)
    out.append("| Duration | %.2f s |" % run.duration_s)
    out.append("| Tests | %d passed, %d failed, %d errored, %d skipped (of %d) |" % (
        run.passed, run.failed, run.errored, run.skipped, run.total))
    out.append("")

    if run.simulated:
        out.append("> Run against simulated instruments. These results verify the "
                   "specification and the tooling, **not** any physical hardware.")
        out.append("")

    if run.setup_error:
        out.append("## Suite setup failed")
        out.append("")
        out.append("```")
        out.append(run.setup_error)
        out.append("```")
        out.append("")
        out.append("No test was run: every measurement after an unknown setup would be "
                   "meaningless.")
        out.append("")
        return "\n".join(out) + "\n"

    verified = run.requirements_verified
    if verified:
        out.append("## Requirements verified")
        out.append("")
        out.append("| Requirement | Result |")
        out.append("|---|---|")
        for requirement, status in verified.items():
            out.append("| %s | %s |" % (requirement, _MARKS[Status(status)]))
        out.append("")

    problems = [case for case in run.cases if case.status.is_problem]
    if problems:
        out.append("## Problems")
        out.append("")
        for case in problems:
            out.append("### %s - %s" % (case.name, case.status.value))
            out.append("")
            if case.error:
                out.append("Could not be executed: `%s`" % case.error)
                out.append("")
            for measurement in case.measurements:
                if measurement.status.is_problem:
                    out.append("- `%s` = %s, limit %s - %s" % (
                        measurement.name,
                        _format_value(measurement.value, measurement.unit),
                        measurement.limit or "-",
                        measurement.reason,
                    ))
            out.append("")

    out.append("## All tests")
    out.append("")
    for case in run.cases:
        out.append("### %s" % case.name)
        out.append("")
        details = ["Result: **%s**" % case.status.value]
        if case.requirement:
            details.append("Requirement: %s" % case.requirement)
        details.append("Duration: %.3f s" % case.duration_s)
        out.append(" | ".join(details))
        out.append("")
        if case.skip_reason:
            out.append("Skipped: %s" % case.skip_reason)
            out.append("")
        if case.measurements:
            out.append("| Measurement | Value | Limit | Result |")
            out.append("|---|---|---|---|")
            for measurement in case.measurements:
                out.append("| %s | %s | %s | %s |" % (
                    measurement.name,
                    _format_value(measurement.value, measurement.unit),
                    measurement.limit or "-",
                    _MARKS[measurement.status],
                ))
            out.append("")
        elif case.error:
            out.append("```")
            out.append(case.error)
            out.append("```")
            out.append("")
    return "\n".join(out) + "\n"


def write_markdown(run: RunRecord, path: str) -> str:
    """Write a markdown report."""
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(format_markdown(run))
    return path


# ---------------------------------------------------------------------------
def write_junit(run: RunRecord, path: str) -> str:
    """Write a JUnit XML report, for CI.

    A measurement outside its limit becomes ``<failure>``; a step that could not
    execute becomes ``<error>``. Most CI systems render and trend these
    differently, which is the distinction worth preserving.
    """
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": run.suite,
            "tests": str(run.total),
            "failures": str(run.failed),
            "errors": str(run.errored),
            "skipped": str(run.skipped),
            "time": "%.3f" % run.duration_s,
            "timestamp": run.started,
        },
    )
    properties = ElementTree.SubElement(suite, "properties")
    for name, value in (
        ("bench", run.bench),
        ("simulated", str(run.simulated).lower()),
        ("specification", run.spec_source or ""),
    ):
        ElementTree.SubElement(properties, "property", {"name": name, "value": value})

    if run.setup_error:
        case = ElementTree.SubElement(
            suite, "testcase", {"name": "suite setup", "classname": run.suite}
        )
        error = ElementTree.SubElement(
            case, "error", {"message": "suite setup failed", "type": "SetupError"}
        )
        error.text = run.setup_error

    for record in run.cases:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            {
                "name": record.name,
                "classname": "%s.%s" % (run.suite, record.requirement or "unassigned"),
                "time": "%.3f" % record.duration_s,
            },
        )
        if record.status is Status.SKIP:
            ElementTree.SubElement(case, "skipped", {"message": record.skip_reason})
        elif record.status is Status.ERROR:
            error = ElementTree.SubElement(
                case, "error", {"message": record.error or "step execution failed",
                                "type": "StepError"}
            )
            error.text = _case_detail(record)
        elif record.status is Status.FAIL:
            failures = record.failures
            message = "; ".join(
                "%s: %s" % (m.name, m.reason) for m in failures
            ) or "a measurement was out of limit"
            failure = ElementTree.SubElement(
                case, "failure", {"message": message, "type": "LimitFailure"}
            )
            failure.text = _case_detail(record)
        else:
            system_out = ElementTree.SubElement(case, "system-out")
            system_out.text = _case_detail(record)

    _ensure_parent(path)
    tree = ElementTree.ElementTree(suite)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def _case_detail(record: CaseRecord) -> str:
    """Render a case's measurements as plain text, for an XML payload."""
    lines = []
    for measurement in record.measurements:
        lines.append(
            "%s = %s [limit %s] %s%s"
            % (
                measurement.name,
                _format_value(measurement.value, measurement.unit),
                measurement.limit or "-",
                measurement.status.value,
                (" - " + measurement.reason) if measurement.reason else "",
            )
        )
    if record.error:
        lines.append("error: %s" % record.error)
    return "\n".join(lines)
