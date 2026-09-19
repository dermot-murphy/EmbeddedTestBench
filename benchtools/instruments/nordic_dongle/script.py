"""A command and response test, read from the document that specifies it.

A sensor's command set is written down long before anyone tests it. Copying
that document into a test specification makes two things that must agree, and
they stop agreeing the first time someone adds a command to one of them. So the
document *is* the test: this module reads a markdown document of commands and
expected responses, runs it against a sensor, and reports each step.

The document is a heading per test, then a table::

    ## Identity

    | Step | Command    | Expected response |
    |------|------------|-------------------|
    | 1    | rd version | 1.4.2             |
    | 2    | rd id      | /^SENS-[0-9A-F]{6}$/ |
    | 3    | delay 100  |                   |
    | 4    | log start  |                   |

Three kinds of step, and only the first can fail:

* **A command with an expected response.** The reply is compared with the
  expected text, exactly, after trimming. A cell written ``/like this/`` is a
  regular expression instead, searched for in the reply - anchor it with ``^``
  and ``$`` to require the whole reply. **Pass** or **fail**.
* **A delay**, written ``delay <milliseconds>`` in the command cell. **Skip**:
  waiting is not a claim about the sensor.
* **A command with no expected response** - the expected cell is empty. The
  command is sent and anything that comes back within a short window is
  recorded, because knowing what the board said is useful even when nothing was
  promised. **Skip**: the document made no claim to check.

A run passes when no step failed. Skipped steps do not make it fail, and they
do not make it pass either - a document of nothing but delays passes, and says
so by reporting that it checked nothing.

The document is forgiving about its punctuation and strict about its content: a
row that cannot be read, a step number used twice, a delay that is not a number
are each an error naming the document and the line. These files are maintained
by hand, and a row silently ignored is a command silently untested.

Traces to: BLE-FR-100 .. BLE-FR-108, BLE-DD-SCRIPT.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ...core.errors import ConfigurationError

__all__ = [
    "PASS",
    "FAIL",
    "SKIP",
    "RESOLUTION_S",
    "CommandScript",
    "ScriptRun",
    "ScriptStep",
    "ScriptTest",
    "StepResult",
    "load_script",
    "parse_script",
]

#: Step and run outcomes. Plain strings rather than the runner's enumeration:
#: an instrument may not import the runner (CORE-NFR-009), and these end up in
#: a document a person reads.
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

#: Resolution the elapsed time is reported at, in seconds. The dongle times the
#: exchange on its microsecond clock; this is the granularity the report quotes,
#: and the measured figure is kept beside it rather than thrown away.
RESOLUTION_S = 0.01

#: ``delay 250``, or ``delay 250 ms``: a pause, not a command.
_DELAY = re.compile(r"^delay\s+(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*(?:ms|msec)?$", re.I)

#: ``/pattern/``: the expected response is a regular expression.
_PATTERN = re.compile(r"^/(?P<body>.*)/$", re.S)

#: A markdown heading. ``#`` is the document's own title; ``##`` and below name
#: a test, so a document can carry prose and still be read as a test.
_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")

#: A table separator row: ``|---|:---:|``.
_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")

#: Column headings this reader understands, by the name it uses for them.
_COLUMNS = {
    "step": ("step", "step number", "no", "#"),
    "command": ("command", "ble command", "request"),
    "expected": ("expected", "expected response", "expected reply", "response"),
}


@dataclass(frozen=True)
class ScriptStep:
    """One row of the document.

    :param test: The heading this row came under.
    :param number: The step number the document gives it, as written.
    :param command: The command to send, empty for a delay.
    :param expected: The expected response as written, empty when none.
    :param delay_s: Seconds to wait, for a delay step.
    :param line: Line in the document, for diagnostics.
    """

    test: str
    number: str
    command: str = ""
    expected: str = ""
    delay_s: Optional[float] = None
    line: int = 0

    @property
    def is_delay(self) -> bool:
        return self.delay_s is not None

    @property
    def expects_response(self) -> bool:
        """Whether this step makes a claim that can fail."""
        return not self.is_delay and bool(self.expected)

    @property
    def pattern(self) -> Optional[str]:
        """The regular expression body, when the expectation is written as one."""
        match = _PATTERN.match(self.expected.strip()) if self.expected else None
        return match.group("body") if match else None

    def matches(self, response: str) -> bool:
        """Whether *response* satisfies this step's expectation."""
        body = self.pattern
        if body is not None:
            return re.search(body, response) is not None
        return response.strip() == self.expected.strip()

    def describe(self) -> str:
        return "%s step %s" % (self.test, self.number)


@dataclass(frozen=True)
class ScriptTest:
    """One heading and the steps under it."""

    name: str
    steps: Sequence[ScriptStep] = ()


