"""Serial capture instrument: record the lines a device prints on a serial port.

A host-side instrument with no hardware of its own beyond a USB serial
adapter. It captures a device's console or test UART for a window or until a
line matches a pattern, logs every line, and gives a test the count, the
matching line and a value from it. It is controlled with ``RD``, ``WR`` and
``ROUTINE`` commands in the Kepler console's form (#247).

Traces to: SER-FR-001 .. SER-FR-013, SER-ARC-001.
"""

from .capture import (
    CaptureBusyError,
    CapturedLine,
    CaptureResult,
    SerialCapture,
    parse_format,
)
from .console import Reply, execute
from .constants import (
    ABORTED,
    COMPLETE,
    DEFAULT_BAUDRATE,
    DEFAULT_FORMAT,
    DEFAULT_WINDOW_MS,
    MODEL,
    NOT_STARTED,
    RUNNING,
)
from .simulator import SimulatedSerialDevice

__all__ = [
    "SerialCapture",
    "SimulatedSerialDevice",
    "CaptureResult",
    "CapturedLine",
    "CaptureBusyError",
    "Reply",
    "execute",
    "parse_format",
    "MODEL",
    "DEFAULT_BAUDRATE",
    "DEFAULT_FORMAT",
    "DEFAULT_WINDOW_MS",
    "NOT_STARTED",
    "RUNNING",
    "ABORTED",
    "COMPLETE",
]
