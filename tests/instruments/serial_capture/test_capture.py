"""The serial capture driver: settings, the capture routine and its result.

Traces to: SER-FR-001, SER-FR-006, SER-FR-008, SER-FR-009, SER-FR-011,
SWE4-UT-SER.
"""

from __future__ import annotations

import logging

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError
from benchtools.instruments.serial_capture import (
    ABORTED,
    COMPLETE,
    NOT_STARTED,
    RUNNING,
    CaptureBusyError,
    SerialCapture,
    parse_format,
)
from benchtools.runner.bench import registered_drivers

#: A script printed all at once: no test waits on real-time pacing.
_SCRIPT = ["BOOT", "VBAT = 3.30 V", "TEMP 21.5", "SELF TEST PASS"]


@pytest.fixture
def uart():
    instrument = SerialCapture.connect("sim://", simulated_lines=_SCRIPT,
                                       simulated_interval=0.0)
    yield instrument
    instrument.close()


class TestConnect:
    def test_a_bare_port_is_a_serial_port(self):
        assert SerialCapture._normalise_resource("COM5") == "serial://COM5"
        assert SerialCapture._normalise_resource("/dev/ttyUSB0") == "serial:///dev/ttyUSB0"
        assert SerialCapture._normalise_resource("") == "sim://"
        assert SerialCapture._normalise_resource("sim://") == "sim://"

    def test_identity(self, uart):
        identity = uart.identify()
        assert identity.model == "Serial capture"
        assert identity.serial_number == "sim://"

    def test_defaults(self, uart):
        assert (uart.baudrate, uart.char_format, uart.window_ms) == (115200, "8N1", 5000)
        assert uart.pattern == ""
        assert uart.lines_on is False

    def test_a_bad_format_is_refused_at_connect(self):
        with pytest.raises(ConfigurationError):
            SerialCapture.connect("sim://", char_format="9Z1")

    def test_registered_as_a_bench_driver(self):
        assert "serial" in registered_drivers()
        assert "serial-capture" in registered_drivers()


class TestFormat:
    @pytest.mark.parametrize("text, parts", [
        ("8N1", (8, "N", 1)), ("7e2", (7, "E", 2)), (" 5O1 ", (5, "O", 1)),
    ])
    def test_valid(self, text, parts):
        assert parse_format(text) == parts

    @pytest.mark.parametrize("text", ["9N1", "8X1", "8N3", "8N", "", "8N1x"])
    def test_invalid(self, text):
        with pytest.raises(ValueError):
            parse_format(text)


class TestSettings:
    def test_window_range(self, uart):
        uart.window_ms = 1
        uart.window_ms = 3600000
        for bad in (0, 3600001):
            with pytest.raises(ValueError):
                uart.window_ms = bad

    def test_a_bad_pattern_is_refused(self, uart):
        with pytest.raises(ValueError):
            uart.pattern = "(unclosed"
        assert uart.pattern == ""

    def test_baud_range(self, uart):
        uart.set_baudrate(9600)
        assert uart.baudrate == 9600
        for bad in (49, 4000001):
            with pytest.raises(ValueError):
                uart.set_baudrate(bad)
        assert uart.baudrate == 9600

    def test_the_port_reopens_with_new_settings(self, uart):
        uart.set_format("7E1")
        assert uart.char_format == "7E1"
        assert uart.is_open

    def test_settings_cannot_change_while_capturing(self, uart):
        uart.start_capture(window_ms=1000)
        with pytest.raises(CaptureBusyError):
            uart.set_baudrate(9600)
        uart.abort_capture()


