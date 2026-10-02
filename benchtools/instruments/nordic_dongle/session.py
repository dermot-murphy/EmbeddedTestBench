"""One command, one reply, with events arriving in between.

The dongle talks back unprompted: advertising reports, notifications from the
sensor, connection changes. They interleave with command replies on the same
line-oriented link, so a session that simply read the next line after writing a
command would eventually read an advertising report as the answer.

Every line is therefore classified before it is used. Replies satisfy the
command in progress; events are queued for the caller, tagged with the host's
own arrival time. Nothing is discarded - an event that arrives while a command
is outstanding is exactly the event a profile capture must not lose.

Session logging lives here rather than in the driver because this is the only
place that sees the *whole* conversation, including the lines the driver
decided were not interesting. A log that omits what the tooling ignored is no
use when the question is why the tooling ignored it.

Traces to: BLE-FR-002, BLE-FR-060 .. BLE-FR-062, BLE-DD-SESSION.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Callable, Deque, List, Optional, Tuple, Union

from ...core.events import SourceLogger
from ...core.errors import (
    ConnectionFailedError,
    InstrumentError,
    TransportError,
    TransportTimeoutError,
)
from ...core.transport.base import Transport
from .constants import DongleError
from .protocol import Event, Reply, parse_line

__all__ = ["DongleSession", "DongleCommandError"]


#: Events retained when nobody is consuming them. Large enough for a minute of
#: advertising at 20 ms, bounded so an unattended session cannot grow without
#: limit.
_EVENT_BACKLOG = 4096


class DongleCommandError(InstrumentError):
    """The dongle refused a command.

    :param command: What was sent.
    :param error: The firmware's error code.
    :param text: The firmware's message.
    """

    def __init__(self, command: str, error: DongleError, text: str) -> None:
        super().__init__(
            "the dongle refused %r: %s (%s)" % (command, text or error.name, int(error))
        )
        self.command = command
        self.error = error
        self.text = text


class DongleSession:
    """Command/reply over a line link, with an event queue beside it.

    :param transport: An open transport.
    :param timeout: Default seconds to wait for a reply.
    """

    def __init__(self, transport: Transport, timeout: float = 5.0) -> None:
        #: Bound to the owning instrument's event-log name (#126).
        self._logger = SourceLogger(logging.getLogger(__name__))
        self._transport = transport
        self._timeout = float(timeout)
        self._events: Deque[Event] = deque(maxlen=_EVENT_BACKLOG)
        self._log = None
        self._log_path: Optional[str] = None
        self._dropped_notices = 0

    # ------------------------------------------------------------------
    @property
    def transport(self) -> Transport:
        """The underlying link."""
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
    def pending_events(self) -> int:
        """Events queued and not yet taken."""
        return len(self._events)

    @property
    def log_path(self) -> Optional[str]:
        """Where the session is being logged, if it is."""
        return self._log_path

    @property
    def dropped_notices(self) -> int:
        """``+drop`` events seen: lines the dongle could not send."""
        return self._dropped_notices

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Discard anything said before anyone was listening.

        A dongle that has been running has probably emitted events already, and
        a reset one may emit a banner. Neither is the answer to the first
        command.
        """
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            line = self._read_line(0.05)
            if line is None:
                break

    def close(self) -> None:
        """Stop logging. The transport is not closed here; its owner does that."""
        self.stop_log()

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
        self._logger.debug("%s %s", direction, text)
        if self._log is None:
            return
        self._log.write("%.6f %s %s\n" % (time.time(), direction, text))
        self._log.flush()

    # ------------------------------------------------------------------
    def execute(
        self,
        command: str,
        *arguments: str,
        timeout: Optional[float] = None,
        allow_error: bool = False,
    ) -> Reply:
        """Send a command and return its reply.

        :param command: Command word.
        :param arguments: Tokens after the command word.
        :param timeout: Seconds to wait; the session default when omitted.
        :param allow_error: Return the failing reply instead of raising.
        :raises DongleCommandError: on ``err`` when *allow_error* is false.
        :raises TransportTimeoutError: if no reply arrives in time.
        """
        line = " ".join([command] + [str(argument) for argument in arguments])
        limit = timeout if timeout is not None else self._timeout

        self._drain()
        self._write_log(">", line)
        self._transport.write(line.encode("ascii"))

        deadline = time.monotonic() + limit
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise TransportTimeoutError(
                    "the dongle did not answer %r within %.3f s. Check the "
                    "firmware is running (the LED is lit) and that the port is "
                    "the dongle's and not another device's." % (line, limit)
                )
            parsed = self._read_line(remaining)
            if isinstance(parsed, Reply):
                if not parsed.ok and not allow_error:
                    raise DongleCommandError(line, parsed.error or DongleError.UNKNOWN, parsed.text)
                return parsed

    def collect(
        self,
        duration: float,
        on_event: Optional[Callable[[Event], None]] = None,
        stop: Optional[Callable[[Event], bool]] = None,
    ) -> List[Event]:
        """Read events for *duration* seconds, or until *stop* says otherwise.

        Returns everything queued when it finishes, including events that
        arrived earlier and have not been taken, so a caller cannot lose the
        first advertising report by starting to collect a moment late.

        :param on_event: Called for each event as it arrives, for live output.
        :param stop: Called for each event; returning true ends the collection
            immediately. A capture bounded by the instrument's own clock rather
            than the host's needs this: against a simulator, whose clock runs as
            fast as it is read, a wall-clock bound would collect minutes of
            events in a quarter of a second.
        """
        deadline = time.monotonic() + float(duration)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            before = len(self._events)
            self._read_line(min(remaining, 0.25))
            if len(self._events) <= before:
                continue
            for event in list(self._events)[before:]:
                if on_event is not None:
                    on_event(event)
                if stop is not None and stop(event):
                    return self.take_events()
        return self.take_events()

    def wait_for_event(
        self,
        name: Union[str, Tuple[str, ...]],
        timeout: Optional[float] = None,
        match: Optional[Callable[[Event], bool]] = None,
    ) -> Event:
        """Wait for the next event called *name*, or any of several names.

        An event already queued satisfies the wait, so a caller that asks a
        moment after the event arrived is not made to wait for a second one.

        :param name: An event name, or a tuple of them to wait for whichever
            comes first - a success and the failure that rules it out, say.
        :param match: Further condition the event must satisfy.
        :raises TransportTimeoutError: if none arrives in time.
        """
        names = (name,) if isinstance(name, str) else tuple(name)
        limit = timeout if timeout is not None else self._timeout
        deadline = time.monotonic() + limit

        while True:
            for index, event in enumerate(self._events):
                if event.name in names and (match is None or match(event)):
                    del self._events[index]
                    return event
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise TransportTimeoutError(
                    "no '+%s' event from the dongle within %.3f s"
                    % ("' or '+".join(names), limit)
                )
            self._read_line(min(remaining, 0.25))

    def take_events(self, name: Optional[str] = None) -> List[Event]:
        """Remove and return queued events, optionally only those named *name*."""
        if name is None:
            taken = list(self._events)
            self._events.clear()
            return taken
        taken = [event for event in self._events if event.name == name]
        remaining = [event for event in self._events if event.name != name]
        self._events.clear()
        self._events.extend(remaining)
        return taken

    def discard_events(self) -> int:
        """Forget queued events. Returns how many were forgotten."""
        count = len(self._events)
        self._events.clear()
        return count

    # ------------------------------------------------------------------
    def poll(self, limit: int = 100) -> None:
        """Read what the dongle has sent without being asked, queueing its events.

        Sends nothing. An unsolicited ``+disc``, say, is otherwise only read
        when the next command waits for its reply. Each read waits at most
        10 ms, so polling a quiet link costs that; *limit* bounds the lines read,
        so a dongle streaming events cannot hold the caller here.
        """
        for _ in range(limit):
            try:
                parsed = self._read_line(0.01)
            except TransportError:
                return
            if parsed is None:
                try:
                    if not self._transport.has_buffered_data:
                        return
                except TransportError:              # pragma: no cover - defensive
                    return

    def _drain(self) -> None:
        """Take whatever has already arrived, so it is not read as a reply."""
        while True:
            try:
                if not self._transport.has_buffered_data:
                    return
            except TransportError:                      # pragma: no cover - defensive
                return
            if self._read_line(0.01) is None:
                return

    def _read_line(self, timeout: float):
        """Read one line; queue it if it is an event.

        :returns: The parsed line, or ``None`` on timeout or for a line that is
            not part of the protocol.
        """
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

        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return None

        self._write_log("<", text)
        parsed = parse_line(text)
        if parsed is None:
            self._logger.debug("ignoring non-protocol line from the dongle: %r", text)
            return None
        if isinstance(parsed, Event):
            parsed.host_time = time.time()
            if parsed.name == "drop":
                self._dropped_notices += parsed.integer("count", 1)
            self._events.append(parsed)
        return parsed
