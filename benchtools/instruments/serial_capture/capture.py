"""Driver for the serial capture instrument: record what a device prints.

The instrument opens a device's serial port - its console, a test UART - and
records the lines the device prints, for a time window or until a line matches
a pattern. A test then checks the lines: how many came, whether one matched,
the value a matching line carried.

It only listens. Nothing is ever written to the device's port.

It is controlled in two equivalent ways:

* the command set, in the form of the Kepler BLE console (#247) -
  ``WR WINDOW 5000``, ``ROUTINE START CAPTURE``, ``RD COUNT`` - through
  :meth:`SerialCapture.command`, from a specification or the
  ``benchtools serial`` command line; see :mod:`.console`;
* the Python methods the commands map onto: :meth:`SerialCapture.capture`,
  :meth:`~SerialCapture.start_capture` and the rest.

**Every captured line goes to the event log** as a ``line`` record under the
instrument's name. ``WR LINES ON`` adds a live copy of each line,
``LINE <n> = <text>``, while the capture runs; it is off until switched on, and
only that command switches it.

Traces to: SER-FR-001, SER-FR-006 .. SER-FR-009, SER-ARC-001, SER-DD-DRIVER.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Pattern, Tuple

from ...core.errors import (
    ConfigurationError,
    InstrumentError,
    TransportError,
    TransportTimeoutError,
)
from ...core.events import log_event
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from ...core.transport.mock import MockTransport
from .constants import (
    ABORTED,
    BAUD_RANGE,
    COMPLETE,
    DATA_BITS,
    DEFAULT_BAUDRATE,
    DEFAULT_FORMAT,
    DEFAULT_TIMEOUT,
    DEFAULT_WINDOW_MS,
    IDLE_SLEEP,
    LINE_PREFIX,
    MANUFACTURER,
    MAX_LINES,
    MODEL,
    NOT_STARTED,
    PARITIES,
    READ_POLL,
    RUNNING,
    STOP_BITS,
    WINDOW_RANGE_MS,
)
from .errors import CaptureBusyError
from .simulator import SimulatedSerialDevice

__all__ = [
    "SerialCapture",
    "CapturedLine",
    "CaptureResult",
    "CaptureBusyError",
    "parse_format",
    "split_lines",
    "OutputLock",
]

#: ``8N1``: data bits, parity, stop bits.
_FORMAT = re.compile(r"^([5-8])([NEOMS])([12])$")

#: Seconds to wait for a stopped reader to finish. It finishes within one
#: read of the port, :data:`~.constants.READ_POLL`, so this is only reached
#: by a port that has hung.
_JOIN_TIMEOUT = 5.0

#: Bytes a line may grow to with no ending before it is kept as a line anyway,
#: so a device that never ends a line cannot exhaust memory.
_MAX_LINE_BYTES = 65536

_CR = 0x0D
_LF = 0x0A


class OutputLock:
    """A re-entrant lock that can say whether this thread holds it.

    The driver needs to know: a thread that holds it while it stops a
    capture cannot wait for the live lines to be shown, because showing
    them needs this lock (#318).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._owner: Optional[int] = None
        self._depth = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Take the lock, as :meth:`threading.RLock.acquire` does."""
        if not self._lock.acquire(blocking, timeout):  # pylint: disable=consider-using-with
            return False
        self._owner = threading.get_ident()
        self._depth += 1
        return True

    def release(self) -> None:
        """Give the lock back."""
        self._depth -= 1
        if self._depth == 0:
            self._owner = None
        self._lock.release()

    def held(self) -> bool:
        """``True`` if this thread holds the lock."""
        return self._owner == threading.get_ident()

    def __enter__(self) -> "OutputLock":
        self.acquire()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()


class _LineState:  # pylint: disable=too-few-public-methods
    """What :func:`split_lines` carries from one chunk of bytes to the next."""

    def __init__(self) -> None:
        self.pending = bytearray()
        #: The byte that, coming next, ends nothing: the second half of a CRLF
        #: or LFCR pair, or either ending after a line cut at its limit.
        self.skip: tuple = ()


def split_lines(state: _LineState, data: bytes) -> List[str]:
    """The lines *data* completes, with what is left kept in *state*.

    A line ends at CR, at LF, or at a CRLF or LFCR pair, so a device that
    ends its lines with CR alone is read as well as one that uses LF (#318).
    A pair split across two chunks is one ending, not two. A line cut at
    :data:`_MAX_LINE_BYTES` takes the ending that follows it, if one does,
    rather than a blank line after it. A byte that is not ASCII is kept as
    ``\\xNN``, so any console can print the line.
    """
    lines: List[str] = []
    for byte in bytearray(data):
        skip, state.skip = state.skip, ()
        if byte in skip:
            # The pair after a CR or LF, or the ending of a line just cut:
            # it ends nothing more, but a CR after a cut is still half a pair.
            if len(skip) == 2:
                state.skip = (_LF,) if byte == _CR else (_CR,)
            continue
        if byte in (_CR, _LF):
            lines.append(bytes(state.pending).decode("ascii", errors="backslashreplace"))
            state.pending.clear()
            state.skip = (_LF,) if byte == _CR else (_CR,)
        else:
            state.pending.append(byte)
            if len(state.pending) >= _MAX_LINE_BYTES:
                lines.append(bytes(state.pending).decode("ascii", errors="backslashreplace"))
                state.pending.clear()
                state.skip = (_CR, _LF)
    return lines


def parse_format(text: str) -> Tuple[int, str, int]:
    """Split a character format such as ``8N1`` into its three parts.

    :raises ValueError: for anything that is not data bits 5-8, parity
        ``N``/``E``/``O``/``M``/``S`` and stop bits 1 or 2.
    """
    match = _FORMAT.match(str(text).strip().upper())
    if not match:
        raise ValueError(
            "%r is not a character format; give data bits %s, parity %s and "
            "stop bits %s, such as 8N1"
            % (text, "/".join(map(str, DATA_BITS)), "/".join(PARITIES),
               "/".join(map(str, STOP_BITS)))
        )
    return int(match.group(1)), match.group(2), int(match.group(3))


@dataclass(frozen=True)
class CapturedLine:
    """One line the device printed.

    :ivar number: Its place in the capture, from 1.
    :ivar text: The line, without its ending.
    :ivar elapsed: Seconds from the start of the capture to its arrival.
    """

    number: int
    text: str
    elapsed: float

    def as_dict(self) -> Dict[str, Any]:
        """The line as a JSON-ready dictionary."""
        return {"number": self.number, "text": self.text, "elapsed": self.elapsed}


@dataclass(frozen=True)
class CaptureResult:  # pylint: disable=too-many-instance-attributes
    """What a capture recorded, as ``ROUTINE RESULTS CAPTURE`` reports it.

    A specification checks it through its fields: ``count``, ``matched``,
    ``match``, ``value``, ``status``, or ``lines`` with an index.

    :ivar status: ``Not Started``, ``Running``, ``Aborted`` or ``Complete``.
    :ivar count: Lines captured. It counts lines dropped beyond
        :data:`~.constants.MAX_LINES` too.
    :ivar lines: The lines kept, oldest first.
    :ivar pattern: The pattern the capture looked for, or ``""``.
    :ivar match: The first line that matched it, or ``None``.
    :ivar match_number: That line's number, or ``0``.
    :ivar value: The pattern's first group in that line, when the pattern
        has a group, or ``None``.
    :ivar elapsed: Seconds the capture ran.
    :ivar error: Why the port stopped the capture, for an ``Aborted``
        capture that was not aborted by a command; otherwise ``""``.
    :ivar unshown: Live lines (``WR LINES ON``) dropped because the live
        output fell :data:`~.constants.MAX_LINES` behind. They are still
        captured and logged.
    """

    status: str = NOT_STARTED
    count: int = 0
    lines: Tuple[CapturedLine, ...] = ()
    pattern: str = ""
    match: Optional[str] = None
    match_number: int = 0
    value: Optional[str] = None
    elapsed: float = 0.0
    error: str = ""
    unshown: int = 0

    @property
    def matched(self) -> bool:
        """``True`` if a line matched the pattern."""
        return self.match is not None

    @property
    def text(self) -> str:
        """The lines kept, joined by newlines."""
        return "\n".join(line.text for line in self.lines)

    def summary(self) -> str:
        """The status as ``ROUTINE RESULTS CAPTURE`` words it.

        ``Not Started``; ``Running, 4 lines``; ``Complete, 12 lines``;
        ``Complete, 12 lines, Matched``; ``Complete, 50 lines, Not Matched``;
        ``Aborted, 3 lines``. Live lines that were not shown are added at
        the end when there are any: ``Complete, 40 lines, 12 unshown``.
        """
        if self.status == NOT_STARTED:
            return NOT_STARTED
        words = "%s, %d line%s" % (self.status, self.count, "" if self.count == 1 else "s")
        if self.pattern and self.status != RUNNING:
            words += ", Matched" if self.matched else ", Not Matched"
        if self.unshown:
            words += ", %d unshown" % self.unshown
        return words

    def as_dict(self) -> Dict[str, Any]:
        """The result as a JSON-ready dictionary."""
        return {
            "status": self.status,
            "count": self.count,
            "pattern": self.pattern,
            "matched": self.matched,
            "match": self.match,
            "match_number": self.match_number,
            "value": self.value,
            "elapsed": self.elapsed,
            "error": self.error,
            "unshown": self.unshown,
            "lines": [line.as_dict() for line in self.lines],
        }


@dataclass
class _Run:  # pylint: disable=too-many-instance-attributes
    """The state of one capture, shared with its reader thread."""

    pattern: Optional[Pattern[str]]
    window_s: float
    started: float
    status: str = RUNNING
    count: int = 0
    lines: Deque[CapturedLine] = field(default_factory=lambda: deque(maxlen=MAX_LINES))
    match: Optional[str] = None
    match_number: int = 0
    value: Optional[str] = None
    ended: Optional[float] = None
    error: str = ""
    #: Set to stop this run's reader. One per run, so a reader that is
    #: still finishing cannot take lines from the capture after it (#318).
    stop: threading.Event = field(default_factory=threading.Event)
    framing: _LineState = field(default_factory=_LineState)
    #: Live lines waiting for ``on_line``. A thread of their own shows them,
    #: so a slow ``on_line`` never holds up the reading of the port (#318).
    #: Bounded like the lines kept; a line that does not fit is counted in
    #: ``unshown`` rather than waited for.
    shown: "queue.Queue[str]" = field(default_factory=lambda: queue.Queue(maxsize=MAX_LINES))
    unshown: int = 0
    #: Set when the reader has finished: the show thread then ends once the
    #: queue is empty.
    read_done: threading.Event = field(default_factory=threading.Event)


class SerialCapture(Instrument):  # pylint: disable=too-many-instance-attributes
    """Record the lines a device prints on its serial port.

    :param make_transport: Builds the link for a line rate and character
        format. The driver calls it again when ``WR BAUD`` or ``WR FORMAT``
        changes either, so the port reopens with the new settings.
    :param resource: The port, as given: reported by ``RD PORT``.
    :param baudrate: Line rate.
    :param char_format: Character format, such as ``8N1``.
    :param window_ms: Capture window in milliseconds.
    :param pattern: Pattern that ends a capture, or ``""`` for none.
    :param on_line: Called with ``LINE <n> = <text>`` for each captured line
        while ``WR LINES ON``, holding :attr:`output_lock`. Without it, those
        lines go to the log at INFO. An error from it is logged, and the
        capture goes on.

    Example::

        from benchtools.instruments.serial_capture import SerialCapture

        with SerialCapture.connect("COM5", baudrate=115200) as uart:
            print(uart.command("WR PATTERN ^SELF TEST (PASS|FAIL)").text)
            result = uart.capture(window_ms=10000)
            print(result.summary(), result.match)
    """

    SIMULATOR_CLASS = SimulatedSerialDevice
    MODEL_NAME = MODEL
    EVENT_SOURCE = "SERIAL"

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        make_transport: Callable[[int, str], Transport],
        resource: str = "sim://",
        baudrate: int = DEFAULT_BAUDRATE,
        char_format: str = DEFAULT_FORMAT,
        window_ms: int = DEFAULT_WINDOW_MS,
        pattern: str = "",
        on_line: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(auto_check_errors=False)
        self._check_baudrate(baudrate)
        parse_format(char_format)
        self._make_transport = make_transport
        self._resource = resource
        self._baudrate = int(baudrate)
        self._format = str(char_format).strip().upper()
        self._window_ms = DEFAULT_WINDOW_MS
        self.window_ms = window_ms
        self._pattern_text = ""
        self.pattern = pattern
        self._lines_on = False
        self.on_line = on_line
        self._lock = threading.Lock()
        self._run: Optional[_Run] = None
        self._reader: Optional[threading.Thread] = None
        self._shower: Optional[threading.Thread] = None
        #: Held while a live line is handed to ``on_line``. A caller that
        #: prints command replies holds it while it runs a command and prints
        #: the reply, so that a reply comes before the lines that follow it.
        #: The reader never waits on it once its capture is stopped.
        self.output_lock = OutputLock()
        self._transport = make_transport(self._baudrate, self._format)
        self._adopt(self._transport)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        cls,
        resource: str = "sim://",
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        char_format: str = DEFAULT_FORMAT,
        window_ms: int = DEFAULT_WINDOW_MS,
        pattern: str = "",
        on_line: Optional[Callable[[str], None]] = None,
        initialise: bool = True,
        simulated_lines: Optional[List[str]] = None,
        simulated_interval: Optional[float] = None,
    ) -> "SerialCapture":
        """Open a device's serial port.

        :param resource: ``COM5``, ``/dev/ttyUSB0``, ``serial://COM5`` or
            ``sim://``. A bare port name is taken as a serial port, not as a
            host name.
        :param timeout: Seconds :meth:`capture` waits beyond its window
            before giving up on the reader.
        :param simulated_lines: ``sim://`` only: the lines the simulated
            device prints when a capture starts.
        :param simulated_interval: ``sim://`` only: seconds between them.
        """
        target = cls._normalise_resource(resource)
        try:
            parse_format(char_format)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        simulator = SimulatedSerialDevice(
            simulated_lines,
            **({} if simulated_interval is None else {"interval": simulated_interval}),
        )

        def make_transport(rate: int, fmt: str) -> Transport:
            bits, parity, stops = parse_format(fmt)
            serial = target.startswith("serial://")
            return open_transport(
                target,
                timeout=timeout,
                open_now=False,
                responder_factory=lambda: simulator,
                **({"baudrate": rate, "bytesize": bits, "parity": parity,
                    "stopbits": stops} if serial else {}),
            )

        instrument = cls(make_transport, resource=resource, baudrate=baudrate,
                         char_format=char_format, window_ms=window_ms,
                         pattern=pattern, on_line=on_line)
        instrument._capture_timeout = float(timeout)
        if initialise:
            try:
                instrument.initialise()
            except Exception:
                instrument.close()
                raise
        return instrument

    #: Seconds :meth:`capture` waits for the reader beyond the window.
    _capture_timeout = DEFAULT_TIMEOUT

    @staticmethod
    def _normalise_resource(resource: str) -> str:
        """Accept a bare port name as a serial port rather than a host name."""
        text = (resource or "").strip()
        if not text:
            return "sim://"
        if "://" in text or text.lower() in ("sim", "mock"):
            return text
        return "serial://%s" % text

    def _open(self) -> None:
        self._transport.open()
        self._transport.timeout = READ_POLL

    def _close(self) -> None:
        self._stop_reader(ABORTED)
        self._finish_live_output()
        self._transport.close()

    def stop_live_output(self) -> None:
        """Drop the live lines still waiting to be shown.

        For a caller that cannot wait for them, such as a command line
        interrupted while it closes. They are counted in ``unshown``.
        """
        with self._lock:
            run = self._run
        if run is not None:
            run.stop.set()

    @property
    def is_open(self) -> bool:
        return self._transport.is_open

    def _read_identity(self) -> InstrumentIdentity:
        port = self._resource or "sim://"
        return InstrumentIdentity(
            raw="%s,%s,%s" % (MANUFACTURER, MODEL, port),
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=port,
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @property
    def port(self) -> str:
        """The port, as it was given."""
        return self._resource

    @property
    def baudrate(self) -> int:
        """The line rate."""
        return self._baudrate

    @property
    def char_format(self) -> str:
        """The character format, such as ``8N1``."""
        return self._format

    @property
    def window_ms(self) -> int:
        """How long a capture runs if no line matches the pattern first."""
        return self._window_ms

    @window_ms.setter
    def window_ms(self, value: int) -> None:
        value = int(value)
        low, high = WINDOW_RANGE_MS
        if not low <= value <= high:
            raise ValueError("a capture window is %d to %d ms, not %d" % (low, high, value))
        self._window_ms = value

    @property
    def pattern(self) -> str:
        """The pattern that ends a capture, searched for in each line, or ``""``."""
        return self._pattern_text

    @pattern.setter
    def pattern(self, value: Optional[str]) -> None:
        text = value or ""
        if text:
            try:
                re.compile(text)
            except re.error as exc:
                raise ValueError("%r is not a regular expression: %s" % (text, exc)) from exc
        self._pattern_text = text

    @property
    def lines_on(self) -> bool:
        """``True`` while captured lines are shown live (``WR LINES ON``)."""
        return self._lines_on

    def set_lines(self, on: bool) -> None:
        """Switch the live line output on or off (``WR LINES ON``/``OFF``)."""
        self._lines_on = bool(on)

    def set_baudrate(self, baudrate: int) -> None:
        """Change the line rate, reopening the port.

        :raises CaptureBusyError: while a capture is running.
        :raises ValueError: for a rate outside :data:`~.constants.BAUD_RANGE`.
        """
        self._check_baudrate(baudrate)
        self._reconfigure(int(baudrate), self._format)

    def set_format(self, char_format: str) -> None:
        """Change the character format, reopening the port.

        :raises CaptureBusyError: while a capture is running.
        :raises ValueError: for a format :func:`parse_format` refuses.
        """
        parse_format(char_format)
        self._reconfigure(self._baudrate, str(char_format).strip().upper())

    @staticmethod
    def _check_baudrate(baudrate: Any) -> None:
        low, high = BAUD_RANGE
        if not low <= int(baudrate) <= high:
            raise ValueError("a line rate is %d to %d baud, not %s" % (low, high, baudrate))

    def _reconfigure(self, baudrate: int, char_format: str) -> None:
        if self.running:
            raise CaptureBusyError("the port settings cannot change while a capture runs")
        if (baudrate, char_format) == (self._baudrate, self._format):
            return
        was_open = self.is_open
        old = (self._baudrate, self._format)
        self._transport.close()
        try:
            self._transport = self._make_transport(baudrate, char_format)
            if was_open:
                self._open()
        except (TransportError, ValueError):
            self._transport = self._make_transport(*old)
            if was_open:
                self._open()
            raise
        finally:
            self._adopt(self._transport)
        self._baudrate, self._format = baudrate, char_format
        self._logger.info("port settings now %d baud %s", baudrate, char_format)

    # ------------------------------------------------------------------
    # The capture routine
    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        """``True`` while a capture runs."""
        with self._lock:
            return self._run is not None and self._run.status == RUNNING

    def start_capture(self, window_ms: Optional[int] = None,
                      pattern: Optional[str] = None) -> CaptureResult:
        """Start a capture (``ROUTINE START CAPTURE``) and return at once.

        The previous capture's lines are discarded, and so is anything the
        device printed before now. *window_ms* and *pattern*, when given,
        replace the instrument's settings first, as ``WR WINDOW`` and
        ``WR PATTERN`` would.

        :raises CaptureBusyError: if a capture is already running.
        """
        if self.running:
            raise CaptureBusyError("a capture is already running; abort it first")
        self._join_reader()
        if self._reader is not None and self._reader.is_alive():
            raise CaptureBusyError("the last capture's reader has not stopped")
        if not self._finish_live_output():
            raise CaptureBusyError("the last capture's live output has not stopped")
        if window_ms is not None:
            self.window_ms = window_ms
        if pattern is not None:
            self.pattern = pattern
        if not self.is_open:
            self._open()
        self._transport.discard_input()
        restart = getattr(getattr(self._transport, "responder", None), "restart", None)
        if callable(restart):
            restart()
        run = _Run(
            pattern=re.compile(self._pattern_text) if self._pattern_text else None,
            window_s=self._window_ms / 1000.0,
            started=time.monotonic(),
        )
        with self._lock:
            self._run = run
        # The result is taken before the reader starts: a capture can be
        # complete by the time this thread runs again, and the reply to
        # ROUTINE START CAPTURE is that it started.
        started = self.results()
        self._shower = threading.Thread(target=self._show_until_done, args=(run,),
                                        name="serial-capture-lines", daemon=True)
        self._reader = threading.Thread(target=self._read_until_done, args=(run,),
                                        name="serial-capture", daemon=True)
        self._shower.start()
        self._reader.start()
        self._logger.info("capture started: window %d ms, pattern %s",
                          self._window_ms, self._pattern_text or "none")
        return started

    def abort_capture(self) -> CaptureResult:
        """Stop a running capture (``ROUTINE ABORT CAPTURE``).

        A capture that is not running is left as it is.
        """
        self._stop_reader(ABORTED)
        return self.results()

    def wait_capture(self, timeout: Optional[float] = None) -> CaptureResult:
        """Wait for the running capture to end, and return its result.

        :param timeout: Seconds to wait. By default, what is left of the
            window plus the connect timeout.
        :raises InstrumentError: if the capture is still running after it.
        """
        reader = self._reader
        if reader is not None:
            if timeout is None:
                with self._lock:
                    run = self._run
                left = 0.0 if run is None else run.started + run.window_s - time.monotonic()
                timeout = max(left, 0.0) + self._capture_timeout
            ends = time.monotonic() + timeout
            reader.join(timeout)
            if reader.is_alive():
                raise InstrumentError("the capture was still running after %.1f s" % timeout)
            # The live lines are all shown before the result is returned, so
            # a caller printing both prints the lines first.
            shower = self._shower
            if shower is not None:
                shower.join(max(ends - time.monotonic(), 0.0) + _JOIN_TIMEOUT)
                if shower.is_alive():
                    self._logger.warning("the capture has ended, but its live lines are "
                                         "still being shown")
        return self.results()

    def capture(self, window_ms: Optional[int] = None, pattern: Optional[str] = None,
                timeout: Optional[float] = None) -> CaptureResult:
        """Run a capture to its end and return what it recorded.

        It ends when a line matches the pattern or when the window runs out,
        whichever comes first. A capture that heard nothing is a result with
        ``count`` 0, not an error, so that silence fails a limit.
        """
        self.start_capture(window_ms=window_ms, pattern=pattern)
        return self.wait_capture(timeout)

    def results(self) -> CaptureResult:
        """The current or last capture's result (``ROUTINE RESULTS CAPTURE``)."""
        with self._lock:
            run = self._run
            if run is None:
                return CaptureResult()
            end = run.ended if run.ended is not None else time.monotonic()
            return CaptureResult(
                status=run.status,
                count=run.count,
                lines=tuple(run.lines),
                pattern=run.pattern.pattern if run.pattern else "",
                match=run.match,
                match_number=run.match_number,
                value=run.value,
                elapsed=round(end - run.started, 6),
                error=run.error,
                unshown=run.unshown,
            )

    def line(self, number: int) -> str:
        """The text of captured line *number*, counting from 1.

        :raises IndexError: for a line that was not captured, or no longer kept.
        """
        result = self.results()
        for item in result.lines:
            if item.number == int(number):
                return item.text
        raise IndexError("line %s was not captured, or is no longer kept" % number)

    def command(self, request: str):
        """Run one command of the command set and return its reply.

        See :mod:`.console` for the commands. The reply is an object whose
        ``text`` is the reply line, ``ok`` is ``True`` for ``ACK``, and
        ``value`` is what follows `` = `` in an ``RD`` reply.
        """
        from .console import execute
        reply = execute(self, request)
        self._logger.info("%s -> %s", reply.command, reply.text)
        return reply

    # ------------------------------------------------------------------
    def _stop_reader(self, status: str) -> None:
        stopped = False
        with self._lock:
            run = self._run
            if run is not None and run.status == RUNNING:
                run.status = status
                run.ended = time.monotonic()
                stopped = True
                # Only a capture that is running is stopped. One that has
                # ended keeps its live lines, and close() shows them (#318).
                run.stop.set()
        # A stopped show thread ends within one READ_POLL; one whose capture
        # had already ended is left to show its lines, and not waited for:
        # the caller may hold output_lock, which showing them needs.
        self._join_reader(shower=stopped)
        if stopped:
            self._logger.info("capture aborted after %d lines", run.count)

    def _join_reader(self, shower: bool = True) -> None:
        """Wait for the reader, and the line shower too, to finish.

        Neither is waited for from its own thread.
        """
        for thread in (self._reader, self._shower if shower else None):
            if thread is None or thread is threading.current_thread():
                continue
            thread.join(_JOIN_TIMEOUT)
            if thread.is_alive():
                self._logger.warning("the capture's %s thread did not stop within %.0f s",
                                     thread.name, _JOIN_TIMEOUT)

    def _finish_live_output(self) -> bool:
        """Let the last capture's live lines be shown, then end the show thread.

        The lines are waited for up to :data:`_JOIN_TIMEOUT`, unless this
        thread holds :attr:`output_lock`, which showing them needs. Lines
        still waiting after that are dropped and counted in ``unshown``.
        ``False`` if the show thread still has not ended: an ``on_line``
        that does not return.
        """
        shower = self._shower
        if shower is None or not shower.is_alive() or shower is threading.current_thread():
            return True
        if not self.output_lock.held():
            shower.join(_JOIN_TIMEOUT)
        if shower.is_alive():
            with self._lock:
                run = self._run
            if run is not None:
                run.stop.set()
            shower.join(READ_POLL * 4)
        if shower.is_alive():
            self._logger.warning("the capture's live output did not stop")
            return False
        return True

    def _show_until_done(self, run: _Run) -> None:
        """Show the run's live lines in order until the reader has finished.

        A stopped run shows nothing more: the lines still waiting are dropped,
        as an abort means.
        """
        while not run.stop.is_set():
            try:
                shown = run.shown.get(timeout=READ_POLL)
            except queue.Empty:
                # The reader queues every line before it sets read_done, so
                # once it is set an empty queue is really the end; a line
                # queued after the timeout is still taken (#318).
                if run.read_done.is_set() and run.shown.empty():
                    return
                continue
            self._show(run, shown)
        dropped = 0
        while True:
            try:
                run.shown.get_nowait()
            except queue.Empty:
                break
            dropped += 1
        if dropped:
            with self._lock:
                run.unshown += dropped
            self._logger.info("%d live lines not shown: the live output was stopped", dropped)

    def _read_until_done(self, run: _Run) -> None:
        try:
            self._read_run(run)
        finally:
            run.read_done.set()
            if run.unshown:
                self._logger.warning("%d live lines were not shown: the live output "
                                     "fell %d lines behind", run.unshown, MAX_LINES)

    def _read_run(self, run: _Run) -> None:
        deadline = run.started + run.window_s
        window = "window of %d ms ended" % round(run.window_s * 1000)
        try:
            while not run.stop.is_set():
                if time.monotonic() >= deadline:
                    self._finish(run, window)
                    return
                arrived, lines = self._read_lines(run)
                # Lines that arrived after the window closed are not in it.
                # The time is when they arrived, not when they are handled:
                # a slow live output must not push lines out of the window.
                if lines and arrived >= deadline:
                    self._finish(run, window)
                    return
                for text in lines:
                    if run.stop.is_set():
                        return
                    if self._record(run, text, arrived):
                        self._finish(run, "line %d matched %s" % (run.match_number,
                                                                  run.pattern.pattern))
                        return
        # Any failure of the port ends the capture, and the result says why;
        # the thread does not end silently with the capture still Running.
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.error("capture stopped: %s", exc)
            with self._lock:
                if run.status == RUNNING:
                    run.status = ABORTED
                    run.ended = time.monotonic()
                    run.error = str(exc) or type(exc).__name__

    def _finish(self, run: _Run, why: str) -> None:
        with self._lock:
            if run.status != RUNNING:
                return
            run.status = COMPLETE
            run.ended = time.monotonic()
        self._logger.info("capture complete, %d lines: %s", run.count, why)

    def _record(self, run: _Run, text: str, arrived: float) -> bool:
        """Keep and log one line that arrived at *arrived*.

        ``True`` if it matched the pattern. A line is not kept once its
        capture has ended, however that happened.
        """
        elapsed = arrived - run.started
        with self._lock:
            if run.status != RUNNING:
                return False
            run.count += 1
            item = CapturedLine(run.count, text, round(elapsed, 6))
            run.lines.append(item)
            found = run.pattern.search(text) if run.pattern else None
            if found and run.match is None:
                run.match = text
                run.match_number = item.number
                run.value = found.group(1) if found.re.groups else None
        shown = "%s %d = %s" % (LINE_PREFIX, item.number, text)
        level = logging.INFO if self._lines_on and self.on_line is None else logging.DEBUG
        log_event(self._logger, "line", shown, item.as_dict(), level=level)
        if self._lines_on and self.on_line is not None:
            try:
                run.shown.put_nowait(shown)
            except queue.Full:
                with self._lock:
                    run.unshown += 1
        return found is not None

    def _show(self, run: _Run, shown: str) -> None:
        """Hand one live line to ``on_line``, unless the capture is stopped first.

        The lock is waited for in short steps, checking the run's stop event
        between them, so a reader is never held by a caller that is printing
        a reply while it aborts this capture.
        """
        while not run.stop.is_set():
            if self.output_lock.acquire(timeout=READ_POLL):  # pylint: disable=consider-using-with
                try:
                    self.on_line(shown)
                # The live copy is a convenience; a failure to show a line
                # (a console that cannot print it) must not end the capture.
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    self._logger.warning("the live line output failed: %s", exc)
                finally:
                    self.output_lock.release()
                return

    def _read_lines(self, run: _Run) -> Tuple[float, List[str]]:
        """When one read of the port returned, and the lines it completed.

        Nothing arriving is no lines. The simulator says at once that it has
        nothing, so that is idle too; any other error from the port is raised,
        which ends the capture ``Aborted`` with the error.
        """
        try:
            data = self._transport.read_available()
        except TransportTimeoutError:
            return time.monotonic(), []
        except TransportError:
            if not isinstance(self._transport, MockTransport):
                raise
            time.sleep(IDLE_SLEEP)
            return time.monotonic(), []
        return time.monotonic(), split_lines(run.framing, data)