class TestCapture:
    def test_before_any_capture(self, uart):
        result = uart.results()
        assert result.status == NOT_STARTED
        assert result.summary() == "Not Started"
        assert result.count == 0

    def test_the_window_ends_it(self, uart):
        result = uart.capture(window_ms=1000)
        assert result.status == COMPLETE
        assert [line.text for line in result.lines] == _SCRIPT
        assert [line.number for line in result.lines] == [1, 2, 3, 4]
        assert result.count == 4
        assert result.matched is False
        assert result.summary() == "Complete, 4 lines"
        assert result.elapsed >= 1.0

    def test_a_match_ends_it_early_and_gives_the_value(self, uart):
        result = uart.capture(window_ms=5000, pattern=r"^VBAT = ([0-9.]+) V")
        assert result.status == COMPLETE
        assert result.count == 2
        assert result.match == "VBAT = 3.30 V"
        assert result.match_number == 2
        assert result.value == "3.30"
        assert result.summary() == "Complete, 2 lines, Matched"
        assert result.elapsed < 1.0

    def test_a_pattern_without_a_group_has_no_value(self, uart):
        result = uart.capture(window_ms=1000, pattern="PASS")
        assert result.matched and result.value is None

    def test_no_match_in_the_window(self, uart):
        result = uart.capture(window_ms=1000, pattern="FAIL")
        assert result.status == COMPLETE
        assert result.summary() == "Complete, 4 lines, Not Matched"

    def test_silence_is_a_result_not_an_error(self):
        with SerialCapture.connect("sim://", simulated_lines=[]) as quiet:
            result = quiet.capture(window_ms=50)
        assert result.status == COMPLETE
        assert result.count == 0

    def test_start_returns_at_once_and_abort_stops_it(self, uart):
        assert uart.start_capture(window_ms=60000).status == RUNNING
        assert uart.running
        with pytest.raises(CaptureBusyError):
            uart.start_capture()
        result = uart.abort_capture()
        assert result.status == ABORTED
        assert not uart.running

    def test_aborting_a_finished_capture_leaves_it(self, uart):
        uart.capture(window_ms=50)
        assert uart.abort_capture().status == COMPLETE

    def test_a_new_capture_forgets_the_last(self, uart):
        uart.capture(window_ms=1000, pattern="VBAT")
        result = uart.capture(window_ms=1000, pattern="BOOT")
        assert result.count == 1
        assert result.pattern == "BOOT"

    def test_line_by_number(self, uart):
        uart.capture(window_ms=5000, pattern="PASS")
        assert uart.line(3) == "TEMP 21.5"
        with pytest.raises(IndexError):
            uart.line(5)

    def test_wait_gives_up(self, uart):
        uart.start_capture(window_ms=60000)
        with pytest.raises(InstrumentError, match="still running"):
            uart.wait_capture(timeout=0.05)
        uart.abort_capture()

    def test_nothing_is_written_to_the_device(self, uart):
        uart.capture(window_ms=50)
        assert uart._transport.responder.received == bytearray()

    def test_as_dict(self, uart):
        payload = uart.capture(window_ms=1000, pattern="VBAT").as_dict()
        assert payload["matched"] is True
        assert payload["lines"][0]["number"] == 1
        assert payload["lines"][0]["text"] == "BOOT"


class TestLog:
    def test_every_line_is_a_line_event(self, uart, caplog):
        caplog.set_level(logging.DEBUG)
        uart.capture(window_ms=5000, pattern="PASS")
        lines = [r for r in caplog.records if getattr(r, "event_kind", "") == "line"]
        assert [r.event_data["text"] for r in lines] == _SCRIPT
        assert all(r.levelno == logging.DEBUG for r in lines)
        assert lines[0].getMessage() == "LINE 1 = BOOT"

    def test_lines_on_shows_them(self, uart):
        shown = []
        uart.on_line = shown.append
        uart.capture(window_ms=5000, pattern="PASS")
        assert not shown
        uart.set_lines(True)
        uart.capture(window_ms=5000, pattern="PASS")
        assert shown == ["LINE %d = %s" % (n, t) for n, t in enumerate(_SCRIPT, 1)]

    def test_lines_on_without_a_sink_logs_at_info(self, uart, caplog):
        caplog.set_level(logging.DEBUG)
        uart.set_lines(True)
        uart.capture(window_ms=5000, pattern="PASS")
        lines = [r for r in caplog.records if getattr(r, "event_kind", "") == "line"]
        assert lines and all(r.levelno == logging.INFO for r in lines)


class TestLoopback:
    """The real serial transport, against pyserial's loopback port."""

    def test_lines_written_to_the_port_are_captured(self):
        pytest.importorskip("serial")
        with SerialCapture.connect("serial://loop://") as uart:
            uart.start_capture(window_ms=2000, pattern="^END$")
            uart._transport.write(b"first\r\nsecond", append_terminator=False)
            uart._transport.write(b"\r\nEND\r\n", append_terminator=False)
            result = uart.wait_capture()
        assert [line.text for line in result.lines] == ["first", "second", "END"]
        assert result.matched

    def test_the_port_takes_the_line_settings(self):
        pytest.importorskip("serial")
        with SerialCapture.connect("serial://loop://", baudrate=9600,
                                   char_format="7E2") as uart:
            port = uart._transport
            assert (port.baudrate, port._bytesize, port._parity, port._stopbits) == \
                (9600, 7, "E", 2)
            uart.set_baudrate(19200)
            assert uart._transport.baudrate == 19200
            assert uart._transport is not port
