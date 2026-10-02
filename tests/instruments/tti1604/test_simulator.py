"""The simulated 1604.

A simulator that only replayed canned frames would let a driver pass while
mishandling the two states in which a real meter is silent, and would not
exercise the segment encoding at all. These tests hold it to the meter's
behaviour.

Traces to: DMM-FR-045, DMM-FR-046, SWE4-UT-DMM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.tti1604 import SimulatedTti1604, decode
from benchtools.instruments.tti1604.constants import FRAME_LENGTH, KEYS, LOCAL, REMOTE


class TestSilence:
    """The two states where a healthy meter says nothing."""

    def test_nothing_is_streamed_in_local_mode(self):
        assert SimulatedTti1604().poll() == b""

    def test_nothing_is_streamed_while_switched_off(self):
        simulator = SimulatedTti1604(operating=False)
        simulator.respond(REMOTE.encode())
        assert simulator.poll() == b""

    def test_frames_stream_once_remote_and_on(self):
        simulator = SimulatedTti1604()
        simulator.respond(REMOTE.encode())
        assert len(simulator.poll()) == FRAME_LENGTH

    def test_going_local_stops_the_stream(self):
        simulator = SimulatedTti1604()
        simulator.respond(REMOTE.encode())
        simulator.respond(LOCAL.encode())
        assert simulator.poll() == b""


class TestKeys:
    def test_every_command_is_echoed(self):
        simulator = SimulatedTti1604()
        assert simulator.respond(b"f") == b"f"

    def test_operate_toggles_rather_than_switching_on(self):
        simulator = SimulatedTti1604(operating=True)
        simulator.respond(KEYS["operate"].encode())
        assert simulator.operating is False
        simulator.respond(KEYS["operate"].encode())
        assert simulator.operating is True

    def test_range_keys_stay_within_the_meter_s_ranges(self):
        # Resistance is the function with all six ranges, 0 to 5. Volts start
        # at the 4 V range (code 1) and stop at 1000 V (code 4), so stepping
        # them is checked separately below (#115).
        simulator = SimulatedTti1604(range_index=0, measurement_type=5)
        simulator.respond(KEYS["down"].encode())
        assert simulator.range_index == 0
        for _ in range(10):
            simulator.respond(KEYS["up"].encode())
        assert simulator.range_index == 5

    def test_an_unknown_character_is_echoed_but_changes_nothing(self):
        simulator = SimulatedTti1604()
        before = (simulator.measurement_type, simulator.range_index, simulator.ac)
        assert simulator.respond(b"z") == b"z"
        assert (simulator.measurement_type, simulator.range_index, simulator.ac) == before


class TestEncoding:
    """What the simulator encodes, the decoder must read back."""

    @pytest.mark.parametrize("value", [0.0, 1.0, -1.0, 1.2345, 399.99, -0.005])
    def test_a_value_survives_the_round_trip(self, value):
        # Auto-ranged, as the meter is after a change of function. 399.99 V on
        # the locked 4 V range is an overrange on a real meter (#115).
        simulator = SimulatedTti1604(value=value, measurement_type=2)
        assert decode(simulator.frame()).value == pytest.approx(value, abs=1e-4)

    def test_a_value_too_large_for_the_display_becomes_overrange(self):
        simulator = SimulatedTti1604(value=123456789.0, measurement_type=2, range_index=1)
        reading = decode(simulator.frame())
        assert reading.overrange is True
        assert reading.value is None

    def test_the_function_flags_reach_the_frame(self):
        simulator = SimulatedTti1604()
        simulator.flags["null"] = True
        assert decode(simulator.frame()).flags["null"] is True

    def test_the_status_flags_reach_the_frame(self):
        simulator = SimulatedTti1604()
        simulator.status["continuity_buzzer"] = True
        assert decode(simulator.frame()).status["continuity_buzzer"] is True


class TestTheMeterAsTheManualDescribesIt:
    """DMM-FR-046: resolution, auto-ranging and reading rate, as the 1604 has them."""

    @pytest.mark.parametrize(
        "kwargs,text,label",
        [
            ({"value": 3.3}, "3.3000", "4 V"),
            ({"value": 33.0}, "33.000", "40 V"),
            ({"value": 230.0, "ac": True}, "230.0", "400 V"),
            ({"value": 0.0123, "measurement_type": 3}, "12.30", "400 mA"),
            ({"value": 0.0012345, "measurement_type": 3}, "1.2345", "4 mA"),
            ({"value": 4700.0, "measurement_type": 5}, "4.700", "40 kohm"),
        ],
    )
    def test_the_display_at_the_range_s_resolution(self, kwargs, text, label):
        reading = decode(SimulatedTti1604(**kwargs).frame())
        assert reading.text == text
        assert reading.range_label == label

    def test_a_change_of_function_sets_auto_range(self):
        simulator = SimulatedTti1604()
        simulator.respond(KEYS["up"].encode())
        assert simulator.flags["auto_range"] is False
        simulator.respond(KEYS["ohms"].encode())
        assert simulator.flags["auto_range"] is True

    def test_hertz_is_refused_on_dc(self):
        simulator = SimulatedTti1604()
        simulator.respond(KEYS["hertz"].encode())
        assert simulator.flags["hertz"] is False

    def test_readings_come_every_0_4_s_and_once_per_gate_measuring_frequency(self):
        simulator = SimulatedTti1604(ac=True)
        simulator.respond(REMOTE.encode())
        simulator.poll()
        before = simulator.clock
        simulator.poll()
        assert simulator.clock - before == pytest.approx(0.4)
        simulator.respond(KEYS["hertz"].encode())
        simulator.poll()
        before = simulator.clock
        simulator.poll()
        assert simulator.clock - before == pytest.approx(1.0)
        simulator.respond(KEYS["down"].encode())
        before = simulator.clock
        simulator.poll()
        assert simulator.clock - before == pytest.approx(10.0)

    def test_a_read_shorter_than_the_measurement_times_out(self):
        from benchtools.core.errors import TransportTimeoutError

        simulator = SimulatedTti1604(ac=True)
        simulator.respond(REMOTE.encode() + KEYS["hertz"].encode())
        before = simulator.clock
        with pytest.raises(TransportTimeoutError):
            simulator.poll_within(0.5)
        assert simulator.clock - before == pytest.approx(0.5)
        assert simulator.poll_within(0.6)[0] == 0x0D

    def test_dropped_and_ignored_keys(self):
        simulator = SimulatedTti1604()
        simulator.drop_keys = 1
        assert simulator.respond(KEYS["ohms"].encode()) is None
        simulator.ignore_keys = True
        assert simulator.respond(KEYS["ohms"].encode()) == b"i"
        assert simulator.measurement_type == 2
