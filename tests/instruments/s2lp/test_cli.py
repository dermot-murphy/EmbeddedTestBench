"""The ``benchtools s2lp`` command line.

Traces to: S2LP-FR-060, SWE4-UT-S2LPCLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.s2lp import PacketLog
from benchtools.instruments.s2lp.cli import build_parser, main


def run(capsys, *argv):
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
        assert payload["board"] == "STEVAL-FKI915V1"
        assert payload["xtal_hz"] == 50_000_000
        assert payload["radio"]["frequency_hz"]

    def test_registers_dumps_the_whole_map(self, capsys):
        status, payload, _ = run(capsys, *SIM, "registers")
        assert status == 0
        assert payload["count"] == 123
        assert len(payload["dump"]) == 123

    def test_a_fresh_radio_has_nothing_changed_from_reset(self, capsys):
        _, payload, _ = run(capsys, *SIM, "registers")
        assert payload["changed_from_reset"] == {}

    def test_one_register_by_name(self, capsys):
        status, payload, _ = run(capsys, *SIM, "registers", "PCKTCTRL3")
        assert status == 0
        assert payload["address"] == "0x2E"
        assert payload["at_reset"] is True
        assert "PCKT_FRMT" in payload["fields"]

    def test_one_register_by_address(self, capsys):
        _, payload, _ = run(capsys, *SIM, "registers", "0x2E")
        assert payload["name"] == "PCKTCTRL3"

    def test_writing_a_register_then_reading_it_back(self, capsys):
        _, payload, _ = run(capsys, *SIM, "registers", "PCKTCTRL3", "--write", "0xC0")
        assert payload["value"] == "0xC0"
        assert payload["at_reset"] is False
        assert payload["fields"]["PCKT_FRMT"] == 3

    def test_the_plain_dump_is_text_not_json(self, capsys):
        status = main(list(SIM) + ["registers", "--plain"])
        text = capsys.readouterr().out
        assert status == 0
        assert text.startswith("0x00 GPIO0_CONF")

    def test_radio_shows_the_configuration(self, capsys):
        status, payload, _ = run(capsys, *SIM, "radio")
        assert status == 0
        assert payload["modulation_name"]
        assert "rssi_dbm" in payload and "power_dbm" in payload

    def test_radio_sets_it(self, capsys):
        _, payload, _ = run(capsys, *SIM, "radio", "--frequency", "915000000",
                            "--rate", "100000", "--modulation", "2-fsk")
        assert payload["frequency_hz"] == 915_000_000
        assert payload["data_rate_bps"] == 100_000
        assert payload["modulation_name"] == "2-fsk"

    def test_a_frequency_the_board_cannot_reach_is_refused(self, capsys):
        status, _, stderr = run(capsys, *SIM, "radio", "--frequency", "868000000")
        assert status == 1
        assert "outside the" in stderr

    def test_tx(self, capsys):
        status, payload, _ = run(capsys, *SIM, "tx", "ping")
        assert status == 0
        assert payload["sent"] == 1
        assert payload["packets"][0]["hex"] == b"ping".hex()

    def test_tx_takes_hex(self, capsys):
        _, payload, _ = run(capsys, *SIM, "tx", "0x0102ff")
        assert payload["packets"][0]["hex"] == "0102ff"

    def test_tx_repeat_runs_a_batch(self, capsys):
        _, payload, _ = run(capsys, *SIM, "tx", "ping", "--repeat", "3", "--interval", "1")
        assert payload["sent"] == 3

    def test_rx_with_nothing_on_the_air_exits_one_and_explains(self, capsys):
        status, payload, _ = run(capsys, *SIM, "rx", "--length", "4", "--timeout", "1")
        assert status == 1
        assert payload["received"] == 0
        assert "not the same as the air being quiet" in payload["warning"]

    def test_capture_with_nothing_on_the_air(self, capsys):
        status, payload, _ = run(capsys, *SIM, "capture", "--count", "2",
                                 "--timeout", "1", "--length", "4")
        assert status == 1
        assert payload["count"] == 0

    def test_strobe(self, capsys):
        status, payload, _ = run(capsys, *SIM, "strobe", "flush_rx")
        assert status == 0 and payload["sent"] is True


class TestConfigFiles:
    """``s2lp config``: the register values a test requires, from a file.

    Traces to: S2LP-FR-017 .. S2LP-FR-019.
    """

    FILE = "PCKTCTRL3 0xC0\nPCKTCTRL2 0x01\nMOD2 0x27\n"

    def write(self, tmp_path, text=None):
        path = tmp_path / "config.regs"
        path.write_text(self.FILE if text is None else text)
        return str(path)

    def test_verifying_a_radio_that_does_not_match_exits_one(self, capsys, tmp_path):
        """So a build step stops rather than measuring a radio set up
        differently from the one the test specifies."""
        status, payload, _ = run(capsys, *SIM, "config", self.write(tmp_path))
        assert status == 1
        assert payload["matches"] is False
        assert payload["applied"] is False
        assert "set up differently" in payload["warning"]
        assert payload["mismatches"]["PCKTCTRL3"] == {"expected": "0xC0", "actual": "0x20"}

    def test_applying_it_then_reports_a_match(self, capsys, tmp_path):
        status, payload, _ = run(capsys, *SIM, "config", self.write(tmp_path), "--apply")
        assert status == 0
        assert payload["matches"] is True and payload["applied"] is True
        assert payload["checked"] == 3

    def test_the_settings_it_read_are_reported(self, capsys, tmp_path):
        _, payload, _ = run(capsys, *SIM, "config", self.write(tmp_path), "--apply")
        names = [setting["name"] for setting in payload["settings"]]
        assert names == ["PCKTCTRL3", "PCKTCTRL2", "MOD2"]
        assert payload["settings"][0]["fields"]["PCKT_FRMT"] == 3

    def test_a_bad_file_names_the_line(self, capsys, tmp_path):
        status, _, stderr = run(capsys, *SIM, "config",
                                self.write(tmp_path, "PCKTCTRL3 0xC0\nNOTAREG 1\n"))
        assert status == 1
        assert "line 2" in stderr

    def test_saving_captures_the_radio(self, capsys, tmp_path):
        path = str(tmp_path / "captured.regs")
        status, payload, _ = run(capsys, *SIM, "config", "--save", path)
        assert status == 0
        assert payload["saved"] == path
        assert "register" in open(path, encoding="utf-8").read()

    def test_the_shipped_example_verifies_against_a_radio_it_was_applied_to(self, capsys):
        """The file in configs/ is a working example, not decoration."""
        example = "configs/s2lp_915_38k4_basic.regs"
        assert run(capsys, *SIM, "config", example)[0] == 1
        assert run(capsys, *SIM, "config", example, "--apply")[0] == 0


class TestLogs:
    def test_both_logs_are_written(self, capsys, tmp_path):
        session = tmp_path / "s.log"
        packets = tmp_path / "p.jsonl"
        status, _, _ = run(capsys, *SIM, "--log", str(session),
                           "--packet-log", str(packets), "tx", "ping")
        assert status == 0
        assert "S2LPSendNBytes" in session.read_text()
        records = PacketLog.read(str(packets))
        assert records[0]["direction"] == "tx"
        assert records[0]["text"] == "ping"

    def test_the_json_result_can_be_written_to_a_file(self, capsys, tmp_path):
        path = tmp_path / "result.json"
        run(capsys, *SIM, "--json", str(path), "info")
        assert json.loads(path.read_text())["board"]


class TestUsage:
    def test_no_subcommand_is_a_usage_error(self):
        with pytest.raises(SystemExit) as caught:
            main(["--resource", "sim://"])
        assert caught.value.code == 2

    def test_an_unknown_strobe_is_rejected_by_the_parser(self):
        with pytest.raises(SystemExit):
            main(["--resource", "sim://", "strobe", "transmit"])

    def test_the_parser_documents_every_subcommand(self):
        text = build_parser().format_help()
        for name in ("info", "registers", "radio", "config", "tx", "rx", "capture", "strobe"):
            assert name in text


class TestDispatch:
    @pytest.mark.parametrize("name", ["s2lp", "s2-lp", "radio"])
    def test_the_top_level_command_dispatches(self, name, capsys):
        assert top_level_main([name, "--resource", "sim://", "info"]) == 0
        assert "STEVAL" in capsys.readouterr().out

    def test_the_usage_lists_the_kit(self, capsys):
        top_level_main([])
        assert "s2lp " in capsys.readouterr().out
