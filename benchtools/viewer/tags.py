"""Tags on each event record, for the Event log page's filters (#148).

The Event log page filters by instrument, by kind of event, by sensor and by
test. The record says its instrument (``source``); :class:`Tagger` adds the
rest as ``record["tags"]`` when the viewer reads it:

* ``kinds`` - what the record is, across instruments: ``rf_rx`` (an RF frame
  received), ``rf_tx``, ``reading``, ``runner`` (the run, a test case or a
  step), ``control`` (an operator's request and what the runner did), and
  ``ble_adv`` (a BLE advertising report).
* ``sensor`` - the sensor the record names: a received frame's Kepler sensor
  ID, or the ID in a BLE device's advertised name (``SENS-0A1B2C`` names
  ``0A1B2C``). ``None`` when it names none.
* ``test`` - the run and test case in progress when it was logged:
  ``"1. Suite > Test case"``, ``"... > setup"`` or ``"... > teardown"``, or
  ``None`` before any run. A log can hold several runs, and a run several test
  cases; this is what tells them apart.

Traces to: VIEW-FR-019 .. VIEW-FR-021, VIEW-DD-TAGS.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..instruments.s2lp.kepler import decode_kepler_frame

__all__ = ["Tagger", "sensor_of"]

_BLE_NAME = re.compile(r"name=[A-Za-z]+-([0-9A-Fa-f]{6})\b")


def sensor_of(record: Dict[str, Any]) -> Optional[str]:
    """The sensor ID *record* names, upper case, or ``None``."""
    data = record.get("data")
    if record.get("kind") == "rf_packet" and isinstance(data, dict):
        decoded = data.get("decoded")
        if isinstance(decoded, dict) and decoded.get("sensor_id"):
            return str(decoded["sensor_id"]).upper()
        if data.get("hex") and not data.get("error"):
            try:
                return decode_kepler_frame(bytes.fromhex(data["hex"]))["sensor_id"]
            except ValueError:
                return None
        return None
    match = _BLE_NAME.search(str(record.get("text", "")))
    return match.group(1).upper() if match else None


class Tagger:
    """Tags records in the order they were logged; keeps where the run is."""

    def __init__(self) -> None:
        self.runs = 0
        self.suite = ""
        self.where: Optional[str] = None
        self.tests: List[str] = []

    def _label(self, part: str) -> str:
        label = "%d. %s > %s" % (self.runs, self.suite, part)
        if label not in self.tests:
            self.tests.append(label)
        return label

    def labels(self) -> List[str]:
        """Every run and test case seen so far, in order, as tags name them."""
        return list(self.tests)

    def tag(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """The tags for *record*, which is also given them as ``record["tags"]``."""
        kind = record.get("kind") or ""
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        if kind == "run_start":
            self.runs += 1
            self.suite = str(data.get("suite", ""))
            self.where = self._label("setup")
        elif kind == "case_start":
            self.where = self._label(str(data.get("name", "")))
        elif kind == "step_start" and data.get("phase") == "teardown":
            self.where = self._label("teardown")
        tags = {"kinds": self._kinds(record, kind, data), "sensor": sensor_of(record),
                "test": self.where}
        if kind == "case_end" and data.get("skip_reason"):
            # A test case that never ran: tag its own end, not the one before.
            tags["test"] = self._label(str(data.get("name", "")))
        if kind == "run_end":
            self.where = None
        record["tags"] = tags
        return tags

    @staticmethod
    def _kinds(record: Dict[str, Any], kind: str, data: Dict[str, Any]) -> List[str]:
        if kind == "rf_packet":
            return ["rf_rx" if data.get("direction") == "rx" else "rf_tx"]
        if kind == "reading":
            return ["reading"]
        if kind.startswith(("run_", "case_", "step_")):
            return ["runner"]
        if kind.startswith("control"):
            return ["control"]
        if str(record.get("text", "")).startswith("< +adv"):
            return ["ble_adv"]
        return []
