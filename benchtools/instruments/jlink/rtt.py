"""SEGGER Real Time Transfer: reading, writing, expecting and logging.

RTT is a ring buffer in target RAM that the probe drains while the target runs.
For a test bench it is the most useful channel a target has: it carries log
output with no halting, and accepts commands back.

Two backends, one interface. The J-Link GDB Server republishes RTT channel 0 on
a TCP port (19021 by default), which is what a real bench uses. The simulator
provides the same bytes directly. Neither is visible to callers.

**On threads and determinism.** A reader thread drains the source continuously,
which is what a log needs. But every read, line fetch and :meth:`expect` also
pumps the source *synchronously* first, so a caller that has just resumed the
target does not have to wait for a thread to be scheduled. Without that, tests
of RTT behaviour become timing-dependent, and a timing-dependent test of a
logging facility is worse than none.

Multi-channel note: the GDB Server's TCP port carries **up-channel 0** only.
Other channels need one port each, or SEGGER's RTT Client; the ``channel``
argument therefore selects which configured port to use rather than multiplexing
a single connection.

Traces to: JLINK-FR-050 .. JLINK-FR-055, JLINK-DD-RTT.
"""

from __future__ import annotations

import logging
import os
import re
import select
import socket
import threading
import time
from collections import deque
from typing import Deque, List, Optional, Pattern, Protocol, Union, runtime_checkable

from ...core.errors import BenchToolsError, ConnectionFailedError, TransportTimeoutError

__all__ = ["RttClient", "RttTimeout", "RttSource", "SocketRttBackend", "SimulatedRttBackend"]

_LOG = logging.getLogger(__name__)

#: How often the reader thread polls the source.
_POLL_INTERVAL = 0.01

#: Lines retained in memory for :attr:`RttClient.history`.
_HISTORY = 10000


class RttTimeout(TransportTimeoutError):
    """Expected RTT output did not arrive in time.

    :param pattern: What was being waited for.
    :param seen: The text that did arrive, which is what makes the failure
        diagnosable - "timed out" alone never tells you why.
    """

    def __init__(self, pattern: str, timeout: float, seen: str) -> None:
        self.pattern = pattern
        self.seen = seen
        excerpt = seen[-500:] if seen else "(nothing)"
        super().__init__(
            "RTT did not produce %r within %.1f s. Received:\n%s"
            % (pattern, timeout, excerpt)
        )


@runtime_checkable
class RttSource(Protocol):
    """A source of RTT bytes."""

    def rtt_open(self) -> None:
        """Make the source ready."""
        ...

    def rtt_close(self) -> None:
        """Release the source."""
        ...

    def rtt_poll(self) -> bytes:
        """Return whatever is available now, without blocking."""
        ...

    def rtt_send(self, data: bytes) -> None:
        """Send *data* to the target."""
        ...


