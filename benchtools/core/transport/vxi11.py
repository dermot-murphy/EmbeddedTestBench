"""Pure-Python VXI-11 (TCP/IP Instrument Protocol) transport.

The TDS3014B's Ethernet interface is an ONC-RPC server implementing the
VXI-11 core channel. VXI-11 is a published open specification (VXIbus
Consortium VXI-11 / VXI-11.2 / VXI-11.3), so a VISA implementation is a
*convenience*, not a requirement: this module speaks the protocol directly
over the standard library's ``socket`` and ``struct``.

Wire format, outermost to innermost:

1. **ONC-RPC record marking** (RFC 5531 §11) on TCP: a 4-byte header whose
   top bit marks the last fragment and whose low 31 bits give the length.
2. **RPC message**: xid, CALL/REPLY, program 0x0607AF (395183) version 1,
   ``AUTH_NULL`` credentials.
3. **XDR-encoded VXI-11 arguments** (RFC 4506): everything is big-endian and
   padded to a 4-byte boundary.

The port of the core channel is discovered from the instrument's portmapper
(program 100000, version 2, procedure ``GETPORT``) on port 111, over TCP with
a UDP fallback for firmware that only answers the datagram form.

Traces to: SWE1-FR-001, SWE1-FR-002, SWE2-ARC-003, SWE3-DD-VXI11.
"""

from __future__ import annotations

import logging
import random
import socket
import struct
from typing import Optional, Sequence, Tuple

from .constants import DEFAULT_VXI11_DEVICE_NAMES
from ..errors import (
    ConnectionFailedError,
    ProtocolError,
    TransportError,
    TransportTimeoutError,
)
from .base import Transport

__all__ = ["Vxi11Transport", "Vxi11Error"]

_LOG = logging.getLogger(__name__)

# --- ONC-RPC ---------------------------------------------------------------
_RPC_VERSION = 2
_MSG_CALL = 0
_MSG_REPLY = 1
_MSG_ACCEPTED = 0
_MSG_DENIED = 1
_ACCEPT_SUCCESS = 0
_AUTH_NULL = 0
_LAST_FRAGMENT = 0x80000000
_FRAGMENT_MASK = 0x7FFFFFFF

_ACCEPT_STAT_TEXT = {
    1: "program unavailable",
    2: "program version mismatch",
    3: "procedure unavailable",
    4: "garbage arguments",
    5: "system error",
}

# --- Portmapper ------------------------------------------------------------
_PMAP_PORT = 111
_PMAP_PROG = 100000
_PMAP_VERS = 2
_PMAP_GETPORT = 3
_IPPROTO_TCP = 6

# --- VXI-11 core channel ---------------------------------------------------
_CORE_PROG = 0x0607AF
_CORE_VERS = 1

_CREATE_LINK = 10
_DEVICE_WRITE = 11
_DEVICE_READ = 12
_DEVICE_READSTB = 13
_DEVICE_TRIGGER = 14
_DEVICE_CLEAR = 15
_DEVICE_REMOTE = 16
_DEVICE_LOCAL = 17
_DEVICE_LOCK = 18
_DEVICE_UNLOCK = 19
_DESTROY_LINK = 23

#: Operation flags (VXI-11 §B.5).
_FLAG_WAIT_LOCK = 0x01
_FLAG_END = 0x08
_FLAG_TERMCHRSET = 0x80

#: ``device_read`` termination reasons (VXI-11 §B.6).
_REASON_REQCNT = 0x01
_REASON_CHR = 0x02
_REASON_END = 0x04

#: VXI-11 error codes (VXI-11 §B.4).
_VXI11_ERRORS = {
    0: "no error",
    1: "syntax error",
    3: "device not accessible",
    4: "invalid link identifier",
    5: "parameter error",
    6: "channel not established",
    8: "operation not supported",
    9: "out of resources",
    11: "device locked by another link",
    12: "no lock held by this link",
    15: "I/O timeout",
    17: "I/O error",
    21: "invalid address",
    23: "abort",
    29: "channel already established",
}

