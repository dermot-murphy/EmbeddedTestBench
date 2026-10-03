"""Raspberry Pi Pico 2 + DollaTek SHT30-D bench thermometer.

A Pico 2 running ``firmware/pico_sht30`` reads the Sensirion SHT30-DIS on a
DollaTek SHT30-D module over I2C and reports temperature and humidity over
USB CDC. :mod:`.flash` reflashes it with no BOOTSEL press.

Traces to: PICO-FR-040 .. PICO-FR-076, PICO-ARC-001.
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
from .flash import FlashError, FlashResult, PicoFlasher, SimulatedRp2350, Uf2Image

__all__ = [
    "PicoSht30",
    "FirmwareInfo",
    "Reading",
    "SensorStatus",
    "SensorError",
    "SimulatedPicoSht30",
    "PicoFlasher",
    "FlashError",
    "FlashResult",
    "SimulatedRp2350",
    "Uf2Image",
    "DEFAULT_ADDRESS",
    "MANUFACTURER",
    "MODEL",
    "PROTOCOL_VERSION",
    "TITLE",
    "raw_to_celsius",
    "raw_to_percent",
]
