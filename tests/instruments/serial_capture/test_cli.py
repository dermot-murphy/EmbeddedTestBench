"""``benchtools serial`` against the simulator.

Traces to: SER-FR-012, SWE4-UT-SERCLI.
"""

from __future__ import annotations

import io

from benchtools.cli import main as top_level_main
from benchtools.instruments.serial_capture.cli import main


def test_commands_in_order(capsys):
    status = main(["RD BAUD", "WR WINDOW 300", "RD WINDOW"])
    out = capsys.readouterr().out.splitlines()
    assert status == 0
    assert out == ["ACK RD BAUD = 115200", "ACK WR WINDOW 300 ms", "ACK RD WINDOW = 300"]


def test_a_running_capture_is_waited_for_and_shown(capsys):
    status = main(["WR WINDOW 2000", "WR PATTERN PASS", "WR LINES ON",
                   "ROUTINE START CAPTURE"])
    out = capsys.readouterr().out.splitlines()
    assert status == 0
    assert out[3] == "ACK ROUTINE START CAPTURE = Running"
    assert out[4:8] == ["LINE 1 = BOOT V1.00.0000", "LINE 2 = SELF TEST START",
                        "LINE 3 = VBAT = 3.30 V", "LINE 4 = SELF TEST PASS"]
    assert out[-1] == "ACK ROUTINE RESULTS CAPTURE = Complete, 4 lines, Matched"


def test_lines_are_not_shown_unless_switched_on(capsys):
    main(["WR WINDOW 5000", "WR PATTERN PASS", "ROUTINE START CAPTURE"])
    out = capsys.readouterr().out
    assert "LINE " not in out
    assert "Complete, 4 lines, Matched" in out


def test_a_nack_fails(capsys):
    assert main(["WR BAUD 1"]) == 1
    assert capsys.readouterr().out.strip() == "NACK WR BAUD 1 OUT OF RANGE"


def test_a_nack_fails_even_when_later_commands_succeed(capsys):
    assert main(["WR BAUD 1", "RD BAUD"]) == 1
    assert capsys.readouterr().out.splitlines() == ["NACK WR BAUD 1 OUT OF RANGE",
                                                    "ACK RD BAUD = 115200"]


def test_commands_from_standard_input(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("RD FORMAT\n\nRD LINES\n"))
    assert main([]) == 0
    assert capsys.readouterr().out.splitlines() == ["ACK RD FORMAT = 8N1",
                                                    "ACK RD LINES = OFF"]


def test_a_bad_format_does_not_connect(capsys):
    assert main(["--format", "8Q1", "RD BAUD"]) == 1
    assert "could not connect" in capsys.readouterr().err


def test_reached_from_the_top_level(capsys):
    assert top_level_main(["serial", "RD PORT"]) == 0
    assert capsys.readouterr().out.strip() == "ACK RD PORT = sim://"
