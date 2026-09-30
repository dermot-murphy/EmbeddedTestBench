"""The ``benchtools dmm`` command line.

Traces to: DMM-FR-060, SWE4-UT-DMMCLI.
"""

from __future__ import annotations

import argparse
import json

from benchtools.cli import main as top_level_main
from benchtools.instruments.tti1604 import Tti1604
from benchtools.instruments.tti1604.cli import _cmd_read, main


def run(capsys, *argv):
    """Run the CLI and return ``(status, payload, stderr)``."""
    status = main(list(argv))
    captured = capsys.readouterr()
    text = captured.out.strip()
    payload = json.loads(text[text.index("{"):]) if "{" in text else None
    return status, payload, captured.err


SIM = ("--resource", "sim://")


class TestSubcommands:
    def test_info(self, capsys):
        status, payload, _ = run(capsys, *SIM, "info")
        assert status == 0
        assert payload["model"] == "1604"
        assert "no identification query" in payload["note"]
        assert payload["state"]["function"] == "dc_volts"

    def test_read(self, capsys):
        status, payload, _ = run(capsys, *SIM, "read")
        assert status == 0
        assert payload["function"] == "dc_volts"
        assert payload["value"] == 0.0

    def test_read_warns_when_the_reading_is_not_live(self, capsys):
        dmm = Tti1604.connect("sim://")
        dmm.transport.simulator.panel_status_bits = 0x40          # Hold
        try:
            status = _cmd_read(dmm, argparse.Namespace(stale=False, json=None))
        finally:
            dmm.close()
        payload = json.loads(capsys.readouterr().out)
        assert status == 0
        assert "held or recalled" in payload["warning"]

    def test_measuring_an_overload_is_an_error(self, capsys):
        status, _, err = run(capsys, *SIM, "measure", "ohms")
        assert status == 1                             # open circuit
        assert "OFL" in err

    def test_measure(self, capsys):
        status, payload, _ = run(capsys, *SIM, "measure", "dc_millivolts")
        assert status == 0
        assert payload["unit"] == "V"
        assert payload["range"] == "400 mV"

    def test_log(self, capsys):
        status, payload, _ = run(capsys, *SIM, "log", "-n", "4")
        assert status == 0
        assert payload["count"] == 4

    def test_function(self, capsys):
        status, payload, _ = run(capsys, *SIM, "function", "ac_volts")
        assert status == 0
        assert payload["function"] == "ac_volts"

    def test_range(self, capsys):
        status, payload, _ = run(capsys, *SIM, "range", "40")
        assert status == 0
        assert payload["range"] == "40 V"
        assert payload["auto_range"] is False

    def test_range_auto(self, capsys):
        status, payload, _ = run(capsys, *SIM, "range", "auto")
        assert status == 0
        assert payload["auto_range"] is True

    def test_a_bad_range_is_an_error(self, capsys):
        status, _, err = run(capsys, *SIM, "range", "lots")
        assert status == 1
        assert "full scale" in err

    def test_a_range_the_function_lacks_is_an_error(self, capsys):
        status, _, err = run(capsys, *SIM, "range", "30")
        assert status == 1
        assert "no 30 range" in err

    def test_the_result_is_also_written_to_a_file(self, capsys, tmp_path):
        path = tmp_path / "reading.json"
        status, _, _ = run(capsys, *SIM, "--json", str(path), "read")
        assert status == 0
        assert json.loads(path.read_text())["function"] == "dc_volts"


class TestErrors:
    def test_an_unopenable_port_is_reported(self, capsys):
        status, _, err = run(capsys, "--resource", "serial://no-such-port-here", "info")
        assert status == 1
        assert "could not connect" in err


class TestTopLevel:
    def test_reachable_from_benchtools(self, capsys):
        assert top_level_main(["dmm", "-r", "sim://", "info"]) == 0
        assert '"model": "1604"' in capsys.readouterr().out
