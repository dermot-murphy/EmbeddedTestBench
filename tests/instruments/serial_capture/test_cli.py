"""``benchtools serial`` against the simulator.

Traces to: SER-FR-012, SWE4-UT-SERCLI.
"""

from __future__ import annotations

import io
import time

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


def test_a_capture_that_ends_before_the_commands_still_shows_its_lines(
        capsys, monkeypatch):
    # The simulated device prints its whole script at once, so the capture
    # ends while the commands are still running, and each line is slow to
    # show, so most are still queued when the commands end.
    from benchtools.instruments.serial_capture import SerialCapture, cli

    original = SerialCapture.connect
    monkeypatch.setattr(SerialCapture, "connect", lambda *args, **kwargs: original(
        *args, simulated_interval=0.0, **kwargs))

    def slow_show(text):
        time.sleep(0.02)
        print(text, flush=True)

    monkeypatch.setattr(cli, "_show", slow_show)
    status = main(["WR LINES ON", "WR PATTERN PASS", "ROUTINE START CAPTURE",
                   "RD PORT", "RD BAUD"])
    out = capsys.readouterr().out.splitlines()
    assert status == 0
    assert [line for line in out if line.startswith("LINE ")] == [
        "LINE 1 = BOOT V1.00.0000", "LINE 2 = SELF TEST START",
        "LINE 3 = VBAT = 3.30 V", "LINE 4 = SELF TEST PASS"]


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


def test_ctrl_c_while_closing_still_closes_the_port(capsys, monkeypatch):
    from benchtools.instruments.serial_capture import SerialCapture

    made = []
    original_connect = SerialCapture.connect
    original_close = SerialCapture.close

    def connect(*args, **kwargs):
        made.append(original_connect(*args, **kwargs))
        return made[-1]

    calls = []

    def close(self):
        calls.append(1)
        if len(calls) == 1:
            raise KeyboardInterrupt
        original_close(self)

    monkeypatch.setattr(SerialCapture, "connect", connect)
    monkeypatch.setattr(SerialCapture, "close", close)
    assert main(["RD PORT"]) == 1
    capsys.readouterr()
    assert len(calls) == 2
    assert not made[0].is_open


def test_ctrl_c_while_closing_drops_the_waiting_lines_at_once(capsys, monkeypatch):
    from benchtools.instruments.serial_capture import SerialCapture, capture as capture_module
    from benchtools.instruments.serial_capture import cli

    # Without stop_live_output the second close would wait out this.
    monkeypatch.setattr(capture_module, "_JOIN_TIMEOUT", 3.0)
    original_connect = SerialCapture.connect
    original_close = SerialCapture.close
    made, calls = [], []

    def connect(*args, **kwargs):
        made.append(original_connect(*args, simulated_interval=0.0, **kwargs))
        return made[-1]

    def close(self):
        calls.append(time.monotonic())
        if len(calls) == 1:
            raise KeyboardInterrupt
        original_close(self)

    def slow_show(text):
        time.sleep(0.2)
        print(text, flush=True)

    monkeypatch.setattr(SerialCapture, "connect", connect)
    monkeypatch.setattr(SerialCapture, "close", close)
    original_run = cli._run

    def run(capture, text):
        ok = original_run(capture, text)
        if text == "RD PORT":
            time.sleep(0.3)      # the capture ends while the commands go on
        return ok

    monkeypatch.setattr(cli, "_show", slow_show)
    monkeypatch.setattr(cli, "_run", run)
    assert main(["WR LINES ON", "WR PATTERN PASS", "ROUTINE START CAPTURE", "RD PORT"]) == 1
    finished = time.monotonic()
    capsys.readouterr()
    assert len(calls) == 2
    assert finished - calls[1] < 1.0
    assert not made[0].is_open
    assert made[0].results().unshown > 0
