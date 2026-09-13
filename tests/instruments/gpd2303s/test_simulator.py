"""Self-checks on the simulated supply.

A simulator that is wrong is worse than none: every test above it passes and
none of them mean anything. These assert the model's own behaviour - Ohm's law,
the constant-current fallback, the single output switch, and the refusals -
independently of the driver.

Traces to: PSU-FR-050, SWE4-UT-PSUSIM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.gpd2303s import ChannelMode, SimulatedGpd
from benchtools.instruments.gpd2303s.simulator import SimulatedChannel


def ask(simulator, command):
    """Send one command line and return the decoded reply, or None."""
    reply = simulator.respond(command.encode("ascii"))
    return None if reply is None else reply.decode("ascii").strip()


class TestChannelModel:
    def test_an_unloaded_channel_delivers_its_setpoint_and_no_current(self):
        channel = SimulatedChannel()
        channel.voltage_setpoint = 5.0
        channel.current_limit = 1.0
        assert channel.output(True) == {
            "voltage": 5.0, "current": 0.0, "mode": ChannelMode.CONSTANT_VOLTAGE}

    def test_a_load_draws_what_ohm_s_law_says(self):
        channel = SimulatedChannel(load_ohms=10.0)
        channel.voltage_setpoint = 5.0
        channel.current_limit = 1.0
        assert channel.output(True)["current"] == pytest.approx(0.5)

    def test_a_load_that_wants_more_than_the_limit_gets_the_limit(self):
        channel = SimulatedChannel(load_ohms=2.0)
        channel.voltage_setpoint = 5.0
        channel.current_limit = 1.0
        result = channel.output(True)
        assert result["mode"] == ChannelMode.CONSTANT_CURRENT
        assert result["current"] == pytest.approx(1.0)
        assert result["voltage"] == pytest.approx(2.0), "V = I x R, not the setpoint"

    def test_exactly_at_the_limit_is_still_constant_voltage(self):
        channel = SimulatedChannel(load_ohms=10.0)
        channel.voltage_setpoint = 5.0
        channel.current_limit = 0.5
        assert channel.output(True)["mode"] == ChannelMode.CONSTANT_VOLTAGE

    def test_a_de_energised_channel_is_at_zero(self):
        channel = SimulatedChannel(load_ohms=10.0)
        channel.voltage_setpoint = 5.0
        channel.current_limit = 1.0
        assert channel.output(False)["voltage"] == 0.0


class TestCommands:
    def test_idn(self, ):
        assert ask(SimulatedGpd(), "*IDN?").startswith("GW INSTEK,GPD-2303S")

    def test_setting_and_reading_back(self):
        simulator = SimulatedGpd()
        assert ask(simulator, "VSET1:3.300") is None
        assert ask(simulator, "VSET1?") == "3.300"
        assert ask(simulator, "ISET1:0.500") is None
        assert ask(simulator, "ISET1?") == "0.500"

    def test_measurements_carry_their_unit(self):
        """As the instrument's do, which is what the driver has to strip."""
        simulator = SimulatedGpd(load_ohms={1: 10.0})
        ask(simulator, "VSET1:3.300")
        ask(simulator, "ISET1:1.000")
        ask(simulator, "OUT1")
        assert ask(simulator, "VOUT1?") == "3.300V"
        assert ask(simulator, "IOUT1?") == "0.330A"

    def test_the_output_switch_is_one_switch(self):
        """Which is the whole reason the driver emulates per-channel control."""
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:1.000")
        ask(simulator, "VSET2:2.000")
        ask(simulator, "OUT1")
        assert ask(simulator, "VOUT1?") == "1.000V"
        assert ask(simulator, "VOUT2?") == "2.000V"
        ask(simulator, "OUT0")
        assert ask(simulator, "VOUT1?") == "0.000V"
        assert ask(simulator, "VOUT2?") == "0.000V"

    def test_out0_is_understood(self):
        """It shares its digit position with a channel number, and an earlier
        version of this simulator quietly refused it."""
        simulator = SimulatedGpd()
        ask(simulator, "OUT1")
        assert simulator.output is True
        ask(simulator, "OUT0")
        assert simulator.output is False
        assert simulator.last_error == ""

    def test_status_is_eight_bits(self):
        assert set(ask(SimulatedGpd(), "STATUS?")) <= {"0", "1"}
        assert len(ask(SimulatedGpd(), "STATUS?")) == 8

    def test_the_supply_clamps_rather_than_refusing(self):
        """Which is exactly what the driver's range check protects against."""
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:35.000")
        assert ask(simulator, "VSET1?") == "30.000"
        assert "Range" in simulator.last_error

    def test_an_unknown_command_is_met_with_silence(self):
        """As the hardware does: a misspelled command reads as a timeout."""
        simulator = SimulatedGpd()
        assert ask(simulator, "VOLTAGE 3.3") is None
        assert "VOLTAGE" in simulator.last_error

    def test_a_channel_that_does_not_exist_is_refused(self):
        simulator = SimulatedGpd()
        assert ask(simulator, "VSET3:1.000") is None
        assert ask(simulator, "VOUT9?") is None
        assert "channel" in simulator.last_error

    def test_err_reports_then_clears(self):
        simulator = SimulatedGpd()
        ask(simulator, "NONSENSE")
        assert "NONSENSE" in ask(simulator, "ERR?")
        assert ask(simulator, "ERR?") == "No Error."

    def test_an_empty_line_is_ignored(self):
        assert ask(SimulatedGpd(), "") is None

    def test_replies_end_as_the_instrument_ends_them(self):
        """CR LF, not bare LF: a driver that assumes otherwise leaves a stray
        byte in the buffer and reads it as the head of the next reply."""
        assert SimulatedGpd().respond(b"*IDN?").endswith(b"\r\n")

    def test_a_load_can_be_attached_after_construction(self):
        simulator = SimulatedGpd()
        simulator.set_load(1, 5.0)
        ask(simulator, "VSET1:5.000")
        ask(simulator, "ISET1:3.000")
        ask(simulator, "OUT1")
        assert ask(simulator, "IOUT1?") == "1.000A"

    def test_reset_returns_it_to_power_on(self):
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:5.000")
        ask(simulator, "OUT1")
        simulator.reset()
        assert simulator.output is False
        assert ask(simulator, "VSET1?") == "0.000"

    def test_every_command_is_logged(self):
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:1.000")
        ask(simulator, "OUT1")
        assert simulator.command_log == ["VSET1:1.000", "OUT1"]
