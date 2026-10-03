"""Notes and the report export, as rf_monitor had them (#156).

**Notes.** rf_monitor had a Fault Description and a Findings box, lost when it
closed. Here they are saved with the run: beside the event log, as
``<event log>.notes.json``, so they outlive the viewer and travel with the log.

**Report.** One self-contained HTML file - no scripts, nothing fetched - that
opens anywhere and prints to PDF from any browser (which is how a PDF is made:
no PDF library is needed). It holds what rf_monitor's export held, and the run:

* when it was made, from which event log, and the sensor it covers;
* the notes;
* the run: test specification, bench, verdict, and each test case;
* the sensor's identification (last VERSION frame);
* the Environment, Short Interval (Z axis) and Ticks graphs, and each TWF
  waveform with its spectrum, drawn as inline SVG;
* the configuration table and the Diagnostics period statistics;
* the latest frames, as rf_monitor's Latest Data log.

Traces to: VIEW-FR-040 .. VIEW-FR-042, VIEW-DD-REPORT.
"""

from __future__ import annotations

import datetime
import html
import json
import math
import os
from typing import Any, Dict, List, Optional

from .. import __version__

__all__ = ["NotesStore", "svg_chart", "build_report"]

#: Most characters kept in each note.
MAX_NOTE = 20000


class NotesStore:
    """The Fault Description and Findings for the event log being followed."""

    def __init__(self, event_log: Optional[str]) -> None:
        self.path = (event_log + ".notes.json") if event_log else None

    def load(self) -> Dict[str, Any]:
        """The notes saved for this run, or empty ones."""
        if self.path and os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    return {"fault": str(data.get("fault", "")),
                            "findings": str(data.get("findings", "")),
                            "updated": data.get("updated")}
            except (OSError, ValueError):
                pass
        return {"fault": "", "findings": "", "updated": None}

    def save(self, fault: Any, findings: Any) -> Dict[str, Any]:
        """Save the notes beside the event log.

        :raises ValueError: when no event log is being followed, or a note is not text.
        """
        if not self.path:
            raise ValueError("notes are saved beside a run's event log: start or attach one")
        if not isinstance(fault, str) or not isinstance(findings, str):
            raise ValueError("notes are text")
        notes = {"fault": fault[:MAX_NOTE], "findings": findings[:MAX_NOTE],
                 "updated": datetime.datetime.now().isoformat(timespec="seconds")}
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(notes, handle, indent=2)
        return notes


# ---------------------------------------------------------------------------
# Charts as SVG, for a report that has no scripts

_COLOURS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7",
            "#e34948")


def _ticks(low: float, high: float, count: int) -> List[float]:
    if not high > low:
        pad = abs(low) * 0.1 or 1.0
        low, high = low - pad, high + pad
    raw = (high - low) / count
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)
    return [k * step for k in range(math.floor(low / step), math.ceil(high / step) + 1)]


def _x_label(chart: Dict[str, Any], value: float) -> str:
    if chart.get("xunit"):
        return "%g %s" % (round(value, 3), chart["xunit"])
    if chart.get("x") == "dongle":
        return "%g s" % round(value, 3)
    return datetime.datetime.fromtimestamp(value).strftime("%H:%M:%S")


