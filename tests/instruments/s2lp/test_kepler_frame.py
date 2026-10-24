"""One whole decoded Kepler frame of a given type from a given sensor (#102).

Traces to: S2LP-FR-073, S2LP-FR-085, SWE4-UT-S2LPFRAME.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import MeasurementError

from .test_kepler import ALIVE_REPEATS, VERSION_FRAME

VERSION = bytes.fromhex(VERSION_FRAME)


def test_the_version_frame_is_returned_whole(radio, simulator):
    simulator.queue_packet(bytes.fromhex(ALIVE_REPEATS[0]))
    simulator.queue_packet(VERSION)
    frame = radio.kepler_frame("VERSION", source="5C1712", timeout=10.0)
    assert (frame["version"], frame["sha"]) == ("V11.00.0000", "bc97874")
    assert frame["battery_loaded_mv"] == 2540 and frame["pcb_version"] == 3
    assert frame["raw"].startswith("5C 17 12 03 06 0C 04 02")


def test_other_sensors_are_left_out(radio, simulator):
    other = bytearray(VERSION)
    other[0:3] = b"\x5c\x31\x4e"
    other[16:27] = b"V10.01.2000"
    simulator.queue_packet(bytes(other))
    simulator.queue_packet(VERSION)
    assert radio.kepler_frame("VERSION", source="5C1712", timeout=10.0)["version"] == "V11.00.0000"


def test_no_frame_is_an_error_naming_what_was_awaited(radio, simulator):
    simulator.queue_packet(bytes.fromhex(ALIVE_REPEATS[0]))
    with pytest.raises(MeasurementError, match="no VERSION frame from 5C1712"):
        radio.kepler_frame("VERSION", source="5C1712", timeout=1.5)


class TestConsecutiveCalls:
    """Frames that arrive while a call stops the board (#293)."""

    @staticmethod
    def _queue_copies(simulator, copies=3):
        for payload in ALIVE_REPEATS[:copies]:
            simulator.queue_packet(bytes.fromhex(payload))

    def test_since_last_gets_consecutive_copies(self, radio, simulator):
        self._queue_copies(simulator)
        repeats = [radio.kepler_frame("ALIVE", source="5C1712", timeout=2.0,
                                      since_last=True)["frame"]["repeat"]
                   for _ in range(3)]
        assert repeats == [0, 1, 2]

    def test_without_it_the_error_says_what_was_set_aside(self, radio, simulator):
        self._queue_copies(simulator)
        assert radio.kepler_frame("ALIVE", source="5C1712", timeout=2.0)["frame"]["repeat"] == 0
        with pytest.raises(MeasurementError,
                           match=r"no ALIVE frame from 5C1712 in 1.5 s; 2 such frames arrived "
                                 r"while the last receive was stopping.*since_last takes them"):
            radio.kepler_frame("ALIVE", source="5C1712", timeout=1.5)

    def test_a_frame_of_another_type_is_passed_over(self, radio, simulator):
        simulator.queue_packet(VERSION)
        self._queue_copies(simulator, 2)
        version = radio.kepler_frame("VERSION", source="5C1712", timeout=2.0)["version"]
        assert version == "V11.00.0000"
        assert radio.kepler_frame("ALIVE", source="5C1712", timeout=2.0,
                                  since_last=True)["frame"]["repeat"] == 0

    def test_another_receive_discards_what_was_set_aside(self, radio, simulator):
        self._queue_copies(simulator, 2)
        radio.kepler_frame("ALIVE", source="5C1712", timeout=2.0)
        assert not list(radio.stream(timeout=0.5))
        with pytest.raises(MeasurementError, match="no ALIVE frame from 5C1712 in 1 s$"):
            radio.kepler_frame("ALIVE", source="5C1712", timeout=1.0, since_last=True)
