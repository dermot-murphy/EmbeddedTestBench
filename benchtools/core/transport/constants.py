"""Protocol-level constants for the instrument link.

These describe the *transports*, not any particular instrument, which is why
they live here rather than in an instrument's own constants module.

Traces to: CORE-FR-001, CORE-FR-003, CORE-DD-TRANSPORT.
"""

from __future__ import annotations

from typing import Tuple

__all__ = [
    "DEFAULT_VXI11_DEVICE_NAMES",
    "DEFAULT_RAW_SOCKET_PORT",
    "SCPI_RAW_SOCKET_PORT",
    "DEFAULT_TERMINATOR",
    "MAX_RESPONSE_BYTES",
]

#: VXI-11 logical device names tried, in order, when opening a link.
#:
#: The VXI-11 specification constrains the name to ``inst<n>`` for VXI-11.3
#: (instrument) devices and ``gpib<n>,<m>`` for VXI-11.2 (GPIB emulation)
#: devices. Instruments differ, and some families differ between firmware
#: revisions, so the transport probes rather than assuming.
DEFAULT_VXI11_DEVICE_NAMES: Tuple[str, ...] = ("inst0", "gpib0,1", "hpib,7", "inst")

#: Port used by Tektronix instruments that expose a raw SCPI socket.
DEFAULT_RAW_SOCKET_PORT = 4000

#: The port registered for SCPI-RAW, used by most other vendors.
SCPI_RAW_SOCKET_PORT = 5025

#: Default end-of-message terminator for SCPI responses.
DEFAULT_TERMINATOR = b"\n"

#: Upper bound on a single buffered response, guarding against a runaway read
#: if an instrument never asserts end-of-message. 64 MiB comfortably exceeds
#: any oscilloscope hardcopy or full-record capture.
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