class SocketRttBackend:
    """RTT over the J-Link GDB Server's TCP port.

    :param host: Host running the GDB Server.
    :param port: RTT port, 19021 by default.
    :param connect_timeout: Seconds to wait for the connection.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 19021, connect_timeout: float = 5.0) -> None:
        self._host = host
        self._port = int(port)
        self._connect_timeout = float(connect_timeout)
        self._socket: Optional[socket.socket] = None

    def rtt_open(self) -> None:
        if self._socket is not None:
            return
        try:
            self._socket = socket.create_connection(
                (self._host, self._port), timeout=self._connect_timeout
            )
        except OSError as exc:
            raise ConnectionFailedError(
                "cannot reach RTT on %s:%d: %s. The GDB Server publishes RTT only "
                "once the target is running and RTT has been started."
                % (self._host, self._port, exc)
            ) from exc
        self._socket.setblocking(False)

    def rtt_close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def rtt_poll(self) -> bytes:
        if self._socket is None:
            return b""
        collected = bytearray()
        while True:
            try:
                readable, _, _ = select.select([self._socket], [], [], 0)
            except (OSError, ValueError):  # pragma: no cover - socket closed
                break
            if not readable:
                break
            try:
                chunk = self._socket.recv(65536)
            except BlockingIOError:  # pragma: no cover - race with select
                break
            except OSError:  # pragma: no cover - socket closed
                break
            if not chunk:
                break
            collected += chunk
        return bytes(collected)

    def rtt_send(self, data: bytes) -> None:
        if self._socket is None:
            raise BenchToolsError("RTT is not connected")
        try:
            self._socket.sendall(data)
        except OSError as exc:
            raise ConnectionFailedError("RTT write failed: %s" % exc) from exc


class SimulatedRttBackend:
    """RTT from a :class:`~benchtools.instruments.jlink.simulator.SimulatedJLink`."""

    def __init__(self, simulator) -> None:
        self._simulator = simulator

    def rtt_open(self) -> None:
        self._simulator.rtt_started = True

    def rtt_close(self) -> None:
        self._simulator.rtt_started = False

    def rtt_poll(self) -> bytes:
        return self._simulator.rtt_read().encode("utf-8")

    def rtt_send(self, data: bytes) -> None:
        self._simulator.rtt_write(data.decode("utf-8", errors="replace"))


class RttClient:
    """Buffered, line-aware access to an RTT channel.

    :param backend: Where the bytes come from.
    :param channel: Channel number, recorded for reports and log headers.
    :param encoding: Text encoding of the stream.
    """

    def __init__(
        self,
        backend: RttSource,
        channel: int = 0,
        encoding: str = "utf-8",
    ) -> None:
        self._backend = backend
        self._channel = int(channel)
        self._encoding = encoding
        self._partial = ""
        #: Lines not yet consumed by a read. Draining reads empty this.
        self._pending: Deque[str] = deque(maxlen=_HISTORY)
        #: Every line received, never consumed by a read. This is what a report
        #: or a post-mortem needs, and it must not be emptied by the reads that
        #: a test performs as it goes.
        self._history: Deque[str] = deque(maxlen=_HISTORY)
        self._all_text: List[str] = []
        self._log_handle = None
        self._log_path: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._running = False

    # ------------------------------------------------------------------
    @property
    def channel(self) -> int:
        """Channel this client reads."""
        return self._channel

    @property
    def is_running(self) -> bool:
        """``True`` between :meth:`start` and :meth:`stop`."""
        return self._running

    @property
    def text(self) -> str:
        """Everything received since :meth:`start`, including partial lines."""
        with self._lock:
            return "".join(self._all_text)

    @property
    def history(self) -> List[str]:
        """Every complete line received since :meth:`start`, in order.

        Unaffected by reads, so a test that consumes lines as it goes still has
        the full transcript afterwards for its report.
        """
        with self._lock:
            return list(self._history)

    @property
    def pending_count(self) -> int:
        """Number of complete lines received but not yet consumed by a read."""
        self._pump()
        with self._lock:
            return len(self._pending)

    @property
    def log_path(self) -> Optional[str]:
        """Path currently being logged to, if any."""
        return self._log_path

    # ------------------------------------------------------------------
    def start(self, log_path: Optional[str] = None, background: bool = True) -> None:
        """Open the channel and begin collecting.

        :param log_path: Write every byte received to this file as well. The file
            is flushed per write, so a log survives a crashed test run - which is
            the run whose log you most need.
        :param background: Run a reader thread. Reads pump synchronously too, so
            turning this off only stops collection between calls.
        """
        if self._running:
            return
        self._backend.rtt_open()
        with self._lock:
            self._partial = ""
            self._pending.clear()
            self._history.clear()
            self._all_text = []
        if log_path:
            directory = os.path.dirname(os.path.abspath(log_path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._log_handle = open(log_path, "w", encoding=self._encoding, errors="replace")
            self._log_path = log_path
            self._log_handle.write(
                "# RTT channel %d, opened %s\n"
                % (self._channel, time.strftime("%Y-%m-%dT%H:%M:%S"))
            )
            self._log_handle.flush()
        self._running = True
        self._stop.clear()
        if background:
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop collecting and close the log. Idempotent."""
        if not self._running:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._pump()
        self._running = False
        try:
            self._backend.rtt_close()
        finally:
            if self._log_handle is not None:
                try:
                    self._log_handle.flush()
                    self._log_handle.close()
                finally:
                    self._log_handle = None

    def __enter__(self) -> "RttClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False

    # ------------------------------------------------------------------
    def _reader(self) -> None:
        while not self._stop.is_set():
            try:
                self._pump()
            except Exception:  # noqa: BLE001 - a reader thread must not die quietly
                _LOG.warning("RTT reader failed", exc_info=True)
                return
            self._stop.wait(_POLL_INTERVAL)

    def _pump(self) -> None:
        """Move whatever is available from the backend into the buffers."""
        data = self._backend.rtt_poll()
        if not data:
            return
        text = data.decode(self._encoding, errors="replace")
        with self._lock:
            self._all_text.append(text)
            if self._log_handle is not None:
                self._log_handle.write(text)
                self._log_handle.flush()
            self._partial += text
            while True:
                index = self._partial.find("\n")
                if index < 0:
                    break
                line = self._partial[:index].rstrip("\r")
                self._partial = self._partial[index + 1 :]
                self._pending.append(line)
                self._history.append(line)

    # ------------------------------------------------------------------
    def read(self) -> str:
        """Return and consume every complete line available now."""
        self._pump()
        with self._lock:
            out = "".join(line + "\n" for line in self._pending)
            self._pending.clear()
        return out

    def read_lines(self) -> List[str]:
        """Return and consume every complete line available now, as a list."""
        self._pump()
        with self._lock:
            out = list(self._pending)
            self._pending.clear()
        return out

    def read_line(self, timeout: float = 2.0) -> Optional[str]:
        """Wait for and consume one line, or return ``None`` on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            self._pump()
            with self._lock:
                if self._pending:
                    return self._pending.popleft()
            if time.monotonic() >= deadline:
                return None
            time.sleep(_POLL_INTERVAL)

    def write(self, text: str, newline: bool = True) -> None:
        """Send *text* to the target, appending a newline by default."""
        payload = text + ("\n" if newline and not text.endswith("\n") else "")
        self._backend.rtt_send(payload.encode(self._encoding))

    def command(self, text: str, pattern: str = ".+", timeout: float = 2.0):
        """Send a command and wait for the first matching reply.

        The common RTT interaction on a bench: write a command, read what the
        firmware says back.
        """
        self.read_lines()          # discard anything older than this command
        self.write(text)
        return self.expect(pattern, timeout=timeout)

    def expect(self, pattern: Union[str, Pattern], timeout: float = 5.0):
        """Wait until a line matches *pattern* and return the match.

        :param pattern: Regular expression searched against each complete line.
        :raises RttTimeout: if no line matches in time, naming what did arrive.
        """
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
        deadline = time.monotonic() + timeout
        examined: List[str] = []
        while True:
            self._pump()
            with self._lock:
                pending = list(self._pending)
                self._pending.clear()
            for line in pending:
                examined.append(line)
                match = compiled.search(line)
                if match:
                    return match
            if time.monotonic() >= deadline:
                raise RttTimeout(
                    compiled.pattern, timeout, "\n".join(examined) or self.text
                )
            time.sleep(_POLL_INTERVAL)
