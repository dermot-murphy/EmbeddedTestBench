"""Running a command document: each step's result, the run's verdict, the report
and the event log.

The document's shape, and the four results a step can have - ERROR, SKIP,
FAIL, PASS, the first that applies - are described in
:mod:`~benchtools.instruments.nordic_dongle.script`.

Traces to: BLE-FR-100 .. BLE-FR-108, BLE-DD-SCRIPT.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Mapping, Optional

from ...core.errors import BenchToolsError, TransportTimeoutError
from .constants import CONNECT_ATTEMPTS, DongleError
from .script import (
    _ADDRESS,
    _VARIABLE,
    CONNECT,
    DISCONNECT,
    ERROR,
    FAIL,
    PASS,
    RESOLUTION_S,
    SKIP,
    CommandScript,
    ScriptStep,
)

__all__ = [
    "CONNECT_ATTEMPTS",
    "CONNECT_SCAN_S",
    "FRAME_WINDOW_S",
    "EventLog",
    "ScriptRun",
    "StepResult",
    "run_script",
]


@dataclass
class StepResult:  # pylint: disable=too-many-instance-attributes
    """What one step did.

    :param elapsed_s: Time from the end of the command to the start of the
        response, as the clock named in *clock* measured it. None for a step
        that asked nothing, and for a delay it is the wait itself.
    :param clock: Which clock produced *elapsed_s* - the dongle's microsecond
        clock, or the host's, which includes USB. Recorded because a figure
        without its clock is not a measurement (BLE-NFR-005).
    """

    test: str
    number: str
    command: str
    response: str = ""
    expected: str = ""
    elapsed_s: Optional[float] = None
    clock: str = ""
    result: str = SKIP
    reason: str = ""
    note: str = ""

    @property
    def notes(self) -> str:
        """Why the step came out as it did, then the document's own note."""
        return " - ".join(part for part in (self.reason, self.note) if part)

    @property
    def reported_s(self) -> Optional[float]:
        """The elapsed time at the resolution this report quotes."""
        if self.elapsed_s is None:
            return None
        return round(round(self.elapsed_s / RESOLUTION_S) * RESOLUTION_S, 3)

    def as_dict(self) -> Dict[str, object]:
        """The step as plain data, for JSON."""
        return {
            "test": self.test,
            "step": self.number,
            "command": self.command,
            "response": self.response,
            "expected": self.expected,
            "seconds": self.reported_s,
            "measured_seconds": self.elapsed_s,
            "resolution_s": RESOLUTION_S,
            "clock": self.clock,
            "result": self.result,
            "reason": self.reason,
            "note": self.note,
        }


