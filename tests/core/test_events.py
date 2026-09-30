"""The bench event log (#82).

Traces to: CORE-FR-060, SWE4-UT-EVENTS.
"""

from __future__ import annotations

import json
import logging

import pytest

from benchtools.core.events import EventTail, source_of, start_event_log


@pytest.fixture
def event_log(tmp_path):
    path = tmp_path / "events.jsonl"
    handler = start_event_log(str(path))
    yield path
    logging.getLogger("benchtools").removeHandler(handler)
    handler.close()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("name,source", [
    ("benchtools.instruments.gpd3303d.psu", "psu"),
    ("benchtools.instruments.nordic_dongle.session", "ble"),
    ("benchtools.instruments.jlink.rtt", "jlink"),
    ("benchtools.instruments.s2lp.session", "rf"),
    ("benchtools.runner.runner", "test"),
    ("benchtools.core.transport.base", "bench"),
    ("benchtools.instruments.s2lpx", "bench"),     # a prefix, not a package
])
def test_the_logger_name_decides_the_source(name, source):
    assert source_of(name) == source


class TestTheLog:
    def test_a_record_is_one_json_line(self, event_log):
        logging.getLogger("benchtools.instruments.gpd3303d.psu").debug(">> %s", "VSET1:3.3")
        (record,) = records(event_log)
        assert record["source"] == "psu" and record["text"] == ">> VSET1:3.3"
        assert record["level"] == "DEBUG" and isinstance(record["t"], float)

    def test_records_outside_benchtools_are_not_written(self, event_log):
        logging.getLogger("somewhere.else").warning("not ours")
        assert event_log.read_text() == ""

    def test_the_console_keeps_its_level(self, tmp_path):
        """Lowering the package's level for the event log must not flood the
        console with DEBUG records."""
        root = logging.getLogger()
        console = logging.StreamHandler()
        root.addHandler(console)
        previous = root.level
        root.setLevel(logging.WARNING)
        handler = start_event_log(str(tmp_path / "e.jsonl"))
        try:
            assert console.level == logging.WARNING
        finally:
            logging.getLogger("benchtools").removeHandler(handler)
            handler.close()
            root.removeHandler(console)
            root.setLevel(previous)


class TestTail:
    def test_it_returns_only_what_is_new(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text(json.dumps({"source": "psu", "text": "a"}) + "\n")
        tail = EventTail(str(path))
        assert [r["text"] for r in tail.read()] == ["a"]
        assert tail.read() == []
        with path.open("a") as handle:
            handle.write(json.dumps({"source": "ble", "text": "b"}) + "\n")
        assert [r["text"] for r in tail.read()] == ["b"]

    def test_a_partial_line_waits_for_the_rest(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text('{"source": "psu", "te')
        tail = EventTail(str(path))
        assert tail.read() == []
        with path.open("a") as handle:
            handle.write('xt": "whole"}\n')
        assert [r["text"] for r in tail.read()] == ["whole"]

    def test_a_line_that_is_not_json_is_kept_as_text(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text("plain text\n")
        (record,) = EventTail(str(path)).read()
        assert record["source"] == "bench" and record["text"] == "plain text"

    def test_a_missing_file_is_no_records_yet(self, tmp_path):
        assert EventTail(str(tmp_path / "later.jsonl")).read() == []

    def test_rewind_reads_it_all_again(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text(json.dumps({"text": "a"}) + "\n")
        tail = EventTail(str(path))
        tail.read()
        tail.rewind()
        assert [r["text"] for r in tail.read()] == ["a"]

    def test_it_can_start_at_the_end(self, tmp_path):
        path = tmp_path / "e.jsonl"
        path.write_text(json.dumps({"text": "old"}) + "\n")
        assert EventTail(str(path), from_start=False).read() == []


class TestWhatFeedsIt:
    def test_the_supply_s_lines_are_the_supply_s(self, event_log):
        """SCPI I/O is logged under the instrument's own module (#82)."""
        from benchtools.instruments.gpd3303d import Gpd3303D

        with Gpd3303D.connect("sim://") as supply:
            supply.set_voltage(1, 3.3)
        texts = [(r["source"], r["text"]) for r in records(event_log)]
        assert ("psu", ">> VSET1:3.300") in texts or any(
            source == "psu" and text.startswith(">> VSET1") for source, text in texts)

    def test_the_runner_reports_each_test_s_result(self, tmp_path):
        from benchtools.runner.cli import main

        path = tmp_path / "events.jsonl"
        status = main(["specs/radio_link.yaml", "--simulate", "--event-log", str(path)])
        assert status == 0
        texts = [r["text"] for r in records(path) if r["source"] == "test"]
        assert any(text.startswith("running test ") for text in texts)
        assert any(text.endswith(": PASS") for text in texts)
        assert any(r["source"] == "rf" for r in records(path))
