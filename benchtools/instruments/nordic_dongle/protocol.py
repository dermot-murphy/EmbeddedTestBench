"""Parsing the dongle's line protocol.

Grammar, in full:

======================  ====================================================
``ok [key=value ...]``  the previous command succeeded
``err <code> <text>``   the previous command failed
``+<name> key=value``   an unsolicited event; always carries ``t=``
anything else           not ours - a boot banner, a stray newline
======================  ====================================================

No I/O happens here and nothing is remembered, so every shape can be tested
directly. That matters more than it sounds: the awkward cases in a protocol
like this are the empty value (``name=``), the value containing an ``=``, the
advertised name containing a space, and the line that is not ours at all, and
each is a one-line test here rather than a hardware session.

Traces to: BLE-FR-001, BLE-DD-PROTOCOL.
"""

from __future__ import annotations

import binascii
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Union

from ...core.errors import InstrumentError
from .constants import AddressType, DongleError

__all__ = [
    "Reply",
    "Event",
    "Line",
    "parse_line",
    "parse_fields",
    "name_has_space",
    "NAME_FIELD",
    "to_hex",
    "from_hex",
    "manufacturer_id",
    "encode_payload",
    "format_address",
    "normalise_address",
    "DongleProtocolError",
]

#: An address as the firmware writes it, most significant octet first, with an
#: optional ``/<type>`` suffix.
_ADDRESS = re.compile(r"^([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})(?:/([0-3]))?$")

#: One space-separated token of a line.
_TOKEN = re.compile(r"\S+")

#: The field whose value may hold a space: the advertised name (#415).
NAME_FIELD = "name"

#: The ``name=`` token where it starts a field.
_NAME_TOKEN = re.compile(r"(?:^|(?<=\s))name=")

#: Events whose ``name=`` is the last field, so it takes the rest of the line:
#: ``+sensor`` (``cmd_parser.c`` writes it last on purpose, #241, #415).
_NAME_LAST_EVENTS = frozenset({"sensor"})


class DongleProtocolError(InstrumentError):
    """A line from the dongle that does not fit the grammar."""


@dataclass
class Reply:
    """The answer to a command.

    :param ok: True for ``ok``, False for ``err``.
    :param fields: Parsed ``key=value`` pairs.
    :param error: The code from an ``err`` reply.
    :param text: The message from an ``err`` reply.
    :param raw: The line as received.
    """

    ok: bool
    fields: Dict[str, str] = field(default_factory=dict)
    error: Optional[DongleError] = None
    text: str = ""
    raw: str = ""

    def __str__(self) -> str:
        return self.raw


@dataclass
class Event:
    """An unsolicited event.

    :param name: Event name without the ``+``.
    :param fields: Parsed ``key=value`` pairs.
    :param timestamp_us: The dongle's microsecond timestamp, from ``t=``.
    :param host_time: The host's own arrival time, filled in by the session.
    :param monotonic_s: The same arrival on :func:`time.perf_counter`, the
        clock the S2-LP driver stamps its packets with, so an event and a
        radio frame can be compared within one run (#243).
    :param raw: The line as received.
    """

    name: str
    fields: Dict[str, str] = field(default_factory=dict)
    timestamp_us: Optional[int] = None
    host_time: Optional[float] = None
    monotonic_s: Optional[float] = None
    raw: str = ""

    def __str__(self) -> str:
        return self.raw

    def get(self, key: str, default: str = "") -> str:
        """The value of *key*, or *default*."""
        return self.fields.get(key, default)

    def integer(self, key: str, default: int = 0) -> int:
        """The value of *key* as an integer, accepting ``0x`` forms."""
        text = self.fields.get(key)
        if text is None or text == "":
            return default
        try:
            return int(text, 0)
        except ValueError:
            return default


#: Either kind of line.
Line = Union[Reply, Event]


def parse_fields(text: str) -> Dict[str, str]:
    """Split ``key=value key=value`` into a mapping.

    A value may be empty (``name=`` for a sensor that advertises no name) and
    may itself contain ``=``; only the first ``=`` of each token separates.
    A token with no ``=`` at all is kept under its own name with an empty
    value, so nothing is silently discarded.

    The advertised name is the one value the firmware writes as it was
    received, so it may hold a space (#415). A token with no ``=`` that
    follows ``name=`` is the rest of that name, and is joined back onto it
    with the spacing it arrived with. In a line where other fields follow the
    name (``+adv``, the ``select`` and ``connect`` replies), a part of a name
    that itself holds an ``=`` cannot be told from a field and is read as
    one; a ``+sensor`` line, whose name is last, is parsed by
    :func:`parse_line` so that its name is always whole. Spaces at the end
    of a name are lost with the line's own trailing space.
    """
    fields: Dict[str, str] = {}
    name_start = -1
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        key, separator, value = token.partition("=")
        if separator:
            fields[key] = value
            name_start = match.start() + len(key) + 1 if key == NAME_FIELD else -1
        elif name_start >= 0:
            fields[NAME_FIELD] = text[name_start:match.end()]
        else:
            fields[token] = ""
    return fields


