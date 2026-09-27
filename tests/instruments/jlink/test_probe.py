"""The J-Link probe driver.

Traces to: JLINK-FR-003 .. JLINK-FR-045, SWE4-UT-JLINK.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from benchtools.core.errors import (
    BenchToolsError,
    ConfigurationError,
    ConnectionFailedError,
    MeasurementError,
    TransportTimeoutError,
)
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.jlink import (
    BreakpointKind,
    HaltReason,
    JLinkProbe,
    ProbeLimits,
    SimulatedJLink,
    WatchpointKind,
)
from benchtools.instruments.jlink.session import GdbMiSession

from .conftest import END_LOCATION, START_LOCATION


def probe_for(**simulator_kwargs) -> JLinkProbe:
    """A connected probe over a simulator built with *simulator_kwargs*."""
    simulator = SimulatedJLink(**simulator_kwargs)
    instance = JLinkProbe(
        session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
        elf="firmware.elf",
        target_address="simulated",
    )
    instance.initialise()
    return instance


class TestConnection:
    def test_connect_to_the_simulator(self):
        with JLinkProbe.connect("sim://", elf="firmware.elf") as probe:
            assert probe.is_attached and probe.is_open

    def test_identification(self, probe):
        identity = probe.identify()
        assert identity.manufacturer == "SEGGER"
        assert identity.model.startswith("J-Link")
        assert identity.serial_number == "801012345"
        assert identity.firmware.startswith("V")

    def test_gdb_is_configured_so_it_cannot_block(self, probe):
        """With confirm or pagination left on, GDB waits for a keypress and an
        unattended run hangs."""
        log = probe.session.transport.responder.command_log
        assert "-gdb-set confirm off" in log
        assert "-gdb-set pagination off" in log

    def test_symbols_are_loaded(self, probe):
        assert probe.elf_path == "firmware.elf"
        assert probe.session.transport.responder.symbols_loaded

    def test_detached_target_is_reported_clearly(self):
        simulator = SimulatedJLink(attached=False)
        instance = JLinkProbe(
            session=GdbMiSession(MockTransport(responder=simulator)),
            elf="firmware.elf", target_address="simulated",
        )
        with pytest.raises(ConnectionFailedError, match="could not attach"):
            instance.initialise()
        instance.close()

    def test_closing_is_idempotent(self, probe):
        probe.close()
        probe.close()
        assert not probe.is_open

    def test_closing_leaves_the_target_running(self):
        """The GDB Server halts the core on attach and does not resume it on
        detach; a sensor left that way stopped advertising (issue #69)."""
        simulator = SimulatedJLink()
        probe = JLinkProbe(
            session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
            elf="firmware.elf", target_address="simulated",
        )
        probe.initialise()
        probe.halt()
        probe.close()
        assert simulator.monitor_log[-1] == "go"
        assert simulator.halted is False

    def test_closing_can_leave_the_target_halted(self):
        simulator = SimulatedJLink()
        probe = JLinkProbe(
            session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
            elf="firmware.elf", target_address="simulated",
        )
        probe.initialise()
        probe.halt()
        probe.leave_halted = True
        probe.close()
        assert "go" not in simulator.monitor_log
        assert simulator.halted is True

    def test_identity_falls_back_to_the_server_banner(self, monkeypatch):
        """J-Link GDB Server V9 rejects 'monitor version'; the banner of the
        server the driver started still names the probe."""

        class Server:
            def probe_identity(self):
                return {"serial_number": "682395790", "hardware": "V8.00",
                        "firmware": "J-Link ARM V8 compiled Nov 28 2014 13:44:46"}

            def stop(self):
                pass

        probe = probe_for()
        probe._server = Server()
        real = probe._session.execute_console

        def console(command, **kwargs):
            if command == "monitor version":
                return SimpleNamespace(text="")
            return real(command, **kwargs)

        monkeypatch.setattr(probe._session, "execute_console", console)
        try:
            identity = probe._read_identity()
        finally:
            probe.close()
        assert identity.serial_number == "682395790"
        assert identity.firmware.startswith("J-Link ARM V8")
        assert "S/N: 682395790" in identity.raw

    @pytest.mark.parametrize(
        "resource,expected",
        [
            ("jlink://", ("127.0.0.1", 2331)),
            ("jlink://localhost", ("localhost", 2331)),
            ("jlink://192.168.1.9:2331", ("192.168.1.9", 2331)),
            ("jlink://10.0.0.5:3333", ("10.0.0.5", 3333)),
        ],
    )
    def test_resource_parsing(self, resource, expected):
        """A remote host is how a containerised bench reaches a probe."""
        assert JLinkProbe._parse_target(resource) == expected

    def test_invalid_port_is_rejected(self):
        with pytest.raises(ConfigurationError, match="invalid port"):
            JLinkProbe._parse_target("jlink://host:notaport")

    def test_missing_elf_is_reported(self):
        """Checked against the filesystem only for a real target: the simulator
        has no files, so its firmware name need not exist on disk."""
        probe = probe_for()
        probe._target_address = "127.0.0.1:2331"
        try:
            with pytest.raises(ConfigurationError, match="no such ELF"):
                probe.load_symbols("/nonexistent/app.elf")
        finally:
            probe.close()


class TestFlashAndVerify:
    def test_flash_reports_what_was_written(self, probe):
        result = probe.flash(verify=True)
        assert result.bytes_written == 0x4000 + 0x200 + 0x180
        assert set(result.sections) == {".text", ".rodata", ".data"}
        assert result.verified is True

    def test_flash_resets_first_by_default(self, probe):
        """Programming a running target corrupts whatever it was doing."""
        probe.flash(verify=False)
        assert any("reset" in entry for entry in probe.session.transport.responder.monitor_log)

    def test_a_named_image_is_loaded_before_it_is_read(self, probe):
        """GDB 15.2 exited when a HEX file on a mapped drive was read with
        'file' and then loaded (issue #69); 'load <file>' first did not."""
        probe.flash("C:\\images\\app.hex", verify=False)
        log = probe.session.transport.responder.command_log
        load = next(i for i, c in enumerate(log) if 'load \\"C:/images/app.hex\\"' in c)
        read = max(i for i, c in enumerate(log) if c.startswith("-file-exec-and-symbols"))
        assert load < read
        assert probe.elf_path == "C:\\images\\app.hex"

    def test_erase_resets_first_and_leaves_flash_blank(self, probe):
        probe.erase()
        responder = probe.session.transport.responder
        assert responder.monitor_log.index("reset") < responder.monitor_log.index("flash erase")
        assert probe.read_word(0) == 0xFFFFFFFF

    def test_an_erase_that_did_not_happen_raises(self, probe, monkeypatch):
        """The server said 'Flash erase: O.K.' and erased nothing (issue #69)."""
        monkeypatch.setattr(probe, "read_word", lambda address: 0x20000400)
        with pytest.raises(BenchToolsError, match="still reads 0x20000400"):
            probe.erase()

    def test_the_blank_check_can_be_skipped(self, probe, monkeypatch):
        monkeypatch.setattr(probe, "read_word", lambda address: 0)
        assert "O.K." in probe.erase(blank_check_address=None)

    def test_verification_failure_raises(self):
        probe = probe_for(flash_matches=False)
        try:
            with pytest.raises(BenchToolsError, match="verification failed"):
                probe.flash(verify=True)
        finally:
            probe.close()

    def test_verify_alone_reports_mismatched_sections(self):
        probe = probe_for(flash_matches=False)
        try:
            result = probe.verify()
            assert not result.matched
            assert ".text" in result.mismatched
        finally:
            probe.close()

    def test_an_empty_comparison_is_not_a_pass(self):
        """Nothing compared means nothing verified; reporting success would pass
        a test that checked nothing."""
        from benchtools.instruments.jlink.probe import VerifyResult

        assert VerifyResult(sections=[]).matched is False

    def test_flash_without_an_image_is_rejected(self):
        probe = probe_for()
        probe._elf = None
        try:
            with pytest.raises(ConfigurationError, match="no image to flash"):
                probe.flash()
        finally:
            probe.close()

    def test_verify_result_serialises(self, probe):
        assert probe.verify().as_dict()["matched"] is True

    def test_flash_result_serialises(self, probe):
        summary = probe.flash(verify=True).as_dict()
        assert summary["bytes_written"] > 0 and summary["verify"]["matched"] is True


class TestRunControl:
    def test_run_to_a_location(self, probe):
        info = probe.run_to(END_LOCATION)
        assert info.reason is HaltReason.BREAKPOINT
        assert info.function == "sensor_done"
        assert info.line == 75
        assert info.location == "sensor.c:75"

    def test_halt_reports_where(self, probe):
        probe.set_breakpoint(START_LOCATION)
        probe.run()
        info = probe.wait_for_halt()
        assert info.function == "sensor_start"
        assert probe.is_halted

    def test_step(self, probe):
        probe.run_to(START_LOCATION)
        info = probe.step()
        assert info.reason is HaltReason.STEP_DONE

    def test_reset_halts_by_default(self, probe):
        """Resetting into a running target races the start-up code."""
        probe.reset()
        assert probe.is_halted
        assert "reset" in probe.session.transport.responder.monitor_log

    def test_reset_can_leave_it_running(self, probe):
        probe.reset(halt=False)
        assert not probe.is_halted

    def test_program_counter_and_registers(self, probe):
        probe.run_to(END_LOCATION)
        assert probe.program_counter() == 0x080012C0
        registers = probe.registers()
        assert registers["pc"] == 0x080012C0
        assert "sp" in registers

    def test_never_reaching_a_breakpoint_times_out(self, probe):
        probe.set_breakpoint("nowhere.c:1")
        probe.run()
        with pytest.raises(TransportTimeoutError):
            probe.wait_for_halt(timeout=0.2)

    def test_unknown_halt_reason_does_not_break_the_driver(self, probe):
        info = probe._halt_info({"reason": "something-new-in-gdb"})
        assert info.reason is HaltReason.UNKNOWN


class TestBreakpoints:
    def test_set_and_list(self, probe):
        first = probe.set_breakpoint(START_LOCATION)
        second = probe.set_breakpoint(END_LOCATION)
        numbers = [entry.number for entry in probe.list_breakpoints()]
        assert first.number in numbers and second.number in numbers

    def test_breakpoint_carries_source_information(self, probe):
        entry = probe.set_breakpoint(END_LOCATION)
        assert entry.file == "sensor.c" and entry.line == 75
        assert entry.address == 0x080012C0

    def test_temporary_breakpoint_is_marked(self, probe):
        entry = probe.set_breakpoint(START_LOCATION, temporary=True)
        assert entry.is_temporary and entry.kind is BreakpointKind.TEMPORARY

    def test_conditional_breakpoint(self, probe):
        """The condition contains spaces, so it must survive as one argument."""
        entry = probe.set_breakpoint(END_LOCATION, condition="sensor_count > 5")
        assert entry.condition == "sensor_count > 5"

    def test_delete_and_clear(self, probe):
        entry = probe.set_breakpoint(START_LOCATION)
        probe.delete_breakpoint(entry.number)
        assert entry.number not in [item.number for item in probe.list_breakpoints()]
        probe.set_breakpoint(END_LOCATION)
        probe.clear_breakpoints()
        assert probe.list_breakpoints() == []

    def test_hardware_breakpoint_limit_is_enforced(self):
        """Cortex-M parts have a handful of comparators; exhausting them should
        say so rather than failing obscurely in the target."""
        probe = probe_for()
        try:
            for index in range(4):
                probe.set_breakpoint("main.c:%d" % (100 + index), hardware=True)
            with pytest.raises(ConfigurationError, match="hardware breakpoints"):
                probe.set_breakpoint("main.c:200", hardware=True)
        finally:
            probe.close()

    def test_limits_are_data_driven(self):
        probe = probe_for()
        probe._limits = ProbeLimits(max_hardware_breakpoints=1)
        try:
            probe.set_breakpoint("main.c:100", hardware=True)
            with pytest.raises(ConfigurationError, match="all 1 hardware"):
                probe.set_breakpoint("main.c:101", hardware=True)
        finally:
            probe.close()

    @pytest.mark.parametrize("kind", ["WRITE", "READ", "ACCESS"])
    def test_watchpoints(self, probe, kind):
        watchpoint = probe.set_watchpoint("sensor_count", kind=kind)
        assert watchpoint.number > 0
        assert watchpoint.kind is WatchpointKind.coerce(kind)


class TestMemory:
    def test_read_and_write_word(self, probe):
        probe.write_word(0x20000100, 0xDEADBEEF)
        assert probe.read_word(0x20000100) == 0xDEADBEEF

    def test_read_memory_returns_bytes(self, probe):
        probe.write_memory(0x20000200, b"\x01\x02\x03\x04")
        assert probe.read_memory(0x20000200, 4) == b"\x01\x02\x03\x04"

    def test_widths(self, probe):
        probe.write_memory(0x20000300, b"\xAA\xBB\xCC\xDD")
        assert probe.read_u8(0x20000300) == 0xAA
        assert probe.read_u16(0x20000300) == 0xBBAA

    def test_zero_length_read(self, probe):
        assert probe.read_memory(0x20000000, 0) == b""

    def test_negative_size_is_rejected(self, probe):
        with pytest.raises(ConfigurationError, match="must not be negative"):
            probe.read_memory(0x20000000, -1)

    def test_large_transfers_are_split(self, probe):
        """A caller should be able to ask for a whole region without knowing the
        probe's chunk size."""
        probe._limits = ProbeLimits(max_transfer_bytes=16)
        payload = bytes(range(64))
        probe.write_memory(0x20001000, payload)
        assert probe.read_memory(0x20001000, 64) == payload
        reads = [
            entry for entry in probe.session.transport.responder.command_log
            if entry.startswith("-data-read-memory-bytes")
        ]
        assert len(reads) >= 4

    def test_ram_aliases(self, probe):
        probe.write_ram(0x20000400, b"\x07")
        assert probe.read_ram(0x20000400, 1) == b"\x07"


class TestVariables:
    def test_read_integer(self, probe):
        assert probe.read_variable("sensor_mv") == 1234

    def test_read_string(self, probe):
        assert probe.read_variable("firmware_version") == "1.4.2"

    def test_write_then_read(self, probe):
        probe.write_variable("sensor_count", 99)
        assert probe.read_variable("sensor_count") == 99

    def test_address_and_size(self, probe):
        assert probe.variable_address("sensor_mv") == 0x20000104
        assert probe.variable_size("sensor_mv") == 4

    def test_memory_agrees_with_the_variable(self, probe):
        """A variable read and a raw read of its address must not disagree."""
        address = probe.variable_address("sensor_mv")
        assert probe.read_word(address) == probe.read_variable("sensor_mv")

    def test_unknown_variable_is_reported(self, probe):
        with pytest.raises(MeasurementError, match="cannot read"):
            probe.read_variable("no_such_symbol")

    def test_missing_symbols_are_mentioned_in_the_error(self):
        probe = probe_for()
        probe._elf = None
        try:
            with pytest.raises(MeasurementError, match="no ELF file is loaded"):
                probe.read_variable("no_such_symbol")
        finally:
            probe.close()

    def test_evaluate_expression(self, probe):
        assert probe.evaluate("sensor_mv") == 1234

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1234", 1234),
            ("0x4d2", 1234),
            ("-7", -7),
            ("1.5", 1.5),
            ('"hello"', "hello"),
            ("(uint32_t *) 0x20000104", 0x20000104),
            ("{a = 1, b = 2}", {"a": 1, "b": 2}),
            ("SOME_ENUM_NAME", "SOME_ENUM_NAME"),
            ("", None),
        ],
    )
    def test_value_parsing(self, text, expected):
        assert JLinkProbe._parse_gdb_value(text) == expected


