"""Tektronix TDS3014B oscilloscope driver.

Four analogue channels, 100 MHz, 1.25 GS/s, controlled over Ethernet without a
VISA installation: the instrument's Ethernet port runs an ONC-RPC VXI-11 server,
which :mod:`benchtools.core.transport.vxi11` implements directly. See
``docs/tek3014b/VISA_Determination_Report.md`` for the analysis.

Quick start::

    from benchtools.instruments.tek3014b import Tek3014B

    with Tek3014B.connect("192.168.1.50") as scope:      # or "sim://"
        scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0)
        scope.set_time_per_div(200e-9)
        scope.configure_edge_trigger(source=1, level=1.4)
        waveforms, spread = scope.measure_channel_spread([1, 2])

Traces to: SCOPE-ARC-001.
"""

from .constants import (
    TDS3014B_LIMITS,
    AcquisitionMode,
    Bandwidth,
    Coupling,
    DataEncoding,
    DelayDirection,
    EdgeDirection,
    HardcopyLayout,
    HardcopyPalette,
    ImageFormat,
    MeasurementType,
    ModelLimits,
    Slope,
    StopAfter,
    TriggerMode,
    TriggerSource,
    TriggerState,
)
from .scope import ChannelSetup, Tek3014B
from .simulator import ChannelSignal, SimulatedTDS3014B, make_png

__all__ = [
    "Tek3014B",
    "ChannelSetup",
    "SimulatedTDS3014B",
    "ChannelSignal",
    "make_png",
    "TDS3014B_LIMITS",
    "ModelLimits",
    "AcquisitionMode",
    "Bandwidth",
    "Coupling",
    "DataEncoding",
    "DelayDirection",
    "EdgeDirection",
    "HardcopyLayout",
    "HardcopyPalette",
    "ImageFormat",
    "MeasurementType",
    "Slope",
    "StopAfter",
    "TriggerMode",
    "TriggerSource",
    "TriggerState",
]
