"""Report writers.

Traces to: RUN-FR-040 .. RUN-FR-043, SWE4-UT-REPORT.
"""

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ElementTree

import pytest

from benchtools.runner import BenchConfig, BenchRunner, Status, TestSpec
from benchtools.runner.report import (
    format_markdown,
    summary_line,
    write_json,
    write_junit,
    write_markdown,
)

SPEC = {
    "name": "Mixed suite",
    "requirements": ["R1", "R2"],
    "tests": [
        {"name": "passes", "requirement": "R1", "steps": [
            {"do": "scope.measure_period", "with": {"channel": 1},
             "expect": [{"name": "period", "scale": 1e6, "display_unit": "us",
                         "nominal": 1.0, "tolerance_percent": 1.0}]}]},
        {"name": "fails", "requirement": "R2", "steps": [
            {"do": "scope.measure_period", "with": {"channel": 1},
             "expect": [{"name": "tight", "max": 1e-12}]}]},
        {"name": "errors", "requirement": "R2", "steps": [{"do": "scope.levitate"}]},
        {"name": "skipped", "requirement": "R1", "skip": True,
         "skip_reason": "fixture absent", "steps": [{"do": "scope.identity"}]},
    ],
}


@pytest.fixture(scope="module")
def run():
    spec = TestSpec.from_mapping(SPEC, source="<test>")
    config = BenchConfig.simulated(["scope"])
    with BenchRunner.from_config(config) as runner:
        return runner.run(spec)


class TestSummary:
    def test_counts(self, run):
        assert run.total == 4
        assert (run.passed, run.failed, run.errored, run.skipped) == (1, 1, 1, 1)

    def test_worst_status_wins(self, run):
        assert run.status is Status.ERROR

    def test_summary_line(self, run):
        line = summary_line(run)
        assert "Mixed suite" in line and "1 passed" in line and "1 errored" in line


class TestJson:
    def test_round_trips(self, run, tmp_path):
        path = write_json(run, str(tmp_path / "r.json"))
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["status"] == "ERROR"
        assert data["totals"] == {"total": 4, "passed": 1, "failed": 1,
                                  "errored": 1, "skipped": 1}
        # R1 is covered by one passing and one skipped test, so it is reported
        # as SKIP: a requirement with an unrun test is not fully verified.
        assert data["requirements_verified"] == {"R1": "SKIP", "R2": "ERROR"}
        assert len(data["cases"]) == 4

    def test_measurements_are_included(self, run, tmp_path):
        path = write_json(run, str(tmp_path / "r.json"))
        data = json.loads(open(path, encoding="utf-8").read())
        passing = next(case for case in data["cases"] if case["name"] == "passes")
        assert passing["steps"][0]["measurements"][0]["name"] == "period"

    def test_nested_directories_are_created(self, run, tmp_path):
        path = write_json(run, str(tmp_path / "deep" / "nested" / "r.json"))
        assert open(path, encoding="utf-8").read()


class TestMarkdown:
    def test_leads_with_the_verdict(self, run):
        text = format_markdown(run)
        assert text.startswith("# Bench test report: Mixed suite")
        assert "| Result | **ERROR** |" in text

    def test_requirements_table(self, run):
        text = format_markdown(run)
        assert "## Requirements verified" in text
        assert "| R2 | **ERROR** |" in text
        assert "| R1 | skip |" in text

    def test_problems_section_names_the_reason(self, run):
        text = format_markdown(run)
        assert "## Problems" in text
        assert "above the maximum" in text

    def test_simulation_is_disclosed(self, run):
        assert "not** any physical hardware" in format_markdown(run)

    def test_skip_reason_is_shown(self, run):
        assert "fixture absent" in format_markdown(run)

    def test_all_tests_are_listed(self, run):
        text = format_markdown(run)
        for name in ("passes", "fails", "errors", "skipped"):
            assert "### %s" % name in text

    def test_file_is_written(self, run, tmp_path):
        path = write_markdown(run, str(tmp_path / "r.md"))
        assert open(path, encoding="utf-8").read().startswith("# Bench test report")

    def test_setup_failure_report_is_explicit(self, tmp_path):
        spec = TestSpec.from_mapping({
            "name": "S",
            "setup": [{"do": "scope.configure_channel", "with": {"channel": 99}}],
            "tests": [{"name": "T", "steps": [{"do": "scope.identity"}]}],
        })
        config = BenchConfig.simulated(["scope"])
        with BenchRunner.from_config(config) as runner:
            failed = runner.run(spec)
        text = format_markdown(failed)
        assert "## Suite setup failed" in text
        assert "No test was run" in text


