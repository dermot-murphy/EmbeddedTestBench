"""PicoScope 3000D series MSO driver (#200).

Four analogue channels and sixteen digital inputs, captured in one block,
and a built-in signal generator. The bench's unit is a PicoScope 3405D MSO
(100 MHz, 1 GS/s, 256 MS), on USB. It is driven through Pico Technology's
``ps3000a`` C library with :mod:`ctypes`, so no Pico Python package is
needed; the library comes with PicoScope 7 or the PicoSDK.

Quick start::

    from benchtools.instruments.picoscope3000 import PicoScope3000

    with PicoScope3000.connect("pico://") as scope:      # or "sim://"
        scope.configure_channel("A", range_volts=2.0)
        scope.configure_edge_trigger("A", level=0.0)
        block = scope.capture()

The 3000D MSO has no digital outputs (spec page); its only output is the
signal generator.

Traces to: PSCOPE-ARC-001.
"""

from .constants import (
    PS3405D_LIMITS,
    Channel,
    Coupling,
    DigitalDirection,
    ModelLimits,
    ThresholdDirection,
    WaveType,
    sample_interval_s,
    timebase_for,
)
from .scope import BlockCapture, ChannelSetup, PicoScope3000
from .sdk import Ps3000aSdk, find_library
from .simulator import ChannelSignal, SimulatedPs3000a

__all__ = [
    "PicoScope3000",
    "BlockCapture",
    "ChannelSetup",
    "Ps3000aSdk",
    "find_library",
    "SimulatedPs3000a",
    "ChannelSignal",
    "PS3405D_LIMITS",
    "ModelLimits",
    "Channel",
    "Coupling",
    "DigitalDirection",
    "ThresholdDirection",
    "WaveType",
    "sample_interval_s",
    "timebase_for",
]
