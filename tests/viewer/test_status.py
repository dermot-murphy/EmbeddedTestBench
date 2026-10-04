"""The status bar: instruments, progress and time left (#149).

Traces to: VIEW-FR-022 .. VIEW-FR-024, SWE4-UT-VIEWSTATUS.
"""

from __future__ import annotations

import logging

from benchtools.core.events import EventTail, start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.control import RunControl
from benchtools.runner.spec import TestSpec
from benchtools.viewer.server import Hub
from benchtools.viewer.state import RunState
from benchtools.viewer.status import SILENT_AFTER_S, InstrumentStatus, progress

SLEEP = {"do": "sleep", "with": {"seconds": 0}}


def _rec(source, text, t, level="DEBUG"):
    return {"source": source, "text": text, "t": t, "level": level, "logger": "x"}


class TestInstruments:
    def test_open_closed_silent_warning_and_error(self):
        links = InstrumentStatus()
        for record in (_rec("PSU", "opened simulated GPD-3303D", 1.0),
                       _rec("PSU", ">> VOUT1?", 2.0),
                       _rec("DMM", "opened COM13", 1.0),
                       _rec("DMM", "closed COM13", 3.0),
                       _rec("TEMP", ">> rd temperature", 100.0),
                       _rec("BLE", "no reply to 'ver'", 100.0, "WARNING"),
                       _rec("JLINK", "GDB server died", 100.0, "ERROR")):
            assert links.feed(record)
        states = {item["source"]: (item["state"], item["since_s"]) for item in links.view(110.0)}
        assert states == {"PSU": ("silent", 108.0), "DMM": ("closed", 107.0),
                          "TEMP": ("ok", 10.0), "BLE": ("warning", 10.0),
                          "JLINK": ("error", 10.0)}
        assert SILENT_AFTER_S < 108.0

    def test_attached_after_it_opened_is_taken_as_open(self):
        links = InstrumentStatus()
        links.feed(_rec("PSU", ">> STATUS?", 1.0))
        assert links.view(2.0)[0]["state"] == "ok"

    def test_the_runner_is_not_an_instrument(self):
        links = InstrumentStatus()
        assert not links.feed(_rec("TEST", "running 'x'", 1.0))
        assert not links.feed(dict(_rec("PSU", "x", 1.0), kind="step_end"))
        assert not links.view(2.0)


def _state(records):
    state = RunState()
    for record in records:
        state.apply(record)
    return state.snapshot()


def _run(tmp_path, spec, selection=(), control=None):
    path = str(tmp_path / "events.jsonl")
    handler = start_event_log(path)
    try:
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True,
                                     control=control) as runner:
            runner.run(spec, selection)
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    return [r for r in EventTail(path).read() if r.get("kind")]


def _spec():
    return TestSpec.from_mapping({"name": "Status", "setup": [SLEEP], "teardown": [SLEEP],
                                  "tests": [{"name": "a", "requirement": "R-1",
                                             "steps": [SLEEP, SLEEP]},
                                            {"name": "b", "steps": [{"do": "nope"}, SLEEP]},
                                            {"name": "c", "steps": [SLEEP, SLEEP, SLEEP]}]})


class TestProgress:
    def test_part_way_through(self, tmp_path):
        records = _run(tmp_path, _spec())
        cut = next(i for i, r in enumerate(records) if r["kind"] == "step_start"
                   and r["data"]["case"] == 0 and r["data"]["step"] == 1)
        shown = progress(_state(records[:cut + 1]))
        assert (shown["steps_run"], shown["steps_total"]) == (2, 9)
        assert shown["test"] == {"number": 1, "of": 3, "name": "a", "requirement": "R-1"}
        assert shown["estimated"] is False

    def test_a_test_case_that_ended_early_leaves_the_total(self, tmp_path):
        shown = progress(_state(_run(tmp_path, _spec())))
        # setup 1, a 2, b 1 (errored; its second step never runs), c 3, teardown 1
        assert (shown["steps_run"], shown["steps_total"]) == (8, 8)
        assert shown["time_left_s"] is None            # the run has ended

    def test_test_cases_not_selected_are_not_counted(self, tmp_path):
        shown = progress(_state(_run(tmp_path, _spec(), selection=["c"])))
        assert (shown["steps_run"], shown["steps_total"]) == (5, 5)

    def test_the_estimate_uses_the_same_step_then_its_action_then_all(self):
        state = {"status": "RUNNING", "position": {"phase": "test", "case": 0, "step": 3},
                 "setup": [], "teardown": [],
                 "cases": [{"name": "a", "status": "RUNNING", "steps": [
                     {"action": "psu.read", "arguments": {"channel": 1}, "status": "PASS",
                      "duration_s": 2.0},
                     {"action": "psu.read", "arguments": {"channel": 2}, "status": "PASS",
                      "duration_s": 4.0},
                     {"action": "sleep", "arguments": {"seconds": 6}, "status": "PASS",
                      "duration_s": 6.0},
                     {"action": "psu.read", "arguments": {"channel": 1}, "status": "PENDING"},
                     {"action": "psu.read", "arguments": {"channel": 3}, "status": "PENDING"},
                     {"action": "dmm.read", "arguments": {}, "status": "PENDING"}]}]}
        shown = progress(state)
        # same step: 2.0; same action: mean(2, 4) = 3.0; neither: mean(2, 4, 6) = 4.0
        assert shown["time_left_s"] == 9.0 and shown["estimated"]

    def test_a_restart_counts_its_steps_again(self, tmp_path):
        class Restart(RunControl):
            def __init__(self):
                super().__init__()
                self.done = False

            def checkpoint(self, phase, case, step, interruptible=True):
                if (phase, case, step) == ("test", 2, 0) and not self.done:
                    self.done = True
                    with self._condition:
                        self._position = {"phase": phase, "case": case, "step": step}
                    self.request({"cmd": "restart_from", "case": 0, "step": 0})
                return super().checkpoint(phase, case, step, interruptible)

        records = _run(tmp_path, _spec(), control=Restart())
        cut = next(i for i, r in enumerate(records) if r["kind"] == "control_applied"
                   and r["data"]["command"] == "restart_from")
        before = progress(_state(records[:cut]))
        after = progress(_state(records[:cut + 2]))
        assert before["steps_run"] == 4
        assert after["steps_run"] < before["steps_run"]

    def test_setup_and_teardown_are_named(self):
        state = {"status": "RUNNING", "position": {"phase": "setup", "case": None, "step": 0},
                 "setup": [{"status": "RUNNING"}], "teardown": [], "cases": []}
        shown = progress(state)
        assert (shown["phase"], shown["test"]) == ("setup", None)


def test_the_hub_serves_status(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("")
    hub = Hub()
    hub.follow(str(path))
    for record in (_rec("PSU", "opened sim", 1.0), _rec("PSU", ">> *IDN?", 2.0)):
        hub._apply(record)                          # pylint: disable=protected-access
    status = hub.status(now=4.0)
    assert status["run"] == "WAITING"
    assert status["instruments"][0]["state"] == "ok"
    assert status["instruments"][0]["since_s"] == 2.0
    assert status["progress"]["steps_total"] == 0
