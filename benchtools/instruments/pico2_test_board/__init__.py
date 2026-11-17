"""PICO2 Test Board: a Raspberry Pi Pico 2 with a thermometer, LEDs and a generator.

Named the Pico 2 SHT30 Temperature Sensor before #330. A Pico 2 running
``firmware/pico2_test_board`` reads the Sensirion SHT30-DIS on a
DollaTek SHT30-D module over I2C and answers ``rd name``, ``rd copyright``,
``rd version``, ``rd sha`` and ``rd temperature`` over USB CDC. The same
firmware drives three indicator LEDs and a UDA1334A I2S DAC as a frequency
generator, controlled with ``wr``, ``rd`` and ``routine`` commands.
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
from .simulator import SimulatedPico2TestBoard
from .thermometer import (
    CommandRefusedError,
    FirmwareInfo,
    FreqStatus,
    NoReadingError,
    Pico2TestBoard,
    RdRefusedError,
    WrRefusedError,
    Reading,
    SensorError,
    SensorStatus,
)
from .flash import FlashError, FlashResult, PicoFlasher, SimulatedRp2350, Uf2Image

# The names before #330, kept so that existing scripts still import.
PicoSht30 = Pico2TestBoard
SimulatedPicoSht30 = SimulatedPico2TestBoard

__all__ = [
    "Pico2TestBoard",
    "FirmwareInfo",
    "FreqStatus",
    "CommandRefusedError",
    "Reading",
    "SensorStatus",
    "SensorError",
    "NoReadingError",
    "RdRefusedError",
    "WrRefusedError",
    "SimulatedPico2TestBoard",
    "PicoSht30",
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
