"""GDB/MI record parsing.

The machine interface is GDB's stable, parseable output mode. Its grammar is
small but has three details that catch naive parsers, all of which this module
handles explicitly:

1. **A list may contain results, not just values.** ``stack=[frame={...},
   frame={...}]`` repeats the key ``frame``. A parser that builds a dict here
   silently keeps only the last frame - which looks like a working backtrace of
   depth one.
2. **C-string escapes.** Stream output arrives as escaped C strings, including
   octal escapes for non-ASCII bytes. Unescaping wrongly corrupts every RTT
   line and every error message.
3. **Records are interleaved.** A command's result may be preceded by console,
   log and asynchronous records, and ``*stopped`` can arrive at any time -
   including while a different command is in flight.

Grammar implemented (GDB manual, "GDB/MI Output Syntax")::

    output            -> ( out-of-band-record )* [ result-record ] "(gdb)"
    result-record     -> [ token ] "^" result-class ( "," result )*
    out-of-band-record-> async-record | stream-record
    async-record      -> [ token ] ( "*" | "+" | "=" ) async-class ( "," result )*
    stream-record     -> ( "~" | "@" | "&" ) c-string
    result            -> variable "=" value
    value             -> c-string | "{" ... "}" | "[" ... "]"

Traces to: JLINK-FR-001, JLINK-DD-GDBMI.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ...core.errors import ProtocolError

__all__ = [
    "RecordKind",
    "Record",
    "ResultRecord",
    "AsyncRecord",
    "StreamRecord",
    "PromptRecord",
    "parse_line",
    "parse_value",
    "unescape_cstring",
]

#: GDB prints this once it is ready for the next command.
PROMPT = "(gdb)"


class RecordKind(str, enum.Enum):
    """Which of the MI record types a line is."""

    RESULT = "result"          # ^done, ^error, ...
    EXEC = "exec"              # *stopped, *running
    STATUS = "status"          # +download
    NOTIFY = "notify"          # =thread-group-added
    CONSOLE = "console"        # ~"text"
    TARGET = "target"          # @"text"
    LOG = "log"                # &"text"
    PROMPT = "prompt"          # (gdb)


@dataclass(frozen=True)
class Record:
    """Base class for a parsed MI record."""

    kind: RecordKind


@dataclass(frozen=True)
class ResultRecord(Record):
    """A synchronous result: ``^done``, ``^error``, ``^running`` and friends.

    :param message: The result class, e.g. ``"done"`` or ``"error"``.
    :param results: Parsed key/value results accompanying it.
    :param token: The command token GDB echoes back, when one was sent.
    """

    message: str = ""
    results: Dict[str, Any] = field(default_factory=dict)
    token: Optional[int] = None

    @property
    def is_error(self) -> bool:
        """``True`` for ``^error``."""
        return self.message == "error"

    @property
    def error_message(self) -> str:
        """The ``msg`` result of an ``^error`` record, if present."""
        value = self.results.get("msg", "")
        return value if isinstance(value, str) else str(value)


@dataclass(frozen=True)
class AsyncRecord(Record):
    """An asynchronous notification: ``*stopped``, ``=thread-exited``, ``+download``.

    :param message: The async class, e.g. ``"stopped"``.
    """

    message: str = ""
    results: Dict[str, Any] = field(default_factory=dict)
    token: Optional[int] = None


@dataclass(frozen=True)
class StreamRecord(Record):
    """Free text from GDB (``~``), the target (``@``) or GDB's log (``&``)."""

    text: str = ""


@dataclass(frozen=True)
class PromptRecord(Record):
    """The ``(gdb)`` prompt, which terminates a command's output."""


# ---------------------------------------------------------------------------
# C-string unescaping
# ---------------------------------------------------------------------------
_SIMPLE_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b",
    "f": "\f", "v": "\v", '"': '"', "\\": "\\", "'": "'", "0": "\0",
}


def unescape_cstring(text: str) -> str:
    """Unescape the body of an MI C-string.

    Handles the simple escapes and octal escapes (``\\NNN``). An unrecognised
    escape is passed through with its backslash, which is what GDB itself does
    and keeps Windows paths in log output readable.
    """
    out: List[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char != "\\":
            out.append(char)
            index += 1
            continue
        index += 1
        if index >= length:
            out.append("\\")
            break
        escape = text[index]
        # Octal: up to three digits. Checked before the simple table so that
        # "\0" followed by more digits is read as one octal byte.
        if escape.isdigit() and escape in "01234567":
            digits = ""
            while index < length and len(digits) < 3 and text[index] in "01234567":
                digits += text[index]
                index += 1
            out.append(chr(int(digits, 8)))
            continue
        if escape in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[escape])
            index += 1
            continue
        out.append("\\")
        out.append(escape)
        index += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------
