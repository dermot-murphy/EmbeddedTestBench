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

A document may declare variables in a table before its first test, and use
them as ``${NAME}`` in any command, expected response or delay - Robot
Framework's own syntax, so a row converts to a keyword call as written::

    | Variable  | Default | Notes              |
    |-----------|---------|--------------------|
    | SENSOR_ID |         | required: no default |
    | SETTLE_MS | 500     |                    |

A variable with no default must be given a value when the document is run
(``--var SENSOR_ID=kappa``); one that is used but not declared, or given but
not declared, is an error naming the line.

Two steps act on the dongle rather than the sensor:

* ``connect <sensor>`` scans, selects the sensor by address or by a fragment of
  its name (any case), and opens the link. **Pass** or **fail**: it is the
  claim that the sensor can be reached. A document that connects closes the
  link again when it ends.
* ``disconnect`` closes the link. **Skip**.

Three kinds of step talk to the sensor, and only the first can fail:

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
from typing import Dict, List, Mapping, Optional, Sequence

from ...core.errors import ConfigurationError

__all__ = [
    "COMMAND",
    "CONNECT",
    "DELAY",
    "DISCONNECT",
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

#: ``connect <sensor>`` and ``disconnect``: steps for the dongle, not the sensor.
_CONNECT = re.compile(r"^connect(?:\s+(?P<target>\S.*))?$", re.I)
_DISCONNECT = re.compile(r"^disconnect$", re.I)

#: A Bluetooth address, optionally with its type: ``D1:8D:3B:4C:19:96/1``.
_ADDRESS = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}(?:/[0-9])?$")

#: ``${NAME}``: a variable, as Robot Framework writes one.
_VARIABLE = re.compile(r"\$\{(?P<name>[^}]*)\}")
_VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: What a step does. A plain command is the default.
COMMAND = "command"
DELAY = "delay"
CONNECT = "connect"
DISCONNECT = "disconnect"

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

