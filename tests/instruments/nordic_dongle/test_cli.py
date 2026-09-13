"""The ``benchtools ble`` command line.

Traces to: BLE-FR-070, SWE4-UT-BLECLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.nordic_dongle.cli import build_parser, main


def run(capsys, *argv):
    """Run the CLI and return ``(status, payload, stderr)``."""
    status = main(list(argv))
    captured = capsys.readouterr()
    payload = None
    text = captured.out.strip()
    # ``monitor`` prints event lines before its JSON summary, so the payload is
    # whatever follows the first brace rather than the whole of stdout.
    if "{" in text:
        payload = json.loads(text[text.index("{"):])
    return status, payload, captured.err


SIM = ("--resource", "sim://")


class TestSubcommands:
    def test_info(self, capsys):
        status, payload, _ = run(capsys, *SIM, "info")
        assert status == 0
        assert payload["manufacturer"] == "Nordic"
        assert payload["protocol"] == "1.0"

    def test_scan(self, capsys):
        status, payload, _ = run(capsys, *SIM, "scan", "--duration", "1")
        assert status == 0
        assert payload["count"] == 3
        assert payload["sensors"][0]["name"] == "SENS-01"

    def test_scan_with_a_filter(self, capsys):
        _, payload, _ = run(capsys, *SIM, "scan", "--duration", "1", "--name", "SENS-02")
        assert payload["count"] == 1

    def test_select(self, capsys):
        status, payload, _ = run(capsys, *SIM, "select", "SENS-01", "--scan-seconds", "1")
        assert status == 0
        assert payload["address"] == "E4:1C:7B:02:9A:11"

    def test_profile(self, capsys):
        status, payload, _ = run(
            capsys, *SIM, "profile", "--select", "SENS-01",
            "--duration", "2", "--interval", "0.1", "--scan-seconds", "1",
        )
        assert status == 0
        assert payload["count"] >= 19
        assert payload["mean_interval_ms"] == pytest.approx(105.0, abs=0.5)
        assert payload["missed_events"] == 0
        assert payload["is_complete"] is True
        assert "warning" not in payload

    def test_profile_can_include_every_event(self, capsys):
        _, payload, _ = run(
            capsys, *SIM, "profile", "--select", "SENS-01",
            "--duration", "1", "--interval", "0.1", "--scan-seconds", "1", "--events",
        )
        assert len(payload["events"]) == payload["count"]
        assert payload["events"][0]["address"] == "E4:1C:7B:02:9A:11"

    def test_cmd_reports_the_reply_and_the_timing(self, capsys):
        status, payload, _ = run(
            capsys, *SIM, "cmd", "measure", "--select", "SENS-01",
            "--repeat", "3", "--scan-seconds", "1",
        )
        assert status == 0
        assert payload["count"] == 3
        assert payload["milliseconds"] == pytest.approx(95.0)
        assert payload["responses"] == ["OK 1024"] * 3
        assert "warning" not in payload

    def test_cmd_warns_when_the_figure_is_not_resolvable(self, capsys):
        """12.5 ms on a 30 ms link is the link's floor, not the sensor's."""
        _, payload, _ = run(
            capsys, *SIM, "cmd", "version", "--select", "SENS-01", "--scan-seconds", "1"
        )
        assert payload["trustworthy"] is False
        assert "connection interval" in payload["warning"]

    def test_monitor_streams_events(self, capsys):
        status, payload, _ = run(
            capsys, *SIM, "monitor", "--duration", "1", "--addr", "E4:1C:7B:02:9A:11"
        )
        assert status == 0
        assert payload["events"] >= 1

    def test_the_session_can_be_logged(self, capsys, tmp_path):
        path = tmp_path / "ble.log"
        run(capsys, *SIM, "--log", str(path), "scan", "--duration", "1")
        text = path.read_text()
        assert "> scan start" in text
        assert "session opened" in text

    def test_json_can_be_written_to_a_file(self, capsys, tmp_path):
        path = tmp_path / "result.json"
        run(capsys, *SIM, "--json", str(path), "info")
        assert json.loads(path.read_text())["model"] == "PCA10059"


class TestFailures:
    def test_an_unreachable_dongle_is_reported(self, capsys):
        status, _, stderr = run(capsys, "--resource", "serial://nonexistent-port-xyz", "info")
        assert status == 1
        assert "could not connect" in stderr

    def test_an_unknown_sensor_is_reported(self, capsys):
        status, _, stderr = run(capsys, *SIM, "select", "NOT-A-SENSOR", "--scan-seconds", "1")
        assert status == 1
        assert stderr.startswith("error:")

    def test_an_unknown_subcommand_is_a_usage_error(self):
        with pytest.raises(SystemExit) as caught:
            main(["--resource", "sim://", "fly"])
        assert caught.value.code == 2

    def test_no_subcommand_is_a_usage_error(self):
        with pytest.raises(SystemExit) as caught:
            main(["--resource", "sim://"])
        assert caught.value.code == 2


class TestDispatch:
    @pytest.mark.parametrize("name", ["ble", "dongle", "nordic"])
    def test_the_top_level_command_dispatches(self, name, capsys):
        assert top_level_main([name, "--resource", "sim://", "info"]) == 0
        assert "Nordic" in capsys.readouterr().out

    def test_the_usage_lists_the_dongle(self, capsys):
        top_level_main([])
        assert "ble " in capsys.readouterr().out

    def test_the_parser_documents_every_subcommand(self):
        text = build_parser().format_help()
        for name in ("info", "scan", "select", "profile", "cmd", "monitor"):
            assert name in text
