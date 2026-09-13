"""In-process transport backed by any :class:`~benchtools.core.simulator.Responder`.

This is the seam that lets every driver in the repository be tested without
hardware. It deliberately returns responses in small chunks, so that the
message framing and buffering in
:class:`~benchtools.core.transport.base.Transport` are exercised rather than
bypassed.

The transport accepts *any* object with a ``respond(bytes) -> bytes | None``
method. It has no knowledge of which instrument is being simulated, which is
what keeps this layer reusable: an instrument driver supplies its own
simulator (see ``ScpiInstrument.SIMULATOR_CLASS``), rather than the transport
importing one.

A simulator that also implements ``poll() -> bytes`` (see
:class:`~benchtools.core.simulator.Streamer`) can speak without being spoken
to, which is what an instrument that streams events needs: the transport calls
``poll()`` when the driver reads and no reply is outstanding.

Traces to: CORE-FR-004, CORE-FR-041, CORE-DD-MOCK.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ..errors import TransportError
from ..simulator import Responder, SimulatedInstrument
from .base import Transport

__all__ = ["MockTransport"]


class MockTransport(Transport):
    """Loopback link to an in-process instrument model.

    :param responder: The instrument model to drive. Defaults to a bare
        :class:`~benchtools.core.simulator.SimulatedInstrument`, which answers
        only the IEEE 488.2 mandated queries - enough for a plain ``sim://``
        resource to be meaningful without naming a model.
    :param timeout: Nominal I/O timeout, for interface compatibility.
    :param chunk_size: Maximum bytes returned per receive, so that chunk
        reassembly is exercised.
    """

    def __init__(
        self,
        responder: Optional[Responder] = None,
        timeout: float = 10.0,
        chunk_size: int = 1024,
    ) -> None:
        super().__init__(timeout=timeout)
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1, got %r" % (chunk_size,))
        self.responder: Responder = responder if responder is not None else SimulatedInstrument()
        self._chunk_size = int(chunk_size)
        self._pending = bytearray()
        self._has_reply = False

    @property
    def simulator(self) -> Responder:
        """Alias for :attr:`responder`, read naturally from a test."""
        return self.responder

    @property
    def description(self) -> str:
        model = getattr(self.responder, "idn", None)
        if isinstance(model, str):
            fields = model.split(",")
            if len(fields) > 1:
                return "simulated %s" % fields[1].strip()
        return "simulated instrument"

    def _open_link(self) -> None:
        self._pending = bytearray()
        self._has_reply = False

    def _close_link(self) -> None:
        self._pending = bytearray()
        self._has_reply = False

    def _send(self, data: bytes) -> None:
        reply = self.responder.respond(data)
        self._pending = bytearray(reply or b"")
        self._has_reply = reply is not None

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if not self._has_reply:
            # Nothing was asked for. An instrument that streams events may still
            # have something to say, so give it the chance before reporting that
            # the read has nothing to return.
            streamed = self._poll_responder()
            if streamed:
                self._pending = bytearray(streamed)
                self._has_reply = True
            else:
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

    def _poll_responder(self) -> bytes:
        """Ask a streaming simulator for unsolicited output."""
        poll = getattr(self.responder, "poll", None)
        if poll is None:
            return b""
        produced = poll()
        return bytes(produced or b"")

    def clear(self) -> None:
        """Discard any pending simulated response."""
        self._pending = bytearray()
        self._has_reply = False
        self._reset_buffer()
