"""Fixtures for the J-Link driver tests.

Traces to: SWE4-UT-JLINK.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.jlink import JLinkProbe, SimulatedJLink
from benchtools.instruments.jlink.session import GdbMiSession

#: The default firmware puts sensor.c:40 at 5 000 cycles and sensor.c:75 at
#: 69 000, so the interval is exactly 64 000 cycles - 1.000 ms at 64 MHz.
INTERVAL_CYCLES = 64_000
INTERVAL_SECONDS = INTERVAL_CYCLES / 64.0e6
START_LOCATION = "sensor.c:40"
END_LOCATION = "sensor.c:75"


@pytest.fixture
def simulator() -> SimulatedJLink:
    """A simulated J-Link with the default firmware."""
    return SimulatedJLink()


@pytest.fixture
def session(simulator) -> GdbMiSession:
    """A GDB/MI session onto the simulator."""
    instance = GdbMiSession(MockTransport(responder=simulator), timeout=5.0)
    instance.start()
    yield instance
    instance.close()


@pytest.fixture
def probe(simulator) -> JLinkProbe:
    """A connected probe with symbols loaded, over the given simulator.

    Built directly rather than through ``connect`` so the test can reach the
    simulator it shares. RTT is attached automatically for a simulated link.
    """
    instance = JLinkProbe(
        session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
        elf="firmware.elf",
        target_address="simulated",
    )
    instance.initialise()
    yield instance
    instance.close()
