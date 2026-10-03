"""rf_monitor's Latest Data, Config and Identification screens in the viewer (#152).

Traces to: VIEW-FR-028 .. VIEW-FR-030, SWE4-UT-VIEWKEPLER.
"""

from __future__ import annotations

import struct

from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.viewer.kepler_view import (
    CONFIG_GROUPS, KeplerView, byte_roles, header_rows, payload_rows,
)
from benchtools.viewer.radio import RfFrames

from . import radio_log


def _config(mux, values, method_byte=0x08, counter=0x13):
    frame = bytearray(21)
    frame[0:8] = bytes.fromhex("5c171203060c0405")
    frame[8] = method_byte
    frame[9] = counter
    frame[10] = mux
    frame[11:21] = struct.pack(">5H", *values)
    return bytes(frame)


def _packet(payload, t=1.0):
    return {"kind": "rf_packet", "t": t, "source": "RF", "text": "packet",
            "data": {"direction": "rx", "hex": payload.hex(), "error": 0, "rssi_dbm": -70.0,
                     "length": len(payload)}}


def _view(*payloads):
    frames, view = RfFrames(), KeplerView()
    for index, payload in enumerate(payloads):
        frames.feed(_packet(payload, float(index)))
        view.feed(frames.last_frame)
    return view


class TestLatestData:
    def test_byte_roles(self):
        alive = decode_kepler_frame(radio_log.ALIVE)
        roles = byte_roles(alive, len(radio_log.ALIVE))
        assert roles[:9] == ["header"] * 7 + ["type", "counter"]
        config = decode_kepler_frame(_config(0, [0] * 5))
        assert byte_roles(config, 21)[7:11] == ["type", "permute", "counter", "payload"]
        assert byte_roles(None, 4) == ["header"] * 4

    def test_header_rows(self):
        rows = dict(header_rows(decode_kepler_frame(_config(0, [0] * 5))))
        assert rows["Sensor ID"] == "0x5C1712"
        assert rows["Product"] == "Kappa GEN2 (3)"
        assert rows["Permute control"] == "None"
        assert rows["Frame counter"] == "1 of 3"

    def test_payload_rows_name_config_parameters_and_ticks(self):
        rows = dict(payload_rows(decode_kepler_frame(_config(8, [600, 1, 0, 2, 40]))))
        assert rows["Alive Period"] == "600 s"
        assert rows["FFT Enable"] == "Enabled"
        alive = dict(payload_rows(decode_kepler_frame(radio_log.ALIVE)))
        assert alive["Ticks"] == "388 (00:06:28:00)"
        assert alive["Temperature c"] == "24.4 °C"

    def test_latest_frames_of_one_sensor(self):
        view = _view(radio_log.ALIVE, radio_log.OTHER_SENSOR, radio_log.VERSION)
        latest = view.view("5C1712")["latest"]
        assert [frame["type"] for frame in latest] == ["ALIVE", "VERSION"]
        assert latest[0]["header"] and latest[0]["payload"]

    def test_an_undecodable_frame_is_still_listed(self):
        latest = _view(b"\x01\x02").view()["latest"]
        assert latest[0]["problem"] and latest[0]["header"] == []


class TestConfig:
    def test_every_parameter_with_its_latest_value(self):
        view = _view(*[_config(mux, [mux * 5 + slot for slot in range(5)]) for mux in range(12)])
        table = view.view("5C1712")["config"]
        assert len(table) == 60
        assert all(row["value"] == row["parameter"] for row in table)
        assert table[5]["name"] == "Transit Max Time" and table[5]["block"] == 1

    def test_a_later_frame_replaces_a_value_and_unseen_ones_are_unknown(self):
        view = _view(_config(8, [600, 1, 0, 2, 40]), _config(8, [300, 0, 0, 2, 40]))
        table = view.view()["config"]
        assert table[40]["shown"] == 300
        assert table[41]["shown"] == "Disabled" and table[41]["disabled"]
        assert table[0]["shown"] is None

    def test_a_polynomial_frame_is_placed_by_its_repeat(self):
        # Under the polynomial a slot's parameter depends on the repeat; the
        # value lands where the firmware's mapping says, not at mux*5 + slot.
        from benchtools.instruments.s2lp.kepler_tables import config_parameter
        view = _view(_config(0, [11, 22, 33, 44, 55], method_byte=0x10, counter=0x23))
        table = view.view()["config"]
        for slot, value in enumerate([11, 22, 33, 44, 55]):
            assert table[config_parameter(0, slot, "polynomial", 1)]["value"] == value

    def test_summary_groups(self):
        groups = _view(_config(8, [600, 1, 0, 2, 40])).view()["groups"]
        assert [group["title"] for group in groups] == [title for title, _ in CONFIG_GROUPS]
        other = next(group for group in groups if group["title"] == "Other")
        assert other["rows"][0]["name"] == "Alive Period" and other["rows"][0]["shown"] == 600


class TestIdentification:
    def test_from_the_last_version_frame(self):
        identification = _view(radio_log.ALIVE, radio_log.VERSION).view()["identification"]
        assert identification["version"] == "V11.00.0000"
        assert identification["reset_reasons"] == ["Soft reset"]
        assert identification["pcb"] == "V4X"
        assert identification["rssi_dbm"] == -70.0

    def test_none_before_a_version_frame(self):
        assert _view(radio_log.ALIVE).view()["identification"] is None


def test_the_frames_list_names_config_parameters():
    frames = RfFrames()
    frames.feed(_packet(_config(8, [600, 1, 0, 2, 40])))
    summary = frames.view()["frames"][0]["summary"]
    assert summary.startswith("Alive Period 600 s, FFT Enable Enabled")
    assert "product" not in summary
