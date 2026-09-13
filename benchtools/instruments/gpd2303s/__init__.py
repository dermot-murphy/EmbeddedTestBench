"""GW Instek GPD-2303S two-channel bench power supply.

Traces to: PSU-FR-001 .. PSU-FR-050, PSU-ARC-001.
"""

from .constants import (
    CHANNELS,
    MAX_CURRENT,
    MAX_VOLTAGE,
    MODEL,
    ChannelMode,
    TrackingMode,
)
from .psu import ChannelReading, Gpd2303S, SupplyStatus
from .simulator import SimulatedChannel, SimulatedGpd

__all__ = [
    "Gpd2303S",
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
]
