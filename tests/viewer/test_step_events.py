"""The events recorded during each step of a run (#201).

Traces to: VIEW-FR-048, SWE4-UT-VIEWSTEPS.
"""

from __future__ import annotations

import logging
import pathlib

import pytest

from benchtools.core.events import EventTail, start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.spec import load_spec
from benchtools.viewer.server import Hub
from benchtools.viewer.step_events import StepEvents, category

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _line(t, text, source="PSU", level="DEBUG", **extra):
    return dict({"t": t, "source": source, "level": level, "logger": "x", "text": text},
                **extra)


def _runner(kind, t, **data):
    return {"t": t, "source": "TEST", "level": "DEBUG", "logger": "benchtools.runner",
            "text": kind, "kind": kind, "data": data}


def _feed(*records):
    events = StepEvents()
    for record in records:
        events.feed(record)
    return events


class TestCategory:
    @pytest.mark.parametrize("record, expected", [
        (_line(1, ">> VOUT1?"), "command"),
        (_line(1, "<< 3.300V"), "reply"),
        (_line(1, "> scan"), "command"),
        (_line(1, "< +adv addr=1"), "event"),
        (_line(1, "opened simulated GPD-3303D"), "note"),
        (_line(1, "x", kind="rf_packet", data={"direction": "rx"}), "frame"),
        (_line(1, "x", kind="reading", data={}), "measurement"),
        (_line(1, "x", kind="control", data={}), "control"),
        (_runner("case_start", 1), "runner"),
        (_line(1, "<< 3.300V", level="WARNING"), "warning"),
        (_line(1, "no reply", level="ERROR"), "error"),
        (_line(1, "boom", level="CRITICAL"), "error"),
    ])
    def test_each_kind_of_record(self, record, expected):
        assert category(record) == expected

    def test_a_record_without_a_level_or_text(self):
        assert category({"t": 1.0}) == "note"


class TestAttribution:
    def test_only_records_between_start_and_end_belong_to_the_step(self):
        events = _feed(
            _runner("run_start", 0.0),
            _line(0.5, ">> *IDN?"),
            _runner("step_start", 1.0, phase="test", case=0, step=0),
            _line(1.25, ">> VSET1:3.3"),
            _line(1.5, "<< OK", level="WARNING"),
            _runner("step_end", 2.0, phase="test", case=0, step=0, status="PASS"),
            _line(2.5, ">> OUT0"),
            _runner("step_start", 3.0, phase="test", case=0, step=1),
            _line(3.1, ">> OUT1"),
            _runner("step_end", 4.0, phase="test", case=0, step=1, status="PASS"))
        view = events.view("test", 0, 0)
        assert [e["text"] for e in view["events"]] == [">> VSET1:3.3", "<< OK"]
        assert [e["dt"] for e in view["events"]] == [0.25, 0.5]
        assert [e["category"] for e in view["events"]] == ["command", "warning"]
        assert (view["started"], view["ended"], view["dropped"]) == (1.0, 2.0, 0)
        assert [e["text"] for e in events.view("test", 0, 1)["events"]] == [">> OUT1"]

    def test_log_order_decides_not_the_time(self):
        """A record logged after the step ended, but stamped earlier, is not the step's."""
        events = _feed(_runner("step_start", 1.0, phase="test", case=0, step=0),
                       _runner("step_end", 2.0, phase="test", case=0, step=0),
                       _line(1.5, "<< late"))
        assert not events.view("test", 0, 0)["events"]

    def test_setup_and_teardown_steps_and_a_step_still_running(self):
        events = _feed(_runner("step_start", 1.0, phase="setup", case=None, step=0),
                       _line(1.1, "setup line"),
                       _runner("step_end", 1.2, phase="setup", case=None, step=0),
                       _runner("step_start", 5.0, phase="teardown", case=None, step=0),
                       _line(5.1, "teardown line"))
        assert [e["text"] for e in events.view("setup", None, 0)["events"]] == ["setup line"]
        running = events.view("teardown", 7, 0)            # the case is ignored outside tests
        assert [e["text"] for e in running["events"]] == ["teardown line"]
        assert running["ended"] is None

    def test_a_step_that_runs_again_starts_afresh(self):
        events = _feed(_runner("step_start", 1.0, phase="test", case=0, step=0),
                       _line(1.1, "first time"),
                       _runner("step_end", 1.2, phase="test", case=0, step=0),
                       _runner("step_start", 2.0, phase="test", case=0, step=0),
                       _line(2.1, "second time"),
                       _runner("step_end", 2.2, phase="test", case=0, step=0))
        assert [e["text"] for e in events.view("test", 0, 0)["events"]] == ["second time"]

    def test_a_start_that_is_not_the_one_kept_shows_nothing(self):
        events = _feed(_runner("step_start", 1.0, phase="test", case=0, step=0),
                       _line(1.1, "line"))
        assert events.view("test", 0, 0, started=1.0)["events"]
        assert not events.view("test", 0, 0, started=9.0)["events"]

    def test_a_new_run_forgets_the_last(self):
        events = _feed(_runner("step_start", 1.0, phase="test", case=0, step=0),
                       _line(1.1, "line"),
                       _runner("run_start", 2.0))
        assert not events.view("test", 0, 0)["events"]

    def test_a_long_step_keeps_its_latest_records_and_counts_the_rest(self):
        events = StepEvents(keep=3)
        events.feed(_runner("step_start", 1.0, phase="test", case=0, step=0))
        for index in range(5):
            events.feed(_line(1.0 + index, "line %d" % index))
        view = events.view("test", 0, 0)
        assert [e["text"] for e in view["events"]] == ["line 2", "line 3", "line 4"]
        assert view["dropped"] == 2

    def test_records_outside_any_step(self):
        events = _feed(_line(1.0, "before"), _runner("run_end", 2.0), _line(3.0, "after"))
        assert not events.steps
        assert events.view("test", 0, 0) == {"started": None, "ended": None, "dropped": 0,
                                              "events": []}


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    """A simulated run's own event log, and the hub that read it."""
    pytest.importorskip("yaml")
    path = str(tmp_path_factory.mktemp("steps") / "events.jsonl")
    handler = start_event_log(path)
    spec = load_spec(str(ROOT / "specs" / "sensor_power_signal_and_link.yaml"))
    try:
        aliases = {alias: spec.instrument_drivers.get(alias, "")
                   for alias in spec.instruments_used}
        with BenchRunner.from_config(BenchConfig.simulated(aliases), simulate=True) as runner:
            runner.run(spec)
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    hub = Hub()
    hub.follow(path)
    hub.poll()
    return path, hub


