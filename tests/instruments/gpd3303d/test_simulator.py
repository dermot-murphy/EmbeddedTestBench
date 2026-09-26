"""Self-checks on the simulated supply.

A simulator that is wrong is worse than none: every test above it passes and
none of them mean anything. These assert the model's own behaviour - Ohm's law,
the constant-current fallback, the single output switch, and the refusals -
independently of the driver.

Traces to: PSU-FR-006, PSU-FR-050, SWE4-UT-PSUSIM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.gpd3303d import (
    TRACKED_CHANNEL,
    ChannelMode,
    SimulatedGpd,
    TrackingMode,
)
from benchtools.instruments.gpd3303d.simulator import SimulatedChannel


def ask(simulator, command):
    """Send one command line and return the decoded reply, or None."""
    reply = simulator.respond(command.encode("ascii"))
    return None if reply is None else reply.decode("ascii").strip()


def status_bits(simulator):
    """The eight ``STATUS?`` fields, without the legend that follows them."""
    return "".join(ask(simulator, "STATUS?").split("\r")[0].split())


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

    def test_a_de_energised_channel_reports_constant_current(self):
        """As a real supply does with its output switch open."""
        channel = SimulatedChannel()
        channel.voltage_setpoint = 5.0
        assert channel.output(False)["mode"] == ChannelMode.CONSTANT_CURRENT


class TestCommands:
    def test_idn(self, ):
        assert ask(SimulatedGpd(), "*IDN?").startswith("GW INSTEK,GPD-3303D")

    def test_setting_and_reading_back(self):
        simulator = SimulatedGpd()
        assert ask(simulator, "VSET1:3.300") is None
        assert ask(simulator, "VSET1?") == "3.3V"
        assert ask(simulator, "ISET1:0.500") is None
        assert ask(simulator, "ISET1?") == "0.50A"

    def test_read_back_is_coarser_than_programming(self):
        """0.1 V and 0.01 A, as firmware V1.09 answers."""
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:3.250")
        ask(simulator, "ISET1:0.123")
        assert ask(simulator, "VSET1?") in ("3.2V", "3.3V")
        assert ask(simulator, "ISET1?") == "0.12A"

    def test_measurements_carry_their_unit(self):
        """As the instrument's do, which is what the driver has to strip."""
        simulator = SimulatedGpd(load_ohms={1: 10.0})
        ask(simulator, "VSET1:3.300")
        ask(simulator, "ISET1:1.000")
        ask(simulator, "OUT1")
        assert ask(simulator, "VOUT1?") == "3.3V"
        assert ask(simulator, "IOUT1?") == "0.33A"

    def test_the_output_switch_is_one_switch(self):
        """Which is the whole reason the driver emulates per-channel control."""
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:1.000")
        ask(simulator, "VSET2:2.000")
        ask(simulator, "OUT1")
        assert ask(simulator, "VOUT1?") == "1.0V"
        assert ask(simulator, "VOUT2?") == "2.0V"
        ask(simulator, "OUT0")
        assert ask(simulator, "VOUT1?") == "0.0V"
        assert ask(simulator, "VOUT2?") == "0.0V"

    def test_out0_is_understood(self):
        """It shares its digit position with a channel number, and an earlier
        version of this simulator quietly refused it."""
        simulator = SimulatedGpd()
        ask(simulator, "OUT1")
        assert simulator.output is True
        ask(simulator, "OUT0")
        assert simulator.output is False
        assert simulator.last_error == ""

    def test_status_is_eight_fields_then_the_legend(self):
        """As firmware V1.09 answers: spaced fields, ``X`` for bits 5 and 7,
        then two lines of legend, every line ending in a carriage return."""
        reply = SimulatedGpd().respond(b"STATUS?").decode("ascii")
        lines = reply.split("\r")
        assert lines[-1] == ""
        fields = lines[0].split(" ")
        assert len(fields) == 8
        assert set(fields) <= {"0", "1", "X"}
        assert fields[5] == fields[7] == "X"
        assert [line[:4] for line in lines[1:-1]] == ["bit0", "bit4"]

    def test_the_output_is_bit_6(self):
        """Confirmed on a real supply by switching its output."""
        simulator = SimulatedGpd()
        assert status_bits(simulator)[6] == "0"
        ask(simulator, "OUT1")
        assert status_bits(simulator)[6] == "1"

    def test_the_supply_clamps_rather_than_refusing(self):
        """Which is exactly what the driver's range check protects against."""
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:35.000")
        assert ask(simulator, "VSET1?") == "30.0V"
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
        """A carriage return alone, as a real supply ends them: a driver
        waiting for a line feed never sees one."""
        reply = SimulatedGpd().respond(b"*IDN?")
        assert reply.endswith(b"\r")
        assert b"\n" not in reply

    def test_a_load_can_be_attached_after_construction(self):
        simulator = SimulatedGpd()
        simulator.set_load(1, 5.0)
        ask(simulator, "VSET1:5.000")
        ask(simulator, "ISET1:3.000")
        ask(simulator, "OUT1")
        assert ask(simulator, "IOUT1?") == "1.00A"

    def test_reset_returns_it_to_power_on(self):
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:5.000")
        ask(simulator, "OUT1")
        simulator.reset()
        assert simulator.output is False
        assert ask(simulator, "VSET1?") == "0.0V"

    def test_every_command_is_logged(self):
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:1.000")
        ask(simulator, "OUT1")
        assert simulator.command_log == ["VSET1:1.000", "OUT1"]


