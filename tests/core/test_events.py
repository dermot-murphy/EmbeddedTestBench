"""The bench event log (#82), and the name each instrument's records carry (#126).

Traces to: CORE-FR-060, CORE-FR-063, SWE4-UT-EVENTS.
"""

from __future__ import annotations

import json
import logging

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.core.events import (
    SOURCES,
    EventSource,
    EventTail,
    SourceLogger,
    connecting_as,
    source_of,
    start_event_log,
    validate_source_name,
)


@pytest.fixture
def event_log(tmp_path):
    path = tmp_path / "events.jsonl"
    handler = start_event_log(str(path))
    yield path
    logging.getLogger("benchtools").removeHandler(handler)
    handler.close()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("name,source", [
    ("benchtools.instruments.gpd3303d.psu", "PSU"),
    ("benchtools.instruments.nordic_dongle.session", "BLE"),
    ("benchtools.instruments.jlink.rtt", "JLINK"),
    ("benchtools.instruments.s2lp.session", "RF"),
    ("benchtools.instruments.tek3014b.scope", "SCOPE"),
    ("benchtools.instruments.tti1604.dmm", "DMM"),
    ("benchtools.instruments.pico_sht30.thermometer", "TEMP"),
    ("benchtools.runner.runner", "TEST"),
    ("benchtools.core.transport.base", "BENCH"),
    ("benchtools.instruments.s2lpx", "BENCH"),     # a prefix, not a package
])
def test_the_logger_name_decides_the_default_source(name, source):
    assert source_of(name) == source


class TestTheLog:
    def test_a_record_is_one_json_line(self, event_log):
        logging.getLogger("benchtools.instruments.gpd3303d.psu").debug(">> %s", "VSET1:3.3")
        (record,) = records(event_log)
        assert record["source"] == "PSU" and record["text"] == ">> VSET1:3.3"
        assert record["level"] == "DEBUG" and isinstance(record["t"], float)

    def test_records_outside_benchtools_are_not_written(self, event_log):
        logging.getLogger("somewhere.else").warning("not ours")
        assert event_log.read_text() == ""

    def test_the_console_keeps_its_level(self, tmp_path):
        """Lowering the package's level for the event log must not flood the
        console with DEBUG records."""
        root = logging.getLogger()
        console = logging.StreamHandler()
        root.addHandler(console)
        previous = root.level
        root.setLevel(logging.WARNING)
        handler = start_event_log(str(tmp_path / "e.jsonl"))
        try:
            assert console.level == logging.WARNING
        finally:
            logging.getLogger("benchtools").removeHandler(handler)
            handler.close()
            root.removeHandler(console)
            root.setLevel(previous)


