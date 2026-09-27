"""Fixtures for the S2-LP tests.

Traces to: SWE4-UT-S2LP.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import S2lpDevkit, SimulatedS2lp

#: A payload short enough to fit the default packet length and long enough that
#: a framing mistake shows up as something other than a single byte.
PAYLOAD = b"\x01\x02\x03\x04\x05"


@pytest.fixture
def simulator() -> SimulatedS2lp:
    """A kit with nothing on the air."""
    return SimulatedS2lp()


@pytest.fixture
def routed() -> SimulatedS2lp:
    """A kit whose interrupt is already routed, for tests that drive the
    simulator directly rather than through the driver."""
    kit = SimulatedS2lp()
    kit.route_interrupt()
    kit.respond(b"S2LPPktBasicInit 64 32 2290649224 0 0 32 0 0 0")
    kit.command_log.clear()
    return kit


@pytest.fixture
def loopback() -> SimulatedS2lp:
    """A kit that hears everything it transmits, so one board tests both ways."""
    return SimulatedS2lp(loopback=True)


@pytest.fixture
def radio(simulator) -> S2lpDevkit:
    instrument = S2lpDevkit(MockTransport(responder=simulator))
    instrument.initialise()
    yield instrument
    instrument.close()


@pytest.fixture
def linked(loopback) -> S2lpDevkit:
    """A connected kit in loopback, with a known payload length."""
    instrument = S2lpDevkit(MockTransport(responder=loopback))
    instrument.initialise()
    instrument.configure_packets()
    instrument.set_payload_length(len(PAYLOAD))
    yield instrument
    instrument.close()
