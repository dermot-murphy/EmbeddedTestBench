"""The GPD-3303D driver.

The tests are organised around the four ways this supply can make a test lie:
a value it rejects silently, a channel in current limit that is not at the
voltage it was asked for, an output switch that is global while the API looks
per-channel, and a tracking mode in which channel 2 is not its own channel at
all.

Traces to: PSU-FR-001 .. PSU-FR-050, SWE4-UT-PSU.
"""

from __future__ import annotations

import dataclasses

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError, ProtocolError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.gpd3303d import (
    CHANNELS,
    MAX_CURRENT,
    MAX_VOLTAGE,
    TRACKED_CHANNEL,
    ChannelMode,
    ChannelReading,
    Gpd3303D,
    SimulatedGpd,
    TrackingMode,
)
from benchtools.instruments.gpd3303d.constants import VOLTAGE_READBACK_RESOLUTION

from .conftest import HEAVY_LOAD_OHMS, LIGHT_LOAD_OHMS


class TestConnection:
    def test_identity(self, psu):
        identity = psu.identify()
        assert identity.manufacturer == "GW INSTEK"
        assert identity.model == "GPD-3303D"
        assert identity.firmware == "V1.09"

    def test_the_serial_number_loses_its_label(self, psu):
        """The instrument sends "SN:EW000000"; the number is the number."""
        assert psu.serial_number == "SIM00000"

    def test_a_bare_port_name_is_a_serial_port(self):
        """COM4 must not be parsed as a network host, which is the sensible
        default everywhere else and wrong here."""
        assert Gpd3303D._normalise_resource("COM4") == "serial://COM4"
        assert Gpd3303D._normalise_resource("/dev/ttyUSB0") == "serial:///dev/ttyUSB0"

    @pytest.mark.parametrize(
        "resource,expected",
        [("sim://", "sim://"), ("", "sim://"), ("sim", "sim"),
         ("serial://COM4:57600", "serial://COM4:57600"),
         ("socket://terminal:4002", "socket://terminal:4002")],
    )
    def test_resource_forms(self, resource, expected):
        assert Gpd3303D._normalise_resource(resource) == expected

    def test_connect_through_the_factory(self):
        with Gpd3303D.connect("sim://") as psu:
            assert psu.model == "GPD-3303D"

    def test_connecting_changes_nothing(self, simulator):
        """A supply powering a board must not be disturbed by a driver
        attaching to it."""
        simulator.channels[1].voltage_setpoint = 5.0
        simulator.channels[1].current_limit = 1.0
        simulator.output = True
        before = list(simulator.command_log)

        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()

        assert simulator.channels[1].voltage_setpoint == 5.0
        assert simulator.output is True
        written = [line for line in simulator.command_log[len(before):] if "?" not in line]
        assert written == [], "connecting wrote %s" % written
        instrument.close()

    def test_it_knows_the_output_was_already_on(self, simulator):
        """Otherwise the driver's first output_off would park a live rail
        without remembering what it had been set to."""
        simulator.channels[1].voltage_setpoint = 5.0
        simulator.output = True
        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()
        assert instrument.is_output_on(1) is True
        instrument.close()

    def test_it_is_not_a_scpi_instrument_beyond_idn(self, psu):
        """No *CLS on connect: this supply does not know the command."""
        assert "*CLS" not in psu.transport.responder.command_log


