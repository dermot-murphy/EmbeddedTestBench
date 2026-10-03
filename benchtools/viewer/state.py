"""The state of a run, rebuilt from its event log (#137).

The runner writes what it does as structured records (#135): ``run_start``
with the whole plan, then each test case and step as it starts and ends, and
``run_end``. :class:`RunState` applies those records one by one and keeps the
tree the viewer draws: test specification, test cases, steps, each with its
status. Built only from the log, it is the same whether the viewer started the
run, attached to it part-way through, or opened the log after it finished.

Traces to: VIEW-FR-003, VIEW-FR-004, VIEW-DD-STATE.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

__all__ = ["RunState", "describe_step", "PENDING", "RUNNING", "NOT_SELECTED"]

PENDING = "PENDING"
RUNNING = "RUNNING"
NOT_SELECTED = "NOT SELECTED"


def _words(name: str) -> str:
    return name.replace("_", " ").strip()


def _value(value: Any) -> str:
    if isinstance(value, dict) and "path" in value and len(value) <= 2:
        # A reference to a saved value, as jsonable writes a Reference.
        return "<%s>" % value["path"]
    if isinstance(value, float):
        return "%g" % value
    return str(value)


def describe_step(action: str, arguments: Optional[Dict[str, Any]] = None,
                  description: str = "") -> str:
    """A step in words: ``psu.set_voltage(channel=2, volts=3.3)`` reads
    "PSU set voltage: channel 2, volts 3.3".

    A step's own description, where the specification gives one, wins.
    """
    if description:
        return description
    instrument, _, method = action.rpartition(".")
    text = ("%s %s" % (instrument.upper(), _words(method))) if instrument else _words(method)
    if arguments:
        text += ": " + ", ".join(
            "%s %s" % (_words(str(name)), _value(value)) for name, value in arguments.items())
    return text


def _steps(planned: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "step": item.get("step", index),
        "action": item.get("action", ""),
        "text": describe_step(item.get("action", ""), item.get("arguments"),
                              item.get("description", "")),
        "arguments": item.get("arguments"),
        "save": item.get("save"),
        "status": PENDING,
        "result": None,
        "error": "",
        "duration_s": None,
        "measurements": [],
        "started": None,
        "ended": None,
    } for index, item in enumerate(planned)]


def _clear(step: Dict[str, Any]) -> None:
    """Back to not yet run, for a step that will run again."""
    step.update(status=PENDING, result=None, error="", duration_s=None, measurements=[],
                started=None, ended=None)


class RunState:  # pylint: disable=too-many-instance-attributes
    """What a run has done so far, from its event records."""

    def __init__(self) -> None:
        self.control_port: Optional[int] = None
        self.runs = 0
        self._reset()

    def _reset(self) -> None:
        self.status = "WAITING"
        self.suite = ""
        self.plan: Dict[str, Any] = {}
        self.setup: List[Dict[str, Any]] = []
        self.teardown: List[Dict[str, Any]] = []
        self.cases: List[Dict[str, Any]] = []
        self.position: Dict[str, Any] = {"phase": None, "case": None, "step": None}
        self.paused = False
        self.last_control: Optional[Dict[str, Any]] = None
        self.verdict: Optional[Dict[str, Any]] = None
        self.started: Optional[float] = None
        self.finished: Optional[float] = None

    # ------------------------------------------------------------------
    def apply(self, record: Dict[str, Any]) -> bool:
        """Apply one event record; ``True`` if the state changed."""
        kind = record.get("kind")
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        handler = getattr(self, "_on_" + str(kind), None) if kind else None
        if not callable(handler):
            return False
        handler(data, record.get("t"))  # pylint: disable=not-callable
        return True

    def _on_run_start(self, data: Dict[str, Any], t: Optional[float]) -> None:
        port = self.control_port
        self._reset()
        self.control_port = port
        self.runs += 1
        self.status = RUNNING
        self.started = t
        self.plan = {key: data.get(key) for key in (
            "suite", "spec_source", "bench", "simulated", "selection", "requirements",
            "parameters")}
        self.suite = data.get("suite", "")
        self.setup = _steps(data.get("setup") or [])
        self.teardown = _steps(data.get("teardown") or [])
        self.cases = [{
            "case": test.get("case", index),
            "name": test.get("name", ""),
            "requirement": test.get("requirement", ""),
            "description": test.get("description", ""),
            "status": PENDING if test.get("selected", True) else NOT_SELECTED,
            "error": "",
            "skip_reason": "",
            "duration_s": None,
            "steps": _steps(test.get("steps") or []),
        } for index, test in enumerate(data.get("tests") or [])]

    def _steps_of(self, data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        phase = data.get("phase")
        if phase == "setup":
            return self.setup
        if phase == "teardown":
            return self.teardown
        case = data.get("case")
        if isinstance(case, int) and 0 <= case < len(self.cases):
            return self.cases[case]["steps"]
        return None

    def _step(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        steps = self._steps_of(data)
        index = data.get("step")
        if steps is None or not isinstance(index, int):
            return None
        while len(steps) <= index:             # attached to a log without the plan
            steps.extend(_steps([{"step": len(steps), "action": data.get("action", "")}]))
        return steps[index]

    def _on_step_start(self, data: Dict[str, Any], t: Optional[float]) -> None:
        self.position = {key: data.get(key) for key in ("phase", "case", "step")}
        step = self._step(data)
        if step is not None:
            step.update(status=RUNNING, started=t, ended=None, result=None, error="",
                        duration_s=None, measurements=[])

    def _on_step_end(self, data: Dict[str, Any], t: Optional[float]) -> None:
        step = self._step(data)
        if step is None:
            return
        step.update(
            status=data.get("status", ""), ended=t, result=data.get("result"),
            error=data.get("error", ""), duration_s=data.get("duration_s"),
            measurements=data.get("measurements") or [],
            resolved=data.get("arguments"))
        if data.get("save") and step.get("save") is None:
            step["save"] = data.get("save")

    def _case(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        index = data.get("case")
        if isinstance(index, int) and 0 <= index < len(self.cases):
            return self.cases[index]
        return None

    def _on_case_start(self, data: Dict[str, Any], _t: Optional[float]) -> None:
        case = self._case(data)
        if case is not None:
            case.update(status=RUNNING, error="", skip_reason="", duration_s=None)
            for step in case["steps"][int(data.get("first_step") or 0):]:
                _clear(step)

    def _on_case_end(self, data: Dict[str, Any], _t: Optional[float]) -> None:
        case = self._case(data)
        if case is not None:
            case.update(status=data.get("status", ""), error=data.get("error", ""),
                        skip_reason=data.get("skip_reason", ""),
                        duration_s=data.get("duration_s"))

    def _on_run_end(self, data: Dict[str, Any], t: Optional[float]) -> None:
        self.status = data.get("status", "")
        self.verdict = data
        self.finished = t
        self.paused = False
        self.position = {"phase": None, "case": None, "step": None}

    def _on_control_listening(self, data: Dict[str, Any], _t: Optional[float]) -> None:
        self.control_port = data.get("port")

    def _on_control(self, data: Dict[str, Any], t: Optional[float]) -> None:
        self.last_control = dict(data, t=t)

    def _on_control_applied(self, data: Dict[str, Any], _t: Optional[float]) -> None:
        self.position = {key: data.get(key) for key in ("phase", "case", "step")}
        command = data.get("command")
        if command == "pause":
            self.paused = True
        elif command in ("resume", "abort"):
            self.paused = False
        elif command == "restart_from":
            self.paused = False
            target = data.get("target_case")
            for case in self.cases:
                if isinstance(target, int) and case["case"] > target and \
                        case["status"] != NOT_SELECTED:
                    case.update(status=PENDING, error="", skip_reason="", duration_s=None)
                    for step in case["steps"]:
                        _clear(step)

    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """Everything the page draws, as JSON-ready data."""
        return copy.deepcopy({
            "status": self.status,
            "suite": self.suite,
            "plan": self.plan,
            "setup": self.setup,
            "teardown": self.teardown,
            "cases": self.cases,
            "position": self.position,
            "paused": self.paused,
            "last_control": self.last_control,
            "verdict": self.verdict,
            "control_port": self.control_port,
            "started": self.started,
            "finished": self.finished,
            "runs": self.runs,
        })
