"""Each instrument's commands paired with their replies, and front panels (#138).

Traces to: VIEW-FR-010 .. VIEW-FR-012, SWE4-UT-VIEWTRAFFIC.
"""

from __future__ import annotations

import logging
import pathlib

import pytest

from benchtools.core.events import start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.spec import load_spec
from benchtools.viewer.server import Hub
from benchtools.viewer.traffic import (
    EVENT, NOTE, RECEIVED, SENT, JlinkPanel, PsuPanel, Traffic, classify, panel_for,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
PSU = "benchtools.instruments.gpd3303d.psu"


def _record(source, text, t, logger=PSU, level="DEBUG"):
    return {"source": source, "text": text, "t": t, "logger": logger, "level": level}


def _feed(*records):
    traffic = Traffic()
    for record in records:
        traffic.feed(record)
    return traffic


class TestClassify:
    def test_a_line_that_is_only_a_prefix(self):
        assert classify(">> ") == (SENT, "")

    @pytest.mark.parametrize("text, expected", [
        (">> VSET1:3.300", (SENT, "VSET1:3.300")),
        ("<< 3.300V", (RECEIVED, "3.300V")),
        ("> ver", (SENT, "ver")),
        ("< ok fw=1.4.0", (RECEIVED, "ok fw=1.4.0")),
        ("< +scan t=2000000", (EVENT, "+scan t=2000000")),
        (">> 12-gdb-set confirm off", (SENT, "-gdb-set confirm off")),
        ("console SEGGER J-Link", (RECEIVED, "SEGGER J-Link")),
        ("async stopped {'reason': 'end'}", (EVENT, "stopped {'reason': 'end'}")),
        ("rtt: sensor: start", (EVENT, "sensor: start")),
        ("opened simulated GPD-3303D", (NOTE, "opened simulated GPD-3303D")),
    ])
    def test_each_kind_of_line(self, text, expected):
        assert classify(text) == expected


class TestPairing:
    def test_a_query_and_its_reply(self):
        traffic = _feed(_record("PSU", ">> VOUT1?", 1.0), _record("PSU", "<< 3.20V", 1.004))
        entry = traffic.view()["PSU"]["entries"][0]
        assert (entry["kind"], entry["text"], entry["replies"], entry["ms"]) == (
            "exchange", "VOUT1?", ["3.20V"], 4.0)

    def test_a_command_with_no_reply_is_closed_by_the_next(self):
        traffic = _feed(_record("PSU", ">> VSET1:3.2", 1.0), _record("PSU", ">> VOUT1?", 1.1),
                        _record("PSU", "<< 3.20V", 1.2))
        entries = traffic.view()["PSU"]["entries"]
        assert [(e["text"], e["replies"]) for e in entries] == [
            ("VSET1:3.2", []), ("VOUT1?", ["3.20V"])]

    def test_events_between_a_command_and_its_reply_do_not_steal_it(self):
        ble = "benchtools.instruments.nordic_dongle.session"
        traffic = _feed(_record("BLE", "> scan list", 1.0, ble),
                        _record("BLE", "< +sensor idx=0", 1.1, ble),
                        _record("BLE", "< ok sensors=1", 1.2, ble))
        entries = traffic.view()["BLE"]["entries"]
        assert [e["kind"] for e in entries] == ["exchange", EVENT]
        assert entries[0]["replies"] == ["ok sensors=1"]

    def test_a_reply_with_no_command_before_it_is_unasked(self):
        entry = _feed(_record("DMM", "<< frame", 1.0)).view()["DMM"]["entries"][0]
        assert entry["kind"] == "unasked"

    def test_sources_are_kept_apart_and_the_runner_is_not_an_instrument(self):
        traffic = _feed(_record("PSU", ">> *IDN?", 1.0), _record("PSU2", "<< late", 1.1),
                        _record("TEST", "step psu.output", 1.2, "benchtools.runner.runner"),
                        dict(_record("PSU", "x", 1.3), kind="step_end"))
        view = traffic.view()
        assert set(view) == {"PSU", "PSU2"}
        assert view["PSU"]["entries"][0]["replies"] == []
        assert view["PSU"]["driver"] == "gpd3303d"

    def test_a_window_selects_by_when_the_command_was_sent(self):
        traffic = _feed(*[_record("PSU", ">> VOUT1?", float(t)) for t in range(10)])
        assert [e["t"] for e in traffic.view(3, 5)["PSU"]["entries"]] == [3.0, 4.0, 5.0]
        assert len(traffic.view(limit=4)["PSU"]["entries"]) == 4

    def test_the_view_is_a_copy(self):
        traffic = _feed(_record("PSU", ">> *IDN?", 1.0), _record("PSU", "<< GW", 1.1))
        traffic.view()["PSU"]["entries"][0]["replies"].append("changed")
        assert traffic.view()["PSU"]["entries"][0]["replies"] == ["GW"]


class TestPanels:
    def test_the_supply_panel_from_its_traffic(self):
        panel = PsuPanel()
        for text in (">> *IDN?", "<< GW INSTEK,GPD-3303D,SN:1,V1.09", ">> VSET1:3.200",
                     ">> ISET1:0.500", ">> OUT1", ">> VOUT1?", "<< 3.198V", ">> IOUT1?",
                     "<< 0.012A", ">> STATUS?", "<< 1 0 0 1 1 X 1 X"):
            panel.feed(_record("PSU", text, 1.0))
        rows = dict(panel.rows())
        assert rows["Identity"].startswith("GW INSTEK")
        assert rows["Channel 1"] == "vout 3.198 V, iout 0.012 A, vset 3.2 V, iset 0.5 A, CV"
        assert rows["Channel 2"] == "CC"
        assert rows["Output"] == "on"

    def test_the_probe_panel_from_its_traffic(self):
        panel = JlinkPanel()
        for text in ('>> 1-file-exec-and-symbols "app.elf"', "console SEGGER J-Link V11",
                     ">> 2-break-insert main", "flashed 17280 bytes in 3 section(s)",
                     "async stopped {'reason': 'breakpoint-hit', 'bkptno': '1', "
                     "'frame': {'func': 'main', 'file': 'main.c', 'line': '9'}}",
                     "rtt: hello"):
            panel.feed(_record("JLINK", text, 1.0, "benchtools.instruments.jlink.session"))
        rows = dict(panel.rows())
        assert rows["Firmware (ELF)"] == "app.elf"
        assert rows["Core"] == "halted: breakpoint-hit 1, main (main.c:9)"
        assert rows["Breakpoints"] == "1"
        assert rows["Last RTT line"] == "hello"

    def test_a_panel_is_chosen_by_driver(self):
        assert isinstance(panel_for(PSU), PsuPanel)
        assert isinstance(panel_for("benchtools.instruments.jlink.rtt"), JlinkPanel)
        assert panel_for("benchtools.core.transport.mock") is None


class TestRecordedRun:
    """A simulated run's own event log, paired as the viewer pairs it."""

    @pytest.fixture(scope="class")
    def hub(self, tmp_path_factory):
        pytest.importorskip("yaml")
        path = str(tmp_path_factory.mktemp("traffic") / "events.jsonl")
        handler = start_event_log(path)
        spec = load_spec(str(ROOT / "specs" / "sensor_power_signal_and_link.yaml"))
        try:
            aliases = {alias: spec.instrument_drivers.get(alias, "")
                       for alias in spec.instruments_used}
            with BenchRunner.from_config(BenchConfig.simulated(aliases), simulate=True) as runner:
                runner.run(spec)
        finally:
            logging.getLogger("benchtools").removeHandler(handler)
            handler.close()
        hub = Hub()
        hub.follow(path)
        hub.poll()
        return hub

    def test_every_supply_query_has_its_reply(self, hub):
        entries = hub.traffic.view()["PSU"]["entries"]
        queries = [e for e in entries if e["kind"] == "exchange" and e["text"].endswith("?")]
        assert queries
        assert all(len(e["replies"]) == 1 for e in queries)

    def test_no_dongle_reply_is_left_unasked(self, hub):
        entries = hub.traffic.view()["BLE"]["entries"]
        assert not [e for e in entries if e["kind"] == "unasked"]
        assert all(e["replies"] for e in entries if e["kind"] == "exchange")

    def test_a_step_s_window_holds_only_its_own_traffic(self, hub):
        steps = [r for _n, r in hub.records if r.get("kind") == "step_end"
                 and r["data"]["action"].startswith("psu.")]
        assert steps
        end = steps[0]
        start = next(r for _n, r in hub.records if r.get("kind") == "step_start"
                     and r["data"]["case"] == end["data"]["case"]
                     and r["data"]["step"] == end["data"]["step"]
                     and r["data"]["phase"] == end["data"]["phase"])
        window = hub.instruments(start["t"], end["t"])["sources"]
        assert window["PSU"]["entries"]
        assert all(start["t"] <= e["t"] <= end["t"]
                   for listed in window.values() for e in listed["entries"])

    def test_the_panels_are_built(self, hub):
        panels = hub.instruments()["panels"]
        assert panels["PSU"]["kind"] == "psu"
        assert dict(panels["PSU"]["rows"])["Identity"].startswith("GW INSTEK")
        assert panels["JLINK"]["kind"] == "jlink"

    def test_a_new_run_in_the_log_starts_the_traffic_afresh(self, hub):
        first = next(r for _n, r in hub.records if r.get("kind") == "run_start")
        fresh = Hub()
        fresh._apply(_record("PSU", ">> *IDN?", 1.0))   # pylint: disable=protected-access
        fresh._apply(first)                              # pylint: disable=protected-access
        assert not fresh.instruments()["sources"]
