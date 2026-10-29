"""The command set: RD, WR and ROUTINE, in the Kepler console's form.

Traces to: SER-FR-002 .. SER-FR-005, SER-FR-007, SER-FR-013, SWE4-UT-SERCONSOLE.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.serial_capture import SerialCapture


@pytest.fixture
def uart():
    instrument = SerialCapture.connect(
        "sim://", simulated_lines=["BOOT", "VBAT = 3.30 V", "SELF TEST PASS"],
        simulated_interval=0.0)
    yield instrument
    instrument.close()


def _say(uart, text):
    return uart.command(text).text


class TestRd:
    @pytest.mark.parametrize("command, reply", [
        ("RD PORT", "ACK RD PORT = sim://"),
        ("RD BAUD", "ACK RD BAUD = 115200"),
        ("RD FORMAT", "ACK RD FORMAT = 8N1"),
        ("RD WINDOW", "ACK RD WINDOW = 5000"),
        ("RD PATTERN", "ACK RD PATTERN = OFF"),
        ("RD LINES", "ACK RD LINES = OFF"),
        ("RD COUNT", "ACK RD COUNT = 0"),
        ("RD MATCH", "NACK RD MATCH NOT FOUND"),
        ("RD VALUE", "NACK RD VALUE NOT FOUND"),
        ("RD LINE 1", "NACK RD LINE 1 NOT FOUND"),
        ("RD LINE x", "NACK RD LINE x INVALID VALUE"),
        ("RD", "NACK Invalid Command"),
        ("RD NOTHING", "NACK Invalid Command"),
        ("RD COUNT 2", "NACK Invalid Command"),
    ])
    def test_before_a_capture(self, uart, command, reply):
        assert _say(uart, command) == reply

    def test_after_a_capture(self, uart):
        _say(uart, "WR PATTERN ^VBAT = ([0-9.]+) V")
        uart.capture()
        assert _say(uart, "RD COUNT") == "ACK RD COUNT = 2"
        assert _say(uart, "RD LINE 1") == "ACK RD LINE 1 = BOOT"
        assert _say(uart, "RD MATCH") == "ACK RD MATCH = VBAT = 3.30 V"
        assert _say(uart, "RD VALUE") == "ACK RD VALUE = 3.30"

    def test_the_reply_carries_the_value(self, uart):
        reply = uart.command("RD BAUD")
        assert reply.ok and reply.value == "115200"


class TestWr:
    @pytest.mark.parametrize("command, reply", [
        ("WR BAUD 9600", "ACK WR BAUD 9600 Baud"),
        ("WR BAUD 49", "NACK WR BAUD 49 OUT OF RANGE"),
        ("WR BAUD fast", "NACK WR BAUD fast INVALID VALUE"),
        ("WR FORMAT 7E1", "ACK WR FORMAT 7E1"),
        ("WR FORMAT 9N1", "NACK WR FORMAT 9N1 INVALID VALUE"),
        ("WR WINDOW 10000", "ACK WR WINDOW 10000 ms"),
        ("WR WINDOW 0", "NACK WR WINDOW 0 OUT OF RANGE"),
        ("WR WINDOW -5", "NACK WR WINDOW -5 INVALID VALUE"),
        ("WR PATTERN ^OK", "ACK WR PATTERN ^OK"),
        ("WR PATTERN (", "NACK WR PATTERN ( INVALID VALUE"),
        ("WR LINES ON", "ACK WR LINES ON"),
        ("WR LINES OFF", "ACK WR LINES OFF"),
        ("WR LINES MAYBE", "NACK WR LINES MAYBE INVALID VALUE"),
        ("WR BAUD", "NACK Invalid Command"),
        ("WR BAUD 9600 8", "NACK Invalid Command"),
        ("WR SPEED 9", "NACK Invalid Command"),
    ])
    def test_replies(self, uart, command, reply):
        assert _say(uart, command) == reply

    def test_settings_take(self, uart):
        _say(uart, "WR BAUD 9600")
        _say(uart, "WR FORMAT 7e2")
        _say(uart, "WR WINDOW 1234")
        assert _say(uart, "RD BAUD") == "ACK RD BAUD = 9600"
        assert _say(uart, "RD FORMAT") == "ACK RD FORMAT = 7E2"
        assert _say(uart, "RD WINDOW") == "ACK RD WINDOW = 1234"

    def test_a_pattern_keeps_its_case_and_spaces(self, uart):
        assert _say(uart, "WR  PATTERN  ^Self Test  (pass|fail)") == \
            "ACK WR PATTERN ^Self Test  (pass|fail)"
        assert uart.pattern == "^Self Test  (pass|fail)"
        assert _say(uart, "WR PATTERN PASS \n") == "ACK WR PATTERN PASS "
        assert uart.pattern == "PASS "
        assert _say(uart, "  WR PATTERN ^X") == "ACK WR PATTERN ^X"
        assert uart.pattern == "^X"

    @pytest.mark.parametrize("command", ["WR PATTERN OFF ", "WR PATTERN off\t",
                                         "WR PATTERN  OFF"])
    def test_off_with_white_space_clears_the_pattern(self, uart, command):
        _say(uart, "WR PATTERN ^X")
        assert _say(uart, command) == "ACK WR PATTERN OFF"
        assert uart.pattern == ""
        _say(uart, "WR PATTERN OFF")
        assert uart.pattern == ""
        assert _say(uart, "RD PATTERN") == "ACK RD PATTERN = OFF"

    def test_only_wr_lines_switches_the_line_output(self, uart):
        assert _say(uart, "RD LINES") == "ACK RD LINES = OFF"
        uart.capture(window_ms=50)
        assert uart.lines_on is False
        _say(uart, "WR LINES ON")
        assert _say(uart, "RD LINES") == "ACK RD LINES = ON"
        uart.capture(window_ms=50)
        assert uart.lines_on is True
        _say(uart, "WR LINES OFF")
        assert uart.lines_on is False

    def test_port_settings_are_busy_during_a_capture(self, uart):
        _say(uart, "WR WINDOW 60000")
        _say(uart, "ROUTINE START CAPTURE")
        assert _say(uart, "WR BAUD 9600") == "NACK WR BAUD 9600 BUSY"
        assert _say(uart, "WR FORMAT 7E1") == "NACK WR FORMAT 7E1 BUSY"
        _say(uart, "ROUTINE ABORT CAPTURE")


class TestRoutine:
    def test_start_results_abort(self, uart):
        _say(uart, "WR WINDOW 60000")
        assert _say(uart, "ROUTINE RESULTS CAPTURE") == \
            "ACK ROUTINE RESULTS CAPTURE = Not Started"
        assert _say(uart, "ROUTINE START CAPTURE") == "ACK ROUTINE START CAPTURE = Running"
        assert _say(uart, "ROUTINE START CAPTURE") == "NACK ROUTINE START CAPTURE BUSY"
        assert _say(uart, "ROUTINE RESULTS CAPTURE").startswith(
            "ACK ROUTINE RESULTS CAPTURE = Running, ")
        assert _say(uart, "ROUTINE ABORT CAPTURE") == "ACK ROUTINE ABORT CAPTURE = Aborted"
        assert _say(uart, "ROUTINE RESULTS CAPTURE").startswith(
            "ACK ROUTINE RESULTS CAPTURE = Aborted, ")

    def test_abort_all(self, uart):
        assert _say(uart, "ROUTINE ABORT ALL") == "ACK ROUTINE ABORT ALL = Not Started"
        _say(uart, "WR WINDOW 60000")
        _say(uart, "ROUTINE START CAPTURE")
        assert _say(uart, "ROUTINE ABORT ALL") == "ACK ROUTINE ABORT ALL = Aborted"

    def test_complete_with_a_match(self, uart):
        _say(uart, "WR PATTERN PASS")
        _say(uart, "ROUTINE START CAPTURE")
        uart.wait_capture()
        assert _say(uart, "ROUTINE RESULTS CAPTURE") == \
            "ACK ROUTINE RESULTS CAPTURE = Complete, 3 lines, Matched"

    @pytest.mark.parametrize("command", [
        "ROUTINE START", "ROUTINE START FREQ", "ROUTINE STOP CAPTURE",
        "ROUTINE START CAPTURE NOW",
    ])
    def test_invalid(self, uart, command):
        assert _say(uart, command) == "NACK Invalid Command"


class TestForm:
    def test_words_are_not_case_sensitive_and_the_echo_is_as_sent(self, uart):
        assert _say(uart, "rd baud") == "ACK rd baud = 115200"
        assert _say(uart, "Wr Window 100") == "ACK Wr Window 100 ms"

    def test_spaces_are_collapsed(self, uart):
        assert _say(uart, "  RD   BAUD  ") == "ACK RD BAUD = 115200"

    @pytest.mark.parametrize("command", ["", "HELLO", "ECURESET HARD", "RDX BAUD"])
    def test_unknown_commands(self, uart, command):
        reply = uart.command(command)
        assert reply.text == "NACK Invalid Command"
        assert reply.ok is False
