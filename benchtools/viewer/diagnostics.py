"""rf_monitor's Diagnostics and Sync screens, from received frames (#155).

**Diagnostics** - per sensor and frame type: how many frames (each counted
once) and packets (every copy), how many copies were dropped, and the period
between frames - mean, standard deviation, shortest and longest with the two
frames either side of each. A sensor sends each frame as a burst of copies,
the frame counter saying ``n of m``. A burst ends at the next frame's first
copy, when all ``m`` copies are in, or when no copy has come for
:data:`BURST_GAP_S`; it then adds ``m`` to
the copies expected and the copies not heard to those dropped. Frame types
without a counter (FFT, FFT2, RESPONSE) count no drops.

**Sync** - per sensor, its synchronisation with the gateway, from CMD frames
(the sensor's requests and acknowledgements) and RESPONSE frames (the
gateway's timers): the phase, retry, slot, and the LORES and HIRES
countdowns. Unlike every other screen this one is not filtered to a sensor.

Both are computed from the frames' own times, never the moment the viewer
read them: rf_monitor timed bursts and countdowns by its own clock, which made
a replayed log's countdowns meaningless. "Now" is the time of the latest
record read. rf_monitor also raised an error on a frame of unknown type in
Diagnostics; here such a frame is counted under its type like any other.

Traces to: VIEW-FR-037 .. VIEW-FR-039, VIEW-DD-DIAG.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional

__all__ = ["Diagnostics", "SyncTracker", "BURST_GAP_S", "SYNC_IDLE_S"]

#: A burst of copies ends after this long with no further copy.
BURST_GAP_S = 1.0

#: A sensor with no sync activity for this long leaves the Sync table.
SYNC_IDLE_S = 1200.0


class _TypeStats:  # pylint: disable=too-many-instance-attributes
    """One sensor's statistics for one frame type."""

    def __init__(self) -> None:
        self.packets = 0
        self.times: Deque[float] = deque(maxlen=500)
        self.recent: Deque[Dict[str, Any]] = deque(maxlen=10)
        self.last_seen: Optional[float] = None
        self.burst_copies: set = set()
        self.burst_total = 0
        self.burst_last: Optional[float] = None
        self.expected = 0
        self.dropped = 0

    def close_burst(self) -> None:
        """End the burst: count its copies expected and those not heard."""
        if self.burst_total:
            self.expected += self.burst_total
            self.dropped += max(0, self.burst_total - len(self.burst_copies))
        self.burst_copies, self.burst_total, self.burst_last = set(), 0, None

    def add(self, when: float, frame: Optional[Dict[str, Any]]) -> None:
        """One copy heard at *when*, with its frame counter."""
        self.packets += 1
        self.last_seen = when
        copy = (frame or {}).get("repeat", 0) + 1
        total = (frame or {}).get("frames_per_packet", 0)
        if self.burst_last is not None and (copy == 1 or when - self.burst_last > BURST_GAP_S):
            self.close_burst()
        if copy == 1 or not self.times or when - self.times[-1] > BURST_GAP_S:
            previous = self.times[-1] if self.times else None
            self.times.append(when)
            self.recent.append({"t": when, "delta_s": None if previous is None
                                else round(when - previous, 3)})
        if total:
            self.burst_copies.add(copy)
            self.burst_total = total
            self.burst_last = when
            if len(self.burst_copies) >= total:
                self.close_burst()              # every copy heard: nothing to wait for

    def view(self, now: float) -> Dict[str, Any]:
        """The statistics at *now*, a burst quiet since before then closed."""
        if self.burst_last is not None and now - self.burst_last > BURST_GAP_S:
            self.close_burst()
        times = list(self.times)
        gaps = [(times[k], times[k + 1], times[k + 1] - times[k]) for k in range(len(times) - 1)
                if times[k + 1] > times[k]]
        row: Dict[str, Any] = {"frames": len(times), "packets": self.packets,
                               "expected": self.expected, "dropped": self.dropped,
                               "success_pct": round(100.0 * (self.expected - self.dropped)
                                                    / self.expected, 1) if self.expected else None,
                               "last_seen": self.last_seen,
                               "recent": list(reversed(self.recent))}
        if gaps:
            values = [gap for _a, _b, gap in gaps]
            mean = sum(values) / len(values)
            shortest = min(gaps, key=lambda gap: gap[2])
            longest = max(gaps, key=lambda gap: gap[2])
            row.update(mean_s=round(mean, 3),
                       std_s=round(math.sqrt(sum((v - mean) ** 2 for v in values)
                                             / len(values)), 3),
                       min_s=round(shortest[2], 3), min_between=shortest[:2],
                       max_s=round(longest[2], 3), max_between=longest[:2])
        return row


