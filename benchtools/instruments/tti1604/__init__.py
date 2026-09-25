"""TTi 1604 bench multimeter, over its opto-isolated RS-232 interface.

The meter has no command language: the link carries single characters standing
for front-panel key presses, and in remote mode it streams a ten-byte binary
frame after every measurement.

Traces to: DMM-FR-001 .. DMM-FR-060, DMM-ARC-001.
"""

from .constants import (
    DEFAULT_BAUDRATE,
    DISPLAY_COUNTS,
    DTR_ASSERTED,
    KEYS,
    MANUFACTURER,
    MODEL,
    READING_INTERVAL,
    RTS_ASSERTED,
)
from .dmm import Tti1604
from .protocol import FrameAssembler, Reading, decode, digits_text, unit_and_scale
from .simulator import SimulatedTti1604

__all__ = [
    "Tti1604",
    "SimulatedTti1604",
    "Reading",
    "FrameAssembler",
    "decode",
    "digits_text",
    "unit_and_scale",
    "KEYS",
    "MODEL",
    "MANUFACTURER",
    "DEFAULT_BAUDRATE",
    "DISPLAY_COUNTS",
    "DTR_ASSERTED",
    "RTS_ASSERTED",
    "READING_INTERVAL",
]