class TestJunit:
    def test_counts_and_elements(self, run, tmp_path):
        path = write_junit(run, str(tmp_path / "r.xml"))
        root = ElementTree.parse(path).getroot()
        assert root.tag == "testsuite"
        assert root.attrib["tests"] == "4"
        assert root.attrib["failures"] == "1"
        assert root.attrib["errors"] == "1"
        assert root.attrib["skipped"] == "1"

    def test_failure_and_error_are_distinct_elements(self, run, tmp_path):
        """CI trends a broken rig differently from a product defect."""
        path = write_junit(run, str(tmp_path / "r.xml"))
        root = ElementTree.parse(path).getroot()
        cases = {case.attrib["name"]: case for case in root.findall("testcase")}
        assert cases["fails"].find("failure") is not None
        assert cases["fails"].find("error") is None
        assert cases["errors"].find("error") is not None
        assert cases["errors"].find("failure") is None
        assert cases["skipped"].find("skipped") is not None

    def test_requirement_is_the_classname(self, run, tmp_path):
        path = write_junit(run, str(tmp_path / "r.xml"))
        root = ElementTree.parse(path).getroot()
        cases = {case.attrib["name"]: case for case in root.findall("testcase")}
        assert cases["passes"].attrib["classname"].endswith("R1")

    def test_properties_record_the_bench(self, run, tmp_path):
        path = write_junit(run, str(tmp_path / "r.xml"))
        root = ElementTree.parse(path).getroot()
        properties = {
            item.attrib["name"]: item.attrib["value"]
            for item in root.find("properties").findall("property")
        }
        # Every resource on this bench is sim://, so the run is disclosed as
        # simulated even though --simulate was not passed.
        assert properties["simulated"] == "true"
        assert properties["bench"] == "simulated bench"

    def test_failure_detail_carries_the_measurement(self, run, tmp_path):
        path = write_junit(run, str(tmp_path / "r.xml"))
        root = ElementTree.parse(path).getroot()
        cases = {case.attrib["name"]: case for case in root.findall("testcase")}
        assert "tight" in cases["fails"].find("failure").text

    def test_setup_error_appears_as_a_case(self, tmp_path):
        spec = TestSpec.from_mapping({
            "name": "S",
            "setup": [{"do": "scope.configure_channel", "with": {"channel": 99}}],
            "tests": [{"name": "T", "steps": [{"do": "scope.identity"}]}],
        })
        config = BenchConfig.simulated(["scope"])
        with BenchRunner.from_config(config) as runner:
            failed = runner.run(spec)
        path = write_junit(failed, str(tmp_path / "r.xml"))
        root = ElementTree.parse(path).getroot()
        assert root.find("testcase").find("error") is not None


class TestInstrumentsSection:
    """Which instruments produced the numbers, and what they were running.

    Traces to: RUN-FR-037, RUN-FR-041, RUN-DD-REPORT.
    """

    @pytest.fixture(scope="class")
    def dongle_run(self):
        spec = TestSpec.from_mapping({
            "name": "Identity suite",
            "tests": [{"name": "reads its build", "steps": [
                {"do": "dongle.firmware_version"}]}],
        }, source="<test>")
        config = BenchConfig.from_mapping({
            "name": "B", "instruments": {"dongle": "ble-dongle@sim://"},
        })
        with BenchRunner.from_config(config) as runner:
            return runner.run(spec)

    def test_the_table_names_the_instrument_and_its_build(self, dongle_run):
        text = format_markdown(dongle_run)
        assert "## Instruments" in text
        assert "| dongle |" in text
        assert "NordicDongle" in text
        assert dongle_run.instruments["dongle"]["firmware"] in text

    def test_json_carries_the_same_facts(self, dongle_run, tmp_path):
        path = write_json(dongle_run, str(tmp_path / "r.json"))
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["instruments"]["dongle"]["driver"] == "NordicDongle"

    def test_an_instrument_that_would_not_identify_is_shown_as_such(self, run):
        run = copy.copy(run)          # the fixture is shared; do not disturb it
        run.instruments = {
            "scope": {"driver": "Tek3014B", "resource": "usb://",
                      "identity_error": "no answer to *IDN?"},
        }
        text = format_markdown(run)
        assert "no answer to *IDN?" in text

    def test_a_run_with_no_instruments_omits_the_section(self, run):
        run = copy.copy(run)
        run.instruments = {}
        assert "## Instruments" not in format_markdown(run)
