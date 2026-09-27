"""Packets in and out, and the structured log of them.

The raw session log (:mod:`session`) keeps every line the board and the host
exchanged. That is the evidence, and it is not convenient: analysing a capture
from it means re-parsing the protocol. This module holds the other half - one
record per packet, written as JSON Lines, which is what a later analysis reads.

Both logs are kept because they answer different questions. "What did the
tooling actually do?" is answered by the session log. "What did the radio
carry?" is answered by this one.

**On completeness.** ST's firmware receives by being asked to: each
``S2LPGetNBytes`` arms the radio, waits, and returns. Between one call and the
next the radio is not listening, and a packet that arrives in that gap is not
merely lost - it is *invisible*. A capture therefore records how it was taken
(:attr:`Capture.gaps`), so that "no packets" can be told apart from "not
listening". A count of what was missed is not available from this hardware path,
and this package does not invent one.

Traces to: S2LP-FR-040 .. S2LP-FR-046, S2LP-DD-PACKETS.
"""

from __future__ import annotations

import datetime
import json
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "BoardClock",
    "Packet",
    "Capture",
    "PacketLog",
    "REPORT_ALL_TAGS",
    "packet_from_reply",
    "rssi_dbm_from_register",
    "rssi_register_from_dbm",
]

#: Tags ``S2LPGetNBytesReportAll`` adds to a batch report, all in hex.
REPORT_ALL_TAGS = ("seq_num", "nack_rx", "source_addr", "dest_addr",
                   "agc_word", "crc", "packet_len")


def rssi_dbm_from_register(value: int) -> float:
    """RSSI_LEVEL to dBm, by the datasheet's conversion: dBm = value/2 - 146."""
    return (int(value) / 2.0) - 146.0


def rssi_register_from_dbm(dbm: float) -> int:
    """dBm back to a RSSI_LEVEL value, for a threshold setting."""
    return max(0, min(255, int(round((float(dbm) + 146.0) * 2.0))))


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


class BoardClock:
    """The motherboard's 32-bit microsecond timer, unwrapped.

    The counter wraps every 71.6 minutes. Each reading is compared with the
    last, and a smaller one counts as one wrap. That is right as long as
    readings are less than 71.6 minutes apart, which a capture satisfies; a
    session idle for longer than that cannot tell one wrap from two, and nothing
    on this link could.
    """

    WRAP = 1 << 32

    def __init__(self) -> None:
        self._last: Optional[int] = None
        self._wraps = 0

    def unwrap(self, raw: int) -> int:
        """Microseconds since the board started, for a raw timer reading."""
        value = int(raw) & (self.WRAP - 1)
        if self._last is not None and value < self._last:
            self._wraps += 1
        self._last = value
        return value + self._wraps * self.WRAP

    @property
    def wraps(self) -> int:
        """How many times the counter has wrapped so far."""
        return self._wraps


