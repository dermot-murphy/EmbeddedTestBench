"""The TTi 1604 driver against its simulator.

Traces to: DMM-FR-001 .. DMM-FR-050, DMM-FR-070, DMM-NFR-002, SWE4-UT-DMM.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import (
    ConfigurationError,
    InstrumentError,
    MeasurementError,
    ProtocolError,
)
from benchtools.core.transport.mock import MockTransport
from benchtools.core.transport.serial_port import SerialTransport
from benchtools.instruments.tti1604 import (
    CURRENT_FUNCTIONS,
    Function,
    Key,
    SimulatedTti1604,
    Tti1604,
)
from benchtools.instruments.tti1604.constants import ECHO_TIMEOUT, SEND_ATTEMPTS


class TestConnecting:
    def test_connecting_puts_the_meter_in_remote_mode(self, dmm, simulator):
        assert simulator.remote is True
        assert simulator.key_log == [Key.REMOTE]

    def test_connecting_changes_nothing_on_the_front_panel(self, simulator):
        """DMM-FR-004: only the remote key is pressed."""
        simulator.function = Function.AC_VOLTS
        simulator.auto_range = False
        instrument = Tti1604(MockTransport(responder=simulator))
        instrument.initialise()
        assert simulator.key_log == [Key.REMOTE]
        assert simulator.function == Function.AC_VOLTS
        assert simulator.auto_range is False
        assert instrument.last_reading.function == Function.AC_VOLTS
        instrument.close()

    def test_the_identity_is_asserted_and_invents_nothing(self, dmm):
        identity = dmm.identify()
        assert identity.manufacturer == "THURLBY THANDAR"
        assert identity.model == "1604"
        assert identity.serial_number == ""
        assert identity.firmware == ""

    def test_a_meter_in_standby_is_diagnosed(self, simulator):
        simulator.operating = False
        instrument = Tti1604(MockTransport(responder=simulator))
        with pytest.raises(InstrumentError, match="Operate"):
            instrument.initialise()

    def test_closing_hands_the_meter_back_to_its_front_panel(self, simulator):
        instrument = Tti1604(MockTransport(responder=simulator))
        instrument.initialise()
        instrument.close()
        assert simulator.remote is False
        assert simulator.key_log[-1] == Key.LOCAL

    def test_closing_a_meter_that_has_gone_silent_does_not_raise(self, dmm, simulator):
        simulator.drop_keys = 100
        dmm.close()                                     # DMM-FR-006
        assert not dmm.is_open

    def test_connect_over_the_simulator(self):
        with Tti1604.connect("sim://") as instrument:
            assert instrument.model == "1604"

    def test_bench_options_for_other_drivers_are_ignored(self):
        instrument = Tti1604.connect("sim://", baudrate=115200, device="x")
        instrument.close()


class TestTheLink:
    @pytest.mark.parametrize(
        "resource,expected",
        [
            ("COM6", "serial://COM6"),
            ("/dev/ttyUSB1", "serial:///dev/ttyUSB1"),
            ("serial://COM6", "serial://COM6"),
            ("sim://", "sim://"),
            ("", "sim://"),
        ],
    )
    def test_a_bare_port_name_is_a_serial_port(self, resource, expected):
        assert Tti1604._normalise_resource(resource) == expected

    def test_the_line_settings_are_the_meters(self):
        """DMM-FR-001: 9600 8N1, DTR asserted and RTS negated to power it."""
        pytest.importorskip("serial")
        instrument = Tti1604.connect("serial://loop://", initialise=False)
        transport = instrument.transport
        assert isinstance(transport, SerialTransport)
        assert transport.baudrate == 9600
        assert transport.dtr is True
        assert transport.rts is False


class TestKeys:
    def test_a_key_is_acknowledged_by_its_echo(self, dmm, simulator):
        assert dmm.press(Key.AUTO) == 1
        assert simulator.key_log[-1] == Key.AUTO

    def test_a_lost_key_is_resent(self, dmm, simulator):
        simulator.drop_keys = 2
        assert dmm.press(Key.AUTO) == 3
        assert simulator.key_log[-1] == Key.AUTO

    def test_a_key_is_resent_after_300_ms_not_sooner(self, dmm, simulator):
        simulator.drop_keys = 1
        before = simulator.clock
        dmm.press(Key.AUTO)
        assert simulator.clock - before >= ECHO_TIMEOUT - 1e-9

    def test_a_meter_that_never_echoes_is_diagnosed(self, dmm, simulator):
        simulator.drop_keys = SEND_ATTEMPTS
        with pytest.raises(ProtocolError, match="DTR") as caught:
            dmm.press(Key.AUTO)
        assert "%d attempt" % SEND_ATTEMPTS in str(caught.value)

    def test_an_echo_is_not_found_inside_a_frame(self, dmm, simulator):
        """DMM-FR-003: the digit 4 is the byte 'f', which is also the Volts key.

        With 4.4444 V on the input every frame carries 'f' bytes; if the
        driver searched inside frames it would take one for the echo of a key
        the meter never received, and not resend it.
        """
        simulator.set_input("dc_volts", 3.4444)          # "3.4444": three 0x66 bytes
        assert 0x66 in simulator.frame()
        simulator.drop_keys = 1
        assert dmm.press(Key.VOLTS) == 2

    def test_an_unknown_key_character_is_refused(self, dmm):
        with pytest.raises(ConfigurationError, match="not a 1604 key"):
            dmm.press("z")


class TestTheStream:
    def test_a_stream_joined_part_way_through_a_frame_resynchronises(self, dmm, simulator):
        simulator.set_input("dc_volts", 1.5)
        simulator.garbage = b"\x0d\x21\x40"             # the tail of a frame, and a CR
        reading = dmm.read(fresh=False)
        assert reading.value == pytest.approx(1.5)

    def test_a_frame_split_across_reads_is_reassembled(self, simulator):
        """A serial port hands over whatever has arrived: often part of a frame."""
        instrument = Tti1604(MockTransport(responder=simulator, chunk_size=3))
        instrument.initialise()
        simulator.set_input("dc_volts", 1.2345)
        assert instrument.measure() == pytest.approx(1.2345)
        instrument.close()

    def test_a_nul_after_each_frame_is_ignored(self, dmm, simulator):
        """DMM-OPEN-01: the note calls the frame null-terminated."""
        simulator.nul_terminated = True
        simulator.set_input("dc_volts", 2.5)
        assert dmm.read_many(3)[-1].value == pytest.approx(2.5)

    def test_a_fresh_reading_skips_what_was_already_waiting(self, dmm, simulator):
        """DMM-FR-030: the reading returned was measured after the request."""
        simulator.set_input("dc_volts", 1.0)
        dmm.read(fresh=False)
        sent = simulator.frames_sent
        simulator.set_input("dc_volts", 2.0)
        reading = dmm.read()
        assert reading.value == pytest.approx(2.0)
        assert simulator.frames_sent - sent == 2       # one skipped, one returned

    def test_a_silent_meter_times_out(self, dmm, simulator):
        simulator.remote = False
        with pytest.raises(MeasurementError, match="no reading"):
            dmm.read()


class TestFunctions:
    @pytest.mark.parametrize(
        "function,keys",
        [
            (Function.AC_VOLTS, [Key.VOLTS, Key.AC]),
            (Function.DC_MILLIVOLTS, [Key.MILLIVOLTS, Key.DC]),
            (Function.AC_MILLIVOLTS, [Key.MILLIVOLTS, Key.AC]),
            (Function.DC_MILLIAMPS, [Key.MILLIAMPS, Key.DC]),
            (Function.AC_MILLIAMPS, [Key.MILLIAMPS, Key.AC]),
            (Function.DC_AMPS, [Key.AMPS, Key.DC]),
            (Function.AC_AMPS, [Key.AMPS, Key.AC]),
            (Function.OHMS, [Key.OHMS]),
        ],
    )
    def test_each_function_is_selected_and_confirmed(self, dmm, simulator, function, keys):
        reading = dmm.select_function(function)
        assert reading.function == function
        assert simulator.function == function
        assert simulator.key_log[1:] == keys

    def test_nothing_is_pressed_for_the_function_already_selected(self, dmm, simulator):
        dmm.select_function(Function.DC_VOLTS)
        assert simulator.key_log == [Key.REMOTE]

    def test_a_key_the_meter_ignores_is_caught_from_the_readings(self, dmm, simulator):
        """DMM-FR-020: the echo is not evidence; the readings are."""
        simulator.ignore_keys = True
        with pytest.raises(ConfigurationError, match="readings show dc_volts"):
            dmm.select_function(Function.OHMS)

    def test_continuity_is_not_selectable(self, dmm):
        with pytest.raises(ConfigurationError, match="cannot select"):
            dmm.select_function(Function.CONTINUITY)

    @pytest.mark.parametrize(
        "function",
        [Function.AC_VOLTS, Function.DC_MILLIVOLTS, Function.OHMS, Function.FREQUENCY],
    )
    def test_no_current_function_is_selected_unless_named(self, dmm, simulator, function):
        """DMM-NFR-002: a current function puts the shunt across the input."""
        dmm.select_function(function)
        assert Key.MILLIAMPS not in simulator.key_log
        assert Key.AMPS not in simulator.key_log
        assert simulator.function not in CURRENT_FUNCTIONS

    def test_frequency_is_selected_from_ac_volts(self, dmm, simulator):
        reading = dmm.select_function(Function.FREQUENCY)
        assert reading.function == Function.FREQUENCY
        assert simulator.key_log[1:] == [Key.VOLTS, Key.AC, Key.HERTZ]

    def test_frequency_keeps_an_ac_current_source(self, dmm, simulator):
        dmm.select_function(Function.AC_MILLIAMPS)
        dmm.select_function(Function.FREQUENCY)
        assert simulator.key_log[-1] == Key.HERTZ
        assert Key.VOLTS not in simulator.key_log


class TestRanges:
    def test_a_range_is_locked_by_its_full_scale(self, dmm, simulator):
        simulator.set_input("dc_volts", 3.3)
        reading = dmm.set_range(400)
        assert reading.range_label == "400 V"
        assert reading.auto_range is False
        assert dmm.measure() == pytest.approx(3.3)

    def test_the_present_range_is_locked_with_auto_man(self, dmm, simulator):
        simulator.set_input("dc_volts", 3.3)
        reading = dmm.set_range(4)
        assert reading.range_label == "4 V"
        assert simulator.key_log[-1] == Key.AUTO

    def test_ranging_down(self, dmm, simulator):
        dmm.set_range(1000)
        assert dmm.set_range(40).range_label == "40 V"

    def test_a_range_the_function_lacks_is_refused_with_the_list(self, dmm):
        with pytest.raises(ConfigurationError, match="4 V .4.*40 V"):
            dmm.set_range(30)

    def test_milliamp_ranges(self, dmm, simulator):
        simulator.set_input("dc_amps", 0.001)
        dmm.select_function(Function.DC_MILLIAMPS)
        assert dmm.set_range(0.4).range_label == "400 mA"
        assert dmm.set_range(4e-3).range_label == "4 mA"

    def test_auto_ranging_is_restored(self, dmm, simulator):
        dmm.set_range(400)
        assert dmm.set_auto_range().auto_range is True
        assert simulator.auto_range is True

    def test_auto_ranging_already_on_presses_nothing(self, dmm, simulator):
        dmm.set_auto_range()
        assert simulator.key_log == [Key.REMOTE]

    def test_a_manual_range_overloads(self, dmm, simulator):
        dmm.set_range(4)
        simulator.set_input("dc_volts", 12.0)
        with pytest.raises(MeasurementError, match="OFL"):
            dmm.measure()

    def test_the_frequency_range_is_the_gate_time(self, dmm, simulator):
        simulator.set_input("frequency", 1234.5)
        dmm.select_function(Function.FREQUENCY)
        reading = dmm.set_range(4000)
        assert reading.gate_10s is True
        assert dmm.measure() == pytest.approx(1234.5)
        assert dmm.set_range(40000).gate_10s is False

    def test_the_ten_second_gate_is_waited_for(self, dmm, simulator):
        """D-41: on the 4 kHz range the meter reads once every 10 s. A wait
        sized for 2.5 readings a second gave up before the first arrived."""
        simulator.set_input("frequency", 50.0)
        dmm.select_function(Function.FREQUENCY)
        before = simulator.clock
        assert dmm.set_range(4000).gate_10s is True
        assert simulator.clock - before >= 10.0
        assert dmm.measure() == pytest.approx(50.0)
        assert dmm.select_function(Function.DC_VOLTS).function == Function.DC_VOLTS

    def test_frequency_has_no_auto_range(self, dmm):
        dmm.select_function(Function.FREQUENCY)
        with pytest.raises(ConfigurationError, match="no auto range"):
            dmm.set_auto_range()


class TestMeasuring:
    def test_dc_voltage(self, dmm, simulator):
        simulator.set_input("dc_volts", -3.3)
        assert dmm.measure_dc_voltage() == pytest.approx(-3.3)

    def test_ac_voltage(self, dmm, simulator):
        simulator.set_input("ac_volts", 230.0)
        assert dmm.measure_ac_voltage() == pytest.approx(230.0)

    def test_dc_current_on_the_milliamp_socket(self, dmm, simulator):
        simulator.set_input("dc_amps", 0.012345)
        assert dmm.measure_dc_current() == pytest.approx(0.01235)   # 10 uA resolution
        assert simulator.function == Function.DC_MILLIAMPS

    def test_a_small_current_autoranges_to_4_ma(self, dmm, simulator):
        simulator.set_input("dc_amps", 0.0012345)
        assert dmm.measure_dc_current() == pytest.approx(0.0012345)
        assert dmm.last_reading.range_label == "4 mA"

    def test_dc_current_on_the_10_amp_socket(self, dmm, simulator):
        simulator.set_input("dc_amps", 2.5)
        assert dmm.measure_dc_current(socket="10A") == pytest.approx(2.5)
        assert simulator.function == Function.DC_AMPS

    def test_ac_current(self, dmm, simulator):
        simulator.set_input("ac_amps", 0.1)
        assert dmm.measure_ac_current() == pytest.approx(0.1)

    def test_an_unknown_socket_is_refused(self, dmm):
        with pytest.raises(ConfigurationError, match="'mA' socket"):
            dmm.measure_dc_current(socket="COM")

    def test_resistance(self, dmm, simulator):
        simulator.set_input("ohms", 4700.0)
        assert dmm.measure_resistance() == pytest.approx(4700.0)

    def test_resistance_with_nothing_connected_is_an_overload(self, dmm):
        with pytest.raises(MeasurementError, match="OFL"):
            dmm.measure_resistance()

    def test_frequency(self, dmm, simulator):
        simulator.set_input("frequency", 50.0)
        assert dmm.measure_frequency() == pytest.approx(50.0)

    def test_frequency_needs_an_ac_source(self, dmm):
        with pytest.raises(ConfigurationError, match="AC function"):
            dmm.measure_frequency(source=Function.DC_VOLTS)

    def test_a_held_reading_is_refused(self, dmm, simulator):
        """DMM-FR-031: Hold freezes the display; it is not a measurement."""
        simulator.panel_status_bits = 0x40
        with pytest.raises(MeasurementError, match="held"):
            dmm.measure()

    def test_a_recalled_minimum_is_refused(self, dmm, simulator):
        simulator.panel_status_bits = 0x10
        with pytest.raises(MeasurementError, match="recalled"):
            dmm.measure()

    def test_a_relative_reading_needs_consent(self, dmm, simulator):
        simulator.panel_function_bits = 0x20
        simulator.set_input("dc_volts", 0.5)
        with pytest.raises(ConfigurationError, match="Null is active"):
            dmm.measure()
        assert dmm.measure(allow_relative=True) == pytest.approx(0.5)

    def test_a_data_log_is_consecutive(self, dmm, simulator):
        simulator.set_input("dc_volts", 1.0)
        readings = dmm.read_many(5)
        assert len(readings) == 5
        stamps = [reading.received_at for reading in readings]
        assert stamps == sorted(stamps)

    def test_a_data_log_needs_a_count(self, dmm):
        with pytest.raises(ConfigurationError):
            dmm.read_many(0)

    def test_the_function_property(self, dmm):
        assert dmm.function == Function.DC_VOLTS
        assert dmm.in_current_function is False

    def test_local_and_remote(self, dmm, simulator):
        dmm.local()
        assert simulator.remote is False
        dmm.remote()
        assert simulator.remote is True


class TestConstruction:
    def test_a_non_positive_echo_timeout_is_refused(self):
        with pytest.raises(ConfigurationError):
            Tti1604(MockTransport(responder=SimulatedTti1604()), echo_timeout=0)

    def test_at_least_one_attempt(self):
        with pytest.raises(ConfigurationError):
            Tti1604(MockTransport(responder=SimulatedTti1604()), attempts=0)


class TestBenchUse:
    def test_registered_as_a_bench_driver(self):
        from benchtools.runner.bench import registered_drivers

        assert "tti1604" in registered_drivers()
        assert "dmm1604" in registered_drivers()

    def test_a_simulated_bench_measures_through_it(self):
        from benchtools.runner.bench import Bench, BenchConfig

        with Bench(BenchConfig.simulated({"dmm": "tti1604"})) as bench:
            dmm = bench.get("dmm")
            dmm.transport.simulator.set_input("dc_amps", 0.02)
            assert dmm.measure_dc_current() == pytest.approx(0.02)
