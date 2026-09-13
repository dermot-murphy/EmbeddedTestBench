"""Fixtures for the BLE dongle tests.

Traces to: SWE4-UT-BLE.
"""

from __future__ import annotations

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import NordicDongle, SimulatedDongle

#: The default simulated sensor: 100 ms nominal interval, advertising delays of
#: 0, 3, 7 and 10 ms in rotation. The bounds are therefore exactly 100 ms and
#: 110 ms; the mean is 105 ms over whole rotations and within a couple of
#: milliseconds of it over a partial one - as with a real sensor, whose advDelay
#: is random rather than rotating.
SENSOR_NAME = "SENS-01"
SENSOR_ADDRESS = "E4:1C:7B:02:9A:11"
NOMINAL_INTERVAL_S = 0.100
MEAN_INTERVAL_S = 0.105

#: The second sensor drops one advertising event in five.
FLAKY_NAME = "SENS-02"
FLAKY_ADDRESS = "C9:3A:51:0F:22:04"
FLAKY_INTERVAL_S = 0.250

#: Round trips the simulated sensor takes, in microseconds.
FAST_LATENCY_US = 12_500
SLOW_LATENCY_US = 95_000
CONNECTION_INTERVAL_US = 30_000


@pytest.fixture
def simulator() -> SimulatedDongle:
    """A simulated dongle with the default sensor population."""
    return SimulatedDongle()


@pytest.fixture
def dongle(simulator) -> NordicDongle:
    """A connected dongle over the given simulator.

    Built directly rather than through ``connect`` so a test can reach the
    simulator it is driving.
    """
    instrument = NordicDongle(MockTransport(responder=simulator), timeout=5.0)
    instrument.initialise()
    yield instrument
    instrument.close()


@pytest.fixture
def scanned(dongle) -> NordicDongle:
    """A dongle that has scanned and selected the sensor under test."""
    dongle.scan(1.0)
    dongle.select(SENSOR_NAME)
    return dongle


@pytest.fixture
def linked(scanned) -> NordicDongle:
    """A dongle connected to the sensor under test."""
    scanned.open_link()
    return scanned
