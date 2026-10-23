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
  its name (any case), and opens the link. A document that connects closes the
  link again when it ends.
* ``disconnect`` closes the link.

Every step gets one of four results, decided in this order - the first that
applies wins:

1. **Error** - the system returned a failure code: the dongle refused the
   command, a connect or disconnect failed, the link or the transport failed,
   or no reply came to a command that expected one.
2. **Skip** - the expected cell is empty: a delay, a connect or disconnect that
   worked, or a command the document promised nothing for (whatever it
   answered, or its silence, is recorded).
3. **Fail** - the reply does not match the expected response.
4. **Pass** - the reply matches.

A run is **ERROR** if any step errored, else **FAIL** if any failed, else
**PASS**. Skips neither fail a run nor vouch for it. Each result carries a note:
why it came out as it did, and the document's own Notes cell.

An expected response of ``<disconnect>`` says the sensor will drop the link
after the command - a reset, say. The command is sent without waiting for a
reply, and the time from sending it to the disconnection is measured on the
dongle's clock. **Pass** if the link drops within the step's timeout, **fail**
if it does not.

A ``Frames`` column says how many reply frames - notifications - a command must
produce, usually 1: a sensor that answers twice leaves every later command
reading the previous one's reply. A step with a Frames cell makes a claim even
with no expected response. The extra frames are logged.

A ``Save`` column names a variable to keep the step's reply in, for later
steps to use as ``${NAME}`` - a value read before an action, compared with the
one read after it. A pattern with a named group saves just that part of the
reply. A reply is saved when it passed its check, or when nothing was expected
of it; a later step whose saved value was never captured is an error.

A ``Timeout`` column, in milliseconds, sets how long a step waits: for the reply
to a command, for the listening window of a command that expects none, for the
link to drop, or for a ``connect`` to find its sensor. Empty means the
document's timeout for the command's prefix, if it gives one, else the run's
default. A delay or a disconnect cannot have one.

Command families often answer at very different speeds - a write that keeps the
sensor busy for seconds, a read that answers at once. A document may declare a
timeout by command prefix, in a table before its first step, rather than write
the same value into every row::

    | Command prefix | Timeout (ms)     |
    |----------------|------------------|
    | WR             | ${WR_TIMEOUT_MS} |
    | ROUTINE        | 45000            |
    | RD             | 500              |
    | RD EOL         | 5000             |

A prefix matches the start of a command sent to the sensor, ignoring case; the
longest one that matches wins, so ``RD EOL`` above overrides ``RD``. It is the
reply timeout for a command with an expected response, the listening window for
one with none, and the time allowed for a ``<disconnect>``. A step's own Timeout
cell still wins over it, and it wins over the run's default. A run can override
or add to the table with ``--timeout PREFIX=MS``. Each result says which timeout
applied, and why.

The steps that talk to the sensor:

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

Running a document, its results and its event log are in
:mod:`~benchtools.instruments.nordic_dongle.script_run`.

Traces to: BLE-FR-100 .. BLE-FR-108, BLE-FR-119, BLE-DD-SCRIPT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ...core.errors import ConfigurationError

__all__ = [
    "COMMAND",
    "CONNECT",
    "DELAY",
    "DISCONNECT",
    "ERROR",
    "PASS",
    "FAIL",
    "SKIP",
    "RESOLUTION_S",
    "CommandScript",
    "PrefixTimeout",
    "ScriptStep",
    "ScriptTest",
    "load_script",
    "longest_prefix",
    "parse_script",
]

#: Step and run outcomes. Plain strings rather than the runner's enumeration:
#: an instrument may not import the runner (CORE-NFR-009), and these end up in
#: a document a person reads.
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
ERROR = "ERROR"

#: Resolution the elapsed time is reported at, in seconds. The dongle times the
#: exchange on its microsecond clock; this is the granularity the report quotes,
#: and the measured figure is kept beside it rather than thrown away.
RESOLUTION_S = 0.01

#: ``delay 250``, or ``delay 250 ms``: a pause, not a command.
_DELAY = re.compile(r"^delay\s+(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*(?:ms|msec)?$", re.I)

