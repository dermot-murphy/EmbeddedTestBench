"""GW Instek GPD-3303D bench power supply, programmable channels 1 and 2.

The supply's third output - the fixed 2.5 / 3.3 / 5 V rail - is selected by a
front-panel switch and is not reachable over the interface, so it is outside
this driver; see :data:`.constants.CHANNELS`.

Traces to: PSU-FR-001 .. PSU-FR-050, PSU-ARC-001.
"""

from .constants import (
    CHANNELS,
    MAX_CURRENT,
    MAX_VOLTAGE,
    MODEL,
    TRACKED_CHANNEL,
    ChannelMode,
    TrackingMode,
)
from .psu import ChannelReading, Gpd3303D, SupplyStatus
from .simulator import SimulatedChannel, SimulatedGpd

__all__ = [
    "Gpd3303D",
    "ChannelReading",
    "SupplyStatus",
    "SimulatedGpd",
    "SimulatedChannel",
    "ChannelMode",
    "TrackingMode",
    "CHANNELS",
    "MAX_VOLTAGE",
    "MAX_CURRENT",
    "MODEL",
    "TRACKED_CHANNEL",
]
