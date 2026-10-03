"""Notes and the report export (#156).

Traces to: VIEW-FR-040 .. VIEW-FR-042, SWE4-UT-VIEWREPORT.
"""

from __future__ import annotations

import json
import logging
import re

import pytest

from benchtools.core.events import start_event_log
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.spec import TestSpec
from benchtools.viewer.report import NotesStore, build_report, svg_chart
from benchtools.viewer.server import Hub

from . import radio_log


class TestNotes:
    def test_saved_beside_the_event_log_and_read_back(self, tmp_path):
        log = str(tmp_path / "run.events.jsonl")
        store = NotesStore(log)
        assert store.load() == {"fault": "", "findings": "", "updated": None}
        saved = store.save("PSU tripped", "Limit was 50 mA")
        assert (tmp_path / "run.events.jsonl.notes.json").is_file()
        again = NotesStore(log).load()
        assert (again["fault"], again["findings"]) == ("PSU tripped", "Limit was 50 mA")
        assert again["updated"] == saved["updated"]

    def test_nothing_to_save_beside(self):
        with pytest.raises(ValueError, match="event log"):
            NotesStore(None).save("a", "b")

    def test_notes_are_text_and_bounded(self, tmp_path):
        store = NotesStore(str(tmp_path / "e.jsonl"))
        with pytest.raises(ValueError, match="text"):
            store.save(3, "b")
        assert len(store.save("x" * 30000, "")["fault"]) == 20000

    def test_a_damaged_notes_file_reads_as_empty(self, tmp_path):
        (tmp_path / "e.jsonl.notes.json").write_text("not json")
        assert NotesStore(str(tmp_path / "e.jsonl")).load()["fault"] == ""


class TestSvgChart:
    def test_a_line_with_a_gap_and_axes(self):
        drawn = svg_chart({"title": "T", "xunit": "ms",
                           "series": [{"points": [[0, 1.0], [1, 2.0], [2, None], [3, 1.5]]}]})
        assert drawn.startswith("<svg") and drawn.endswith("</svg>")
        path = re.search(r'<path d="([^"]*)"', drawn).group(1)
        assert path.count("M") == 2              # broken at the gap
        assert "ms" in drawn

    def test_nothing_to_draw(self):
        assert svg_chart({"title": "T", "series": [{"points": [[0, None]]}]}) == ""


def _combined_log(path):
    handler = start_event_log(path)
    try:
        spec = TestSpec.from_mapping({"name": "Report run", "tests": [
            {"name": "t", "requirement": "R-9",
             "steps": [{"do": "sleep", "with": {"seconds": 0}}]}]})
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            runner.run(spec)
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    radio_log.write(path)


class TestReport:
    @pytest.fixture
    def hub(self, tmp_path):
        log = str(tmp_path / "run.events.jsonl")
        _combined_log(log)
        NotesStore(log).save("Fault <b>here</b>", "Found it")
        hub = Hub()
        hub.follow(log)
        hub.poll()
        return hub

    def test_every_section_is_there(self, hub):
        report = build_report(hub, "5C1712")
        sections = re.findall(r"<h2>([^<]*)", report)
        assert sections == ["Fault description", "Findings", "Run", "Identification",
                            "Environment", "Short interval (Z axis)", "Ticks",
                            "Time waveforms", "Configuration",
                            "Diagnostics: period statistics", "Latest data"]
        assert "Report run" in report and "R-9" in report and "PASS" in report
        assert "V11.00.0000" in report
        assert report.count("<svg") >= 2

    def test_it_is_self_contained_and_escaped(self, hub):
        report = build_report(hub, "5C1712")
        assert "<script" not in report and "http://" not in report.split("</style>", maxsplit=1)[0]
        assert "Fault &lt;b&gt;here&lt;/b&gt;" in report

    def test_without_notes_or_frames(self, tmp_path):
        log = tmp_path / "empty.jsonl"
        log.write_text("")
        hub = Hub()
        hub.follow(str(log))
        report = build_report(hub)
        assert "Fault description" not in report
        assert "No VERSION frame received." in report and "No TWF frames." in report


def test_the_api_saves_notes_and_serves_the_report(tmp_path):
    from benchtools.viewer.server import GUARD_HEADER, Catalogue, Launcher, ViewerServer
    import http.client
    import threading
    log = str(tmp_path / "run.events.jsonl")
    _combined_log(log)
    hub = Hub(interval=0.05).start()
    hub.follow(log)
    server = ViewerServer(hub, Catalogue([], []), Launcher(Catalogue([], []), str(tmp_path)))
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        connection.request("POST", "/api/notes", body=json.dumps(
            {"fault": "F", "findings": "G"}).encode(), headers={
                "Host": "127.0.0.1", GUARD_HEADER: "1", "Content-Type": "application/json"})
        assert json.loads(connection.getresponse().read())["ok"]
        connection.request("GET", "/api/notes", headers={"Host": "127.0.0.1"})
        assert json.loads(connection.getresponse().read())["fault"] == "F"
        connection.request("GET", "/api/report?download=1", headers={"Host": "127.0.0.1"})
        response = connection.getresponse()
        body = response.read()
        assert response.getheader("Content-Type").startswith("text/html")
        assert "attachment" in response.getheader("Content-Disposition")
        assert b"<h2>Fault description</h2>" in body
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        hub.stop()