class TestCallStack:
    def test_frames_innermost_first(self, probe):
        probe.run_to(END_LOCATION)
        frames = probe.call_stack()
        assert [frame.function for frame in frames] == [
            "sensor_done", "sensor_read", "main",
        ]
        assert frames[0].level == 0

    def test_frames_carry_source_positions(self, probe):
        probe.run_to(END_LOCATION)
        frame = probe.call_stack()[2]
        assert frame.file == "main.c" and frame.line == 130

    def test_limit(self, probe):
        probe.run_to(END_LOCATION)
        assert len(probe.call_stack(limit=2)) == 2

    def test_invalid_limit_is_rejected(self, probe):
        with pytest.raises(ConfigurationError, match="limit"):
            probe.call_stack(limit=0)

    def test_backtrace_is_the_same_call(self, probe):
        probe.run_to(END_LOCATION)
        assert [f.function for f in probe.backtrace()] == [
            f.function for f in probe.call_stack()
        ]

    def test_frame_renders_readably(self, probe):
        probe.run_to(END_LOCATION)
        assert str(probe.call_stack()[0]) == "#0  sensor_done at sensor.c:75"


class TestMonitorAndRaw:
    def test_monitor_passthrough(self, probe):
        output = probe.monitor("version")
        assert "J-Link" in output

    def test_unknown_console_command_is_an_error(self, probe):
        """A driver sending the wrong thing should fail, not pass quietly."""
        from benchtools.instruments.jlink.session import GdbError

        with pytest.raises(GdbError):
            probe.session.execute_console("nonsense-command")


