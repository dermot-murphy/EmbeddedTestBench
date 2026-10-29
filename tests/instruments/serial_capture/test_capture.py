"""The serial capture driver: settings, the capture routine and its result.

Traces to: SER-FR-001, SER-FR-004, SER-FR-006, SER-FR-008, SER-FR-009,
SER-FR-011, SWE4-UT-SER.
"""

from __future__ import annotations

import logging
import socket
import threading
import time

import pytest

from benchtools.core.errors import (
    ConfigurationError,
    ConnectionFailedError,
    InstrumentError,
    TransportError,
    TransportTimeoutError,
)
from benchtools.core.transport.base import Transport
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.serial_capture import capture as capture_module
from benchtools.instruments.serial_capture import (
    ABORTED,
    COMPLETE,
    NOT_STARTED,
    RUNNING,
    CaptureBusyError,
    SerialCapture,
    SimulatedSerialDevice,
    parse_format,
)
from benchtools.instruments.serial_capture.capture import _LineState, split_lines
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


class TestSocketPort:
    """The real serial transport, reading a device that a socket stands in for.

    pyserial's ``socket://`` handler is a serial port whose far end is a TCP
    socket, so the test writes as the device would, from its own end, and the
    capture reads through its own transport alone.
    """

    @pytest.fixture
    def device(self):
        pytest.importorskip("serial")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        accepted = {}

        def accept():
            accepted["end"], _ = listener.accept()

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        yield listener.getsockname()[1], accepted, thread
        if "end" in accepted:
            accepted["end"].close()
        listener.close()

    @staticmethod
    def _connect(port, accepted, thread):
        uart = SerialCapture.connect("serial://socket://localhost:%d" % port)
        thread.join(5.0)
        return uart, accepted["end"]

    def test_lines_the_device_prints_are_captured(self, device):
        uart, end = self._connect(*device)
        with uart:
            uart.start_capture(window_ms=5000, pattern="^END$")
            end.sendall(b"first\r\nsecond")
            end.sendall(b"\r\nEND\r\n")
            result = uart.wait_capture()
        assert [line.text for line in result.lines] == ["first", "second", "END"]
        assert result.matched

    def test_what_came_before_the_capture_is_discarded(self, device):
        uart, end = self._connect(*device)
        with uart:
            end.sendall(b"OLD\r\n")
            time.sleep(0.3)
            uart.start_capture(window_ms=5000, pattern="^NEW$")
            end.sendall(b"NEW\r\n")
            result = uart.wait_capture()
        assert [line.text for line in result.lines] == ["NEW"]


class TestLineSettings:
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

    def test_settings_the_port_refuses_leave_the_old_ones(self):
        device = SimulatedSerialDevice(["BOOT"], interval=0.0)

        def make_transport(rate, _fmt):
            if rate == 9600:
                raise ConnectionFailedError("the adapter cannot do 9600")
            return MockTransport(device)

        uart = SerialCapture(make_transport)
        uart.initialise()
        with uart:
            assert uart.command("WR BAUD 9600").text == "NACK WR BAUD 9600 INVALID VALUE"
            assert uart.baudrate == 115200
            assert uart.is_open
            assert uart.capture(window_ms=5000, pattern="BOOT").matched


class TestLineEndings:
    @staticmethod
    def _split(*chunks):
        state = _LineState()
        lines = []
        for chunk in chunks:
            lines.extend(split_lines(state, chunk))
        return lines, bytes(state.pending)

    def test_cr_lf_and_crlf_each_end_a_line(self):
        assert self._split(b"A\rB\nC\r\nD") == (["A", "B", "C"], b"D")

    def test_a_crlf_split_across_chunks_is_one_ending(self):
        assert self._split(b"A\r", b"\nB\n") == (["A", "B"], b"")

    def test_two_endings_are_a_blank_line(self):
        assert self._split(b"A\n\nB\r\r") == (["A", "", "B", ""], b"")

    def test_a_byte_that_is_not_ascii_is_escaped(self):
        assert self._split(b"caf\xe9\n") == (["caf\\xe9"], b"")

    def test_a_line_with_no_ending_is_cut_at_its_limit(self, monkeypatch):
        monkeypatch.setattr(capture_module, "_MAX_LINE_BYTES", 4)
        assert self._split(b"ABCDEF") == (["ABCD"], b"EF")

    def test_the_ending_after_a_cut_line_is_its_ending(self, monkeypatch):
        monkeypatch.setattr(capture_module, "_MAX_LINE_BYTES", 4)
        assert self._split(b"ABCD\r\nEF\n") == (["ABCD", "EF"], b"")
        assert self._split(b"ABCD", b"\nEF\n") == (["ABCD", "EF"], b"")

    def test_an_lfcr_pair_is_one_ending(self):
        assert self._split(b"A\n\rB\n", b"\rC\n\r") == (["A", "B", "C"], b"")

    def test_a_device_that_ends_lines_with_cr_alone(self):
        uart = SerialCapture.connect("sim://", simulated_lines=[], simulated_interval=0.0)
        with uart:
            device = uart._transport.responder
            device.lines = ["A", "B"]
            device.ending = b"\r"
            result = uart.capture(window_ms=5000, pattern="^B$")
        assert result.status == COMPLETE
        assert [line.text for line in result.lines] == ["A", "B"]


