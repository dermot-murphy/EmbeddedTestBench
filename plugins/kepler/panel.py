"""Kepler's viewer panel: rf_monitor's screens, and Kepler's sections of the report (#303).

The viewer feeds every received frame to each plugin panel and asks it what
to show (``benchtools.core.plugins``). :class:`KeplerPanel` is the one Kepler
panel. It holds rf_monitor's screens, each a tab on the viewer's RF page:

* Latest Data, Config and Identification - :class:`.view.KeplerView`;
* Environment, Short Interval and Ticks - :class:`.series.SensorSeries`;
* TWF - :class:`.twf.TwfAssembler`;
* Diagnostics and Sync - :class:`.diagnostics.Diagnostics` and
  :class:`.diagnostics.SyncTracker`.

``view(sensor, tab=...)`` gives one tab's data; ``action("reset", sensor)``
starts the Diagnostics statistics again; ``report(sensor)`` gives the report's
Kepler sections as data - tables, charts and text - which the viewer draws.
Until #303 these screens were the viewer's own, and named Kepler's fields
there.

Traces to: VIEW-FR-028 .. VIEW-FR-042, VIEW-FR-047, VIEW-DD-KEPLER.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Tuple

from .diagnostics import Diagnostics, SyncTracker
from .series import SensorSeries
from .twf import TwfAssembler
from .view import KeplerView

__all__ = ["KeplerPanel", "TABS"]

#: The panel's tabs on the RF page, in order: id and label.
TABS: Tuple[Tuple[str, str], ...] = (
    ("latest", "Latest Data"), ("config", "Config"), ("identification", "Identification"),
    ("environment", "Environment"), ("short", "Short Interval"), ("ticks", "Ticks"),
    ("twf", "TWF"), ("diagnostics", "Diagnostics"), ("sync", "Sync"))

_SCREEN_TABS = ("latest", "config", "identification")
_SERIES_TABS = ("environment", "short", "ticks")


def _time(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""
    return datetime.datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


class KeplerPanel:
    """Every rf_monitor screen, fed the same received frames."""

    def __init__(self) -> None:
        self.screens = KeplerView()
        self.series = SensorSeries()
        self.twf = TwfAssembler()
        self.diagnostics = Diagnostics()
        self.sync = SyncTracker()

    def feed(self, frame: Dict[str, Any]) -> None:
        """One received frame, as the viewer's radio view holds it."""
        self.screens.feed(frame)
        self.series.feed(frame)
        self.twf.feed(frame)
        self.diagnostics.feed(frame)
        self.sync.feed(frame)

    def view(self, sensor: str = "", tab: str = "latest", axis: str = "",
             buffer: str = "A") -> Dict[str, Any]:
        """One tab's data for *sensor*, or the first heard.

        Latest Data, Config and Identification share one reply, as do
        Diagnostics and Sync, and Environment, Short Interval and Ticks.
        """
        if tab in _SERIES_TABS:
            return self.series.view(sensor, axis or "Z")
        if tab == "twf":
            return self.twf.view(sensor, buffer, axis or "X")
        if tab in ("diagnostics", "sync"):
            return {"diagnostics": self.diagnostics.view(sensor), "sync": self.sync.view()}
        return self.screens.view(sensor)

    def action(self, name: str, sensor: str = "") -> Dict[str, Any]:
        """``reset``: start the Diagnostics statistics again, for *sensor* or all.

        :raises ValueError: for any other action.
        """
        if name != "reset":
            raise ValueError("the kepler panel has no action %r; it has: reset" % name)
        self.diagnostics.reset(sensor)
        return {"ok": True}

    # ------------------------------------------------------------------
    def report(self, sensor: str = "") -> Dict[str, Any]:
        """The report's Kepler sections for *sensor*, or the first heard, as data."""
        screens = self.screens.view(sensor)
        chosen = screens.get("sensor") or sensor
        graphs = self.series.view(chosen, "Z")
        sections: List[Dict[str, Any]] = [
            {"title": "Identification", "blocks": [self._identification(screens)]},
            {"title": "Environment", "blocks": [{"charts": graphs["environment"]}]},
            {"title": "Short interval (Z axis)", "blocks": [{"charts": graphs["short_interval"]}]},
            {"title": "Ticks", "blocks": [{"charts": graphs["ticks"]}]},
            {"title": "Time waveforms", "blocks": self._waveforms(chosen)},
            {"title": "Configuration", "blocks": [{"table": {
                "headers": ["Block", "Parameter", "Name", "Value", "Unit"],
                "rows": [[r["block"], r["parameter"], r["name"], r["shown"], r["unit"]]
                         for r in screens.get("config", []) if r["shown"] is not None]}}]},
            {"title": "Diagnostics: period statistics", "blocks": [self._diagnostics(chosen)]},
            {"title": "Latest data", "blocks": [{"text": self._latest(screens)}]},
        ]
        return {"sensor": chosen, "sections": sections}

    @staticmethod
    def _identification(screens: Dict[str, Any]) -> Dict[str, Any]:
        identification = screens.get("identification")
        if not identification:
            return {"note": "No VERSION frame received."}
        return {"table": {"headers": ["Item", "Value"], "rows": [
            ["Sensor / product", "0x%s / %s" % (identification.get("sensor_id"),
                                                identification.get("product"))],
            ["Firmware", identification.get("version")], ["SHA", identification.get("sha")],
            ["PCB", identification.get("pcb")],
            ["Reset reason", ", ".join(identification.get("reset_reasons") or [])],
            ["Received", _time(identification.get("t"))]]}}

    def _waveforms(self, sensor: str) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for buffer in ("A", "B"):
            for axis in ("X", "Y", "Z"):
                twf = self.twf.view(sensor, buffer, axis)
                capture = twf.get("capture")
                if not capture or twf.get("buffer") != buffer:
                    continue
                blocks.append({"heading": "TWF%s %s-axis: %s, ODR %s Hz, %s of %s packets, %s" % (
                    buffer, axis, "complete" if capture["complete"] else "partial",
                    capture["odr_hz"], capture["packets"], capture["total_packets"],
                    capture["method"])})
                blocks.append({"chart": {"title": "waveform", "unit": "mg", "xunit": "ms",
                                         "series": [{"points": twf["waveform"]}]}})
                blocks.append({"chart": {"title": "spectrum", "unit": "mg", "xunit": "Hz",
                                         "zero": True, "series": [{"points": twf["spectrum"]}]}})
        return blocks or [{"note": "No TWF frames."}]

    def _diagnostics(self, sensor: str) -> Dict[str, Any]:
        types = self.diagnostics.view(sensor)["types"]
        return {"table": {
            "headers": ["Frame type", "Frames", "Packets", "Dropped", "Success %", "Mean s",
                        "Std dev s", "Min s", "Max s", "Last seen"],
            "rows": [[t["type"], t["frames"], t["packets"],
                      t["dropped"] if t["expected"] else "-", t["success_pct"], t.get("mean_s"),
                      t.get("std_s"), t.get("min_s"), t.get("max_s"), _time(t.get("last_seen"))]
                     for t in types],
            "numeric": [1, 2, 3, 4, 5, 6, 7, 8]}}

    @staticmethod
    def _latest(screens: Dict[str, Any]) -> str:
        lines: List[str] = []
        for frame in screens.get("latest", []):
            lines.append("%s  Sensor 0x%s  %s  %s dBm\n" % (
                _time(frame.get("t")), frame.get("sensor_id"), frame.get("type"),
                frame.get("rssi_dbm")))
            for name, value in frame.get("header", []) + frame.get("payload", []):
                lines.append("    %-26s %s\n" % (name, value))
            if frame.get("problem"):
                lines.append("    %s\n" % frame["problem"])
        return "".join(lines)