class TestWhatWasFlashed:
    """The build description of the image on the target.

    A specification that wrote the version down would go stale the day someone
    rebuilt the firmware, and the comparison it makes - build against running
    firmware - would be circular. The probe knows which file it flashed, and
    the build that produced that file left a manifest beside it.

    Traces to: JLINK-FR-024.
    """

    def build_directory(self, tmp_path, version="1.4.2"):
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "firmware_manifest.json").write_text(
            json.dumps({"version": version, "built": "2026-09-13T12:00:00Z"})
        )
        return tmp_path

    def test_it_reads_the_manifest_beside_the_image(self, tmp_path):
        directory = self.build_directory(tmp_path)
        (directory / "app.elf").write_text("not really an elf")
        probe = JLinkProbe.connect("sim://", elf=str(directory / "app.elf"))
        try:
            assert probe.image_build().version == "1.4.2"
        finally:
            probe.close()

    def test_a_configured_build_directory_wins(self, tmp_path):
        """The bench says where the build is; the ELF is only symbols."""
        directory = self.build_directory(tmp_path / "build", version="2.0.0")
        probe = JLinkProbe.connect("sim://", firmware=str(directory))
        try:
            assert probe.image_build().version == "2.0.0"
        finally:
            probe.close()

    def test_a_path_given_at_the_step_wins_over_both(self, tmp_path):
        elsewhere = self.build_directory(tmp_path / "elsewhere", version="3.1.4")
        probe = JLinkProbe.connect("sim://", firmware=str(tmp_path / "nothing"))
        try:
            assert probe.image_build(str(elsewhere)).version == "3.1.4"
        finally:
            probe.close()

    def test_the_manifest_itself_can_be_named(self, tmp_path):
        directory = self.build_directory(tmp_path)
        probe = JLinkProbe.connect("sim://")
        try:
            build = probe.image_build(str(directory / "firmware_manifest.json"))
            assert build.version == "1.4.2"
        finally:
            probe.close()

    def test_no_manifest_says_where_it_looked_and_what_makes_one(self, tmp_path):
        probe = JLinkProbe.connect("sim://", firmware=str(tmp_path))
        try:
            with pytest.raises(ConfigurationError, match="written by the build"):
                probe.image_build()
        finally:
            probe.close()


