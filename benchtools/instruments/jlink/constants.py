"""SEGGER J-Link and Cortex-M constants.

Register addresses are from the ARMv7-M architecture reference manual; port
numbers are the J-Link GDB Server defaults.

Traces to: JLINK-FR-010, JLINK-FR-060, JLINK-DD-CONST.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ...core.enums import ScpiEnum

__all__ = [
    "DebugInterface",
    "HaltReason",
    "BreakpointKind",
    "WatchpointKind",
    "TimingMethod",
    "ResetType",
    "ProbeLimits",
    "JLINK_LIMITS",
    "DEFAULT_GDB_PORT",
    "DEFAULT_RTT_PORT",
    "DEFAULT_SWO_PORT",
    "DEFAULT_TELNET_PORT",
    "DEMCR",
    "DEMCR_TRCENA",
    "DWT_CTRL",
    "DWT_CTRL_CYCCNTENA",
    "DWT_CYCCNT",
]


class DebugInterface(ScpiEnum):
    """Physical debug interface to the target."""

    SWD = "SWD"
    JTAG = "JTAG"
    CJTAG = "cJTAG"
    FINE = "FINE"


class ResetType(ScpiEnum):
    """How the target is reset.

    ``HALT`` is the default everywhere in this driver: resetting into a running
    target then trying to halt it races the start-up code, and a test that
    sometimes catches ``main`` and sometimes catches the reset handler is worse
    than useless.
    """

    HALT = "HALT"
    RUN = "RUN"


class HaltReason(ScpiEnum):
    """Why the target stopped.

    Values mirror the ``reason`` field of GDB/MI's ``*stopped`` record, with
    :attr:`UNKNOWN` for anything unrecognised so a new GDB does not break the
    driver.
    """

    BREAKPOINT = "breakpoint-hit"
    WATCHPOINT = "watchpoint-trigger"
    READ_WATCHPOINT = "read-watchpoint-trigger"
    ACCESS_WATCHPOINT = "access-watchpoint-trigger"
    STEP_DONE = "end-stepping-range"
    FUNCTION_FINISHED = "function-finished"
    SIGNAL = "signal-received"
    EXITED = "exited"
    EXITED_NORMALLY = "exited-normally"
    UNKNOWN = "unknown"

    @classmethod
    def from_mi(cls, reason: str) -> "HaltReason":
        """Map an MI ``reason`` string, falling back to :attr:`UNKNOWN`."""
        for member in cls:
            if member.value == reason:
                return member
        return cls.UNKNOWN


class BreakpointKind(ScpiEnum):
    """Kind of code breakpoint."""

    SOFTWARE = "SOFTWARE"
    HARDWARE = "HARDWARE"
    TEMPORARY = "TEMPORARY"


class WatchpointKind(ScpiEnum):
    """Kind of data watchpoint."""

    WRITE = "WRITE"
    READ = "READ"
    ACCESS = "ACCESS"


class TimingMethod(ScpiEnum):
    """How an interval between two code locations is measured.

    The four differ in accuracy and in what they require of the target, and the
    difference matters: the same interval measured by :attr:`HOST_CLOCK` and
    :attr:`CYCLE_COUNTER` can differ by three orders of magnitude.

    :cvar CYCLE_COUNTER: Read the Cortex-M DWT cycle counter at both points.
        Sub-microsecond, independent of host and USB latency. Cortex-M only, and
        the interval must be short enough not to wrap a 32-bit counter.
    :cvar HOST_CLOCK: Time the two halts on the host clock. Works on any core
        and needs nothing of the target, but includes probe and host latency, so
        it is millisecond-grade. Honest for long intervals, misleading for short.
    :cvar SWO_ITM: Timestamp ITM writes in the SWO trace stream. Precise and
        does not halt the target, so it measures real timing rather than
        stop-start timing. Needs the SWO pin wired and the firmware
        instrumented.
    :cvar TARGET_TIMER: The target samples its own timer into a variable at each
        point and the driver reads the variable. Needs firmware cooperation, and
        is the most faithful to real execution.
    """

    CYCLE_COUNTER = "CYCLE_COUNTER"
    HOST_CLOCK = "HOST_CLOCK"
    SWO_ITM = "SWO_ITM"
    TARGET_TIMER = "TARGET_TIMER"


# --- J-Link GDB Server default ports --------------------------------------
DEFAULT_GDB_PORT = 2331
DEFAULT_TELNET_PORT = 2333
DEFAULT_SWO_PORT = 2332
DEFAULT_RTT_PORT = 19021

# --- ARMv7-M debug and trace registers ------------------------------------
#: Debug Exception and Monitor Control Register.
DEMCR = 0xE000EDFC
#: DEMCR bit enabling the trace and debug blocks, DWT included.
DEMCR_TRCENA = 1 << 24
#: Data Watchpoint and Trace control register.
DWT_CTRL = 0xE0001000
#: DWT_CTRL bit enabling the cycle counter.
DWT_CTRL_CYCCNTENA = 1 << 0
#: DWT cycle counter. Counts core clocks; wraps every 2**32 cycles.
DWT_CYCCNT = 0xE0001004


@dataclass(frozen=True)
class ProbeLimits:
    """Capability envelope of the probe and target, used to validate requests.

    Defaults are conservative and suit a Cortex-M with the common four
    comparators. Pass a different instance for a target with more.
    """

    model: str = "J-Link"
    #: Hardware code breakpoints available in the target's FPB unit.
    max_hardware_breakpoints: int = 4
    #: Data watchpoints available in the target's DWT unit.
    max_watchpoints: int = 4
    #: RTT channels the driver will address.
    max_rtt_channels: int = 16
    #: Interface speed range in kHz; 0 means adaptive.
    speed_khz_range: Tuple[int, int] = (5, 50000)
    #: Largest single memory transfer, in bytes.
    max_transfer_bytes: int = 0x10000
    #: Core clock assumed when converting cycles to seconds, in hertz.
    #: Wrong here means every cycle-counter timing is wrong by the same ratio,
    #: so it is required to be set deliberately rather than guessed.
    core_clock_hz: float = 64.0e6

    @property
    def cycle_counter_max_seconds(self) -> float:
        """Longest interval the 32-bit cycle counter can measure without wrapping."""
        return (2 ** 32) / self.core_clock_hz


#: Default envelope: a J-Link against a Cortex-M with four FPB comparators.
JLINK_LIMITS = ProbeLimits()