class _DeadPort(Transport):
    """A port that fails as soon as it is read, as an unplugged adapter does."""

    def _open_link(self):
        pass

    def _close_link(self):
        pass

    def _send(self, data):
        pass

    def _recv_chunk(self, max_bytes):
        raise TransportError("the port has gone")


class _LatePort(Transport):
    """A port whose one line ends after the window has closed."""

    def _open_link(self):
        self.sent = False

    def _close_link(self):
        pass

    def _send(self, data):
        pass

    def _recv_chunk(self, max_bytes):
        if self.sent:
            raise TransportTimeoutError("nothing more")
        time.sleep(0.3)
        self.sent = True
        return b"LATE\n", True


class _RefusingPort(Transport):
    """A port that cannot be opened: the adapter refuses the line rate."""

    def _open_link(self):
        raise ConnectionFailedError("the adapter cannot do this rate")

    def _close_link(self):
        pass

    def _send(self, data):
        pass

    def _recv_chunk(self, max_bytes):
        raise TransportTimeoutError("nothing")


class _BurstPort(Transport):
    """A port that delivers a burst of lines in one read, then nothing."""

    BURST = b"".join(b"L%02d\n" % n for n in range(40))

    def _open_link(self):
        self.sent = False

    def _close_link(self):
        pass

    def _send(self, data):
        pass

    def _recv_chunk(self, max_bytes):
        if self.sent:
            time.sleep(0.01)
            raise TransportTimeoutError("nothing more")
        self.sent = True
        return self.BURST, True


class _TricklePort(Transport):
    """A port that delivers one line every 5 ms, 40 in all, then nothing."""

    def _open_link(self):
        self.sent = 0

    def _close_link(self):
        pass

    def _send(self, data):
        pass

    def _recv_chunk(self, max_bytes):
        time.sleep(0.005)
        if self.sent >= 40:
            raise TransportTimeoutError("nothing more")
        self.sent += 1
        return b"T%02d\n" % self.sent, True


class TestPortFailures:
    def test_a_dead_port_aborts_the_capture_and_says_why(self):
        uart = SerialCapture(lambda _rate, _fmt: _DeadPort())
        uart.initialise()
        with uart:
            result = uart.capture(window_ms=5000)
        assert result.status == ABORTED
        assert result.count == 0
        assert "the port has gone" in result.error

    def test_a_line_that_ends_after_the_window_is_not_in_it(self):
        uart = SerialCapture(lambda _rate, _fmt: _LatePort())
        uart.initialise()
        with uart:
            result = uart.capture(window_ms=100)
        assert result.status == COMPLETE
        assert result.count == 0

    def test_a_port_that_cannot_open_at_a_new_rate_reopens_at_the_old(self):
        device = SimulatedSerialDevice(["BOOT"], interval=0.0)

        def make_transport(rate, _fmt):
            return _RefusingPort() if rate == 9600 else MockTransport(device)

        uart = SerialCapture(make_transport)
        uart.initialise()
        with uart:
            with pytest.raises(ConnectionFailedError):
                uart.set_baudrate(9600)
            assert uart.baudrate == 115200
            assert uart.is_open
            assert isinstance(uart._transport, MockTransport)
            assert uart.capture(window_ms=5000, pattern="BOOT").matched

    def test_lines_are_timed_by_when_they_arrived_not_when_shown(self):
        uart = SerialCapture(lambda _rate, _fmt: _BurstPort())
        uart.initialise()
        shown = []
        uart.on_line = lambda text: (shown.append(text), time.sleep(0.02))
        uart.set_lines(True)
        with uart:
            # Showing the burst takes longer than the window.
            result = uart.capture(window_ms=2000, timeout=30.0)
        assert result.count == 40
        assert result.lines[-1].elapsed == result.lines[0].elapsed
        assert len(shown) == 40

    def test_a_slow_live_output_does_not_hold_up_reading(self):
        uart = SerialCapture(lambda _rate, _fmt: _TricklePort())
        uart.initialise()
        shown = []
        uart.on_line = lambda text: (shown.append(text), time.sleep(0.05))
        uart.set_lines(True)
        with uart:
            # 40 lines, each 5 ms after the last, read well inside the window;
            # showing them takes 2 s, which a reader that showed them itself
            # would spend instead of reading.
            result = uart.capture(window_ms=1500, timeout=30.0)
        assert result.count == 40
        assert len(shown) == 40
        assert result.lines[-1].elapsed < 1.5

    def test_a_failing_live_output_does_not_end_the_capture(self, uart, caplog):
        def broken(_shown):
            raise UnicodeEncodeError("cp1252", "�", 0, 1, "cannot print")

        uart.on_line = broken
        uart.set_lines(True)
        result = uart.capture(window_ms=5000, pattern="PASS")
        assert result.status == COMPLETE
        assert result.count == 4
        assert "live line output failed" in caplog.text


