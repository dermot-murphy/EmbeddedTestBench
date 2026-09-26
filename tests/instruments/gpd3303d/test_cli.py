"""The ``benchtools psu`` command line.

Traces to: PSU-FR-060, SWE4-UT-PSUCLI.
"""

from __future__ import annotations

import argparse
import json

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.cli import main as top_level_main
from benchtools.instruments.gpd3303d import Gpd3303D, SimulatedGpd, TrackingMode
from benchtools.instruments.gpd3303d.cli import _cmd_read, build_parser, main


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
        assert payload["manufacturer"] == "GW INSTEK"
        assert payload["model"] == "GPD-3303D"
        assert payload["status"]["tracking"] == "independent"

    def test_status(self, capsys):
        status, payload, _ = run(capsys, *SIM, "status")
        assert status == 0
        assert len(payload["raw"].split()) == 8

    def test_read_covers_every_channel_by_default(self, capsys):
        status, payload, _ = run(capsys, *SIM, "read")
        assert status == 0
        assert [row["channel"] for row in payload["channels"]] == [1, 2]

    def test_read_one_channel(self, capsys):
        _status, payload, _ = run(capsys, *SIM, "read", "1")
        assert [row["channel"] for row in payload["channels"]] == [1]

    def test_set_programs_the_channel(self, capsys):
        status, payload, _ = run(capsys, *SIM, "set", "1", "-V", "3.3", "-I", "0.5")
        assert status == 0
        assert payload["voltage_setpoint"] == 3.3
        assert payload["current_limit"] == 0.5

    def test_set_does_not_switch_the_output_on(self, capsys):
        """Energising a rail is a separate decision from programming one."""
        _status, payload, _ = run(capsys, *SIM, "set", "1", "-V", "3.3", "-I", "0.5")
        assert payload["is_on"] is False

    def test_set_with_on_does(self, capsys):
        _status, payload, _ = run(capsys, *SIM, "set", "1", "-V", "3.3", "-I", "0.5", "--on")
        assert payload["is_on"] is True
        assert payload["voltage"] == pytest.approx(3.3)

    def test_a_value_the_supply_would_reject_is_refused(self, capsys):
        status, _, stderr = run(capsys, *SIM, "set", "1", "-V", "35")
        assert status == 1
        assert "reject" in stderr

    def test_off_for_one_channel_says_what_it_did_not_do(self, capsys):
        """A single channel is parked at 0 V, not disconnected, and anyone
        reading this output needs to know that before trusting it."""
        status, payload, _ = run(capsys, *SIM, "off", "1")
        assert status == 0
        assert "not a safety interlock" in payload["note"]

    def test_off_with_no_channel_opens_the_real_switch(self, capsys):
        _status, payload, _ = run(capsys, *SIM, "off")
        assert payload["output"] is False
        assert "note" not in payload

    def test_on(self, capsys):
        status, payload, _ = run(capsys, *SIM, "on")
        assert status == 0
        assert payload["output"] is True


class TestWarnings:
    def test_a_channel_in_current_limit_is_flagged(self, capsys, monkeypatch):
        """The numbers are real and describe a circuit nobody asked for."""
        import benchtools.instruments.gpd3303d.cli as module

        original = module.Gpd3303D.connect

        def loaded(*args, **kwargs):
            psu = original(*args, **kwargs)
            psu.transport.responder.set_load(1, 2.0)
            psu.configure_channel(1, volts=3.3, current_limit=0.5, output=True)
            return psu

        monkeypatch.setattr(module.Gpd3303D, "connect", loaded)
        status, payload, _ = run(capsys, *SIM, "read", "1")
        assert status == 0
        assert "current limit" in payload["warning"]

    def test_no_warning_when_every_channel_is_regulated(self, capsys):
        _, payload, _ = run(capsys, *SIM, "read")
        assert "warning" not in payload


class TestUsage:
    def test_no_subcommand_is_a_usage_error(self):
        with pytest.raises(SystemExit) as caught:
            main(["--resource", "sim://"])
        assert caught.value.code == 2

    def test_an_unknown_channel_is_rejected_by_the_parser(self):
        with pytest.raises(SystemExit):
            main(["--resource", "sim://", "read", "3"])

    def test_the_parser_documents_every_subcommand(self):
        text = build_parser().format_help()
        for name in ("info", "read", "set", "on", "off", "status"):
            assert name in text


class TestDispatch:
    @pytest.mark.parametrize("name", ["psu", "gpd3303d", "supply"])
    def test_the_top_level_command_dispatches(self, name, capsys):
        assert top_level_main([name, "--resource", "sim://", "info"]) == 0
        assert "GW INSTEK" in capsys.readouterr().out

    def test_the_usage_lists_the_supply(self, capsys):
        top_level_main([])
        assert "psu " in capsys.readouterr().out


class TestTrackingIsVisibleWhenReading:
    """`read` never refuses - reading is always allowed - but the figures for a
    slaved channel are channel 1's, and nothing in the numbers says so.

    Traces to: PSU-FR-006, PSU-FR-060.
    """

    def read(self, capsys, tracking):
        simulator = SimulatedGpd(tracking=tracking)
        psu = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        psu.initialise()
        try:
            _cmd_read(psu, argparse.Namespace(channel=None, json=True))
        finally:
            psu.close()
        text = capsys.readouterr().out
        return json.loads(text[text.index("{"):])

    def test_an_independent_supply_says_so_and_does_not_warn(self, capsys):
        payload = self.read(capsys, TrackingMode.INDEPENDENT)
        assert payload["tracking"] == "independent"
        assert "tracking_warning" not in payload

    @pytest.mark.parametrize("mode", [TrackingMode.SERIES, TrackingMode.PARALLEL])
    def test_a_tracking_supply_is_flagged(self, capsys, mode):
        payload = self.read(capsys, mode)
        assert payload["tracking"] == mode
        assert mode in payload["tracking_warning"]
        assert "follows channel 1" in payload["tracking_warning"]
