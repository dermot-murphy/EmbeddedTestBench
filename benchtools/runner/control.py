"""Controlling a run while it goes: pause, resume, abort, restart (#136).

A run on the bench takes minutes, and an operator watching it needs to stop and
look, stop for good, or go back over a test case without starting again. The
runner obeys a :class:`RunControl` **between steps only**: a step in progress is
an instrument call, and interrupting one leaves the instrument in a state
nobody chose.

:class:`ControlServer` serves a RunControl to another program - the test run
viewer - as JSON Lines over TCP. It binds to 127.0.0.1 and nothing else: a run
drives the bench's supply, so the control channel is never reachable from
another machine. A viewer on another PC goes through the viewer's own server.

One request per line, one reply per line::

    {"cmd": "status"}
    {"cmd": "pause"}
    {"cmd": "resume"}
    {"cmd": "abort"}
    {"cmd": "restart_test"}
    {"cmd": "restart_from", "case": 1, "step": 2}

Every reply carries ``ok``; a refusal carries ``error``, saying why.

ASPICE 4.0 asks each verification measure to define its abort and re-start
criteria (08-60); this is how an operator applies them.

Traces to: RUN-FR-061 .. RUN-FR-065, RUN-DD-CONTROL.
"""

from __future__ import annotations

import json
import logging
import socketserver
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from ..core.events import log_event

__all__ = [
    "PAUSE", "RESUME", "ABORT", "RESTART_TEST", "RESTART_FROM", "STATUS",
    "Command", "RunControl", "ControlServer", "HOST",
]

_LOG = logging.getLogger(__name__)

PAUSE = "pause"
RESUME = "resume"
ABORT = "abort"
RESTART_TEST = "restart_test"
RESTART_FROM = "restart_from"
STATUS = "status"

#: The only address the control channel listens on.
HOST = "127.0.0.1"

#: Longest request line accepted, in bytes.
_MAX_LINE = 4096


@dataclass(frozen=True)
class Command:
    """An instruction the runner acts on at its next checkpoint."""

    kind: str
    case: Optional[int] = None
    step: Optional[int] = None


