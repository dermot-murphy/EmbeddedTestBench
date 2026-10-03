"""rf_monitor's Environment, Short Interval and Ticks graphs, from received frames (#153).

Per sensor, from the frames :class:`~benchtools.viewer.radio.RfFrames` has
decoded:

* **Environment** - temperature (°C) and battery (V) from ALIVE, TWF and
  VERSION frames (VERSION's is the loaded battery);
* **Short Interval** - per axis, acceleration RMS and peak to peak in mg and
  velocity RMS in mm/s, from ALIVE frames and from TWF frames by their SI type,
  and the magnetometer's frequency and amplitude (counts) from TWF frames.
  rf_monitor's conversion: full scale ``8 << si_scale`` g,
  ``counts_per_g = 32767 / full_scale``, mg ``raw * 1000 / counts_per_g``,
  mm/s ``raw * 10 / counts_per_g``. The raw count is kept beside each value;
* **Ticks** - the tick counter (1 tick = 1 minute) from ALIVE frames, and the
  change from one frame to the next, a fall (a reset) shown as 0.

A sensor sends each frame several times (its frames per packet). rf_monitor
plotted every copy, so a point appeared up to three times; here a copy is
plotted only once - the first copy heard of each frame. The magnetometer is
recorded once per frame, where rf_monitor could record it twice.

Each chart has one y-axis: where rf_monitor drew raw counts with a second axis
in mg, the chart is in mg and the hover readout gives the count.

Traces to: VIEW-FR-031 .. VIEW-FR-033, VIEW-DD-SENSOR.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, Tuple

__all__ = ["SensorSeries", "to_mg", "to_mm_s", "KEEP_POINTS", "REPEAT_WINDOW_S"]

#: Points kept per series.
KEEP_POINTS = 1000

#: A copy of a frame within this long of the last plotted one of its type is a
#: repeat, whatever its counter says, in case the first copy was lost.
REPEAT_WINDOW_S = 1.0

_AXES = ("X", "Y", "Z")
_SI_TYPES = {0: "acc", 1: "vel", 2: "pk", 3: "mag_freq", 4: "mag_amp"}


def _counts_per_g(si_scale: int) -> float:
    return 32767.0 / (8 << (si_scale & 3))


def to_mg(raw: int, si_scale: int) -> float:
    """An acceleration count in mg, at the sensor's full scale ``8 << si_scale`` g."""
    return round(raw * 1000.0 / _counts_per_g(si_scale), 3)


def to_mm_s(raw: int, si_scale: int) -> float:
    """A velocity count in mm/s."""
    return round(raw * 10.0 / _counts_per_g(si_scale), 4)


