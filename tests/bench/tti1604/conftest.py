"""Fixtures for exercising a real TTi 1604.

Nothing here runs unless it is asked for twice: the directory is excluded from
the default collection (``norecursedirs`` in ``pyproject.toml``), and the
tests skip unless ``BENCHTOOLS_TTI1604`` names the meter's port. See
``README.md`` beside this file for the wiring and the variables.

``BENCHTOOLS_TTI1604=sim://`` runs the same tests against the simulator, with
the reference values applied to its input. That is a dry run of this file, not
evidence about a meter, and the findings record says so.

Traces to: SWE4-UT-DMMBENCH.
"""

from __future__ import annotations

import datetime
import os
import pathlib
from typing import Dict, List, Optional, Tuple

import pytest

from benchtools.instruments.tti1604 import Tti1604

#: Environment variables the bench tests read.
RESOURCE = "BENCHTOOLS_TTI1604"
DC_VOLTS = "BENCHTOOLS_TTI1604_DCV"
OHMS = "BENCHTOOLS_TTI1604_OHMS"
DC_AMPS = "BENCHTOOLS_TTI1604_DCI"
HERTZ = "BENCHTOOLS_TTI1604_HZ"
TOLERANCE = "BENCHTOOLS_TTI1604_TOLERANCE"
REPORT = "BENCHTOOLS_TTI1604_REPORT"

DEFAULT_REPORT = "tti1604_bench_findings.md"


def reference(name: str) -> Optional[float]:
    """A reference value from the environment, or ``None`` if not wired."""
    text = os.environ.get(name, "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        raise pytest.UsageError("%s must be a number, got %r" % (name, text))


class Findings:
    """What the bench showed, written out as a markdown record at the end.

    Assertions say whether the driver works; findings say what the meter did,
    which is what the bench confirmation items (DMM-OPEN-nn) need.
    """

    def __init__(self, resource: str) -> None:
        self.resource = resource
        self.rows: List[Tuple[str, str, str]] = []

    def record(self, item: str, observation: str, bears_on: str = "") -> None:
        self.rows.append((item, observation, bears_on))

    def write(self, path: pathlib.Path, outcomes: Dict[str, str]) -> None:
        simulated = self.resource.lower().startswith(("sim", "mock"))
        lines = [
            "# TTi 1604 — Bench Findings",
            "",
            "| Field | Value |",
            "|---|---|",
            "| Date | %s |" % datetime.datetime.now().isoformat(timespec="seconds"),
            "| Resource | `%s` |" % self.resource,
            "| Kind of run | %s |" % ("**Dry run against the simulator - not "
                                        "evidence about a meter**" if simulated
                                        else "Real instrument"),
            "| References | %s |" % (", ".join(
                "%s=%s" % (name, os.environ[name])
                for name in (DC_VOLTS, OHMS, DC_AMPS, HERTZ, TOLERANCE)
                if os.environ.get(name)) or "none"),
            "",
            "## Test outcomes",
            "",
            "| Test | Outcome |",
            "|---|---|",
        ]
        lines += ["| `%s` | %s |" % (name, outcome) for name, outcome in outcomes.items()]
        lines += ["", "## Observations", "", "| Item | Observation | Bears on |",
                  "|---|---|---|"]
        lines += ["| %s | %s | %s |" % row for row in self.rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_OUTCOMES: Dict[str, str] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        text = report.outcome
        if report.skipped and isinstance(report.longrepr, tuple):
            text = "skipped: %s" % report.longrepr[2].replace("Skipped: ", "")
        _OUTCOMES[item.name] = text


@pytest.fixture(scope="session")
def resource() -> str:
    value = os.environ.get(RESOURCE, "").strip()
    if not value:
        pytest.skip("no meter named: set %s to its port (/dev/ttyUSB1, COM6), "
                    "or to sim:// for a dry run" % RESOURCE)
    return value


@pytest.fixture(scope="session")
def tolerance() -> float:
    """Relative tolerance for comparing against a reference: 1% by default."""
    value = reference(TOLERANCE)
    return 0.01 if value is None else value


@pytest.fixture(scope="session")
def findings(resource):
    record = Findings(resource)
    yield record
    path = pathlib.Path(os.environ.get(REPORT) or DEFAULT_REPORT)
    record.write(path, _OUTCOMES)
    print("\nbench findings written to %s" % path.resolve())


@pytest.fixture(scope="session")
def meter(resource) -> Tti1604:
    """The meter, connected once for the session and handed back at the end."""
    dmm = Tti1604.connect(resource)
    simulator = getattr(dmm.transport, "simulator", None)
    if simulator is not None:
        # A dry run: put the references on the simulated input, so that the
        # comparisons below are exercised rather than skipped.
        for name, quantity in ((DC_VOLTS, "dc_volts"), (OHMS, "ohms"),
                               (DC_AMPS, "dc_amps"), (HERTZ, "frequency")):
            value = reference(name)
            if value is not None:
                simulator.set_input(quantity, value)
        if reference(HERTZ) is not None:
            simulator.set_input("ac_volts", 1.0)
    yield dmm
    dmm.close()
