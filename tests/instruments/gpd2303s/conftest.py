"""Fixtures for the GPD-2303S tests.

Traces to: SWE4-UT-PSU.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.gpd2303s import Gpd2303S, SimulatedGpd

#: A load that draws 330 mA at 3.3 V - comfortably inside a 500 mA limit, so a
#: channel with it connected stays in constant voltage.
LIGHT_LOAD_OHMS = 10.0

#: A load that would draw 1.65 A at 3.3 V. Under a 500 mA limit the supply goes
#: to constant current and the rail sits at 1.0 V instead of 3.3 V, which is the
#: condition every one of these tests exists to make visible.
HEAVY_LOAD_OHMS = 2.0


@pytest.fixture
def simulator() -> SimulatedGpd:
    """An unloaded supply, both channels at zero, output off."""
    return SimulatedGpd()


@pytest.fixture
def psu(simulator) -> Gpd2303S:
    """A connected supply with nothing attached to its terminals."""
    instrument = Gpd2303S(MockTransport(responder=simulator), command_interval=0.0)
    instrument.initialise()
    yield instrument
    instrument.close()


@pytest.fixture
def loaded(simulator) -> Gpd2303S:
    """A supply with 10 ohms on channel 1 and 2 ohms on channel 2."""
    simulator.set_load(1, LIGHT_LOAD_OHMS)
    simulator.set_load(2, HEAVY_LOAD_OHMS)
    instrument = Gpd2303S(MockTransport(responder=simulator), command_interval=0.0)
    instrument.initialise()
    yield instrument
    instrument.close()
