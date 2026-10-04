"""The test run viewer's server (#137).

Traces to: VIEW-FR-001 .. VIEW-FR-009, SWE4-UT-VIEWSERVER.
"""

from __future__ import annotations

import http.client
import json
import logging
import pathlib
import threading
import time

import pytest

from benchtools.cli import main as top_level_main
from benchtools.core.events import start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.control import ControlServer, RunControl
from benchtools.runner.spec import TestSpec
from benchtools.viewer.server import (
    GUARD_HEADER, Catalogue, Hub, Launcher, ViewerServer, build_parser, send_control,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _wait(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return bool(predicate())


@pytest.fixture
def viewer(tmp_path):
    hub = Hub(interval=0.05).start()
    catalogue = Catalogue([str(ROOT / "specs")], [str(ROOT / "benches")])
    server = ViewerServer(hub, catalogue, Launcher(catalogue, str(tmp_path / "runs")))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                              daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    hub.stop()
    process = server.launcher.process
    if process is not None and process.poll() is None:
        process.kill()
        process.wait(10)


def _request(server, method, path, body=None, **options):
    """*options*: ``headers`` to add, and ``host`` for the Host header."""
    headers, host = options.get("headers"), options.get("host")
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    sent = {"Host": host or "127.0.0.1:%d" % server.port}
    if method == "POST":
        sent.update({"Content-Type": "application/json", GUARD_HEADER: "1"})
    sent.update(headers or {})
    payload = json.dumps(body).encode() if body is not None else None
    connection.request(method, path, body=payload, headers=sent)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, response.getheader("Content-Type"), data


def _json(server, method, path, body=None, **kwargs):
    status, _type, data = _request(server, method, path, body, **kwargs)
    return status, json.loads(data)


def _write_log(path, spec=None):
    handler = start_event_log(str(path))
    try:
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            runner.run(spec or TestSpec.from_mapping({"name": "logged", "tests": [
                {"name": "t", "steps": [{"do": "sleep", "with": {"seconds": 0}}]}]}))
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()


class TestPage:
    def test_the_page_and_its_files_are_served(self, viewer):
        status, kind, body = _request(viewer, "GET", "/")
        assert status == 200 and kind.startswith("text/html")
        assert b"/static/app.js" in body
        for name, expected in (("app.js", "text/javascript"), ("app.css", "text/css")):
            status, kind, _body = _request(viewer, "GET", "/static/" + name)
            assert status == 200 and kind.startswith(expected)

    def test_nothing_outside_the_static_directory_is_served(self, viewer):
        assert _request(viewer, "GET", "/static/../server.py")[0] == 404
        assert _request(viewer, "GET", "/static/%2e%2e/server.py")[0] == 404
        assert _request(viewer, "GET", "/nope")[0] == 404

    def test_the_page_loads_nothing_from_another_site(self):
        page = (ROOT / "benchtools" / "viewer" / "static" / "index.html").read_text()
        assert "http://" not in page and "https://" not in page

    def test_it_listens_on_127_0_0_1(self, viewer):
        assert viewer.server_address[0] == "127.0.0.1"


class TestGuards:
    def test_a_post_without_the_header_is_refused(self, viewer):
        status, reply = _json(viewer, "POST", "/api/attach", {"event_log": "x"},
                              headers={GUARD_HEADER: ""})
        assert status == 403 and GUARD_HEADER in reply["error"]

    def test_another_host_name_is_refused(self, viewer):
        assert _json(viewer, "GET", "/api/state", host="evil.example:80")[0] == 403
        assert _json(viewer, "POST", "/api/attach", {"event_log": "x"},
                     host="evil.example")[0] == 403

    def test_localhost_by_name_is_allowed(self, viewer):
        assert _json(viewer, "GET", "/api/state", host="localhost:%d" % viewer.port)[0] == 200

    def test_a_body_that_is_not_an_object_is_refused(self, viewer):
        status, reply = _json(viewer, "POST", "/api/attach", [1, 2])
        assert status == 400 and "JSON object" in reply["error"]


class TestFollowing:
    def test_attach_to_a_finished_log_shows_the_run(self, viewer, tmp_path):
        log = tmp_path / "events.jsonl"
        _write_log(log)
        status, reply = _json(viewer, "POST", "/api/attach", {"event_log": str(log)})
        assert status == 200 and reply["ok"]
        assert _wait(lambda: _json(viewer, "GET", "/api/state")[1]["status"] == "PASS")
        state = _json(viewer, "GET", "/api/state")[1]
        assert state["suite"] == "logged"
        assert state["event_log"] == str(log)

    def test_attach_needs_a_log_and_a_numeric_port(self, viewer):
        assert _json(viewer, "POST", "/api/attach", {})[0] == 400
        assert _json(viewer, "POST", "/api/attach", {"event_log": "x",
                                                     "control_port": "1"})[0] == 400

    def test_the_event_stream_replays_the_log_then_the_state(self, viewer, tmp_path):
        log = tmp_path / "events.jsonl"
        _write_log(log)
        viewer.hub.follow(str(log))
        assert _wait(lambda: viewer.hub.state.status == "PASS")
        connection = http.client.HTTPConnection("127.0.0.1", viewer.port, timeout=10)
        connection.request("GET", "/api/events", headers={"Host": "127.0.0.1"})
        response = connection.getresponse()
        assert response.getheader("Content-Type") == "text/event-stream"
        names, state = [], None
        while state is None:
            line = response.fp.readline().decode().strip()
            if line.startswith("event: "):
                names.append(line[7:])
            elif line.startswith("data: ") and names[-1] == "state":
                state = json.loads(line[6:])
        connection.close()
        assert names[0] == "reset"
        assert names.count("record") >= 4
        assert state["status"] == "PASS"

    def test_records_arriving_later_are_not_lost(self, tmp_path):
        log = tmp_path / "events.jsonl"
        hub = Hub()
        hub.follow(str(log))
        first = hub.since(0, -1)
        _write_log(log)
        hub.poll()
        later = hub.since(first["sequence"], first["generation"])
        assert not later["replaced"]
        assert [r["kind"] for _n, r in later["records"] if "kind" in r][0] == "run_start"


class TestInstruments:
    def test_instruments_api(self, viewer, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text("".join(json.dumps(r) + "\n" for r in (
            {"t": 1.0, "source": "PSU", "level": "DEBUG",
             "logger": "benchtools.instruments.gpd3303d.psu", "text": ">> *IDN?"},
            {"t": 1.1, "source": "PSU", "level": "DEBUG",
             "logger": "benchtools.instruments.gpd3303d.psu", "text": "<< GW INSTEK"},
            {"t": 5.0, "source": "PSU", "level": "DEBUG",
             "logger": "benchtools.instruments.gpd3303d.psu", "text": ">> OUT1"})))
        viewer.hub.follow(str(log))
        assert _wait(lambda: viewer.hub.traffic.counts.get("PSU") == 2)
        status, reply = _json(viewer, "GET", "/api/instruments")
        assert status == 200
        assert [e["text"] for e in reply["sources"]["PSU"]["entries"]] == ["*IDN?", "OUT1"]
        assert reply["panels"]["PSU"]["kind"] == "psu"
        status, reply = _json(viewer, "GET", "/api/instruments?t0=0&t1=2")
        assert [e["text"] for e in reply["sources"]["PSU"]["entries"]] == ["*IDN?"]

    @pytest.mark.parametrize("query", ["t0=x", "t1=nan", "t0=inf"])
    def test_a_window_that_is_not_numbers_is_refused(self, viewer, query):
        assert _json(viewer, "GET", "/api/instruments?" + query)[0] == 400


class TestControl:
    def test_control_without_a_channel_is_refused(self, viewer):
        status, reply = _json(viewer, "POST", "/api/control", {"cmd": "pause"})
        assert status == 409 and "no control channel" in reply["error"]

    def test_control_is_passed_to_the_runner(self, viewer, tmp_path):
        control = RunControl()
        control.begin("x", lambda case, step: None)
        with ControlServer(control) as channel:
            viewer.hub.follow(str(tmp_path / "none.jsonl"), channel.port)
            status, reply = _json(viewer, "POST", "/api/control", {"cmd": "pause"})
        assert status == 200 and reply["state"] == "paused"

    def test_a_runner_that_does_not_answer_is_reported(self, viewer, tmp_path):
        control = RunControl()
        channel = ControlServer(control)
        port = channel.port
        channel.close()
        viewer.hub.follow(str(tmp_path / "none.jsonl"), port)
        status, reply = _json(viewer, "POST", "/api/control", {"cmd": "pause"})
        assert status == 502 and "did not answer" in reply["error"]

    def test_send_control(self):
        control = RunControl()
        with ControlServer(control) as channel:
            assert send_control(channel.port, {"cmd": "status"})["state"] == "idle"


class TestCatalogue:
    def test_specifications_with_their_test_cases_and_warnings(self, viewer):
        pytest.importorskip("yaml")
        status, reply = _json(viewer, "GET", "/api/catalogue")
        assert status == 200
        by_name = {entry.get("name"): entry for entry in reply["specs"]}
        assert "Rising-edge skew across the four clock loads" in [
            test["name"] for test in by_name["Clock distribution timing"]["tests"]]
        assert by_name["Bench self-check"]["warning"]
        assert any(path.endswith("simulated.yaml") for path in reply["benches"])

    def test_a_specification_that_will_not_load_says_why(self, tmp_path):
        (tmp_path / "bad.json").write_text("{\"name\": \"x\"}")
        entry = Catalogue([str(tmp_path)]).specs()[0]
        assert entry["error"]


class TestStart:
    @pytest.fixture(autouse=True)
    def _yaml(self):
        pytest.importorskip("yaml")

    def _spec(self, name):
        return str(ROOT / "specs" / name)

    def test_a_simulated_run_started_from_the_page(self, viewer):
        status, reply = _json(viewer, "POST", "/api/start", {
            "spec": self._spec("clock_skew.yaml"), "simulate": True,
            "tests": ["Clock period within 1 percent of 1 us"]})
        assert status == 200, reply
        assert _wait(lambda: viewer.hub.state.status == "PASS", 60)
        state = _json(viewer, "GET", "/api/state")[1]
        assert state["control_port"]
        assert [c["status"] for c in state["cases"]].count("PASS") == 1
        assert pathlib.Path(reply["event_log"]).is_file()

    @pytest.mark.parametrize("body, words", [
        ({"spec": "elsewhere.yaml", "simulate": True}, "test specifications offered"),
        ({"spec": "clock_skew.yaml", "simulate": False, "bench": "/tmp/x.yaml"}, "bench offered"),
        ({"spec": "clock_skew.yaml", "simulate": True, "tests": ["nope"]}, "test cases"),
    ])
    def test_a_request_for_something_not_offered_is_refused(self, viewer, body, words):
        if body["spec"] == "clock_skew.yaml":
            body = dict(body, spec=self._spec("clock_skew.yaml"))
        status, reply = _json(viewer, "POST", "/api/start", body)
        assert status == 400 and words in reply["error"]

    def test_a_warning_must_be_acknowledged_on_hardware(self, viewer):
        bench = next(path for path in viewer.catalogue.benches() if "lab" in path
                     or "kepler" in path or "bench" in path)
        status, reply = _json(viewer, "POST", "/api/start", {
            "spec": self._spec("bench_self_check.yaml"), "simulate": False, "bench": bench})
        assert status == 400 and "safety warning" in reply["error"]


class TestCommandLine:
    def test_the_top_level_command_knows_view(self, capsys):
        assert top_level_main(["--help"]) == 0
        assert "view" in capsys.readouterr().out

    def test_options(self):
        args = build_parser().parse_args(["--event-log", "e.jsonl", "--control", "5", "--port",
                                          "0", "--specs", "a", "--specs", "b"])
        assert (args.event_log, args.control, args.port, args.specs) == (
            "e.jsonl", 5, 0, ["a", "b"])
