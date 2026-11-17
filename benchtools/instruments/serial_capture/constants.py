"""What the serial capture instrument's command set allows, and its defaults.

The command set is the Kepler BLE console's form (#247): ``RD``, ``WR`` and
``ROUTINE`` commands, one per line, answered ``ACK <command> = <value>``,
``ACK <command> [<unit>]`` or ``NACK <command> <REASON>``. The routine verbs
and statuses are those of the owner's UDS-style routine design (#202).

Traces to: SER-FR-002 .. SER-FR-005, SER-DD-CONST.
"""

from __future__ import annotations

from typing import Tuple

__all__ = [
    "MANUFACTURER",
    "MODEL",
    "DEFAULT_BAUDRATE",
    "DEFAULT_FORMAT",
    "DEFAULT_WINDOW_MS",
    "DEFAULT_TIMEOUT",
    "BAUD_RANGE",
    "WINDOW_RANGE_MS",
    "DATA_BITS",
    "PARITIES",
    "STOP_BITS",
    "MAX_LINES",
    "READ_POLL",
    "IDLE_SLEEP",
    "ROUTINE_CAPTURE",
    "NOT_STARTED",
    "RUNNING",
    "ABORTED",
    "COMPLETE",
    "STATUSES",
    "ON",
    "OFF",
    "PATTERN_OFF",
    "INVALID_COMMAND",
    "INVALID_VALUE",
    "OUT_OF_RANGE",
    "BUSY",
    "NOT_FOUND",
    "LINE_PREFIX",
]

#: Who makes it: the bench itself. The instrument is a host-side driver for
#: any device's serial output, so it has no manufacturer of its own.
MANUFACTURER = "EmbeddedTestBench"

#: The model name ``identify()`` reports.
MODEL = "Serial capture"

#: Line rate when none is given: the rate most device consoles use.
DEFAULT_BAUDRATE = 115200

#: Character format when none is given: 8 data bits, no parity, 1 stop bit.
DEFAULT_FORMAT = "8N1"

#: How long a capture runs, in milliseconds, when no pattern ends it first.
DEFAULT_WINDOW_MS = 5000

#: Seconds a driver call waits for the port before giving up.
DEFAULT_TIMEOUT = 2.0

#: Line rates ``WR BAUD`` accepts, inclusive. Wider than any bench adapter
#: needs; a rate the adapter cannot do is refused by the port when it opens.
BAUD_RANGE: Tuple[int, int] = (50, 4000000)

#: Capture windows ``WR WINDOW`` accepts, in milliseconds, inclusive.
WINDOW_RANGE_MS: Tuple[int, int] = (1, 3600000)

#: The parts of a ``WR FORMAT`` value such as ``8N1`` or ``7E2``.
DATA_BITS = (5, 6, 7, 8)
PARITIES = ("N", "E", "O", "M", "S")
STOP_BITS = (1, 2)

#: Lines one capture keeps. Older lines are dropped beyond this, and the count
#: still counts them, so a flood cannot exhaust memory.
MAX_LINES = 100000

#: Seconds one read of the port waits. Set on the transport once and left
#: there: reconfiguring a serial port per read loses bytes on Windows, as
#: the S2-LP session found (``s2lp/session.py``, ``_read_line``).
READ_POLL = 0.05

#: Seconds to sleep when a link with nothing pending says so at once (the
#: simulator), so the reader does not spin.
IDLE_SLEEP = 0.01

#: The one routine this instrument runs.
ROUTINE_CAPTURE = "CAPTURE"

#: Routine statuses, as ``ROUTINE RESULTS`` reports them (#202).
NOT_STARTED = "Not Started"
RUNNING = "Running"
ABORTED = "Aborted"
COMPLETE = "Complete"
STATUSES = (NOT_STARTED, RUNNING, ABORTED, COMPLETE)

#: ``WR LINES`` values.
ON = "ON"
OFF = "OFF"

#: ``WR PATTERN OFF`` clears the pattern: the capture then runs its window.
PATTERN_OFF = "OFF"

#: ``NACK`` replies, in the Kepler console's words.
INVALID_COMMAND = "NACK Invalid Command"
INVALID_VALUE = "INVALID VALUE"
OUT_OF_RANGE = "OUT OF RANGE"
BUSY = "BUSY"
NOT_FOUND = "NOT FOUND"

#: How a captured line is shown while ``WR LINES ON``: ``LINE 3 = <text>``.
LINE_PREFIX = "LINE"
