"""The test run viewer's server: a browser page onto a bench run (#137).

``benchtools view`` serves one page and a small JSON API on 127.0.0.1, built
on the standard library alone. It follows a run's event log, keeps the run's
state (:class:`~benchtools.viewer.state.RunState`), and pushes every change to
the page as Server-Sent Events. Control requests from the page go to the
runner's control channel (#136); the viewer can also start a run itself.

The API:

========================  ====================================================
``GET /``                 the page
``GET /api/state``        the run's state as JSON
``GET /api/events``       Server-Sent Events: ``state`` on every change, and
                          ``record`` for every event-log record
``GET /api/instruments``  each instrument's commands and replies, and front
                          panels; ``?t0=&t1=`` for a step's window (#138)
``GET /api/radio``        received Kepler frames and each sensor's latest;
                          ``?sensor=`` for one sensor (#139)
``GET /api/ble``          BLE devices, events and the dongle's exchanges (#139)
``GET /api/graphs``       readings, BLE advertising and step markers;
                          ``?ble=&expected_ms=`` (#140)
``GET /api/status``       the status bar: run, progress, time left, instruments
``GET /api/catalogue``    test specifications and benches the viewer can start
``POST /api/control``     a control request, passed to the runner
``POST /api/start``       start a run as a subprocess and follow it
``POST /api/attach``      follow another event log, and its control port
========================  ====================================================

A request that changes anything must carry the header ``X-Benchtools: 1``. A
web page from another site cannot add that header to a request without the
browser first asking this server, which never agrees, so another site open in
the same browser cannot start or abort a run. The ``Host`` header must name
this machine, which stops a DNS-rebinding page reaching the API by name.

Traces to: VIEW-FR-001 .. VIEW-FR-024, VIEW-DD-SERVER.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import math
import os
import pathlib
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlsplit

from .. import __version__
from ..core.errors import BenchToolsError
from ..core.events import EventTail
from ..runner.control import HOST
from ..runner.spec import load_spec
from .graphs import Readings, advertising, step_markers
from .radio import BleAir, RfFrames
from .state import RunState
from .status import InstrumentStatus, progress
from .tags import Tagger
from .traffic import Traffic, panel_for

__all__ = ["Hub", "Catalogue", "Launcher", "ViewerServer", "send_control", "main"]

_LOG = logging.getLogger(__name__)

STATIC = pathlib.Path(__file__).resolve().parent / "static"

#: Header a request that changes anything must carry, and its value.
GUARD_HEADER = "X-Benchtools"

#: Most records kept for a page that connects later; the state is kept whole.
KEEP_RECORDS = 5000

#: Seconds between keep-alive comments on an idle event stream.
KEEPALIVE_S = 15.0

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


class Hub:  # pylint: disable=too-many-instance-attributes
    """Follows one event log, and holds its records and the run's state.

    A background thread reads the log every *interval* seconds. Readers wait on
    :meth:`wait` for anything newer than the sequence number they have.
    """

    def __init__(self, interval: float = 0.2) -> None:
        self.interval = interval
        self._condition = threading.Condition()
        self._tail: Optional[EventTail] = None
        self.path: Optional[str] = None
        self.state = RunState()
        self.traffic = Traffic()
        self.panels: Dict[str, Any] = {}
        self.rf = RfFrames()
        self.ble = BleAir()
        self.readings = Readings()
        self.tagger = Tagger()
        self.links = InstrumentStatus()
        self.records: List[Tuple[int, Dict[str, Any]]] = []
        self.sequence = 0
        self.generation = 0
        self._override_port: Optional[int] = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="viewer-tail", daemon=True)

    def start(self) -> "Hub":
        """Start following in the background."""
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop following."""
        self._stop.set()
        self._thread.join(2)

    def follow(self, path: Optional[str], control_port: Optional[int] = None) -> None:
        """Follow *path* from its start, forgetting the previous log."""
        with self._condition:
            self.path = path
            self._tail = EventTail(path) if path else None
            self.state = RunState()
            self.traffic = Traffic()
            self.panels = {}
            self.rf = RfFrames()
            self.ble = BleAir()
            self.readings = Readings()
            self.tagger = Tagger()
            self.links = InstrumentStatus()
            self.records = []
            self._override_port = control_port
            self.generation += 1
            self.sequence += 1
            self._condition.notify_all()

    @property
    def control_port(self) -> Optional[int]:
        """The runner's control port: as given, else as the log announced it."""
        with self._condition:
            return self._override_port or self.state.control_port

    def poll(self) -> int:
        """Read the log once; the number of records added."""
        with self._condition:
            tail = self._tail
        if tail is None:
            return 0
        added = tail.read()
        if not added:
            return 0
        with self._condition:
            if tail is not self._tail:           # followed something else meanwhile
                return 0
            for record in added:
                self.sequence += 1
                self.records.append((self.sequence, record))
                self._apply(record)
            del self.records[:-KEEP_RECORDS]
            self._condition.notify_all()
        return len(added)

    def _apply(self, record: Dict[str, Any]) -> None:
        """One record into the run's state, the traffic and the front panels."""
        self.tagger.tag(record)
        if record.get("kind") == "run_start":
            self.traffic.clear()
            self.panels = {}
        self.state.apply(record)
        self.rf.feed(record)
        self.ble.feed(record)
        self.readings.feed(record)
        self.links.feed(record)
        if self.traffic.feed(record):
            source = record["source"]
            if self.panels.get(source) is None:
                # The first lines may be the transport's; the driver's say which.
                self.panels[source] = panel_for(str(record.get("logger", "")))
            if self.panels[source] is not None:
                self.panels[source].feed(record)

    def instruments(self, t0: Optional[float] = None, t1: Optional[float] = None
                    ) -> Dict[str, Any]:
        """Each instrument's exchanges - the latest, or those in a window - and panels."""
        with self._condition:
            return {
                "sources": self.traffic.view(t0, t1),
                "panels": {source: {"kind": panel.kind, "rows": panel.rows()}
                           for source, panel in self.panels.items() if panel is not None},
            }

    def radio(self, sensor: str = "") -> Dict[str, Any]:
        """Received Kepler frames - of one sensor, or all - and the sensor table."""
        with self._condition:
            return self.rf.view(sensor)

    def bluetooth(self) -> Dict[str, Any]:
        """BLE devices and events, and every dongle's commands and replies."""
        with self._condition:
            view = self.ble.view()
            traffic = self.traffic.view()
            view["exchanges"] = {source: listed for source, listed in traffic.items()
                                 if listed["driver"] == "nordic_dongle"}
            return view

    def graphs(self, address: str = "", expected_ms: Optional[float] = None) -> Dict[str, Any]:
        """Readings charts, BLE advertising charts and step markers (#140)."""
        with self._condition:
            return {"charts": self.readings.charts(),
                    "ble": advertising(list(self.ble.adverts), address, expected_ms),
                    "markers": step_markers(self.state.snapshot())}

    def status(self, now: Optional[float] = None) -> Dict[str, Any]:
        """The status bar: the run, its progress and time left, each instrument (#149)."""
        now = time.time() if now is None else now
        with self._condition:
            state = self.state.snapshot()
            return {"run": state["status"], "paused": state["paused"], "suite": state["suite"],
                    "progress": progress(state), "instruments": self.links.view(now),
                    "now": now}

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll()
            except OSError as exc:                  # a log being replaced
                _LOG.debug("event log read failed: %s", exc)
            self._stop.wait(self.interval)

    def wait(self, since: int, timeout: float) -> int:
        """Block until the sequence passes *since*, or *timeout*; the sequence."""
        with self._condition:
            self._condition.wait_for(lambda: self.sequence > since, timeout)
            return self.sequence

    def since(self, sequence: int, generation: int) -> Dict[str, Any]:
        """What a reader that has seen up to *sequence* of *generation* has not.

        :returns: ``generation`` and ``sequence`` now, ``replaced`` if the log
            was replaced since, ``records`` after *sequence* (all of them when
            replaced), and the ``state``. All read under one lock, so a record
            is never counted as seen without being returned.
        """
        with self._condition:
            replaced = generation != self.generation
            records = [item for item in self.records if replaced or item[0] > sequence]
            snapshot = self.state.snapshot()
            snapshot.update(event_log=self.path, control_port=self._override_port
                            or self.state.control_port, tests=self.tagger.labels())
            return {"generation": self.generation, "sequence": self.sequence,
                    "replaced": replaced, "records": records, "state": snapshot}


