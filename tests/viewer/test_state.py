"""The viewer's run state, rebuilt from event records (#137).

Traces to: VIEW-FR-003, VIEW-FR-004, SWE4-UT-VIEWSTATE.
"""

from __future__ import annotations

import logging

from benchtools.core.events import EventTail, start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.spec import TestSpec
from benchtools.viewer.state import NOT_SELECTED, PENDING, RUNNING, RunState, describe_step

SLEEP = {"do": "sleep", "with": {"seconds": 0}}


def _spec() -> TestSpec:
    return TestSpec.from_mapping({
        "name": "viewer",
        "setup": [SLEEP],
        "teardown": [SLEEP],
        "tests": [
            {"name": "a", "requirement": "R-1", "steps": [dict(SLEEP, save="w"), SLEEP]},
            {"name": "b", "steps": [{"do": "nope"}]},
            {"name": "c", "steps": [SLEEP]},
        ],
    })


def _log(tmp_path, selection=()):
    path = str(tmp_path / "events.jsonl")
    handler = start_event_log(path)
    try:
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            run = runner.run(_spec(), selection)
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    return run, EventTail(path).read()


def _state(records):
    state = RunState()
    for record in records:
        state.apply(record)
    return state


class TestDescribeStep:
    def test_instrument_method_and_arguments_in_words(self):
        assert describe_step("psu.set_voltage", {"channel": 2, "volts": 3.3}) == \
            "PSU set voltage: channel 2, volts 3.3"

    def test_a_builtin_action(self):
        assert describe_step("sleep", {"seconds": 0.5}) == "sleep: seconds 0.5"

    def test_a_reference_shows_the_saved_name(self):
        assert describe_step("dongle.scan", {"name": {"path": "sensor_id", "format": ""}}) \
            == "DONGLE scan: name <sensor_id>"

    def test_the_specification_s_description_wins(self):
        assert describe_step("psu.output", {"on": True}, "Power the board") == "Power the board"


class TestRebuild:
    def test_the_whole_tree_matches_the_run(self, tmp_path):
        run, records = _log(tmp_path)
        state = _state(records)
        assert state.suite == "viewer"
        assert state.status == run.status.value == "ERROR"
        assert [case["status"] for case in state.cases] == [c.status.value for c in run.cases]
        assert [s["status"] for s in state.cases[0]["steps"]] == ["PASS", "PASS"]
        assert state.cases[1]["steps"][0]["error"]
        assert state.setup[0]["status"] == state.teardown[0]["status"] == "PASS"
        assert state.verdict["totals"]["errored"] == 1
        assert state.position == {"phase": None, "case": None, "step": None}

    def test_steps_are_described_and_saved_values_kept(self, tmp_path):
        _run, records = _log(tmp_path)
        step = _state(records).cases[0]["steps"][0]
        assert step["text"] == "sleep: seconds 0"
        assert step["save"] == "w"
        assert step["result"] == 0.0

    def test_test_cases_not_selected_are_shown_as_such(self, tmp_path):
        _run, records = _log(tmp_path, selection=["c"])
        state = _state(records)
        assert [case["status"] for case in state.cases[:2]] == ["SKIP", "SKIP"]
        partial = _state([r for r in records if r.get("kind") == "run_start"])
        assert [case["status"] for case in partial.cases] == [
            NOT_SELECTED, NOT_SELECTED, PENDING]

    def test_part_way_through_a_run(self, tmp_path):
        _run, records = _log(tmp_path)
        cut = next(i for i, r in enumerate(records) if r.get("kind") == "step_start"
                   and r["data"].get("case") == 0 and r["data"]["step"] == 1)
        state = _state(records[:cut + 1])
        assert state.status == RUNNING
        assert state.cases[0]["status"] == RUNNING
        assert [s["status"] for s in state.cases[0]["steps"]] == ["PASS", RUNNING]
        assert state.cases[2]["status"] == PENDING
        assert state.position == {"phase": "test", "case": 0, "step": 1}

    def test_a_second_run_in_the_same_log_starts_afresh(self, tmp_path):
        _run, records = _log(tmp_path)
        state = _state(records + records[:1])
        assert state.runs == 2
        assert state.status == RUNNING
        assert all(case["status"] == PENDING for case in state.cases)

    def test_records_without_a_kind_change_nothing(self):
        state = RunState()
        assert state.apply({"source": "PSU", "text": ">> VSET1:3.3"}) is False
        assert state.status == "WAITING"


class TestControlRecords:
    def test_the_control_port_is_taken_from_the_log(self):
        state = RunState()
        state.apply({"kind": "control_listening", "data": {"port": 5555}})
        state.apply({"kind": "run_start", "data": {"suite": "x"}})
        assert state.control_port == 5555

    def test_pause_resume_and_refusals(self):
        state = RunState()
        state.apply({"kind": "control_applied", "data": {"command": "pause", "phase": "test",
                                                          "case": 0, "step": 1}})
        assert state.paused
        assert state.position == {"phase": "test", "case": 0, "step": 1}
        state.apply({"kind": "control_applied", "data": {"command": "resume"}})
        assert not state.paused
        state.apply({"kind": "control", "data": {"command": "abort", "accepted": False,
                                                  "reason": "teardown"}, "t": 1.0})
        assert state.last_control["reason"] == "teardown"

    def test_a_restart_returns_later_test_cases_to_pending(self, tmp_path):
        _run, records = _log(tmp_path)
        state = _state(records[:-1])
        state.apply({"kind": "control_applied", "data": {
            "command": "restart_from", "target_case": 0, "target_step": 1}})
        assert [case["status"] for case in state.cases[1:]] == [PENDING, PENDING]
        assert state.cases[1]["steps"][0]["error"] == ""
        state.apply({"kind": "case_start", "data": {"case": 0, "first_step": 1}})
        assert [s["status"] for s in state.cases[0]["steps"]] == ["PASS", PENDING]

    def test_the_snapshot_is_a_copy(self, tmp_path):
        _run, records = _log(tmp_path)
        state = _state(records)
        snapshot = state.snapshot()
        snapshot["cases"][0]["name"] = "changed"
        assert state.cases[0]["name"] == "a"
