"""Series for the viewer's graphs: readings over time, and BLE advertising (#140).

Values come from structured records, never from parsing text:

* ``reading`` records (CORE-FR-065), which the drivers log where they have a
  measurement in hand - the supply's voltage and current per channel, the
  thermometer's temperature, the multimeter's reading. Each instrument,
  quantity and channel is one series, grouped into one chart per unit, so no
  chart needs two y-axes.
* BLE advertising reports, from :class:`~benchtools.viewer.radio.BleAir`:
  per device, the interval between consecutive adverts on the dongle's own
  clock, each interval's difference from the device's typical interval (its
  median, or the period the operator expects), and the RSSI of each advert.

Step starts are markers on the time axis, so a change can be tied to the step
that caused it.

Traces to: VIEW-FR-016 .. VIEW-FR-018, VIEW-DD-GRAPHS.
"""

from __future__ import annotations

import statistics
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["Readings", "advertising", "step_markers", "KEEP_POINTS", "UNIT_NAMES"]

#: Points kept per series; older ones are dropped.
KEEP_POINTS = 5000

#: How a unit is named on a chart's axis.
UNIT_NAMES = {"A": "Current (A)", "V": "Voltage (V)", "degC": "Temperature (°C)",
              "ohm": "Resistance (Ω)", "Hz": "Frequency (Hz)"}


class Readings:
    """Every ``reading`` record, as series of ``(t, value)`` per instrument and quantity."""

    def __init__(self) -> None:
        self.series: Dict[str, Dict[str, Any]] = {}

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; ``True`` if it was a reading."""
        data = record.get("data")
        if record.get("kind") != "reading" or not isinstance(data, dict):
            return False
        value, when = data.get("value"), record.get("t")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or when is None:
            return False
        source = str(record.get("source", ""))
        quantity = str(data.get("quantity", "value"))
        channel = data.get("channel")
        key = "%s %s%s" % (source, quantity, " ch%s" % channel if channel is not None else "")
        entry = self.series.setdefault(key, {
            "key": key, "source": source, "quantity": quantity, "channel": channel,
            "unit": str(data.get("unit", "")), "points": deque(maxlen=KEEP_POINTS)})
        entry["points"].append((when, float(value)))
        return True

    def charts(self) -> List[Dict[str, Any]]:
        """One chart per unit, each with its series, in a fixed order by key."""
        by_unit: Dict[str, List[Dict[str, Any]]] = {}
        for key in sorted(self.series):
            entry = self.series[key]
            by_unit.setdefault(entry["unit"], []).append({
                "key": key, "label": key, "points": [list(point) for point in entry["points"]]})
        return [{"id": "unit-" + unit, "title": UNIT_NAMES.get(unit, unit or "Value"),
                 "unit": unit, "series": series} for unit, series in sorted(by_unit.items())]


def _intervals(adverts: List[Dict[str, Any]], origin: int) -> List[Tuple[float, float]]:
    """``(seconds on the dongle's clock, interval ms)`` between consecutive adverts.

    The dongle's clock, not the host's: the dongle reports adverts in batches,
    so the host's times bunch together while the dongle's say when each was heard.
    """
    out = []
    previous: Optional[int] = None
    for advert in adverts:
        board = advert.get("board_us")
        if not isinstance(board, int):
            continue
        if previous is not None and board > previous:
            out.append((round((board - origin) / 1e6, 6), (board - previous) / 1000.0))
        previous = board
    return out


def advertising(adverts: List[Dict[str, Any]], address: str = "",
                expected_ms: Optional[float] = None) -> Dict[str, Any]:
    """BLE advertising charts for one device - by default the one heard most.

    :param expected_ms: The advertising period the sensor should keep; the
        delta chart is measured against it, else against the median interval.
    :returns: ``devices`` heard, the ``address`` shown, its ``period_ms`` and
        whether it was the ``expected`` one or the median, and three charts:
        the interval, each interval's delta from the period, and RSSI.
    """
    counts: Dict[str, int] = {}
    for advert in adverts:
        counts[advert.get("addr", "")] = counts.get(advert.get("addr", ""), 0) + 1
    devices = sorted(counts, key=lambda item: (-counts[item], item))
    chosen = address if address in counts else (devices[0] if devices else "")
    mine = [advert for advert in adverts if advert.get("addr") == chosen
            and isinstance(advert.get("board_us"), int)]
    origin = mine[0]["board_us"] if mine else 0
    gaps = _intervals(mine, origin)
    period = expected_ms if expected_ms else (
        statistics.median(gap for _t, gap in gaps) if gaps else None)
    def series(key, points):
        return [{"key": key, "label": key, "points": points}]

    charts = [
        {"id": "ble-interval", "title": "Advertising interval (ms)", "unit": "ms",
         "x": "dongle", "series": series(chosen, [[t, gap] for t, gap in gaps])},
        {"id": "ble-delta", "title": "Interval minus %s period (ms)" % (
            "expected" if expected_ms else "median"), "unit": "ms", "zero": True,
         "x": "dongle",
         "series": series(chosen, [[t, round(gap - period, 3)] for t, gap in gaps]
                          if period is not None else [])},
        {"id": "ble-rssi", "title": "RSSI (dBm)", "unit": "dBm", "x": "dongle",
         "series": series(chosen, [[round((advert["board_us"] - origin) / 1e6, 6),
                                    advert["rssi"]] for advert in mine
                                   if isinstance(advert.get("rssi"), int)])},
    ]
    return {"devices": [{"addr": item, "adverts": counts[item]} for item in devices],
            "address": chosen, "period_ms": period, "expected": bool(expected_ms),
            "charts": charts}


def step_markers(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """When each step started, from the run's state: setup, test steps, teardown."""
    markers = []
    groups = [("Setup", state.get("setup") or [])]
    groups += [(case.get("name", ""), case.get("steps") or []) for case in state.get("cases") or []]
    groups.append(("Teardown", state.get("teardown") or []))
    for name, steps in groups:
        for step in steps:
            if step.get("started"):
                markers.append({"t": step["started"],
                                "label": "%s: %s" % (name, step.get("text", "")),
                                "status": step.get("status")})
    return sorted(markers, key=lambda marker: marker["t"])
