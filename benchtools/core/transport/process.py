"""Transport over a child process's standard input and output.

Some instruments are reached through a vendor tool rather than a socket: a
debugger front end, a dongle utility, a protocol bridge. This transport spawns
such a tool and talks to it over pipes, reusing the same framing the socket and
VXI-11 transports use.

**Why a reader thread rather than ``select``.** On POSIX a pipe can be polled
with ``select``; on Windows it cannot - ``select`` accepts sockets only. Since
these tools run on a Windows bench, output is drained by a background thread
into a queue, and :meth:`_recv_chunk` pops from that queue with a timeout. The
same code then behaves identically on both platforms, which is worth more than
the thread costs.

``stderr`` is drained by a second thread and kept in a bounded buffer. If it
were left unread, a tool that writes a lot of diagnostics would eventually
block on a full pipe and the session would hang for no visible reason.

Traces to: CORE-FR-009, CORE-ARC-003, CORE-DD-PROCESS.
"""

from __future__ import annotations

import logging
import os
import queue
import shlex
import subprocess
import threading
from collections import deque
from typing import Deque, List, Optional, Tuple

from ..errors import ConnectionFailedError, TransportError, TransportTimeoutError
from .base import Transport

__all__ = ["ProcessTransport"]

_LOG = logging.getLogger(__name__)

#: Lines of stderr retained for diagnostics.
_STDERR_LINES = 200