@dataclass(frozen=True)
class CommandScript:
    """A whole document: the tests it names, in the order it names them."""

    tests: Sequence[ScriptTest] = ()
    source: str = ""

    @property
    def steps(self) -> List[ScriptStep]:
        """Every step, across every test, in document order."""
        return [step for test in self.tests for step in test.steps]

    @property
    def checks(self) -> int:
        """How many steps make a claim that can fail.

        Worth knowing before a run: a document whose rows are all delays and
        fire-and-forget commands cannot fail, and a report that said "PASS"
        without saying that would be misleading.
        """
        return sum(1 for step in self.steps if step.expects_response)

    def __len__(self) -> int:
        return len(self.steps)


# ----------------------------------------------------------------------
# Reading the document
# ----------------------------------------------------------------------
def _cells(row: str) -> List[str]:
    """The cells of a markdown table row, without the outer pipes."""
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _column_index(headings: Sequence[str], where: str) -> Dict[str, int]:
    """Map this reader's column names onto the document's own headings."""
    found: Dict[str, int] = {}
    for position, heading in enumerate(headings):
        name = heading.strip().lower().rstrip(":")
        for column, accepted in _COLUMNS.items():
            if name in accepted and column not in found:
                found[column] = position
    missing = [column for column in ("step", "command", "expected") if column not in found]
    if missing:
        raise ConfigurationError(
            "%s: the table needs %s column(s); it has %s. Columns are matched by "
            "name, so extra ones (notes, requirement) are kept out of the way."
            % (where, ", ".join(missing), ", ".join(repr(item) for item in headings))
        )
    return found


def _parse_delay(text: str, where: str) -> Optional[float]:
    """Seconds for a delay command, or None when this is not one."""
    match = _DELAY.match(text.strip())
    if match is None:
        return None
    amount = float(match.group("amount"))
    if amount <= 0:
        raise ConfigurationError(
            "%s: a delay of %s ms is not a wait. Remove the row or give it a "
            "positive duration." % (where, match.group("amount"))
        )
    return amount / 1000.0


def parse_script(text: str, source: str = "") -> CommandScript:
    """Read a command document.

    :param text: The document.
    :param source: Its path, for diagnostics.
    :raises ConfigurationError: for anything that cannot be read as a step,
        naming the document and the line. A row this reader skipped quietly
        would be a command nobody tested and nobody missed.
    """
    label = source or "command document"
    tests: List[ScriptTest] = []
    heading: Optional[str] = None
    steps: List[ScriptStep] = []
    numbers: Dict[str, int] = {}
    columns: Optional[Dict[str, int]] = None
    width = 0

    def close() -> None:
        if heading is not None and steps:
            tests.append(ScriptTest(name=heading, steps=tuple(steps)))

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        where = "%s line %d" % (label, number)
        stripped = line.strip()

        match = _HEADING.match(stripped)
        if match:
            if len(match.group("hashes")) == 1 and heading is None and not steps:
                continue                      # the document's own title
            close()
            heading = match.group("title")
            steps, numbers, columns = [], {}, None
            continue

        if not stripped.startswith("|"):
            continue                          # prose between tables

        if heading is None:
            raise ConfigurationError(
                "%s: a table before any test heading. Put the rows under a "
                "'## <test name>' heading, so every result can name its test."
                % where
            )

        if columns is None:
            columns = _column_index(_cells(line), where)
            width = len(_cells(line))
            continue

        if _SEPARATOR.match(stripped):
            continue

        cells = _cells(line)
        if len(cells) != width:
            raise ConfigurationError(
                "%s: the row has %d cell(s) and the table has %d column(s). A "
                "pipe inside a command or a response needs escaping as \\|."
                % (where, len(cells), width)
            )

        step_number = cells[columns["step"]]
        command = cells[columns["command"]]
        expected = cells[columns["expected"]]

        if not step_number:
            raise ConfigurationError(
                "%s: the row has no step number. Results are reported against "
                "it, so a row without one could not be read back." % where
            )
        if step_number in numbers:
            raise ConfigurationError(
                "%s: step %s is already used on line %d of this test. Two rows "
                "with one number make a result ambiguous."
                % (where, step_number, numbers[step_number])
            )
        numbers[step_number] = number

        delay_s = _parse_delay(command, where)
        if delay_s is not None:
            if expected:
                raise ConfigurationError(
                    "%s: a delay cannot have an expected response (%r). A delay "
                    "waits; it does not ask the sensor anything."
                    % (where, expected)
                )
        elif not command:
            raise ConfigurationError(
                "%s: the row has no command. Use 'delay <milliseconds>' for a "
                "wait, or remove the row." % where
            )

        steps.append(
            ScriptStep(
                test=heading,
                number=step_number,
                command="" if delay_s is not None else command,
                expected=expected,
                delay_s=delay_s,
                line=number,
            )
        )

    close()
    if not tests:
        raise ConfigurationError(
            "%s names no tests. A command document is a '## <test name>' "
            "heading followed by a table of | Step | Command | Expected "
            "response | rows." % label
        )
    return CommandScript(tests=tuple(tests), source=source)