class TestTail:
    def test_it_returns_only_what_is_new(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text(json.dumps({"source": "psu", "text": "a"}) + "\n")
        tail = EventTail(str(path))
        assert [r["text"] for r in tail.read()] == ["a"]
        assert tail.read() == []
        with path.open("a") as handle:
            handle.write(json.dumps({"source": "ble", "text": "b"}) + "\n")
        assert [r["text"] for r in tail.read()] == ["b"]

    def test_a_partial_line_waits_for_the_rest(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text('{"source": "psu", "te')
        tail = EventTail(str(path))
        assert tail.read() == []
        with path.open("a") as handle:
            handle.write('xt": "whole"}\n')
        assert [r["text"] for r in tail.read()] == ["whole"]

    def test_a_line_that_is_not_json_is_kept_as_text(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text("plain text\n")
        (record,) = EventTail(str(path)).read()
        assert record["source"] == "BENCH" and record["text"] == "plain text"

    def test_a_missing_file_is_no_records_yet(self, tmp_path):
        assert EventTail(str(tmp_path / "later.jsonl")).read() == []

    def test_rewind_reads_it_all_again(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text(json.dumps({"text": "a"}) + "\n")
        tail = EventTail(str(path))
        tail.read()
        tail.rewind()
        assert [r["text"] for r in tail.read()] == ["a"]

    def test_it_can_start_at_the_end(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text(json.dumps({"text": "old"}) + "\n")
        assert EventTail(str(path), from_start=False).read() == []


class TestWhatFeedsIt:
    def test_the_supply_s_lines_are_the_supply_s(self, event_log):
        """SCPI I/O is logged under the instrument's own module (#82)."""
        from benchtools.instruments.gpd3303d import Gpd3303D

        with Gpd3303D.connect("sim://") as supply:
            supply.set_voltage(1, 3.3)
        texts = [(r["source"], r["text"]) for r in records(event_log)]
        assert ("PSU", ">> VSET1:3.300") in texts or any(
            source == "PSU" and text.startswith(">> VSET1") for source, text in texts)

    def test_the_runner_reports_each_test_s_result(self, tmp_path):
        from benchtools.runner.cli import main

        path = tmp_path / "events.jsonl"
        status = main(["specs/radio_link.yaml", "--simulate", "--event-log", str(path)])
        assert status == 0
        texts = [r["text"] for r in records(path) if r["source"] == "TEST"]
        assert any(text.startswith("running test ") for text in texts)
        assert any(text.endswith(": PASS") for text in texts)
        assert any(r["source"] == "RF" for r in records(path))


class TestSourceNames:
    @pytest.mark.parametrize("name", ["TEMP", "PSU", "PSU2", "A", "RF_2", "ABCDEFGH"])
    def test_a_valid_name(self, name):
        assert validate_source_name(name) == name

    @pytest.mark.parametrize("name", ["", "temp", "Temp", "2PSU", "_PSU", "ABCDEFGHI",
                                      "PS U", "PSU-2", None, 7])
    def test_an_invalid_name_is_refused_with_the_rule(self, name):
        with pytest.raises(ConfigurationError, match="1 to 8 characters"):
            validate_source_name(name)

    def test_every_default_is_itself_a_valid_name(self):
        for name in SOURCES:
            validate_source_name(name)

    def test_the_thermometer_defaults_to_temp(self):
        assert "TEMP" in SOURCES


class TestPerInstrumentNames:
    def test_a_bound_logger_writes_its_name(self, event_log):
        source = EventSource("RTT")
        SourceLogger(logging.getLogger("benchtools.instruments.jlink.rtt"), source).info("x")
        (record,) = records(event_log)
        assert record["source"] == "RTT"
        assert record["logger"] == "benchtools.instruments.jlink.rtt"

    def test_an_unbound_logger_falls_back_to_the_logger_name(self, event_log):
        SourceLogger(logging.getLogger("benchtools.instruments.jlink.rtt")).info("x")
        assert records(event_log)[0]["source"] == "JLINK"

    def test_renaming_reaches_a_logger_already_bound(self, event_log):
        source = EventSource("JLINK")
        logger = SourceLogger(logging.getLogger("benchtools.instruments.jlink.rtt"), source)
        source.name = "RTT"
        logger.info("x")
        assert records(event_log)[0]["source"] == "RTT"

    def test_a_bad_rename_is_refused(self):
        with pytest.raises(ConfigurationError):
            EventSource("TEMP").name = "temp"

    def test_two_instruments_of_one_driver_are_told_apart(self, event_log):
        from benchtools.instruments.gpd3303d import Gpd3303D
        first = Gpd3303D.connect("sim://")
        second = Gpd3303D.connect("sim://")
        first.event_source = "PSU"
        second.event_source = "PSU2"
        try:
            first.set_voltage(1, 3.3)
            second.set_voltage(1, 5.0)
        finally:
            first.close()
            second.close()
        lines = [(r["source"], r["text"]) for r in records(event_log)]
        assert any(src == "PSU" and "3.300" in text for src, text in lines)
        assert any(src == "PSU2" and "5.000" in text for src, text in lines)

    def test_the_transport_s_lines_carry_the_instrument_s_name(self, event_log):
        from benchtools.instruments.gpd3303d import Gpd3303D
        with connecting_as("BENCHPSU"):
            psu = Gpd3303D.connect("sim://")
        psu.close()
        transport = [r for r in records(event_log)
                     if r["logger"].startswith("benchtools.core.transport")]
        assert transport and {r["source"] for r in transport} == {"BENCHPSU"}

    def test_an_instrument_is_named_from_construction(self, event_log):
        from benchtools.instruments.pico_sht30 import PicoSht30
        with connecting_as("BENCHT"):
            thermometer = PicoSht30.connect("sim://")
        assert thermometer.event_source == "BENCHT"
        thermometer.close()
        assert records(event_log) and {r["source"] for r in records(event_log)} == {"BENCHT"}

    @pytest.mark.parametrize("module,cls,name", [
        ("benchtools.instruments.gpd3303d", "Gpd3303D", "PSU"),
        ("benchtools.instruments.nordic_dongle", "NordicDongle", "BLE"),
        ("benchtools.instruments.jlink", "JLinkProbe", "JLINK"),
        ("benchtools.instruments.s2lp", "S2lpDevkit", "RF"),
        ("benchtools.instruments.tek3014b", "Tek3014B", "SCOPE"),
        ("benchtools.instruments.tti1604", "Tti1604", "DMM"),
        ("benchtools.instruments.pico_sht30", "PicoSht30", "TEMP"),
    ])
    def test_each_driver_s_default(self, module, cls, name):
        import importlib
        assert getattr(importlib.import_module(module), cls).EVENT_SOURCE == name

    def test_connecting_as_refuses_a_bad_name(self):
        with pytest.raises(ConfigurationError):
            with connecting_as("bad name"):
                pass
