"""The Test Bench monitor's data sources (tools/test_bench, #82).

The GUI itself is rf_monitor's, and is checked by running it; these check what
feeds it: a live packet must reach rf_monitor's own parser as the same frame a
logged one would, and each event must keep its source.

Traces to: SWE4-UT-TESTBENCH.
"""

from __future__ import annotations

import pathlib
import sys
import time

import pytest

from benchtools.instruments.s2lp.packets import Packet

TOOL = pathlib.Path(__file__).resolve().parents[2] / "tools" / "test_bench"
sys.path.insert(0, str(TOOL))

import sources  # noqa: E402  pylint: disable=wrong-import-position,wrong-import-order,import-error

ALIVE = bytes.fromhex(
    "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005")


def packet(**changes):
    values = {"direction": "rx", "data": ALIVE, "rssi_dbm": -94.5,
              "host_time": "2026-09-28T10:02:08.123456+00:00"}
    values.update(changes)
    return Packet(**values)


class TestSpiritLine:
    def test_it_is_the_line_st_s_gui_writes(self):
        line = sources.spirit_line(packet())
        clock, received, rssi, data = line.split("\t")
        assert len(clock) == 11 and clock.endswith(".12")
        assert received == "Packet received (35 bytes)"
        assert rssi in ("-94", "-95")
        assert data.split()[:3] == ["5C", "17", "12"]

    def test_rf_monitor_s_parser_reads_it_as_the_same_frame(self):
        pytest.importorskip("tkinter")
        pytest.importorskip("matplotlib")
        import test_bench  # pylint: disable=import-error

        frame = test_bench.parse_packet_line(sources.spirit_line(packet()))
        assert frame is not None
        assert frame.sensor_id == "5C1712" and frame.frame_name == "ALIVE"
        assert frame.raw_bytes == list(ALIVE)


class TestStGuiRow:
    def test_time_bytes_rssi_hex(self):
        _when, length, rssi, data = sources.st_gui_row(packet())
        assert (length, rssi) == ("35", "-94.5")
        assert data.startswith("5C 17 12 03")

    def test_a_crc_failure_shows_as_st_s_gui_shows_it(self):
        row = sources.st_gui_row(packet(data=b"", error=2))
        assert row[3] == "Packet lost. CRC error" and row[1] == ""


class TestEvents:
    def test_an_rf_frame(self):
        record = sources.rf_event(packet(), {"sensor_id": "5C1712", "type": "ALIVE",
                                             "frame_of": (1, 3)})
        assert record["source"] == "RF"
        assert record["text"] == "5C1712 ALIVE frame 1 of 3, 35 bytes, -94.5 dBm"

    def test_a_decoder_frame_counts_from_one(self):
        record = sources.rf_event(packet(), {"sensor_id": "5C1712", "type": "ALIVE",
                                             "frame": {"repeat": 0, "frames_per_packet": 3}})
        assert "frame 1 of 3" in record["text"]

    def test_a_rejected_reception(self):
        assert "rejected (error 2)" in sources.rf_event(packet(data=b"", error=2))["text"]

    def test_each_source_has_a_label_and_a_colour(self):
        for source in sources.SOURCE_ORDER:
            label, colour = sources.SOURCE_STYLES[source]
            assert label and colour.startswith("#")

    def test_an_event_row(self):
        when, source, label, text = sources.event_row(
            {"t": 1790600000.5, "source": "PSU", "text": ">> VSET1:3.300"})
        assert (source, label, text) == ("PSU", "PSU", ">> VSET1:3.300")
        assert len(when) == 11

    def test_a_log_from_before_126_reads_the_same(self):
        # Lower-case names were written before #126.
        assert sources.event_row({"source": "psu", "text": "x"})[1:3] == ("PSU", "PSU")
        assert sources.event_row({"source": "rf", "text": "x"})[1:3] == ("RF", "ST RF")

    def test_a_declared_name_is_shown_as_itself(self):
        _, source, label, _ = sources.event_row({"source": "RTT", "text": "x"})
        assert (source, label) == ("RTT", "RTT")

    def test_a_declared_name_keeps_its_colour(self):
        assert sources.style_of("PSU2") == sources.style_of("PSU2")
        assert sources.style_of("PSU2")[1].startswith("#")

    def test_a_record_with_no_source_is_bench(self):
        assert sources.event_row({"text": "x"})[1] == "BENCH"

    def test_the_thermometer_has_a_style_of_its_own(self):
        assert sources.style_of("TEMP") == sources.SOURCE_STYLES["TEMP"]