class RunControl:
    """What an operator has asked of the run, and where the run is.

    The runner calls :meth:`begin`, :meth:`checkpoint` between steps, and
    :meth:`finish`. Anything else - the control server's threads - calls
    :meth:`request`. All state is under one condition variable.

    :param validator: Set by the runner for each run: given a test case and a
        step index, the reason a restart there is refused, or ``None``.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._paused = False
        self._pending: Optional[Command] = None
        self._active = False
        self._suite = ""
        self._position: Dict[str, Any] = {"phase": None, "case": None, "step": None}
        self._validator: Optional[Callable[[int, int], Optional[str]]] = None

    # ------------------------------------------------------------------
    # The runner's side
    # ------------------------------------------------------------------
    def begin(self, suite: str, validator: Callable[[int, int], Optional[str]]) -> None:
        """A run of *suite* has started; *validator* checks restart targets."""
        with self._condition:
            self._active = True
            self._suite = suite
            self._paused = False
            self._pending = None
            self._validator = validator
            self._position = {"phase": None, "case": None, "step": None}

    def finish(self) -> None:
        """The run has ended. Nothing pending carries over to the next."""
        with self._condition:
            self._active = False
            self._paused = False
            self._pending = None
            self._validator = None
            self._position = {"phase": None, "case": None, "step": None}
            self._condition.notify_all()

    def checkpoint(self, phase: str, case: Optional[int], step: Optional[int],
                   interruptible: bool = True) -> Optional[Command]:
        """Called by the runner before each step; the command to act on, if any.

        Blocks while the run is paused, until it is resumed, aborted or
        restarted. With *interruptible* false - teardown - nothing is returned
        and nothing blocks, because teardown always runs to the end.
        """
        with self._condition:
            self._position = {"phase": phase, "case": case, "step": step}
            if not interruptible:
                return None
            if self._paused and self._pending is None:
                log_event(_LOG, "control_applied", "paused before %s step %s" % (phase, step),
                          dict(self._position, command=PAUSE))
            while self._paused and self._pending is None:
                self._condition.wait()
            command, self._pending = self._pending, None
            if command is not None:
                log_event(_LOG, "control_applied", "%s applied" % command.kind, dict(
                    self._position, command=command.kind,
                    target_case=command.case, target_step=command.step))
            return command

    # ------------------------------------------------------------------
    # The operator's side
    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        """Where the run is and whether it is paused."""
        with self._condition:
            return self._status()

    def _status(self) -> Dict[str, Any]:
        if not self._active:
            state = "idle"
        elif self._paused:
            state = "paused"
        else:
            state = "running"
        return dict(self._position, ok=True, state=state, suite=self._suite,
                    pending=self._pending.kind if self._pending else None)

    def request(self, message: Any) -> Dict[str, Any]:
        """Act on one request from the operator; the reply to send back."""
        if not isinstance(message, dict) or not isinstance(message.get("cmd"), str):
            return {"ok": False, "error": "a request is a JSON object with a 'cmd'"}
        kind = message["cmd"]
        with self._condition:
            if kind == STATUS:
                return self._status()
            refusal = self._refusal(kind, message)
            log_event(_LOG, "control", "%s %s%s" % (
                kind, "refused" if refusal else "accepted",
                (": " + refusal) if refusal else ""), dict(
                    self._position, command=kind, accepted=refusal is None, reason=refusal,
                    target_case=message.get("case"), target_step=message.get("step")))
            if refusal:
                return {"ok": False, "error": refusal}
            self._accept(kind, message)
            self._condition.notify_all()
            return self._status()

    def _refusal(  # pylint: disable=too-many-return-statements
            self, kind: str, message: Dict[str, Any]) -> Optional[str]:
        """Why *kind* cannot be done now; ``None`` when it can."""
        if kind not in (PAUSE, RESUME, ABORT, RESTART_TEST, RESTART_FROM):
            return "unknown command %r; known: %s" % (kind, ", ".join(
                (STATUS, PAUSE, RESUME, ABORT, RESTART_TEST, RESTART_FROM)))
        if not self._active:
            return "no run is in progress"
        phase = self._position["phase"]
        if phase == "teardown":
            return "teardown is running and always runs to the end"
        if kind == PAUSE and self._paused:
            return "the run is already paused"
        if kind == RESUME and not self._paused:
            return "the run is not paused"
        if self._pending is not None and kind in (ABORT, RESTART_TEST, RESTART_FROM):
            if self._pending.kind == ABORT:
                return "an abort is already pending"
        if kind in (RESTART_TEST, RESTART_FROM):
            return self._restart_refusal(kind, message)
        return None

    def _restart_refusal(self, kind: str, message: Dict[str, Any]) -> Optional[str]:
        if self._position["phase"] == "setup":
            return "setup is still running; restart once the test cases have begun"
        if kind == RESTART_TEST:
            if self._position["phase"] != "test" or self._position["case"] is None:
                return "no test case is running to restart"
            target: Tuple[Any, Any] = (self._position["case"], 0)
        else:
            target = (message.get("case"), message.get("step", 0))
            if not all(isinstance(item, int) and not isinstance(item, bool)
                       for item in target):
                return "restart_from needs integer 'case' and 'step'"
        if self._validator is None:
            return "this run cannot be restarted"
        return self._validator(target[0], target[1])

    def _accept(self, kind: str, message: Dict[str, Any]) -> None:
        if kind == PAUSE:
            self._paused = True
        elif kind == RESUME:
            self._paused = False
            log_event(_LOG, "control_applied", "resumed", dict(self._position, command=RESUME))
        elif kind == ABORT:
            self._pending = Command(ABORT)
        elif kind == RESTART_TEST:
            self._pending = Command(RESTART_FROM, self._position["case"], 0)
        else:
            self._pending = Command(RESTART_FROM, message["case"], message.get("step", 0))


class _Handler(socketserver.StreamRequestHandler):
    """One connection: a request per line, a reply per line, until it closes."""

    server: "_Server"

    def handle(self) -> None:
        while True:
            line = self.rfile.readline(_MAX_LINE + 1)
            if not line:
                return
            if len(line) > _MAX_LINE:
                reply: Dict[str, Any] = {"ok": False, "error": "request too long"}
            else:
                try:
                    message = json.loads(line.decode("utf-8"))
                except ValueError:
                    reply = {"ok": False, "error": "a request is one JSON object per line"}
                else:
                    reply = self.server.control.request(message)
            self.wfile.write((json.dumps(reply) + "\n").encode("utf-8"))
            self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, control: RunControl) -> None:
        self.control = control
        super().__init__(address, _Handler)


class ControlServer:
    """Serve a :class:`RunControl` on 127.0.0.1.

    :param port: TCP port; 0 picks a free one, which :attr:`port` then gives.
    """

    def __init__(self, control: RunControl, port: int = 0) -> None:
        self.control = control
        self._server = _Server((HOST, int(port)), control)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="run-control", daemon=True)

    @property
    def port(self) -> int:
        """The port listened on."""
        return self._server.server_address[1]

    def start(self) -> "ControlServer":
        """Start answering requests in the background."""
        self._thread.start()
        log_event(_LOG, "control_listening", "control channel on %s:%d" % (HOST, self.port),
                  {"host": HOST, "port": self.port})
        return self

    def close(self) -> None:
        """Stop answering and release the port."""
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> "ControlServer":
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()
