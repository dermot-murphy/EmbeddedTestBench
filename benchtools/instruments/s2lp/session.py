"""The command/reply session with ST's CLI firmware, and its log.

Two things here are not obvious from the protocol alone.

**Where a reply ends.** ST's firmware does not terminate a reply with a sentinel
line. It opens a brace, writes tags, and closes it - sometimes on one line, and
sometimes over five. So a reply is complete when the braces balance, and that is
what this session waits for. Waiting for a fixed number of lines would work for
half the commands and truncate the other half.

**Stopping a batch.** A capture command runs on the board for as long as it was
asked to. ST's firmware polls the serial port inside that loop for a single
character, ``S``. Sending it is the only way to end a capture early without
resetting the board, and it is what :meth:`S2lpSession.stop` does.

The log written here is the **raw session log**: every line, both directions,
host-timestamped, flushed per line. It is the evidence for anything measured
through this driver. The structured packet log is a different file and lives in
:mod:`packets`.

Traces to: S2LP-FR-001 .. S2LP-FR-004, S2LP-FR-045, S2LP-DD-SESSION.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque, Iterator, List, Optional

from ...core.errors import (
    ConnectionFailedError,
    ProtocolError,
    TransportError,
    TransportTimeoutError,
)
from ...core.transport.base import Transport
from .constants import DEFAULT_TIMEOUT, STOP_CHARACTER
from .protocol import Reply, firmware_error, format_command, parse_reply

#: How many unclaimed lines to keep. The firmware echoes every command, so an
#: unbounded list grows by one line per command for the life of the session.
UNCLAIMED_LIMIT = 200

#: Seconds each read waits for a line before the session checks its deadline.
#: Fixed, so the port is configured once rather than on every read.
READ_POLL = 0.05

#: The prompt the firmware prints after each reply.
PROMPT = ">"

#: How every reply begins: ``{{(Command)} API call...``.
REPLY_START = "{{"

#: The command name the firmware acknowledges a stop with.
STOP_ACK = "StopCmd"

__all__ = ["S2lpSession"]

_LOG = logging.getLogger(__name__)


class S2lpSession:
    """Commands in, replies out, everything logged.

    :param transport: The link to the board, usually its USB serial port.
    :param timeout: Seconds to wait for a reply to complete.
    """

    def __init__(self, transport: Transport, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._transport = transport
        self._timeout = float(timeout)
        self._log = None
        self._log_path: Optional[str] = None
        #: Lines the firmware sent that were not part of any reply, most recent
        #: last: the echo of each command, and anything nobody expected. Kept
        #: rather than dropped, because a line nobody expected is evidence. The
        #: session log keeps all of them; this keeps the latest.
        self.unclaimed: Deque[str] = deque(maxlen=UNCLAIMED_LIMIT)

    # ------------------------------------------------------------------
    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = max(0.0, float(value))

    @property
    def log_path(self) -> Optional[str]:
        """Where the raw session log is being written, if anywhere."""
        return self._log_path

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Open the link and discard anything the board was mid-sentence on."""
        if not self._transport.is_open:
            self._transport.open()
        self._drain()

    def close(self) -> None:
        """Stop logging. The transport belongs to whoever opened it."""
        self.stop_log()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def log_to(self, path: str) -> str:
        """Log every line, both directions, to a text file.

        Flushed per line, so the log of a session that then hung is complete up
        to the moment it hung - which is the log worth having.

        :returns: The path written.
        """
        self.stop_log()
        self._log = open(path, "a", encoding="utf-8")
        self._log_path = path
        self._write_log("#", "session opened on %s" % self._transport.description)
        return path

    def stop_log(self) -> None:
        """Close the log file, if one is open. Idempotent."""
        if self._log is not None:
            self._write_log("#", "session closed")
            try:
                self._log.close()
            finally:
                self._log = None
                self._log_path = None

    def note(self, text: str) -> None:
        """Write a comment into the log, for whoever reads it later."""
        self._write_log("#", text)

    def _write_log(self, direction: str, text: str) -> None:
        if self._log is None:
            return
        self._log.write("%.6f %s %s\n" % (time.time(), direction, text))
        self._log.flush()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def send(self, name: str, *arguments) -> str:
        """Format and send one command, without waiting for its reply."""
        line = format_command(name, *arguments)
        _LOG.debug(">> %s", line)
        self._write_log(">", line)
        self._transport.write(line.encode("ascii"))
        return line

    def execute(self, name: str, *arguments, timeout: Optional[float] = None) -> Reply:
        """Send one command and return its reply.

        :raises TransportTimeoutError: if the reply does not complete in time,
            saying what was received so far - a half-finished reply is the most
            useful thing to look at when a command hangs.
        """
        self.send(name, *arguments)
        return self.read_reply(timeout=timeout, command=name, expect=name)

    def read_reply(
        self, timeout: Optional[float] = None, command: str = "", expect: str = ""
    ) -> Reply:
        """Read the next reply, and parse it.

        :param command: What to call the command in an error message.
        :param expect: Skip replies from any other command, keeping them in
            :attr:`unclaimed`. On a kit, a send interrupted by a stop printed
            its own acknowledgement *after* the stop's, which would otherwise
            have been taken as the answer to whatever was sent next.
        :raises ProtocolError: at once, when the command interpreter rejects the
            command (``no such command``, ``wrong number of arguments``, ...).
            It sends that line instead of a reply, so waiting would only turn a
            named error into a timeout.
        """
        limit = self._timeout if timeout is None else float(timeout)
        deadline = time.monotonic() + limit
        while True:
            reply = self._read_one_reply(deadline, limit, command)
            if not expect or not reply.command or reply.command == expect:
                return reply
            _LOG.debug("skipping a stale reply from %s", reply.command)
            self._write_log("#", "stale reply from %s skipped" % reply.command)
            self.unclaimed.append(reply.raw)

    def _read_one_reply(self, deadline: float, limit: float, command: str) -> Reply:
        """Read lines until the braces balance, and parse them."""
        lines: List[str] = []
        depth = 0
        started = False

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportTimeoutError(
                    "the board did not finish answering %s within %.3f s. "
                    "Received so far: %s"
                    % (command or "the command", limit,
                       " / ".join(lines) if lines else "(nothing)")
                )
            line = self._read_line()
            if line is None:
                continue
            if not started and not line.lstrip().startswith("{") and REPLY_START in line:
                # The echo of the command ran into the reply. Seen on a kit
                # with SdkEvalRfboardIdentification, whose echo arrives
                # truncated and without its line end.
                head, _, tail = line.partition(REPLY_START)
                self.unclaimed.append(head)
                line = REPLY_START + tail
            if not started and not line.lstrip().startswith("{"):
                if line == PROMPT:
                    continue
                error = firmware_error(line)
                if error:
                    raise ProtocolError(
                        "the firmware rejected %s: %s"
                        % (command or "the command", error)
                    )
                # The command's echo, or output from before it. Keep it.
                self.unclaimed.append(line)
                continue
            started = True
            lines.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                break

        return parse_reply(lines)

    def collect(
        self,
        count: int,
        timeout: Optional[float] = None,
        per_reply_timeout: Optional[float] = None,
    ) -> Iterator[Reply]:
        """Read up to *count* replies, for a batch command.

        Yields as they arrive rather than returning a list, so a caller can log
        each packet as it lands rather than after the capture. Stops early when
        the overall *timeout* expires, because a batch that was cut short is a
        fact the caller needs, not an exception.
        """
        overall = time.monotonic() + (self._timeout if timeout is None else float(timeout))
        produced = 0
        while produced < count:
            remaining = overall - time.monotonic()
            if remaining <= 0:
                return
            try:
                yield self.read_reply(
                    timeout=min(remaining, per_reply_timeout or remaining)
                )
            except TransportTimeoutError:
                return
            produced += 1

    def stop(self, wait: float = 2.0) -> List[Reply]:
        """End a batch or blocking command early, and wait for it to end.

        ST's firmware polls the port for one character, ``S``, inside its
        receive and transmit loops. It is sent without a terminator on purpose:
        the firmware reads a character, not a line.

        Sending it is only safe while such a loop is running. On a kit it was
        seen that an ``S`` sent to an idle board sits in the command buffer and
        turns the next command into ``no such command``. So this waits for the
        firmware's ``StopCmd`` acknowledgement, and when none comes it ends the
        line and swallows the error it produces.

        :param wait: Seconds to wait for the acknowledgement. 0 sends the
            character and returns, for a caller that reads the replies itself.
        :returns: Replies that arrived before the acknowledgement - a packet
            that landed while the stop was on its way is still a packet.
        """
        _LOG.debug(">> (stop)")
        self._write_log(">", "(stop)")
        self._transport.write(STOP_CHARACTER, append_terminator=False, keep_buffer=True)
        if wait <= 0:
            return []

        arrived: List[Reply] = []
        deadline = time.monotonic() + float(wait)
        while time.monotonic() < deadline:
            try:
                reply = self.read_reply(timeout=deadline - time.monotonic(),
                                        command="the stop")
            except TransportTimeoutError:
                break
            if reply.command == STOP_ACK:
                return arrived
            arrived.append(reply)

        # Nothing was running, so the character is sitting in the firmware's
        # command buffer. End the line so the next command starts clean.
        self._write_log(">", "(end the line left by the stop)")
        self._transport.write(b"")
        try:
            self.read_reply(timeout=min(1.0, self._timeout), command="the stop")
        except ProtocolError:
            pass                        # "no such command": the expected answer
        except TransportTimeoutError:
            _LOG.debug("no answer to the line ended after a stop")
        return arrived

    # ------------------------------------------------------------------
    def _read_line(self) -> Optional[str]:
        """Read one line, or ``None`` if none completed within :data:`READ_POLL`.

        The transport's timeout is set once, to :data:`READ_POLL`, and left
        there. Setting it per read - as this did - reconfigures a serial port on
        every assignment, and on Windows that loses bytes: on a kit, a stop
        acknowledgement arrived as ``{{)} Acall...}`` and the next reply lost its
        opening braces, while the same exchange over a port left alone came
        back clean every time. A line cut short by the poll stays in the
        transport's buffer and is finished by the next read.
        """
        if self._transport.timeout != READ_POLL:
            self._transport.timeout = READ_POLL
        try:
            raw = self._transport.read_message()
        except TransportTimeoutError:
            return None
        except ConnectionFailedError:
            raise
        except TransportError:
            return None

        text = raw.decode("ascii", errors="replace").strip()
        if not text:
            return None
        _LOG.debug("<< %s", text)
        self._write_log("<", text)
        return text

    def _drain(self) -> None:
        """Discard whatever the board was saying before we started."""
        while self._read_line() is not None:
            pass
