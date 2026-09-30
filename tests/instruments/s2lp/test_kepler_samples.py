"""A decoded Kepler field, taken from each transmission a sensor sends (#95).

Traces to: S2LP-FR-072, SWE4-UT-S2LPSAMPLES.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import MeasurementError
from benchtools.instruments.s2lp.kepler import decode_kepler_frame

#: An ALIVE from 5C1712 as received (#86); byte 8 counts the repeats.
ALIVE = bytes.fromhex(
    "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005")


def alive(repeat: int, sequence: int = 0x84, sensor: bytes = b"\x5c\x17\x12") -> bytes:
    data = bytearray(ALIVE)
    data[0:3] = sensor
    data[8] = ((repeat + 1) << 4) | 3
    data[12] = sequence
    return bytes(data)


def send(kit, sequence, sensor=b"\x5c\x17\x12"):
    for repeat in range(3):
        kit.queue_packet(alive(repeat, sequence, sensor))


def test_each_transmission_is_one_reading_not_three(radio, simulator):
    expected = decode_kepler_frame(ALIVE)["temperature_c"]
    send(simulator, 0x84)
    send(simulator, 0x85)
    samples = radio.kepler_samples("temperature_c", source="5C1712", frame_type="ALIVE",
                                   count=2, timeout=10.0, unit="C")
    assert samples.values == [expected, expected]
    assert samples.complete and samples.sources[0].startswith("5C 17 12")


def test_copies_that_differ_in_status_are_still_one_transmission(radio, simulator):
    """5C1712 clears ALIVE_STATUS's "SI updated" bit after the first copy
    (captured 2026-09-28), so copies cannot be matched on their bytes."""
    captured = [
        "5C171203060C04031301037E008F0000870053005E0076003501120384020502510405",
        "5C171203060C04032301037E008F0000870053005E0076003501120384020502510404",
        "5C171203060C04033301037E008F0000870053005E0076003501120384020502510404",
        "5C171203060C04031301037F00900000870055005A0064009E005A02D90222020D0405",
        "5C171203060C04032301037F00900000870055005A0064009E005A02D90222020D0404",
        "5C171203060C04033301037F00900000870055005A0064009E005A02D90222020D0404",
    ]
    for text in captured:
        simulator.queue_packet(bytes.fromhex(text))
    samples = radio.kepler_samples("temperature_c", source="5C1712", frame_type="ALIVE",
                                   count=3, timeout=1.5)
    assert samples.count == 2


def test_a_lost_first_copy_still_starts_a_new_transmission(radio, simulator):
    send(simulator, 0x84)
    for repeat in (1, 2):                        # the next one's first copy was lost
        simulator.queue_packet(alive(repeat, 0x85))
    samples = radio.kepler_samples("temperature_c", source="5C1712", count=3, timeout=1.5)
    assert samples.count == 2


def test_other_sensors_are_left_out(radio, simulator):
    send(simulator, 0x84, sensor=b"\x5c\x31\x4e")
    send(simulator, 0x85)
    samples = radio.kepler_samples("temperature_c", source="5C1712", count=1, timeout=10.0)
    assert samples.count == 1


def test_too_few_frames_returns_what_came(radio, simulator):
    send(simulator, 0x84)
    samples = radio.kepler_samples("temperature_c", source="5C1712", count=3, timeout=1.5)
    assert samples.count == 1 and not samples.complete


def test_a_reading_after_a_stopped_one_still_hears_the_sensor(radio, simulator):
    """The first reading stops the board part-way, which leaves nIRQ asserted.
    Uncleared, every later reading heard nothing from any sensor: the bench
    run of kepler_battery.yaml on 2026-09-29 (#99)."""
    send(simulator, 0x84)
    first = radio.kepler_samples("battery_mv", source="5C1712", count=1, timeout=1.5)
    assert simulator.stopped
    send(simulator, 0x85)
    second = radio.kepler_samples("battery_mv", source="5C1712", count=1, timeout=1.5)
    assert (first.count, second.count) == (1, 1)


def test_a_field_the_frame_does_not_have_is_an_error(radio, simulator):
    send(simulator, 0x84)
    with pytest.raises(MeasurementError, match="no field 'rpm'"):
        radio.kepler_samples("rpm", source="5C1712", count=1, timeout=10.0)
