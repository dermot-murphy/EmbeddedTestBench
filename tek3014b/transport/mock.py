"""In-process transport backed by :class:`~tek3014b.simulator.SimulatedTDS3014B`.

Deliberately returns responses in small chunks so that the message framing and
buffering in :class:`~tek3014b.transport.base.Transport` are exercised rather
than bypassed.

Traces to: SWE2-ARC-006, SWE4-UT-ENV.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ..errors import TransportError
from ..simulator import SimulatedTDS3014B
from .base import Transport

__all__ = ["MockTransport"]


class MockTransport(Transport):
    """Loopback link to a simulated instrument.

    :param simulator: Instrument model to drive; a default one is created when
        omitted.
    :param chunk_size: Maximum bytes returned per ``_recv_chunk`` call.
    """

    def __init__(
        self,
        simulator: Optional[SimulatedTDS3014B] = None,
        timeout: float = 10.0,
        chunk_size: int = 1024,
    ) -> None:
        super().__init__(timeout=timeout)
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1, got %r" % (chunk_size,))
        self.simulator = simulator or SimulatedTDS3014B()
        self._chunk_size = int(chunk_size)
        self._pending = bytearray()
        self._has_reply = False

    @property
    def description(self) -> str:
        return "simulated TDS3014B"

    def _open_link(self) -> None:
        self._pending = bytearray()
        self._has_reply = False

    def _close_link(self) -> None:
        self._pending = bytearray()
        self._has_reply = False

    def _send(self, data: bytes) -> None:
        reply = self.simulator.respond(data)
        self._pending = bytearray(reply or b"")
        self._has_reply = reply is not None

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if not self._has_reply:
            raise TransportError(
                "the simulated instrument has no response pending; the last "
                "command was not a query"
            )
        take = min(int(max_bytes), self._chunk_size, len(self._pending))
        chunk = bytes(self._pending[:take])
        del self._pending[:take]
        end = not self._pending
        if end:
            self._has_reply = False
        return chunk, end

    def clear(self) -> None:
        """Discard any pending simulated response."""
        self._pending = bytearray()
        self._has_reply = False
        self._reset_buffer()
