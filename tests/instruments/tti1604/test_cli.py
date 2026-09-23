"""The ``benchtools dmm`` command line.

Traces to: DMM-FR-070, SWE4-UT-DMM.
"""

from __future__ import annotations

import json

import pytest

from benchtools.instruments.tti1604.cli import main


def run(capsys, *argv):
    status = main(["-r", "sim://"] + list(argv))
    out = capsys.readouterr()
    return status, out


class TestRead:
    def test_a_reading_is_printed_as_json(self, capsys):
        status, out = run(capsys, "read")
        payload = json.loads(out.out)
        assert status == 0
        assert payload["unit"] == "V"
        assert payload["value"] == pytest.approx(1.0)
        assert payload["held"] is False

    def test_several_readings_come_back_as_a_list(self, capsys):
        status, out = run(capsys, "read", "-n", "3")
        assert status == 0
        assert len(json.loads(out.out)) == 3

    def test_the_display_text_is_reported_beside_the_value(self, capsys):
        # The display is the evidence for the number; a report that keeps only
        # the number cannot be checked afterwards.
        _status, out = run(capsys, "read")
        assert json.loads(out.out)["display"] == "1.0000"


class TestKeys:
    def test_keys_are_listed(self, capsys):
        status, out = run(capsys, "keys")
        assert status == 0
        assert json.loads(out.out)["keys"]["volts"] == "f"

    def test_keys_can_be_pressed_by_name(self, capsys):
        status, out = run(capsys, "press", "ohms", "ac")
        assert status == 0
        assert json.loads(out.out)["pressed"] == ["ohms", "ac"]

    def test_an_unknown_key_fails_without_a_traceback(self, capsys):
        status, out = run(capsys, "press", "gigawatts")
        assert status == 1
        assert "gigawatts" in out.err


class TestInfo:
    def test_info_says_the_identity_is_the_driver_s_own(self, capsys):
        status, out = run(capsys, "info")
        payload = json.loads(out.out)
        assert status == 0
        assert payload["model"] == "1604"
        assert "no identification query" in payload["note"]

    def test_info_reports_whether_the_meter_is_in_remote_mode(self, capsys):
        # Local mode is one of the two states in which a healthy meter is
        # silent, so it is worth being able to see it without a reading.
        _status, out = run(capsys, "info")
        assert json.loads(out.out)["remote"] is True
