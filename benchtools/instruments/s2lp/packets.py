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

__all__ = ["Packet", "Capture", "PacketLog"]


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


@dataclass
class Packet:
    """One packet, sent or received.

    :param direction: ``"tx"`` or ``"rx"``.
    :param data: The payload the radio carried.
    :param rssi_dbm: Signal strength, for a received packet. ``None`` for a
        transmitted one, and for a received one the firmware did not report.
    :param host_time: When the host recorded it, ISO 8601 UTC.
    :param board_time_ms: The board's own millisecond timer at the event. It is
        the better clock of the two for intervals, and it is *milliseconds*: it
        cannot resolve anything shorter, and this package does not pretend
        otherwise.
    :param error: The firmware's error code, 0 when it reported none.
    """

    direction: str
    data: bytes
    rssi_dbm: Optional[float] = None
    host_time: str = field(default_factory=_now)
    board_time_ms: Optional[int] = None
    error: int = 0
    note: str = ""

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
            "board_time_ms": self.board_time_ms,
            "length": self.length,
            "hex": self.hex,
            "text": self.text,
            "rssi_dbm": self.rssi_dbm,
            "error": self.error,
            "note": self.note,
        }

    def __str__(self) -> str:
        parts = ["%s %3d bytes" % (self.direction.upper(), self.length)]
        if self.rssi_dbm is not None:
            parts.append("%.1f dBm" % self.rssi_dbm)
        if not self.ok:
            parts.append("error 0x%02X" % self.error)
        parts.append(self.hex[:48] + ("..." if len(self.hex) > 48 else ""))
        return "  ".join(parts)


@dataclass
class Capture:
    """What one receive session produced, and how it was taken.

    :param packets: The packets that arrived, in order.
    :param requested: How many the capture asked for.
    :param duration_s: Wall-clock seconds the capture ran.
    :param gaps: Number of times the radio was re-armed between packets. Each
        one is an interval during which nothing could have been received, so a
        capture with gaps cannot be quoted as a complete record of the air.
    :param stopped_early: True when the host ended the capture rather than the
        board finishing it.
    """

    packets: List[Packet] = field(default_factory=list)
    requested: int = 0
    duration_s: float = 0.0
    gaps: int = 0
    stopped_early: bool = False

    @property
    def count(self) -> int:
        return len(self.packets)

    @property
    def is_continuous(self) -> bool:
        """True when the radio listened without being re-armed mid-capture.

        Only a batch capture can be continuous. A capture that is not cannot be
        used to say a packet was *absent* - only that none was seen while
        listening.
        """
        return self.gaps == 0

    @property
    def mean_rssi_dbm(self) -> Optional[float]:
        values = [p.rssi_dbm for p in self.packets if p.rssi_dbm is not None]
        return statistics.fmean(values) if values else None

    @property
    def errors(self) -> int:
        return sum(1 for packet in self.packets if not packet.ok)

    @property
    def bytes_received(self) -> int:
        return sum(packet.length for packet in self.packets)

    def describe(self) -> str:
        """One line for a console or a report."""
        text = "%d packet(s) in %.2f s" % (self.count, self.duration_s)
        if self.mean_rssi_dbm is not None:
            text += ", mean RSSI %.1f dBm" % self.mean_rssi_dbm
        if self.errors:
            text += ", %d with errors" % self.errors
        if not self.is_continuous:
            text += " (%d re-arm gap(s): not a complete record of the air)" % self.gaps
        if self.stopped_early:
            text += " (stopped by the host)"
        return text

    def as_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "requested": self.requested,
            "duration_s": round(self.duration_s, 6),
            "gaps": self.gaps,
            "is_continuous": self.is_continuous,
            "stopped_early": self.stopped_early,
            "errors": self.errors,
            "bytes_received": self.bytes_received,
            "mean_rssi_dbm": self.mean_rssi_dbm,
            "packets": [packet.as_dict() for packet in self.packets],
        }


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
