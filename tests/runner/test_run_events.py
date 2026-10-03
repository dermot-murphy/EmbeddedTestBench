"""Structured run, test case and step records in the event log (#135).

Traces to: CORE-FR-064, RUN-FR-060, SWE4-UT-RUNEVENTS.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import logging

import pytest

from benchtools.core.events import EventTail, MAX_ITEMS, jsonable, log_event, start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.runner import NOT_SELECTED
from benchtools.runner.spec import TestSpec

SLEEP = {"do": "sleep", "with": {"seconds": 0}}


def _spec() -> TestSpec:
    return TestSpec.from_mapping({
        "name": "events",
        "setup": [SLEEP],
        "teardown": [SLEEP],
        "tests": [
            {"name": "first", "requirement": "REQ-1", "steps": [
                dict(SLEEP, save="waited"),
                {"do": "sleep", "with": {"seconds": {"from": "waited"}},
                 "expect": {"name": "slept", "max": 1.0}},
            ]},
            {"name": "second", "steps": [{"do": "no_such_action"}]},
            {"name": "third", "steps": [SLEEP]},
        ],
    })


def _records(tmp_path, selection=(), spec=None):
    path = str(tmp_path / "events.jsonl")
    handler = start_event_log(path)
    try:
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            run = runner.run(spec or _spec(), selection)
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    return run, [record for record in EventTail(path).read() if "kind" in record]


class TestKinds:
    def test_the_sequence_of_kinds(self, tmp_path):
        _run, records = _records(tmp_path)
        kinds = [record["kind"] for record in records]
        assert kinds[0] == "run_start"
        assert kinds[-1] == "run_end"
        assert kinds.count("case_start") == 3
        assert kinds.count("case_end") == 3
        # setup 1, first 2, second 1 (errors), third 1, teardown 1
        assert kinds.count("step_start") == kinds.count("step_end") == 6

    def test_every_structured_record_is_from_the_runner_and_keeps_its_text(self, tmp_path):
        _run, records = _records(tmp_path)
        for record in records:
            assert record["source"] == "TEST"
            assert record["text"]
            assert isinstance(record["data"], dict)

    def test_every_line_is_standard_json(self, tmp_path):
        _records(tmp_path)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines():
            json.loads(line, parse_constant=pytest.fail)


class TestRebuildingTheRun:
    def test_run_start_carries_the_whole_plan(self, tmp_path):
        _run, records = _records(tmp_path)
        plan = records[0]["data"]
        assert plan["suite"] == "events"
        assert plan["simulated"] is True
        assert [test["name"] for test in plan["tests"]] == ["first", "second", "third"]
        assert [step["action"] for step in plan["tests"][0]["steps"]] == ["sleep", "sleep"]
        assert plan["tests"][0]["steps"][0]["save"] == "waited"
        assert len(plan["setup"]) == len(plan["teardown"]) == 1

    def test_the_tree_and_every_result_can_be_rebuilt(self, tmp_path):
        run, records = _records(tmp_path)
        tree = {}
        for record in records:
            data = record["data"]
            if record["kind"] == "case_end":
                tree[data["case"]] = {"name": data["name"], "status": data["status"], "steps": {}}
        for record in records:
            data = record["data"]
            if record["kind"] == "step_end" and data["phase"] == "test":
                tree[data["case"]]["steps"][data["step"]] = data["status"]
        assert [tree[i]["name"] for i in sorted(tree)] == [case.name for case in run.cases]
        assert [tree[i]["status"] for i in sorted(tree)] == [
            case.status.value for case in run.cases]
        for index, case in enumerate(run.cases):
            assert [tree[index]["steps"][i] for i in sorted(tree[index]["steps"])] == [
                step.status.value for step in case.steps]

    def test_step_end_carries_resolved_arguments_result_and_measurements(self, tmp_path):
        _run, records = _records(tmp_path)
        ends = [r["data"] for r in records if r["kind"] == "step_end"
                and r["data"]["phase"] == "test" and r["data"]["case"] == 0]
        assert ends[0]["save"] == "waited"
        assert ends[1]["arguments"] == {"seconds": 0.0}
        assert ends[1]["result"] == 0.0
        assert ends[1]["measurements"][0]["name"] == "slept"
        assert ends[1]["measurements"][0]["status"] == "PASS"

    def test_an_erroring_step_carries_its_error_and_no_save(self, tmp_path):
        _run, records = _records(tmp_path)
        end = next(r["data"] for r in records if r["kind"] == "step_end"
                   and r["data"]["case"] == 1)
        assert end["status"] == "ERROR"
        assert "no_such_action" in end["error"]
        assert end["save"] is None

    def test_setup_and_teardown_steps_are_marked(self, tmp_path):
        _run, records = _records(tmp_path)
        phases = [r["data"]["phase"] for r in records if r["kind"] == "step_end"]
        assert phases[0] == "setup"
        assert phases[-1] == "teardown"
        assert all(r["data"]["case"] is None for r in records
                   if r["kind"] == "step_end" and r["data"]["phase"] != "test")

    def test_run_end_carries_the_verdict(self, tmp_path):
        run, records = _records(tmp_path)
        end = records[-1]["data"]
        assert end["status"] == run.status.value == "ERROR"
        assert end["totals"] == {"total": 3, "passed": 2, "failed": 0,
                                 "errored": 1, "skipped": 0}

    def test_a_test_case_not_selected_has_an_end_and_no_start(self, tmp_path):
        _run, records = _records(tmp_path, selection=["third"])
        starts = [r["data"]["name"] for r in records if r["kind"] == "case_start"]
        ends = {r["data"]["name"]: r["data"] for r in records if r["kind"] == "case_end"}
        assert starts == ["third"]
        assert ends["first"]["skip_reason"] == NOT_SELECTED
        assert records[0]["data"]["selection"] == ["third"]
        assert [t["selected"] for t in records[0]["data"]["tests"]] == [False, False, True]

    def test_a_refused_bench_still_starts_and_ends_the_run(self, tmp_path):
        spec = TestSpec.from_mapping({"name": "x", "tests": [
            {"name": "t", "steps": [{"do": "missing.read"}]}]})
        run, records = _records(tmp_path, spec=spec)
        assert run.setup_error
        assert [r["kind"] for r in records] == ["run_start", "run_end"]
        assert records[-1]["data"]["setup_error"] == run.setup_error


class _Colour(enum.Enum):
    RED = "red"


@dataclasses.dataclass
class _Reading:
    volts: float
    raw: bytes


class TestJsonable:
    @pytest.mark.parametrize("value", [None, True, 3, 2.5, "text"])
    def test_plain_values_pass_through(self, value):
        assert jsonable(value) == value

    def test_a_float_that_is_not_finite_becomes_text(self):
        assert jsonable(float("nan")) == "nan"
        assert jsonable(float("inf")) == "inf"

    def test_containers_dataclasses_bytes_and_enums(self):
        value = {"r": _Reading(3.3, b"\x01\xff"), "c": _Colour.RED, 1: (1, 2)}
        assert jsonable(value) == {"r": {"volts": 3.3, "raw": "01ff"}, "c": "red",
                                   "1": [1, 2]}

    def test_a_long_sequence_is_cut_short_and_says_so(self):
        converted = jsonable(list(range(MAX_ITEMS + 10)))
        assert len(converted) == MAX_ITEMS + 1
        assert converted[-1] == "... 10 more"

    def test_anything_else_is_its_repr(self):
        assert jsonable(object).startswith("<class")

    def test_log_event_without_the_event_log_is_ordinary_text(self, caplog):
        logger = logging.getLogger("benchtools.test")
        with caplog.at_level(logging.INFO, logger="benchtools.test"):
            log_event(logger, "thing", "50% done", {"x": 1})
        assert caplog.records[-1].getMessage() == "50% done"
