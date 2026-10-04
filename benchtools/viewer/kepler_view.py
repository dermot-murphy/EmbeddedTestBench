"""rf_monitor's Latest Data, Config and Identification screens, from received frames (#152).

The Kepler project's rf_monitor showed each frame as it arrived, broken into
its header and payload; the latest value of every configuration parameter a
sensor has sent; and what its last VERSION frame said. :class:`KeplerView`
keeps the same, per sensor, from the frames :class:`~benchtools.viewer.radio.RfFrames`
has decoded, with the names the firmware gives (S2LP-FR-081 .. -083).

Traces to: VIEW-FR-028 .. VIEW-FR-030, VIEW-DD-KEPLER.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from ..instruments.s2lp.kepler_tables import CONFIG_PARAMETERS, CONFIG_PER_FRAME

__all__ = ["KeplerView", "byte_roles", "header_rows", "payload_rows", "CONFIG_GROUPS",
           "KEEP_LATEST"]

#: Frames kept for Latest Data.
KEEP_LATEST = 500

_HEADER_KEYS = {"type", "pl_type", "sensor_id", "product_id", "product", "rf_capability",
                "type_capability", "hw_capability", "fw_capability", "frame",
                "permute_method", "warnings"}

#: Units of decoded fields, for the payload rows.
_UNITS = {"temperature_c": "°C", "battery_mv": "mV", "battery_loaded_mv": "mV",
          "time_taken_us": "µs", "odr_hz": "Hz", "timer": "", "rssi_dbm": "dBm"}

#: rf_monitor's summary tables on its Config screen: title to parameter names.
CONFIG_GROUPS: List[Tuple[str, List[str]]] = [
    ("Operation timings", ["Wakeup Idle Count", "Sample Delay Count", "Post Sample Interval",
                           "Seek Machine On", "Delay Confirm", "Confirm Machine",
                           "Transmit TWF", "Return Idle", "Machine ON Confirm Count"]),
    ("Trigger settings", ["Trigger Method", "TWFA Scaling", "TWFB Scaling",
                          "Machine ACC Threshold", "Machine Peaks Threshold",
                          "Machine ACC Detect", "Machine VEL Threshold",
                          "Machine Pk2Pk Threshold"]),
    ("Sampling", ["TWFA Enable", "TWFA ODR", "TWFA Samples", "TWFA X Enable", "TWFA Y Enable",
                  "TWFA Z Enable", "TWFA X Sampling", "TWFA Y Sampling", "TWFA Z Sampling",
                  "TWFB Enable", "TWFB ODR", "TWFB Samples", "TWFB X Enable", "TWFB Y Enable",
                  "TWFB Z Enable", "TWFB X Sampling", "TWFB Y Sampling", "TWFB Z Sampling",
                  "RMS ODR", "RMS Samples", "RMS Min Frequency"]),
    ("Sync", ["Sync Enable", "Sync Retry", "Sync Max Wait", "Listen Enable"]),
    ("FFT", ["FFT Enable", "FFT3 Axis Enable", "FFT3 First Bin", "FFT3 Last Bin", "FFT ODR",
             "FFT Samples", "FFT Scaling", "Short Capture", "FFT Machine Off Count"]),
    ("Other", ["Alive Period", "Battery Sample Delay", "Permute Method", "Transit Max Time",
               "Transit Wait Time", "Ignore Duration", "Frames Per Packet", "Preamble Length",
               "DC Offset Enable"]),
]


def byte_roles(decoded: Optional[Dict[str, Any]], length: int) -> List[str]:
    """What each byte of a frame is, for colouring: ``header``, ``type``,
    ``permute``, ``counter`` or ``payload``."""
    roles = ["payload"] * length
    for index in range(min(7, length)):
        roles[index] = "header"
    if length > 7:
        roles[7] = "type"
    if not decoded:
        return roles
    permuted = "permute_method" in decoded
    if permuted and length > 8:
        roles[8] = "permute"
    if "frame" in decoded:
        at = 9 if permuted else 8
        if length > at:
            roles[at] = "counter"
    return roles


def header_rows(decoded: Dict[str, Any]) -> List[Tuple[str, str]]:
    """rf_monitor's "Packet Header" rows for a decoded frame."""
    rows = [("Sensor ID", "0x%s" % decoded.get("sensor_id", "")),
            ("Product", "%s (%s)" % (decoded.get("product", ""), decoded.get("product_id", ""))),
            ("RF capability", "RF02 (issue %s)" % decoded.get("rf_capability", "")),
            ("HW capability / type", "HW %s, type %s" % (decoded.get("hw_capability", ""),
                                                        decoded.get("type_capability", ""))),
            ("FW capability", str(decoded.get("fw_capability", "")))]
    if "permute_method" in decoded:
        rows.append(("Permute control", str(decoded["permute_method"]).capitalize()))
    frame = decoded.get("frame")
    if isinstance(frame, dict):
        rows.append(("Frame counter", "%d of %d" % (frame.get("repeat", 0) + 1,
                                                   frame.get("frames_per_packet", 0))))
    return rows


