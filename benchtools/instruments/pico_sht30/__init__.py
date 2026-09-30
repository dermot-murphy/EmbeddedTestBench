"""Raspberry Pi Pico 2 + DollaTek SHT30-D bench thermometer.

A Pico 2 running ``firmware/pico_sht30`` reads the Sensirion SHT30-DIS on a
DollaTek SHT30-D module over I2C and reports temperature and humidity over
USB CDC.

Traces to: PICO-FR-040 .. PICO-FR-060, PICO-ARC-001.
"""

from .constants import (
    DEFAULT_ADDRESS,
    MANUFACTURER,
    MODEL,
    PROTOCOL_VERSION,
    TITLE,
    raw_to_celsius,
    raw_to_percent,
)
from .simulator import SimulatedPicoSht30
from .thermometer import FirmwareInfo, PicoSht30, Reading, SensorError, SensorStatus

__all__ = [
    "PicoSht30",
    "FirmwareInfo",
    "Reading",
    "SensorStatus",
    "SensorError",
    "SimulatedPicoSht30",
    "DEFAULT_ADDRESS",
    "MANUFACTURER",
    "MODEL",
    "PROTOCOL_VERSION",
    "TITLE",
    "raw_to_celsius",
    "raw_to_percent",
]