def test_a_live_radio_receives_from_a_simulated_kit_and_stops_the_board():
    radio = sources.LiveRadio("sim://")
    air = sources.SimulatedAir(radio.radio, interval=0.1)
    air.start()
    radio.start()
    received = []
    deadline = time.monotonic() + 10.0
    while len(received) < 3 and time.monotonic() < deadline:
        received += radio.drain()
        time.sleep(0.05)
    air.stop()
    kit = radio.radio.transport.responder
    radio.close()
    assert len(received) >= 3
    assert received[0].data[:3] == ALIVE[:3]
    assert kit.stopped
    assert radio.error is None


@pytest.fixture(scope="module")
def kepler_snapshot():
    """A snapshot of a simulated kit set up to receive Kepler frames, as the
    ST GUI page reads one: reception is running, so it must pause and resume."""
    setup = pathlib.Path(__file__).resolve().parents[2] / "configs" / "s2lp_kepler_433_rx.regs"
    radio = sources.LiveRadio("sim://", setup=str(setup))
    radio.start()
    try:
        snapshot = radio.snapshot()
        resumed = radio._thread.is_alive()  # pylint: disable=protected-access
    finally:
        radio.close()
    assert radio.error is None
    return snapshot, resumed


class TestStGuiSetup:
    def test_reading_the_setup_resumes_reception(self, kepler_snapshot):
        snapshot, resumed = kepler_snapshot
        assert resumed
        assert snapshot["paused_s"] >= 0.0
        assert set(snapshot) >= {"radio", "registers", "power_dbm", "eeprom"}

    def test_the_rf_setup_shows_the_kepler_link(self, kepler_snapshot):
        rows = {(section, label): value
                for section, label, value in sources.rf_setup_rows(kepler_snapshot[0])}
        assert {section for section, _label in rows} >= {"Radio", "Packet"}
        radio = kepler_snapshot[0]["radio"]
        assert rows[("Radio", "Frequency base")] == "%.6f MHz" % (radio["frequency_hz"] / 1e6)
        assert rows[("Packet", "Sync word")] == "0x4E63F358"
        assert rows[("Packet", "Second sync word")] == "0xB19C0CA7 (on)"
        assert rows[("Packet", "CRC")] == "16 bit (0x8005)"
        assert rows[("Packet", "Length")] == "variable"

    def test_a_register_row_is_st_s_address_register_value_default(self, kepler_snapshot):
        rows = {row[1]: row for row in sources.register_rows(kepler_snapshot[0]["registers"])}
        addr, _name, value, default, fields, changed = rows["PCKTCTRL1"]
        assert (addr, value, default) == ("0x30", "0x42", "0x2C") and changed
        assert dict(fields)["CRC_MODE"] == 2 and dict(fields)["SECOND_SYNC_SEL"] == 1

    def test_a_read_only_register_is_never_marked_changed(self, kepler_snapshot):
        from benchtools.instruments.s2lp import registers as reg

        read_only = {r.name for r in reg.REGISTERS if not r.writable}
        for _addr, name, _value, _default, _fields, changed in sources.register_rows(
                kepler_snapshot[0]["registers"]):
            if name in read_only:
                assert not changed

    def test_the_export_is_a_register_file_the_driver_reads_back(self, kepler_snapshot):
        from benchtools.instruments.s2lp.configuration import parse_register_file

        values = kepler_snapshot[0]["registers"]
        config = parse_register_file(sources.regs_text(values), source="export")
        assert config.settings
        for setting in config.settings:
            assert values[setting.register.address] == setting.value


def psu(text, level="DEBUG", t=1790600000.0):
    return {"t": t, "source": "psu", "level": level, "text": text}


def jlink(text, logger="benchtools.instruments.jlink.session", level="DEBUG"):
    return {"t": 1790600000.0, "source": "jlink", "logger": logger, "level": level,
            "text": text}