class SensorSeries:
    """Per sensor, the Environment, Short Interval and Ticks series."""

    def __init__(self) -> None:
        self.sensors: Dict[str, Dict[str, Deque[Tuple[float, Any]]]] = {}
        self._last: Dict[Tuple[str, str], float] = {}

    def _series(self, sensor: str, name: str) -> Deque[Tuple[float, Any]]:
        return self.sensors.setdefault(sensor, {}).setdefault(name, deque(maxlen=KEEP_POINTS))

    def _first_copy(self, sensor: str, kind: str, decoded: Dict[str, Any], t: float) -> bool:
        """Whether this copy is the first heard of its frame, and so plotted."""
        repeat = (decoded.get("frame") or {}).get("repeat", 0)
        last = self._last.get((sensor, kind))
        if repeat > 0 and last is not None and t - last < REPEAT_WINDOW_S:
            return False
        self._last[(sensor, kind)] = t
        return True

    def feed(self, frame: Dict[str, Any]) -> bool:
        """Take one received frame as :class:`RfFrames` lists it; ``True`` if plotted."""
        decoded, sensor, when = frame.get("decoded"), frame.get("sensor_id"), frame.get("t")
        if not decoded or not sensor or not isinstance(when, (int, float)):
            return False
        kind = decoded.get("type")
        if kind not in ("ALIVE", "TWF", "VERSION"):
            return False
        packet = str(decoded.get("packet_number", ""))
        if not self._first_copy(sensor, kind + packet, decoded, when):
            return False
        if "temperature_c" in decoded:
            self._series(sensor, "temperature").append((when, decoded["temperature_c"]))
        battery = decoded.get("battery_mv", decoded.get("battery_loaded_mv"))
        if isinstance(battery, int):
            self._series(sensor, "battery").append((when, battery / 1000.0))
        if kind == "ALIVE":
            self._alive(sensor, decoded, when)
        elif kind == "TWF":
            self._twf(sensor, decoded, when)
        return True

    def _alive(self, sensor: str, decoded: Dict[str, Any], t: float) -> None:
        scale = int(decoded.get("si_scale", 0))
        for axis, index in zip(_AXES, range(3)):
            for name, key, convert in (("acc", "acc_rms", to_mg), ("vel", "velocity", to_mm_s),
                                       ("pk", "peak_to_peak", to_mg)):
                values = decoded.get(key) or []
                if len(values) == 3:
                    raw = values[index]
                    self._series(sensor, "%s_%s" % (name, axis)).append(
                        (t, (convert(raw, scale), raw)))
        if isinstance(decoded.get("ticks"), int):
            self._series(sensor, "ticks").append((t, decoded["ticks"]))

    def _twf(self, sensor: str, decoded: Dict[str, Any], t: float) -> None:
        param = decoded.get("param") or {}
        kind = _SI_TYPES.get(param.get("si_type"))
        scale = int(param.get("si_scale", 0))
        values = decoded.get("si") or []
        if kind is None or len(values) != 3:
            return
        for axis, raw in zip(_AXES, values):
            if kind in ("acc", "pk"):
                point = (to_mg(raw, scale), raw)
            elif kind == "vel":
                point = (to_mm_s(raw, scale), raw)
            else:
                point = (raw, raw)
            self._series(sensor, "%s_%s" % (kind, axis)).append((t, point))

    # ------------------------------------------------------------------
    def view(self, sensor: str = "", axis: str = "Z") -> Dict[str, Any]:
        """The three screens' charts for *sensor* (or the first heard) and *axis*."""
        sensors = sorted(self.sensors)
        chosen = sensor if sensor in self.sensors else (sensors[0] if sensors else "")
        axis = axis.upper() if axis.upper() in _AXES else "Z"
        data = self.sensors.get(chosen, {})

        def chart(chart_id, title, unit, name):
            # In time order, whatever order the frames were read in.
            points = [[when, value[0], value[1]] if isinstance(value, tuple) else [when, value]
                      for when, value in sorted(data.get(name, ()), key=lambda p: p[0])]
            return {"id": chart_id, "title": title, "unit": unit,
                    "series": [{"key": name, "label": chosen, "points": points}]}

        ticks = sorted(data.get("ticks", ()), key=lambda point: point[0])
        deltas = [[ticks[k + 1][0], max(0, ticks[k + 1][1] - ticks[k][1])]
                  for k in range(len(ticks) - 1)]
        tick_delta = {"id": "tick-delta", "title": "Tick delta (frame to frame)", "unit": "ticks",
                      "zero": True, "series": [{"key": "delta", "label": chosen,
                                                "points": deltas}]}
        return {
            "sensors": sensors, "sensor": chosen, "axis": axis,
            "environment": [chart("temperature", "Temperature (°C)", "degC", "temperature"),
                            chart("battery", "Battery (V)", "V", "battery")],
            "short_interval": [
                chart("acc", "Acceleration RMS (%s, mg)" % axis, "mg", "acc_%s" % axis),
                chart("vel", "Velocity RMS (%s, mm/s)" % axis, "mm/s", "vel_%s" % axis),
                chart("pk", "Peak to peak (%s, mg)" % axis, "mg", "pk_%s" % axis),
                chart("mag-freq", "Magnetometer frequency (%s, counts)" % axis, "counts",
                      "mag_freq_%s" % axis),
                chart("mag-amp", "Magnetometer amplitude (%s, counts)" % axis, "counts",
                      "mag_amp_%s" % axis)],
            "ticks": [chart("ticks", "Ticks (1 tick = 1 min)", "ticks", "ticks"), tick_delta],
        }
