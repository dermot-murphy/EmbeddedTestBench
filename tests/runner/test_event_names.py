"""Event-log names: allocated in the specification, attached on the bench (#126).

The specification's name wins; the bench's applies where the specification
gives none; the driver's default where neither does. Two instruments a run
uses may not share a name, defaults included.

Traces to: RUN-FR-008, CORE-FR-063, SWE4-UT-EVENTNAMES.
"""

from __future__ import annotations

import json
import logging
import pathlib

import pytest

from benchtools.core.errors import BenchConfigError, SpecError
from benchtools.core.events import start_event_log
from benchtools.runner.bench import Bench, BenchConfig, InstrumentConfig, load_bench
from benchtools.runner.report import format_markdown
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import TestSpec

ROOT = pathlib.Path(__file__).resolve().parents[2]

READ = [{"name": "read", "steps": [{"do": "temp.read"}]}]


def spec(instruments, tests=None):
    return TestSpec.from_mapping(
        {"name": "Names", "instruments": instruments, "tests": tests or READ})


def bench(instruments):
    return Bench(BenchConfig.from_mapping({"instruments": instruments}), simulate=True)


@pytest.fixture
def event_log(tmp_path):
    path = tmp_path / "events.jsonl"
    handler = start_event_log(str(path))
    yield path
    logging.getLogger("benchtools").removeHandler(handler)
    handler.close()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class TestTheSpecification:
    def test_a_driver_and_a_name(self):
        loaded = spec({"temp": {"driver": "pico-sht30", "event": "TEMP"}})
        assert loaded.instrument_drivers == {"temp": "pico-sht30"}
        assert loaded.instrument_events == {"temp": "TEMP"}

    def test_a_name_alone(self):
        loaded = spec({"temp": {"event": "TEMP"}})
        assert loaded.instrument_drivers == {} and loaded.instrument_events == {"temp": "TEMP"}

    def test_the_short_form_still_works(self):
        loaded = spec({"temp": "pico-sht30"})
        assert loaded.instrument_drivers == {"temp": "pico-sht30"}
        assert loaded.instrument_events == {}

    def test_an_invalid_name_is_refused(self):
        with pytest.raises(SpecError, match="1 to 8 characters"):
            spec({"temp": {"driver": "pico-sht30", "event": "temp"}})

    def test_a_shared_name_is_refused(self):
        with pytest.raises(SpecError, match="both given event name 'TEMP'"):
            spec({"a": {"event": "TEMP"}, "b": {"event": "TEMP"}})

    def test_an_unknown_key_is_refused(self):
        with pytest.raises(SpecError, match="unknown key"):
            spec({"temp": {"driver": "pico-sht30", "name": "TEMP"}})


class TestTheBench:
    def test_an_instrument_carries_a_name(self):
        item = InstrumentConfig.from_mapping(
            "temp", {"driver": "pico-sht30", "resource": "sim://", "event": "TEMP"})
        assert item.event == "TEMP" and "event" not in item.options

    def test_an_invalid_name_is_refused(self):
        with pytest.raises(BenchConfigError, match="1 to 8 characters"):
            InstrumentConfig.from_mapping("temp", {"driver": "pico-sht30", "event": "Temp"})

    def test_a_shared_name_is_refused_at_load(self):
        with pytest.raises(BenchConfigError, match="both given event name"):
            BenchConfig.from_mapping({"instruments": {
                "a": {"driver": "gpd3303d", "event": "PSU"},
                "b": {"driver": "gpd3303d", "event": "PSU"}}})

    def test_the_shipped_benches_name_the_thermometer_and_rtt(self):
        for name in ("lab1.yaml", "simulated_bench.yaml"):
            config = load_bench(str(ROOT / "benches" / name))
            assert config.instruments["temp"].driver == "pico-sht30"
            assert config.instruments["temp"].event == "TEMP"
            assert config.instruments["rtt"].event == "RTT"


