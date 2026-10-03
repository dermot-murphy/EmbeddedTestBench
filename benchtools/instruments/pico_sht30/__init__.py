"""Raspberry Pi Pico 2 + DollaTek SHT30-D bench thermometer.

A Pico 2 running ``firmware/pico_sht30`` reads the Sensirion SHT30-DIS on a
DollaTek SHT30-D module over I2C and answers ``rd name``, ``rd copyright``,
``rd version``, ``rd sha`` and ``rd temperature`` over USB CDC.
:mod:`.flash` reflashes it with no BOOTSEL press.

Traces to: PICO-FR-040 .. PICO-FR-076, PICO-ARC-001.
"""

from .constants import (
    DEFAULT_ADDRESS,
    MANUFACTURER,
    MODEL,
    NAME,
    COPYRIGHT,
    PROTOCOL_VERSION,
    raw_to_celsius,
    raw_to_percent,
)
from .simulator import SimulatedPicoSht30
from .thermometer import (
    FirmwareInfo,
    NoReadingError,
    PicoSht30,
    RdRefusedError,
    Reading,
    SensorError,
    SensorStatus,
)
from .flash import FlashError, FlashResult, PicoFlasher, SimulatedRp2350, Uf2Image

__all__ = [
    "PicoSht30",
    "FirmwareInfo",
    "Reading",
    "SensorStatus",
    "SensorError",
    "NoReadingError",
    "RdRefusedError",
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
    "NAME",
    "COPYRIGHT",
    "raw_to_celsius",
    "raw_to_percent",
]
