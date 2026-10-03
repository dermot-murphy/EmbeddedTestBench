"""Radio traffic for the viewer: Kepler frames over the S2-LP, and BLE (#139).

**RF.** The S2-LP driver logs every packet it sends or receives as an
``rf_packet`` record (S2LP-FR-080). :class:`RfFrames` keeps the received
ones, decodes any the driver did not with the Kepler decoder, and keeps per
sensor the latest frame of each type, so the page can show both the frames as
they arrive and what each sensor last said.

**BLE.** The dongle's session logs every line it exchanges: ``> command``,
``< reply`` and ``< +event key=value ...``. :class:`BleAir` reads the events -
advertising reports (``+adv``), sensors found in a scan (``+sensor``),
connections (``+conn``, ``+disc``) - into a device table and an event list.
The commands and their replies are the Instruments page's (#138).

Traces to: VIEW-FR-013 .. VIEW-FR-015, VIEW-DD-RADIO.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from ..instruments.s2lp.kepler import decode_kepler_frame

__all__ = ["RfFrames", "BleAir", "parse_fields", "KEEP_FRAMES", "KEEP_BLE_EVENTS"]

#: Received frames kept for the page; older ones are dropped.
KEEP_FRAMES = 1000

#: BLE events kept for the page.
KEEP_BLE_EVENTS = 1000

#: Kepler fields worth a column in the sensor table, in order, when present.
SUMMARY_FIELDS = ("temperature_c", "battery_mv", "battery_loaded_mv", "version", "sha",
                  "frame_count", "ticks", "rms", "velocity", "peak_to_peak")

_FIELD = re.compile(r"(\w+)=(\S*)")


def parse_fields(text: str) -> Dict[str, Any]:
    """``key=value`` pairs of a dongle event line, numbers as numbers."""
    fields: Dict[str, Any] = {}
    for key, value in _FIELD.findall(text):
        if re.fullmatch(r"-?\d+", value):
            fields[key] = int(value)
        else:
            fields[key] = value
    return fields


def _summary(decoded: Dict[str, Any]) -> str:
    """One line of what a decoded frame says."""
    parts = []
    for key, value in decoded.items():
        if key in ("type", "pl_type", "sensor_id", "product_id", "rf_capability",
                   "type_capability", "hw_capability", "fw_capability", "warnings"):
            continue
        if isinstance(value, (dict, list)):
            continue
        parts.append("%s %s" % (key.replace("_", " "), value))
    return ", ".join(parts[:8])


class RfFrames:
    """Received Kepler frames, and each sensor's latest of every frame type."""

    def __init__(self) -> None:
        self.frames: Deque[Dict[str, Any]] = deque(maxlen=KEEP_FRAMES)
        self.sensors: Dict[str, Dict[str, Any]] = {}
        self.received = 0
        self.failed = 0
        self.sent = 0

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; ``True`` if it was a packet."""
        if record.get("kind") != "rf_packet" or not isinstance(record.get("data"), dict):
            return False
        packet = record["data"]
        if packet.get("direction") != "rx":
            self.sent += 1
            return True
        self.received += 1
        decoded, problem = packet.get("decoded"), packet.get("decode_error") or ""
        if packet.get("error"):
            self.failed += 1
            problem = problem or "the radio reported error 0x%02X" % packet["error"]
        elif not decoded and packet.get("hex"):
            try:
                decoded = decode_kepler_frame(bytes.fromhex(packet["hex"]))
            except ValueError as exc:
                problem = str(exc)
        decoded = decoded if isinstance(decoded, dict) else None
        sensor = (decoded or {}).get("sensor_id", "")
        frame = {
            "t": record.get("t"),
            "source": record.get("source"),
            "sensor_id": sensor,
            "type": (decoded or {}).get("type", ""),
            "length": packet.get("length"),
            "rssi_dbm": packet.get("rssi_dbm"),
            "board_time_us": packet.get("board_time_us"),
            "error": packet.get("error", 0),
            "hex": packet.get("hex", ""),
            "summary": _summary(decoded) if decoded else problem,
            "decoded": decoded,
            "problem": problem,
        }
        self.frames.append(frame)
        if sensor:
            entry = self.sensors.setdefault(sensor, {"sensor_id": sensor, "frames": 0,
                                                     "latest": {}, "first_t": frame["t"]})
            entry["frames"] += 1
            entry["last_t"] = frame["t"]
            entry["rssi_dbm"] = frame["rssi_dbm"]
            entry["latest"][frame["type"]] = {
                "t": frame["t"], "summary": frame["summary"],
                **{key: decoded[key] for key in SUMMARY_FIELDS if key in decoded}}
        return True

    def view(self, sensor: str = "", limit: int = 300) -> Dict[str, Any]:
        """The latest *limit* frames, of one sensor or all, and the sensor table."""
        frames = [dict(frame) for frame in self.frames
                  if not sensor or frame["sensor_id"] == sensor][-limit:]
        return {"frames": frames, "sensors": [dict(entry) for _id, entry in
                                              sorted(self.sensors.items())],
                "received": self.received, "failed": self.failed, "sent": self.sent}


class BleAir:
    """BLE advertising, scan results and connections, from the dongle's events."""

    def __init__(self) -> None:
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.events: Deque[Dict[str, Any]] = deque(maxlen=KEEP_BLE_EVENTS)
        self.adverts: Deque[Dict[str, Any]] = deque(maxlen=KEEP_BLE_EVENTS * 5)

    @staticmethod
    def is_dongle(record: Dict[str, Any]) -> bool:
        """Whether *record* is a line from a Nordic dongle's session."""
        return str(record.get("logger", "")).startswith("benchtools.instruments.nordic_dongle")

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; ``True`` if it was a dongle event."""
        if record.get("kind") or not self.is_dongle(record):
            return False
        text = str(record.get("text", ""))
        if not text.startswith("< +"):
            return False
        name, _, rest = text[3:].partition(" ")
        fields = parse_fields(rest)
        event = {"t": record.get("t"), "source": record.get("source"), "event": name,
                 "fields": fields}
        if name in ("adv", "sensor"):
            self._device(event)
        if name == "adv":
            self.adverts.append({"t": event["t"], "addr": fields.get("addr", ""),
                                 "board_us": fields.get("t"), "rssi": fields.get("rssi"),
                                 "ch": fields.get("ch"), "name": fields.get("name", "")})
        else:
            self.events.append(event)
        return True

    def _device(self, event: Dict[str, Any]) -> None:
        fields = event["fields"]
        address = str(fields.get("addr", ""))
        if not address:
            return
        device = self.devices.setdefault(address, {
            "addr": address, "name": "", "adverts": 0, "seen": 0, "rssi": None,
            "rssi_sum": 0, "rssi_n": 0, "first_us": None, "last_us": None, "last_t": None})
        if fields.get("name"):
            device["name"] = fields["name"]
        device["last_t"] = event["t"]
        if isinstance(fields.get("rssi"), int):
            device["rssi"] = fields["rssi"]
            device["rssi_sum"] += fields["rssi"]
            device["rssi_n"] += 1
        if event["event"] == "sensor":
            device["seen"] += 1
            return
        device["adverts"] += 1
        board = fields.get("t")
        if isinstance(board, int):
            if device["first_us"] is None:
                device["first_us"] = board
            device["last_us"] = board

    def view(self) -> Dict[str, Any]:
        """The device table - with mean RSSI and advertising interval - and events."""
        devices: List[Dict[str, Any]] = []
        for address in sorted(self.devices):
            device = dict(self.devices[address])
            heard, rssi_sum = device.pop("rssi_n"), device.pop("rssi_sum")
            device["rssi_mean"] = round(rssi_sum / heard, 1) if heard else None
            span: Optional[float] = None
            if device["adverts"] > 1 and device["first_us"] is not None:
                span = (device["last_us"] - device["first_us"]) / 1000.0
            device["interval_ms"] = round(span / (device["adverts"] - 1), 3) \
                if span is not None else None
            devices.append(device)
        return {"devices": devices, "events": [dict(event) for event in self.events][-300:],
                "adverts": len(self.adverts)}
