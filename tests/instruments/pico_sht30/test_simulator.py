"""The simulated thermometer answers as the firmware does.

The reply strings asserted here are the ones the firmware's own unit tests
assert (firmware/pico_sht30/test/test_cmd_parser.c), so the simulator and the
firmware are held to the same text.

Traces to: PICO-FR-050, SWE4-UT-PICOSIM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.pico_sht30 import SimulatedPicoSht30, raw_to_celsius
from benchtools.instruments.pico_sht30.simulator import celsius_to_raw, percent_to_raw


def _ask(simulator: SimulatedPicoSht30, line: str) -> str:
    reply = simulator.respond((line + "\n").encode())
    return reply.decode() if reply else ""


class TestConversion:
    @pytest.mark.parametrize(
        "raw,celsius",
        [(0x0000, -45.0), (0xFFFF, 130.0), (0x6666, 25.0), (0x4000, -1.249), (0x0001, -44.997)],
    )
    def test_matches_the_firmware_vectors(self, raw, celsius):
        """The same vectors as firmware/pico_sht30/test/test_sht30.c."""
        assert raw_to_celsius(raw) == pytest.approx(celsius, abs=1e-9)

    def test_raw_is_clamped(self):
        assert celsius_to_raw(-100.0) == 0
        assert celsius_to_raw(200.0) == 0xFFFF
        assert percent_to_raw(-5.0) == 0
        assert percent_to_raw(150.0) == 0xFFFF


class TestReplies:
    def test_temp_matches_the_firmware_text(self):
        simulator = SimulatedPicoSht30(temperature=25.0, humidity=50.0)
        assert _ask(simulator, "temp") == "ok t=25.000 rh=50.001 raw_t=0x6666 raw_rh=0x8000\n"

    def test_ver(self):
        reply = _ask(SimulatedPicoSht30(), "ver")
        assert reply.startswith("ok title=Pico2-SHT30-Thermometer fw=1.0.0 ")
        assert " addr=0x44 " in reply

    def test_blank_line_has_no_reply(self):
        assert SimulatedPicoSht30().respond(b"\n") is None

    def test_unknown_command(self):
        assert _ask(SimulatedPicoSht30(), "fly") == "err 1 unknown command\n"

    def test_unexpected_argument(self):
        assert _ask(SimulatedPicoSht30(), "temp now") == "err 2 wrong number of arguments\n"

    def test_over_length_line(self):
        assert _ask(SimulatedPicoSht30(), "t" * 70) == "err 3 line too long\n"

    def test_help_ends_with_ok(self):
        lines = _ask(SimulatedPicoSht30(), "help").splitlines()
        assert len(lines) == 8
        assert lines[0].startswith("# help - ")
        assert lines[-1] == "ok"

    def test_faults(self):
        simulator = SimulatedPicoSht30()
        simulator.corrupt_next = True
        assert _ask(simulator, "temp") == "err 5 the sensor checksum did not match\n"
        assert _ask(simulator, "temp").startswith("ok ")
        simulator.sensor_present = False
        assert _ask(simulator, "status") == "err 4 the sensor did not acknowledge\n"
        simulator.bus_timeout = True
        assert _ask(simulator, "sreset") == "err 6 I2C bus timeout\n"

    def test_reset_restarts_uptime(self):
        simulator = SimulatedPicoSht30()
        simulator.uptime_s = 100
        assert _ask(simulator, "reset") == "ok\n"
        assert simulator.uptime_s == 0
