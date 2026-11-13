"""Fixtures for the Pico 2 + SHT30-D thermometer tests.

Traces to: SWE4-UT-PICO.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.pico2_test_board import Pico2TestBoard, SimulatedPico2TestBoard


@pytest.fixture
def simulator() -> SimulatedPico2TestBoard:
    """A thermometer at 22.5 C and 45 %RH, with its sensor present."""
    return SimulatedPico2TestBoard()


@pytest.fixture
def thermometer(simulator) -> Pico2TestBoard:
    """A connected thermometer."""
    instrument = Pico2TestBoard(MockTransport(responder=simulator))
    instrument.initialise()
    yield instrument
    instrument.close()
