"""ST's CLI line protocol, as the S2-LP DK GUI speaks it.

The firmware on the kit is ST's ``S2LP_CLI`` application, built on Ember's
``command-interpreter2``. This module is the host's half of that interface, and
nothing else: it formats a command line and it parses a reply. It knows nothing
about radios.

**Commands** are one ASCII line: a name, then arguments separated by spaces.
Integers are decimal or ``0x``-prefixed; a byte string is written in braces,
``{ 08 A1 F2 }``, or in quotes for ASCII. ST's argument-type letters are ``u``
(one byte), ``v`` (two), ``w`` (four) and ``b`` (byte string), and this module
checks a command's arguments against them before sending, because the firmware's
answer to a malformed line is a terse error that does not say which argument was
wrong.

**Replies** are ASCII, brace-delimited, produced by ST's ``responsePrintf``.
Recorded from a kit (ST CLI, S2-LP library 1.3.5), most are one line:

.. code-block:: text

    S2LPRadioGetFrequencyBase
    {{(S2LPRadioGetFrequencyBase)} API call...{value:31BF1BAD}}
    >

and a few are several:

.. code-block:: text

    {{(SdkEvalSpiReadRegisters)} API callback...
    {regs_list: 0x2E,0x20,0x2F,0x00}
    {timer:055E5BB1}
    }

The firmware echoes the command line first and prints a ``>`` prompt after the
reply; neither is part of the reply. So a reply is a set of **tags**. Most
getters answer in a tag called ``value``; a few name their fields
(``Frequency_base``, ``regs_list``, ``bytes``, ``rssi``). The parser collects
them by name and leaves interpretation to the caller. Tag text that is not
understood is *kept*, not discarded: a log that omits what the tooling did not
recognise cannot explain why it ignored it.

**How a value is written depends on the command, not on the value.** ST's
``&tx``, ``&t2x`` and ``&t4x`` print 2, 4 and 8 hex digits with no ``0x``;
``&td`` prints signed decimal; one command prints a float with ``%.1f``. The
caller picks the matching accessor (:meth:`Reply.hex_number`,
:meth:`Reply.number`, :meth:`Reply.real`), because the characters alone cannot
say which: ``{value:70}`` is 0x70 from one command and seventy from another.

**A command the interpreter rejects** gets one line and no braces, for example
``no such command`` or ``wrong number of arguments``. :data:`FIRMWARE_ERRORS`
lists them, so the session can fail at once instead of waiting out its timeout.

Traces to: S2LP-FR-001 .. S2LP-FR-004, S2LP-DD-PROTOCOL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Union

from ...core.errors import ProtocolError
from .constants import COMMANDS

__all__ = [
    "FIRMWARE_ERRORS",
    "Reply",
    "firmware_error",
    "format_command",
    "format_bytes",
    "parse_reply",
    "parse_pairs",
]

#: The command interpreter's own error lines, from ST's ``command-interpreter2``.
#: Each arrives on its own line in place of a reply.
FIRMWARE_ERRORS = (
    "serial port error",
    "no such command",
    "wrong number of arguments",
    "integer argument out of range",
    "argument syntax error",
    "string too long",
    "invalid argument type",
)

#: Widths ST's argument letters accept, as unsigned integers.
_LIMITS = {"u": 0xFF, "v": 0xFFFF, "w": 0xFFFFFFFF, "s": 0x7F}

#: Letters for arguments the firmware reads with ``signedCommandArgument``. ST's
#: table declares them ``w``, but the handler reads a leading ``-``, and a power
#: level of -10 dBm cannot be sent as an unsigned number. ``i`` is this module's
#: letter for that, not ST's; the line sent is the same.
_SIGNED_LIMITS = {"i": (-0x80000000, 0x7FFFFFFF)}

#: ``{tag: value}`` or ``{tag:value}``. The name is letters, digits and
#: underscores; the value is everything to the closing brace.
_TAG = re.compile(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^{}]*?)\s*\}")

#: A lone ``{name}`` or ``{(name)}`` with no colon - how ST's ``&N`` renders a
#: command name. The firmware on the kit writes the parentheses.
_NAME = re.compile(r"\{\s*\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?\s*\}")

#: ``0x1F`` or ``31`` or ``-110``, as the firmware writes values. The sign
#: matters: RSSI in dBm arrives from ``S2LPQiGetRssidBm`` as a negative decimal,
#: and dropping the minus turns -110 dBm into +110 dBm - a number that is not
#: merely wrong but impossible, and that nothing downstream would question.
_NUMBER = re.compile(r"-?0x[0-9A-Fa-f]+|-?\d+")


def format_bytes(data: Union[bytes, bytearray, Sequence[int]]) -> str:
    """Render *data* as ST's brace-delimited hex argument.

    ``b"\\x08\\xa1"`` becomes ``{08 A1}``. An empty payload is ``{}``, which the
    firmware accepts as a zero-length string.
    """
    payload = bytes(data)
    return "{%s}" % " ".join("%02X" % byte for byte in payload)


def _format_argument(value, letter: str, command: str, index: int) -> str:
    if letter == "b":
        if isinstance(value, str):
            if '"' in value:
                raise ProtocolError(
                    "%s argument %d: a quoted string cannot contain a quote"
                    % (command, index + 1)
                )
            return '"%s"' % value
        return format_bytes(value)

    number = int(value)
    if letter in _SIGNED_LIMITS:
        low, high = _SIGNED_LIMITS[letter]
        if not low <= number <= high:
            raise ProtocolError(
                "%s argument %d is %d, outside the signed 32-bit range the "
                "firmware reads it as" % (command, index + 1, number)
            )
        return str(number)
    limit = _LIMITS.get(letter)
    if limit is None:
        raise ProtocolError("%s: unknown argument type %r" % (command, letter))
    if number < 0 or number > limit:
        raise ProtocolError(
            "%s argument %d is %d, which does not fit the %d-bit field the "
            "firmware declares for it (0 to %d)"
            % (command, index + 1, number, (limit.bit_length()), limit)
        )
    return str(number)


def format_command(name: str, *arguments) -> str:
    """Build one command line for *name*.

    The argument types come from the command table, so a driver that sends the
    wrong number or an out-of-range value is stopped here, naming the command,
    rather than producing a firmware error four steps later.

    :raises ProtocolError: for an unknown command, the wrong argument count, or
        a value the declared type cannot hold.
    """
    if name not in COMMANDS:
        raise ProtocolError(
            "%r is not a command of the S2-LP CLI firmware. Known commands: %s"
            % (name, ", ".join(sorted(COMMANDS)))
        )
    letters = COMMANDS[name]
    if len(arguments) != len(letters):
        raise ProtocolError(
            "%s takes %d argument(s) (%s), not %d"
            % (name, len(letters), letters or "none", len(arguments))
        )
    parts = [name]
    for index, (value, letter) in enumerate(zip(arguments, letters)):
        parts.append(_format_argument(value, letter, name, index))
    return " ".join(parts)


def firmware_error(line: str) -> Optional[str]:
    """The interpreter error *line* reports, or ``None`` if it is not one."""
    text = line.strip().lower()
    for error in FIRMWARE_ERRORS:
        if text == error:
            return error
    return None


def parse_pairs(text: str) -> List[int]:
    """Every number in *text*, in order.

    ``"0x00,0x0A,0x01,0xA2"`` becomes ``[0, 10, 1, 162]``. Used for the
    ``regs_list`` tag, which interleaves addresses and values, and for the
    ``bytes`` tag, which does not.
    """
    values = []
    for item in _NUMBER.findall(text):
        negative = item.startswith("-")
        digits = item[1:] if negative else item
        number = int(digits, 16) if digits.lower().startswith("0x") else int(digits)
        values.append(-number if negative else number)
    return values


@dataclass
class Reply:
    """One parsed reply from the firmware.

    :param command: The command name the firmware echoed, when it echoed one.
    :param tags: Tag name to its raw text, in the order they arrived.
    :param lines: Every line of the reply, kept verbatim for the log.
    """

    command: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    lines: List[str] = field(default_factory=list)

    @property
    def raw(self) -> str:
        return "\n".join(self.lines)

    def has(self, tag: str) -> bool:
        return tag in self.tags

    def text(self, tag: str, default: Optional[str] = None) -> str:
        """The raw text of a tag.

        :raises ProtocolError: if it is absent and no default was given - which
            means the firmware answered something other than what was asked, and
            guessing would put an invented number into a report.
        """
        if tag in self.tags:
            return self.tags[tag]
        if default is not None:
            return default
        raise ProtocolError(
            "the reply carries no %r; it has %s. Reply was: %s"
            % (tag, ", ".join(sorted(self.tags)) or "no tags", self.raw or "(empty)")
        )

    def number(self, tag: str, default: Optional[int] = None) -> int:
        """One tag as a single number."""
        if tag not in self.tags and default is not None:
            return default
        values = parse_pairs(self.text(tag))
        if len(values) != 1:
            raise ProtocolError(
                "expected one number in %r, got %r" % (tag, self.tags.get(tag))
            )
        return values[0]

    def hex_number(self, tag: str, default: Optional[int] = None) -> int:
        """One tag as a number, read as **hex whether or not it says ``0x``**.

        ST's firmware writes some tags with its ``%x`` specifier, which emits
        bare hex: an RSSI of 212 arrives as ``{rssi:D4}`` and a timer as
        ``{timer:000004D2}``. Read as decimal, ``D4`` yields 4 - a number that is
        a plausible RSSI and is wrong by 104 dB. So the tags the firmware writes
        in hex are read in hex, explicitly, rather than guessed at from the
        characters that happen to be present.
        """
        if tag not in self.tags and default is not None:
            return default
        text = self.text(tag).strip()
        try:
            return int(text, 16)
        except ValueError:
            raise ProtocolError(
                "expected a hexadecimal value in %r, got %r" % (tag, text)
            ) from None

    def real(self, tag: str, default: Optional[float] = None) -> float:
        """One tag as a signed decimal that may have a fraction.

        ``S2LPQiGetRssidBm`` answers ``{value:-116.0}``. :meth:`number` would
        read that as two numbers, -116 and 0, and refuse it.
        """
        if tag not in self.tags and default is not None:
            return default
        text = self.text(tag).strip()
        try:
            return float(text)
        except ValueError:
            raise ProtocolError(
                "expected a decimal value in %r, got %r" % (tag, text)
            ) from None

    def numbers(self, tag: str) -> List[int]:
        """One tag as a list of numbers, empty when the tag is absent."""
        if tag not in self.tags:
            return []
        return parse_pairs(self.text(tag))

    def as_dict(self) -> Dict[str, str]:
        return {"command": self.command, **self.tags}


def parse_reply(lines: Iterable[str]) -> Reply:
    """Parse the lines of one reply.

    Tags are collected wherever they appear; a repeated tag keeps the **last**
    value, which is how the firmware's own batch replies read. Lines that carry
    no tag are still recorded in :attr:`Reply.lines`.
    """
    reply = Reply()
    for line in lines:
        text = line.rstrip("\r\n")
        reply.lines.append(text)
        remainder = text
        for match in _TAG.finditer(text):
            reply.tags[match.group(1)] = match.group(2)
            remainder = remainder.replace(match.group(0), " ")
        if not reply.command:
            name = _NAME.search(remainder)
            if name:
                reply.command = name.group(1)
    return reply
