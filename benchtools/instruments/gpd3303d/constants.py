"""What the GPD-3303D is, and what its command set says.

The numbers here are the supply's published limits, not the driver's policy.
They exist so that an out-of-range setting is refused *before* it is sent:
the supply clamps silently, and a test that asked for 35 V, got 30 V and was
never told would report a pass against a condition it never applied.

Traces to: PSU-FR-001 .. PSU-FR-032, PSU-DD-CONST.
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "MODEL",
    "MANUFACTURER",
    "CHANNELS",
    "TRACKED_CHANNEL",
    "MAX_VOLTAGE",
    "MAX_CURRENT",
    "VOLTAGE_RESOLUTION",
    "CURRENT_RESOLUTION",
    "DEFAULT_BAUDRATE",
    "SUPPORTED_BAUDRATES",
    "DEFAULT_COMMAND_INTERVAL",
    "STATUS_LENGTH",
    "TRACKING_MODES",
    "ChannelMode",
    "TrackingMode",
]

MANUFACTURER = "GW INSTEK"
MODEL = "GPD-3303D"

#: Programmable output channels, numbered as the front panel numbers them.
#:
#: The supply has a **third** output - a fixed 2.5 / 3.3 / 5 V, 3 A rail
#: selected by a front-panel switch. It is deliberately outside this driver:
#: the switch is not a remote control, so nothing the driver could report
#: about that rail would be a measurement. Power a rail from CH3 if it suits
#: the bench, and record which position the switch is in by hand.
CHANNELS: Tuple[int, ...] = (1, 2)

#: Per-channel ratings. Both programmable channels of a GPD-3303D are
#: 30 V / 3 A.
MAX_VOLTAGE = 30.0
MAX_CURRENT = 3.0

#: The channel the supply slaves to the other in series or parallel tracking.
#:
#: CH1 is the master in both tracking modes and keeps working normally. CH2
#: follows it, and the supply accepts and ignores setpoints sent to CH2 -
#: which is why the driver refuses to send them (PSU-FR-006).
TRACKED_CHANNEL = 2

#: Programming resolution. The supply accepts three decimals and rounds to
#: these steps; the driver formats to match so that a setpoint read back
#: compares equal to the one that was sent.
VOLTAGE_RESOLUTION = 0.001
CURRENT_RESOLUTION = 0.001

#: Factory line rate. The front panel can select others (Utility > Baud).
DEFAULT_BAUDRATE = 9600
SUPPORTED_BAUDRATES: Tuple[int, ...] = (9600, 57600, 115200)

#: Minimum gap between commands on a real link, in seconds.
#:
#: The supply has a small input buffer and no flow control. Commands sent
#: back to back at 9600 baud are accepted silently and acted on partially,
#: which is the worst failure mode available: the supply answers, the driver
#: believes it, and the rail is not where the test thinks it is. A simulated
#: link sets this to zero - there is no buffer to overrun.
DEFAULT_COMMAND_INTERVAL = 0.05

#: Characters in a ``STATUS?`` reply.
STATUS_LENGTH = 8


class ChannelMode:
    """Which loop is in control of a channel.

    A supply in **CV** is holding the voltage that was set; in **CC** it has
    hit the current limit and is holding *that* instead, so the rail is below
    the setpoint. Every reading taken in CC is a reading of a different
    circuit from the one the test specified, which is why the driver exposes
    the mode beside the numbers rather than leaving it in a status word.
    """

    CONSTANT_VOLTAGE = "CV"
    CONSTANT_CURRENT = "CC"


class TrackingMode:
    """How the two programmable channels are wired together inside the supply.

    In **series** and **parallel** the supply drives CH2 from CH1's setting.
    A setpoint sent to CH2 is accepted and discarded: nothing in the reply, and
    nothing in ``STATUS?``, says it was. That is the one thing about this
    supply the driver refuses rather than reports.
    """

    INDEPENDENT = "independent"
    SERIES = "series"
    PARALLEL = "parallel"
    UNKNOWN = "unknown"


#: Bits 2 and 3 of ``STATUS?``, as the programming manual defines them.
TRACKING_MODES: Dict[int, str] = {
    0b01: TrackingMode.INDEPENDENT,
    0b11: TrackingMode.SERIES,
    0b10: TrackingMode.PARALLEL,
}

#: Line rates encoded in bits 6 and 7 of ``STATUS?``.
STATUS_BAUDRATES: Dict[int, int] = {
    0b00: 115200,
    0b01: 57600,
    0b10: 9600,
}
