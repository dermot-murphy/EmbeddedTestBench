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
like this are the empty value (``name=``), the value containing an ``=``, and
the line that is not ours at all, and each is a one-line test here rather than
a hardware session.

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
    "to_hex",
    "from_hex",
    "encode_payload",
    "format_address",
    "normalise_address",
    "DongleProtocolError",
]

#: An address as the firmware writes it, most significant octet first, with an
#: optional ``/<type>`` suffix.
_ADDRESS = re.compile(r"^([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})(?:/([0-3]))?$")


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
    :param raw: The line as received.
    """

    name: str
    fields: Dict[str, str] = field(default_factory=dict)
    timestamp_us: Optional[int] = None
    host_time: Optional[float] = None
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
    """
    fields: Dict[str, str] = {}
    for token in text.split():
        key, separator, value = token.partition("=")
        if separator:
            fields[key] = value
        else:
            fields[token] = ""
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
