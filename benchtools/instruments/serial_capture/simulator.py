"""A simulated device whose serial output the capture instrument records.

The capture instrument only listens, so the simulator only talks: a script of
lines, one every *interval* seconds of real time, starting when a capture
starts. That is what a device powered on just after the capture started does,
which is how a bench test of power-on output runs.

Traces to: SER-FR-010, SER-DD-SIM.
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence

__all__ = ["SimulatedSerialDevice", "DEFAULT_SCRIPT", "DEFAULT_INTERVAL"]

#: What the simulated device says when a bench gives no ``simulated_lines``.
DEFAULT_SCRIPT = (
    "BOOT V1.00.0000",
    "SELF TEST START",
    "VBAT = 3.30 V",
    "SELF TEST PASS",
)

#: Seconds between two lines of the script.
DEFAULT_INTERVAL = 0.05


class SimulatedSerialDevice:
    """A device that prints a fixed script of lines on its serial port.

    :param lines: The script, in order. Each is sent with a ``\\r\\n`` ending,
        as most device consoles do.
    :param interval: Seconds from the start of a capture to the first line,
        and between lines.
    """

    def __init__(self, lines: Optional[Sequence[str]] = None,
                 interval: float = DEFAULT_INTERVAL) -> None:
        self.lines: List[str] = list(DEFAULT_SCRIPT if lines is None else lines)
        self.interval = float(interval)
        if self.interval < 0:
            raise ValueError("the interval between simulated lines cannot be negative")
        self._started_at: Optional[float] = None
        self._sent = 0
        #: Bytes written to the port. The instrument writes nothing; a test
        #: asserts this stays empty.
        self.received = bytearray()

    def restart(self) -> None:
        """Start the script again: the device has just been powered on."""
        self._started_at = time.monotonic()
        self._sent = 0

    @property
    def sent(self) -> int:
        """Lines sent since the last :meth:`restart`."""
        return self._sent

    def respond(self, message: bytes) -> Optional[bytes]:
        """The device ignores anything written to it."""
        self.received.extend(message)

    def poll(self) -> bytes:
        """The next line of the script, once it is due, or ``b""``."""
        if self._started_at is None or self._sent >= len(self.lines):
            return b""
        due = self._started_at + (self._sent + 1) * self.interval
        if time.monotonic() < due:
            return b""
        line = self.lines[self._sent]
        self._sent += 1
        return line.encode("ascii", errors="replace") + b"\r\n"