def load_script(path: str) -> CommandScript:
    """Read a command document from a file."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ConfigurationError(
            "cannot read the command document %s: %s" % (path, exc)
        ) from exc
    return parse_script(text, source=path)


# ----------------------------------------------------------------------
# Running it
# ----------------------------------------------------------------------
@dataclass
class StepResult:
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

    @property
    def reported_s(self) -> Optional[float]:
        """The elapsed time at the resolution this report quotes."""
        if self.elapsed_s is None:
            return None
        return round(round(self.elapsed_s / RESOLUTION_S) * RESOLUTION_S, 3)

    def as_dict(self) -> Dict[str, object]:
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
        }


@dataclass
class ScriptRun:
    """Every step of one run of a document, and the verdict over them."""

    results: List[StepResult] = field(default_factory=list)
    source: str = ""
    sensor: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.result == PASS)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.results if item.result == FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.results if item.result == SKIP)

    @property
    def result(self) -> str:
        """**Pass** when no step failed.

        Skipped steps neither fail a run nor vouch for it, which is why the
        report states how many steps were checked as well as how many passed.
        """
        return FAIL if self.failed else PASS

    @property
    def is_pass(self) -> bool:
        """The verdict as a number a limit can check: 1 when it passed."""
        return self.result == PASS

    @property
    def failures(self) -> List[StepResult]:
        return [item for item in self.results if item.result == FAIL]

    def as_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "sensor": self.sensor,
            "result": self.result,
            "passed": self.passed,
            "failed": self.failed,
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
            "| Steps | %d passed, %d failed, %d skipped |"
            % (self.passed, self.failed, self.skipped),
            "",
            "Times are from the end of the command to the start of the response, "
            "quoted to %g ms. A skipped step made no claim: a delay, or a command "
            "the document gives no expected response for."
            % (RESOLUTION_S * 1000.0),
            "",
            "| Test | Step | Command | Response | Expected | Time (s) | Result |",
            "|---|---|---|---|---|---|---|",
        ]
        for item in self.results:
            seconds = "-" if item.reported_s is None else "%.2f" % item.reported_s
            lines.append(
                "| %s | %s | %s | %s | %s | %s | %s |"
                % (
                    item.test,
                    item.number,
                    _cell(item.command) or "_delay_",
                    _cell(item.response),
                    _cell(item.expected),
                    seconds,
                    item.result,
                )
            )
        if self.failures:
            lines += ["", "## Failures", ""]
            for item in self.failures:
                lines.append(
                    "- **%s step %s** `%s`: expected `%s`, got `%s`%s"
                    % (
                        item.test,
                        item.number,
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


def run_script(
    dongle,
    script: CommandScript,
    timeout: float = 3.0,
    listen: float = 0.5,
    sleep=time.sleep,
) -> ScriptRun:
    """Run *script* against a connected *dongle*, one step at a time.

    :param dongle: A :class:`~benchtools.instruments.nordic_dongle.NordicDongle`
        with a link open to the sensor.
    :param timeout: Seconds to wait for a reply the document expects. A step
        that times out **fails**: the document said the sensor would answer.
    :param listen: Seconds to wait after a command the document expects no
        reply to. Whatever arrives is recorded and the step is still skipped.
    :param sleep: Injected for the tests, which must not wait in real time.
    """
    run = ScriptRun(source=script.source, sensor=_sensor_name(dongle))
    for test in script.tests:
        _note(dongle, "script: %s" % test.name)
        for step in test.steps:
            run.results.append(_run_step(dongle, step, timeout, listen, sleep))
    return run


def _run_step(dongle, step: ScriptStep, timeout: float, listen: float, sleep) -> StepResult:
    """Execute one step. Never raises: a step's outcome is its result."""
    if step.is_delay:
        sleep(step.delay_s)
        return StepResult(
            test=step.test,
            number=step.number,
            command="delay %g ms" % (step.delay_s * 1000.0),
            elapsed_s=step.delay_s,
            clock="requested",
            result=SKIP,
            reason="a delay makes no claim about the sensor",
        )

    wanted = timeout if step.expects_response else listen
    try:
        sample = dongle.command(step.command, timeout=wanted)
    except Exception as exc:                 # noqa: BLE001 - reported, not raised
        if step.expects_response:
            return StepResult(
                test=step.test,
                number=step.number,
                command=step.command,
                expected=step.expected,
                result=FAIL,
                reason="no reply within %.2f s (%s)" % (wanted, type(exc).__name__),
            )
        return StepResult(
            test=step.test,
            number=step.number,
            command=step.command,
            result=SKIP,
            reason="no reply within %.2f s, and the document expected none" % wanted,
        )

    elapsed, clock = _elapsed(sample)
    response = sample.text.strip()
    if not step.expects_response:
        return StepResult(
            test=step.test,
            number=step.number,
            command=step.command,
            response=response,
            elapsed_s=elapsed,
            clock=clock,
            result=SKIP,
            reason="the document gives no expected response",
        )

    matched = step.matches(response)
    return StepResult(
        test=step.test,
        number=step.number,
        command=step.command,
        response=response,
        expected=step.expected,
        elapsed_s=elapsed,
        clock=clock,
        result=PASS if matched else FAIL,
        reason="" if matched else "the reply does not match the expected response",
    )


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