class ProcessTransport(Transport):
    """Talk to a child process over its standard input and output.

    :param command: Program and arguments. A string is split with :mod:`shlex`.
    :param resource: Alias for *command*, so the transport can be selected by a
        ``process://`` resource string.
    :param timeout: Default I/O timeout in seconds.
    :param terminator: Line terminator; the default suits line-oriented tools.
        With the default, a line ending in CR LF is returned without the CR:
        a child on Windows writing text ends its lines that way, and a message
        of ``b"done\\r"`` is not the ``b"done"`` it sent (#79).
    :param cwd: Working directory for the child.
    :param env: Extra environment variables for the child.
    :param ready_timeout: Seconds to allow for the process to still be alive
        after starting. A tool that exits immediately - a missing shared
        library, a bad argument - is reported as a connection failure with its
        stderr, rather than as a read timeout later.
    """

    def __init__(
        self,
        command=None,
        resource: Optional[str] = None,
        timeout: float = 10.0,
        terminator: bytes = b"\n",
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        ready_timeout: float = 0.5,
    ) -> None:
        super().__init__(timeout=timeout, terminator=terminator)
        raw = command if command is not None else resource
        if not raw:
            raise ValueError("a command is required")
        self._command: List[str] = list(raw) if isinstance(raw, (list, tuple)) else shlex.split(str(raw))
        if not self._command:
            raise ValueError("a command is required")
        self._cwd = cwd
        self._env = dict(env) if env else None
        self._ready_timeout = float(ready_timeout)

        self._process: Optional[subprocess.Popen] = None
        self._returncode: Optional[int] = None
        self._stdout_queue: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._stderr_lines: Deque[str] = deque(maxlen=_STDERR_LINES)
        self._readers: List[threading.Thread] = []

    # ------------------------------------------------------------------
    @property
    def command(self) -> Tuple[str, ...]:
        """The command this transport runs."""
        return tuple(self._command)

    @property
    def description(self) -> str:
        return "process %s" % os.path.basename(self._command[0])

    @property
    def stderr_text(self) -> str:
        """Recent standard-error output, for diagnostics."""
        return "".join(self._stderr_lines)

    @property
    def returncode(self) -> Optional[int]:
        """Exit status of the child, or ``None`` while it is running.

        Retained after :meth:`close`, because the exit status of a tool that
        failed is exactly what a diagnostic needs.
        """
        if self._process is not None:
            live = self._process.poll()
            if live is not None:
                self._returncode = live
            return live
        return self._returncode

    # ------------------------------------------------------------------
    def read_message(self, strip_terminator: bool = True) -> bytes:
        """Read one line; with the default LF terminator, CR LF counts as one too."""
        message = super().read_message(strip_terminator=strip_terminator)
        if strip_terminator and self._read_terminator == b"\n" and message.endswith(b"\r"):
            message = message[:-1]
        return message

    def _open_link(self) -> None:
        environment = None
        if self._env:
            environment = dict(os.environ)
            environment.update(self._env)
        try:
            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._cwd,
                env=environment,
                bufsize=0,
            )
        except OSError as exc:
            raise ConnectionFailedError(
                "cannot start %r: %s. Check the program is installed and on PATH."
                % (self._command[0], exc)
            ) from exc

        self._stdout_queue = queue.Queue()
        self._stderr_lines.clear()
        self._readers = [
            threading.Thread(target=self._drain_stdout, daemon=True),
            threading.Thread(target=self._drain_stderr, daemon=True),
        ]
        for reader in self._readers:
            reader.start()

        # A tool that dies immediately should say so now, with its stderr,
        # rather than surfacing as an unexplained read timeout later.
        try:
            self._process.wait(timeout=self._ready_timeout)
        except subprocess.TimeoutExpired:
            return                      # still running: what we want
        raise ConnectionFailedError(
            "%r exited immediately with status %s%s"
            % (
                self._command[0],
                self._process.returncode,
                (": " + self.stderr_text.strip()) if self.stderr_text.strip() else "",
            )
        )

    def _drain_stdout(self) -> None:
        stream = self._process.stdout if self._process else None
        if stream is None:  # pragma: no cover - defensive
            return
        # bufsize=0 makes stdout a raw FileIO, so read() is a single syscall
        # that returns as soon as any data is available. Reading in blocks keeps
        # a large transfer - the console output of a flash programming run -
        # from costing one queue item per byte.
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                self._stdout_queue.put(chunk)
        except (OSError, ValueError):  # pragma: no cover - pipe closed
            pass
        finally:
            self._stdout_queue.put(None)     # end-of-stream sentinel

    def _drain_stderr(self) -> None:
        stream = self._process.stderr if self._process else None
        if stream is None:  # pragma: no cover - defensive
            return
        try:
            for line in iter(stream.readline, b""):
                text = line.decode("utf-8", errors="replace")
                self._stderr_lines.append(text)
                _LOG.debug("stderr: %s", text.rstrip())
        except (OSError, ValueError):  # pragma: no cover - pipe closed
            pass

    def _close_link(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        self._returncode = process.poll()
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:  # pragma: no cover - defensive
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:  # pragma: no cover - stubborn child
                process.kill()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    _LOG.warning("%s did not exit after kill", self.description)
        for reader in self._readers:
            reader.join(timeout=1.0)
        self._readers = []
        self._returncode = process.returncode

    # ------------------------------------------------------------------
    def _send(self, data: bytes) -> None:
        if self._process is None or self._process.stdin is None:
            raise TransportError("%s is not running" % self.description)
        if self._process.poll() is not None:
            raise ConnectionFailedError(
                "%s has exited with status %s%s"
                % (
                    self.description,
                    self._process.returncode,
                    (": " + self.stderr_text.strip()) if self.stderr_text.strip() else "",
                )
            )
        try:
            self._process.stdin.write(data)
            self._process.stdin.flush()
        except OSError as exc:
            raise ConnectionFailedError(
                "%s closed its input: %s" % (self.description, exc)
            ) from exc

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if self._process is None:
            raise TransportError("%s is not running" % self.description)
        collected = bytearray()
        try:
            first = self._stdout_queue.get(timeout=self._timeout)
        except queue.Empty:
            raise TransportTimeoutError(
                "no output from %s within %.3f s" % (self.description, self._timeout)
            ) from None
        if first is None:
            return b"", True                # process ended: end-of-message
        collected += first

        # Drain whatever else has already arrived, without waiting again.
        while len(collected) < max_bytes:
            try:
                extra = self._stdout_queue.get_nowait()
            except queue.Empty:
                break
            if extra is None:
                return bytes(collected), True
            collected += extra
        return bytes(collected), False
