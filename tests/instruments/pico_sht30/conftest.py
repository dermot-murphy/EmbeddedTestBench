"""Fixtures for the Pico 2 + SHT30-D thermometer tests.

Traces to: SWE4-UT-PICO.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.pico_sht30 import PicoSht30, SimulatedPicoSht30


@pytest.fixture
def simulator() -> SimulatedPicoSht30:
    """A thermometer at 22.5 C and 45 %RH, with its sensor present."""
    return SimulatedPicoSht30()


@pytest.fixture
def thermometer(simulator) -> PicoSht30:
    """A connected thermometer."""
    instrument = PicoSht30(MockTransport(responder=simulator))
    instrument.initialise()
    yield instrument
    instrument.close()
