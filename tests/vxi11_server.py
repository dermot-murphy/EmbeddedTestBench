"""A minimal ONC-RPC / VXI-11 server used to test the client on a real socket.

This is deliberately an independent implementation of the wire format rather
than a reuse of the client's codec, so that a test passing means the two ends
genuinely agree about bytes on a socket - not that one module agrees with
itself.

Traces to: SWE4-UT-VXI11-WIRE.
"""

from __future__ import annotations

import socket
import struct
import threading
from typing import Dict, Optional

from tek3014b.simulator import SimulatedTDS3014B

_LAST_FRAGMENT = 0x80000000
_FRAGMENT_MASK = 0x7FFFFFFF

CREATE_LINK = 10
DEVICE_WRITE = 11
DEVICE_READ = 12
DEVICE_READSTB = 13
DEVICE_TRIGGER = 14
DEVICE_CLEAR = 15
DEVICE_REMOTE = 16
DEVICE_LOCAL = 17
DESTROY_LINK = 23

REASON_REQCNT = 0x01
REASON_END = 0x04

ERROR_NO_DEVICE = 3
ERROR_INVALID_LINK = 4


def _pad(data: bytes) -> bytes:
    return data + b"\x00" * ((-len(data)) % 4)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def uint(self) -> int:
        value = struct.unpack(">I", self.data[self.pos : self.pos + 4])[0]
        self.pos += 4
        return value

    def int(self) -> int:
        value = struct.unpack(">i", self.data[self.pos : self.pos + 4])[0]
        self.pos += 4
        return value

    def opaque(self) -> bytes:
        length = self.uint()
        payload = self.data[self.pos : self.pos + length]
        self.pos += length + ((-length) % 4)
        return payload


