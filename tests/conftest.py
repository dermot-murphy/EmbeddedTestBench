"""Shared fixtures for the TDS3014B driver test suite.

Traces to: SWE4-UT-ENV (shared test environment).
"""

from __future__ import annotations

import pytest

from benchtools.core import MockTransport
from benchtools.instruments.tek3014b import ChannelSignal, SimulatedTDS3014B, Tek3014B

#: Skews used across the timing tests, in seconds.
REFERENCE_SKEWS = {1: 0.0, 2: 12.0e-9, 3: 25.0e-9, 4: 5.0e-9}


@pytest.fixture
def simulator() -> SimulatedTDS3014B:
    """A simulated instrument with four 1 MHz, 3.3 V signals at known skews."""
    return SimulatedTDS3014B(
        signals={
            channel: ChannelSignal(
                frequency=1.0e6, amplitude=3.3, baseline=0.0,
                rise_time=2.0e-9, fall_time=2.0e-9, delay=delay,
            )
            for channel, delay in REFERENCE_SKEWS.items()
        }
    )


@pytest.fixture
def scope(simulator: SimulatedTDS3014B) -> Tek3014B:
    """A driver bound to the simulated instrument, ready for use."""
    instrument = Tek3014B(MockTransport(simulator))
    instrument.initialise()
    yield instrument
    instrument.close()


@pytest.fixture
def configured_scope(scope: Tek3014B) -> Tek3014B:
    """A driver with all four channels set up so nothing clips the digitiser.

    A 3.3 V signal at 1 V/div spans 3.3 divisions, so the positions are chosen
    to keep every trace inside the digitiser's usable +/-5.1 division range.
    """
    for channel, position in zip((1, 2, 3, 4), (-4.0, -3.0, -2.0, -1.0)):
        scope.configure_channel(channel, volts_per_div=1.0, position_div=position, coupling="DC")
    scope.set_time_per_div(200.0e-9)
    scope.set_record_length(10000)
    scope.configure_edge_trigger(source=1, level=1.65, slope="RISE", mode="NORMAL")
    return scope
