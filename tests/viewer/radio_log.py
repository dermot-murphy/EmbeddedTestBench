"""An event log with Kepler frames and BLE advertising, from simulated instruments.

Used by the viewer's radio tests (#139), and runnable to make a log to look at:
``python -m tests.viewer.radio_log events.jsonl``.

Traces to: SWE4-UT-VIEWRADIO.
"""

from __future__ import annotations

import logging
import sys

from benchtools.core.events import start_event_log
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import NordicDongle
from benchtools.instruments.nordic_dongle.simulator import SimulatedDongle
from benchtools.instruments.s2lp import S2lpDevkit
from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.instruments.s2lp.simulator import SimulatedS2lp

ALIVE = bytes.fromhex(
    "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005")
VERSION = bytes.fromhex(
    "5c171203060c040213626339373837345631312e30302e303030300000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000000000"
    "047f0301060001")
OTHER_SENSOR = b"\x5c\x31\x4e" + ALIVE[3:]


def write(path: str) -> None:
    """Write the log: four frames from two sensors, one bad, and a BLE profile."""
    handler = start_event_log(path)
    try:
        kit = SimulatedS2lp()
        radio = S2lpDevkit(MockTransport(responder=kit))
        radio.initialise()
        for frame in (ALIVE, VERSION, OTHER_SENSOR, b"\x01\x02"):
            kit.queue_packet(frame, rssi_dbm=-80.0)
        for _packet in radio.stream(decoder=decode_kepler_frame, count=4, timeout=10.0,
                                    mode="polled"):
            pass
        radio.close()
        dongle = NordicDongle(MockTransport(responder=SimulatedDongle()), timeout=5.0)
        dongle.initialise()
        found = dongle.scan(duration=1.0)
        dongle.measure_advertising_profile(duration=2.0, address=found[0].address)
        dongle.close()
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else "radio_events.jsonl")