class TestTracking:
    """Series and parallel tracking, which is where channel 2 stops being a
    channel: the supply drives it from channel 1 and discards what is sent to
    it. The driver refuses to send it - these assert the behaviour that makes
    the refusal worth having."""

    def test_it_starts_independent(self):
        assert SimulatedGpd().tracking == TrackingMode.INDEPENDENT

    @pytest.mark.parametrize(
        "command,mode",
        [
            ("TRACK0", TrackingMode.INDEPENDENT),
            ("TRACK1", TrackingMode.SERIES),
            ("TRACK2", TrackingMode.PARALLEL),
        ],
    )
    def test_the_mode_can_be_set(self, command, mode):
        simulator = SimulatedGpd()
        ask(simulator, command)
        assert simulator.tracking == mode

    def test_a_mode_that_does_not_exist_is_refused(self):
        simulator = SimulatedGpd()
        ask(simulator, "TRACK9")
        assert simulator.tracking == TrackingMode.INDEPENDENT
        assert "no tracking mode" in simulator.last_error

    @pytest.mark.parametrize("mode", [TrackingMode.SERIES, TrackingMode.PARALLEL])
    def test_the_slaved_channel_is_discarded_silently(self, mode):
        """No error, no reply, no change: the supply's silence is exactly what
        makes this dangerous, so the model must be silent too."""
        simulator = SimulatedGpd(tracking=mode)
        ask(simulator, "VSET1:5.000")
        assert ask(simulator, "VSET%d:1.000" % TRACKED_CHANNEL) is None
        assert ask(simulator, "VSET%d?" % TRACKED_CHANNEL) == "5.0V"
        assert simulator.last_error == ""

    @pytest.mark.parametrize("mode", [TrackingMode.SERIES, TrackingMode.PARALLEL])
    def test_the_slaved_channel_follows_channel_1(self, mode):
        simulator = SimulatedGpd(tracking=mode)
        ask(simulator, "VSET1:5.000")
        ask(simulator, "ISET1:0.500")
        assert ask(simulator, "VSET%d?" % TRACKED_CHANNEL) == "5.0V"
        assert ask(simulator, "ISET%d?" % TRACKED_CHANNEL) == "0.50A"

    def test_switching_to_tracking_brings_the_slaved_channel_with_it(self):
        simulator = SimulatedGpd()
        ask(simulator, "VSET1:5.000")
        ask(simulator, "VSET2:1.000")
        ask(simulator, "TRACK1")
        assert ask(simulator, "VSET%d?" % TRACKED_CHANNEL) == "5.0V"

    @pytest.mark.parametrize(
        "mode,bits",
        [
            (TrackingMode.INDEPENDENT, "01"),
            (TrackingMode.SERIES, "11"),
            (TrackingMode.PARALLEL, "10"),
        ],
    )
    def test_the_status_word_carries_the_mode(self, mode, bits):
        """Bits 2 and 3, bit 2 first, as the supply's own legend writes them:
        a real supply in independent reports bit 2 clear and bit 3 set."""
        simulator = SimulatedGpd(tracking=mode)
        assert status_bits(simulator)[2:4] == bits

    def test_an_unmodelled_mode_reports_an_undocumented_pattern(self):
        """Not a comfortable default: a state the model cannot describe must
        look undescribable to the driver, or the driver's handling of one is
        never exercised."""
        simulator = SimulatedGpd(tracking="something else entirely")
        assert status_bits(simulator)[2:4] == "00"

    def test_a_reset_does_not_move_the_switch(self):
        """On the supply the mode is a front-panel switch; a power cycle does
        not move it."""
        simulator = SimulatedGpd(tracking=TrackingMode.SERIES)
        simulator.reset()
        assert simulator.tracking == TrackingMode.SERIES