#: ``connect <sensor>`` and ``disconnect``: steps for the dongle, not the sensor.
_CONNECT = re.compile(r"^connect(?:\s+(?P<target>\S.*))?$", re.I)
_DISCONNECT = re.compile(r"^disconnect$", re.I)

#: ``<disconnect>`` in the expected cell: the sensor drops the link.
_DISCONNECT_EXPECTED = re.compile(r"^<\s*disconnect\s*>$", re.I)

#: A timeout cell: milliseconds, optionally written with the unit.
_TIMEOUT = re.compile(r"^(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*(?:ms|msec)?$", re.I)

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
    "note": ("note", "notes", "comment", "comments"),
    "timeout": ("timeout", "timeout (ms)", "timeout ms", "timeout_ms"),
    "frames": ("frames", "reply frames", "frame count"),
    "save": ("save", "save as", "save to"),
}

#: Column headings of the variables table.
_VARIABLE_COLUMNS = {
    "variable": ("variable", "name"),
    "default": ("default", "value", "default value"),
}

#: Column headings of the timeouts-by-prefix table. Its Timeout heading is a
#: step table's too, so the Command prefix heading is what tells them apart.
_PREFIX_COLUMNS = {
    "prefix": ("command prefix", "prefix"),
    "timeout": _COLUMNS["timeout"],
}