def _value(key: str, value: Any) -> str:
    if key == "ticks" and isinstance(value, int):
        seconds = value * 60
        return "%d (%02d:%02d:%02d:%02d)" % (value, seconds // 86400, seconds // 3600 % 24,
                                            seconds // 60 % 60, seconds % 60)
    if isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) for v in value):
        return "X %d  Y %d  Z %d" % tuple(value)
    if isinstance(value, dict):
        return ", ".join("%s %s" % (k.replace("_", " "), v) for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if len(value) <= 12 else \
            "%d values" % len(value)
    unit = _UNITS.get(key, "")
    return "%s %s" % (value, unit) if unit else str(value)


def payload_rows(decoded: Dict[str, Any]) -> List[Tuple[str, str]]:
    """rf_monitor's "Payload" rows: every decoded field that is not the header's."""
    rows = []
    for key, value in decoded.items():
        if key in _HEADER_KEYS or key in ("parameters", "samples", "bins", "values"):
            continue
        rows.append((key.replace("_", " ").capitalize(), _value(key, value)))
    for parameter in decoded.get("parameters") or []:
        name = parameter.get("name") or "slot %d (not identified)" % parameter["slot"]
        rows.append((name, ("%s %s" % (parameter["shown"], parameter["unit"])).strip()))
    if decoded.get("samples"):
        rows.append(("Samples", ", ".join(str(v) for v in decoded["samples"])))
    return rows


class KeplerView:
    """Per sensor: the latest frames, every configuration parameter's latest value,
    and the identification from its last VERSION frame."""

    def __init__(self) -> None:
        self.latest: Deque[Dict[str, Any]] = deque(maxlen=KEEP_LATEST)
        self.config: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.identification: Dict[str, Dict[str, Any]] = {}

    def feed(self, frame: Dict[str, Any]) -> None:
        """Take one received frame as :class:`RfFrames` lists it."""
        decoded = frame.get("decoded")
        length = len(frame.get("hex", "")) // 2
        entry = {"t": frame.get("t"), "sensor_id": frame.get("sensor_id", ""),
                 "type": frame.get("type", ""), "rssi_dbm": frame.get("rssi_dbm"),
                 "hex": frame.get("hex", ""), "problem": frame.get("problem", ""),
                 "roles": byte_roles(decoded, length),
                 "header": header_rows(decoded) if decoded else [],
                 "payload": payload_rows(decoded) if decoded else []}
        self.latest.append(entry)
        if not decoded or not frame.get("sensor_id"):
            return
        sensor = frame["sensor_id"]
        if decoded.get("type") == "CONFIG":
            for parameter in decoded.get("parameters") or []:
                if parameter.get("parameter") is not None:
                    self.config.setdefault(sensor, {})[parameter["parameter"]] = dict(
                        parameter, t=frame.get("t"))
        elif decoded.get("type") == "VERSION":
            self.identification[sensor] = dict(decoded, t=frame.get("t"),
                                               rssi_dbm=frame.get("rssi_dbm"))

    def view(self, sensor: str = "", limit: int = 50) -> Dict[str, Any]:
        """Latest Data (of *sensor*, or all), and *sensor*'s - or the first's - config
        and identification."""
        latest = [dict(entry) for entry in self.latest
                  if not sensor or entry["sensor_id"] == sensor][-limit:]
        sensors = sorted(set(self.config) | set(self.identification))
        chosen = sensor if sensor else (sensors[0] if sensors else "")
        known = self.config.get(chosen, {})
        table = []
        for index, (name, unit, kind) in enumerate(CONFIG_PARAMETERS):
            item = known.get(index)
            table.append({"parameter": index, "block": index // CONFIG_PER_FRAME, "name": name,
                          "unit": unit, "value": item["value"] if item else None,
                          "shown": item["shown"] if item else None,
                          "t": item["t"] if item else None,
                          "disabled": kind == "enable" and item is not None and not item["value"]})
        by_name = {row["name"]: row for row in table}
        groups = [{"title": title, "rows": [by_name[name] for name in names if name in by_name]}
                  for title, names in CONFIG_GROUPS]
        return {"latest": latest, "sensor": chosen, "config": table, "groups": groups,
                "identification": self.identification.get(chosen)}