class TestPsuPanel:
    def feed(self, *texts):
        panel = sources.PsuPanel()
        for text in texts:
            panel.feed(psu(text))
        return panel

    def test_settings_come_from_the_commands(self):
        panel = self.feed(">> VSET1:3.300", ">> ISET1:0.500", ">> VSET2:5.000", ">> OUT1")
        assert panel.channels[1]["vset"] == 3.3 and panel.channels[1]["iset"] == 0.5
        assert panel.channels[2]["vset"] == 5.0
        assert panel.output is True

    def test_readings_come_from_the_replies_to_queries(self):
        panel = self.feed(">> VOUT1?", "<< 3.29V", ">> IOUT1?", "<< 0.012A",
                          ">> *IDN?", "<< GW INSTEK,GPD-3303D,SN:X,V1.09")
        assert panel.channels[1]["vout"] == 3.29 and panel.channels[1]["iout"] == 0.012
        assert panel.identity.startswith("GW INSTEK")

    def test_status_gives_modes_output_tracking_and_beep(self):
        panel = self.feed(">> STATUS?", "<< 0 1 0 1 1 X 1 X")
        assert panel.channels[1]["mode"] == "CC" and panel.channels[2]["mode"] == "CV"
        assert panel.output is True and panel.beep is True
        assert panel.tracking == "independent"

    def test_a_reply_without_a_query_changes_no_value(self):
        panel = self.feed(">> VSET1:3.300", "<< 9.9V")
        assert panel.channels[1]["vout"] is None and panel.channels[1]["vset"] == 3.3

    def test_only_the_last_ten_commands_are_kept_each_with_its_reply(self):
        panel = self.feed(*[">> VSET1:%d.000" % n for n in range(12)] + [">> VOUT1?", "<< 3.3V"])
        assert len(panel.recent) == 10
        assert panel.recent[-1][1:] == ["VOUT1?", "3.3V"]
        assert panel.recent[0][1] == "VSET1:3.000"

    def test_other_sources_are_not_taken(self):
        assert not sources.PsuPanel().feed({"source": "ble", "text": ">> OUT1"})


class TestJlinkPanel:
    def rows(self, *records):
        panel = sources.JlinkPanel()
        for record in records:
            panel.feed(record)
        return panel, dict(panel.rows())

    def test_a_flash_and_verify(self):
        _panel, rows = self.rows(
            jlink('>> 6-file-exec-and-symbols "firmware.elf"'),
            jlink(">> 7-target-select extended-remote localhost:2331"),
            jlink('>> 10-interpreter-exec console "load"'),
            jlink("flashed 17280 bytes in 3 section(s) in 0.40 s",
                  logger="benchtools.instruments.jlink.probe", level="INFO"),
            jlink('>> 11-interpreter-exec console "compare-sections"'),
            jlink("console Section .text, range 0x0 -- 0x4000: matched."))
        assert rows["Firmware (ELF)"] == "firmware.elf"
        assert rows["Target"] == "extended-remote localhost:2331"
        assert rows["Last flash"].startswith("17280 bytes")
        assert rows["Verify"] == "match"

    def test_a_mismatch_is_reported(self):
        _panel, rows = self.rows(
            jlink('>> 11-interpreter-exec console "compare-sections"'),
            jlink("console Section .text, range 0x0 -- 0x4000: MIS-MATCHED!"))
        assert rows["Verify"].startswith("MISMATCH")

    def test_the_core_follows_halt_continue_and_a_breakpoint(self):
        panel, rows = self.rows(jlink('>> 9-interpreter-exec console "monitor halt"'))
        assert rows["Core"] == "halted"
        panel.feed(jlink(">> 12-break-insert sensor.c:40"))
        panel.feed(jlink(">> 13-exec-continue"))
        assert dict(panel.rows())["Core"] == "running"
        panel.feed(jlink("async stopped{'reason': 'breakpoint-hit', 'disp': 'keep', "
                         "'bkptno': '1', 'frame': {'func': 'sensor_start', "
                         "'file': 'sensor.c', 'line': '40'}}"))
        rows = dict(panel.rows())
        assert rows["Core"] == "halted: breakpoint-hit 1, sensor_start (sensor.c:40)"
        assert rows["Breakpoints"] == "1"

    def test_rtt_lines_are_counted(self):
        _panel, rows = self.rows(jlink('>> 17-interpreter-exec console "monitor rtt start"'),
                                 jlink("console RTT started"),
                                 jlink("rtt: 1.4.2", logger="benchtools.instruments.jlink.rtt"),
                                 jlink("rtt: main: loop",
                                       logger="benchtools.instruments.jlink.rtt"))
        assert rows["RTT"] == "started, 2 line(s)" and rows["Last RTT line"] == "main: loop"

    def test_the_probe_and_a_problem(self):
        panel, rows = self.rows(jlink("console SEGGER,J-Link V11,801012345,V7.94e"),
                                jlink("console S/N: 801012345"),
                                jlink("RTT reader failed", level="WARNING",
                                      logger="benchtools.instruments.jlink.rtt"))
        assert rows["Probe"] == "SEGGER,J-Link V11,801012345,V7.94e, S/N 801012345"
        assert rows["Last problem"] == "RTT reader failed"
        assert [kind for _t, kind, _text in panel.recent] == ["console", "console", "problem"]

    def test_detaching_after_resuming_leaves_the_core_running(self):
        _panel, rows = self.rows(jlink('>> 17-interpreter-exec console "monitor go"'),
                                 jlink(">> 18-target-detach"))
        assert rows["Core"] == "detached, core running"