@dataclass
class Packet:  # pylint: disable=too-many-instance-attributes
    """One packet, sent or received.

    :param direction: ``"tx"`` or ``"rx"``.
    :param data: The payload the radio carried.
    :param rssi_dbm: Signal strength, for a received packet. ``None`` for a
        transmitted one, and for a received one the firmware did not report.
    :param host_time: When the host recorded it, ISO 8601 UTC.
    :param board_time_us: The board's own timer when it reported the packet, in
        microseconds, unwrapped by :class:`BoardClock`. It is the better clock
        of the two for intervals. It is read when the firmware *prints* the
        report, after the packet has been read out of the radio, so it orders
        packets and times a sequence; it is not the moment the packet arrived.
        ``None`` for a transmission, whose acknowledgement carries no timer.
    :param error: The firmware's error code, 0 when it reported none.
    :param extra: Further fields the firmware reported with the packet, by the
        firmware's own tag names (``seq_num``, ``agc_word``, ``crc``, ...).
    :param registers: Radio registers read straight after the packet, by name,
        as a stream reads them - PQI, SQI and the like, which the firmware does
        not report itself.
    :param decoded: What a frame decoder made of the payload, or ``None``.
    :param decode_error: Why the decoder could not, when it could not. The raw
        payload is kept either way.
    """

    direction: str
    data: bytes
    rssi_dbm: Optional[float] = None
    host_time: str = field(default_factory=_now)
    board_time_us: Optional[int] = None
    error: int = 0
    note: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
    registers: Dict[str, int] = field(default_factory=dict)
    decoded: Optional[Dict[str, Any]] = None
    decode_error: str = ""

    @property
    def length(self) -> int:
        return len(self.data)

    @property
    def hex(self) -> str:
        return self.data.hex()

    @property
    def is_received(self) -> bool:
        return self.direction == "rx"

    @property
    def ok(self) -> bool:
        return self.error == 0

    @property
    def text(self) -> str:
        """The payload as text, with anything unprintable as a dot.

        A convenience for a log a person reads; :attr:`hex` is the record.
        """
        return "".join(chr(b) if 32 <= b < 127 else "." for b in self.data)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "host_time": self.host_time,
            "board_time_us": self.board_time_us,
            "length": self.length,
            "hex": self.hex,
            "text": self.text,
            "rssi_dbm": self.rssi_dbm,
            "error": self.error,
            "note": self.note,
            "extra": dict(self.extra),
            "registers": dict(self.registers),
            "decoded": self.decoded,
            "decode_error": self.decode_error,
        }

    def __str__(self) -> str:
        parts = ["%s %3d bytes" % (self.direction.upper(), self.length)]
        if self.rssi_dbm is not None:
            parts.append("%.1f dBm" % self.rssi_dbm)
        if "pqi" in self.extra:
            parts.append("PQI %d SQI %d" % (self.extra["pqi"], self.extra.get("sqi", 0)))
        if not self.ok:
            parts.append("error 0x%02X" % self.error)
        if self.decoded:
            parts.append(str(self.decoded.get("type", "decoded")))
        elif self.decode_error:
            parts.append("undecoded: %s" % self.decode_error)
        parts.append(self.hex[:48] + ("..." if len(self.hex) > 48 else ""))
        return "  ".join(parts)


@dataclass
class Capture:
    """What one receive session produced, and how it was taken.

    :param packets: The packets that arrived intact, in order.
    :param rejected: Receptions the firmware reported with an error code (CRC,
        address filter, ...), in order. They are receptions, so they are kept -
        a CRC failure rate is a measurement - but they are not packets.
    :param requested: How many the capture asked for.
    :param duration_s: Wall-clock seconds the capture ran.
    :param gaps: Number of times the radio was re-armed during the capture.
        Each re-arm is an interval in which nothing could be received.
    :param rearm: Who re-armed the radio: ``"firmware"`` (ST's batch loop, which
        re-arms in the board's own loop) or ``"host"`` (one command per packet,
        so each gap includes a USB round trip and the host's own latency).
    :param stopped_early: True when the host ended the capture rather than the
        board finishing it.
    """

    packets: List[Packet] = field(default_factory=list)
    rejected: List[Packet] = field(default_factory=list)
    requested: int = 0
    duration_s: float = 0.0
    gaps: int = 0
    rearm: str = "firmware"
    stopped_early: bool = False

    @property
    def count(self) -> int:
        return len(self.packets)

    @property
    def is_continuous(self) -> bool:
        """True when the radio was never re-armed during the capture.

        No capture of more than one packet is, on this firmware: even its batch
        loop re-arms the radio after reading each packet out. So this is only
        true of a capture that received at most one reception, and a capture
        that is not continuous cannot be used to say a packet was *absent* -
        only that none was seen while listening. :attr:`rearm` says how long
        the gaps were likely to be.
        """
        return self.gaps == 0

    @property
    def mean_rssi_dbm(self) -> Optional[float]:
        values = [p.rssi_dbm for p in self.packets if p.rssi_dbm is not None]
        return statistics.fmean(values) if values else None

    @property
    def errors(self) -> int:
        """Receptions the firmware rejected (CRC, address filter, ...)."""
        return len(self.rejected)

    @property
    def bytes_received(self) -> int:
        return sum(packet.length for packet in self.packets)

    def describe(self) -> str:
        """One line for a console or a report."""
        text = "%d packet(s) in %.2f s" % (self.count, self.duration_s)
        if self.mean_rssi_dbm is not None:
            text += ", mean RSSI %.1f dBm" % self.mean_rssi_dbm
        if self.errors:
            text += ", %d rejected" % self.errors
        if not self.is_continuous:
            text += (" (%d %s re-arm gap(s): not a complete record of the air)"
                     % (self.gaps, self.rearm))
        if self.stopped_early:
            text += " (stopped by the host)"
        return text

    def as_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "requested": self.requested,
            "duration_s": round(self.duration_s, 6),
            "gaps": self.gaps,
            "rearm": self.rearm,
            "is_continuous": self.is_continuous,
            "stopped_early": self.stopped_early,
            "errors": self.errors,
            "bytes_received": self.bytes_received,
            "mean_rssi_dbm": self.mean_rssi_dbm,
            "packets": [packet.as_dict() for packet in self.packets],
            "rejected": [packet.as_dict() for packet in self.rejected],
        }


