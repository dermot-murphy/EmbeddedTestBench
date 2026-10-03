"""Controlling a run: pause, resume, abort, restart (#136).

Traces to: RUN-FR-061 .. RUN-FR-065, SWE4-UT-CONTROL.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time

import pytest

from benchtools.core.events import EventTail, start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.cli import main
from benchtools.runner.control import (
    ABORT, PAUSE, RESTART_FROM, RESUME, ControlServer, HOST, RunControl,
)
from benchtools.runner.results import Status
from benchtools.runner.runner import ABORTED, NOT_SELECTED, SKIPPED_BY_OPERATOR
from benchtools.runner.spec import TestSpec

SLEEP = {"do": "sleep", "with": {"seconds": 0}}


def _spec(teardown=True) -> TestSpec:
    return TestSpec.from_mapping({
        "name": "control",
        "setup": [SLEEP],
        "teardown": [SLEEP, SLEEP] if teardown else [],
        "tests": [
            {"name": "a", "steps": [SLEEP, SLEEP]},
            {"name": "b", "steps": [dict(SLEEP, save="value"),
                                    {"do": "sleep", "with": {"seconds": {"from": "value"}}},
                                    SLEEP]},
            {"name": "c", "steps": [SLEEP]},
        ],
    })


class _Scripted(RunControl):
    """Sends *script*'s requests when the run reaches each (phase, case, step)."""

    def __init__(self, script):
        super().__init__()
        self.script = dict(script)
        self.replies = []
        self.visited = []

    def checkpoint(self, phase, case, step, interruptible=True):
        self.visited.append((phase, case, step))
        with self._condition:
            self._position = {"phase": phase, "case": case, "step": step}
        message = self.script.pop((phase, case, step), None)
        if message is not None:
            self.replies.append(self.request(message))
        return super().checkpoint(phase, case, step, interruptible)


def _run(control, spec=None, selection=()):
    with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True,
                                 control=control) as runner:
        return runner.run(spec or _spec(), selection)


def _steps_run(control):
    return [where for where in control.visited if where[2] is not None]


class TestAbort:
    def test_abort_stops_after_the_current_step_and_teardown_still_runs(self):
        control = _Scripted({("test", 0, 1): {"cmd": ABORT}})
        run = _run(control)
        assert control.replies[0]["ok"]
        assert [case.status for case in run.cases] == [Status.ERROR, Status.SKIP, Status.SKIP]
        assert run.cases[0].error == ABORTED
        assert len(run.cases[0].steps) == 1
        assert [case.skip_reason for case in run.cases[1:]] == [ABORTED, ABORTED]
        assert [w for w in control.visited if w[0] == "teardown"] == [
            ("teardown", None, 0), ("teardown", None, 1)]
        assert run.status is Status.ERROR

    def test_abort_during_setup_runs_no_test_case(self):
        run = _run(_Scripted({("setup", None, 0): {"cmd": ABORT}}))
        assert run.setup_error == ABORTED
        assert run.cases == []

    def test_a_case_not_selected_stays_not_selected_after_an_abort(self):
        run = _run(_Scripted({("test", 0, 0): {"cmd": ABORT}}), selection=["a", "b"])
        assert [case.skip_reason for case in run.cases[1:]] == [ABORTED, NOT_SELECTED]


