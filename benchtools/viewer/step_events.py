"""The events recorded during each step of a run, for the Run page (#201).

Selecting a step on the Run page shows what happened while it ran: each
instrument's commands and replies, frames, readings, warnings and errors, each
at its time from the step's start, beside the measurements that decided the
step's verdict and the limits they were checked against.

A record belongs to a step if it was logged after the step's ``step_start``
record and before its ``step_end`` (#135), in the order the log holds them -
not by comparing times, which a record from another thread could tie. The
runner runs one step at a time, so between a step's start and end every record
is that step's. The ``step_start`` and ``step_end`` records themselves are not
listed: what they say is the step's own row and its measurements.

Only the latest time a step ran is kept: a step that runs again (a test case
restarted, a restart from a step) starts afresh, and a step marked to run again
and not yet run shows nothing. A step keeps its last :data:`KEEP_STEP_RECORDS`
records, and the run as a whole its last :data:`KEEP_RUN_RECORDS`: beyond that,
the records of the steps that started longest ago go first. Each step counts the
records it dropped, so neither a long step nor a long run of short ones can take
the viewer's memory with it.

Traces to: VIEW-FR-048, VIEW-DD-STEPEVENTS.
"""

from __future__ import annotations

import copy
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from .traffic import EVENT, NOTE, RECEIVED, SENT, classify

__all__ = ["StepEvents", "category", "step_query", "step_view", "KEEP_STEP_RECORDS",
           "KEEP_RUN_RECORDS", "PHASES"]

#: Most records kept for one step; earlier ones are dropped and counted.
KEEP_STEP_RECORDS = 5000

#: Most records kept for all of a run's steps together; the records of the steps
#: that started longest ago are dropped first, and counted by their step.
KEEP_RUN_RECORDS = 50000

#: The phases a step belongs to, as the runner names them.
PHASES = ("setup", "test", "teardown")

#: A step: its phase, test case index (``None`` outside a test case) and index.
StepKey = Tuple[str, Optional[int], int]

_BY_LEVEL = {"ERROR": "error", "CRITICAL": "error", "WARNING": "warning"}
_BY_KIND = {"rf_packet": "frame", "reading": "measurement"}
_BY_PREFIX = ((("run_", "case_", "step_"), "runner"), (("control",), "control"))
_BY_LINE = {SENT: "command", RECEIVED: "reply", EVENT: "event", NOTE: "note"}

_NONE: Dict[str, Any] = {"started": None, "ended": None, "dropped": 0, "events": []}


def _key(data: Dict[str, Any]) -> Optional[StepKey]:
    phase, case, step = data.get("phase"), data.get("case"), data.get("step")
    if phase not in PHASES or not isinstance(step, int):
        return None
    if phase != "test":
        return (phase, None, step)
    return (phase, case, step) if isinstance(case, int) else None


def category(record: Dict[str, Any]) -> str:
    """What *record* is, in one word: ``error`` or ``warning`` by its level, else
    ``frame``, ``measurement``, ``runner`` or ``control`` by its kind, else
    ``command``, ``reply``, ``event`` or ``note`` by its line (VIEW-DD-TRAFFIC)."""
    level = _BY_LEVEL.get(str(record.get("level", "")).upper())
    if level:
        return level
    kind = str(record.get("kind") or "")
    if kind in _BY_KIND:
        return _BY_KIND[kind]
    for prefixes, name in _BY_PREFIX:
        if kind.startswith(prefixes):
            return name
    return _BY_LINE[classify(str(record.get("text", "")))[0]]


