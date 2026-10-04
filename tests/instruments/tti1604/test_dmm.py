"""The TTi 1604 driver.

The tests are organised around the ways this meter can make a test lie: an
interface left unpowered by the handshake lines, a meter that was never put
into remote mode, a dropped keystroke that leaves it measuring something else,
and a reading taken from a frozen display.

Traces to: DMM-FR-001 .. DMM-FR-033, DMM-FR-045, SWE4-UT-DMM.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import InstrumentError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.tti1604 import SimulatedTti1604, Tti1604
from benchtools.instruments.tti1604.constants import DTR_ASSERTED, KEYS, RTS_ASSERTED


def driver(simulator=None, **kwargs) -> Tti1604:
    simulator = simulator if simulator is not None else SimulatedTti1604()
    instrument = Tti1604(MockTransport(responder=simulator), **kwargs)
    instrument.initialise()
    return instrument


class TestConnecting:
    def test_the_handshake_lines_are_driven_for_a_serial_port(self, monkeypatch):
        # The opto-isolated interface takes its power from DTR and RTS. Left
        # at the library defaults the meter is mute, and every obvious
        # diagnosis - rate, cable, dead meter - is wrong.
        captured = {}

        def fake_open_transport(resource, **kwargs):
            captured["resource"] = resource
            captured.update(kwargs)
            return MockTransport(responder=SimulatedTti1604())

        monkeypatch.setattr(
            "benchtools.instruments.tti1604.dmm.open_transport", fake_open_transport
        )
        Tti1604.connect("/dev/ttyUSB0").close()

        assert captured["resource"] == "serial:///dev/ttyUSB0"
        assert captured["dtr"] is DTR_ASSERTED
        assert captured["rts"] is RTS_ASSERTED
        assert captured["dsrdtr"] is False

    def test_a_bare_port_name_is_a_port_not_a_host(self):
        assert Tti1604._normalise_resource("COM5") == "serial://COM5"
        assert Tti1604._normalise_resource("sim://") == "sim://"
        assert Tti1604._normalise_resource("") == "sim://"

    def test_connecting_enters_remote_mode(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            assert dmm.is_remote is True
            assert simulator.remote is True

    def test_remote_mode_can_be_declined(self):
        # For watching a meter another program is already driving.
        simulator = SimulatedTti1604()
        instrument = driver(simulator, enter_remote=False)
        assert instrument.is_remote is False
        assert simulator.remote is False
        instrument.close()

    def test_connecting_does_not_touch_the_operate_key(self):
        # Operate toggles. Pressing it to "make sure it is on" switches off a
        # meter that already was, and the interface stays alive either way, so
        # it would not even look like a mistake.
        simulator = SimulatedTti1604(operating=True)
        with driver(simulator):
            assert simulator.operating is True
            assert KEYS["operate"] not in simulator.received

    def test_identity_comes_from_the_driver(self):
        # The meter answers no identification query at all.
        with driver() as dmm:
            assert dmm.model == "1604"
            assert "Thurlby" in dmm.manufacturer
            assert dmm.serial_number == ""

    def test_checking_errors_is_a_no_op(self):
        with driver() as dmm:
            dmm.check_errors()


class TestKeyPresses:
    def test_a_key_press_reaches_the_meter(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            dmm.select_milliamps()
            assert simulator.measurement_type == 3

    def test_selecting_ac_and_dc(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            dmm.select_ac()
            assert simulator.ac is True
            dmm.select_dc()
            assert simulator.ac is False

    def test_an_unknown_key_is_refused_by_name(self):
        with driver() as dmm:
            with pytest.raises(InstrumentError) as excinfo:
                dmm.press("gigawatts")
        assert "no 'gigawatts' key" in str(excinfo.value)

    def test_a_dropped_keystroke_is_resent(self):
        class DropsTheFirst(SimulatedTti1604):
            def __init__(self):
                super().__init__()
                self.dropped = 0

            def respond(self, message):
                if self.dropped == 0 and message == b"f":
                    self.dropped += 1
                    return None          # swallowed, as a real meter does
                return super().respond(message)

        simulator = DropsTheFirst()
        with driver(simulator) as dmm:
            dmm.select_volts()
        assert simulator.dropped == 1
        assert simulator.measurement_type == 2

    def test_a_meter_that_never_echoes_is_reported_with_the_likely_cause(self):
        class Mute(SimulatedTti1604):
            def respond(self, message):
                return None

            def poll(self):
                return b""

        with pytest.raises(InstrumentError) as excinfo:
            driver(Mute())
        message = str(excinfo.value)
        assert "did not echo" in message
        assert "DTR" in message          # the actual cause, not a generic timeout


class TestReading:
    def test_a_reading_is_decoded_from_the_stream(self):
        with driver(SimulatedTti1604(value=2.5, measurement_type=2, range_index=1)) as dmm:
            reading = dmm.read()
        assert reading.value == pytest.approx(2.5)
        assert reading.unit == "V"

    def test_several_readings_can_be_collected(self):
        with driver() as dmm:
            assert len(dmm.read_many(3)) == 3

    def test_a_silent_meter_names_both_states_that_cause_it(self):
        # Local mode and Operate-off both produce exactly this silence, and
        # neither is a fault, so the message must not say "broken".
        simulator = SimulatedTti1604(operating=False)
        with driver(simulator) as dmm:
            with pytest.raises(InstrumentError) as excinfo:
                dmm.read(timeout=0.05)
        message = str(excinfo.value)
        assert "remote mode" in message
        assert "Operate" in message

    def test_going_local_stops_the_stream(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            dmm.read()
            dmm.local()
            assert simulator.remote is False
            with pytest.raises(InstrumentError):
                dmm.read(timeout=0.05)

    def test_the_bench_can_say_what_the_simulated_meter_reads(self):
        # So that a specification carrying real limits can be exercised with
        # no hardware. The limits stay the specification's; only the value
        # being judged comes from the bench.
        with Tti1604.connect("sim://", simulated_value=0.0214) as dmm:
            dmm.select_milliamps()
            assert dmm.read().value == pytest.approx(0.0214)

    def test_a_held_reading_is_flagged_rather_than_hidden(self):
        simulator = SimulatedTti1604(value=1.0)
        simulator.status["hold"] = True
        with driver(simulator) as dmm:
            assert dmm.read().held is True


class TestTheSerialLink:
    """#115: the driver must read a real serial port, which never ends a message."""

    @pytest.fixture
    def loop(self):
        pytest.importorskip("serial")
        from benchtools.core.transport.serial_port import SerialTransport

        transport = SerialTransport("loop://", timeout=0.5, dtr=True, rts=False)
        yield transport
        transport.close()

    def test_connecting_over_a_serial_port_sees_the_echo(self, loop):
        # pyserial's loopback echoes what is written, exactly as the meter
        # echoes a key. Before #115 this raised "did not echo 'u'".
        dmm = Tti1604(loop)
        dmm.initialise()
        assert dmm.is_remote is True

    def test_a_frame_on_a_serial_port_is_decoded(self, loop):
        dmm = Tti1604(loop)
        dmm.initialise()
        frame = SimulatedTti1604(value=2.5).frame()
        loop.write(frame + frame, append_terminator=False)
        reading = dmm.read(timeout=1.0)
        assert reading.value == pytest.approx(2.5)