class _Cursor:
    """A position in a line being parsed."""

    __slots__ = ("text", "pos")

    def __init__(self, text: str, pos: int = 0) -> None:
        self.text = text
        self.pos = pos

    @property
    def at_end(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def take(self) -> str:
        char = self.peek()
        self.pos += 1
        return char

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise ProtocolError(
                "malformed MI output: expected %r at offset %d of %r"
                % (char, self.pos, self.text)
            )
        self.pos += 1


def _parse_cstring(cursor: _Cursor) -> str:
    cursor.expect('"')
    start = cursor.pos
    while True:
        if cursor.at_end:
            raise ProtocolError("unterminated MI string in %r" % cursor.text)
        char = cursor.take()
        if char == "\\":
            if cursor.at_end:
                raise ProtocolError("unterminated MI escape in %r" % cursor.text)
            cursor.take()
            continue
        if char == '"':
            return unescape_cstring(cursor.text[start : cursor.pos - 1])


def _parse_variable(cursor: _Cursor) -> str:
    start = cursor.pos
    while not cursor.at_end and cursor.peek() not in "=":
        cursor.take()
    name = cursor.text[start : cursor.pos]
    if not name:
        raise ProtocolError("empty MI result name in %r" % cursor.text)
    return name


def _parse_tuple(cursor: _Cursor) -> Dict[str, Any]:
    cursor.expect("{")
    values: Dict[str, Any] = {}
    if cursor.peek() == "}":
        cursor.take()
        return values
    while True:
        name, value = _parse_result(cursor)
        values[name] = value
        if cursor.peek() == ",":
            cursor.take()
            continue
        cursor.expect("}")
        return values


def _parse_list(cursor: _Cursor) -> Union[List[Any], Dict[str, Any]]:
    """Parse an MI list, which may hold bare values or named results.

    A list of results with one repeated name - ``[frame={..},frame={..}]`` - is
    returned as a plain list of the values, because that is what a caller wants
    and the repeated name carries no extra information. A list mixing names
    keeps each entry as a single-key dict so nothing is lost.
    """
    cursor.expect("[")
    if cursor.peek() == "]":
        cursor.take()
        return []

    entries: List[Any] = []
    names: List[Optional[str]] = []
    while True:
        if cursor.peek() == '"' or cursor.peek() in "{[":
            entries.append(_parse_value(cursor))
            names.append(None)
        else:
            name, value = _parse_result(cursor)
            entries.append(value)
            names.append(name)
        if cursor.peek() == ",":
            cursor.take()
            continue
        cursor.expect("]")
        break

    named = [name for name in names if name is not None]
    if not named:
        return entries
    if len(set(named)) == 1 and len(named) == len(entries):
        return entries                     # uniformly named: drop the name
    return [
        entry if name is None else {name: entry}
        for name, entry in zip(names, entries)
    ]


def _parse_value(cursor: _Cursor) -> Any:
    char = cursor.peek()
    if char == '"':
        return _parse_cstring(cursor)
    if char == "{":
        return _parse_tuple(cursor)
    if char == "[":
        return _parse_list(cursor)
    raise ProtocolError(
        "malformed MI value at offset %d of %r" % (cursor.pos, cursor.text)
    )


def _parse_result(cursor: _Cursor) -> tuple:
    name = _parse_variable(cursor)
    cursor.expect("=")
    return name, _parse_value(cursor)


def _parse_results(cursor: _Cursor) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    while not cursor.at_end:
        if cursor.peek() == ",":
            cursor.take()
            continue
        if cursor.peek() in '{["':
            # GDB's own "load" progress breaks the grammar with an unnamed
            # tuple: +download,{section=".sec1",section-size="2584",...}.
            # Its fields are kept as if they had been results.
            value = _parse_value(cursor)
            if isinstance(value, dict):
                results.update(value)
            else:
                results.setdefault("value", value)
            continue
        name, value = _parse_result(cursor)
        if name in results:
            # Repeated top-level name: keep every occurrence.
            existing = results[name]
            if isinstance(existing, list) and not isinstance(value, list):
                existing.append(value)
            else:
                results[name] = [existing, value]
        else:
            results[name] = value
    return results


def parse_value(text: str) -> Any:
    """Parse a single MI value, for tests and for ad-hoc use."""
    cursor = _Cursor(text)
    value = _parse_value(cursor)
    if not cursor.at_end:
        raise ProtocolError("trailing text after MI value: %r" % text[cursor.pos :])
    return value


# ---------------------------------------------------------------------------
# Line parsing
# ---------------------------------------------------------------------------
_ASYNC_KINDS = {"*": RecordKind.EXEC, "+": RecordKind.STATUS, "=": RecordKind.NOTIFY}
_STREAM_KINDS = {"~": RecordKind.CONSOLE, "@": RecordKind.TARGET, "&": RecordKind.LOG}


def parse_line(line: str) -> Optional[Record]:
    """Parse one line of MI output.

    :returns: The record, or ``None`` for a blank line or anything that is not
        MI at all. GDB emits the occasional stray line - a banner, a warning
        before MI starts - and discarding it is correct: raising would abandon a
        session over output that carries no information.
    """
    text = line.strip()
    if not text:
        return None
    if text.startswith(PROMPT):
        return PromptRecord(kind=RecordKind.PROMPT)

    # Optional numeric token prefix.
    index = 0
    while index < len(text) and text[index].isdigit():
        index += 1
    token = int(text[:index]) if index else None
    if index >= len(text):
        return None
    marker = text[index]
    body = text[index + 1 :]

    if marker in _STREAM_KINDS:
        cursor = _Cursor(body)
        try:
            return StreamRecord(kind=_STREAM_KINDS[marker], text=_parse_cstring(cursor))
        except ProtocolError:
            # Some builds emit unquoted stream text; keep it rather than fail.
            return StreamRecord(kind=_STREAM_KINDS[marker], text=body)

    if marker == "^" or marker in _ASYNC_KINDS:
        class_end = body.find(",")
        message = body if class_end < 0 else body[:class_end]
        remainder = "" if class_end < 0 else body[class_end + 1 :]
        results = _parse_results(_Cursor(remainder)) if remainder else {}
        if marker == "^":
            return ResultRecord(
                kind=RecordKind.RESULT, message=message.strip(),
                results=results, token=token,
            )
        return AsyncRecord(
            kind=_ASYNC_KINDS[marker], message=message.strip(),
            results=results, token=token,
        )

    return None
