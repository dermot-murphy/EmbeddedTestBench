"""Readings logged by the drivers, and the viewer's graph series (#140).

Traces to: CORE-FR-065, PSU-FR-044, PICO-FR-048, DMM-FR-034, VIEW-FR-016 .. VIEW-FR-018,
SWE4-UT-VIEWGRAPHS.
"""

from __future__ import annotations

import logging

import pytest

from benchtools.core.events import EventTail, log_reading, start_event_log
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.gpd3303d import Gpd3303D
from benchtools.instruments.gpd3303d.simulator import SimulatedGpd
from benchtools.instruments.pico_sht30 import PicoSht30
from benchtools.instruments.pico_sht30.simulator import SimulatedPicoSht30
from benchtools.instruments.tti1604 import Tti1604
from benchtools.instruments.tti1604.simulator import SimulatedTti1604
from benchtools.viewer.graphs import Readings, advertising, step_markers
from benchtools.viewer.server import Hub


def _logged(tmp_path, action):
    path = str(tmp_path / "events.jsonl")
    handler = start_event_log(path)
    try:
        action()
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    return [r for r in EventTail(path).read() if r.get("kind") == "reading"]


class TestDriversLogReadings:
    def test_the_supply_s_voltage_and_current(self, tmp_path):
        def act():
            psu = Gpd3303D(MockTransport(responder=SimulatedGpd()))
            psu.initialise()
            psu.measure_voltage(1)
            psu.measure_current(2)
            psu.close()
        records = _logged(tmp_path, act)
        assert [(r["source"], r["data"]["quantity"], r["data"]["unit"], r["data"]["channel"])
                for r in records] == [("PSU", "voltage", "V", 1), ("PSU", "current", "A", 2)]

    def test_a_channel_reading_logs_both(self, tmp_path):
        def act():
            psu = Gpd3303D(MockTransport(responder=SimulatedGpd()))
            psu.initialise()
            psu.read_channel(1)
            psu.close()
        assert {r["data"]["quantity"] for r in _logged(tmp_path, act)} == {"voltage", "current"}

    def test_the_thermometer_s_temperature(self, tmp_path):
        def act():
            thermometer = PicoSht30(MockTransport(responder=SimulatedPicoSht30()))
            thermometer.initialise()
            value = thermometer.temperature()
            thermometer.close()
            assert isinstance(value, float)
        records = _logged(tmp_path, act)
        assert len(records) == 1
        data = records[0]["data"]
        assert (records[0]["source"], data["quantity"], data["unit"]) == (
            "TEMP", "temperature", "degC")
        assert data["text"] == "%.2f" % data["value"]

    def test_the_meter_s_reading(self, tmp_path):
        def act():
            meter = Tti1604(MockTransport(responder=SimulatedTti1604()))
            meter.initialise()
            meter.read()
            meter.close()
        records = _logged(tmp_path, act)
        assert records
        data = records[-1]["data"]
        assert records[-1]["source"] == "DMM"
        assert {"quantity", "value", "unit", "ac", "text"} <= set(data)

    def test_log_reading_is_ordinary_text_on_a_console(self, caplog):
        logger = logging.getLogger("benchtools.test")
        with caplog.at_level(logging.DEBUG, logger="benchtools.test"):
            log_reading(logger, "current", 0.012, "A", channel=1)
        assert caplog.records[-1].getMessage() == "reading current 0.012 A"


def _reading(t, source, quantity, value, unit, **detail):
    data = dict(detail, quantity=quantity, value=value, unit=unit)
    return {"kind": "reading", "t": t, "source": source, "data": data}