def send_control(port: int, message: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
    """Send one request to a runner's control channel; its reply."""
    with socket.create_connection((HOST, int(port)), timeout=timeout) as connection:
        stream = connection.makefile("rwb")
        stream.write((json.dumps(message) + "\n").encode("utf-8"))
        stream.flush()
        line = stream.readline()
    if not line:
        raise OSError("the runner closed the control channel without a reply")
    return json.loads(line.decode("utf-8"))


class Catalogue:
    """The test specifications and benches the viewer offers to start a run with."""

    def __init__(self, specs: Sequence[str] = (), benches: Sequence[str] = ()) -> None:
        self.spec_dirs = [pathlib.Path(item) for item in specs]
        self.bench_dirs = [pathlib.Path(item) for item in benches]

    @staticmethod
    def _files(directories: Sequence[pathlib.Path]) -> List[pathlib.Path]:
        found: List[pathlib.Path] = []
        for directory in directories:
            if directory.is_file():
                found.append(directory)
            elif directory.is_dir():
                found.extend(sorted(path for path in directory.iterdir() if path.suffix in (
                    ".yaml", ".yml", ".json")))
        return found

    def specs(self) -> List[Dict[str, Any]]:
        """Each specification: path, name, test cases, warning, or why it would not load."""
        listed = []
        for path in self._files(self.spec_dirs):
            entry: Dict[str, Any] = {"path": str(path)}
            try:
                spec = load_spec(str(path))
            except (BenchToolsError, OSError) as exc:
                entry["error"] = str(exc)
            else:
                entry.update(name=spec.name, warning=spec.warning or "",
                             tests=[{"name": case.name, "requirement": case.requirement,
                                     "skip": case.skip} for case in spec.tests])
            listed.append(entry)
        return listed

    def benches(self) -> List[str]:
        """Each bench configuration's path."""
        return [str(path) for path in self._files(self.bench_dirs)]


class Launcher:
    """Starts ``benchtools run`` as a subprocess writing into *runs_dir*."""

    def __init__(self, catalogue: Catalogue, runs_dir: str) -> None:
        self.catalogue = catalogue
        self.runs_dir = runs_dir
        self.process: Optional[subprocess.Popen] = None

    @property
    def running(self) -> bool:
        """Whether a run started here is still in progress."""
        return self.process is not None and self.process.poll() is None

    def start(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Start the run *request* describes; the event log it writes.

        :raises ValueError: for a request that names something not offered, a
            run already in progress, or a warning not acknowledged.
        """
        if self.running:
            raise ValueError("a run started here is still in progress")
        specs = {entry["path"]: entry for entry in self.catalogue.specs()}
        spec = specs.get(request.get("spec"))
        if spec is None or "error" in spec:
            raise ValueError("choose one of the test specifications offered")
        simulate = bool(request.get("simulate"))
        bench = request.get("bench")
        if not simulate and bench not in self.catalogue.benches():
            raise ValueError("choose a bench offered, or simulate")
        tests = request.get("tests") or []
        known = {test["name"] for test in spec["tests"]}
        if not isinstance(tests, list) or not set(tests) <= known:
            raise ValueError("choose test cases from the specification")
        if spec["warning"] and not simulate and request.get("acknowledge") is not True:
            raise ValueError("this specification carries a safety warning, which must be "
                             "acknowledged before a run on hardware")
        os.makedirs(self.runs_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.join(self.runs_dir, "%s-%s" % (stamp, pathlib.Path(spec["path"]).stem))
        command = [sys.executable, "-m", "benchtools", "run", spec["path"],
                   "--event-log", base + ".events.jsonl", "--control", "0",
                   "--json", base + ".json", "--markdown", base + ".md"]
        command += ["--simulate"] if simulate else ["--bench", bench]
        for name in tests:
            command += ["--test", name]
        if spec["warning"] and not simulate:
            command.append("--acknowledge")
        with open(base + ".console.txt", "w", encoding="utf-8") as console:
            self.process = subprocess.Popen(  # pylint: disable=consider-using-with
                command, stdout=console, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL)
        _LOG.info("started %s", " ".join(command))
        return {"ok": True, "event_log": base + ".events.jsonl", "pid": self.process.pid}


#: The read-only API: path to the handler method serving it.
_GET_API = {
    "/api/state": "_get_state",
    "/api/instruments": "_get_instruments",
    "/api/radio": "_get_radio",
    "/api/ble": "_get_ble",
    "/api/graphs": "_get_graphs",
    "/api/catalogue": "_get_catalogue",
    "/api/status": "_get_status",
    "/api/events": "_get_events",
}


class _Handler(BaseHTTPRequestHandler):
    server: "ViewerServer"
    protocol_version = "HTTP/1.1"
    server_version = "benchtools-view/" + __version__

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        _LOG.debug("%s - %s", self.address_string(), format % args)

    # ------------------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(value).encode("utf-8"), "application/json")

    def _host_allowed(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in self.server.allowed_hosts

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 65536:
            raise ValueError("request too large")
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("a request body is a JSON object")
        return data

    # ------------------------------------------------------------------
    def do_GET(self) -> None:  # pylint: disable=invalid-name
        """Serve the page, its files, and the read-only API."""
        if not self._host_allowed():
            self._json({"ok": False, "error": "unexpected Host"}, HTTPStatus.FORBIDDEN)
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._static("index.html")
        elif path.startswith("/static/"):
            self._static(path[len("/static/"):])
        elif path in _GET_API:
            try:
                getattr(self, _GET_API[path])()
            except ValueError as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        else:
            self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)

    # The read-only API, one method per path (_GET_API). A ValueError is a
    # bad request, its message the reason.
    def _get_state(self) -> None:
        hub = self.server.hub
        self._json(hub.since(hub.sequence, hub.generation)["state"])

    def _get_instruments(self) -> None:
        try:
            t0, t1 = (_number(self._query(name)) for name in ("t0", "t1"))
        except ValueError as exc:
            raise ValueError("t0 and t1 are numbers") from exc
        self._json(self.server.hub.instruments(t0, t1))

    def _get_radio(self) -> None:
        self._json(self.server.hub.radio((self._query("sensor") or "").upper()))

    def _get_ble(self) -> None:
        self._json(self.server.hub.bluetooth())

    def _get_graphs(self) -> None:
        try:
            expected = _number(self._query("expected_ms"))
        except ValueError as exc:
            raise ValueError("expected_ms is a number") from exc
        self._json(self.server.hub.graphs(self._query("ble") or "", expected))

    def _get_catalogue(self) -> None:
        self._json({"specs": self.server.catalogue.specs(),
                    "benches": self.server.catalogue.benches(),
                    "running": self.server.launcher.running})

    def _get_status(self) -> None:
        self._json(self.server.hub.status())

    def _get_events(self) -> None:
        self._events()

    def _query(self, name: str) -> Optional[str]:
        values = parse_qs(urlsplit(self.path).query).get(name)
        return values[0] if values else None

    def _static(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if STATIC not in target.parents or not target.is_file():
            self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send(HTTPStatus.OK, target.read_bytes(),
                   _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

    def _events(self) -> None:
        """Stream records and state as Server-Sent Events until the page goes."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        hub = self.server.hub
        sequence, generation = 0, -1
        try:
            while not self.server.stopping.is_set():
                news = hub.since(sequence, generation)
                if news["replaced"]:
                    self._event("reset", {})
                for number, record in news["records"]:
                    self._event("record", dict(record, seq=number))
                self._event("state", news["state"])
                generation, sequence = news["generation"], news["sequence"]
                if hub.wait(sequence, KEEPALIVE_S) <= sequence:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
        except OSError:                         # the page went away
            pass

    def _event(self, name: str, data: Any) -> None:
        self.wfile.write(("event: %s\ndata: %s\n\n" % (name, json.dumps(data))).encode("utf-8"))
        self.wfile.flush()

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        """Start, attach and control: each guarded (VIEW-FR-002)."""
        if not self._host_allowed() or self.headers.get(GUARD_HEADER) != "1":
            self._json({"ok": False, "error": "refused: missing %s header or unexpected Host"
                        % GUARD_HEADER}, HTTPStatus.FORBIDDEN)
            return
        try:
            body = self._body()
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/control":
            self._control(body)
        elif path == "/api/start":
            try:
                reply = self.server.launcher.start(body)
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.server.hub.follow(reply["event_log"])
            self._json(reply)
        elif path == "/api/attach":
            log = body.get("event_log")
            port = body.get("control_port")
            if not isinstance(log, str) or not log:
                self._json({"ok": False, "error": "name an event log"}, HTTPStatus.BAD_REQUEST)
                return
            if port is not None and not isinstance(port, int):
                self._json({"ok": False, "error": "the control port is a number"},
                           HTTPStatus.BAD_REQUEST)
                return
            self.server.hub.follow(log, port)
            self._json({"ok": True, "event_log": log, "control_port": port})
        else:
            self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)

    def _control(self, body: Dict[str, Any]) -> None:
        port = self.server.hub.control_port
        if not port:
            self._json({"ok": False, "error": "this run has no control channel; start it "
                        "with --control, or attach with its port"}, HTTPStatus.CONFLICT)
            return
        try:
            reply = send_control(port, body)
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "error": "the runner did not answer: %s" % exc},
                       HTTPStatus.BAD_GATEWAY)
            return
        self._json(reply)