def _where(data):
    return (data["phase"], data["case"] if data["phase"] == "test" else None, data["step"])


class TestRecordedRun:
    """Each step of a recorded run lists exactly the records between its start and end."""

    def test_every_step_lists_exactly_its_own_records(self, recorded):
        path, hub = recorded
        records = EventTail(path).read()                   # the log, independently of the hub
        expected, current = {}, None
        for record in records:
            if record.get("kind") == "step_start":
                current = _where(record["data"])
                expected[current] = []
            elif record.get("kind") in ("step_end", "run_end"):
                current = None
            elif current is not None:
                expected[current].append((record["t"], record["source"], record["text"]))
        assert len(expected) > 5
        assert any(expected.values())
        for (phase, case, step), wanted in expected.items():
            view = hub.step(phase, case, step)
            assert [(e["t"], e["source"], e["text"]) for e in view["events"]] == wanted, \
                (phase, case, step)
            assert all(view["started"] <= e["t"] <= view["ended"] for e in view["events"])
            assert view["step"]["started"] == view["started"]

    def test_a_supply_step_shows_its_commands_and_replies(self, recorded):
        _path, hub = recorded
        state = hub.state.snapshot()
        index, case = next((i, c) for c in state["cases"] for i, s in enumerate(c["steps"])
                           if s["action"].startswith("psu."))
        view = hub.step("test", case["case"], index)
        sources = {e["source"] for e in view["events"]}
        assert "PSU" in sources
        assert {"command", "reply"} <= {e["category"] for e in view["events"]}
        assert all(e["dt"] >= 0 for e in view["events"])

    def test_a_measured_step_carries_its_limits(self, recorded):
        _path, hub = recorded
        state = hub.state.snapshot()
        found = [(c["case"], i) for c in state["cases"] for i, s in enumerate(c["steps"])
                 if s["measurements"]]
        assert found
        view = hub.step("test", *found[0])
        measurement = view["step"]["measurements"][0]
        assert {"name", "value", "unit", "limit", "status"} <= set(measurement)

    def test_no_such_step_is_refused(self, recorded):
        _path, hub = recorded
        for where in (("test", 99, 0), ("test", None, 0), ("test", 0, 99), ("setup", None, -1),
                      ("cleanup", None, 0)):
            with pytest.raises(ValueError):
                hub.step(*where)

    def test_a_step_marked_to_run_again_shows_nothing(self, recorded):
        path, _hub = recorded
        hub = Hub()
        hub.follow(path)
        hub.poll()
        case = next(c for c in hub.state.cases if c["steps"])
        assert hub.step("test", case["case"], 0)["started"] is not None
        case["steps"][0]["started"] = None                 # as restart_from leaves it
        assert not hub.step("test", case["case"], 0)["events"]
