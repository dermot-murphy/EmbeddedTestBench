"""The serial capture instrument's command set, in the Kepler console's form.

One ASCII command per line, one reply line per command (#247). The command
words are not case sensitive; the reply echoes the command as it was sent, as
the Kepler sensor's BLE console does.

======================================  =======================================================
Command                                 Reply
======================================  =======================================================
``RD PORT``                             ``ACK RD PORT = COM5``
``RD BAUD``                             ``ACK RD BAUD = 115200``
``RD FORMAT``                           ``ACK RD FORMAT = 8N1``
``RD WINDOW``                           ``ACK RD WINDOW = 5000``
``RD PATTERN``                          ``ACK RD PATTERN = ^SELF TEST PASS`` (``OFF`` if none)
``RD LINES``                            ``ACK RD LINES = OFF``
``RD COUNT``                            ``ACK RD COUNT = 12``
``RD LINE <n>``                         ``ACK RD LINE 3 = <text>``
``RD MATCH``                            ``ACK RD MATCH = <line that matched>``
``RD VALUE``                            ``ACK RD VALUE = 3.30`` (the pattern's first group)
``WR BAUD <rate>``                      ``ACK WR BAUD 9600 Baud``
``WR FORMAT <format>``                  ``ACK WR FORMAT 7E1``
``WR WINDOW <ms>``                      ``ACK WR WINDOW 10000 ms``
``WR PATTERN <regex>``                  ``ACK WR PATTERN ^OK`` (``WR PATTERN OFF`` clears it)
``WR LINES ON`` / ``WR LINES OFF``      ``ACK WR LINES ON``
``ROUTINE START CAPTURE``               ``ACK ROUTINE START CAPTURE = Running``
``ROUTINE ABORT CAPTURE``               ``ACK ROUTINE ABORT CAPTURE = Aborted``
``ROUTINE ABORT ALL``                   ``ACK ROUTINE ABORT ALL = Aborted``
``ROUTINE RESULTS CAPTURE``             ``ACK ROUTINE RESULTS CAPTURE = Complete, 3 lines, Matched``
======================================  =======================================================

An abort answers with the status after it: ``Aborted`` for a capture that was
running, or the status it already had (``Complete``, ``Not Started``).

Refusals are ``NACK <command> <REASON>``: ``INVALID VALUE`` (not a number, not
a format, not a regular expression), ``OUT OF RANGE``, ``BUSY`` (a capture is
running) and ``NOT FOUND`` (no such line, no match, no value). A command the
set does not have is ``NACK Invalid Command``.

``WR LINES ON`` is the only way to switch the live line output on, and
``WR LINES OFF`` the only way to switch it off. While it is on, each captured
line is also shown as ``LINE <n> = <text>``.

Traces to: SER-FR-002 .. SER-FR-005, SER-FR-007, SER-DD-CONSOLE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from ...core.errors import TransportError
from .constants import (
    BUSY,
    INVALID_COMMAND,
    INVALID_VALUE,
    NOT_FOUND,
    OFF,
    ON,
    OUT_OF_RANGE,
    PATTERN_OFF,
    ROUTINE_CAPTURE,
)

__all__ = ["Reply", "execute"]


@dataclass(frozen=True)
class Reply:
    """One reply of the command set.

    :ivar command: The command, as it was sent (spaces collapsed).
    :ivar text: The reply line.
    :ivar ok: ``True`` for ``ACK``, ``False`` for ``NACK``.
    :ivar value: For an ``RD`` or ``ROUTINE`` reply, what follows `` = ``;
        otherwise ``None``.
    """

    command: str
    text: str
    ok: bool
    value: Optional[str] = None

    def __str__(self) -> str:
        return self.text


def _ack(command: str, value: Optional[str] = None, unit: str = "") -> Reply:
    if value is not None:
        return Reply(command, "ACK %s = %s" % (command, value), True, value)
    return Reply(command, "ACK %s%s" % (command, " " + unit if unit else ""), True)


def _nack(command: str, reason: str) -> Reply:
    return Reply(command, "NACK %s %s" % (command, reason), False)


def _invalid(command: str) -> Reply:
    return Reply(command, INVALID_COMMAND, False)


def execute(capture, text: str) -> Reply:
    """Run one command on *capture* (a :class:`~.capture.SerialCapture`)."""
    command = " ".join(str(text).split())
    words = command.split(" ")
    verb = words[0].upper() if words else ""
    handler = _VERBS.get(verb)
    if handler is None:
        return _invalid(command)
    return handler(capture, command, words[1:])


# ----------------------------------------------------------------------
# RD
# ----------------------------------------------------------------------
def _rd(capture, command: str, args) -> Reply:  # pylint: disable=too-many-return-statements
    if not args:
        return _invalid(command)
    what = args[0].upper()
    if what == "LINE":
        if len(args) != 2:
            return _invalid(command)
        if not args[1].isdigit():
            return _nack(command, INVALID_VALUE)
        try:
            return _ack(command, capture.line(int(args[1])))
        except IndexError:
            return _nack(command, NOT_FOUND)
    if len(args) != 1:
        return _invalid(command)
    getter = _READINGS.get(what)
    if getter is None:
        return _invalid(command)
    value = getter(capture)
    if value is None:
        return _nack(command, NOT_FOUND)
    return _ack(command, value)


_READINGS: Dict[str, Callable[[object], Optional[str]]] = {
    "PORT": lambda c: c.port or "sim://",
    "BAUD": lambda c: str(c.baudrate),
    "FORMAT": lambda c: c.char_format,
    "WINDOW": lambda c: str(c.window_ms),
    "PATTERN": lambda c: c.pattern or PATTERN_OFF,
    "LINES": lambda c: ON if c.lines_on else OFF,
    "COUNT": lambda c: str(c.results().count),
    "MATCH": lambda c: c.results().match,
    "VALUE": lambda c: c.results().value,
}


# ----------------------------------------------------------------------
# WR
# ----------------------------------------------------------------------
def _wr(capture, command: str, args) -> Reply:  # pylint: disable=too-many-return-statements
    if len(args) < 2:
        return _invalid(command)
    what = args[0].upper()
    # The pattern is everything after WR PATTERN, spaces included, as sent.
    value = command.split(" ", 2)[2]
    if what == "LINES":
        word = value.upper()
        if word not in (ON, OFF):
            return _nack(command, INVALID_VALUE)
        capture.set_lines(word == ON)
        return _ack(command)
    if what == "PATTERN":
        try:
            capture.pattern = "" if value.upper() == PATTERN_OFF else value
        except ValueError:
            return _nack(command, INVALID_VALUE)
        return _ack(command)
    if len(args) != 2:
        return _invalid(command)
    if what == "WINDOW":
        return _number(command, value, lambda n: setattr(capture, "window_ms", n), "ms")
    if what == "BAUD":
        return _number(command, value, capture.set_baudrate, "Baud", busy=capture.running)
    if what == "FORMAT":
        if capture.running:
            return _nack(command, BUSY)
        try:
            capture.set_format(value)
        except (ValueError, TransportError):        # a bad format, or the port refused it
            return _nack(command, INVALID_VALUE)
        return _ack(command)
    return _invalid(command)


def _number(command: str, value: str, apply, unit: str, busy: bool = False) -> Reply:
    if not value.isdigit():
        return _nack(command, INVALID_VALUE)
    if busy:
        return _nack(command, BUSY)
    try:
        apply(int(value))
    except ValueError:
        return _nack(command, OUT_OF_RANGE)
    except TransportError:                          # the port refused the setting
        return _nack(command, INVALID_VALUE)
    return _ack(command, unit=unit)


# ----------------------------------------------------------------------
# ROUTINE
# ----------------------------------------------------------------------
def _routine(capture, command: str, args) -> Reply:  # pylint: disable=too-many-return-statements
    if len(args) != 2:
        return _invalid(command)
    action, name = args[0].upper(), args[1].upper()
    if action == "ABORT" and name == "ALL":
        return _ack(command, capture.abort_capture().status)
    if name != ROUTINE_CAPTURE:
        return _invalid(command)
    if action == "START":
        if capture.running:
            return _nack(command, BUSY)
        return _ack(command, capture.start_capture().status)
    if action == "ABORT":
        return _ack(command, capture.abort_capture().status)
    if action == "RESULTS":
        return _ack(command, capture.results().summary())
    return _invalid(command)


_VERBS = {"RD": _rd, "WR": _wr, "ROUTINE": _routine}
