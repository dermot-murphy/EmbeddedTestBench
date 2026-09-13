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

Traces to: S2LP-FR-001 .. S2LP-FR-004, S2LP-FR-035, S2LP-DD-SESSION.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator, List, Optional

from ...core.errors import (
    ConnectionFailedError,
    ProtocolError,
    TransportError,
    TransportTimeoutError,
)
from ...core.transport.base import Transport
from .constants import DEFAULT_TIMEOUT, STOP_CHARACTER
from .protocol import Reply, format_command, parse_reply

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
        #: Lines the firmware sent that were not part of any reply. Kept rather
        #: than dropped: a line nobody expected is evidence, not noise.
        self.unclaimed: List[str] = []

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
        return self.read_reply(timeout=timeout, command=name)

    def read_reply(self, timeout: Optional[float] = None, command: str = "") -> Reply:
        """Read lines until the braces balance, and parse them."""
        limit = self._timeout if timeout is None else float(timeout)
        deadline = time.monotonic() + limit
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
            line = self._read_line(min(remaining, 0.5))
            if line is None:
                continue
            if not started and not line.lstrip().startswith("{"):
                # Output from before this command, or an error line. Keep it.
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

    def stop(self) -> None:
        """End a batch command early.

        ST's firmware polls the port for this one character inside its capture
        loops. It is sent without a terminator on purpose: the firmware reads a
        character, not a line.
        """
        _LOG.debug(">> (stop)")
        self._write_log(">", "(stop)")
        self._transport.write(STOP_CHARACTER, append_terminator=False)

    # ------------------------------------------------------------------
    def _read_line(self, timeout: float) -> Optional[str]:
        """Read one line, or ``None`` on timeout."""
        previous = self._transport.timeout
        self._transport.timeout = max(float(timeout), 0.01)
        try:
            raw = self._transport.read_message()
        except TransportTimeoutError:
            return None
        except ConnectionFailedError:
            raise
        except TransportError:
            return None
        finally:
            self._transport.timeout = previous

        text = raw.decode("ascii", errors="replace").strip()
        if not text:
            return None
        _LOG.debug("<< %s", text)
        self._write_log("<", text)
        return text

    def _drain(self) -> None:
        """Discard whatever the board was saying before we started."""
        while self._read_line(0.01) is not None:
            pass
