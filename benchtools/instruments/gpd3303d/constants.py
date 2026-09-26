"""What the GPD-3303D is, and what its command set says.

The numbers here are the supply's published limits, not the driver's policy.
They exist so that an out-of-range setting is refused *before* it is sent:
the supply rejects it, keeps whatever it was set to before, and says so only
through ``ERR?``. A test that asked for 35 V would run at the previous setting
and never be told.

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
    "VOLTAGE_READBACK_RESOLUTION",
    "CURRENT_READBACK_RESOLUTION",
    "DEFAULT_BAUDRATE",
    "SUPPORTED_BAUDRATES",
    "DEFAULT_COMMAND_INTERVAL",
    "REPLY_TERMINATOR",
    "STATUS_LENGTH",
    "STATUS_LEGEND_LINES",
    "STATUS_BIT_BEEP",
    "STATUS_BIT_OUTPUT",
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

#: Read-back resolution, which is coarser than the programming resolution.
#:
#: Firmware V1.09 answers ``VSET1?`` and ``VOUT1?`` to 0.1 V and ``ISET1?`` and
#: ``IOUT1?`` to 0.01 A: ``VSET1:3.250`` reads back as ``3.3V``, and an
#: unloaded channel set to 3.600 V measures ``3.5V``. A setpoint read back
#: therefore agrees with the one sent only to this resolution, and a
#: comparison between a measurement and a setpoint must allow for it.
VOLTAGE_READBACK_RESOLUTION = 0.1
CURRENT_READBACK_RESOLUTION = 0.01

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

#: The byte that ends every reply. Commands are sent ending in a line feed,
#: which the supply accepts; its answers end in a carriage return alone, so a
#: reader waiting for a line feed never sees one.
REPLY_TERMINATOR = b"\r"

#: Fields in a ``STATUS?`` reply, one per bit, bit 0 first.
#:
#: Firmware V1.09 separates them with spaces, reports bits 5 and 7 as ``X``,
#: and follows the eight fields with its own legend on two further lines -
#: see :data:`STATUS_LEGEND_LINES`.
STATUS_LENGTH = 8

#: Lines of legend a V1.09 supply sends after a spaced ``STATUS?`` reply::
#:
#:     bit0:(CH1)0=CC,1=CV;bit1:(CH2)0=CC,1=CV;bit23=(TRACK)01=INDEP,...;
#:     bit4:(BEEP)0=OFF,1=ON;bit6:(OUT)0=OFF,1=ON;
#:
#: They must be read, not left in the port: unread, they are taken as the
#: replies to the next two queries.
STATUS_LEGEND_LINES = 2

#: ``STATUS?`` bit positions, as the V1.09 legend gives them and as switching
#: the beeper and the output on a real supply confirms.
STATUS_BIT_BEEP = 4
STATUS_BIT_OUTPUT = 6


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


#: Bits 2 and 3 of ``STATUS?``, written as the supply's legend writes them:
#: bit 2 is the **left** digit. ``01`` - bit 2 clear, bit 3 set - is
#: independent, which is what a real supply in independent reports.
TRACKING_MODES: Dict[int, str] = {
    0b01: TrackingMode.INDEPENDENT,
    0b11: TrackingMode.SERIES,
    0b10: TrackingMode.PARALLEL,
}