class Diagnostics:
    """Per sensor and frame type: frames, packets, drops and periods."""

    def __init__(self) -> None:
        self.sensors: Dict[str, Dict[str, _TypeStats]] = {}
        self.now = 0.0

    def feed(self, frame: Dict[str, Any]) -> bool:
        """Take one received frame as :class:`RfFrames` lists it."""
        decoded, sensor, when = frame.get("decoded"), frame.get("sensor_id"), frame.get("t")
        if not decoded or not sensor or not isinstance(when, (int, float)):
            return False
        self.now = max(self.now, when)
        kind = str(decoded.get("type") or "UNKNOWN")
        self.sensors.setdefault(sensor, {}).setdefault(kind, _TypeStats()).add(
            when, decoded.get("frame"))
        return True

    def reset(self, sensor: str = "") -> None:
        """Start the statistics again, for one sensor or all."""
        if sensor:
            self.sensors.pop(sensor, None)
        else:
            self.sensors.clear()

    def view(self, sensor: str = "") -> Dict[str, Any]:
        """The period table and overall success for *sensor*, or the first heard."""
        sensors = sorted(self.sensors)
        chosen = sensor if sensor in self.sensors else (sensors[0] if sensors else "")
        rows = []
        expected = dropped = 0
        for kind, stats in sorted(self.sensors.get(chosen, {}).items()):
            row = stats.view(self.now)
            row["type"] = kind
            expected += row["expected"]
            dropped += row["dropped"]
            rows.append(row)
        return {"sensors": sensors, "sensor": chosen, "types": rows,
                "overall": {"expected": expected, "dropped": dropped,
                            "received": expected - dropped,
                            "success_pct": round(100.0 * (expected - dropped) / expected, 1)
                            if expected else None}}


_CMD_PHASES = {0x0001: "REQ_LORES sent", 0x0002: "REQ_HIRES sent",
               0x8001: "ACK_LORES, escalating to HIRES", 0x8002: "ACK_HIRES",
               0x8003: "ACK_CONFIG", 0x0003: "Idle (GENERAL)",
               0x7F01: "NACK", 0x7F02: "NACK", 0x7F03: "NACK"}


class SyncTracker:
    """Each sensor's sync phase and countdowns, from CMD and RESPONSE frames."""

    def __init__(self) -> None:
        self.sensors: Dict[str, Dict[str, Any]] = {}
        self.now = 0.0

    def feed(self, frame: Dict[str, Any]) -> bool:
        """Take one received frame; ``True`` if it was a CMD or RESPONSE."""
        decoded, when = frame.get("decoded"), frame.get("t")
        if not decoded or not isinstance(when, (int, float)):
            return False
        self.now = max(self.now, when)
        kind = decoded.get("type")
        if kind == "CMD":
            sensor = str(decoded.get("sensor_id", ""))
            param = decoded.get("cmd_param")
            entry = self.sensors.get(sensor)
            if entry is None or param == 0x0001:
                entry = {"sensor_id": sensor, "slot": None, "lores_deadline": None,
                         "hires_deadline": None}
                self.sensors[sensor] = entry
            entry.update(phase=_CMD_PHASES.get(param, "CMD 0x%04X" % (param or 0)),
                         retry=decoded.get("retry"), last_seen=when)
            return True
        if kind == "RESPONSE":
            sensor = str(decoded.get("for_sensor", ""))
            if decoded.get("timer") is None:
                return True
            entry = self.sensors.setdefault(sensor, {"sensor_id": sensor, "retry": None,
                                                     "lores_deadline": None,
                                                     "hires_deadline": None})
            entry.update(slot=decoded.get("slot"), last_seen=when)
            if decoded.get("response_param") == 1:
                entry.update(phase="LORES: counting down",
                             lores_deadline=when + decoded["timer"] / 1000.0)
            else:
                entry.update(phase="HIRES: counting down",
                             hires_deadline=when + decoded["timer"] / 1e6)
            return True
        return False

    def view(self) -> Dict[str, Any]:
        """Every sensor heard in the last :data:`SYNC_IDLE_S`, with its countdowns."""
        rows: List[Dict[str, Any]] = []
        for sensor in sorted(self.sensors):
            entry = self.sensors[sensor]
            if self.now - entry.get("last_seen", self.now) > SYNC_IDLE_S:
                continue
            row = {key: entry.get(key) for key in ("sensor_id", "phase", "retry", "slot",
                                                    "last_seen")}
            lores, hires = entry.get("lores_deadline"), entry.get("hires_deadline")
            row["lores_remaining_s"] = None if lores is None else round(lores - self.now, 3)
            row["hires_remaining_s"] = None if hires is None else round(hires - self.now, 6)
            if row["phase"] == "NACK":
                row["state"] = "nack"
            elif hires is not None:
                row["state"] = "fired" if hires <= self.now else "hires"
            else:
                row["state"] = ""
            rows.append(row)
        return {"now": self.now, "sensors": rows}