def _number(text: Optional[str]) -> Optional[float]:
    """*text* as a number, or ``None`` for nothing; ValueError for anything else."""
    if text is None or text == "":
        return None
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(text)
    return value


class ViewerServer(ThreadingHTTPServer):
    """The viewer's HTTP server, on 127.0.0.1 unless told otherwise."""

    daemon_threads = True

    def __init__(self, hub: Hub, catalogue: Catalogue, launcher: Launcher,
                 port: int = 0, host: str = HOST) -> None:
        self.hub = hub
        self.catalogue = catalogue
        self.launcher = launcher
        self.stopping = threading.Event()
        self.allowed_hosts = {"127.0.0.1", "localhost", "::1"}
        super().__init__((host, int(port)), _Handler)

    @property
    def port(self) -> int:
        """The port listened on."""
        return self.server_address[1]

    def server_close(self) -> None:
        self.stopping.set()
        super().server_close()


def build_parser() -> argparse.ArgumentParser:
    """The ``benchtools view`` command line."""
    parser = argparse.ArgumentParser(
        prog="benchtools view",
        description="Watch and control bench test runs in a browser.",
        epilog="Open the address it prints. It listens on 127.0.0.1 only.",
    )
    parser.add_argument("--event-log", metavar="PATH",
                        help="follow this run's event log from the start")
    parser.add_argument("--control", type=int, metavar="PORT",
                        help="the run's control port, if the event log does not say")
    parser.add_argument("--port", type=int, default=8130,
                        help="port to serve the page on (default: %(default)s; 0 picks one)")
    parser.add_argument("--specs", action="append", metavar="DIR",
                        help="where to offer test specifications from (default: specs)")
    parser.add_argument("--benches", action="append", metavar="DIR",
                        help="where to offer benches from (default: benches)")
    parser.add_argument("--runs", default="runs", metavar="DIR",
                        help="where a run started from the page writes its event log and "
                             "reports (default: %(default)s)")
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools view``."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-8s %(name)s: %(message)s")
    catalogue = Catalogue(args.specs or ["specs"], args.benches or ["benches"])
    hub = Hub().start()
    if args.event_log:
        hub.follow(args.event_log, args.control)
    try:
        server = ViewerServer(hub, catalogue, Launcher(catalogue, args.runs), args.port)
    except OSError as exc:
        print("error: cannot serve on %s:%d: %s" % (HOST, args.port, exc), file=sys.stderr)
        return 2
    print("benchtools view: http://%s:%d/  (Ctrl+C to stop)" % (HOST, server.port))
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        hub.stop()
    return 0