_ERR_IO_TIMEOUT = 15
_ERR_INVALID_LINK = 4


class Vxi11Error(TransportError):
    """The instrument's VXI-11 server returned a non-zero error code."""

    def __init__(self, code: int, operation: str) -> None:
        self.code = int(code)
        self.operation = operation
        super().__init__(
            "VXI-11 %s failed: error %d (%s)"
            % (operation, code, _VXI11_ERRORS.get(code, "unknown error"))
        )


# ---------------------------------------------------------------------------
# Minimal XDR codec
# ---------------------------------------------------------------------------
class _Packer:
    """Builds an XDR byte stream (RFC 4506)."""

    __slots__ = ("_buf",)

    def __init__(self) -> None:
        self._buf = bytearray()

    def uint(self, value: int) -> "_Packer":
        self._buf += struct.pack(">I", value & 0xFFFFFFFF)
        return self

    def int(self, value: int) -> "_Packer":
        self._buf += struct.pack(">i", value)
        return self

    def bool(self, value: bool) -> "_Packer":
        return self.uint(1 if value else 0)

    def opaque(self, data: bytes) -> "_Packer":
        self.uint(len(data))
        self._buf += data
        self._buf += b"\x00" * ((-len(data)) % 4)
        return self

    def string(self, text: str) -> "_Packer":
        return self.opaque(text.encode("ascii"))

    def bytes(self) -> bytes:
        return bytes(self._buf)


