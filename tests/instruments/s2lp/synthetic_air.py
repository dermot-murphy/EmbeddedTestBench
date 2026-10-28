"""A synthetic hour of Kepler traffic, for the frame-measure tests (#243).

Built from the frame layouts the Kepler plugin decodes, not recorded: every
payload is one of the test frames in ``test_kepler.py`` with its sensor, repeat
number, multiplex, packet number or permutation set here. The schedule is
chosen so that each measure has something to find:

* sensor ``AA0001`` sends a CMD every 50 s, missing three (a 100 s gap and
  a 150 s one), and
  ``AA0002`` a CMD sequence every 30 s: three attempts 0.1 s apart;
* 5C1712 sends CONFIG multiplexes 0 to 11 under the distance permutation,
  45 s apart, then 0 to 11 under the polynomial, three copies each; an ALIVE
  every 60 s, three copies; TWF packets 0 to 7 of 256, three copies, group 1;
  and one VERSION, three copies;
* a gateway ``AA00FF`` answers each ``AA0001`` CMD with a RESPONSE;
* three CONFIG frames one byte short, which the decoder refuses, and one
  reception the receiver rejected.

:func:`frames` gives the frames; :func:`write_log` writes them as an S2-LP
packet log, timed by ``host_time`` (as a log from before #243) or by
``monotonic_s``.

Traces to: SWE4-UT-ENV (shared test environment).
"""

from __future__ import annotations

import datetime
import json
from typing import List, Tuple

from benchtools.analysis import frames as fr

from ...kepler_plugin import decode_kepler_frame, tables
from .test_kepler import ALIVE_REPEATS, CONFIG_FRAME, TWF_FRAMES, VERSION_FRAME, header

SENSOR = b"\x5c\x17\x12"
#: Where the hour starts on the wall clock, for a log timed by host_time.
EPOCH = datetime.datetime(2026, 10, 28, tzinfo=datetime.timezone.utc)

#: Seconds into the hour of each CMD from AA0001: every 50 s, three missed.
CMD_A_TIMES = [20.0 + 50.0 * n for n in range(62) if n not in (17, 40, 41)]
#: CONFIG transmissions: 12 under distance from 100 s, 12 under the
#: polynomial after a 300 s pause; 45 s apart.
CONFIG_DISTANCE_AT = [100.0 + 45.0 * n for n in range(12)]
CONFIG_POLY_AT = [CONFIG_DISTANCE_AT[-1] + 300.0 + 45.0 * n for n in range(12)]


def _repeat(repeat: int, copies: int = 3) -> int:
    """The count byte: ((repeat + 1) << 4) | copies."""
    return ((repeat + 1) << 4) | copies


def cmd(sensor: bytes, attempt: int = 0) -> bytes:
    """A CMD frame for *sensor*, asking for the gateway's answer."""
    data = header(8, 15, type_cap=0)
    data[0:3] = sensor
    data[4] = 5
    data[8] = _repeat(0, 1)
    data[9:12] = sensor
    data[12:14] = (1).to_bytes(2, "big")
    data[14] = attempt
    return bytes(data)


def response(gateway: bytes, sensor: bytes) -> bytes:
    data = header(9, 14)
    data[0:3] = gateway
    data[9:12] = sensor
    data[12:14] = (4).to_bytes(2, "big")
    return bytes(data)


def config(mux: int, repeat: int, method: int) -> bytes:
    """CONFIG multiplex *mux*, copy *repeat*: method 0 distance, 2 polynomial.

    Each slot carries its parameter's number times ten, so a parameter carries
    the same value in whichever frame and slot the permutation puts it.
    """
    data = bytearray.fromhex(CONFIG_FRAME)
    data[8] = (data[8] & ~0x18) | (method << 3)
    data[9] = _repeat(repeat)
    data[10] = mux
    name = {0: "distance", 2: "polynomial"}[method]
    for slot in range(5):
        parameter = tables.config_parameter(mux, slot, name, repeat)
        data[11 + 2 * slot:13 + 2 * slot] = (10 * parameter).to_bytes(2, "big")
    return bytes(data)


def alive(repeat: int) -> bytes:
    data = bytearray.fromhex(ALIVE_REPEATS[0])
    data[8] = _repeat(repeat)
    return bytes(data)


def twf(packet: int, repeat: int) -> bytes:
    data = bytearray.fromhex(TWF_FRAMES[0])
    data[9] = _repeat(repeat)
    data[17:19] = packet.to_bytes(2, "big")
    return bytes(data)


def version(repeat: int) -> bytes:
    data = bytearray.fromhex(VERSION_FRAME)
    data[8] = _repeat(repeat)
    return bytes(data)


def schedule() -> List[Tuple[float, bytes, int]]:
    """Every reception of the hour: (seconds, payload, receiver error)."""
    sent: List[Tuple[float, bytes, int]] = []
    for at in CMD_A_TIMES:
        sent.append((at, cmd(b"\xaa\x00\x01"), 0))
        sent.append((at + 0.12, response(b"\xaa\x00\xff", b"\xaa\x00\x01"), 0))
    for start in range(5, 3600, 30):
        for attempt in range(3):
            sent.append((start + 0.1 * attempt, cmd(b"\xaa\x00\x02", attempt), 0))
    for method, times in ((0, CONFIG_DISTANCE_AT), (2, CONFIG_POLY_AT)):
        for mux, at in enumerate(times):
            for repeat in range(3):
                sent.append((at + 0.05 * repeat, config(mux, repeat, method), 0))
    for at in range(30, 3600, 60):
        for repeat in range(3):
            sent.append((at + 0.05 * repeat, alive(repeat), 0))
    for packet in range(8):
        for repeat in range(3):
            sent.append((2000.0 + packet + 0.05 * repeat, twf(packet, repeat), 0))
    for repeat in range(3):
        sent.append((10.0 + 0.05 * repeat, version(repeat), 0))
        sent.append((3000.0 + 0.05 * repeat, config(0, repeat, 0)[:20], 0))
    sent.append((1500.0, b"", 2))
    return sorted(sent, key=lambda item: item[0])


def frames() -> List[fr.Frame]:
    """The hour's frames, decoded, timed in seconds from its start."""
    out = []
    for at, data, error in schedule():
        decoded, problem = None, ""
        if not error:
            try:
                decoded = decode_kepler_frame(data)
            except Exception as exc:  # pylint: disable=broad-except
                problem = str(exc)
        out.append(fr.Frame(data, decoded, at, error, problem))
    return out


def write_log(path: str, monotonic: bool = False) -> str:
    """Write the hour as an S2-LP packet log, as the driver records one."""
    with open(path, "w", encoding="utf-8") as handle:
        for at, data, error in schedule():
            record = {"direction": "rx", "hex": data.hex(), "error": error,
                      "host_time": (EPOCH + datetime.timedelta(seconds=at)).isoformat()}
            if monotonic:
                record["monotonic_s"] = 5000.0 + at
            handle.write(json.dumps(record) + "\n")
    return path
