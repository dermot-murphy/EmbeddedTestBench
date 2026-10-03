"""The viewer's status bar: each instrument, the test running, progress and time left (#149).

Everything here is computed from the event log, so it is the same whether the
viewer started the run or attached to it.

**Instruments.** :class:`InstrumentStatus` keeps, per event-log source, whether
its link is open - every transport logs ``opened ...`` and ``closed ...`` -
when it last sent or received anything, and the level and text of its last
record. Its state is the worst that applies: ``closed``, ``error`` or
``warning`` (the last record was one), ``silent`` (nothing for
:data:`SILENT_AFTER_S`), else ``ok``.

**Progress.** :func:`progress` counts the steps the run will execute - setup,
teardown, and the steps of each selected test case that is not marked skip -
and those it has. A test case that ended early (a step errored) has no more to
run, so its unrun steps leave the total. A restart returns steps to pending
(VIEW-DD-STATE), so they count again.

**Time left** is an estimate: each remaining step is expected to take what the
same step, with the same arguments, took when it last ran; else the mean of its
action; else the mean of all the steps that have run. It is ``None`` until
:data:`MIN_STEPS_FOR_ESTIMATE` steps have run. It is built from step
durations, never the wall clock, so a pause does not inflate it.

Traces to: VIEW-FR-022 .. VIEW-FR-024, VIEW-DD-STATUS.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["InstrumentStatus", "progress", "SILENT_AFTER_S", "MIN_STEPS_FOR_ESTIMATE"]

#: An open instrument with nothing logged for this long is shown as silent.
SILENT_AFTER_S = 30.0

#: Steps that must have run before the time left is estimated.
MIN_STEPS_FOR_ESTIMATE = 3

_DONE = ("PASS", "FAIL", "ERROR", "SKIP")
_UNRUN = ("PENDING", "RUNNING")


class InstrumentStatus:
    """Each instrument's link, last activity and last problem."""

    def __init__(self) -> None:
        self.sources: Dict[str, Dict[str, Any]] = {}

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; ``True`` if it was an instrument's."""
        source = record.get("source")
        if not source or source in ("TEST", "BENCH") or record.get("kind") in (
                "run_start", "run_end", "case_start", "case_end", "step_start", "step_end"):
            return False
        entry = self.sources.setdefault(source, {"source": source, "open": None,
                                                 "last_t": None, "level": "", "text": ""})
        text = str(record.get("text", ""))
        if text.startswith("opened "):
            entry["open"] = True
        elif text.startswith("closed "):
            entry["open"] = False
        elif entry["open"] is None:
            entry["open"] = True                    # attached after it opened
        entry["last_t"] = record.get("t", entry["last_t"])
        entry["level"] = str(record.get("level", ""))
        entry["text"] = text
        return True

    def view(self, now: float) -> List[Dict[str, Any]]:
        """Each instrument's state, at time *now*, in order of name."""
        listed = []
        for source in sorted(self.sources):
            entry = dict(self.sources[source])
            since = (now - entry["last_t"]) if isinstance(entry["last_t"], (int, float)) else None
            entry["since_s"] = round(since, 1) if since is not None else None
            if entry["open"] is False:
                state = "closed"
            elif entry["level"] in ("ERROR", "CRITICAL"):
                state = "error"
            elif entry["level"] == "WARNING":
                state = "warning"
            elif since is not None and since > SILENT_AFTER_S:
                state = "silent"
            else:
                state = "ok"
            entry["state"] = state
            listed.append(entry)
        return listed


def _steps_to_run(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every step the run will execute, run or not, in order."""
    steps = list(state.get("setup") or [])
    for case in state.get("cases") or []:
        if case.get("status") in ("NOT SELECTED",) or case.get("skip_reason"):
            continue
        finished = case.get("status") in _DONE
        for step in case.get("steps") or []:
            if finished and step.get("status") in _UNRUN:
                continue                            # the test case ended before it
            steps.append(step)
    steps.extend(state.get("teardown") or [])
    return steps


def _same(step: Dict[str, Any]) -> str:
    return "%s %r" % (step.get("action", ""), step.get("arguments"))


def _expected(step: Dict[str, Any], timed: List[Dict[str, Any]]) -> float:
    """How long *step* should take: what the same step with the same arguments
    took when it last ran, else the mean of its action, else the mean of all."""
    same = [float(done["duration_s"]) for done in timed if _same(done) == _same(step)]
    if same:
        return same[-1]
    action = [float(done["duration_s"]) for done in timed
              if done.get("action") == step.get("action")]
    pool = action or [float(done["duration_s"]) for done in timed]
    return sum(pool) / len(pool)


def progress(state: Dict[str, Any]) -> Dict[str, Any]:
    """Steps run of total, the test case running, and the time left, from a run's state."""
    steps = _steps_to_run(state)
    done = [step for step in steps if step.get("status") in _DONE]
    remaining = [step for step in steps if step.get("status") not in _DONE]
    timed = [step for step in done if isinstance(step.get("duration_s"), (int, float))]
    left: Optional[float] = None
    if len(timed) >= MIN_STEPS_FOR_ESTIMATE and state.get("status") == "RUNNING":
        left = round(sum(_expected(step, timed) for step in remaining), 1)
    position = state.get("position") or {}
    cases = state.get("cases") or []
    current = None
    if position.get("phase") == "test" and isinstance(position.get("case"), int) \
            and 0 <= position["case"] < len(cases):
        case = cases[position["case"]]
        current = {"number": position["case"] + 1, "of": len(cases), "name": case.get("name"),
                   "requirement": case.get("requirement", "")}
    return {"steps_run": len(done), "steps_total": len(steps), "phase": position.get("phase"),
            "test": current, "time_left_s": left, "estimated": left is not None}