class TestTheStream:
    def test_a_stream_joined_part_way_through_a_frame_resynchronises(self):
        simulator = SimulatedTti1604(value=1.5)
        with driver(simulator) as dmm:
            simulator.garbage = b"\x0d\x21\x40"          # the tail of a frame, and a CR
            dmm._discard_input()
            assert dmm.read().value == pytest.approx(1.5)
            assert dmm.resynchronised_bytes >= 1

    def test_an_echo_is_not_found_inside_a_frame(self):
        # With 3.4444 V on the input every frame carries 0x66, the pattern for
        # 4, which is also 'f', the Volts key. A lost Volts key must still be
        # resent rather than "confirmed" from a digit.
        simulator = SimulatedTti1604(value=3.4444)
        with driver(simulator) as dmm:
            assert 0x66 in simulator.frame()
            simulator.drop_keys = 1
            dmm.select_volts()
        assert simulator.received.count("f") == 1

    def test_a_measurement_is_taken_after_the_call(self):
        # DMM-FR-031: what was waiting is discarded, then one more frame.
        simulator = SimulatedTti1604(value=1.0)
        with driver(simulator) as dmm:
            dmm.read()
            simulator.set_value(2.0)
            sent = simulator.frames_sent
            assert dmm.measure().value == pytest.approx(2.0)
            assert simulator.frames_sent - sent == 2


