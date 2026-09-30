"""Base class for behavioural instrument simulators.

Every instrument driver in this repository ships a simulator, so that the
driver, the SCPI vocabulary it emits and the analysis above it can all be
verified without hardware. The machinery those simulators share - compound
message splitting, handler dispatch, the IEEE 488.2 mandated queries, the
event queue and binary replies - lives here.

A concrete simulator subclasses :class:`SimulatedInstrument`, overrides
:meth:`reset` to declare its state, and adds one ``_cmd_<slug>`` method per
command it answers. The slug is the SCPI header uppercased with ``:``
replaced by ``_``, a trailing ``?`` replaced by ``_Q``, and any leading ``*``
removed - so ``CH1:SCALE?`` dispatches to ``_cmd_CH1_SCALE_Q`` and ``*IDN?``
to ``_cmd_IDN_Q``.

Unrecognised headers are pushed into the event queue exactly as a real
instrument does. That matters more than it sounds: it means a driver that
misspells a command fails a test with an ``InstrumentError`` rather than
silently having the command ignored, which is what real hardware does.

Traces to: CORE-FR-040, CORE-FR-041, CORE-DD-SIM.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple, runtime_checkable

__all__ = [
    "Responder",
    "Streamer",
    "SimulatedInstrument",
    "scpi_slug",
    "format_number",
    "UNDEFINED_HEADER",
    "DATA_OUT_OF_RANGE",
    "COMMAND_ERROR",
]

#: Event code a real instrument reports for an unrecognised command header.
UNDEFINED_HEADER = 113

#: Event code for a value outside the instrument's accepted range.
DATA_OUT_OF_RANGE = 222

#: Event code for a command that is recognised but used incorrectly.
COMMAND_ERROR = 100

#: Standard Event Status Register bit for a command error.
ESR_COMMAND_ERROR = 0x20


@runtime_checkable
class Responder(Protocol):
    """Anything that can answer a raw instrument message.

    :class:`~benchtools.core.transport.mock.MockTransport` accepts any object
    satisfying this protocol, which is what keeps the transport layer free of
    any dependency on a particular instrument's simulator.
    """

    def respond(self, message: bytes) -> Optional[bytes]:
        """Return the raw reply to *message*, or ``None`` if there is none."""
        ...


class Streamer(Protocol):
    """A responder that also speaks when it is not spoken to.

    Some instruments push data without being asked: a BLE dongle reporting
    advertising packets, a protocol analyser reporting frames, a logger sending
    a reading every second. A simulator for one of those implements ``poll()``
    beside ``respond()``, and
    :class:`~benchtools.core.transport.mock.MockTransport` calls it when the
    driver reads with no reply outstanding.

    ``poll()`` must not block: it returns whatever the instrument has to say
    now, or ``b""``. A simulator whose events are on a virtual clock advances
    that clock here, which is what lets a test capture a minute of advertising
    in a few milliseconds and still assert on exact intervals.
    """

    def respond(self, message: bytes) -> Optional[bytes]:
        """Return the raw reply to *message*, or ``None`` if there is none."""
        ...

    def poll(self) -> bytes:
        """Return unsolicited output, or ``b""`` if there is none."""
        ...


def scpi_slug(head: str) -> str:
    """Map a SCPI header to the suffix of its handler method name.

    ``"*IDN?"`` becomes ``"IDN_Q"``; ``"CH1:SCALE?"`` becomes ``"CH1_SCALE_Q"``.
    """
    text = head.upper().replace("*", "")
    if text.endswith("?"):
        text = text[:-1] + "_Q"
    return text.replace(":", "_")


def format_number(value: float) -> str:
    """Format a float the way an instrument does: NR3, six significant digits."""
    return "%.6E" % float(value)


class SimulatedInstrument:
    """Minimal instrument answering the IEEE 488.2 mandated queries.

    Usable on its own as a stand-in for any instrument that only needs to be
    identified - which is what makes a bare ``sim://`` resource meaningful
    without reference to any specific model.

    :param idn: Identification string returned by ``*IDN?``.
    """

    #: Default ``*IDN?`` response. Subclasses override.
    DEFAULT_IDN = "BENCHTOOLS,SIMULATED INSTRUMENT,0,1.0"

    def __init__(self, idn: Optional[str] = None) -> None:
        self.idn = idn if idn is not None else self.DEFAULT_IDN
        #: Every command element received, in order. Tests assert on this.
        self.command_log: List[str] = []
        self.events: List[Tuple[int, str]] = []
        self.esr = 0
        self._binary_reply: Optional[bytes] = None
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Return the model to its power-on state.

        Subclasses must call ``super().reset()`` and then set their own state.
        """
        self.events = []
        self.esr = 0
        self._binary_reply = None

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------
    def push_event(self, code: int, message: str) -> None:
        """Record an event, as the instrument's own event queue would."""
        self.events.append((int(code), str(message)))

    def set_binary_reply(self, data: bytes) -> None:
        """Answer the current message with raw bytes instead of text.

        Used for responses that are not ASCII, such as a waveform block or a
        screen image.
        """
        self._binary_reply = bytes(data)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Process one raw message and return the raw reply.

        Text replies are encoded as ASCII with a line-feed terminator; binary
        replies are returned verbatim, exactly as an instrument would stream
        them.
        """
        self._binary_reply = None
        text = self.handle(message.decode("ascii", errors="replace").strip())
        if self._binary_reply is not None:
            return self._binary_reply
        if text is None:
            return None
        return text.encode("ascii") + b"\n"

    def handle(self, message: str) -> Optional[str]:
        """Process one possibly compound SCPI message.

        Elements are separated by ``;``; a leading ``:`` resets to the command
        root, matching SCPI. Responses are joined with ``;``.
        """
        responses = []
        for element in message.split(";"):
            element = element.strip().lstrip(":")
            if not element:
                continue
            self.command_log.append(element)
            reply = self._dispatch(element)
            if reply is not None:
                responses.append(reply)
        return ";".join(responses) if responses else None

    def _dispatch(self, element: str) -> Optional[str]:
        """Route one command element to its handler."""
        head, _, argument = element.partition(" ")
        handler = getattr(self, "_cmd_" + scpi_slug(head), None)
        if handler is not None:
            return handler(argument.strip())
        return self._unknown_command(element)

    def _unknown_command(self, element: str) -> Optional[str]:
        """Handle a command with no registered handler.

        Subclasses override this to add pattern-matched families of commands
        (for example ``CH<n>:<setting>``) before falling back to ``super()``.
        """
        self.push_event(UNDEFINED_HEADER, 'Undefined header; command "%s"' % element)
        self.esr |= ESR_COMMAND_ERROR
        return "" if element.rstrip().endswith("?") else None

    # ------------------------------------------------------------------
    # IEEE 488.2 mandated commands
    # ------------------------------------------------------------------
    def _cmd_IDN_Q(self, _argument: str) -> str:
        return self.idn

    def _cmd_RST(self, _argument: str) -> None:
        self.reset()
        return None

    def _cmd_CLS(self, _argument: str) -> None:
        self.events = []
        self.esr = 0
        return None

    def _cmd_OPC_Q(self, _argument: str) -> str:
        return "1"

    def _cmd_OPC(self, _argument: str) -> None:
        return None

    def _cmd_ESR_Q(self, _argument: str) -> str:
        value = self.esr
        self.esr = 0
        return str(value)

    def _cmd_STB_Q(self, _argument: str) -> str:
        return "32" if self.events else "0"

    def _cmd_WAI(self, _argument: str) -> None:
        return None

    # ------------------------------------------------------------------
    # SCPI standard error queue (instruments that use SYSTem:ERRor?)
    # ------------------------------------------------------------------
    def _cmd_SYSTEM_ERROR_Q(self, _argument: str) -> str:
        if not self.events:
            return '0,"No error"'
        code, message = self.events.pop(0)
        return '%d,"%s"' % (code, message.replace('"', "'"))

    def _cmd_SYSTEM_ERROR_NEXT_Q(self, argument: str) -> str:
        return self._cmd_SYSTEM_ERROR_Q(argument)

    def _cmd_SYSTEM_ERROR_COUNT_Q(self, _argument: str) -> str:
        return str(len(self.events))
