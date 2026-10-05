"""Self-checks on the J-Link simulator.

The simulator is test equipment: if it misrepresents a probe, every test above it
is worthless. Its determinism is what lets timing tests assert exact figures, so
that determinism is itself pinned down here.

Traces to: JLINK-FR-090, SWE4-UT-JLINKSIM.
"""

from __future__ import annotations

import pytest

from benchtools.core.simulator import Responder
from benchtools.instruments.jlink import SimulatedFirmware, SimulatedJLink, SimulatedSymbol
from benchtools.instruments.jlink.constants import DWT_CYCCNT
from benchtools.instruments.jlink.gdbmi import parse_line


class TestProtocol:
    def test_satisfies_the_responder_protocol(self, simulator):
        assert isinstance(simulator, Responder)

    def test_every_reply_ends_with_the_prompt(self, simulator):
        for command in (b"1-gdb-set confirm off", b"2-break-list", b"3-stack-list-frames"):
            reply = simulator.respond(command).decode()
            assert reply.rstrip().endswith("(gdb)")

    def test_token_is_echoed(self, simulator):
        assert simulator.respond(b"7-gdb-set x").decode().startswith("7^done")

    def test_output_parses_as_mi(self, simulator):
        reply = simulator.respond(b"1-break-insert sensor.c:40").decode()
        record = parse_line(reply.splitlines()[0])
        assert record.message == "done" and record.results["bkpt"]["line"] == "40"

    def test_unknown_command_is_an_error(self, simulator):
        """A driver sending the wrong thing should fail a test, not pass."""
        assert "^error" in simulator.respond(b"1-not-a-command").decode()

    def test_commands_are_logged(self, simulator):
        simulator.respond(b"1-gdb-set confirm off")
        assert simulator.command_log[-1] == "-gdb-set confirm off"


class TestExecutionModel:
    def test_execution_is_deterministic(self):
        """Two runs of the same programme must give the same cycle counts, or a
        timing test can only assert a tolerance."""
        runs = []
        for _ in range(2):
            simulator = SimulatedJLink()
            simulator.connected = True
            simulator.breakpoints[1] = {"location": "sensor.c:40", "enabled": True}
            simulator.breakpoints[2] = {"location": "sensor.c:75", "enabled": True}
            simulator.resume()
            first = simulator.cycles
            simulator.resume()
            runs.append((first, simulator.cycles))
        assert runs[0] == runs[1] == (5_000, 69_000)

    def test_the_interval_is_exactly_one_millisecond(self):
        """64 000 cycles at 64 MHz. Chosen so tests assert a round number."""
        _firmware = SimulatedFirmware()
        default = SimulatedJLink().firmware
        assert default.cycles_at["sensor.c:75"] - default.cycles_at["sensor.c:40"] == 64_000
        assert 64_000 / default.core_clock_hz == pytest.approx(1.0e-3)

    def test_cycle_counter_is_readable_through_memory(self, simulator):
        """The DWT register must answer a raw read, or the cycle-counter timing
        method could only be tested at the arithmetic level."""
        simulator.connected = True
        simulator.breakpoints[1] = {"location": "sensor.c:75", "enabled": True}
        simulator.resume()
        assert int.from_bytes(simulator.read_memory(DWT_CYCCNT, 4), "little") == 69_000

    def test_temporary_breakpoints_are_removed_when_hit(self, simulator):
        simulator.connected = True
        simulator.breakpoints[1] = {
            "location": "sensor.c:40", "enabled": True, "temporary": True,
        }
        simulator.resume()
        assert 1 not in simulator.breakpoints

    def test_step_advances_one_location(self, simulator):
        simulator.connected = True
        before = simulator.location
        simulator.step()
        assert simulator.location != before

    def test_reset_returns_to_the_start(self, simulator):
        simulator.connected = True
        simulator.breakpoints[1] = {"location": "sensor.c:75", "enabled": True}
        simulator.resume()
        simulator.respond(b'1-interpreter-exec console "monitor reset"')
        assert simulator.cycles == 0
        assert simulator.location == simulator.firmware.flow[0]

    @pytest.mark.parametrize("command", ["monitor reset", "monitor reset 0"])
    def test_every_reset_type_leaves_the_core_halted(self, simulator, command):
        """As the J-Link GDB Server does: after 'monitor reset 0' the nRF52840
        on the bench stayed halted until something resumed it (issue #177)."""
        simulator.connected = True
        simulator.resume()
        assert not simulator.halted
        simulator.respond(('1-interpreter-exec console "%s"' % command).encode())
        assert simulator.halted

    def test_running_with_no_breakpoint_does_not_hang(self, simulator):
        simulator.connected = True
        assert simulator.resume() == {}
        assert not simulator.halted


class TestMemoryAndSymbols:
    def test_symbol_values_are_in_memory(self, simulator):
        """A variable read and a raw read of its address must agree."""
        symbol = simulator.firmware.symbols["sensor_mv"]
        assert simulator._read_int(symbol.address, 4) == 1234

    def test_writes_are_readable(self, simulator):
        simulator.write_memory(0x20000900, b"\xde\xad\xbe\xef")
        assert simulator.read_memory(0x20000900, 4) == b"\xde\xad\xbe\xef"

    def test_unmapped_memory_reads_as_zero(self, simulator):
        assert simulator.read_memory(0x30000000, 4) == b"\x00\x00\x00\x00"

    def test_evaluate_forms(self, simulator):
        assert simulator.evaluate("sensor_mv") == "1234"
        assert "0x20000104" in simulator.evaluate("&sensor_mv")
        assert simulator.evaluate("sizeof(sensor_mv)") == "4"
        assert simulator.evaluate("firmware_version") == '"1.4.2"'

    def test_unknown_symbol_raises(self, simulator):
        with pytest.raises(KeyError):
            simulator.evaluate("not_a_symbol")

    def test_setting_a_variable_updates_memory(self, simulator):
        simulator.set_variable("sensor_mv", 4242)
        assert simulator.evaluate("sensor_mv") == "4242"
        assert simulator._read_int(0x20000104, 4) == 4242


class TestCustomFirmware:
    def test_a_custom_programme_can_be_supplied(self):
        firmware = SimulatedFirmware(
            flow=["a.c:1", "a.c:2"],
            cycles_at={"a.c:1": 0, "a.c:2": 1_000},
            locations={"a.c:1": 0x1000, "a.c:2": 0x1100},
            symbols={"counter": SimulatedSymbol(0x20000000, 4, 42, "int")},
            core_clock_hz=16.0e6,
        )
        simulator = SimulatedJLink(firmware=firmware)
        simulator.connected = True
        simulator.breakpoints[1] = {"location": "a.c:2", "enabled": True}
        simulator.resume()
        assert simulator.cycles == 1_000
        assert simulator.evaluate("counter") == "42"

    def test_an_unlisted_location_gets_a_stable_address(self, simulator):
        first = simulator.firmware.address_of("unknown.c:7")
        assert first == simulator.firmware.address_of("unknown.c:7")

    def test_a_detached_probe_refuses_to_attach(self):
        simulator = SimulatedJLink(attached=False)
        assert "^error" in simulator.respond(b"1-target-select extended-remote x:1").decode()

    def test_flash_mismatch_can_be_simulated(self):
        simulator = SimulatedJLink(flash_matches=False)
        reply = simulator.respond(b'1-interpreter-exec console "compare-sections"').decode()
        assert "MIS-MATCHED" in reply