#: Where a step's timeout came from when its own Timeout cell set it.
TIMEOUT_CELL = "Timeout cell"


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
    :param timeout_s: Seconds the step waits, from its Timeout cell or the
        document's timeout for its prefix; None for the run's default.
    :param timeout_from: Where *timeout_s* came from, as the result reports it.
    """

    test: str
    number: str
    command: str = ""
    expected: str = ""
    delay_s: Optional[float] = None
    line: int = 0
    action: str = COMMAND
    target: str = ""
    note: str = ""
    timeout_s: Optional[float] = None
    frames: Optional[int] = None
    save: str = ""
    timeout_from: str = ""

    @property
    def is_delay(self) -> bool:
        """Whether this step waits rather than acts."""
        return self.delay_s is not None

    @property
    def expects_disconnect(self) -> bool:
        """Whether the sensor is expected to drop the link after this command."""
        return self.action == COMMAND and bool(_DISCONNECT_EXPECTED.match(self.expected.strip()))

    @property
    def expects_response(self) -> bool:
        """Whether this step sends a command and checks the reply."""
        return self.action == COMMAND and bool(self.expected) and not self.expects_disconnect

    @property
    def makes_claim(self) -> bool:
        """Whether this step can pass or fail: it expects a response, a frame count, or a drop."""
        return self.expects_response or self.expects_disconnect or self.frames is not None

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
        """The step as a person would name it: test and number."""
        return "%s step %s" % (self.test, self.number)


@dataclass(frozen=True)
class PrefixTimeout:
    """A timeout for every command that starts with *prefix*, ignoring case.

    :param prefix: The start of the command, as written.
    :param timeout_s: Seconds a matching command waits.
    :param origin: ``document`` for the document's own table, ``--timeout``
        for a value given for the run.
    """

    prefix: str
    timeout_s: float
    origin: str = "document"

    def matches(self, command: str) -> bool:
        """Whether *command* starts with this prefix, ignoring case."""
        return command.strip().lower().startswith(self.prefix.lower())

    def describe(self) -> str:
        """Why a step waited this long, for its result."""
        return "prefix %s (%s)" % (self.prefix, self.origin)


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
    #: The timeouts by command prefix the steps were given.
    timeouts: Sequence[PrefixTimeout] = ()

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
    """The cells of a markdown table row, without the outer pipes.

    A cell is split only at an unescaped pipe. ``\\|`` is a literal pipe in the
    cell's text - a regular expression's alternation, say - as in GitHub's
    markdown; a backslash before anything else is kept as written, so ``\\.``
    and ``\\b`` in a pattern are untouched.
    """
    text = row.strip()
    if text.startswith("|"):
        text = text[1:]
    cells: List[str] = []
    current: List[str] = []
    escaped = False
    closed = False                         # the row ended on an unescaped pipe
    for character in text:
        closed = False
        if escaped:
            current.append(character if character == "|" else "\\" + character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current))
            current = []
            closed = True
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    if not closed:
        cells.append("".join(current))
    return [cell.strip() for cell in cells]


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


def _substitute(text: str, values: Mapping[str, Optional[str]], where: str,
                deferred: Sequence[str] = ()) -> str:
    """Replace every ``${NAME}`` in *text*.

    Names in *deferred* - replies an earlier row saves - are left in place for
    the run to fill in when it reaches the step.

    :raises ConfigurationError: for a name the document does not declare, or
        one declared without a default and not given a value.
    """
    def value_of(match) -> str:
        name = match.group("name")
        if name in deferred:
            return match.group(0)
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

    return _VARIABLE.sub(value_of, text)


def _prefix_columns(headings: Sequence[str]) -> Optional[Dict[str, int]]:
    """Columns of a timeouts-by-prefix table, or None when the table is not one."""
    found: Dict[str, int] = {}
    for position, heading in enumerate(headings):
        name = heading.strip().lower().rstrip(":")
        for column, accepted in _PREFIX_COLUMNS.items():
            if name in accepted and column not in found:
                found[column] = position
    return found if "prefix" in found else None


def longest_prefix(timeouts: Sequence[PrefixTimeout], command: str) -> Optional[PrefixTimeout]:
    """The longest prefix in *timeouts* that *command* starts with, or None."""
    matching = [item for item in timeouts if item.matches(command)]
    return max(matching, key=lambda item: len(item.prefix)) if matching else None


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


class _Reader:  # pylint: disable=too-many-instance-attributes
    """State while reading one document, so each kind of row has one place."""

    def __init__(self, label: str, overrides: Mapping[str, str],
                 timeouts: Mapping[str, object]) -> None:
        self.label = label
        self.overrides = dict(overrides)
        #: Timeouts by prefix given for the run, applied when the variables bind.
        self.given_timeouts = dict(timeouts)
        #: The document's prefix table rows as written: prefix, timeout, where.
        self.prefix_rows: List[Tuple[str, str, str]] = []
        self.timeouts: List[PrefixTimeout] = []
        self.declared: Dict[str, Optional[str]] = {}
        self.bound = False
        self.saved: List[str] = []          # names earlier rows save replies in
        self.tests: List[ScriptTest] = []
        self.heading: Optional[str] = None
        self.steps: List[ScriptStep] = []
        self.numbers: Dict[str, int] = {}
        #: What the table being read is: None between tables, else "steps",
        #: "variables", "timeouts" or "prose".
        self.mode: Optional[str] = None
        self.columns: Dict[str, int] = {}
        self.width = 0

    # -- structure ---------------------------------------------------------
    def close(self) -> None:
        """Finish the test being read, if it has steps."""
        if self.heading is not None and self.steps:
            self.tests.append(ScriptTest(name=self.heading, steps=tuple(self.steps)))

    def start_test(self, title: str) -> None:
        """Begin the test a heading names."""
        self.close()
        self.heading = title
        self.steps, self.numbers = [], {}
        self.mode = None

    def end_table(self) -> None:
        """Note that a table has ended, so the next one is read afresh."""
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
        self.timeouts = self.resolve_timeouts()

    def resolve_timeouts(self) -> List[PrefixTimeout]:
        """The prefix table, variables substituted, with the run's values over it.

        Resolved when the variables bind, so a ``--var`` value reaches a
        timeout written as ``${NAME}``.
        """
        table: Dict[str, PrefixTimeout] = {}
        for prefix, text, where in self.prefix_rows:
            prefix = _substitute(prefix, self.declared, where).strip()
            if not prefix:
                raise ConfigurationError(
                    "%s: the row has no command prefix. A timeout for every "
                    "command is the run's default, --timeout-s." % where)
            if prefix.lower() in table:
                raise ConfigurationError(
                    "%s: the prefix %s is given a timeout twice (prefixes ignore "
                    "case)." % (where, prefix))
            seconds = _prefix_seconds(_substitute(text, self.declared, where), where)
            table[prefix.lower()] = PrefixTimeout(prefix, seconds)
        for prefix, value in self.given_timeouts.items():
            where = "--timeout %s=%s" % (prefix, value)
            prefix = str(prefix).strip()
            if not prefix:
                raise ConfigurationError("%s: the command prefix is empty." % where)
            table[prefix.lower()] = PrefixTimeout(prefix, _prefix_seconds(str(value), where),
                                                  origin="--timeout")
        return list(table.values())

    @property
    def values(self) -> Dict[str, str]:
        """The variables that have a value, as the run will use them."""
        return {name: value for name, value in self.declared.items() if value is not None}

    # -- rows --------------------------------------------------------------
    def table_row(self, line: str, stripped: str, where: str, number: int) -> None:
        """Read one line of a table, whichever kind of table it is."""
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
        elif self.mode == "timeouts":
            self.prefix_rows.append((cells[self.columns["prefix"]].strip("`").strip(),
                                     cells[self.columns["timeout"]].strip("`").strip(), where))
        else:
            self.step_row(cells, where, number)

    def table_header(self, headings: List[str], where: str) -> None:
        """Decide from its headings what kind of table this is."""
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
        prefixes = _prefix_columns(headings)
        if prefixes is not None:
            if self.bound:
                raise ConfigurationError(
                    "%s: a timeouts-by-prefix table after the first step. Put it "
                    "before the first test, so every step it covers sees it." % where
                )
            if "timeout" not in prefixes:
                raise ConfigurationError(
                    "%s: a Command prefix table needs a 'Timeout (ms)' column; it "
                    "has %s." % (where, ", ".join(repr(item) for item in headings))
                )
            self.mode, self.columns = "timeouts", prefixes
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
        """Declare one variable, with its default if it has one."""
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

    def save_name(self, cell: str, step: ScriptStep, where: str) -> str:
        """Check a Save cell, and make its name usable by the rows after it."""
        name = cell.strip("`").strip()
        if not _VARIABLE_NAME.match(name):
            raise ConfigurationError(
                "%s: %r is not a variable name to save a reply in." % (where, name)
            )
        if name in self.declared:
            raise ConfigurationError(
                "%s: %s is declared in the Variables table; a saved reply needs a "
                "name of its own." % (where, name)
            )
        if step.action != COMMAND or step.expects_disconnect:
            raise ConfigurationError(
                "%s: only a command's reply can be saved, not a %s step's."
                % (where, "<disconnect>" if step.expects_disconnect else step.action)
            )
        if name not in self.saved:
            self.saved.append(name)
        return name

    def apply_prefix_timeout(self, step: ScriptStep) -> ScriptStep:
        """Give a command with no Timeout cell its prefix's timeout, saying why.

        A step's own cell wins; then the longest prefix the command starts
        with; otherwise the step is left to the run's default.
        """
        if step.timeout_s is not None:
            return replace(step, timeout_from=TIMEOUT_CELL)
        if step.action != COMMAND:
            return step
        match = longest_prefix(self.timeouts, step.command)
        if match is None:
            return step
        return replace(step, timeout_s=match.timeout_s, timeout_from=match.describe())

    def step_row(self, cells: List[str], where: str, number: int) -> None:
        """Read one step, with the variables substituted."""
        self.bind(where)
        step_number = cells[self.columns["step"]]
        command = _substitute(cells[self.columns["command"]], self.declared, where, self.saved)
        expected = _substitute(cells[self.columns["expected"]], self.declared, where, self.saved)

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
        step = _interpret(ScriptStep(test=self.heading, number=step_number, command=command,
                                     expected=expected, line=number), where)
        if "note" in self.columns:
            note = _substitute(cells[self.columns["note"]], self.declared, where, self.saved)
            step = replace(step, note=note)
        if "save" in self.columns and cells[self.columns["save"]]:
            step = replace(step, save=self.save_name(cells[self.columns["save"]], step, where))
        if "timeout" in self.columns:
            text = _substitute(cells[self.columns["timeout"]], self.declared, where)
            step = replace(step, timeout_s=_parse_timeout(text, step, where))
        step = self.apply_prefix_timeout(step)
        if "frames" in self.columns and cells[self.columns["frames"]]:
            step = replace(step, frames=_parse_frames(cells[self.columns["frames"]], step, where))
        self.steps.append(step)


#: Bounds on a Timeout cell, in seconds, by what the step does.
_TIMEOUT_RANGES = {COMMAND: (0.1, 60.0), CONNECT: (1.0, 60.0)}


def _parse_timeout(text: str, step: ScriptStep, where: str) -> Optional[float]:
    """Seconds from a Timeout cell, or None when it is empty."""
    text = text.strip()
    if not text:
        return None
    if step.action not in _TIMEOUT_RANGES:
        raise ConfigurationError(
            "%s: a %s step cannot have a timeout (%r); it does not wait for "
            "anything." % (where, step.action, text)
        )
    match = _TIMEOUT.match(text)
    low, high = _TIMEOUT_RANGES[step.action]
    seconds = float(match.group("amount")) / 1000.0 if match else None
    if seconds is None or not low <= seconds <= high:
        raise ConfigurationError(
            "%s: a timeout is milliseconds from %g to %g for a %s step, not %r."
            % (where, low * 1000.0, high * 1000.0, step.action, text)
        )
    return seconds


def _prefix_seconds(text: str, where: str) -> float:
    """Seconds from a timeouts-by-prefix row; the range is a command step's."""
    match = _TIMEOUT.match(text.strip())
    low, high = _TIMEOUT_RANGES[COMMAND]
    seconds = float(match.group("amount")) / 1000.0 if match else None
    if seconds is None or not low <= seconds <= high:
        raise ConfigurationError(
            "%s: a timeout for a command prefix is milliseconds from %g to %g, "
            "not %r." % (where, low * 1000.0, high * 1000.0, text.strip())
        )
    return seconds


