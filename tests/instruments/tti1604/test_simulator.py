"""The simulated 1604.

A simulator that only replayed canned frames would let a driver pass while
mishandling the two states in which a real meter is silent, and would not
exercise the segment encoding at all. These tests hold it to the meter's
behaviour.

Traces to: DMM-FR-040 .. DMM-FR-052, SWE4-UT-DMM.
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
        simulator = SimulatedTti1604(range_index=0)
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
        simulator = SimulatedTti1604(value=value, measurement_type=2, range_index=1)
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
