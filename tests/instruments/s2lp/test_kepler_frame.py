"""One whole decoded Kepler frame of a given type from a given sensor (#102).

Traces to: S2LP-FR-073, SWE4-UT-S2LPFRAME.
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