class TestSetting:
    def test_voltage(self, psu):
        assert psu.set_voltage(1, 3.3) == 3.3
        assert psu.voltage_setpoint(1) == 3.3

    def test_current_limit(self, psu):
        assert psu.set_current_limit(2, 0.25) == 0.25
        assert psu.current_limit(2) == 0.25

    def test_the_setpoint_read_back_agrees_to_the_read_back_resolution(self, psu):
        """The supply programs to 1 mV and reads back to 0.1 V, so a setpoint
        read back agrees with the one sent only to that resolution."""
        for wanted in (0.0, 1.234, 3.3, 12.5, MAX_VOLTAGE):
            assert psu.set_voltage(1, wanted) == pytest.approx(
                psu.voltage_setpoint(1), abs=VOLTAGE_READBACK_RESOLUTION / 2 + 1e-9)

    def test_a_value_between_steps_is_rounded_as_the_supply_rounds_it(self, psu):
        assert psu.set_voltage(1, 3.30049) == 3.3
        assert psu.set_current_limit(1, 0.12345) == 0.123

    @pytest.mark.parametrize("volts", [-0.1, MAX_VOLTAGE + 0.001, 35.0])
    def test_an_impossible_voltage_is_refused_before_it_is_sent(self, psu, volts):
        """The supply rejects it silently, which is the dangerous case: no
        reply, the previous setpoint kept, and only ERR? - which is not polled
        by default - saying so."""
        with pytest.raises(ConfigurationError, match="reject"):
            psu.set_voltage(1, volts)
        assert not any(
            line.startswith("VSET") and ":" in line
            for line in psu.transport.responder.command_log
        )

    @pytest.mark.parametrize("amps", [-0.5, MAX_CURRENT + 0.001])
    def test_an_impossible_current_limit_is_refused(self, psu, amps):
        with pytest.raises(ConfigurationError, match="reject"):
            psu.set_current_limit(1, amps)

    @pytest.mark.parametrize("channel", [0, 3, -1, "one"])
    def test_a_channel_that_does_not_exist_is_named(self, psu, channel):
        with pytest.raises(ConfigurationError, match="channels 1 and 2"):
            psu.set_voltage(channel, 1.0)

    def test_configure_sets_the_limit_before_the_voltage(self, psu):
        """A channel coming up at a new voltage must never be protected by the
        previous test's current limit, even for a moment."""
        psu.configure_channel(1, volts=5.0, current_limit=0.2)
        written = [line for line in psu.transport.responder.command_log if ":" in line]
        assert written.index("ISET1:0.200") < written.index("VSET1:5.000")

    def test_configure_can_switch_on_and_reads_back(self, loaded):
        reading = loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        assert reading.is_on is True
        assert reading.voltage == pytest.approx(3.3)


