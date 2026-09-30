"""Fixtures for the TTi 1604 tests.

Traces to: SWE4-UT-DMM.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.tti1604 import SimulatedTti1604, Tti1604


@pytest.fixture
def simulator() -> SimulatedTti1604:
    """A meter on DC volts, auto-ranging, with nothing on its input."""
    return SimulatedTti1604()


@pytest.fixture
def dmm(simulator) -> Tti1604:
    """A connected meter, in remote mode, on the simulator's clock."""
    instrument = Tti1604(MockTransport(responder=simulator))
    instrument.initialise()
    yield instrument
    instrument.close()
