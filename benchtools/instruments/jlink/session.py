"""A GDB/MI conversation: commands in, records out.

:class:`GdbMiSession` turns the line stream of :mod:`.gdbmi` into a
request/response API, and keeps the asynchronous records that arrive alongside.

Two properties of MI drive the design:

**Asynchronous records are not responses.** ``*stopped`` arrives when the target
halts, which may be long after the ``-exec-continue`` that let it run, and may
be while another command is in flight. They are therefore buffered in a deque as
they are seen, whatever else is happening, and consumed with
:meth:`wait_for_stop`.

**Unsolicited output must not be discarded.** The transport drops buffered bytes
on write, which is right for SCPI and wrong here, so every already-received
record is drained into the deque *before* a command is sent.

Traces to: JLINK-FR-002, JLINK-DD-SESSION.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from ...core.errors import (
    BenchToolsError,
    ConnectionFailedError,
    TransportError,
    TransportTimeoutError,
)
from ...core.transport.base import Transport
from .gdbmi import (
    AsyncRecord,
    PromptRecord,
    Record,
    RecordKind,
    ResultRecord,
    StreamRecord,
    parse_line,
)

__all__ = ["GdbMiSession", "GdbError", "ConsoleResult"]

_LOG = logging.getLogger(__name__)

#: Records kept for diagnostics when nothing consumes them.
_HISTORY = 400


class GdbError(BenchToolsError):
    """GDB reported ``^error`` for a command.

    :param command: The command that failed.
    :param message: GDB's own message, which is usually the useful part.
    """

    def __init__(self, command: str, message: str) -> None:
        self.command = command
        self.message = message
        super().__init__("%s failed: %s" % (command, message or "no message given"))


class ConsoleResult:
    """The console output of a command run through GDB's own interpreter.

    Commands such as ``load`` and ``compare-sections`` have no MI equivalent, so
    they are run with ``-interpreter-exec console`` and their human-readable
    output is what carries the information.

    :param lines: Console lines, in order, with terminators stripped.
    """

    __slots__ = ("lines", "record")

    def __init__(self, lines: List[str], record: ResultRecord) -> None:
        self.lines = lines
        self.record = record

    @property
    def text(self) -> str:
        """The console output as one string."""
        return "\n".join(self.lines)

    def __contains__(self, needle: str) -> bool:
        return needle in self.text

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<ConsoleResult %d line(s)>" % len(self.lines)


class GdbMiSession:
    """A live GDB/MI conversation over a line-oriented transport.

    :param transport: An open or unopened transport carrying MI lines - a GDB
        child process, or the simulator.
    :param timeout: Default seconds to wait for a command's result.
    """

    def __init__(self, transport: Transport, timeout: float = 20.0) -> None:
        self._transport = transport
        self._timeout = float(timeout)
        self._token = 0
        self._async: Deque[AsyncRecord] = deque(maxlen=_HISTORY)
        self._console: Deque[str] = deque(maxlen=_HISTORY)
        self._log: Deque[str] = deque(maxlen=_HISTORY)

    # ------------------------------------------------------------------
    @property
    def transport(self) -> Transport:
        """The underlying transport."""
        return self._transport

    @property
    def timeout(self) -> float:
        """Default command timeout in seconds."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        if value <= 0.0:
            raise ValueError("timeout must be positive, got %r" % (value,))
        self._timeout = float(value)

    @property
    def console_output(self) -> str:
        """Console text seen so far, for diagnostics."""
        return "\n".join(self._console)

    @property
    def log_output(self) -> str:
        """GDB's own log text seen so far, for diagnostics."""
        return "\n".join(self._log)

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Open the transport and consume GDB's start-up output."""
        self._transport.open()
        self._drain(settle=0.2)

    def close(self) -> None:
        """End the session, asking GDB to exit first so it tidies up."""
        try:
            if self._transport.is_open:
                self._transport.write(b"-gdb-exit")
        except Exception:  # noqa: BLE001 - closing must not raise
            _LOG.debug("could not send -gdb-exit", exc_info=True)
        finally:
            self._transport.close()

    # ------------------------------------------------------------------
    # Record handling
    # ------------------------------------------------------------------
    def _file(self, record: Record) -> None:
        """Put a non-result record where it belongs."""
        if isinstance(record, AsyncRecord):
            self._async.append(record)
            _LOG.debug("async %s%s", record.message, record.results or "")
        elif isinstance(record, StreamRecord):
            text = record.text.rstrip("\r\n")
            if record.kind is RecordKind.LOG:
                self._log.append(text)
            elif text:
                self._console.append(text)
                _LOG.debug("console %s", text)

    def _read_record(self, deadline: float) -> Optional[Record]:
        """Read and parse one record, or return ``None`` on timeout."""
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return None
        previous = self._transport.timeout
        self._transport.timeout = max(remaining, 0.01)
        try:
            line = self._transport.read_message().decode("utf-8", errors="replace")
        except TransportTimeoutError:
            return None
        finally:
            self._transport.timeout = previous
        return parse_line(line)

    def _drain(self, settle: float = 0.0) -> None:
        """File every record already received, without waiting for more.

        Called before each command, so asynchronous records are not lost when
        the transport discards its buffer on write.
        """
        while self._transport.has_buffered_data:
            try:
                record = self._read_record(time.monotonic() + 0.01)
            except TransportError:
                # A partial line with nothing behind it. Leave it buffered; the
                # rest will arrive and be read by the next command.
                break
            if record is None:
                break
            self._file(record)
        if settle > 0.0:
            # Real GDB prints a banner and a prompt on start-up; the simulator
            # prints nothing at all. A transport with nothing pending is the same
            # situation as a transport that stays quiet, so both end the wait.
            deadline = time.monotonic() + settle
            while True:
                try:
                    record = self._read_record(deadline)
                except TransportError:
                    break
                if record is None or isinstance(record, PromptRecord):
                    break
                self._file(record)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def execute(
        self,
        command: str,
        timeout: Optional[float] = None,
        allow_error: bool = False,
    ) -> ResultRecord:
        """Send an MI command and return its result record.

        :param command: An MI command, e.g. ``"-break-insert main"``.
        :param timeout: Seconds to wait; the session default when omitted.
        :param allow_error: Return an ``^error`` record instead of raising. Use
            for commands whose failure is a legitimate answer, such as reading a
            symbol that may not exist.
        :raises GdbError: on ``^error`` unless *allow_error*.
        :raises TransportTimeoutError: if no result arrives in time.
        """
        self._drain()
        self._token += 1
        token = self._token
        _LOG.debug(">> %d%s", token, command)
        self._transport.write(("%d%s" % (token, command)).encode("utf-8"))

        deadline = time.monotonic() + (timeout if timeout is not None else self._timeout)
        while True:
            record = self._read_record(deadline)
            if record is None:
                raise TransportTimeoutError(
                    "GDB did not answer %r within %.1f s"
                    % (command, timeout if timeout is not None else self._timeout)
                )
            if isinstance(record, ResultRecord):
                if record.token is not None and record.token != token:
                    # A result for an earlier command; keep looking.
                    continue
                if record.is_error and not allow_error:
                    raise GdbError(command, record.error_message)
                return record
            self._file(record)

    def execute_console(
        self,
        command: str,
        timeout: Optional[float] = None,
        allow_error: bool = False,
    ) -> ConsoleResult:
        """Run a plain GDB command and capture its console output.

        For commands with no MI form - ``load``, ``compare-sections``,
        ``monitor`` - where the console text is the result.
        """
        before = len(self._console)
        escaped = command.replace("\\", "\\\\").replace('"', '\\"')
        record = self.execute(
            '-interpreter-exec console "%s"' % escaped,
            timeout=timeout,
            allow_error=allow_error,
        )
        return ConsoleResult(list(self._console)[before:], record)

    # ------------------------------------------------------------------
    # Asynchronous records
    # ------------------------------------------------------------------
    def pending_async(self, message: Optional[str] = None) -> List[AsyncRecord]:
        """Return buffered asynchronous records, optionally filtered by class."""
        self._drain()
        if message is None:
            return list(self._async)
        return [record for record in self._async if record.message == message]

    def clear_async(self) -> None:
        """Discard buffered asynchronous records.

        Call before resuming the target, so a stale ``*stopped`` from an earlier
        run is not mistaken for this one.
        """
        self._drain()
        self._async.clear()

    def wait_for_async(
        self,
        message: str = "stopped",
        timeout: Optional[float] = None,
    ) -> AsyncRecord:
        """Wait for an asynchronous record of class *message* and return it.

        A matching record already buffered is returned immediately, so there is
        no race between the target halting and this call being made.

        :raises TransportTimeoutError: if none arrives in time.
        """
        waited = timeout if timeout is not None else self._timeout
        deadline = time.monotonic() + waited
        self._drain()
        for index, record in enumerate(self._async):
            if record.message == message:
                del self._async[index]
                return record
        while True:
            try:
                record = self._read_record(deadline)
            except ConnectionFailedError:
                # The link is gone. That is not "still waiting" and must not be
                # reported as a timeout, or a crashed GDB looks like a target
                # that simply never stopped.
                raise
            except TransportError:
                # The link has nothing pending. Indistinguishable from a quiet
                # target, so keep waiting until the deadline.
                record = None
            if record is None:
                if time.monotonic() >= deadline:
                    raise TransportTimeoutError(
                        "no %r notification from GDB within %.1f s" % (message, waited)
                    )
                time.sleep(0.005)
                continue
            if isinstance(record, AsyncRecord) and record.message == message:
                return record
            self._file(record)

    def wait_for_stop(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Wait for the target to halt and return the ``*stopped`` results.

        The returned mapping carries ``reason``, and usually ``frame`` with the
        function, file and line where it stopped.
        """
        return dict(self.wait_for_async("stopped", timeout=timeout).results)