def name_has_space(name: Optional[str]) -> bool:
    """True when an advertised *name* holds a space, a tab or other whitespace.

    The line protocol splits on whitespace, so such a name is a breach of the
    rule that an advertised name holds none (#415). The driver reports it
    rather than trusting it silently.
    """
    return any(character.isspace() for character in (name or ""))


def _split_name_last(text: str) -> Dict[str, str]:
    """Parse the fields of a line whose ``name=`` is the last field.

    Everything after the first ``name=`` token is the name, ``=`` and all,
    so a name such as ``KAPPA a=b`` is kept whole rather than cut at the
    part that looks like a field (#415).
    """
    match = _NAME_TOKEN.search(text)
    if match is None:
        return parse_fields(text)
    fields = parse_fields(text[:match.start()])
    fields[NAME_FIELD] = text[match.end():]
    return fields


def parse_line(line: str) -> Optional[Line]:
    """Parse one line from the dongle.

    :returns: A :class:`Reply`, an :class:`Event`, or ``None`` for a line that
        is not part of the protocol.
    """
    text = (line or "").strip()
    if not text:
        return None

    if text.startswith("+"):
        name, _, remainder = text[1:].partition(" ")
        if name in _NAME_LAST_EVENTS:
            fields = _split_name_last(remainder)
        else:
            fields = parse_fields(remainder)
        timestamp = None
        if "t" in fields:
            try:
                timestamp = int(fields["t"])
            except ValueError:
                timestamp = None
        return Event(name=name, fields=fields, timestamp_us=timestamp, raw=text)

    if text == "ok" or text.startswith("ok "):
        return Reply(ok=True, fields=parse_fields(text[2:]), raw=text)

    if text.startswith("err"):
        parts = text.split(None, 2)
        code = DongleError.coerce(parts[1]) if len(parts) > 1 else DongleError.UNKNOWN
        message = parts[2] if len(parts) > 2 else ""
        return Reply(ok=False, error=code, text=message, raw=text)

    return None


def to_hex(data: bytes) -> str:
    """Encode bytes as lower-case hex, as the firmware expects."""
    return binascii.hexlify(bytes(data)).decode("ascii")


def from_hex(text: str) -> bytes:
    """Decode hex from the firmware.

    :raises DongleProtocolError: if *text* is not valid hex, naming the value.
    """
    try:
        return binascii.unhexlify(text.strip())
    except (binascii.Error, ValueError) as exc:
        raise DongleProtocolError(
            "the dongle sent %r where hex was expected: %s" % (text, exc)
        ) from exc


def manufacturer_id(payload: bytes) -> Optional[int]:
    """The company ID opening the first manufacturer-specific record, or None.

    Advertising data is a run of (length, type, data) records; a
    manufacturer-specific record (type 0xFF) starts with the company ID, least
    significant byte first. This is what the firmware reports as ``mfr=``.
    """
    index = 0
    while index + 1 < len(payload):
        length = payload[index]
        if length == 0:
            return None
        if payload[index + 1] == 0xFF and length >= 3 and index + 3 < len(payload):
            return payload[index + 2] | (payload[index + 3] << 8)
        index += length + 1
    return None


def encode_payload(payload) -> str:
    """Encode a command payload as hex.

    Accepts ``bytes`` or ``str``; text is encoded as UTF-8, because a firmware
    console speaks text and making every caller encode it by hand invites the
    mistake of sending the repr of a string.
    """
    if isinstance(payload, (bytes, bytearray)):
        return to_hex(bytes(payload))
    return to_hex(str(payload).encode("utf-8"))


def format_address(address: str, address_type: Optional[int] = None) -> str:
    """Render an address, with its type when one is known.

    The type travels with the address because connecting with the wrong one
    fails by never finding the device, which is the least diagnosable failure
    in BLE.
    """
    normalised = normalise_address(address)
    if address_type is None:
        return normalised
    return "%s/%d" % (normalised, int(address_type))


def normalise_address(address: str) -> str:
    """Validate and upper-case an address, dropping any type suffix.

    :raises DongleProtocolError: if it is not six colon-separated octets.
    """
    match = _ADDRESS.match((address or "").strip())
    if match is None:
        raise DongleProtocolError(
            "%r is not a BLE address; expected six colon-separated octets "
            "such as E4:1C:7B:02:9A:11, optionally with /0 to /3 for the "
            "address type" % address
        )
    return match.group(1).upper()


def address_type_of(address: str) -> Optional[AddressType]:
    """The type from an ``AA:BB:CC:DD:EE:FF/<n>`` string, if it carries one."""
    match = _ADDRESS.match((address or "").strip())
    if match is None or match.group(2) is None:
        return None
    return AddressType.coerce(match.group(2))
