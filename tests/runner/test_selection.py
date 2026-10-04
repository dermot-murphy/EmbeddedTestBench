"""Running a selected subset of a specification's test cases (#134).

Traces to: RUN-FR-059, SWE4-UT-SELECT.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.cli import main
from benchtools.runner.report import format_markdown, write_junit
from benchtools.runner.results import Status
from benchtools.runner.runner import NOT_SELECTED, check_selection
from benchtools.runner.spec import TestSpec

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = str(ROOT / "specs" / "clock_skew.yaml")
RISING = "Rising-edge skew across the four clock loads"
PERIOD = "Clock period within 1 percent of 1 us"


def _spec(*names, setup=(), teardown=()) -> TestSpec:
    return TestSpec.from_mapping({
        "name": "selection",
        "setup": list(setup),
        "teardown": list(teardown),
        "tests": [
            {"name": name, "steps": [{"do": "sleep", "with": {"seconds": 0}}]}
            for name in names
        ],
    })


def _run(spec, selection=()):
    with BenchRunner.from_config(BenchConfig.simulated(spec.instruments_used),
                                 simulate=True) as runner:
        return runner.run(spec, selection)


class TestRunner:
    def test_no_selection_runs_every_test_case(self):
        run = _run(_spec("a", "b"))
        assert [case.status for case in run.cases] == [Status.PASS, Status.PASS]
        assert run.selection == ()

    def test_only_the_selected_test_case_runs(self):
        run = _run(_spec("a", "b", "c"), ["b"])
        assert [(case.name, case.status) for case in run.cases] == [
            ("a", Status.SKIP), ("b", Status.PASS), ("c", Status.SKIP)]
        assert run.cases[0].skip_reason == NOT_SELECTED
        assert run.cases[0].steps == []
        assert run.status is Status.PASS

    def test_order_follows_the_specification_not_the_selection(self):
        run = _run(_spec("a", "b", "c"), ["c", "a"])
        assert [case.name for case in run.cases if case.status is Status.PASS] == ["a", "c"]

    def test_setup_and_teardown_still_run(self, caplog):
        spec = _spec("a", "b",
                     setup=[{"do": "sleep", "with": {"seconds": 0}}],
                     teardown=[{"do": "sleep", "with": {"seconds": 0}}])
        with caplog.at_level("INFO", logger="benchtools.runner"):
            _run(spec, ["b"])
        assert "running suite setup" in caplog.text
        assert "running suite teardown" in caplog.text

    def test_the_selection_is_in_the_record(self):
        run = _run(_spec("a", "b"), ["b"])
        record = run.as_dict()
        assert record["selection"] == ["b"]
        assert record["cases"][0]["skip_reason"] == NOT_SELECTED


class TestCheckSelection:
    def test_known_names_are_accepted(self):
        check_selection([_spec("a", "b")], ["b"])

    def test_an_unknown_name_is_refused_naming_it_and_the_known_ones(self):
        with pytest.raises(SpecError) as caught:
            check_selection([_spec("a", "b")], ["x"])
        assert "'x'" in str(caught.value)
        assert "'a', 'b'" in str(caught.value)

    def test_a_name_in_any_of_several_specifications_is_accepted(self):
        check_selection([_spec("a"), _spec("b")], ["b"])


class TestReports:
    def test_markdown_states_the_selection(self):
        text = format_markdown(_run(_spec("a", "b"), ["b"]))
        assert "| Selected tests | b |" in text
        assert NOT_SELECTED in text

    def test_markdown_without_a_selection_has_no_row(self):
        assert "Selected tests" not in format_markdown(_run(_spec("a")))

    def test_junit_records_the_selection_and_the_skip(self, tmp_path):
        path = write_junit(_run(_spec("a", "b"), ["b"]), str(tmp_path / "r.xml"))
        text = pathlib.Path(path).read_text(encoding="utf-8")
        assert 'name="selected test" value="b"' in text
        assert 'message="%s"' % NOT_SELECTED in text


class TestCommandLine:
    @pytest.fixture(autouse=True)
    def _yaml(self):
        pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

    def test_selected_test_runs_and_others_are_not_selected(self, tmp_path):
        out = tmp_path / "r.json"
        assert main([SPEC, "--simulate", "--test", PERIOD, "--json", str(out)]) == 0
        record = json.loads(out.read_text())
        assert record["selection"] == [PERIOD]
        statuses = {case["name"]: case["status"] for case in record["cases"]}
        assert statuses[PERIOD] == "PASS"
        assert statuses[RISING] == "SKIP"

    def test_repeated_option_selects_several(self, tmp_path):
        out = tmp_path / "r.json"
        assert main([SPEC, "--simulate", "--test", PERIOD, "--test", RISING,
                     "--json", str(out)]) == 0
        assert json.loads(out.read_text())["totals"]["passed"] == 2

    def test_an_unknown_name_is_a_usage_error_before_the_bench_opens(self, capsys):
        assert main([SPEC, "--simulate", "--test", "No such test"]) == 2
        err = capsys.readouterr().err
        assert "'No such test'" in err
        assert PERIOD in err