class TestReadings:
    def test_one_chart_per_unit_one_series_per_instrument_quantity_and_channel(self):
        readings = Readings()
        for record in (_reading(1.0, "PSU", "current", 0.01, "A", channel=1),
                       _reading(2.0, "PSU", "current", 0.02, "A", channel=1),
                       _reading(2.0, "PSU", "current", 0.03, "A", channel=2),
                       _reading(3.0, "PSU", "voltage", 3.2, "V", channel=1),
                       _reading(3.0, "DMM", "volts", 3.19, "V"),
                       _reading(4.0, "TEMP", "temperature", 22.4, "degC")):
            assert readings.feed(record)
        charts = {chart["unit"]: chart for chart in readings.charts()}
        assert set(charts) == {"A", "V", "degC"}
        assert [s["key"] for s in charts["A"]["series"]] == ["PSU current ch1", "PSU current ch2"]
        assert charts["A"]["series"][0]["points"] == [[1.0, 0.01], [2.0, 0.02]]
        assert [s["key"] for s in charts["V"]["series"]] == ["DMM volts", "PSU voltage ch1"]
        assert charts["degC"]["title"] == "Temperature (°C)"

    @pytest.mark.parametrize("record", [
        {"kind": "step_end", "t": 1.0, "data": {"value": 1}},
        _reading(None, "PSU", "current", 0.1, "A"),
        _reading(1.0, "PSU", "current", None, "A"),
        _reading(1.0, "PSU", "current", True, "A"),
    ])
    def test_what_is_not_a_reading_is_ignored(self, record):
        assert Readings().feed(record) is False


def _adverts(address, start_us, gaps_ms, rssi=-60):
    board, out = start_us, []
    for index, gap in enumerate([0] + list(gaps_ms)):
        board += int(gap * 1000)
        out.append({"t": 100.0, "addr": address, "board_us": board, "rssi": rssi - index})
    return out


class TestAdvertising:
    def test_interval_delta_and_rssi_on_the_dongle_s_clock(self):
        view = advertising(_adverts("AA", 5_000_000, [100, 104, 96, 100]))
        assert view["address"] == "AA"
        assert view["period_ms"] == 100
        interval, delta, rssi = (chart["series"][0]["points"] for chart in view["charts"])
        assert interval == [[0.1, 100.0], [0.204, 104.0], [0.3, 96.0], [0.4, 100.0]]
        assert [point[1] for point in delta] == [0.0, 4.0, -4.0, 0.0]
        assert rssi[0] == [0.0, -60] and len(rssi) == 5
        assert all(chart["x"] == "dongle" for chart in view["charts"])

    def test_an_expected_period_is_the_reference(self):
        view = advertising(_adverts("AA", 0, [100, 110]), expected_ms=105)
        assert view["expected"] is True
        assert [p[1] for p in view["charts"][1]["series"][0]["points"]] == [-5.0, 5.0]

    def test_the_device_heard_most_is_shown_unless_one_is_chosen(self):
        adverts = _adverts("AA", 0, [100]) + _adverts("BB", 0, [100, 100])
        assert advertising(adverts)["address"] == "BB"
        assert advertising(adverts, "AA")["address"] == "AA"
        assert advertising(adverts)["devices"] == [{"addr": "BB", "adverts": 3},
                                                   {"addr": "AA", "adverts": 2}]

    def test_nothing_heard(self):
        view = advertising([])
        assert view["address"] == "" and view["period_ms"] is None
        assert all(not chart["series"][0]["points"] for chart in view["charts"])


def test_step_markers_in_time_order():
    state = {
        "setup": [{"started": 1.0, "text": "PSU set voltage", "status": "PASS"}],
        "cases": [{"name": "a", "steps": [{"started": 3.0, "text": "x", "status": "PASS"},
                                          {"started": None, "text": "y"}]}],
        "teardown": [{"started": 5.0, "text": "PSU output off", "status": "PASS"}],
    }
    assert [(m["t"], m["label"]) for m in step_markers(state)] == [
        (1.0, "Setup: PSU set voltage"), (3.0, "a: x"), (5.0, "Teardown: PSU output off")]


def test_the_hub_serves_graphs(tmp_path):
    log = tmp_path / "events.jsonl"
    import json
    log.write_text("".join(json.dumps(record) + "\n" for record in (
        _reading(1.0, "PSU", "current", 0.01, "A", channel=1),
        {"t": 2.0, "source": "BLE", "logger": "benchtools.instruments.nordic_dongle.session",
         "text": "< +adv t=1000 addr=AA rssi=-50 name=X"},
        {"t": 2.1, "source": "BLE", "logger": "benchtools.instruments.nordic_dongle.session",
         "text": "< +adv t=101000 addr=AA rssi=-51 name=X"})))
    hub = Hub()
    hub.follow(str(log))
    hub.poll()
    graphs = hub.graphs()
    assert graphs["charts"][0]["unit"] == "A"
    assert graphs["ble"]["charts"][0]["series"][0]["points"] == [[0.1, 100.0]]
