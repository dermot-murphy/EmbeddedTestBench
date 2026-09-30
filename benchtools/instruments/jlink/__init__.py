"""SEGGER J-Link debug probe driver.

Flash and verify an image, control execution, set breakpoints and watchpoints,
read and write RAM, read variables by name, read the call stack, use RTT, and
measure the time between two points in the code by any of four methods.

Driven over the J-Link GDB Server using GDB's machine interface, so symbol-aware
features - variables by name, source-line breakpoints, call stacks - come from
GDB's own DWARF handling rather than a reimplementation.

Both links are TCP, so the probe can be on another machine::

    from benchtools.instruments.jlink import JLinkProbe

    with JLinkProbe.connect("sim://") as probe:                    # no hardware
        ...
    with JLinkProbe.connect("jlink://", device="nRF52840_xxAA",
                            elf="build/app.elf") as probe:          # local probe
        ...
    with JLinkProbe.connect("jlink://192.168.1.9:2331",
                            elf="build/app.elf") as probe:          # probe elsewhere

Traces to: JLINK-ARC-001.
"""

from .constants import (
    JLINK_LIMITS,
    BreakpointKind,
    DebugInterface,
    HaltReason,
    ProbeLimits,
    ResetType,
    TimingMethod,
    WatchpointKind,
)
from .gdbmi import parse_line, parse_value
from .probe import (
    Breakpoint,
    FlashResult,
    HaltInfo,
    JLinkProbe,
    JLinkRttReader,
    SectionVerdict,
    StackFrame,
    VerifyResult,
    Watchpoint,
)
from .rtt import RttClient, RttTimeout
from .server import GdbServer, find_gdb, find_gdb_server
from .session import GdbError, GdbMiSession
from .simulator import SimulatedFirmware, SimulatedJLink, SimulatedSymbol
from .swo import ItmDecoder, ItmEvent, SwoStream
from .timing import TimingResult, TimingSample

__all__ = [
    "JLinkProbe",
    "JLinkRttReader",
    "Breakpoint",
    "Watchpoint",
    "StackFrame",
    "HaltInfo",
    "FlashResult",
    "VerifyResult",
    "SectionVerdict",
    "TimingResult",
    "TimingSample",
    "TimingMethod",
    "HaltReason",
    "BreakpointKind",
    "WatchpointKind",
    "DebugInterface",
    "ResetType",
    "ProbeLimits",
    "JLINK_LIMITS",
    "RttClient",
    "RttTimeout",
    "ItmDecoder",
    "ItmEvent",
    "SwoStream",
    "GdbMiSession",
    "GdbError",
    "GdbServer",
    "find_gdb",
    "find_gdb_server",
    "SimulatedJLink",
    "SimulatedFirmware",
    "SimulatedSymbol",
    "parse_line",
    "parse_value",
]
