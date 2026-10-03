"""Tags for the Event log page's filters: kind, sensor and test (#148).

Traces to: VIEW-FR-019 .. VIEW-FR-021, SWE4-UT-VIEWTAGS.
"""

from __future__ import annotations

import logging

import pytest

from benchtools.core.events import EventTail, start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.spec import TestSpec
from benchtools.viewer.server import Hub
from benchtools.viewer.tags import Tagger, sensor_of

from . import radio_log

DONGLE = "benchtools.instruments.nordic_dongle.session"


def _packet(hex_text, error=0, decoded=None, direction="rx"):
    return {"kind": "rf_packet", "source": "RF", "text": "packet",
            "data": {"direction": direction, "hex": hex_text, "error": error,
                     "decoded": decoded}}


class TestSensor:
    def test_a_frame_s_decoded_sensor(self):
        assert sensor_of(_packet("", decoded={"sensor_id": "5c1712"})) == "5C1712"

    def test_a_frame_the_driver_did_not_decode(self):
        assert sensor_of(_packet(radio_log.ALIVE.hex())) == "5C1712"

    @pytest.mark.parametrize("record", [_packet("0102"), _packet("", error=2)])
    def test_a_frame_that_names_no_sensor(self, record):
        assert sensor_of(record) is None

    def test_a_ble_name_names_its_sensor(self):
        record = {"source": "BLE", "logger": DONGLE,
                  "text": "< +adv t=1 addr=E4:1C:7B:02:9A:11 rssi=-62 name=SENS-0a1b2c"}
        assert sensor_of(record) == "0A1B2C"

    def test_other_lines_name_none(self):
        assert sensor_of({"source": "PSU", "text": ">> VOUT1?"}) is None


class TestKinds:
    @pytest.mark.parametrize("record, kinds", [
        (_packet("00"), ["rf_rx"]),
        (_packet("00", direction="tx"), ["rf_tx"]),
        ({"kind": "reading", "data": {}}, ["reading"]),
        ({"kind": "step_end", "data": {}}, ["runner"]),
        ({"kind": "run_start", "data": {}}, ["runner"]),
        ({"kind": "control_applied", "data": {}}, ["control"]),
        ({"source": "BLE", "text": "< +adv t=1 addr=AA"}, ["ble_adv"]),
        ({"source": "PSU", "text": ">> *IDN?"}, []),
    ])
    def test_each_kind(self, record, kinds):
        assert Tagger().tag(record)["kinds"] == kinds

    def test_the_tags_are_put_on_the_record(self):
        record = {"source": "PSU", "text": "x"}
        tags = Tagger().tag(record)
        assert record["tags"] is tags


SLEEP = {"do": "sleep", "with": {"seconds": 0}}


def _run_log(path, selection=()):
    handler = start_event_log(path)
    try:
        spec = TestSpec.from_mapping({"name": "Tags", "setup": [SLEEP], "teardown": [SLEEP],
                                      "tests": [{"name": "first", "steps": [SLEEP]},
                                                {"name": "second", "steps": [SLEEP]}]})
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            runner.run(spec, selection)
            runner.run(spec, selection)
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    return EventTail(path).read()


class TestTest:
    def test_each_record_is_tagged_with_the_run_and_test_case(self, tmp_path):
        tagger = Tagger()
        records = _run_log(str(tmp_path / "e.jsonl"))
        tags = [(r.get("kind"), tagger.tag(r)["test"]) for r in records if r.get("kind")]
        assert tags[0] == ("run_start", "1. Tags > setup")
        assert ("step_end", "1. Tags > first") in tags
        assert ("step_end", "1. Tags > second") in tags
        assert ("step_end", "1. Tags > teardown") in tags
        assert ("step_end", "2. Tags > first") in tags
        assert tags[-1] == ("run_end", "2. Tags > teardown")
        assert tagger.tests == ["1. Tags > setup", "1. Tags > first", "1. Tags > second",
                                "1. Tags > teardown", "2. Tags > setup", "2. Tags > first",
                                "2. Tags > second", "2. Tags > teardown"]

    def test_a_test_case_not_selected_tags_its_own_end(self, tmp_path):
        tagger = Tagger()
        records = _run_log(str(tmp_path / "e.jsonl"), selection=["second"])
        for record in records:
            tagger.tag(record)
        ends = [(r["data"]["name"], r["tags"]["test"]) for r in records
                if r.get("kind") == "case_end"]
        assert ends[:2] == [("first", "1. Tags > first"), ("second", "1. Tags > second")]

    def test_nothing_before_a_run(self):
        assert Tagger().tag({"source": "PSU", "text": "x"})["test"] is None


def test_the_hub_tags_records_and_lists_the_tests(tmp_path):
    path = tmp_path / "e.jsonl"
    _run_log(str(path))
    radio_log.write(str(path))           # appended: two sensors' frames and BLE
    hub = Hub()
    hub.follow(str(path))
    hub.poll()
    records = [record for _n, record in hub.records]
    assert all("tags" in record for record in records)
    sensors = {record["tags"]["sensor"] for record in records} - {None}
    assert {"5C1712", "5C314E", "0A1B2C"} <= sensors
    received = [r for r in records if "rf_rx" in r["tags"]["kinds"]]
    assert len(received) == 4
    assert hub.since(0, -1)["state"]["tests"][0] == "1. Tags > setup"