class StepEvents:
    """Every record logged during each step, in log order, for the latest run."""

    def __init__(self, keep: int = KEEP_STEP_RECORDS,
                 keep_run: int = KEEP_RUN_RECORDS) -> None:
        self.keep = keep
        self.keep_run = keep_run
        #: Each step's records, in the order the steps last started.
        self.steps: Dict[StepKey, Dict[str, Any]] = {}
        #: The step whose records are arriving, between its start and end.
        self.current: Optional[StepKey] = None
        #: Records kept across every step.
        self.total = 0

    def feed(self, record: Dict[str, Any]) -> None:
        """One event record, in the order the log holds it."""
        kind = record.get("kind")
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        if kind == "run_start":
            self.steps.clear()
            self.current = None
            self.total = 0
        elif kind == "step_start":
            self._start(_key(data), record.get("t"))
        elif kind == "step_end":
            key = _key(data)
            if key is not None and key in self.steps:
                self.steps[key]["ended"] = record.get("t")
            self.current = None
        elif kind == "run_end":
            self.current = None
        elif self.current is not None:
            self._add(record)

    def _start(self, key: Optional[StepKey], started: Any) -> None:
        """A step starts: afresh, and as the newest, even if it ran before."""
        self.current = key
        if key is None:
            return
        earlier = self.steps.pop(key, None)
        if earlier is not None:
            self.total -= len(earlier["records"])
        self.steps[key] = {"started": started, "ended": None,
                           "records": deque(maxlen=self.keep), "dropped": 0}

    def _add(self, record: Dict[str, Any]) -> None:
        """A record of the current step, within the step's and the run's bounds."""
        entry = self.steps[self.current]
        listed: Deque[Dict[str, Any]] = entry["records"]
        if len(listed) == listed.maxlen:
            entry["dropped"] += 1
        else:
            self.total += 1
        listed.append(record)
        for oldest in self.steps.values():         # the steps that started longest ago
            if self.total <= self.keep_run:
                break
            while oldest["records"] and self.total > self.keep_run:
                oldest["records"].popleft()
                oldest["dropped"] += 1
                self.total -= 1

    def view(self, phase: str, case: Optional[int], step: int,
             started: Optional[float] = None) -> Dict[str, Any]:
        """The records of one step, each with its time from the step's start.

        :param started: the step's start as the run's state has it. When it is
            given and is not the start these records were kept from, there are
            none.
        """
        entry = self.steps.get((phase, case if phase == "test" else None, step))
        if entry is None or (started is not None and entry["started"] != started):
            return copy.deepcopy(_NONE)
        origin = entry["started"]
        events: List[Dict[str, Any]] = []
        for record in entry["records"]:
            stamp = record.get("t")
            events.append({
                "t": stamp,
                "dt": (round(stamp - origin, 6) if isinstance(stamp, (int, float))
                       and isinstance(origin, (int, float)) else None),
                "source": record.get("source", ""),
                "level": record.get("level", ""),
                "kind": record.get("kind") or "",
                "category": category(record),
                "text": record.get("text", ""),
            })
        return {"started": origin, "ended": entry["ended"], "dropped": entry["dropped"],
                "events": events}


def step_view(state: Any, events: StepEvents, phase: str, case: Optional[int],
              step: int) -> Dict[str, Any]:
    """One step of *state* (a :class:`~benchtools.viewer.state.RunState`) as the
    Run page has it, with its measurements and their limits, and the records
    logged between its start and end. A step marked to run again, its start
    cleared, has none.

    :raises ValueError: when the run has no such step.
    """
    if phase == "test" and case is not None and 0 <= case < len(state.cases):
        steps = state.cases[case]["steps"]
    else:
        steps = {"setup": state.setup, "teardown": state.teardown}.get(phase)
    if steps is None or not 0 <= step < len(steps):
        raise ValueError("the run has no such step")
    shown = copy.deepcopy(steps[step])
    listed = (events.view(phase, case, step, shown["started"])
              if shown.get("started") is not None else copy.deepcopy(_NONE))
    return dict(listed, phase=phase, case=case if phase == "test" else None, index=step,
                step=shown)


def step_query(query: Callable[[str], Optional[str]]) -> Tuple[str, Optional[int], int]:
    """``(phase, case, step)`` from ``/api/step``'s query, *query* giving each value.

    :raises ValueError: for a phase not in :data:`PHASES`, or a step - or a test
        case, for a ``test`` step - that is not a whole number.
    """
    phase = query("phase") or ""
    if phase not in PHASES:
        raise ValueError("phase is one of %s" % ", ".join(PHASES))
    try:
        case = int(query("case") or "") if phase == "test" else None
        return phase, case, int(query("step") or "")
    except ValueError as exc:
        raise ValueError("step, and case for a test case's step, are whole numbers") from exc