@dataclass
class ScriptRun:
    """Every step of one run of a document, and the verdict over them."""

    results: List[StepResult] = field(default_factory=list)
    source: str = ""
    sensor: str = ""
    variables: Mapping[str, str] = field(default_factory=dict)
    #: Replies steps saved, by the name their Save cell gave.
    saved: Dict[str, str] = field(default_factory=dict)
    #: The event log's lines, header first.
    events: List[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        """Steps that passed."""
        return sum(1 for item in self.results if item.result == PASS)

    @property
    def failed(self) -> int:
        """Steps that failed: the reply differed."""
        return sum(1 for item in self.results if item.result == FAIL)

    @property
    def skipped(self) -> int:
        """Steps that made no claim."""
        return sum(1 for item in self.results if item.result == SKIP)

    @property
    def errors(self) -> int:
        """Steps where the system returned a failure code."""
        return sum(1 for item in self.results if item.result == ERROR)

    @property
    def result(self) -> str:
        """**Pass** when no step failed.

        Skipped steps neither fail a run nor vouch for it, which is why the
        report states how many steps were checked as well as how many passed.
        """
        if self.errors:
            return ERROR
        return FAIL if self.failed else PASS

    @property
    def is_pass(self) -> bool:
        """The verdict as a number a limit can check: 1 when it passed."""
        return self.result == PASS

    @property
    def failures(self) -> List[StepResult]:
        """Steps that errored or failed, in order."""
        return [item for item in self.results if item.result in (ERROR, FAIL)]

    def as_dict(self) -> Dict[str, object]:
        """The run as plain data, for JSON."""
        return {
            "source": self.source,
            "sensor": self.sensor,
            "variables": dict(self.variables),
            "saved": dict(self.saved),
            "result": self.result,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "steps": [item.as_dict() for item in self.results],
        }

    # ------------------------------------------------------------------
    def markdown(self) -> str:
        """The run as a report: the verdict, then every step in order."""
        lines = [
            "# BLE command and response results",
            "",
            "| | |",
            "|---|---|",
            "| Result | **%s** |" % self.result,
            "| Document | `%s` |" % (self.source or "?"),
            "| Sensor | %s |" % (self.sensor or "not recorded"),
            "| Variables | %s |" % (_cell(", ".join(
                "%s=%s" % item for item in sorted(self.variables.items()))) or "none"),
            "| Steps | %d passed, %d failed, %d errors, %d skipped |"
            % (self.passed, self.failed, self.errors, self.skipped),
            "",
            "Times are from the end of the command to the start of the response, "
            "quoted to %g ms. Results, first that applies: ERROR when the system "
            "returned a failure code, SKIP when nothing was expected, FAIL when the "
            "reply differs, PASS when it matches." % (RESOLUTION_S * 1000.0),
            "",
            "| Test | Step | Command | Expected | Actual | Response time (ms) | Result | Note |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for item in self.results:
            seconds = "-" if item.reported_s is None else "%.0f" % (item.reported_s * 1000.0)
            lines.append(
                "| %s | %s | %s | %s | %s | %s | %s | %s |"
                % (
                    item.test,
                    item.number,
                    _cell(item.command) or "_delay_",
                    _cell(item.expected),
                    _cell(item.response),
                    seconds,
                    item.result,
                    _cell(item.notes),
                )
            )
        if self.failures:
            lines += ["", "## Errors and failures", ""]
            for item in self.failures:
                lines.append(
                    "- **%s step %s** %s `%s`: expected `%s`, got `%s`%s"
                    % (
                        item.test,
                        item.number,
                        item.result,
                        item.command,
                        item.expected,
                        item.response,
                        " - %s" % item.reason if item.reason else "",
                    )
                )
        return "\n".join(lines) + "\n"

    def write(self, path: str) -> str:
        """Write the markdown report to *path* and return the path."""
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.markdown())
        return path


def _cell(text: str) -> str:
    """Text safe to put in a markdown table cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ")


#: Seconds a ``connect`` step scans before choosing: long enough to hear a
#: sensor that advertises every 9 s at least once.
CONNECT_SCAN_S = 10.0

#: Seconds a step with a Frames cell goes on listening after the reply, to
#: catch a second notification.
FRAME_WINDOW_S = 0.5

# CONNECT_ATTEMPTS, imported above and exported from here, is how many links a
# ``connect`` step tries. A sensor that advertises rarely can fall outside a
# connect window; each failed attempt is in the event log.


class EventLog:
    """One line per event, with the time it happened, for reading beside the report.

    Tab-separated: time, event, step, data, result. Events are ``TX``, ``RX``,
    ``DELAY``, ``CONNECT``, ``DISCONNECT`` and ``ERROR``. The time is the
    host's clock, to the millisecond; the dongle's own measurement of each
    exchange is in the data, to the microsecond.
    """

    EVENTS = ("TX", "RX", "DELAY", "CONNECT", "DISCONNECT", "ERROR")

    def __init__(self, path: Optional[str] = None, clock=None) -> None:
        self.path = path
        self._clock = clock or _wall_clock
        # Held open for the run and flushed per line, so an interrupted run
        # still leaves its log: close() ends it.
        self._handle = (open(path, "w", encoding="utf-8")  # pylint: disable=consider-using-with
                        if path else None)
        self.lines: List[str] = []
        self._emit("time\tevent\tstep\tdata\tresult")

    def event(self, event: str, step: Optional[ScriptStep], data: str, result: str = "") -> None:
        """Record *event* now."""
        where = "%s/%s" % (step.test, step.number) if step is not None else "-"
        self._emit("\t".join((self._clock(), event, where, _flat(data), result or "-")))

    def _emit(self, line: str) -> None:
        self.lines.append(line)
        if self._handle is not None:
            self._handle.write(line + "\n")
            self._handle.flush()

    def close(self) -> None:
        """Close the file, if there is one."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def _wall_clock() -> str:
    """Local time to the millisecond."""
    now = time.time()
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + ".%03d" % (
        int(now * 1000.0) % 1000)


def _flat(text: str) -> str:
    """Text safe for one tab-separated field."""
    return (text or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def run_script(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    dongle,
    script: CommandScript,
    timeout: float = 3.0,
    listen: float = 0.5,
    sleep=time.sleep,
    scan_s: float = CONNECT_SCAN_S,
    connect_attempts: int = CONNECT_ATTEMPTS,
    events: Optional[EventLog] = None,
) -> ScriptRun:
    """Run *script* against *dongle*, one step at a time.

    :param dongle: A :class:`~benchtools.instruments.nordic_dongle.NordicDongle`,
        with a link open to the sensor unless the document connects itself.
    :param timeout: Seconds to wait for a reply the document expects. A step
        that times out **fails**: the document said the sensor would answer.
    :param listen: Seconds to wait after a command the document expects no
        reply to. Whatever arrives is recorded and the step is still skipped.
    :param sleep: Injected for the tests, which must not wait in real time.
    :param scan_s: How long a ``connect`` step scans.
    :param connect_attempts: How many links a ``connect`` step tries.
    :param events: Where to log each event as it happens, if anywhere.

    A link a ``connect`` step opened is closed when the run ends, pass or fail.
    """
    log = events or EventLog()
    run = ScriptRun(source=script.source, sensor=_sensor_name(dongle),
                    variables=dict(script.variables))
    link = _LinkWatch(dongle, log)
    try:
        for test in script.tests:
            _note(dongle, "script: %s" % test.name)
            for step in test.steps:
                if link.blocks(step):
                    run.results.append(_result(step, ERROR, link.lost, command=step.command,
                                               expected=step.expected))
                    continue
                if step.action == CONNECT:
                    link.restored()
                    result = _run_connect(dongle, step, scan_s, connect_attempts, log)
                    link.opened = link.opened or result.result != ERROR
                    run.sensor = _sensor_name(dongle) or run.sensor
                elif step.action == DISCONNECT:
                    result = _run_disconnect(dongle, step, log)
                elif step.expects_disconnect:
                    result = _run_expect_disconnect(dongle, step, step.timeout_s or timeout, log)
                else:
                    filled = _fill_saved(step, run.saved)
                    if filled is None:
                        result = _result(step, ERROR, "a reply it uses was not saved: the step "
                                         "that saves it errored or failed",
                                         command=step.command, expected=step.expected)
                    else:
                        result = _run_step(dongle, filled, (timeout, listen), sleep, log)
                        _keep_saved(filled, result, run.saved)
                if result.result == ERROR:
                    log.event("ERROR", step, result.reason, ERROR)
                run.results.append(result)
    finally:
        if link.opened and getattr(dongle, "is_linked", False):
            dongle.close_link()
    run.events = list(log.lines)
    return run


def _result(step: ScriptStep, result: str, reason: str = "", **fields) -> StepResult:
    """A step's result, carrying the document's own note."""
    return StepResult(test=step.test, number=step.number, result=result,
                      reason=reason, note=step.note, **fields)


class _LinkWatch:
    """Whether the link has dropped unasked, checked before each step."""

    def __init__(self, dongle, log: EventLog) -> None:
        self._dongle = dongle
        self._log = log
        self._previous: Optional[ScriptStep] = None
        self._lost = ""                 # why the link is gone, until a connect restores it
        #: Whether the document opened a link of its own, to close when it ends.
        self.opened = False

    def before(self, step: ScriptStep) -> str:
        """Check for a drop since the last step; why the link is gone, or empty."""
        self._lost = _link_lost(self._dongle, self._previous, self._log) or self._lost
        self._previous = step
        return self._lost

    def blocks(self, step: ScriptStep) -> bool:
        """Whether *step* talks to the sensor over a link that has been lost."""
        lost = self.before(step)
        return bool(lost) and step.action not in (CONNECT, DISCONNECT) and not step.is_delay

    @property
    def lost(self) -> str:
        """Why the link is gone, or empty while it is up."""
        return self._lost

    def restored(self) -> None:
        """A connect is being made: the loss no longer applies."""
        self._lost = ""


def _link_lost(dongle, previous: Optional[ScriptStep], log: EventLog) -> str:
    """Why the link dropped since the last step, logged once; empty if it did not."""
    check = getattr(dongle, "check_link", None)
    event = check() if callable(check) else None
    if event is None:
        return ""
    where = "%s/%s" % (previous.test, previous.number) if previous else "the start"
    reason = event.get("reason") or "?"
    text = "link lost during or after %s (reason %s%s, dongle time %.6f s)" % (
        where, reason, ", supervision timeout: the sensor went silent" if reason == "0x08" else "",
        event.integer("t", 0) / 1.0e6)
    log.event("DISCONNECT", previous, text, ERROR)
    return "not sent: " + text


def _first_sentence(exc: Exception) -> str:
    """The first sentence of an error, which says what happened; the rest advises."""
    return str(exc).split(". ", maxsplit=1)[0]


def _is_no_reply(exc: Exception) -> bool:
    """Whether *exc* says the sensor was silent, as opposed to something failing."""
    if isinstance(exc, TransportTimeoutError):
        return True
    return getattr(exc, "error", None) == DongleError.TIMEOUT


def _run_connect(dongle, step: ScriptStep, scan_s: float, attempts: int,
                 log: EventLog) -> StepResult:
    """Scan, choose the sensor the step names, and open a link. Never raises.

    **Error** if no link opened; otherwise **skip** - a connect has no expected
    response - with the sensor it linked to in the note.
    """
    started = time.perf_counter()
    try:
        if getattr(dongle, "is_linked", False):
            dongle.close_link()
        dongle.scan(scan_s, active=True)
        if _ADDRESS.match(step.target):
            dongle.select(step.target)
        else:
            dongle.select_by_name(step.target)
        # The step makes every attempt itself, whatever the failure, so
        # open_link is asked for one: its own retry would multiply them.
        window = {} if step.timeout_s is None else {"connect_timeout": step.timeout_s}
        attempts = max(1, attempts)
        for attempt in range(1, attempts + 1):
            try:
                dongle.open_link(attempts=1, **window)
                break
            except BenchToolsError as exc:     # retried, then reported
                if attempt == attempts:
                    raise
                log.event("CONNECT", step, "%s: attempt %d of %d failed: %s"
                          % (step.command, attempt, attempts, _first_sentence(exc)))
    except BenchToolsError as exc:             # reported, not raised
        log.event("CONNECT", step, "%s: no link" % step.command, ERROR)
        return _result(step, ERROR, _first_sentence(exc), command=step.command)
    linked = _sensor_name(dongle) or step.target
    elapsed = time.perf_counter() - started
    log.event("CONNECT", step, "%s: linked to %s in %.3f s" % (step.command, linked, elapsed),
              SKIP)
    return _result(step, SKIP, "linked to %s" % linked, command=step.command,
                   response="linked to %s" % linked, elapsed_s=elapsed, clock="host")


def _run_disconnect(dongle, step: ScriptStep, log: EventLog) -> StepResult:
    """Close the link. **Error** if that fails, otherwise **skip**. Never raises."""
    try:
        dongle.close_link()
    except BenchToolsError as exc:             # reported, not raised
        log.event("DISCONNECT", step, "disconnect", ERROR)
        return _result(step, ERROR, "disconnect failed: %s" % exc, command=step.command)
    log.event("DISCONNECT", step, "link closed by the dongle", SKIP)
    return _result(step, SKIP, "link closed", command=step.command)


def _run_expect_disconnect(dongle, step: ScriptStep, timeout: float,
                           log: EventLog) -> StepResult:
    """Send a command the sensor should drop the link after, and time the drop.

    **Error** if it could not be sent, **pass** if the link dropped within
    *timeout*, **fail** if it did not. Never raises.
    """
    log.event("TX", step, "%s (expecting a disconnect within %g ms)" % (step.command,
                                                                      timeout * 1000.0))
    try:
        sample = dongle.command_expecting_disconnect(step.command, timeout=timeout)
    except BenchToolsError as exc:             # reported, not raised
        return _result(step, ERROR, "%s (%s)" % (_first_sentence(exc), type(exc).__name__),
                       command=step.command, expected=step.expected)
    if not sample.disconnected:
        log.event("DISCONNECT", step, "expected; none within %.2f s" % timeout, FAIL)
        return _result(step, FAIL, "still connected %.2f s after the command" % timeout,
                       command=step.command, expected=step.expected,
                       response="still connected")
    if sample.dongle_us is not None:
        elapsed, clock = sample.dongle_us / 1.0e6, "dongle"
    else:
        elapsed, clock = sample.host_s, "host"
    # Reason 0x08 is a supervision timeout: the sensor went silent (a reset, say)
    # and the time includes the dongle waiting out the supervision timeout.
    log.event("DISCONNECT", step, "sensor dropped the link %.3f ms after the command (%s "
              "clock, reason %s%s)" % (elapsed * 1000.0, clock, sample.reason or "?",
                                       ", supervision timeout" if sample.reason == "0x08"
                                       else ""), PASS)
    return _result(step, PASS, "", command=step.command, expected=step.expected,
                   response="<disconnect>", elapsed_s=elapsed, clock=clock)


def _fill_saved(step: ScriptStep, saved: Mapping[str, str]) -> Optional[ScriptStep]:
    """*step* with the replies earlier steps saved filled in; None if one is missing.

    In an expected response written as a pattern the value is escaped, so a
    saved ``V11.00`` matches itself and not ``V11x00``.
    """
    missing = []

    def value_of(match, escape: bool) -> str:
        name = match.group("name")
        if name not in saved:
            missing.append(name)
            return match.group(0)
        return re.escape(saved[name]) if escape else saved[name]

    command = _VARIABLE.sub(lambda match: value_of(match, False), step.command)
    expected = _VARIABLE.sub(lambda match: value_of(match, step.pattern is not None),
                             step.expected)
    note = _VARIABLE.sub(lambda match: value_of(match, False), step.note)
    if missing:
        return None
    return replace(step, command=command, expected=expected, note=note)


def _saved_value(step: ScriptStep, response: str) -> str:
    """What a Save cell keeps: a pattern's first named group if it has one, else the reply."""
    if step.pattern is not None:
        match = re.search(step.pattern, response)
        if match is not None:
            for value in match.groupdict().values():
                if value is not None:
                    return value
    return response


def _keep_saved(step: ScriptStep, result: StepResult, saved: Dict[str, str]) -> None:
    """Keep the reply in *saved* if the step's Save cell asks and the reply earned it."""
    if step.save and result.result in (PASS, SKIP) and result.response:
        saved[step.save] = _saved_value(step, result.response)
        result.reason = " - ".join(part for part in (
            result.reason, "saved %s = %s" % (step.save, saved[step.save])) if part)


def _run_step(dongle, step: ScriptStep, waits, sleep, log: EventLog) -> StepResult:
    """Execute one step. Never raises: a step's outcome is its result.

    *waits* is the run's default reply timeout and listening window; a step's
    own Timeout cell overrides whichever applies.

    Results in priority order: **error** if the system returned a failure code,
    **skip** if nothing was expected, **fail** if the reply differs, **pass** if
    it matches. Silence is an error only where a reply was expected.
    """
    if step.is_delay:
        log.event("DELAY", step, "%g ms" % (step.delay_s * 1000.0), SKIP)
        sleep(step.delay_s)
        return _result(step, SKIP, "a delay makes no claim about the sensor",
                       command="delay %g ms" % (step.delay_s * 1000.0),
                       elapsed_s=step.delay_s, clock="requested")

    expects = step.expects_response or step.frames is not None
    wanted = step.timeout_s or (waits[0] if expects else waits[1])
    log.event("TX", step, "%s (timeout %g ms)" % (step.command, wanted * 1000.0))
    try:
        sample = dongle.command(step.command, timeout=wanted,
                                **({"frame_window": FRAME_WINDOW_S} if step.frames else {}))
    except BenchToolsError as exc:            # reported, not raised
        if not expects and _is_no_reply(exc):
            log.event("RX", step, "(no reply within %.2f s)" % wanted, SKIP)
            return _result(step, SKIP,
                           "no reply within %.2f s, and the document expected none" % wanted,
                           command=step.command)
        reason = ("no reply within %.2f s" % wanted if _is_no_reply(exc)
                  else _first_sentence(exc))
        return _result(step, ERROR, "%s (%s)" % (reason, type(exc).__name__),
                       command=step.command, expected=step.expected)

    elapsed, clock = _elapsed(sample)
    response = sample.text.strip()
    rx = "%s (%.3f ms, %s clock)" % (response, elapsed * 1000.0, clock)
    if step.frames is not None:
        return _frames_result(step, sample, response, (elapsed, clock, rx), log)
    if not step.expects_response:
        log.event("RX", step, rx, SKIP)
        return _result(step, SKIP, "the document gives no expected response",
                       command=step.command, response=response,
                       elapsed_s=elapsed, clock=clock)

    matched = step.matches(response)
    log.event("RX", step, rx, PASS if matched else FAIL)
    return _result(step, PASS if matched else FAIL,
                   "" if matched else "the reply does not match the expected response",
                   command=step.command, response=response, expected=step.expected,
                   elapsed_s=elapsed, clock=clock)


def _frames_result(step: ScriptStep, sample, response: str, timing,
                   log: EventLog) -> StepResult:
    """A step with a Frames cell: the count must match, and the reply too if one is expected."""
    elapsed, clock, rx = timing
    extra = [frame.decode("utf-8", "replace").strip() for frame in sample.extra_frames]
    counted = sample.frames == step.frames
    matched = step.matches(response) if step.expects_response else True
    result = PASS if counted and matched else FAIL
    log.event("RX", step, rx, result)
    for index, frame in enumerate(extra, start=2):
        log.event("RX", step, "frame %d: %s" % (index, frame), result)
    reasons = []
    if not counted:
        reasons.append("%d reply frame(s), expected %d%s" % (
            sample.frames, step.frames, (": then " + " / ".join(extra)) if extra else ""))
    if not matched:
        reasons.append("the reply does not match the expected response")
    return _result(step, result, "; ".join(reasons) or "%d reply frame(s)" % sample.frames,
                   command=step.command, response=response, expected=step.expected,
                   elapsed_s=elapsed, clock=clock)


def _elapsed(sample):
    """The exchange time and which clock measured it."""
    if sample.dongle_us is not None:
        return sample.dongle_us / 1.0e6, "dongle"
    return sample.host_s, "host"


def _sensor_name(dongle) -> str:
    """Which sensor the run talked to, for the report's header."""
    selected = getattr(dongle, "selected", None)
    if selected is None:
        return ""
    name = getattr(selected, "name", "") or ""
    address = getattr(selected, "address", "") or ""
    return ("%s %s" % (name, address)).strip()


def _note(dongle, text: str) -> None:
    """Mark the session log, so the log and the report read together."""
    note = getattr(dongle, "log_note", None)
    if callable(note):
        note(text)
