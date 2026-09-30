"""TTi (Thurlby Thandar) 1604 40,000-count bench multimeter, over RS-232.

The meter's interface is a 9-way D-type on the back, opto-isolated and
powered from the host's DTR and RTS lines. It is driven by sending the
characters of its front-panel keys, and it reports by streaming a frame after
every measurement; see :mod:`.dmm` for what that means for a driver.

Traces to: DMM-FR-001 .. DMM-FR-060, DMM-ARC-001.
"""

from .constants import (
    BAUDRATE,
    CURRENT_FUNCTIONS,
    MODEL,
    RANGES,
    SELECTABLE_FUNCTIONS,
    Function,
    Key,
    MeterRange,
)
from .dmm import Tti1604
from .frame import Reading, decode_frame
from .simulator import SimulatedTti1604

__all__ = [
    "Tti1604",
    "Reading",
    "SimulatedTti1604",
    "decode_frame",
    "Function",
    "Key",
    "MeterRange",
    "BAUDRATE",
    "CURRENT_FUNCTIONS",
    "MODEL",
    "RANGES",
    "SELECTABLE_FUNCTIONS",
]