def packet_from_reply(reply, clock: BoardClock) -> Optional[Packet]:
    """One ``S2LPGetNBytes`` report as a packet, or ``None`` if it is not one.

    A report with a non-zero error is still a reception - the firmware heard
    something and rejected it (1 timeout, 2 CRC, 3 and 4 address filters, 6,
    per ST's source) - so it becomes a packet with its error set and no data,
    and the caller decides what to do with it.
    """
    if reply.command != "S2LPGetNBytes" and not reply.has("bytes"):
        return None
    error = reply.hex_number("error", 0)
    timer = reply.hex_number("timer", -1)
    return Packet(
        direction="rx",
        data=bytes(reply.numbers("bytes")) if not error else b"",
        rssi_dbm=(rssi_dbm_from_register(reply.hex_number("rssi"))
                  if reply.has("rssi") else None),
        board_time_us=clock.unwrap(timer) if timer >= 0 else None,
        error=error,
        extra={tag: reply.hex_number(tag) for tag in REPORT_ALL_TAGS if reply.has(tag)},
    )


class PacketLog:
    """A JSON Lines log of packets, one object per line.

    One object per line rather than one document, so that a capture interrupted
    half way through is still a readable file - which is the case that matters,
    since a capture is usually interrupted on purpose.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._file = open(path, "a", encoding="utf-8")
        self._count = 0

    @property
    def count(self) -> int:
        """Packets written to this log."""
        return self._count

    def write(self, packet: Packet) -> None:
        """Append one packet, flushed immediately."""
        self._file.write(json.dumps(packet.as_dict(), sort_keys=True) + "\n")
        self._file.flush()
        self._count += 1

    def write_all(self, packets: Iterable[Packet]) -> int:
        """Append several, and return how many."""
        written = 0
        for packet in packets:
            self.write(packet)
            written += 1
        return written

    def note(self, text: str, **fields: Any) -> None:
        """Append a note, so a capture can carry its own context.

        A note is a record like any other, marked ``"note"``, so a reader that
        expects packets does not have to special-case it out of the file.
        """
        record = {"direction": "note", "host_time": _now(), "note": text}
        record.update(fields)
        self._file.write(json.dumps(record, sort_keys=True) + "\n")
        self._file.flush()

    def close(self) -> None:
        """Close the file. Idempotent."""
        if self._file is not None and not self._file.closed:
            self._file.close()

    def __enter__(self) -> "PacketLog":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    @staticmethod
    def read(path: str) -> List[Dict[str, Any]]:
        """Read a packet log back.

        Skips a truncated final line rather than failing: a capture killed mid
        write should still be readable up to the last complete record.
        """
        records: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue
        return records
