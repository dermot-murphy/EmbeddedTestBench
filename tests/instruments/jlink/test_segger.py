"""The ``segger`` J-Link backend: J-Link Commander and RTT Logger, no GDB (#71).

Nothing here touches a probe. The real runner is tested with ``subprocess``
replaced; the probe is tested against the simulator, which runs the same
command files the real runner would hand to ``JLink.exe``.

Traces to: JLINK-FR-006, JLINK-FR-007, JLINK-FR-008, JLINK-FR-009,
JLINK-FR-091, SWE4-UT-JLINKSEGGER.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from benchtools.core.errors import (
    BenchToolsError,
    ConfigurationError,
    ConnectionFailedError,
    TransportTimeoutError,
)
from benchtools.instruments.jlink import JLinkProbe, JLinkRttReader
from benchtools.instruments.jlink import commander as commander_module
from benchtools.instruments.jlink import server as server_module
from benchtools.instruments.jlink.cli import main as cli_main
from benchtools.instruments.jlink.commander import (
    CommanderError,
    JLinkCommander,
    RttLoggerBackend,
    check_output,
    parse_banner,
)
from benchtools.instruments.jlink.segger import (
    GDB_ONLY_OPERATIONS,
    SeggerJLinkProbe,
    UnsupportedOperationError,
)
from benchtools.runner.bench import Bench, BenchConfig

UICR_ID = 0x10001080


@pytest.fixture
def probe():
    """A segger-backend probe over the simulator."""
    instance = JLinkProbe.connect("sim://", backend="segger")
    yield instance
    instance.close()


def simulator_of(probe):
    return probe.commander.simulator


def commands_run(probe):
    """Every command file the simulated Commander ran, as lists of lines."""
    return probe.commander.log


class TestSelection:
    def test_gdb_is_the_default(self):
        with JLinkProbe.connect("sim://") as probe:
            assert not isinstance(probe, SeggerJLinkProbe) and probe.backend == "gdb"

    @pytest.mark.parametrize("name", ["segger", "SEGGER", " Segger "])
    def test_segger_is_selected_by_name_in_any_case(self, name):
        with JLinkProbe.connect("sim://", backend=name) as probe:
            assert isinstance(probe, SeggerJLinkProbe) and probe.backend == "segger"

    def test_it_is_still_a_jlink_probe(self, probe):
        """The bench compares driver classes; a segger probe is a JLinkProbe."""
        assert isinstance(probe, JLinkProbe)

    def test_an_unknown_backend_is_refused(self):
        with pytest.raises(ConfigurationError, match="unknown J-Link backend 'openocd'"):
            JLinkProbe.connect("sim://", backend="openocd")

    def test_a_remote_host_is_refused(self):
        with pytest.raises(ConfigurationError, match="this machine's USB"):
            JLinkProbe.connect("jlink://192.168.1.9:2331", backend="segger", device="X")

    def test_the_bench_option_selects_it(self):
        config = BenchConfig.from_mapping({
            "name": "B",
            "instruments": {"probe": {"driver": "jlink", "resource": "sim://",
                                      "options": {"backend": "segger"}}},
        })
        with Bench(config) as bench:
            assert bench.get("probe").backend == "segger"

    def test_a_missing_commander_is_reported_at_connect(self, monkeypatch):
        monkeypatch.setattr(commander_module, "find_jlink_commander", lambda explicit: None)
        with pytest.raises(ConnectionFailedError, match="no J-Link Commander"):
            JLinkProbe.connect("jlink://", backend="segger", device="nRF52840_xxAA")

    def test_the_rtt_only_driver_passes_the_backend_on(self):
        with JLinkRttReader.connect("sim://", backend="segger") as reader:
            assert reader.backend == "segger" and not reader.is_attached


class TestCommandLine:
    def runner(self, **kwargs):
        options = {"device": "nRF52840_xxAA", "executable": "C:/SEGGER/JLink.exe"}
        options.update(kwargs)
        return JLinkCommander(**options)

    def test_options_from_the_v942_binary(self):
        arguments = self.runner(serial_number="682395790").command_line("cmd.jlink")
        assert arguments == [
            "C:/SEGGER/JLink.exe", "-NoGui", "1", "-Device", "nRF52840_xxAA", "-If", "SWD",
            "-Speed", "4000", "-AutoConnect", "1", "-USB", "682395790",
            "-CommandFile", "cmd.jlink"]

    def test_speed_zero_is_adaptive(self):
        assert "adaptive" in self.runner(speed_khz=0).command_line("c")

    def test_a_device_is_required(self):
        with pytest.raises(ConnectionFailedError, match="device name is required"):
            self.runner(device=None).command_line("c")

    def test_a_missing_commander_names_where_it_is_installed(self, monkeypatch):
        monkeypatch.setattr(commander_module, "find_jlink_commander", lambda explicit: None)
        with pytest.raises(ConnectionFailedError, match=r"JLink\.exe.*SEGGER"):
            self.runner(executable=None).command_line("c")


class FakeRun:  # pylint: disable=too-few-public-methods
    """Stands in for ``subprocess.run``, keeping the command file it was given."""

    def __init__(self, output="", returncode=0, raises=None):
        self.output, self.returncode, self.raises = output, returncode, raises
        self.script = None
        self.arguments = None

    def __call__(self, arguments, **_kwargs):
        self.arguments = arguments
        with open(arguments[arguments.index("-CommandFile") + 1], encoding="ascii") as handle:
            self.script = handle.read().splitlines()
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(arguments, self.returncode,
                                           stdout=self.output.encode())


class TestRunning:
    @pytest.fixture
    def runner(self):
        instance = JLinkCommander(device="nRF52840_xxAA", executable="JLink.exe")
        yield instance
        instance.close()

    def test_a_command_file_stops_on_error_and_ends_with_quit(self, monkeypatch, runner):
        fake = FakeRun("O.K.")
        monkeypatch.setattr(commander_module.subprocess, "run", fake)
        runner.run(["r", "h"], "reset")
        assert fake.script == ["exitonerror 1", "r", "h", "q"]

    def test_an_error_line_fails_the_run_whatever_the_status(self, monkeypatch, runner):
        monkeypatch.setattr(commander_module.subprocess, "run",
                            FakeRun("Error occurred: Could not connect to the target device."))
        with pytest.raises(CommanderError, match="Could not connect to the target device"):
            runner.run([], "identify")

    def test_a_non_zero_status_fails_the_run(self, monkeypatch, runner):
        monkeypatch.setattr(commander_module.subprocess, "run", FakeRun("", returncode=1))
        with pytest.raises(CommanderError, match="status 1"):
            runner.run(["h"], "halt")

    def test_a_run_that_does_not_finish_times_out(self, monkeypatch, runner):
        monkeypatch.setattr(commander_module.subprocess, "run",
                            FakeRun(raises=subprocess.TimeoutExpired("JLink.exe", 1)))
        with pytest.raises(TransportTimeoutError, match="did not finish"):
            runner.run(["h"], "halt", timeout=1)

    def test_the_command_files_are_removed_on_close(self, monkeypatch, runner):
        monkeypatch.setattr(commander_module.subprocess, "run", FakeRun("O.K."))
        runner.run(["g"], "run")
        directory = runner.directory
        runner.close()
        assert not os.path.exists(directory)

    @pytest.mark.parametrize("line", [
        "Error while programming flash: Verify failed.",
        "Could not read memory.",
        "Unknown command. '?' for help.",
        "Connecting to J-Link via USB...FAILED",
        "ERROR: Erase returned with error code -1.",
    ])
    def test_each_failure_message_is_recognised(self, line):
        with pytest.raises(CommanderError):
            check_output("SEGGER J-Link Commander V9.42\n" + line, 0, "x")

    def test_a_clean_run_passes(self):
        check_output("Erasing device...\nErasing done.\nScript processing completed.", 0, "x")

    def test_the_banner_is_read(self):
        banner = parse_banner(
            "SEGGER J-Link Commander V9.42 (Compiled May  6 2026 12:31:09)\n"
            "Firmware: J-Link ARM V8 compiled Nov 28 2014 13:44:46\n"
            "Hardware version: V8.00\nS/N: 682395790\n")
        assert banner == {"serial_number": "682395790", "hardware": "V8.00",
                          "firmware": "J-Link ARM V8 compiled Nov 28 2014 13:44:46",
                          "version": "V9.42"}


class TestDiscovery:
    def test_an_explicit_path_wins(self):
        assert server_module.find_jlink_commander("X:/JLink.exe") == "X:/JLink.exe"
        assert server_module.find_rtt_logger("X:/L.exe") == "X:/L.exe"

    def test_path_is_searched_first(self, monkeypatch):
        monkeypatch.setattr(server_module.shutil, "which",
                            lambda name: "/p/" + name if name == "JLink.exe" else None)
        assert server_module.find_jlink_commander() == "/p/JLink.exe"

    def test_the_newest_segger_release_wins(self, monkeypatch, tmp_path):
        """Beside find_gdb_server: the same install directories (#71)."""
        for release in ("JLink_V924a", "JLink_V942"):
            folder = tmp_path / "SEGGER" / release
            folder.mkdir(parents=True)
            (folder / "JLink.exe").write_text("")
            (folder / "JLinkRTTLogger.exe").write_text("")
        monkeypatch.setattr(server_module.shutil, "which", lambda name: None)
        monkeypatch.setattr(server_module, "_SERVER_DIRECTORIES",
                            (str(tmp_path / "SEGGER" / "JLink*"),))
        assert server_module.find_jlink_commander().endswith(("JLink_V942\\JLink.exe",
                                                              "JLink_V942/JLink.exe"))
        assert "JLink_V942" in server_module.find_rtt_logger()


class TestRefusals:
    @pytest.mark.parametrize("operation", sorted(GDB_ONLY_OPERATIONS))
    def test_a_gdb_only_operation_is_refused_by_name_before_the_probe_is_used(
            self, probe, operation):
        before = len(commands_run(probe))
        with pytest.raises(UnsupportedOperationError) as raised:
            getattr(probe, operation)("main")
        message = str(raised.value)
        assert operation in message and "'segger' backend" in message
        assert "backend: gdb" in message
        assert len(commands_run(probe)) == before

    def test_there_is_no_gdb_session(self, probe):
        with pytest.raises(UnsupportedOperationError, match="session"):
            _ = probe.session

    def test_writing_rtt_is_refused(self, probe):
        probe.rtt_start()
        with pytest.raises(ConfigurationError, match="RTT Logger only reads"):
            probe.rtt_write("version")

    def test_an_rtt_only_link_sends_nothing_else(self):
        with JLinkProbe.connect("sim://", backend="segger", attach=False) as probe:
            with pytest.raises(UnsupportedOperationError, match="RTT only"):
                probe.read_memory(UICR_ID, 4)
            assert commands_run(probe) == []


class TestFlashAndVerify:
    def test_flash_resets_halts_loads_and_reads_every_range_back(self, probe):
        result = probe.flash()
        load, readback = commands_run(probe)[-2:]
        assert load[1:4] == ["r", "h", "loadfile firmware.elf"]
        assert all(line.startswith("savebin ") for line in readback[1:-1])
        assert result.verified is True and result.bytes_written > 0
        assert set(result.sections) == {".text", ".rodata"}

    def test_a_range_that_does_not_read_back_fails_naming_it(self, probe):
        simulator_of(probe).flash_matches = False
        with pytest.raises(BenchToolsError, match=r"\.text"):
            probe.flash()

    def test_verify_compares_by_reading_back(self, probe):
        assert probe.verify().matched is False           # nothing programmed yet
        probe.flash()
        assert probe.verify().matched is True

    def test_a_real_hex_file_is_parsed_and_compared(self, probe, tmp_path):
        image = tmp_path / "app.hex"
        body = bytes([4, 0x00, 0x00, 0x00]) + bytes(range(4))
        image.write_text(":" + (body + bytes([(-sum(body)) & 0xFF])).hex() + "\n:00000001FF\n")
        result = probe.flash(str(image))
        assert result.sections == {"0x00000000": (0, 4)} and result.verified is True
        assert probe.read_memory(0, 4) == bytes(range(4))

    def test_without_reset_only_the_explicit_reset_is_left_out(self, probe):
        probe.flash(reset=False, verify=False)
        assert commands_run(probe)[-1][1:-1] == ["loadfile firmware.elf"]

    def test_a_file_name_with_a_space_is_quoted(self, probe, tmp_path):
        image = tmp_path / "my image.hex"
        image.write_text(":0100000001FE\n:00000001FF\n")
        probe.flash(str(image), verify=False)
        assert commands_run(probe)[-1][-2] == 'loadfile "%s"' % image

    def test_preserve_keeps_the_sensor_id(self, probe):
        probe.write_memory(UICR_ID, bytes.fromhex("005c1712"))
        result = probe.flash(preserve=[(UICR_ID, 4)])
        assert result.preserved == {UICR_ID: "005c1712"}

    def test_restore_records_the_backend(self, probe):
        result = probe.restore(["firmware.elf"])
        assert result.as_dict()["backend"] == "segger" and result.unchanged


class TestErase:
    def test_erase_resets_halts_and_is_blank_checked(self, probe):
        probe.flash(verify=False)
        probe.erase()
        erase, check = commands_run(probe)[-2:]
        assert erase[1:4] == ["r", "h", "erase"]
        assert check[1].startswith("savebin ") and check[1].endswith(", 0, 4")

    def test_an_erase_that_erased_nothing_is_caught(self, probe):
        """As 'monitor flash erase' said O.K. and erased nothing (#69)."""
        probe.flash(verify=False)
        probe.commander.erase_works = False
        with pytest.raises(BenchToolsError, match="still reads"):
            probe.erase()


class TestMemory:
    def test_read_uses_savebin_with_hex_numbers(self, probe):
        assert probe.read_memory(UICR_ID, 4) == bytes.fromhex("000a1b2c")
        assert commands_run(probe)[-1][1].endswith(", 10001080, 4")

    def test_words_where_aligned_bytes_elsewhere(self, probe):
        probe.write_memory(0x20000001, bytes(range(1, 8)), verify=False)
        assert commands_run(probe)[-1][1:-1] == [
            "w1 20000001, 1", "w1 20000002, 2", "w1 20000003, 3", "w4 20000004, 7060504"]
        assert probe.read_memory(0x20000001, 7) == bytes(range(1, 8))

    def test_a_write_is_read_back_in_a_run_of_its_own(self, probe):
        probe.write_memory(UICR_ID, bytes.fromhex("005c1712"))
        write, readback = commands_run(probe)[-2:]
        assert write[1].startswith("w4 ") and readback[1].startswith("savebin ")

    def test_a_write_that_did_not_stick_raises(self, probe, monkeypatch):
        for name in ("w1", "w4"):
            monkeypatch.setitem(probe.commander.handlers, name, lambda *args: True)
        with pytest.raises(BenchToolsError, match="read back"):
            probe.write_word(UICR_ID, 0x12175C00)

    def test_the_integer_readers_work_over_it(self, probe):
        assert probe.read_integer(UICR_ID + 1, 3, byteorder="big") == 0x0A1B2C


class TestRunControlAndClose:
    def test_reset_and_run(self, probe):
        probe.reset(halt=False)
        assert commands_run(probe)[-1][1:3] == ["r", "g"] and not probe.is_halted
        probe.reset()
        assert commands_run(probe)[-1][1:3] == ["r", "h"] and probe.is_halted

    def test_closing_lets_the_core_run(self):
        probe = JLinkProbe.connect("sim://", backend="segger")
        probe.reset()
        log = commands_run(probe)
        probe.close()
        assert log[-1][1:-1] == ["g"]

    def test_closing_can_leave_it_halted(self):
        probe = JLinkProbe.connect("sim://", backend="segger")
        probe.halt()
        probe.leave_halted = True
        log = commands_run(probe)
        count = len(log)
        probe.close()
        assert len(log) == count

    def test_a_probe_never_used_sends_nothing_on_close(self):
        probe = JLinkProbe.connect("sim://", backend="segger")
        log = commands_run(probe)
        probe.close()
        assert log == []

    def test_exit_resumes_the_core_in_the_model(self, probe):
        """What was seen once on the bench (notes §4.3); unverified for a halt
        Commander itself made, so the model is what a test can rely on."""
        probe.halt()
        assert probe.is_halted and not simulator_of(probe).halted


class TestIdentityAndResults:
    def test_identity_comes_from_the_banner(self, probe):
        identity = probe.identify()
        assert identity.serial_number == "801012345" and identity.manufacturer == "SEGGER"
        assert "J-Link Commander: V9.42" in identity.raw

    def test_gdb_results_say_gdb(self):
        with JLinkProbe.connect("sim://") as probe:
            result = probe.flash()
            assert result.as_dict()["backend"] == "gdb"
            assert result.as_dict()["verify"]["backend"] == "gdb"

    def test_segger_results_say_segger(self, probe):
        assert probe.flash().as_dict()["backend"] == "segger"
        assert probe.verify().as_dict()["backend"] == "segger"


class TestRtt:
    def test_lines_are_read_from_the_logger(self, probe):
        probe.rtt_start()
        simulator_of(probe).rtt_out.append("Sensor ID is: 0x0A1B2C")
        assert probe.rtt_expect("Sensor ID is: (0x[0-9A-F]+)").group(1) == "0x0A1B2C"

    def test_a_halted_core_is_let_go_before_reading(self, probe):
        probe.reset()
        probe.rtt_start()
        assert commands_run(probe)[-1][1:-1] == ["g"]

    def test_the_logger_command_line_always_names_channel_0(self):
        backend = RttLoggerBackend(device="nRF52840_xxAA", executable="L.exe",
                                   serial_number="682395790")
        assert backend.command_line("out.log") == [
            "L.exe", "-Device", "nRF52840_xxAA", "-If", "SWD", "-Speed", "4000",
            "-USB", "682395790", "-RTTChannel", "0", "out.log"]

    def test_a_missing_logger_is_reported(self, monkeypatch):
        monkeypatch.setattr(commander_module, "find_rtt_logger", lambda explicit: None)
        with pytest.raises(ConnectionFailedError, match="JLinkRTTLogger"):
            RttLoggerBackend(device="X").command_line("out.log")

    def test_bytes_the_logger_writes_are_polled_from_its_file(self, monkeypatch, tmp_path):
        script = tmp_path / "logger.py"
        script.write_text(
            "import sys, time\n"
            "open(sys.argv[1], 'wb').write(b'line one\\n')\n"
            "time.sleep(30)\n")
        backend = RttLoggerBackend(device="X", directory=str(tmp_path))
        monkeypatch.setattr(backend, "command_line",
                            lambda path: [sys.executable, str(script), path])
        backend.rtt_open()
        try:
            deadline, data = time.monotonic() + 10, b""
            while not data and time.monotonic() < deadline:
                data = backend.rtt_poll()
                time.sleep(0.05)
            assert data == b"line one\n"
        finally:
            backend.rtt_close()

    def test_a_logger_that_exits_says_what_it_printed(self, monkeypatch, tmp_path):
        script = tmp_path / "logger.py"
        script.write_text("print('RTT Control Block not found. Cannot get data.')\n")
        backend = RttLoggerBackend(device="X", directory=str(tmp_path))
        monkeypatch.setattr(backend, "command_line",
                            lambda path: [sys.executable, str(script), path])
        with pytest.raises(ConnectionFailedError, match="Control Block not found"):
            backend.rtt_open()


class TestCli:
    def run(self, capsys, *arguments):
        status = cli_main(["-r", "sim://"] + list(arguments))
        captured = capsys.readouterr()
        return status, (json.loads(captured.out) if captured.out.strip() else None), captured.err

    def test_info_names_the_backend(self, capsys):
        status, payload, _ = self.run(capsys, "--backend", "segger", "info")
        assert status == 0 and payload["backend"] == "segger"
        assert payload["program_counter"] is None

    def test_the_default_backend_is_gdb(self, capsys):
        _, payload, _ = self.run(capsys, "info")
        assert payload["backend"] == "gdb" and payload["program_counter"]

    def test_erase_names_the_backend(self, capsys):
        status, payload, _ = self.run(capsys, "--backend", "segger", "erase")
        assert status == 0 and payload["backend"] == "segger"

    def test_a_gdb_only_sub_command_fails_saying_why(self, capsys):
        status, _, err = self.run(capsys, "--backend", "segger", "var", "sensor_count")
        assert status == 1 and "'segger' backend" in err and "backend: gdb" in err

    def test_an_unknown_backend_is_a_usage_error(self, capsys):
        with pytest.raises(SystemExit) as raised:
            cli_main(["--backend", "openocd", "info"])
        assert raised.value.code == 2
        capsys.readouterr()
