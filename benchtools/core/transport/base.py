"""Abstract instrument link.

The driver talks to the oscilloscope only through :class:`Transport`. This is
what makes the VISA question an implementation detail rather than an
architectural commitment: VXI-11, a raw socket, PyVISA and the built-in
simulator are interchangeable behind this one interface.

Concrete subclasses implement three primitives:

``_open_link`` / ``_close_link``
    Establish and tear down the underlying connection.
``_send`` 
    Push a complete message to the instrument.
``_recv_chunk``
    Return ``(data, end)`` where *end* is ``True`` when the instrument has
    signalled end-of-message (VXI-11 END bit, or terminator for byte streams).

The base class builds buffered message framing on top of those, so higher
layers can ask for "a whole response", "exactly N bytes" or "up to the
terminator" without caring which transport is underneath.

Traces to: CORE-FR-005, CORE-ARC-002, CORE-DD-TRANSPORT.
"""

from __future__ import annotations

import abc
import logging
from typing import Optional, Tuple

from ..errors import ProtocolError, TransportError, TransportTimeoutError
from .constants import DEFAULT_TERMINATOR, MAX_RESPONSE_BYTES

__all__ = ["Transport", "DEFAULT_TERMINATOR", "MAX_RESPONSE_BYTES"]

_LOG = logging.getLogger(__name__)