class FakeVxi11Server:
    """Serves the VXI-11 core channel for one simulated instrument.

    :param simulator: Instrument model to answer from.
    :param device_names: Logical device names ``create_link`` will accept.
    :param max_recv_size: Value reported to the client in the link reply.
    """

    def __init__(
        self,
        simulator: Optional[SimulatedTDS3014B] = None,
        device_names=("inst0",),
        max_recv_size: int = 1024,
    ) -> None:
        self.simulator = simulator or SimulatedTDS3014B()
        self.device_names = tuple(device_names)
        self.max_recv_size = int(max_recv_size)
        self.create_link_attempts = []
        #: Procedure numbers of the generic (clear/trigger/remote/local) calls seen.
        self.generic_calls = []

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(4)
        # Poll rather than block in accept(), so close() can stop the thread
        # promptly: on Linux, closing a listening socket from another thread
        # does not wake a blocked accept().
        self._socket.settimeout(0.1)
        self.port = self._socket.getsockname()[1]

        self._links: Dict[int, bytearray] = {}
        self._pending: Dict[int, bytearray] = {}
        self._next_link = 1
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def close(self) -> None:
        """Stop serving and release the listening socket."""
        self._running = False
        try:
            self._socket.close()
        except OSError:
            pass
        self._thread.join(timeout=2.0)

    def __enter__(self) -> "FakeVxi11Server":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    # ------------------------------------------------------------------
    def _accept_loop(self) -> None:
        while self._running:
            try:
                connection, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connection.settimeout(5.0)
            threading.Thread(target=self._serve, args=(connection,), daemon=True).start()

    def _serve(self, connection: socket.socket) -> None:
        with connection:
            while self._running:
                try:
                    message = self._read_record(connection)
                except socket.timeout:
                    continue
                if message is None:
                    return
                reply = self._dispatch(message)
                if reply is None:
                    return
                connection.sendall(struct.pack(">I", len(reply) | _LAST_FRAGMENT) + reply)

    @staticmethod
    def _read_exactly(connection: socket.socket, count: int) -> Optional[bytes]:
        chunks = []
        remaining = count
        while remaining > 0:
            try:
                chunk = connection.recv(remaining)
            except OSError:
                return None
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_record(self, connection: socket.socket) -> Optional[bytes]:
        fragments = []
        while True:
            header = self._read_exactly(connection, 4)
            if header is None:
                return None
            value = struct.unpack(">I", header)[0]
            length = value & _FRAGMENT_MASK
            body = self._read_exactly(connection, length) if length else b""
            if body is None:
                return None
            fragments.append(body)
            if value & _LAST_FRAGMENT:
                return b"".join(fragments)

    # ------------------------------------------------------------------
    def _dispatch(self, message: bytes) -> Optional[bytes]:
        reader = _Reader(message)
        xid = reader.uint()
        if reader.int() != 0:  # must be a CALL
            return None
        reader.uint()  # rpcvers
        reader.uint()  # prog
        reader.uint()  # vers
        procedure = reader.uint()
        reader.uint(); reader.opaque()  # credentials
        reader.uint(); reader.opaque()  # verifier

        body = self._handle(procedure, reader)
        header = struct.pack(
            ">IiiIIi",
            xid,
            1,  # REPLY
            0,  # MSG_ACCEPTED
            0,  # verifier flavour AUTH_NULL
            0,  # verifier length
            0,  # accept_stat SUCCESS
        )
        return header + body

    def _handle(self, procedure: int, reader: _Reader) -> bytes:
        if procedure == CREATE_LINK:
            reader.int()  # clientId
            reader.uint()  # lockDevice
            reader.uint()  # lock_timeout
            device = reader.opaque().decode("ascii")
            self.create_link_attempts.append(device)
            if device not in self.device_names:
                return struct.pack(">iiII", ERROR_NO_DEVICE, 0, 0, 0)
            link = self._next_link
            self._next_link += 1
            self._links[link] = bytearray()
            self._pending[link] = bytearray()
            return struct.pack(">iiII", 0, link, 0, self.max_recv_size)

        if procedure == DEVICE_WRITE:
            link = reader.int()
            reader.uint(); reader.uint()
            flags = reader.int()
            data = reader.opaque()
            if link not in self._links:
                return struct.pack(">iI", ERROR_INVALID_LINK, 0)
            self._links[link].extend(data)
            if flags & 0x08:  # END
                command = bytes(self._links[link])
                self._links[link] = bytearray()
                reply = self.simulator.respond(command.strip())
                self._pending[link] = bytearray(reply or b"")
            return struct.pack(">iI", 0, len(data))

        if procedure == DEVICE_READ:
            link = reader.int()
            request = reader.uint()
            if link not in self._links:
                return struct.pack(">iiI", ERROR_INVALID_LINK, 0, 0)
            buffer = self._pending[link]
            take = min(request, len(buffer))
            payload = bytes(buffer[:take])
            del buffer[:take]
            reason = REASON_END if not buffer else REASON_REQCNT
            return struct.pack(">ii", 0, reason) + struct.pack(">I", len(payload)) + _pad(payload)

        if procedure == DEVICE_READSTB:
            return struct.pack(">ii", 0, 16)

        if procedure in (DEVICE_CLEAR, DEVICE_TRIGGER, DEVICE_REMOTE, DEVICE_LOCAL):
            link = reader.int()
            if procedure == DEVICE_CLEAR and link in self._pending:
                self._pending[link] = bytearray()
            self.generic_calls.append(procedure)
            return struct.pack(">i", 0)

        if procedure == DESTROY_LINK:
            link = reader.int()
            self._links.pop(link, None)
            self._pending.pop(link, None)
            return struct.pack(">i", 0)

        return struct.pack(">i", 8)  # operation not supported


class FakePortmapper:
    """Answers a single ``GETPORT`` request over TCP with a fixed port."""

    def __init__(self, mapped_port: int) -> None:
        self.mapped_port = int(mapped_port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(2)
        self._socket.settimeout(0.1)
        self.port = self._socket.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            try:
                connection, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(5.0)
                header = connection.recv(4)
                if len(header) < 4:
                    continue
                length = struct.unpack(">I", header)[0] & _FRAGMENT_MASK
                body = connection.recv(length)
                xid = struct.unpack(">I", body[:4])[0]
                reply = struct.pack(">IiiIIiI", xid, 1, 0, 0, 0, 0, self.mapped_port)
                connection.sendall(struct.pack(">I", len(reply) | _LAST_FRAGMENT) + reply)

    def close(self) -> None:
        """Stop serving."""
        self._running = False
        try:
            self._socket.close()
        except OSError:
            pass
        self._thread.join(timeout=2.0)

    def __enter__(self) -> "FakePortmapper":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False