def _parse_frames(text: str, step: ScriptStep, where: str) -> int:
    """The number of reply frames a Frames cell requires."""
    if step.action != COMMAND or step.expects_disconnect:
        raise ConfigurationError(
            "%s: only a command's reply frames can be counted, not a %s step's."
            % (where, "<disconnect>" if step.expects_disconnect else step.action)
        )
    if not text.strip().isdigit() or int(text) < 1:
        raise ConfigurationError(
            "%s: a Frames cell is how many reply frames the command must produce, "
            "a whole number from 1, not %r." % (where, text)
        )
    return int(text)


def _interpret(row: ScriptStep, where: str) -> ScriptStep:
    """Turn one row's cells, variables already substituted, into a step.

    *row* carries the test, step number, command, expected response and line
    as read; what the step does is decided here.
    """
    test, number, line = row.test, row.number, row.line
    command, expected = row.command, row.expected
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
    timeouts: Optional[Mapping[str, object]] = None,
) -> CommandScript:
    """Read a command document.

    :param text: The document.
    :param source: Its path, for diagnostics.
    :param variables: Values for the document's variables, overriding its
        defaults - the sensor to test, typically.
    :param timeouts: Timeouts in milliseconds by command prefix, for this run:
        ``{"WR": 45000}``. Each overrides the document's own row for the same
        prefix, ignoring case, or adds one.
    :raises ConfigurationError: for anything that cannot be read as a step,
        naming the document and the line. A row this reader skipped quietly
        would be a command nobody tested and nobody missed.
    """
    label = source or "command document"
    reader = _Reader(label, variables or {}, timeouts or {})

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
    return CommandScript(tests=tuple(reader.tests), source=source, variables=reader.values,
                         timeouts=tuple(reader.timeouts))


def load_script(path: str, variables: Optional[Mapping[str, str]] = None,
                timeouts: Optional[Mapping[str, object]] = None) -> CommandScript:
    """Read a command document from a file, with values for its variables and
    any timeouts by command prefix given for the run."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ConfigurationError(
            "cannot read the command document %s: %s" % (path, exc)
        ) from exc
    return parse_script(text, source=path, variables=variables, timeouts=timeouts)