class TestIsItRunning:
    """RTT output arriving at all, which is what "it started" looks like from
    outside.

    Traces to: JLINK-FR-054.
    """

    def test_a_running_target_produces_lines(self, probe):
        probe.rtt_start()
        probe.reset(halt=False)
        assert probe.rtt_lines_within(1.0) >= 1

    def test_a_halted_target_produces_none(self, probe):
        """Zero is a number a limit can fail, which is the point of counting
        rather than waiting for a pattern: a silent board is a failed test, not
        a broken bench."""
        probe.rtt_start()
        assert probe.rtt_lines_within(0.2) == 0

    def test_it_does_not_wait_once_lines_have_arrived(self, probe):
        import time

        probe.rtt_start()
        probe.reset(halt=False)
        started = time.monotonic()
        probe.rtt_lines_within(5.0)
        assert time.monotonic() - started < 1.0


class TestByteOrderedReads:
    """Reading a field a part was programmed with, rather than a word the core
    would load.

    An identity record's width and byte order belong to the record. The word
    accessors are little-endian because that is how a Cortex-M loads a word;
    an identifier written at manufacture is usually in address order, because
    that is the order it is printed and read back in.

    Traces to: JLINK-FR-043.
    """

    RECORD = bytes([0x00, 0x0A, 0x1B, 0x2C])
    ADDRESS = 0x20000200

    @pytest.fixture
    def programmed(self, probe):
        probe.write_memory(self.ADDRESS, self.RECORD)
        return probe

    def test_address_order(self, programmed):
        assert programmed.read_integer(self.ADDRESS + 1, 3, byteorder="big") == 0x0A1B2C

    def test_the_other_order_is_a_different_number(self, programmed):
        """Worth asserting: getting this wrong reads a plausible value, and
        nothing downstream would question 0x2C1B0A."""
        assert programmed.read_integer(self.ADDRESS + 1, 3) == 0x2C1B0A

    def test_one_byte(self, programmed):
        assert programmed.read_integer(self.ADDRESS, 1) == 0x00

    def test_signed(self, probe):
        probe.write_memory(self.ADDRESS, b"\xff\xff")
        assert probe.read_integer(self.ADDRESS, 2, signed=True) == -1
        assert probe.read_integer(self.ADDRESS, 2) == 0xFFFF

    @pytest.mark.parametrize("size", [0, -1, 9])
    def test_a_width_it_does_not_support_is_refused(self, probe, size):
        with pytest.raises(ConfigurationError, match="1 to 8 bytes"):
            probe.read_integer(self.ADDRESS, size)

    def test_a_misspelled_byte_order_is_refused(self, probe):
        """Not silently treated as little-endian: that would read a plausible
        and entirely wrong number."""
        with pytest.raises(ConfigurationError, match="little.*big"):
            probe.read_integer(self.ADDRESS, 2, byteorder="bug")