class TestMeasuring:
    def test_an_unloaded_channel(self, psu):
        psu.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        assert psu.measure_voltage(1) == pytest.approx(3.3)
        assert psu.measure_current(1) == pytest.approx(0.0)

    def test_a_loaded_channel_draws_what_ohm_s_law_says(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        assert loaded.measure_current(1) == pytest.approx(3.3 / LIGHT_LOAD_OHMS, abs=1e-3)

    def test_a_switched_off_supply_measures_zero(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=False)
        assert loaded.measure_voltage(1) == 0.0

    def test_the_unit_suffix_is_not_mistaken_for_a_number(self, psu):
        """VOUT answers "3.300V" and ISET answers "0.500"; both are numbers."""
        assert Gpd3303D._parse_reading("3.300V", "VOUT1?") == 3.3
        assert Gpd3303D._parse_reading("0.500A", "IOUT1?") == 0.5
        assert Gpd3303D._parse_reading(" 12.000 ", "VSET1?") == 12.0

    def test_a_reply_that_is_not_a_number_is_reported_with_the_command(self, psu):
        with pytest.raises(ProtocolError, match="VOUT1"):
            Gpd3303D._parse_reading("OVERLOAD", "VOUT1?")

    def test_power_is_derived_from_both_readings(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        assert loaded.measure_power(1) == pytest.approx(3.3 * 3.3 / LIGHT_LOAD_OHMS, abs=1e-3)

    def test_read_channel_gathers_everything_at_once(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        reading = loaded.read_channel(1)
        assert reading.channel == 1
        assert reading.voltage == pytest.approx(3.3)
        assert reading.current == pytest.approx(0.33, abs=1e-3)
        assert reading.mode == ChannelMode.CONSTANT_VOLTAGE
        assert reading.voltage_setpoint == 3.3
        assert reading.current_limit == 0.5
        assert reading.is_on is True

    def test_read_all_covers_every_channel(self, psu):
        assert [reading.channel for reading in psu.read_all()] == list(CHANNELS)


class TestCurrentLimit:
    """A channel in CC is not delivering the voltage the test asked for.

    This is the failure that looks like a measurement: the board browns out,
    the rail sits wherever the load puts it, and nothing in a bare voltage
    reading says the supply stopped doing what it was told.
    """

    def test_a_heavy_load_puts_the_channel_into_constant_current(self, loaded):
        loaded.configure_channel(2, volts=3.3, current_limit=0.5, output=True)
        reading = loaded.read_channel(2)
        assert reading.mode == ChannelMode.CONSTANT_CURRENT
        assert reading.in_current_limit is True

    def test_the_rail_is_below_its_setpoint_there(self, loaded):
        loaded.configure_channel(2, volts=3.3, current_limit=0.5, output=True)
        reading = loaded.read_channel(2)
        assert reading.current == pytest.approx(0.5, abs=1e-3)
        assert reading.voltage == pytest.approx(0.5 * HEAVY_LOAD_OHMS, abs=1e-3)
        assert reading.voltage < reading.voltage_setpoint

    def test_regulated_is_the_question_a_test_actually_means(self, loaded):
        """Energised, in constant voltage, and at the setpoint - all three.

        Channel 2's load takes it into CC, so it is energised and reading a
        perfectly plausible voltage that is not the one it was set to.
        """
        loaded.configure_channel(1, volts=3.3, current_limit=0.5)
        loaded.configure_channel(2, volts=3.3, current_limit=0.5)
        loaded.all_outputs_on()
        assert loaded.read_channel(1).regulated is True
        assert loaded.read_channel(2).regulated is False

    def test_a_channel_that_is_off_is_not_in_current_limit(self, psu):
        """A real supply reports CC for both channels while its output is
        off. That is not a board drawing too much current."""
        reading = psu.read_channel(1)
        assert reading.mode == ChannelMode.CONSTANT_CURRENT
        assert reading.in_current_limit is False

    def test_regulated_allows_for_the_read_back_resolution(self):
        """Seen on a real supply: set to 3.600 V, unloaded, it reads back a
        setpoint of 3.6 V and measures 3.5 V. That channel is regulating."""
        reading = ChannelReading(
            channel=1, voltage=3.5, current=0.0, mode=ChannelMode.CONSTANT_VOLTAGE,
            is_on=True, voltage_setpoint=3.6, current_limit=0.8)
        assert reading.regulated is True
        assert dataclasses.replace(reading, voltage=3.3).regulated is False

    def test_raising_the_limit_restores_constant_voltage(self, loaded):
        loaded.configure_channel(2, volts=3.3, current_limit=0.5, output=True)
        loaded.set_current_limit(2, 2.0)
        reading = loaded.read_channel(2)
        assert reading.mode == ChannelMode.CONSTANT_VOLTAGE
        assert reading.voltage == pytest.approx(3.3)

    def test_channel_mode_can_be_asked_for_on_its_own(self, loaded):
        loaded.configure_channel(2, volts=3.3, current_limit=0.5, output=True)
        assert loaded.channel_mode(2) == ChannelMode.CONSTANT_CURRENT
        assert loaded.channel_mode(1) == ChannelMode.CONSTANT_VOLTAGE


class TestOutputSwitching:
    """The switch is global; the API is per-channel. That gap is the risk."""

    def test_switching_a_channel_on_energises_it(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5)
        loaded.output_on(1)
        assert loaded.is_output_on(1) is True
        assert loaded.measure_voltage(1) == pytest.approx(3.3)

    def test_switching_a_channel_off_parks_it_at_zero_volts(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.output_off(1)
        assert loaded.measure_voltage(1) == 0.0
        assert loaded.is_output_on(1) is False

    def test_the_setpoint_survives_being_switched_off(self, loaded):
        """The channel is at 0 V; what the test asked for is still 3.3 V."""
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.output_off(1)
        assert loaded.voltage_setpoint(1) == 3.3
        loaded.output_on(1)
        assert loaded.measure_voltage(1) == pytest.approx(3.3)

    def test_the_current_limit_is_not_parked(self, loaded):
        """It is the protection for whatever is connected, on or off."""
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.output_off(1)
        assert loaded.current_limit(1) == 0.5

    def test_one_channel_off_leaves_the_other_running(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5)
        loaded.configure_channel(2, volts=5.0, current_limit=3.0)
        loaded.all_outputs_on()
        loaded.output_off(1)
        assert loaded.measure_voltage(1) == 0.0
        assert loaded.measure_voltage(2) == pytest.approx(5.0)
        assert loaded.output is True

    def test_the_last_channel_off_opens_the_real_switch(self, loaded):
        """"All off" should mean what it says, not two rails at 0 V."""
        loaded.configure_channel(1, volts=3.3, current_limit=0.5)
        loaded.configure_channel(2, volts=5.0, current_limit=3.0)
        loaded.all_outputs_on()
        loaded.output_off(1)
        assert loaded.output is True
        loaded.output_off(2)
        assert loaded.output is False
        assert "OUT0" in loaded.transport.responder.command_log

    def test_setting_a_voltage_on_a_parked_channel_does_not_energise_it(self, loaded):
        """Otherwise set_voltage would be a way to switch a rail on by
        accident, which is not what it is for."""
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.output_off(1)
        loaded.set_voltage(1, 5.0)
        assert loaded.measure_voltage(1) == 0.0
        assert loaded.voltage_setpoint(1) == 5.0

    def test_and_that_new_setpoint_is_what_comes_up(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.output_off(1)
        loaded.set_voltage(1, 5.0)
        loaded.output_on(1)
        assert loaded.measure_voltage(1) == pytest.approx(5.0)

    def test_set_output_is_the_same_thing_either_way(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5)
        loaded.set_output(1, True)
        assert loaded.is_output_on(1) is True
        loaded.set_output(1, False)
        assert loaded.is_output_on(1) is False

    def test_all_outputs_off_really_switches_off(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.all_outputs_off()
        assert loaded.output is False
        assert loaded.measure_voltage(1) == 0.0

    def test_all_outputs_on_restores_every_parked_channel(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.configure_channel(2, volts=5.0, current_limit=3.0)
        loaded.all_outputs_off()
        loaded.all_outputs_on()
        assert loaded.measure_voltage(1) == pytest.approx(3.3)
        assert loaded.measure_voltage(2) == pytest.approx(5.0)


class TestStatus:
    def test_it_decodes_the_documented_bits(self, psu):
        status = psu.status()
        assert status.tracking == TrackingMode.INDEPENDENT
        assert status.beep is True
        assert status.output is False

    def test_the_raw_reply_is_kept(self, psu):
        """The bit order is the one thing that cannot be settled without the
        instrument in front of you (PSU-OPEN-01), so the evidence is kept."""
        status = psu.status()
        assert status.raw == "0 0 0 1 1 X 0 X"

    def test_a_real_supply_s_reply_decodes(self, simulator):
        """Captured from a GPD-3303D, firmware V1.09, in independent tracking
        with its output switched on and nothing connected."""
        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()
        simulator._cmd_status_q = lambda *_: "\r".join(
            ("1 1 0 1 0 X 1 X",) + SimulatedGpd.STATUS_LEGEND)
        status = instrument.status()
        assert status.modes == (ChannelMode.CONSTANT_VOLTAGE,) * 2
        assert status.tracking == TrackingMode.INDEPENDENT
        assert status.beep is False
        assert status.output is True
        instrument.close()

    def test_the_legend_is_not_taken_as_the_next_reply(self, psu):
        psu.status()
        assert psu.identify().model == "GPD-3303D"

    def test_the_compact_form_is_accepted_too(self, simulator):
        """Eight characters with nothing between them, as the manual prints
        the reply: no legend follows, and none is waited for."""
        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()
        simulator._cmd_status_q = lambda *_: "11010X1X"
        status = instrument.status()
        assert status.tracking == TrackingMode.INDEPENDENT
        assert status.output is True
        instrument.close()

    def test_the_output_bit_follows_the_output(self, psu):
        assert psu.status().output is False
        psu.all_outputs_on()
        assert psu.status().output is True

    def test_the_mode_bits_follow_the_load(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5)
        loaded.configure_channel(2, volts=3.3, current_limit=0.5)
        loaded.all_outputs_on()
        status = loaded.status()
        assert status.mode(1) == ChannelMode.CONSTANT_VOLTAGE
        assert status.mode(2) == ChannelMode.CONSTANT_CURRENT

    def test_a_short_reply_blames_the_line_rate(self, simulator):
        """Which is what it almost always is, and is worth saying rather than
        decoding four characters into a confident wrong answer."""
        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()
        simulator._cmd_status_q = lambda *_: "1010"
        with pytest.raises(ProtocolError, match="line rate"):
            instrument.status()
        instrument.close()

    def test_as_dict_is_assertable_by_a_specification(self, psu):
        psu.all_outputs_on()
        summary = psu.status().as_dict()
        assert summary["modes"][1] == ChannelMode.CONSTANT_VOLTAGE
        psu.all_outputs_off()
        summary = psu.status().as_dict()
        assert summary["output"] is False


class TestErrors:
    def test_a_clean_supply_reports_nothing(self, psu):
        assert psu.read_event_queue() == []

    def test_a_complaint_is_carried_verbatim(self, psu, simulator):
        """The exact wording is a confirmation item, so it is reported rather
        than parsed into a code that might be wrong."""
        simulator.last_error = 'Command Error, "VSET3:1.000"'
        events = psu.read_event_queue()
        assert events and "VSET3" in events[0][1]

    def test_reading_it_clears_it(self, psu, simulator):
        simulator.last_error = "Data Out of Range"
        assert psu.read_event_queue()
        assert psu.read_event_queue() == []

    def test_checking_errors_raises_with_what_the_supply_said(self, psu, simulator):
        simulator.last_error = "Data Out of Range"
        with pytest.raises(InstrumentError, match="Data Out of Range"):
            psu.check_errors()

    def test_error_checking_is_off_by_default(self, psu):
        """At 9600 baud a poll after every command doubles the time of a sweep,
        and this supply's range checking is done in the driver instead."""
        assert psu.auto_check_errors is False

    def test_it_can_be_turned_on(self, simulator):
        simulator.last_error = "Data Out of Range"
        instrument = Gpd3303D(MockTransport(responder=simulator),
                              auto_check_errors=True, command_interval=0.0)
        instrument.initialise()
        with pytest.raises(InstrumentError):
            instrument.set_voltage(1, 1.0)
        instrument.close()


class TestPacing:
    def test_a_simulated_link_is_not_paced(self, psu):
        """Otherwise every test would pay 50 ms per command for a buffer that
        does not exist."""
        assert psu._command_interval == 0.0

    @pytest.mark.parametrize(
        "description,paced",
        [("serial:///dev/ttyUSB0", True), ("serial://COM4:9600", True),
         ("socket://terminal-server:4002", True),
         ("simulated GPD-3303D", False), ("serial://loop://", False)],
    )
    def test_which_links_are_paced(self, description, paced):
        interval = Gpd3303D._default_command_interval(description)
        assert (interval > 0.0) is paced

    def test_the_interval_can_be_set(self):
        instrument = Gpd3303D(MockTransport(responder=SimulatedGpd()), command_interval=0.2)
        assert instrument._command_interval == 0.2

    def test_it_waits_between_commands(self, simulator):
        import time

        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.02)
        instrument.initialise()
        started = time.monotonic()
        for _ in range(3):
            instrument.set_voltage(1, 1.0)
        assert time.monotonic() - started >= 0.035
        instrument.close()


class TestReset:
    def test_it_switches_off_and_zeroes_the_rails(self, loaded):
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.reset(settle=0.0)
        assert loaded.output is False
        assert loaded.voltage_setpoint(1) == 0.0

    def test_it_leaves_the_current_limits_alone(self, loaded):
        """They are the protection the operator set for the board that is
        connected; a reset that raised them would be the opposite of safe."""
        loaded.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
        loaded.reset(settle=0.0)
        assert loaded.current_limit(1) == 0.5

    def test_it_sends_no_rst(self, loaded):
        """The supply does not know the command; sending it would be answered
        with silence and a timeout."""
        loaded.reset(settle=0.0)
        assert "*RST" not in loaded.transport.responder.command_log


class TestTracking:
    """Channel 2 while the supply is slaving it to channel 1.

    The supply takes ``VSET2:`` in series or parallel tracking, does nothing
    with it, and reports nothing. Every test here is about the driver refusing
    to be the component that turns that silence into a number.

    Traces to: PSU-FR-006.
    """

    @pytest.fixture(params=[TrackingMode.SERIES, TrackingMode.PARALLEL])
    def tracking(self, request) -> str:
        return request.param

    @pytest.fixture
    def tracked(self, tracking) -> Gpd3303D:
        """A supply whose front panel is in series or parallel tracking."""
        simulator = SimulatedGpd(tracking=tracking)
        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()
        yield instrument
        instrument.close()

    def test_the_supply_really_does_discard_the_setpoint(self, tracking):
        """The premise. If the simulated supply accepted VSET2 while tracking,
        every test below would be asserting a rule that protects nothing."""
        simulator = SimulatedGpd(tracking=tracking)
        simulator.respond(b"VSET1:5.000")
        simulator.respond(b"VSET2:1.000")
        assert simulator.channels[TRACKED_CHANNEL].voltage_setpoint == 5.0
        assert simulator.last_error == "", "the supply reports no error either"

    def test_a_voltage_is_refused(self, tracked, tracking):
        with pytest.raises(ConfigurationError, match=tracking):
            tracked.set_voltage(TRACKED_CHANNEL, 3.3)

    def test_a_current_limit_is_refused(self, tracked, tracking):
        with pytest.raises(ConfigurationError, match=tracking):
            tracked.set_current_limit(TRACKED_CHANNEL, 0.5)

    def test_the_refusal_says_what_to_do_instead(self, tracked):
        with pytest.raises(ConfigurationError, match="independent"):
            tracked.set_voltage(TRACKED_CHANNEL, 3.3)

    def test_nothing_was_sent(self, tracked):
        """A refusal that still writes is worse than no refusal: the setpoint
        is discarded by the supply and the driver has raised about it."""
        with pytest.raises(ConfigurationError):
            tracked.set_voltage(TRACKED_CHANNEL, 3.3)
        assert not any(
            line.startswith("VSET%d:" % TRACKED_CHANNEL)
            for line in tracked.transport.responder.command_log
        )

    def test_a_parked_channel_is_refused_too(self, tracked):
        """Parking would record a setpoint the hardware can never honour."""
        tracked.set_voltage(1, 1.0)
        with pytest.raises(ConfigurationError):
            tracked.output_off(TRACKED_CHANNEL)
        with pytest.raises(ConfigurationError):
            tracked.set_voltage(TRACKED_CHANNEL, 3.3)

    def test_switching_the_slaved_channel_is_refused(self, tracked):
        """The per-channel switch is emulated by programming the channel to
        zero volts, so it is discarded exactly as a setpoint is."""
        with pytest.raises(ConfigurationError):
            tracked.output_off(TRACKED_CHANNEL)
        with pytest.raises(ConfigurationError):
            tracked.output_on(TRACKED_CHANNEL)

    def test_channel_1_is_unaffected(self, tracked):
        """It is the master in both modes; refusing it would be a driver that
        cannot use a supply in tracking at all."""
        assert tracked.set_voltage(1, 5.0) == 5.0
        assert tracked.set_current_limit(1, 0.5) == 0.5

    def test_the_slaved_channel_follows_channel_1(self, tracked):
        tracked.set_voltage(1, 5.0)
        assert tracked.voltage_setpoint(TRACKED_CHANNEL) == 5.0

    def test_the_global_switch_still_works(self, tracked):
        """A safe state must be reachable in every mode."""
        tracked.set_voltage(1, 5.0)
        tracked.all_outputs_on()
        assert tracked.output is True
        tracked.all_outputs_off()
        assert tracked.output is False

    def test_reset_still_works(self, tracked):
        tracked.set_voltage(1, 5.0)
        tracked.all_outputs_on()
        tracked.reset(settle=0.0)
        assert tracked.output is False
        assert tracked.voltage_setpoint(1) == 0.0
        assert tracked.voltage_setpoint(TRACKED_CHANNEL) == 0.0

    def test_the_mode_is_reported(self, tracked, tracking):
        assert tracked.tracking == tracking
        assert tracked.status().tracking == tracking

    def test_independent_is_not_refused(self, psu):
        assert psu.tracking == TrackingMode.INDEPENDENT
        assert psu.set_voltage(TRACKED_CHANNEL, 3.3) == 3.3

    def test_the_mode_is_re_read_for_every_setting(self, tracked):
        """It is a front-panel switch: it can move between two commands, and a
        cached answer would be a guess about hardware nobody was watching."""
        with pytest.raises(ConfigurationError):
            tracked.set_voltage(TRACKED_CHANNEL, 3.3)
        tracked.transport.responder.respond(b"TRACK0")
        assert tracked.set_voltage(TRACKED_CHANNEL, 3.3) == 3.3

    def test_an_undecodable_mode_warns_and_allows(self, psu, caplog):
        """The status bit order is a bench confirmation item (PSU-OPEN-01).
        Refusing on a pattern we do not recognise would turn one unverified bit
        into a driver that cannot set anything at all - so it warns instead."""
        psu.transport.responder.tracking = "a mode this driver has no name for"
        assert psu.status().tracking == TrackingMode.UNKNOWN
        with caplog.at_level("WARNING"):
            assert psu.set_voltage(TRACKED_CHANNEL, 3.3) == 3.3
        assert "tracking mode did not decode" in caplog.text