class _Unpacker:
    """Reads an XDR byte stream (RFC 4506)."""

    __slots__ = ("_data", "_pos")

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def _take(self, count: int) -> bytes:
        end = self._pos + count
        if end > len(self._data):
            raise ProtocolError(
                "truncated XDR stream: wanted %d bytes at offset %d of %d"
                % (count, self._pos, len(self._data))
            )
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def uint(self) -> int:
        return struct.unpack(">I", self._take(4))[0]

    def int(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def opaque(self) -> bytes:
        length = self.uint()
        data = self._take(length)
        self._take((-length) % 4)  # discard padding
        return data

    def skip_opaque(self) -> None:
        self.opaque()


# ---------------------------------------------------------------------------
# RPC helpers
# ---------------------------------------------------------------------------
def _recv_exactly(sock: socket.socket, count: int) -> bytes:
    """Receive exactly *count* bytes or raise."""
    chunks = []
    remaining = count
    while remaining > 0:
        try:
            chunk = sock.recv(remaining)
        except socket.timeout as exc:
            raise TransportTimeoutError("timed out reading from instrument") from exc
        if not chunk:
            raise ConnectionFailedError("instrument closed the connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _rpc_call_body(xid: int, prog: int, vers: int, proc: int, args: bytes) -> bytes:
    """Build a complete ONC-RPC CALL message with ``AUTH_NULL`` credentials."""
    packer = _Packer()
    packer.uint(xid).int(_MSG_CALL).uint(_RPC_VERSION)
    packer.uint(prog).uint(vers).uint(proc)
    packer.uint(_AUTH_NULL).uint(0)  # credentials
    packer.uint(_AUTH_NULL).uint(0)  # verifier
    return packer.bytes() + args


def _parse_rpc_reply(message: bytes, xid: int) -> _Unpacker:
    """Validate an RPC REPLY and return an unpacker positioned at the results."""
    unpacker = _Unpacker(message)
    reply_xid = unpacker.uint()
    if reply_xid != xid:
        raise ProtocolError("RPC transaction id mismatch: sent %d, got %d" % (xid, reply_xid))
    if unpacker.int() != _MSG_REPLY:
        raise ProtocolError("expected an RPC REPLY message")
    reply_stat = unpacker.int()
    if reply_stat == _MSG_DENIED:
        raise ProtocolError("instrument rejected the RPC call (authentication or version)")
    if reply_stat != _MSG_ACCEPTED:
        raise ProtocolError("unknown RPC reply status %d" % reply_stat)
    unpacker.uint()  # verifier flavour
    unpacker.skip_opaque()  # verifier body
    accept_stat = unpacker.int()
    if accept_stat != _ACCEPT_SUCCESS:
        raise ProtocolError(
            "RPC call not accepted: %s" % _ACCEPT_STAT_TEXT.get(accept_stat, "status %d" % accept_stat)
        )
    return unpacker


def _rpc_tcp(sock: socket.socket, xid: int, prog: int, vers: int, proc: int, args: bytes) -> _Unpacker:
    """Perform one RPC call over a record-marked TCP stream."""
    body = _rpc_call_body(xid, prog, vers, proc, args)
    sock.sendall(struct.pack(">I", len(body) | _LAST_FRAGMENT) + body)

    fragments = []
    while True:
        header = struct.unpack(">I", _recv_exactly(sock, 4))[0]
        length = header & _FRAGMENT_MASK
        fragments.append(_recv_exactly(sock, length) if length else b"")
        if header & _LAST_FRAGMENT:
            break
    return _parse_rpc_reply(b"".join(fragments), xid)


def _rpc_udp(address: Tuple[str, int], xid: int, prog: int, vers: int,
             proc: int, args: bytes, timeout: float) -> _Unpacker:
    """Perform one RPC call over UDP (used only for the portmapper fallback)."""
    body = _rpc_call_body(xid, prog, vers, proc, args)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.sendto(body, address)
        try:
            reply, _ = sock.recvfrom(8192)
        except socket.timeout as exc:
            raise TransportTimeoutError("portmapper did not answer over UDP") from exc
    finally:
        sock.close()
    return _parse_rpc_reply(reply, xid)


def _next_xid() -> int:
    return random.randint(1, 0x7FFFFFFF)


def query_portmapper(host: str, prog: int = _CORE_PROG, vers: int = _CORE_VERS,
                     timeout: float = 5.0) -> int:
    """Ask *host*'s portmapper which TCP port serves *prog*/*vers*.

    TCP is tried first because it gives a clearer failure mode; instruments
    that only implement the datagram portmapper are handled by the UDP
    fallback.

    :returns: The TCP port number.
    :raises ConnectionFailedError: if the program is not registered or the
        portmapper cannot be reached by either transport.
    """
    args = _Packer().uint(prog).uint(vers).uint(_IPPROTO_TCP).uint(0).bytes()

    tcp_error: Optional[Exception] = None
    try:
        sock = socket.create_connection((host, _PMAP_PORT), timeout=timeout)
        try:
            sock.settimeout(timeout)
            xid = _next_xid()
            port = _rpc_tcp(sock, xid, _PMAP_PROG, _PMAP_VERS, _PMAP_GETPORT, args).uint()
        finally:
            sock.close()
        if port:
            _LOG.debug("portmapper (TCP) mapped %#x/%d to port %d", prog, vers, port)
            return port
        tcp_error = ConnectionFailedError("portmapper reports program %#x is not registered" % prog)
    except (OSError, TransportError) as exc:
        tcp_error = exc

    try:
        port = _rpc_udp((host, _PMAP_PORT), _next_xid(), _PMAP_PROG, _PMAP_VERS,
                        _PMAP_GETPORT, args, timeout).uint()
    except (OSError, TransportError) as exc:
        raise ConnectionFailedError(
            "cannot reach the portmapper on %s:%d (TCP: %s; UDP: %s)"
            % (host, _PMAP_PORT, tcp_error, exc)
        ) from exc

    if not port:
        raise ConnectionFailedError(
            "portmapper on %s does not have VXI-11 program %#x registered; "
            "check that the instrument's Ethernet interface is enabled" % (host, prog)
        )
    _LOG.debug("portmapper (UDP) mapped %#x/%d to port %d", prog, vers, port)
    return port


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
class Vxi11Transport(Transport):
    """VXI-11 instrument link implemented without VISA.

    :param host: Host name or IPv4 address of the oscilloscope.
    :param device_names: Logical device names to try with ``create_link``.
        The default probes the VXI-11.3 name (``inst0``) then the VXI-11.2
        GPIB-emulation names, because TDS3000B firmware revisions differ in
        which they accept.
    :param timeout: Default I/O timeout in seconds.
    :param core_port: Bypass the portmapper and use this core-channel port.
    :param lock_device: Request an exclusive lock on the instrument when the
        link is created, so another client cannot change settings mid-sequence.
    :param lock_timeout: Time in seconds the instrument waits for a lock.
    """

    def __init__(
        self,
        host: str,
        device_names: Sequence[str] = DEFAULT_VXI11_DEVICE_NAMES,
        timeout: float = 10.0,
        core_port: Optional[int] = None,
        lock_device: bool = False,
        lock_timeout: float = 5.0,
        client_id: Optional[int] = None,
    ) -> None:
        super().__init__(timeout=timeout)
        if not host:
            raise ValueError("host must be a non-empty string")
        self._host = str(host)
        self._device_names = tuple(device_names)
        if not self._device_names:
            raise ValueError("device_names must contain at least one entry")
        self._core_port = core_port
        self._lock_device = bool(lock_device)
        self._lock_timeout_ms = max(int(lock_timeout * 1000.0), 0)
        self._client_id = int(client_id) if client_id is not None else _next_xid()

        self._sock: Optional[socket.socket] = None
        self._link_id: Optional[int] = None
        self._max_recv_size = 4096
        self._device_name: Optional[str] = None

    # ------------------------------------------------------------------
    @property
    def host(self) -> str:
        """Host name or address of the instrument."""
        return self._host

    @property
    def device_name(self) -> Optional[str]:
        """Logical device name that ``create_link`` accepted, once open."""
        return self._device_name

    @property
    def max_recv_size(self) -> int:
        """Largest ``device_write`` payload the instrument will accept."""
        return self._max_recv_size

    @property
    def description(self) -> str:
        return "VXI-11 %s::%s" % (self._host, self._device_name or "<unlinked>")

    # ------------------------------------------------------------------
    # RPC plumbing
    # ------------------------------------------------------------------
    def _call(self, proc: int, args: bytes) -> _Unpacker:
        if self._sock is None:
            raise TransportError("VXI-11 core channel is not connected")
        try:
            return _rpc_tcp(self._sock, _next_xid(), _CORE_PROG, _CORE_VERS, proc, args)
        except socket.timeout as exc:
            raise TransportTimeoutError("VXI-11 RPC timed out (procedure %d)" % proc) from exc
        except OSError as exc:
            raise TransportError("VXI-11 RPC failed (procedure %d): %s" % (proc, exc)) from exc

    def _check(self, code: int, operation: str) -> None:
        if code == 0:
            return
        if code == _ERR_IO_TIMEOUT:
            raise TransportTimeoutError(
                "instrument reported an I/O timeout during %s; the command may "
                "be unsupported or the acquisition is still in progress" % operation
            )
        if code == _ERR_INVALID_LINK:
            self._link_id = None
            raise ConnectionFailedError("VXI-11 link was dropped by the instrument")
        raise Vxi11Error(code, operation)

    @property
    def _io_timeout_ms(self) -> int:
        return max(int(self._timeout * 1000.0), 1)

    # ------------------------------------------------------------------
    # Transport primitives
    # ------------------------------------------------------------------
    def _open_link(self) -> None:
        port = self._core_port or query_portmapper(self._host, timeout=self._timeout)
        try:
            self._sock = socket.create_connection((self._host, port), timeout=self._timeout)
        except OSError as exc:
            raise ConnectionFailedError(
                "cannot open the VXI-11 core channel to %s:%d: %s" % (self._host, port, exc)
            ) from exc
        self._sock.settimeout(self._timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        failures = []
        for name in self._device_names:
            args = (
                _Packer()
                .int(self._client_id)
                .bool(self._lock_device)
                .uint(self._lock_timeout_ms)
                .string(name)
                .bytes()
            )
            reply = self._call(_CREATE_LINK, args)
            error = reply.int()
            link_id = reply.int()
            reply.uint()  # abort channel port, unused: the driver never aborts
            max_recv = reply.uint()
            if error == 0:
                self._link_id = link_id
                self._device_name = name
                # Leave headroom for the RPC envelope, and never trust a zero.
                self._max_recv_size = max(min(max_recv, 1024 * 1024), 512) if max_recv else 4096
                _LOG.info("VXI-11 link established to %s as %r", self._host, name)
                return
            failures.append("%s: error %d (%s)" % (name, error, _VXI11_ERRORS.get(error, "unknown")))

        self._close_link()
        raise ConnectionFailedError(
            "the instrument at %s refused every logical device name (%s). "
            "Override device_names if this instrument uses a different one."
            % (self._host, "; ".join(failures))
        )

    def _close_link(self) -> None:
        if self._sock is not None:
            if self._link_id is not None:
                try:
                    self._call(_DESTROY_LINK, _Packer().int(self._link_id).bytes())
                except (TransportError, OSError):
                    _LOG.debug("destroy_link failed; closing the socket anyway", exc_info=True)
            try:
                self._sock.close()
            finally:
                self._sock = None
        self._link_id = None
        self._device_name = None

    def _send(self, data: bytes) -> None:
        if self._link_id is None:
            raise TransportError("VXI-11 link is not established")
        view = memoryview(data)
        total = len(data)
        offset = 0
        # An empty write still has to be sent so the instrument sees END.
        while True:
            chunk = bytes(view[offset : offset + self._max_recv_size])
            offset += len(chunk)
            last = offset >= total
            flags = _FLAG_END if last else 0
            args = (
                _Packer()
                .int(self._link_id)
                .uint(self._io_timeout_ms)
                .uint(self._lock_timeout_ms)
                .int(flags)
                .opaque(chunk)
                .bytes()
            )
            reply = self._call(_DEVICE_WRITE, args)
            self._check(reply.int(), "device_write")
            written = reply.uint()
            if written != len(chunk):
                raise ProtocolError(
                    "instrument accepted %d of %d bytes" % (written, len(chunk))
                )
            if last:
                return

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if self._link_id is None:
            raise TransportError("VXI-11 link is not established")
        request = max(min(int(max_bytes), 1024 * 1024), 1)
        args = (
            _Packer()
            .int(self._link_id)
            .uint(request)
            .uint(self._io_timeout_ms)
            .uint(self._lock_timeout_ms)
            .int(0)  # no termination character: framing is done by the caller
            .uint(0)
            .bytes()
        )
        reply = self._call(_DEVICE_READ, args)
        self._check(reply.int(), "device_read")
        reason = reply.int()
        data = reply.opaque()
        return data, bool(reason & _REASON_END)

    # ------------------------------------------------------------------
    # Optional VXI-11 services
    # ------------------------------------------------------------------
    def _generic(self, proc: int, operation: str) -> _Unpacker:
        if self._link_id is None:
            raise TransportError("VXI-11 link is not established")
        args = (
            _Packer()
            .int(self._link_id)
            .int(0)
            .uint(self._lock_timeout_ms)
            .uint(self._io_timeout_ms)
            .bytes()
        )
        reply = self._call(proc, args)
        self._check(reply.int(), operation)
        return reply

    def clear(self) -> None:
        """Issue a VXI-11 ``device_clear`` (the equivalent of GPIB DCL)."""
        self._generic(_DEVICE_CLEAR, "device_clear")
        self._reset_buffer()

    def trigger(self) -> None:
        """Issue a VXI-11 ``device_trigger`` (the equivalent of GPIB GET)."""
        self._generic(_DEVICE_TRIGGER, "device_trigger")

    def remote(self) -> None:
        """Place the instrument in remote state."""
        self._generic(_DEVICE_REMOTE, "device_remote")

    def local(self) -> None:
        """Return front-panel control to the operator."""
        self._generic(_DEVICE_LOCAL, "device_local")

    def read_stb(self) -> int:
        """Read the status byte using ``device_readstb`` rather than ``*STB?``.

        This works even while the instrument is busy with an acquisition.
        """
        return self._generic(_DEVICE_READSTB, "device_readstb").int() & 0xFF