class TestWhichNameWins:
    def test_the_specification_s(self):
        live = bench({"temp": {"driver": "pico-sht30", "event": "BENCHT"}})
        live.name_events({"temp": "SPECT"})
        assert live.event_source_for("temp") == "SPECT"

    def test_the_bench_s_when_the_specification_gives_none(self):
        live = bench({"temp": {"driver": "pico-sht30", "event": "BENCHT"}})
        live.name_events({})
        assert live.event_source_for("temp") == "BENCHT"

    def test_the_driver_s_default_when_neither_does(self):
        assert bench({"temp": {"driver": "pico-sht30"}}).event_source_for("temp") == "TEMP"

    def test_an_instrument_is_opened_under_its_name(self):
        live = bench({"temp": {"driver": "pico-sht30", "event": "BENCHT"}})
        live.name_events({"temp": "SPECT"})
        try:
            assert live.get("temp").event_source == "SPECT"
        finally:
            live.close()

    def test_an_open_instrument_is_renamed_for_the_next_specification(self):
        live = bench({"temp": {"driver": "pico-sht30"}})
        try:
            thermometer = live.get("temp")
            assert thermometer.event_source == "TEMP"
            live.name_events({"temp": "ROOM"})
            assert thermometer.event_source == "ROOM"
        finally:
            live.close()


class TestNoTwoInstrumentsShareAName:
    def test_two_defaults_clash(self):
        live = bench({"probe": {"driver": "jlink"}, "rtt": {"driver": "jlink-rtt"}})
        with pytest.raises(BenchConfigError, match="'probe' and 'rtt' are both JLINK"):
            live.check_event_sources(["probe", "rtt"])

    def test_naming_one_settles_it(self):
        live = bench({"probe": {"driver": "jlink"},
                      "rtt": {"driver": "jlink-rtt", "event": "RTT"}})
        live.check_event_sources(["probe", "rtt"])

    def test_only_the_instruments_a_run_uses_count(self):
        live = bench({"probe": {"driver": "jlink"}, "rtt": {"driver": "jlink-rtt"}})
        live.check_event_sources(["rtt"])

    def test_a_clash_stops_the_run_before_anything_connects(self):
        live = bench({"a": {"driver": "pico-sht30"}, "b": {"driver": "pico-sht30"}})
        tests = [{"name": "both", "steps": [{"do": "a.read"}, {"do": "b.read"}]}]
        record = BenchRunner(live).run(spec({}, tests))
        assert record.status is Status.ERROR
        assert "both TEMP" in record.setup_error
        assert not live.connected


class TestARun:
    def test_records_carry_the_specification_s_names(self, event_log):
        live = bench({"probe": {"driver": "jlink"}, "rtt": {"driver": "jlink-rtt"},
                      "temp": {"driver": "pico-sht30"}})
        tests = [{"name": "all three", "steps": [
            {"do": "temp.read"},
            {"do": "probe.read_memory", "with": {"address": 0x20000000, "size": 4}},
            {"do": "rtt.rtt_start"}, {"do": "rtt.rtt_stop"}]}]
        loaded = spec({"probe": {"driver": "jlink", "event": "PROBE"},
                       "rtt": {"driver": "jlink-rtt", "event": "RTT"},
                       "temp": {"driver": "pico-sht30", "event": "ROOM"}}, tests)
        with BenchRunner(live) as runner:
            record = runner.run(loaded)
        assert record.status is Status.PASS, [s.error for c in record.cases for s in c.steps]
        sources = {r["source"] for r in records(event_log)}
        assert {"PROBE", "RTT", "ROOM", "TEST"} <= sources
        assert not {"JLINK", "TEMP", "BENCH"} & sources

    def test_the_record_and_report_name_each_instrument(self):
        live = bench({"temp": {"driver": "pico-sht30", "event": "ROOM"}})
        with BenchRunner(live) as runner:
            record = runner.run(spec({"temp": "pico-sht30"}))
        assert record.instruments["temp"]["event"] == "ROOM"
        assert "| temp | ROOM | PicoSht30 |" in format_markdown(record)
