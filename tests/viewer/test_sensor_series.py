"""rf_monitor's Environment, Short Interval and Ticks series (#153).

Traces to: VIEW-FR-031 .. VIEW-FR-033, SWE4-UT-VIEWSENSOR.
"""

from __future__ import annotations

import struct

import pytest

from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.viewer.sensor_series import SensorSeries, to_mg, to_mm_s

from . import radio_log


def _alive(ticks=388, repeat=0, **values):
    """An ALIVE frame; *values* may give acc, vel, pk, temperature, battery, si_scale."""
    acc = values.get("acc", (80, 60, 90))
    vel = values.get("vel", (30, 25, 40))
    pk = values.get("pk", (400, 350, 500))
    temperature, battery = values.get("temperature", 244), values.get("battery", 127)
    si_scale = values.get("si_scale", 0)
    frame = bytearray(35)
    frame[0:8] = bytes.fromhex("5c171203060c0403")
    frame[8] = ((repeat + 1) << 4) | 3
    frame[9:11] = struct.pack(">h", temperature)
    frame[11] = battery
    frame[12:14] = struct.pack(">H", ticks)
    frame[14] = si_scale
    frame[15:21] = struct.pack(">3H", *acc)
    frame[21:27] = struct.pack(">3H", *vel)
    frame[27:33] = struct.pack(">3H", *pk)
    frame[34] = 0x05
    return bytes(frame)


def _twf(si_type, si=(100, 200, 300), si_scale=1, packet=0):
    frame = bytearray(100)
    frame[0:8] = bytes.fromhex("5c171203060c0404")
    frame[8] = 0x08
    frame[9] = 0x13
    frame[10:12] = struct.pack(">h", 250)
    frame[12] = 126
    frame[13:15] = struct.pack(">H", (2 << 14) | (si_scale << 10) | (si_type << 5))
    frame[17:19] = struct.pack(">H", packet)
    frame[19:21] = struct.pack(">H", 64)
    frame[23:29] = struct.pack(">3H", *si)
    return bytes(frame)


def _frame(payload, t):
    decoded = decode_kepler_frame(payload)
    return {"t": t, "sensor_id": decoded["sensor_id"], "decoded": decoded}


def _feed(*frames):
    series = SensorSeries()
    for frame in frames:
        series.feed(frame)
    return series


def _points(view, group, chart_id):
    return next(c for c in view[group] if c["id"] == chart_id)["series"][0]["points"]


class TestConversion:
    def test_a_larger_full_scale_halves_the_counts_per_g(self):
        assert to_mg(100, 2) == pytest.approx(2 * to_mg(100, 1), abs=0.01)

    def test_rf_monitor_s_scaling(self):
        # full scale 8 << si_scale g; counts per g 32767 / full scale
        assert to_mg(4096, 0) == pytest.approx(1000.03, abs=0.01)
        assert to_mg(4096, 1) == pytest.approx(2000.06, abs=0.01)
        assert to_mm_s(4096, 0) == pytest.approx(10.0003, abs=0.0001)


class TestEnvironment:
    def test_temperature_and_battery_from_alive_twf_and_version(self):
        view = _feed(_frame(_alive(), 1.0), _frame(_twf(0), 2.0),
                     _frame(radio_log.VERSION, 3.0)).view()
        assert [p[1] for p in _points(view, "environment", "temperature")] == [24.4, 25.0, 26.2]
        assert [p[1] for p in _points(view, "environment", "battery")] == [2.54, 2.52, 2.54]

    def test_each_frame_once_however_many_copies(self):
        view = _feed(*[_frame(_alive(repeat=r), 1.0 + r * 0.05) for r in range(3)],
                     _frame(_alive(repeat=0), 61.0)).view()
        assert len(_points(view, "environment", "temperature")) == 2

    def test_a_later_copy_counts_when_the_first_was_lost(self):
        view = _feed(_frame(_alive(repeat=1), 1.0), _frame(_alive(repeat=2), 1.05)).view()
        assert len(_points(view, "environment", "temperature")) == 1


class TestShortInterval:
    def test_alive_per_axis_in_mg_and_mm_s_with_the_raw_count(self):
        view = _feed(_frame(_alive(), 1.0)).view(axis="Z")
        assert _points(view, "short_interval", "acc") == [[1.0, to_mg(90, 0), 90]]
        assert _points(view, "short_interval", "vel") == [[1.0, to_mm_s(40, 0), 40]]
        assert _points(view, "short_interval", "pk") == [[1.0, to_mg(500, 0), 500]]
        assert _points(_feed(_frame(_alive(), 1.0)).view(axis="x"), "short_interval",
                       "acc")[0][2] == 80

    @pytest.mark.parametrize("si_type, chart_id", [(0, "acc"), (1, "vel"), (2, "pk"),
                                                   (3, "mag-freq"), (4, "mag-amp")])
    def test_twf_si_values_by_their_type(self, si_type, chart_id):
        view = _feed(_frame(_twf(si_type), 1.0)).view(axis="Y")
        points = _points(view, "short_interval", chart_id)
        assert len(points) == 1 and points[0][2] == 200
        if chart_id in ("mag-freq", "mag-amp"):
            assert points[0][1] == 200
        elif chart_id == "vel":
            assert points[0][1] == to_mm_s(200, 1)
        else:
            assert points[0][1] == to_mg(200, 1)

    def test_each_twf_packet_once(self):
        view = _feed(_frame(_twf(3, packet=0), 1.0), _frame(_twf(3, packet=1), 1.1)).view()
        assert len(_points(view, "short_interval", "mag-freq")) == 2


class TestTicks:
    def test_ticks_come_from_alive_frames_only(self):
        view = _feed(_frame(_twf(0), 1.0)).view()
        assert not _points(view, "ticks", "ticks")

    def test_ticks_and_their_delta_a_reset_shown_as_zero(self):
        view = _feed(_frame(_alive(ticks=10), 60.0), _frame(_alive(ticks=11), 120.0),
                     _frame(_alive(ticks=2), 180.0)).view()
        assert [p[1] for p in _points(view, "ticks", "ticks")] == [10, 11, 2]
        assert _points(view, "ticks", "tick-delta") == [[120.0, 1], [180.0, 0]]


def test_sensors_and_their_choice():
    view = _feed(_frame(_alive(), 1.0), _frame(radio_log.OTHER_SENSOR, 2.0)).view()
    assert view["sensors"] == ["5C1712", "5C314E"] and view["sensor"] == "5C1712"
    assert _feed(_frame(_alive(), 1.0)).view(axis="Q")["axis"] == "Z"


def test_frames_without_a_sensor_or_time_are_ignored():
    series = SensorSeries()
    assert not series.feed({"t": 1.0, "sensor_id": "", "decoded": None})
    assert not series.feed({"t": None, "sensor_id": "5C1712",
                            "decoded": decode_kepler_frame(_alive())})
    assert not series.feed(_frame(bytes.fromhex("5c171203060c0405") + bytes(13), 1.0))
