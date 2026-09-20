"""Raw TCP socket ("SCPI-RAW") transport.

.. warning::
   **The TDS3014B does not expose a raw SCPI socket.** Its Ethernet interface
   offers only the VXI-11 RPC server and the e*Scope HTTP server. This module
   exists because later Tektronix scopes that share the TDS3000 command set
   (TDS3000C, DPO/MSO2000/3000/4000) do listen on TCP port 4000, and because
   it lets the same driver be pointed at a SCPI-over-TCP simulator or a
   protocol gateway.

The important limitation of a raw socket is that it carries **no
end-of-message indication**. VXI-11 sets an END bit; a stream socket does not.
Responses therefore have to be delimited by the line terminator, and a binary
transfer with no length prefix - a hardcopy image - can only be bounded by an
inter-byte idle period. :meth:`SocketTransport.read_raw` implements that with
a configurable quiet time, which is inherently heuristic. This asymmetry is
the main technical argument for preferring VXI-11 on this instrument.

Traces to: SWE1-FR-003, SWE2-ARC-003, SWE3-DD-SOCKET.
"""

from __future__ import annotations

import logging
import socket
from typing import Optional, Tuple

from .constants import DEFAULT_RAW_SOCKET_PORT
from ..errors import ConnectionFailedError, TransportError, TransportTimeoutError
from .base import Transport

__all__ = ["SocketTransport"]

_LOG = logging.getLogger(__name__)


class SocketTransport(Transport):
    """SCPI over a bare TCP stream.

    :param host: Host name or IPv4 address.
    :param port: TCP port; 4000 on Tektronix instruments that support it.
    :param timeout: Default I/O timeout in seconds.
    :param terminator: Line terminator used to delimit responses.
    :param idle_gap: Quiet time in seconds that :meth:`read_raw` treats as the
        end of an unframed binary transfer.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_RAW_SOCKET_PORT,
        timeout: float = 10.0,
        terminator: bytes = b"\n",
        idle_gap: float = 1.0,
    ) -> None:
        super().__init__(timeout=timeout, terminator=terminator)
        if not host:
            raise ValueError("host must be a non-empty string")
        if not 0 < int(port) < 65536:
            raise ValueError("port must be in 1..65535, got %r" % (port,))
        if idle_gap <= 0.0:
            raise ValueError("idle_gap must be positive, got %r" % (idle_gap,))
        self._host = str(host)
        self._port = int(port)
        self._idle_gap = float(idle_gap)
        self._sock: Optional[socket.socket] = None

    @property
    def description(self) -> str:
        return "socket %s:%d" % (self._host, self._port)

    def _open_link(self) -> None:
        try:
            self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        except OSError as exc:
            raise ConnectionFailedError(
                "cannot connect to %s:%d: %s. Note that the TDS3014B has no raw "
                "SCPI socket; use the VXI-11 transport for that model."
                % (self._host, self._port, exc)
            ) from exc
        self._sock.settimeout(self._timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _close_link(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _send(self, data: bytes) -> None:
        if self._sock is None:
            raise TransportError("socket is not connected")
        try:
            self._sock.sendall(data)
        except OSError as exc:
            raise TransportError("failed to send %d bytes: %s" % (len(data), exc)) from exc

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if self._sock is None:
            raise TransportError("socket is not connected")
        try:
            data = self._sock.recv(max(int(max_bytes), 1))
        except socket.timeout as exc:
            raise TransportTimeoutError(
                "no data from %s within %.3f s" % (self.description, self._timeout)
            ) from exc
        except OSError as exc:
            raise TransportError("receive failed: %s" % exc) from exc
        if not data:
            # A closed stream is the only definite end-of-message a raw socket
            # can give us.
            return b"", True
        return data, False

    def read_raw(self) -> bytes:
        """Read until the instrument stops sending for ``idle_gap`` seconds.

        Used for hardcopy transfers, which carry no length prefix. The result
        is only as reliable as the idle threshold, so prefer the VXI-11
        transport when the instrument supports it.
        """
        self._require_open()
        if self._sock is None:  # pragma: no cover - guarded by _require_open
            raise TransportError("socket is not connected")

        collected = bytearray(self._buffer)
        self._reset_buffer()
        previous_timeout = self._sock.gettimeout()
        try:
            # The first chunk may take the full timeout; subsequent ones only
            # need to arrive within the idle gap.
            self._sock.settimeout(self._timeout)
            while True:
                try:
                    chunk = self._sock.recv(65536)
                except socket.timeout as exc:
                    if collected:
                        break
                    raise TransportTimeoutError(
                        "no data from %s within %.3f s" % (self.description, self._timeout)
                    ) from exc
                if not chunk:
                    break
                collected.extend(chunk)
                self._sock.settimeout(self._idle_gap)
        finally:
            self._sock.settimeout(previous_timeout)
        _LOG.debug("read %d unframed bytes from %s", len(collected), self.description)
        return bytes(collected)
