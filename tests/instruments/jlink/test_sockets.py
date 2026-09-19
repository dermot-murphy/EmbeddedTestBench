"""The TCP links to the J-Link GDB Server's RTT and SWO ports.

These two classes are the ones that actually run on a bench: everything else in
the RTT and SWO modules is exercised through the simulator, which does not go
near a socket. They are tested here against a loopback server, in the same way
the VXI-11 client is, so the socket handling is verified rather than assumed -
including the part that makes a containerised bench possible, namely that the
host and port are arguments and nothing is local by construction.

Traces to: JLINK-FR-050, JLINK-FR-064, JLINK-NFR-002, JLINK-NFR-003,
SWE4-UT-JLINKSOCKETS.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from benchtools.core.errors import BenchToolsError, ConnectionFailedError
from benchtools.instruments.jlink.rtt import RttClient, SocketRttBackend
from benchtools.instruments.jlink.swo import ItmDecoder, SwoStream


class LoopbackServer:
    """Accepts one connection, sends what it is told, records what it receives."""

    def __init__(self) -> None:
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self._listener.settimeout(0.1)
        self.port = self._listener.getsockname()[1]
        self.received = bytearray()
        self._client = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                self._client, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:                       # pragma: no cover - closed
                return
            self._client.settimeout(0.1)
            while not self._stop.is_set():
                try:
                    chunk = self._client.recv(4096)
                except socket.timeout:
                    continue
                except OSError:                   # pragma: no cover - closed
                    break
                if not chunk:
                    break
                self.received += chunk
            return

    def send(self, data: bytes) -> None:
        """Push bytes to the connected client, waiting for it to connect."""
        deadline = time.monotonic() + 2.0
        while self._client is None and time.monotonic() < deadline:
            time.sleep(0.005)
        assert self._client is not None, "the client never connected"
        self._client.sendall(data)

    def wait_for(self, data: bytes, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if data in bytes(self.received):
                return True
            time.sleep(0.005)
        return False

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        if self._client is not None:
            self._client.close()
        self._listener.close()


@pytest.fixture
def server():
    instance = LoopbackServer()
    yield instance
    instance.close()


@pytest.fixture
def closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def drain(poll, expected_bytes, timeout=2.0):
    """Poll until *expected_bytes* have arrived; the network is not instant."""
    collected = bytearray()
    deadline = time.monotonic() + timeout
    while len(collected) < expected_bytes and time.monotonic() < deadline:
        collected += poll()
        if len(collected) < expected_bytes:
            time.sleep(0.005)
    return bytes(collected)


class TestRttOverASocket:
    def test_reads_what_the_server_publishes(self, server):
        backend = SocketRttBackend(port=server.port)
        backend.rtt_open()
        try:
            server.send(b"sensor: ready\n")
            assert drain(backend.rtt_poll, 14) == b"sensor: ready\n"
        finally:
            backend.rtt_close()

    def test_a_fragmented_line_is_assembled_by_the_client(self, server):
        """RTT arrives in whatever fragments TCP chooses, not in lines."""
        client = RttClient(SocketRttBackend(port=server.port))
        client.start()
        try:
            server.send(b"ver")
            server.send(b"sion 1.4.2\nnext\n")
            deadline = time.monotonic() + 2.0
            lines = []
            while len(lines) < 2 and time.monotonic() < deadline:
                lines += client.read_lines()
                time.sleep(0.005)
            assert lines == ["version 1.4.2", "next"]
        finally:
            client.stop()

    def test_writes_reach_the_server(self, server):
        backend = SocketRttBackend(port=server.port)
        backend.rtt_open()
        try:
            backend.rtt_send(b"version\n")
            assert server.wait_for(b"version\n")
        finally:
            backend.rtt_close()

    def test_polling_before_opening_yields_nothing(self):
        assert SocketRttBackend(port=1).rtt_poll() == b""

    def test_writing_before_opening_is_reported(self):
        with pytest.raises(BenchToolsError, match="not connected"):
            SocketRttBackend(port=1).rtt_send(b"x")

    def test_an_unreachable_port_says_what_to_check(self, closed_port):
        """The usual cause is that RTT has not been started on the target."""
        with pytest.raises(ConnectionFailedError) as caught:
            SocketRttBackend(port=closed_port, connect_timeout=0.5).rtt_open()
        assert "cannot reach RTT" in str(caught.value)
        assert "once the target is running" in str(caught.value)

    def test_opening_twice_keeps_one_connection(self, server):
        backend = SocketRttBackend(port=server.port)
        backend.rtt_open()
        backend.rtt_open()
        backend.rtt_close()
        backend.rtt_close()                      # idempotent

    def test_the_host_is_an_argument(self):
        """JLINK-NFR-003: the probe need not be on this machine."""
        backend = SocketRttBackend(host="bench-pc.example.com", port=19021)
        assert backend._host == "bench-pc.example.com"


class TestSwoOverASocket:
    @staticmethod
    def stream(port: int, count: int = 3) -> bytes:
        data = bytearray()
        for index in range(count):
            data += ItmDecoder.encode_local_timestamp(1000 * (index + 1))
            data += ItmDecoder.encode_software_event(port, index + 1, size=1)
        return bytes(data)

    def test_events_are_decoded_from_the_wire(self, server):
        swo = SwoStream(port=server.port)
        swo.open()
        try:
            server.send(self.stream(1))
            events = []
            deadline = time.monotonic() + 2.0
            while len(events) < 3 and time.monotonic() < deadline:
                events += swo.poll()
                time.sleep(0.005)
            assert [event.value for event in events] == [1, 2, 3]
            assert {event.port for event in events} == {1}
        finally:
            swo.close()

    def test_collect_waits_for_the_events_it_was_asked_for(self, server):
        swo = SwoStream(port=server.port)
        swo.open()
        try:
            threading.Timer(0.05, server.send, [self.stream(2, count=2)]).start()
            events = swo.collect(port=2, count=2, timeout=3.0)
            assert [event.value for event in events] == [1, 2]
        finally:
            swo.close()

    def test_collect_returns_what_arrived_when_it_times_out(self, server):
        """A caller must be able to tell "nothing was instrumented" from a hang."""
        swo = SwoStream(port=server.port)
        swo.open()
        try:
            server.send(self.stream(1, count=1))
            assert swo.collect(port=1, count=5, timeout=0.3) != []
            assert swo.collect(port=9, count=1, timeout=0.1) == []
        finally:
            swo.close()

    def test_polling_before_opening_yields_nothing(self):
        assert SwoStream(port=1).poll() == []

    def test_an_unreachable_port_says_what_to_check(self, closed_port):
        with pytest.raises(ConnectionFailedError) as caught:
            SwoStream(port=closed_port).open()
        assert "cannot reach SWO" in str(caught.value)
        assert "monitor swo start" in str(caught.value)

    def test_context_manager(self, server):
        with SwoStream(port=server.port) as swo:
            server.send(self.stream(4, count=1))
            assert swo.collect(port=4, count=1, timeout=2.0)

    def test_opening_twice_keeps_one_connection(self, server):
        swo = SwoStream(port=server.port)
        swo.open()
        swo.open()
        swo.close()
        swo.close()                              # idempotent

    def test_the_prescaler_reaches_the_decoder(self):
        assert SwoStream(port=1, prescaler=16).decoder.prescaler == 16
