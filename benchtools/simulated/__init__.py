"""What the simulated instruments share: the devices on a simulated bench.

A real bench has one sensor wired to the supply, the probe, the dongle's radio
and the S2-LP kit's. A simulated bench builds each instrument's simulator
separately, so the things they all touch live here, once per process: a supply
the simulated sensor is powered from, and the sensors themselves.

Traces to: BLE-DD-SIMWORLD.
"""

from .kepler import (
    KEPLER_5C1712_ADDRESS,
    KEPLER_5C1712_ID,
    KEPLER_5C1712_NAME,
    KeplerSensorModel,
)
from .world import kepler_sensor, register_supply, reset_world, rtt_source, supply_volts

__all__ = [
    "KEPLER_5C1712_ADDRESS",
    "KEPLER_5C1712_ID",
    "KEPLER_5C1712_NAME",
    "KeplerSensorModel",
    "kepler_sensor",
    "register_supply",
    "reset_world",
    "rtt_source",
    "supply_volts",
]