class TestStopping:
    def test_an_aborted_reader_is_gone_before_abort_returns(self, uart):
        uart.start_capture(window_ms=60000, pattern="NEVER")
        reader = uart._reader
        uart.abort_capture()
        assert not reader.is_alive()

    def test_the_next_capture_gets_every_line(self, uart):
        uart.start_capture(window_ms=60000, pattern="NEVER")
        first = uart.abort_capture()
        result = uart.capture(window_ms=5000, pattern="PASS")
        assert [line.text for line in result.lines] == _SCRIPT
        assert uart.results().count == 4
        assert first.status == ABORTED

    def test_a_reader_waiting_to_show_a_line_stops_when_aborted(self, uart):
        shown = []
        uart.on_line = shown.append
        uart.set_lines(True)
        with uart.output_lock:
            uart.start_capture(window_ms=60000, pattern="NEVER")
            time.sleep(0.2)
            started = time.monotonic()
            uart.abort_capture()
            assert time.monotonic() - started < 1.0
        assert not uart._reader.is_alive()
        assert len(shown) == 0

    def test_no_line_is_kept_after_the_capture_has_ended(self, uart):
        uart.capture(window_ms=5000, pattern="PASS")
        run = uart._run
        assert uart._record(run, "LATE", time.monotonic()) is False
        assert uart.results().count == 4

    def test_an_abort_drops_the_live_lines_not_yet_shown(self):
        uart = SerialCapture(lambda _rate, _fmt: _BurstPort())
        uart.initialise()
        shown = []

        def slow(text):
            shown.append(text)
            time.sleep(0.05)

        uart.on_line = slow
        uart.set_lines(True)
        with uart:
            uart.start_capture(window_ms=60000)
            time.sleep(0.2)
            uart.abort_capture()
            seen = len(shown)
            time.sleep(0.2)
        assert 0 < seen < 40
        assert len(shown) == seen

    def test_a_start_waits_for_the_last_reader_to_finish(self, uart):
        release = threading.Event()
        old = threading.Thread(target=release.wait, args=(5.0,), daemon=True)
        old.start()
        uart._reader = old
        threading.Timer(0.2, release.set).start()
        assert uart.start_capture(window_ms=5000, pattern="PASS").status == RUNNING
        assert not old.is_alive()
        uart.wait_capture()

    def test_a_reader_that_will_not_stop_refuses_the_next_start(self, uart, monkeypatch):
        monkeypatch.setattr(capture_module, "_JOIN_TIMEOUT", 0.1)
        release = threading.Event()
        stuck = threading.Thread(target=release.wait, args=(5.0,), daemon=True)
        stuck.start()
        uart._reader = stuck
        try:
            started = time.monotonic()
            with pytest.raises(CaptureBusyError, match="has not stopped"):
                uart.start_capture()
            assert time.monotonic() - started < 1.0
            assert uart.command("ROUTINE START CAPTURE").text == \
                "NACK ROUTINE START CAPTURE BUSY"
        finally:
            release.set()
            stuck.join()

    def test_start_says_running_even_if_the_capture_ends_at_once(self, uart):
        result = uart.start_capture(window_ms=5000, pattern="^BOOT$")
        uart.wait_capture()
        assert result.status == RUNNING
        assert uart.results().status == COMPLETE

    def test_the_summary_while_running_has_no_verdict(self, uart):
        uart.start_capture(window_ms=60000, pattern="NEVER")
        summary = uart.results().summary()
        uart.abort_capture()
        assert summary.startswith("Running, ")
        assert "Matched" not in summary

    def test_the_lines_kept_are_bounded_and_every_line_counted(self, uart, monkeypatch):
        monkeypatch.setattr(capture_module, "MAX_LINES", 2)
        result = uart.capture(window_ms=5000, pattern="PASS")
        assert result.count == 4
        assert [line.text for line in result.lines] == _SCRIPT[2:]