class TestRestart:
    def test_restart_test_runs_the_test_case_again_from_its_first_step(self):
        control = _Scripted({("test", 1, 2): {"cmd": "restart_test"}})
        run = _run(control)
        assert [w for w in _steps_run(control) if w[0] == "test"] == [
            ("test", 0, 0), ("test", 0, 1),
            ("test", 1, 0), ("test", 1, 1), ("test", 1, 2),
            ("test", 1, 0), ("test", 1, 1), ("test", 1, 2),
            ("test", 2, 0)]
        assert [case.status for case in run.cases] == [Status.PASS] * 3
        assert len(run.cases[1].steps) == 3

    def test_restart_from_an_earlier_test_case_runs_everything_after_it_again(self):
        control = _Scripted({("test", 2, 0): {"cmd": RESTART_FROM, "case": 0, "step": 1}})
        run = _run(control)
        tests = [w for w in _steps_run(control) if w[0] == "test"]
        assert tests[-5:] == [("test", 0, 1), ("test", 1, 0), ("test", 1, 1),
                              ("test", 1, 2), ("test", 2, 0)]
        assert len(run.cases) == 3
        assert len(run.cases[0].steps) == 2      # step 0 kept from the first pass
        assert run.status is Status.PASS

    def test_restart_forward_skips_what_it_jumps_over(self):
        control = _Scripted({("test", 0, 1): {"cmd": RESTART_FROM, "case": 2, "step": 0}})
        run = _run(control)
        assert [(case.status, case.skip_reason) for case in run.cases] == [
            (Status.SKIP, SKIPPED_BY_OPERATOR), (Status.SKIP, SKIPPED_BY_OPERATOR),
            (Status.PASS, "")]
        assert len(run.cases[0].steps) == 1      # what ran before the jump is kept

    def test_restart_from_a_step_using_a_value_saved_earlier_is_allowed(self):
        control = _Scripted({("test", 2, 0): {"cmd": RESTART_FROM, "case": 1, "step": 1}})
        run = _run(control)
        assert control.replies[0]["ok"]
        assert run.status is Status.PASS

    def test_restart_needing_a_value_never_saved_is_refused(self):
        control = _Scripted({("test", 0, 0): {"cmd": RESTART_FROM, "case": 1, "step": 1}})
        run = _run(control)
        assert control.replies[0]["ok"] is False
        assert "'value'" in control.replies[0]["error"]
        assert run.status is Status.PASS

    @pytest.mark.parametrize("message, words", [
        ({"cmd": RESTART_FROM, "case": 9, "step": 0}, "no test case 9"),
        ({"cmd": RESTART_FROM, "case": 0, "step": 9}, "no step 9"),
        ({"cmd": RESTART_FROM, "case": "a"}, "integer"),
    ])
    def test_a_target_that_does_not_exist_is_refused(self, message, words):
        control = _Scripted({("test", 0, 0): message})
        _run(control)
        assert words in control.replies[0]["error"]

    def test_a_test_case_not_selected_cannot_be_a_target(self):
        control = _Scripted({("test", 0, 0): {"cmd": RESTART_FROM, "case": 2, "step": 0}})
        _run(control, selection=["a", "b"])
        assert "not selected" in control.replies[0]["error"]

    def test_restart_is_refused_during_setup(self):
        control = _Scripted({("setup", None, 0): {"cmd": "restart_test"}})
        _run(control)
        assert "setup" in control.replies[0]["error"]

    def test_requests_and_their_effect_are_in_the_event_log(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        handler = start_event_log(path)
        try:
            _run(_Scripted({("test", 1, 0): {"cmd": "restart_test"},
                            ("test", 2, 0): {"cmd": ABORT}}))
        finally:
            logging.getLogger("benchtools").removeHandler(handler)
            handler.close()
        records = [r for r in EventTail(path).read() if r.get("kind", "").startswith("control")]
        assert [(r["kind"], r["data"]["command"]) for r in records] == [
            ("control", "restart_test"), ("control_applied", RESTART_FROM),
            ("control", ABORT), ("control_applied", ABORT)]
        assert records[0]["data"]["accepted"] is True


class TestRefusals:
    def test_teardown_cannot_be_interrupted(self):
        control = _Scripted({("teardown", None, 0): {"cmd": ABORT}})
        run = _run(control)
        assert "teardown" in control.replies[0]["error"]
        assert run.status is Status.PASS

    def test_nothing_is_accepted_with_no_run(self):
        assert RunControl().request({"cmd": PAUSE}) == {
            "ok": False, "error": "no run is in progress"}

    @pytest.mark.parametrize("message", [None, [], {"cmd": 3}, {"x": 1}])
    def test_a_malformed_request_is_refused(self, message):
        assert RunControl().request(message)["ok"] is False

    def test_an_unknown_command_is_refused_naming_the_known_ones(self):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        reply = control.request({"cmd": "jump"})
        assert "unknown command" in reply["error"]
        assert "restart_from" in reply["error"]

    def test_resume_when_not_paused_and_pause_twice_are_refused(self):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        assert control.request({"cmd": RESUME})["ok"] is False
        assert control.request({"cmd": PAUSE})["ok"]
        assert control.request({"cmd": PAUSE})["ok"] is False

    def test_a_second_abort_is_refused(self):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        assert control.request({"cmd": ABORT})["ok"]
        assert "already pending" in control.request({"cmd": ABORT})["error"]


class TestPause:
    def test_a_paused_run_waits_between_steps_until_resumed(self):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        control.request({"cmd": PAUSE})
        returned = []
        worker = threading.Thread(
            target=lambda: returned.append(control.checkpoint("test", 0, 1)))
        worker.start()
        time.sleep(0.1)
        assert worker.is_alive()
        assert control.status()["state"] == "paused"
        control.request({"cmd": RESUME})
        worker.join(2)
        assert not worker.is_alive()
        assert returned == [None]

    def test_an_abort_ends_a_pause(self):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        control.request({"cmd": PAUSE})
        returned = []
        worker = threading.Thread(
            target=lambda: returned.append(control.checkpoint("test", 0, 1)))
        worker.start()
        control.request({"cmd": ABORT})
        worker.join(2)
        assert returned[0].kind == ABORT

    def test_status_says_where_the_run_is(self):
        control = RunControl()
        assert control.status()["state"] == "idle"
        control.begin("suite", lambda case, step: None)
        control.checkpoint("test", 1, 2)
        assert {k: control.status()[k] for k in ("state", "suite", "phase", "case", "step")} \
            == {"state": "running", "suite": "suite", "phase": "test", "case": 1, "step": 2}
        control.finish()
        assert control.status()["state"] == "idle"


def _ask(port, *messages):
    with socket.create_connection((HOST, port), timeout=5) as connection:
        stream = connection.makefile("rwb")
        replies = []
        for message in messages:
            raw = message if isinstance(message, bytes) else json.dumps(message).encode()
            stream.write(raw + b"\n")
            stream.flush()
            replies.append(json.loads(stream.readline()))
        return replies


class TestServer:
    def test_it_listens_on_127_0_0_1_only(self):
        with ControlServer(RunControl()) as server:
            assert server._server.server_address[0] == "127.0.0.1"
            assert server.port > 0

    def test_requests_and_replies_are_json_lines(self):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        with ControlServer(control) as server:
            replies = _ask(server.port, {"cmd": "status"}, {"cmd": PAUSE}, b"not json")
        status, paused, bad = replies[0], replies[1], replies[2]
        assert status["state"] == "running"
        assert paused["state"] == "paused"
        assert bad["ok"] is False

    def test_a_run_driven_over_the_channel(self):
        control = RunControl()
        spec = TestSpec.from_mapping({"name": "slow", "tests": [
            {"name": "t", "steps": [{"do": "sleep", "with": {"seconds": 0.05}}] * 40}]})
        with ControlServer(control) as server:
            result = []
            worker = threading.Thread(target=lambda: result.append(_run(control, spec)))
            worker.start()
            deadline = time.monotonic() + 5
            while control.status()["state"] != "running" and time.monotonic() < deadline:
                time.sleep(0.01)
            assert _ask(server.port, {"cmd": ABORT})[0]["ok"]
            worker.join(5)
        assert result[0].cases[0].error == ABORTED
        assert len(result[0].cases[0].steps) < 40


class TestCommandLine:
    def test_control_opens_a_port_and_reports_it(self, capsys):
        spec_path = "specs/clock_skew.yaml"
        pytest.importorskip("yaml")
        assert main([spec_path, "--simulate", "--control", "0"]) == 0
        assert "control channel on 127.0.0.1:" in capsys.readouterr().err

    def test_without_control_no_port_is_opened(self, capsys):
        pytest.importorskip("yaml")
        assert main(["specs/clock_skew.yaml", "--simulate"]) == 0
        assert "control channel" not in capsys.readouterr().err
