"""The TTi 1604 driver.

The tests are organised around the ways this meter can make a test lie: an
interface left unpowered by the handshake lines, a meter that was never put
into remote mode, a dropped keystroke that leaves it measuring something else,
and a reading taken from a frozen display.

Traces to: DMM-FR-001 .. DMM-FR-060, SWE4-UT-DMM.
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

    def test_a_held_reading_is_flagged_rather_than_hidden(self):
        simulator = SimulatedTti1604(value=1.0)
        simulator.status["hold"] = True
        with driver(simulator) as dmm:
            assert dmm.read().held is True
