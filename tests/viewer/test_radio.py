"""Kepler frames and BLE in the viewer, and the driver's packet records (#139).

Traces to: VIEW-FR-013 .. VIEW-FR-015, S2LP-FR-080, SWE4-UT-VIEWRADIO.
"""

from __future__ import annotations

import pytest

from benchtools.core.events import EventTail
from benchtools.viewer.radio import BleAir, RfFrames, parse_fields
from benchtools.viewer.server import Hub

from . import radio_log

DONGLE = "benchtools.instruments.nordic_dongle.session"


@pytest.fixture(scope="module")
def log_path(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("radio") / "events.jsonl")
    radio_log.write(path)
    return path


@pytest.fixture(scope="module")
def hub(log_path):
    hub = Hub()
    hub.follow(log_path)
    hub.poll()
    return hub


class TestDriverRecords:
    def test_every_packet_is_a_structured_record(self, log_path):
        packets = [r for r in EventTail(log_path).read() if r.get("kind") == "rf_packet"]
        assert len(packets) == 4
        assert all(r["source"] == "RF" for r in packets)
        first = packets[0]["data"]
        assert (first["direction"], first["hex"]) == ("rx", radio_log.ALIVE.hex())
        assert first["decoded"]["sensor_id"] == "5C1712"
        assert first["rssi_dbm"] == -80.0

    def test_a_transmitted_packet_is_counted_as_sent(self):
        frames = RfFrames()
        frames.feed({"kind": "rf_packet", "data": {"direction": "tx", "hex": "00"}})
        assert (frames.sent, frames.received) == (1, 0)


class TestFrames:
    def test_frames_are_decoded_and_listed(self, hub):
        view = hub.radio()
        assert [(f["sensor_id"], f["type"]) for f in view["frames"]] == [
            ("5C1712", "ALIVE"), ("5C1712", "VERSION"), ("5C314E", "ALIVE"), ("", "")]
        assert "temperature c" in view["frames"][0]["summary"]
        assert "shorter than the 8-byte header" in view["frames"][3]["problem"]

    def test_each_sensor_s_latest_frame_of_each_type(self, hub):
        sensors = {s["sensor_id"]: s for s in hub.radio()["sensors"]}
        assert set(sensors) == {"5C1712", "5C314E"}
        assert sensors["5C1712"]["frames"] == 2
        assert set(sensors["5C1712"]["latest"]) == {"ALIVE", "VERSION"}
        assert sensors["5C1712"]["latest"]["VERSION"]["version"] == "V11.00.0000"

    def test_one_sensor_only(self, hub):
        frames = hub.radio("5C314E")["frames"]
        assert [f["sensor_id"] for f in frames] == ["5C314E"]

    def test_a_frame_the_driver_did_not_decode_is_decoded_here(self):
        frames = RfFrames()
        frames.feed({"kind": "rf_packet", "t": 1.0, "data": {
            "direction": "rx", "hex": radio_log.VERSION.hex(), "error": 0, "decoded": None}})
        assert frames.view()["frames"][0]["type"] == "VERSION"

    def test_a_radio_error_is_counted_and_said(self):
        frames = RfFrames()
        frames.feed({"kind": "rf_packet", "t": 1.0, "data": {
            "direction": "rx", "hex": "", "error": 2}})
        view = frames.view()
        assert view["failed"] == 1
        assert "0x02" in view["frames"][0]["problem"]

    def test_records_that_are_not_packets_are_ignored(self):
        assert RfFrames().feed({"kind": "step_end", "data": {}}) is False
        assert RfFrames().feed({"source": "RF", "text": "<< {Data: 0xFF}"}) is False


class TestBle:
    def test_fields_of_an_event_line(self):
        assert parse_fields("t=2000 addr=E4:1C:7B:02:9A:11 rssi=-62 name=SENS-0A1B2C") == {
            "t": 2000, "addr": "E4:1C:7B:02:9A:11", "rssi": -62, "name": "SENS-0A1B2C"}

    def test_devices_with_advert_count_interval_and_rssi(self, hub):
        devices = {d["addr"]: d for d in hub.bluetooth()["devices"]}
        profiled = devices["E4:1C:7B:02:9A:11"]
        assert profiled["name"] == "SENS-0A1B2C"
        assert profiled["adverts"] == 20
        assert profiled["interval_ms"] == pytest.approx(105.3, abs=0.1)
        assert profiled["rssi_mean"] == -62
        assert devices["C9:3A:51:0F:22:04"]["adverts"] == 0

    def test_events_other_than_adverts_are_listed(self, hub):
        names = [event["event"] for event in hub.bluetooth()["events"]]
        assert "scan" in names and "sensor" in names
        assert "adv" not in names

    def test_the_dongle_s_commands_and_replies(self, hub):
        exchanges = hub.bluetooth()["exchanges"]["BLE"]["entries"]
        sent = [e["text"] for e in exchanges if e["kind"] == "exchange"]
        assert sent[0] == "ver"
        assert any(text.startswith("adv start") for text in sent)

    def test_only_the_dongle_s_lines_count(self):
        air = BleAir()
        assert air.feed({"source": "BLE", "logger": "benchtools.instruments.jlink.rtt",
                         "text": "< +adv addr=x"}) is False
        assert air.feed({"source": "BLE", "logger": DONGLE, "text": "> scan start"}) is False
        assert air.feed({"source": "BLE", "logger": DONGLE, "text": "< +conn state=ready"})
        assert air.view()["events"][0]["event"] == "conn"

    def test_a_device_heard_once_has_no_interval(self):
        air = BleAir()
        air.feed({"source": "BLE", "logger": DONGLE, "t": 1.0,
                  "text": "< +adv t=100 addr=AA rssi=-50 name=X"})
        device = air.view()["devices"][0]
        assert (device["adverts"], device["interval_ms"]) == (1, None)
