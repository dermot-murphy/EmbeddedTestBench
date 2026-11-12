"""The simulated thermometer answers as the firmware does.

The reply strings asserted here are the ones the firmware's own unit tests
assert (firmware/pico_sht30/test/test_cmd_parser.c), so the simulator and the
firmware are held to the same text.

Traces to: PICO-FR-050, SWE4-UT-PICOSIM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.pico_sht30 import SimulatedPicoSht30, raw_to_celsius
from benchtools.instruments.pico_sht30.constants import milli_to_centi_text
from benchtools.instruments.pico_sht30.simulator import celsius_to_raw, raw_to_milli


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
        assert raw_to_milli(raw) == round(celsius * 1000)

    def test_raw_is_clamped(self):
        assert celsius_to_raw(-100.0) == 0
        assert celsius_to_raw(200.0) == 0xFFFF

    @pytest.mark.parametrize(
        "milli,text",
        [(22848, "22.85"), (22844, "22.84"), (25000, "25.00"), (-1234, "-1.23"),
         (-1235, "-1.24"), (-5, "-0.01"), (-4, "0.00"), (4, "0.00"), (5, "0.01"),
         (0, "0.00"), (-45000, "-45.00"), (130000, "130.00")],
    )
    def test_two_places_half_away_from_zero(self, milli, text):
        assert milli_to_centi_text(milli) == text


class TestReplies:
    @pytest.mark.parametrize(
        "line,reply",
        [("rd name", "ACK rd name = Pico 2 SHT30 Temperature Sensor"),
         ("rd copyright", "ACK rd copyright = (c) 2026 Dermot Murphy"),
         ("rd version", "ACK rd version = V1.02.0000"),
         ("rd sha", "ACK rd sha = 0c0ffee"),
         ("rd colour", "NAK rd colour = Error"),
         ("rd NAME", "NAK rd NAME = Error")],
    )
    def test_rd(self, line, reply):
        assert _ask(SimulatedPicoSht30(), line) == reply + "\n"

    def test_rd_temperature(self):
        assert _ask(SimulatedPicoSht30(temperature=25.0), "rd temperature") == \
            "ACK rd temperature = 25.00\n"
        assert _ask(SimulatedPicoSht30(temperature=-1.249), "rd temperature") == \
            "ACK rd temperature = -1.25\n"

    def test_rd_needs_exactly_one_option(self):
        assert _ask(SimulatedPicoSht30(), "rd") == "err 2 wrong number of arguments\n"
        assert _ask(SimulatedPicoSht30(), "rd name sha") == "err 2 wrong number of arguments\n"

    @pytest.mark.parametrize("removed", ["ver", "temp", "reset"])
    def test_removed_commands_are_unknown(self, removed):
        assert _ask(SimulatedPicoSht30(), removed) == "err 1 unknown command\n"

    def test_blank_line_has_no_reply(self):
        assert SimulatedPicoSht30().respond(b"\n") is None

    def test_unexpected_argument(self):
        assert _ask(SimulatedPicoSht30(), "status now") == "err 2 wrong number of arguments\n"

    def test_over_length_line(self):
        assert _ask(SimulatedPicoSht30(), "t" * 70) == "err 3 line too long\n"

    def test_help_ends_with_ok(self):
        lines = _ask(SimulatedPicoSht30(), "help").splitlines()
        assert len(lines) == 9
        assert lines[0].startswith("# help - ")
        assert lines[1].startswith("# rd - ")
        assert lines[2].startswith("# wr - ")
        assert lines[-1] == "ok"

    def test_faults(self):
        simulator = SimulatedPicoSht30()
        simulator.corrupt_next = True
        assert _ask(simulator, "rd temperature") == "ACK rd temperature = Error\n"
        assert _ask(simulator, "rd temperature") == "ACK rd temperature = 22.50\n"
        simulator.sensor_present = False
        assert _ask(simulator, "rd temperature") == "ACK rd temperature = Error\n"
        assert _ask(simulator, "status") == "err 4 the sensor did not acknowledge\n"
        simulator.bus_timeout = True
        assert _ask(simulator, "rd temperature") == "ACK rd temperature = Error\n"
        assert _ask(simulator, "sreset") == "err 6 I2C bus timeout\n"

    def test_leds_are_off_at_boot(self):
        simulator = SimulatedPicoSht30()
        for colour in ("red", "yellow", "green"):
            assert _ask(simulator, "rd led-%s" % colour) == "ACK rd led-%s = off\n" % colour

    def test_wr_led_on_and_off(self):
        """The same reply text as test_wr_led_red_on_and_off in test_cmd_parser.c."""
        simulator = SimulatedPicoSht30()
        assert _ask(simulator, "wr led-red on") == "ACK wr led-red = on\n"
        assert _ask(simulator, "rd led-red") == "ACK rd led-red = on\n"
        assert _ask(simulator, "rd led-yellow") == "ACK rd led-yellow = off\n"
        assert _ask(simulator, "wr led-red off") == "ACK wr led-red = off\n"
        assert _ask(simulator, "rd led-red") == "ACK rd led-red = off\n"

    @pytest.mark.parametrize("line,option",
                             [("wr led-blue on", "led-blue"), ("wr name on", "name"),
                              ("wr LED-RED on", "LED-RED"), ("wr led-red 1", "led-red"),
                              ("wr led-red OFF", "led-red")])
    def test_wr_refused(self, line, option):
        simulator = SimulatedPicoSht30()
        assert _ask(simulator, line) == "NAK wr %s = Error\n" % option
        assert not any(simulator.leds.values())

    def test_wr_needs_an_option_and_a_value(self):
        for line in ("wr", "wr led-red", "wr led-red on now", "wr led-red 2 on"):
            assert _ask(SimulatedPicoSht30(), line) == "err 2 wrong number of arguments\n"

    def test_ecureset_turns_the_leds_off(self):
        simulator = SimulatedPicoSht30()
        _ask(simulator, "wr led-green on")
        _ask(simulator, "ecureset")
        assert _ask(simulator, "rd led-green") == "ACK rd led-green = off\n"

    def test_ecureset(self):
        simulator = SimulatedPicoSht30()
        assert _ask(simulator, "ecureset") == "ok\n"
        assert simulator.reboots == 1

    def test_bootsel_calls_the_board(self):
        simulator = SimulatedPicoSht30()
        calls = []
        simulator.on_bootloader = lambda: calls.append(True)
        assert _ask(simulator, "bootsel") == "ok\n"
        assert calls == [True]