class Transport(abc.ABC):
    """Base class for every instrument link.

    Instances are usable as context managers::

        with Vxi11Transport("192.168.1.50") as link:
            link.write(b"*IDN?")
            print(link.read_message())

    :param timeout: Default I/O timeout in seconds.
    :param terminator: Byte sequence appended to outgoing commands and used to
        delimit responses on stream transports.
    """

    def __init__(self, timeout: float = 10.0, terminator: bytes = DEFAULT_TERMINATOR) -> None:
        if timeout <= 0.0:
            raise ValueError("timeout must be positive, got %r" % (timeout,))
        self._timeout = float(timeout)
        self._terminator = bytes(terminator)
        self._buffer = bytearray()
        self._buffer_end = False
        self._is_open = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def timeout(self) -> float:
        """Default I/O timeout in seconds."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        if value <= 0.0:
            raise ValueError("timeout must be positive, got %r" % (value,))
        self._timeout = float(value)

    @property
    def is_open(self) -> bool:
        """``True`` while the link is established."""
        return self._is_open

    @property
    def description(self) -> str:
        """Short human-readable description of the link, for logs and reports."""
        return type(self).__name__

    # ------------------------------------------------------------------
    # Primitives implemented by subclasses
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def _open_link(self) -> None:
        """Establish the underlying connection."""

    @abc.abstractmethod
    def _close_link(self) -> None:
        """Tear down the underlying connection. Must not raise."""

    @abc.abstractmethod
    def _send(self, data: bytes) -> None:
        """Transmit *data* to the instrument as one complete message."""

    @abc.abstractmethod
    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        """Receive up to *max_bytes*.

        :returns: ``(data, end)``; *end* is ``True`` when the instrument
            signalled end-of-message with this chunk.
        """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self) -> "Transport":
        """Open the link. Idempotent."""
        if not self._is_open:
            self._open_link()
            self._is_open = True
            self._reset_buffer()
            _LOG.debug("opened %s", self.description)
        return self

    def close(self) -> None:
        """Close the link. Idempotent and never raises."""
        if self._is_open:
            try:
                self._close_link()
            except Exception:  # pragma: no cover - defensive
                _LOG.warning("error while closing %s", self.description, exc_info=True)
            finally:
                self._is_open = False
                self._reset_buffer()
                _LOG.debug("closed %s", self.description)

    def __enter__(self) -> "Transport":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    # ------------------------------------------------------------------
    # Buffered I/O
    # ------------------------------------------------------------------
    def _reset_buffer(self) -> None:
        self._buffer = bytearray()
        self._buffer_end = False

    def _require_open(self) -> None:
        if not self._is_open:
            raise TransportError("%s is not open" % self.description)

    def _fill(self, max_bytes: int = 65536) -> None:
        """Pull one more chunk from the instrument into the receive buffer."""
        if self._buffer_end:
            return
        data, end = self._recv_chunk(max_bytes)
        if data:
            self._buffer.extend(data)
        if end:
            self._buffer_end = True
        if not data and not end:
            raise TransportTimeoutError(
                "%s returned no data before the timeout elapsed" % self.description
            )
        if len(self._buffer) > MAX_RESPONSE_BYTES:
            raise ProtocolError(
                "response exceeded %d bytes without end-of-message" % MAX_RESPONSE_BYTES
            )

    def write(self, data: bytes, append_terminator: bool = True) -> None:
        """Send *data* to the instrument.

        Any unread bytes from a previous response are discarded first: a stale
        response would otherwise be mistaken for the answer to this command.
        """
        self._require_open()
        if isinstance(data, str):
            data = data.encode("ascii")
        payload = bytes(data)
        if append_terminator and self._terminator and not payload.endswith(self._terminator):
            payload += self._terminator
        if self._buffer:
            _LOG.debug("discarding %d stale bytes before write", len(self._buffer))
        self._reset_buffer()
        self._send(payload)

    def read_message(self, strip_terminator: bool = True) -> bytes:
        """Read one complete response.

        For VXI-11 this reads until the END bit; for byte-stream transports it
        reads until the terminator is seen.
        """
        self._require_open()
        while not self._buffer_end:
            index = self._buffer.find(self._terminator) if self._terminator else -1
            if index >= 0:
                break
            self._fill()
        if self._terminator:
            index = self._buffer.find(self._terminator)
            if index >= 0:
                end = index + len(self._terminator) if not strip_terminator else index
                message = bytes(self._buffer[:end])
                del self._buffer[: index + len(self._terminator)]
                if not self._buffer:
                    self._buffer_end = False
                return message
        message = bytes(self._buffer)
        self._reset_buffer()
        if strip_terminator:
            message = message.rstrip(self._terminator)
        return message

    def read_exactly(self, count: int) -> bytes:
        """Read exactly *count* bytes, regardless of message framing.

        Used for IEEE 488.2 definite-length blocks, whose payload may legally
        contain the terminator byte.
        """
        self._require_open()
        if count < 0:
            raise ValueError("count must not be negative, got %r" % (count,))
        while len(self._buffer) < count:
            if self._buffer_end:
                raise ProtocolError(
                    "instrument ended the response after %d of %d expected bytes"
                    % (len(self._buffer), count)
                )
            self._fill(max(count - len(self._buffer), 4096))
        data = bytes(self._buffer[:count])
        del self._buffer[:count]
        return data

    def read_raw(self) -> bytes:
        """Read the remainder of the current response, including terminators.

        Required for hardcopy transfers, where the instrument streams a binary
        image with no length prefix and no usable terminator.
        """
        self._require_open()
        while not self._buffer_end:
            self._fill()
        data = bytes(self._buffer)
        self._reset_buffer()
        return data

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def query(self, command: bytes) -> bytes:
        """Send *command* and return the single response message."""
        self.write(command)
        return self.read_message()

    def clear(self) -> None:
        """Clear the instrument's input and output buffers.

        The default implementation is a no-op; transports that support a device
        clear (VXI-11) override it.
        """

    def read_stb(self) -> int:
        """Read the IEEE 488.2 status byte.

        The default implementation falls back to the ``*STB?`` query, which is
        valid on every transport.
        """
        response = self.query(b"*STB?")
        try:
            return int(response.strip())
        except ValueError as exc:
            raise ProtocolError("unparsable *STB? response %r" % response) from exc

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        state = "open" if self._is_open else "closed"
        return "<%s %s>" % (self.description, state)
