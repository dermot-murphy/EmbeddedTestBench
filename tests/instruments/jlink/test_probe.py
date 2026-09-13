"""The J-Link probe driver.

Traces to: JLINK-FR-003 .. JLINK-FR-045, SWE4-UT-JLINK.
"""

from __future__ import annotations

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