class TestConfirmation:
    """DMM-FR-029: a key press is confirmed from the readings, not the echo."""

    def test_each_selection_returns_the_reading_that_confirms_it(self):
        simulator = SimulatedTti1604(value=0.0214)
        with driver(simulator) as dmm:
            assert dmm.select_milliamps().function == "dc_milliamps"
            assert dmm.select_ac().function == "ac_milliamps"
            assert dmm.select_volts().function == "ac_volts"
            assert dmm.select_dc().function == "dc_volts"
            assert dmm.select_ohms().function == "ohms"
            assert dmm.select_millivolts().function == "dc_millivolts"
            assert dmm.select_amps().function == "dc_amps"

    def test_a_key_the_meter_ignores_is_reported_with_what_it_shows(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            simulator.ignore_keys = True
            with pytest.raises(InstrumentError, match="readings show dc_volts"):
                dmm.select_ohms()

    def test_ac_or_dc_on_resistance_is_refused_before_pressing(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            dmm.select_ohms()
            with pytest.raises(InstrumentError, match="no AC or DC"):
                dmm.select_ac()
        assert "l" not in simulator.received


class TestRanges:
    """DMM-FR-030: ranges by full scale, and an auto range that does not toggle."""

    def test_a_range_is_locked_by_its_full_scale(self):
        simulator = SimulatedTti1604(value=3.3)
        with driver(simulator) as dmm:
            reading = dmm.set_range(400)
            assert reading.range_label == "400 V"
            assert reading.flags["auto_range"] is False
            assert dmm.measure().value == pytest.approx(3.3)

    def test_the_present_range_is_locked_with_auto_man(self):
        simulator = SimulatedTti1604(value=3.3)
        with driver(simulator) as dmm:
            assert dmm.set_range(4).range_label == "4 V"
        assert simulator.received[-1] == "c"

    def test_milliamp_ranges_skip_the_codes_milliamps_do_not_have(self):
        simulator = SimulatedTti1604(value=0.001)
        with driver(simulator) as dmm:
            dmm.select_milliamps()
            assert dmm.set_range(0.4).range_label == "400 mA"
            assert dmm.set_range(4e-3).range_label == "4 mA"

    def test_a_range_the_function_lacks_is_refused_with_the_list(self):
        with driver() as dmm:
            with pytest.raises(InstrumentError, match="4 V .4.*40 V"):
                dmm.set_range(30)

    def test_auto_range_is_idempotent(self):
        simulator = SimulatedTti1604()
        with driver(simulator) as dmm:
            dmm.select_auto_range()
            assert "c" not in simulator.received        # already auto: nothing pressed
            dmm.set_range(40)
            assert dmm.select_auto_range().flags["auto_range"] is True
            assert dmm.select_auto_range().flags["auto_range"] is True

    def test_a_manual_range_overranges(self):
        simulator = SimulatedTti1604(value=1.0)
        with driver(simulator) as dmm:
            dmm.set_range(4)
            simulator.set_value(12.0)
            reading = dmm.measure()
        assert reading.overrange is True
        assert reading.is_live is False


class TestFrequency:
    """DMM-FR-032, -033: frequency is read once per gate, and waited for."""

    def test_hertz_needs_an_ac_range(self):
        with driver() as dmm:
            with pytest.raises(InstrumentError, match="AC volts or AC current"):
                dmm.select_hertz()

    def test_the_ten_second_gate_is_waited_for(self):
        # The 4 kHz range reads once every 10 s. Waits sized for 2.5 readings
        # a second gave up before the first arrived (#115).
        simulator = SimulatedTti1604(value=50.0, ac=True)
        with driver(simulator) as dmm:
            assert dmm.select_hertz().function == "frequency"
            before = simulator.clock
            reading = dmm.set_range(4000)
            assert reading.status["gate_ten_seconds"] is True
            assert simulator.clock - before >= 10.0
            assert dmm.measure().value == pytest.approx(50.0)
            assert dmm.set_range(40000).status["gate_ten_seconds"] is False
            assert dmm.select_volts().function == "ac_volts"