#: Column headings of the variables table.
_VARIABLE_COLUMNS = {
    "variable": ("variable", "name"),
    "default": ("default", "value", "default value"),
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
    :param action: What the step does: :data:`COMMAND`, :data:`DELAY`,
        :data:`CONNECT` or :data:`DISCONNECT`.
    :param target: The sensor a ``connect`` step names.
    """

    test: str
    number: str
    command: str = ""
    expected: str = ""
    delay_s: Optional[float] = None
    line: int = 0
    action: str = COMMAND
    target: str = ""

    @property
    def is_delay(self) -> bool:
        return self.delay_s is not None

    @property
    def expects_response(self) -> bool:
        """Whether this step sends a command and checks the reply."""
        return self.action == COMMAND and bool(self.expected)

    @property
    def makes_claim(self) -> bool:
        """Whether this step can fail: a checked command, or a connect."""
        return self.expects_response or self.action == CONNECT

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
    variables: Mapping[str, str] = field(default_factory=dict)

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
        return sum(1 for step in self.steps if step.makes_claim)

    @property
    def connects(self) -> bool:
        """Whether the document opens its own link before its first command."""
        for step in self.steps:
            if step.action == CONNECT:
                return True
            if step.action == COMMAND:
                return False
        return False

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


def _variable_columns(headings: Sequence[str]) -> Optional[Dict[str, int]]:
    """Columns of a variables table, or None when the table is not one."""
    found: Dict[str, int] = {}
    for position, heading in enumerate(headings):
        name = heading.strip().lower().rstrip(":")
        for column, accepted in _VARIABLE_COLUMNS.items():
            if name in accepted and column not in found:
                found[column] = position
    return found if "variable" in found else None


def _substitute(text: str, values: Mapping[str, Optional[str]], where: str) -> str:
    """Replace every ``${NAME}`` in *text*.

    :raises ConfigurationError: for a name the document does not declare, or
        one declared without a default and not given a value.
    """
    def replace(match) -> str:
        name = match.group("name")
        if name not in values:
            raise ConfigurationError(
                "%s: ${%s} is not declared. Add it to the | Variable | Default | "
                "table at the top of the document." % (where, name)
            )
        value = values[name]
        if value is None:
            raise ConfigurationError(
                "%s: ${%s} has no default and was not given a value. Run with "
                "--var %s=<value>." % (where, name, name)
            )
        return value

    return _VARIABLE.sub(replace, text)


def _is_step_table(headings: Sequence[str]) -> bool:
    """Whether a table claims to hold steps: it names any step column.

    One that names some but not all of them is a step table with a mistake in
    it, and is refused rather than skipped - a skipped table is a set of
    commands nobody tested and nobody missed. A table naming none of them is
    prose (a legend, a conversion table) and is left alone.
    """
    for heading in headings:
        name = heading.strip().lower().rstrip(":")
        if any(name in accepted for accepted in _COLUMNS.values()):
            return True
    return False


class _Reader:
    """State while reading one document, so each kind of row has one place."""

    def __init__(self, label: str, overrides: Mapping[str, str]) -> None:
        self.label = label
        self.overrides = dict(overrides)
        self.declared: Dict[str, Optional[str]] = {}
        self.bound = False
        self.tests: List[ScriptTest] = []
        self.heading: Optional[str] = None
        self.steps: List[ScriptStep] = []
        self.numbers: Dict[str, int] = {}
        #: What the table being read is: None between tables, else "steps",
        #: "variables" or "prose".
        self.mode: Optional[str] = None
        self.columns: Dict[str, int] = {}
        self.width = 0

    # -- structure ---------------------------------------------------------
    def close(self) -> None:
        if self.heading is not None and self.steps:
            self.tests.append(ScriptTest(name=self.heading, steps=tuple(self.steps)))

    def start_test(self, title: str) -> None:
        self.close()
        self.heading = title
        self.steps, self.numbers = [], {}
        self.mode = None

    def end_table(self) -> None:
        self.mode = None

    def bind(self, where: str) -> None:
        """Apply the values given for the run, once, before the first step."""
        if self.bound:
            return
        self.bound = True
        unknown = sorted(set(self.overrides) - set(self.declared))
        if unknown:
            raise ConfigurationError(
                "%s: a value was given for %s, which the document does not "
                "declare. Declared: %s."
                % (where, ", ".join(unknown), ", ".join(sorted(self.declared)) or "none")
            )
        self.declared.update(self.overrides)

    @property
    def values(self) -> Dict[str, str]:
        return {name: value for name, value in self.declared.items() if value is not None}

    # -- rows --------------------------------------------------------------
    def table_row(self, line: str, stripped: str, where: str, number: int) -> None:
        if self.mode is None:
            self.table_header(_cells(line), where)
            return
        if self.mode == "prose" or _SEPARATOR.match(stripped):
            return
        cells = _cells(line)
        if len(cells) != self.width:
            raise ConfigurationError(
                "%s: the row has %d cell(s) and the table has %d column(s). A "
                "pipe inside a command or a response needs escaping as \\|."
                % (where, len(cells), self.width)
            )
        if self.mode == "variables":
            self.variable_row(cells, where)
        else:
            self.step_row(cells, where, number)

    def table_header(self, headings: List[str], where: str) -> None:
        self.width = len(headings)
        variables = _variable_columns(headings)
        if variables is not None:
            if self.bound:
                raise ConfigurationError(
                    "%s: a variables table after the first step. Declare every "
                    "variable before any step uses one." % where
                )
            self.mode, self.columns = "variables", variables
            return
        if not _is_step_table(headings):
            self.mode = "prose"
            return
        if self.heading is None:
            raise ConfigurationError(
                "%s: a table before any test heading. Put the rows under a "
                "'## <test name>' heading, so every result can name its test."
                % where
            )
        self.mode, self.columns = "steps", _column_index(headings, where)

    def variable_row(self, cells: List[str], where: str) -> None:
        name = cells[self.columns["variable"]].strip("`").strip()
        if not _VARIABLE_NAME.match(name):
            raise ConfigurationError(
                "%s: %r is not a variable name. Use letters, digits and "
                "underscores, starting with a letter - SENSOR_ID, say." % (where, name)
            )
        if name in self.declared:
            raise ConfigurationError("%s: %s is declared twice." % (where, name))
        column = self.columns.get("default")
        default = cells[column].strip("`").strip() if column is not None else ""
        self.declared[name] = default if default else None

    def step_row(self, cells: List[str], where: str, number: int) -> None:
        self.bind(where)
        step_number = cells[self.columns["step"]]
        command = _substitute(cells[self.columns["command"]], self.declared, where)
        expected = _substitute(cells[self.columns["expected"]], self.declared, where)

        if not step_number:
            raise ConfigurationError(
                "%s: the row has no step number. Results are reported against "
                "it, so a row without one could not be read back." % where
            )
        if step_number in self.numbers:
            raise ConfigurationError(
                "%s: step %s is already used on line %d of this test. Two rows "
                "with one number make a result ambiguous."
                % (where, step_number, self.numbers[step_number])
            )
        self.numbers[step_number] = number
        self.steps.append(_interpret(self.heading, step_number, command, expected, where, number))


def _interpret(test: str, number: str, command: str, expected: str, where: str,
               line: int) -> ScriptStep:
    """Turn one row's cells, variables already substituted, into a step."""
    delay_s = _parse_delay(command, where)
    connect = _CONNECT.match(command)
    if expected and delay_s is not None:
        raise ConfigurationError(
            "%s: a delay cannot have an expected response (%r). A delay "
            "waits; it does not ask the sensor anything." % (where, expected)
        )
    if expected and (connect or _DISCONNECT.match(command)):
        raise ConfigurationError(
            "%s: %r cannot have an expected response (%r). It acts on the "
            "dongle; it does not ask the sensor anything. A connect passes "
            "when the link opens." % (where, command.split()[0], expected)
        )
    if delay_s is not None:
        return ScriptStep(test=test, number=number, delay_s=delay_s, line=line, action=DELAY)
    if connect:
        target = (connect.group("target") or "").strip()
        if not target:
            raise ConfigurationError(
                "%s: 'connect' names no sensor. Give an address or part of its "
                "name: connect ${SENSOR_ID}." % where
            )
        return ScriptStep(test=test, number=number, command=command, line=line,
                          action=CONNECT, target=target)
    if _DISCONNECT.match(command):
        return ScriptStep(test=test, number=number, command=command, line=line,
                          action=DISCONNECT)
    if not command:
        raise ConfigurationError(
            "%s: the row has no command. Use 'delay <milliseconds>' for a "
            "wait, or remove the row." % where
        )
    return ScriptStep(test=test, number=number, command=command, expected=expected, line=line)


def parse_script(
    text: str,
    source: str = "",
    variables: Optional[Mapping[str, str]] = None,
) -> CommandScript:
    """Read a command document.

    :param text: The document.
    :param source: Its path, for diagnostics.
    :param variables: Values for the document's variables, overriding its
        defaults - the sensor to test, typically.
    :raises ConfigurationError: for anything that cannot be read as a step,
        naming the document and the line. A row this reader skipped quietly
        would be a command nobody tested and nobody missed.
    """
    label = source or "command document"
    reader = _Reader(label, variables or {})

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        where = "%s line %d" % (label, number)
        stripped = line.strip()

        match = _HEADING.match(stripped)
        if match:
            if len(match.group("hashes")) == 1 and reader.heading is None and not reader.steps:
                continue                      # the document's own title
            reader.start_test(match.group("title"))
            continue

        if not stripped.startswith("|"):
            reader.end_table()                # prose between tables
            continue

        reader.table_row(line, stripped, where, number)

    reader.close()
    reader.bind(label)                        # a value for nothing is still an error
    if not reader.tests:
        raise ConfigurationError(
            "%s names no tests. A command document is a '## <test name>' "
            "heading followed by a table of | Step | Command | Expected "
            "response | rows." % label
        )
    return CommandScript(tests=tuple(reader.tests), source=source, variables=reader.values)


def load_script(path: str, variables: Optional[Mapping[str, str]] = None) -> CommandScript:
    """Read a command document from a file, with values for its variables."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ConfigurationError(
            "cannot read the command document %s: %s" % (path, exc)
        ) from exc
    return parse_script(text, source=path, variables=variables)


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
    variables: Mapping[str, str] = field(default_factory=dict)

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
            "variables": dict(self.variables),
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
            "| Variables | %s |" % (_cell(", ".join(
                "%s=%s" % item for item in sorted(self.variables.items()))) or "none"),
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


#: Seconds a ``connect`` step scans before choosing: long enough to hear a
#: sensor that advertises every 9 s at least once.
CONNECT_SCAN_S = 10.0

#: Connection attempts a ``connect`` step makes. A sensor that advertises rarely
#: can fall outside a connect window; each failure is in the session log.
CONNECT_ATTEMPTS = 3


def run_script(
    dongle,
    script: CommandScript,
    timeout: float = 3.0,
    listen: float = 0.5,
    sleep=time.sleep,
    scan_s: float = CONNECT_SCAN_S,
    connect_attempts: int = CONNECT_ATTEMPTS,
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

    A link a ``connect`` step opened is closed when the run ends, pass or fail.
    """
    run = ScriptRun(source=script.source, sensor=_sensor_name(dongle),
                    variables=dict(script.variables))
    opened = False
    try:
        for test in script.tests:
            _note(dongle, "script: %s" % test.name)
            for step in test.steps:
                if step.action == CONNECT:
                    result = _run_connect(dongle, step, scan_s, connect_attempts)
                    opened = opened or result.result == PASS
                    run.sensor = _sensor_name(dongle) or run.sensor
                elif step.action == DISCONNECT:
                    result = _run_disconnect(dongle, step)
                else:
                    result = _run_step(dongle, step, timeout, listen, sleep)
                run.results.append(result)
    finally:
        if opened and getattr(dongle, "is_linked", False):
            dongle.close_link()
    return run


def _run_connect(dongle, step: ScriptStep, scan_s: float, attempts: int) -> StepResult:
    """Scan, choose the sensor the step names, and open a link. Never raises."""
    started = time.perf_counter()
    try:
        if getattr(dongle, "is_linked", False):
            dongle.close_link()
        dongle.scan(scan_s, active=True)
        if _ADDRESS.match(step.target):
            dongle.select(step.target)
        else:
            dongle.select_by_name(step.target)
        failure = None
        for _ in range(max(1, attempts)):
            try:
                dongle.open_link()
                failure = None
                break
            except Exception as exc:          # noqa: BLE001 - retried, then reported
                failure = exc
        if failure is not None:
            raise failure
    except Exception as exc:                  # noqa: BLE001 - reported, not raised
        return StepResult(test=step.test, number=step.number, command=step.command,
                          result=FAIL, reason=str(exc).split(". ")[0])
    return StepResult(
        test=step.test,
        number=step.number,
        command=step.command,
        response="linked to %s" % (_sensor_name(dongle) or step.target),
        elapsed_s=time.perf_counter() - started,
        clock="host",
        result=PASS,
    )


def _run_disconnect(dongle, step: ScriptStep) -> StepResult:
    """Close the link, if one is open. Never raises."""
    try:
        dongle.close_link()
    except Exception as exc:                  # noqa: BLE001 - reported, not raised
        return StepResult(test=step.test, number=step.number, command=step.command,
                          result=SKIP, reason="disconnect failed: %s" % exc)
    return StepResult(test=step.test, number=step.number, command=step.command,
                      result=SKIP, reason="closing the link makes no claim about the sensor")


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