def svg_chart(  # pylint: disable=too-many-locals
        chart: Dict[str, Any], width: int = 860, height: int = 200) -> str:
    """A line chart as an SVG string: one y-axis, gridlines, a line per series,
    gaps where a value is ``None``. Empty string when there is nothing to draw."""
    points = [p for s in chart.get("series", []) for p in s.get("points", [])
              if p[1] is not None]
    if not points:
        return ""
    left, right, top, bottom = 60, 12, 10, 26
    plot_w, plot_h = width - left - right, height - top - bottom
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    low, high = min(ys), max(ys)
    if chart.get("zero"):
        low, high = min(low, 0), max(high, 0)
    y_ticks = _ticks(low, high, 4)
    y0, y1 = y_ticks[0], y_ticks[-1]
    x0, x1 = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1

    def sx(value):
        return left + (value - x0) / (x1 - x0) * plot_w

    def sy(value):
        return top + (1 - (value - y0) / ((y1 - y0) or 1)) * plot_h

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
             'height="%d" role="img" aria-label="%s">'
             % (width, height, width, height, html.escape(chart.get("title", "")))]
    for value in y_ticks:
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#e1e0d9"/>'
                     % (left, width - right, sy(value), sy(value)))
        parts.append('<text x="%d" y="%.1f" font-size="11" fill="#898781" '
                     'text-anchor="end">%g</text>' % (left - 6, sy(value) + 4, round(value, 6)))
    for value in _ticks(x0, x1, max(2, plot_w // 120)):
        if x0 <= value <= x1:
            parts.append('<text x="%.1f" y="%d" font-size="11" fill="#898781" '
                         'text-anchor="middle">%s</text>'
                         % (sx(value), height - 8, html.escape(_x_label(chart, value))))
    for index, series in enumerate(chart.get("series", [])):
        path, pen = [], "M"
        for point in series.get("points", []):
            if point[1] is None:
                pen = "M"
                continue
            path.append("%s%.1f %.1f" % (pen, sx(point[0]), sy(point[1])))
            pen = "L"
        if path:
            parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.5"/>'
                         % (" ".join(path), _COLOURS[index % len(_COLOURS)]))
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# The report

_CSS = """
body { font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color: #1b1f24;
       background: #fff; max-width: 960px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 16px; margin: 24px 0 6px;
     border-bottom: 1px solid #dfe3e8; padding-bottom: 2px; } h3 { font-size: 13px; margin: 14px 0 4px; }
.meta { color: #5d6673; } table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { text-align: left; padding: 2px 8px; border-bottom: 1px solid #eef0f3; vertical-align: top; }
th { color: #5d6673; font-weight: 500; } td.num { text-align: right; }
pre { white-space: pre-wrap; font: 12px ui-monospace, Consolas, monospace; background: #f6f7f9;
      padding: 8px; border-radius: 6px; } .PASS { color: #1f8a4c; } .FAIL { color: #c23b22; }
.ERROR { color: #b0127a; } .SKIP { color: #8a8f98; } svg { max-width: 100%; height: auto; }
@media print { body { margin: 0; } h2 { break-after: avoid; } svg, table { break-inside: avoid; } }
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _table(headers: List[str], rows: List[List[Any]], numeric=()) -> str:
    if not rows:
        return '<p class="meta">None.</p>'
    head = "".join("<th>%s</th>" % _e(h) for h in headers)
    body = "".join("<tr>%s</tr>" % "".join(
        '<td%s>%s</td>' % (' class="num"' if i in numeric else "", _e(c))
        for i, c in enumerate(row)) for row in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body)


def _charts(charts: List[Dict[str, Any]]) -> str:
    out = []
    for chart in charts:
        drawn = svg_chart(chart)
        if drawn:
            out.append("<h3>%s</h3>%s" % (_e(chart.get("title")), drawn))
    return "".join(out) or '<p class="meta">No data.</p>'


def _time(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""
    return datetime.datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def build_report(hub: Any, sensor: str = "") -> str:  # pylint: disable=too-many-locals
    """The run as one self-contained HTML document."""
    state = hub.since(hub.sequence, hub.generation)["state"]
    notes = NotesStore(hub.path).load()
    kepler = hub.kepler_screens(sensor)
    chosen = kepler.get("sensor") or sensor
    sensor_graphs = hub.sensor_graphs(chosen, "Z")
    diagnostics = hub.diagnostic_screens(chosen)["diagnostics"]
    parts = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
             "<title>Bench report: %s</title><style>%s</style></head><body>"
             % (_e(state.get("suite") or "test run"), _CSS),
             "<h1>Bench report: %s</h1>" % _e(state.get("suite") or "no run"),
             '<p class="meta">Made %s by benchtools %s from %s. Sensor %s.</p>'
             % (_e(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")), _e(__version__),
                _e(hub.path or "no event log"), _e("0x" + chosen if chosen else "none"))]
    if notes["fault"] or notes["findings"]:
        if notes["fault"]:
            parts.append("<h2>Fault description</h2><pre>%s</pre>" % _e(notes["fault"]))
        if notes["findings"]:
            parts.append("<h2>Findings</h2><pre>%s</pre>" % _e(notes["findings"]))
    plan = state.get("plan") or {}
    parts.append("<h2>Run</h2>")
    parts.append(_table(["Item", "Value"], [
        ["Test specification", state.get("suite")], ["Source", plan.get("spec_source")],
        ["Bench", "%s%s" % (plan.get("bench") or "", " (simulated)" if plan.get("simulated")
                            else "")],
        ["Verdict", state.get("status")], ["Started", _time(state.get("started"))],
        ["Finished", _time(state.get("finished"))]]))
    parts.append("<h3>Test cases</h3>")
    parts.append(_table(["Test case", "Requirement", "Status", "Reason"],
                        [[c.get("name"), c.get("requirement"), c.get("status"),
                          c.get("error") or c.get("skip_reason")]
                         for c in state.get("cases") or []]))
    identification = kepler.get("identification")
    parts.append("<h2>Identification</h2>")
    parts.append(_table(["Item", "Value"], [
        ["Sensor / product", "0x%s / %s" % (identification.get("sensor_id"),
                                            identification.get("product"))],
        ["Firmware", identification.get("version")], ["SHA", identification.get("sha")],
        ["PCB", identification.get("pcb")],
        ["Reset reason", ", ".join(identification.get("reset_reasons") or [])],
        ["Received", _time(identification.get("t"))]]) if identification
                 else '<p class="meta">No VERSION frame received.</p>')
    parts.append("<h2>Environment</h2>" + _charts(sensor_graphs["environment"]))
    parts.append("<h2>Short interval (Z axis)</h2>" + _charts(sensor_graphs["short_interval"]))
    parts.append("<h2>Ticks</h2>" + _charts(sensor_graphs["ticks"]))
    parts.append("<h2>Time waveforms</h2>")
    shown_any = False
    for buffer in ("A", "B"):
        for axis in ("X", "Y", "Z"):
            twf = hub.waveform(chosen, buffer, axis)
            capture = twf.get("capture")
            if not capture or twf.get("buffer") != buffer:
                continue
            shown_any = True
            parts.append("<h3>TWF%s %s-axis: %s, ODR %s Hz, %s of %s packets, %s</h3>" % (
                buffer, axis, "complete" if capture["complete"] else "partial",
                capture["odr_hz"], capture["packets"], capture["total_packets"],
                capture["method"]))
            parts.append(svg_chart({"title": "waveform", "unit": "mg", "xunit": "ms",
                                    "series": [{"points": twf["waveform"]}]}))
            parts.append(svg_chart({"title": "spectrum", "unit": "mg", "xunit": "Hz",
                                    "zero": True, "series": [{"points": twf["spectrum"]}]}))
    if not shown_any:
        parts.append('<p class="meta">No TWF frames.</p>')
    parts.append("<h2>Configuration</h2>")
    parts.append(_table(["Block", "Parameter", "Name", "Value", "Unit"],
                        [[r["block"], r["parameter"], r["name"], r["shown"], r["unit"]]
                         for r in kepler.get("config", []) if r["shown"] is not None]))
    parts.append("<h2>Diagnostics: period statistics</h2>")
    parts.append(_table(
        ["Frame type", "Frames", "Packets", "Dropped", "Success %", "Mean s", "Std dev s",
         "Min s", "Max s", "Last seen"],
        [[t["type"], t["frames"], t["packets"], t["dropped"] if t["expected"] else "-",
          t["success_pct"], t.get("mean_s"), t.get("std_s"), t.get("min_s"), t.get("max_s"),
          _time(t.get("last_seen"))] for t in diagnostics["types"]],
        numeric=(1, 2, 3, 4, 5, 6, 7, 8)))
    parts.append("<h2>Latest data</h2><pre>")
    for frame in kepler.get("latest", []):
        parts.append(_e("%s  Sensor 0x%s  %s  %s dBm\n" % (
            _time(frame.get("t")), frame.get("sensor_id"), frame.get("type"),
            frame.get("rssi_dbm"))))
        for name, value in frame.get("header", []) + frame.get("payload", []):
            parts.append(_e("    %-26s %s\n" % (name, value)))
        if frame.get("problem"):
            parts.append(_e("    %s\n" % frame["problem"]))
    parts.append("</pre></body></html>")
    return "".join(parts)
