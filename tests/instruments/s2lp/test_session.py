"""The command/reply session.

Two behaviours here are not in the protocol and are easy to get wrong: knowing
where a reply ends, and stopping a capture that is already running.

Traces to: S2LP-FR-001 .. S2LP-FR-004, S2LP-FR-045, SWE4-UT-S2LPSESSION.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ProtocolError, TransportTimeoutError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import S2lpSession
from benchtools.instruments.s2lp.session import READ_POLL, UNCLAIMED_LIMIT


class Scripted:
    """A responder that answers with whatever it was told to, once."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.received = []

    def respond(self, message):
        self.received.append(message.decode("ascii").strip())
        if not self.replies:
            return None
        return self.replies.pop(0).encode("ascii")


@pytest.fixture
def session(simulator):
    instance = S2lpSession(MockTransport(responder=simulator), timeout=1.0)
    instance.start()
    yield instance
    instance.close()


class TestFraming:
    def test_a_one_line_reply(self, session):
        reply = session.execute("SdkEvalGetVersion")
        assert reply.command == "SdkEvalGetVersion"

    def test_a_reply_spread_over_several_lines(self, session):
        """The firmware closes the brace on its own line; waiting for a fixed
        number of lines would truncate this one."""
        reply = session.execute("SdkEvalSpiReadRegisters", 0x00, 4)
        assert len(reply.numbers("regs_list")) == 8
        assert reply.has("timer")

    def test_a_reply_that_never_closes_is_a_timeout_that_says_what_arrived(self):
        transport = MockTransport(responder=Scripted("{{X} started...\r\n"))
        session = S2lpSession(transport, timeout=0.2)
        session.start()
        with pytest.raises(TransportTimeoutError, match="started"):
            session.execute("SdkEvalGetVersion")
        session.close()

    def test_output_before_the_reply_is_kept_not_swallowed(self):
        """A line nobody expected is evidence, not noise."""
        transport = MockTransport(
            responder=Scripted(
                "boot banner\r\n{{(SdkEvalGetVersion)} API call... {version:80}}\r\n")
        )
        session = S2lpSession(transport, timeout=1.0)
        session.start()
        session.execute("SdkEvalGetVersion")
        assert "boot banner" in session.unclaimed
        session.close()

    def test_a_stale_reply_from_another_command_is_skipped(self):
        """Seen on a kit: a send interrupted by a stop acknowledges after the
        stop does, ahead of whatever is sent next."""
        transport = MockTransport(responder=Scripted(
            "{{(S2LPSendNBytes)} API call...}\r\n>S2LPGetVersion\r\n"
            "{{(S2LPGetVersion)} API call...{value:03C1}}\r\n>"))
        session = S2lpSession(transport, timeout=1.0)
        session.start()
        assert session.execute("S2LPGetVersion").text("value") == "03C1"
        assert any("S2LPSendNBytes" in line for line in session.unclaimed)
        session.close()

    def test_nested_braces_do_not_end_the_reply_early(self, session):
        transport = MockTransport(
            responder=Scripted(
                "{{(SdkEvalGetVersion)} a...\r\n{tag: {inner}}\r\n{timer:1}\r\n}\r\n")
        )
        local = S2lpSession(transport, timeout=1.0)
        local.start()
        reply = local.execute("SdkEvalGetVersion")
        assert reply.has("timer")
        local.close()


class TestStopping:
    def test_the_stop_character_goes_out_without_a_terminator(self, simulator):
        """The firmware reads a character inside its loop, not a line."""
        transport = MockTransport(responder=simulator)
        session = S2lpSession(transport, timeout=1.0)
        session.start()
        session.send("S2LPGetNBytes", 4)
        session.stop()
        assert simulator.stopped is True
        session.close()

    def test_a_stop_to_an_idle_board_does_not_spoil_the_next_command(self, simulator):
        """Seen on a kit: an ``S`` with nothing running sits in the command
        buffer. The session ends that line, so the next command is clean."""
        session = S2lpSession(MockTransport(responder=simulator), timeout=1.0)
        session.start()
        assert not session.stop(wait=0.2)
        assert session.execute("S2LPGetVersion").text("value") == "03C1"
        session.close()

    def test_a_reply_that_arrived_before_the_stop_is_kept(self, routed):
        session = S2lpSession(MockTransport(responder=routed), timeout=1.0)
        session.start()
        session.send("S2LPGetNBytesBatch", 0, 3)
        routed.queue_packet(b"\x01")
        routed.queue_packet(b"\x02")
        first = session.read_reply()
        assert first.command == "S2LPGetNBytes"
        session.close()

    def test_stopping_is_logged(self, session, tmp_path):
        path = session.log_to(str(tmp_path / "s.log"))
        session.stop()
        assert "(stop)" in open(path, encoding="utf-8").read()


class TestCollecting:
    def test_it_yields_each_reply_as_it_arrives(self, routed):
        for index in range(3):
            routed.queue_packet(bytes([index]))
        session = S2lpSession(MockTransport(responder=routed), timeout=2.0)
        session.start()
        session.send("S2LPGetNBytesBatch", 0, 3)
        replies = list(session.collect(3, timeout=2.0))
        assert len(replies) == 3
        assert replies[0].numbers("bytes") == [0]
        session.close()

    def test_a_batch_cut_short_returns_what_arrived(self, routed):
        """A capture that was cut short is a fact the caller needs, not an
        exception to handle."""
        routed.queue_packet(b"\x01")
        session = S2lpSession(MockTransport(responder=routed), timeout=0.3)
        session.start()
        session.send("S2LPGetNBytesBatch", 0, 5)
        assert len(list(session.collect(5, timeout=0.3))) <= 5
        session.close()


class TestLogging:
    def test_both_directions_are_recorded(self, session, tmp_path):
        path = session.log_to(str(tmp_path / "s.log"))
        session.execute("SdkEvalGetVersion")
        text = open(path, encoding="utf-8").read()
        assert " > SdkEvalGetVersion" in text
        assert " < {" in text

    def test_a_note_is_marked_as_one(self, session, tmp_path):
        path = session.log_to(str(tmp_path / "s.log"))
        session.note("antenna disconnected on purpose")
        assert " # antenna disconnected" in open(path, encoding="utf-8").read()

    def test_lines_carry_a_host_timestamp(self, session, tmp_path):
        path = session.log_to(str(tmp_path / "s.log"))
        session.execute("SdkEvalGetVersion")
        first = open(path, encoding="utf-8").read().splitlines()[0]
        assert float(first.split()[0]) > 1_600_000_000

    def test_starting_a_second_log_closes_the_first(self, session, tmp_path):
        session.log_to(str(tmp_path / "one.log"))
        session.log_to(str(tmp_path / "two.log"))
        assert session.log_path.endswith("two.log")
        assert "session closed" in open(tmp_path / "one.log", encoding="utf-8").read()

    def test_stopping_the_log_is_idempotent(self, session, tmp_path):
        session.log_to(str(tmp_path / "s.log"))
        session.stop_log()
        session.stop_log()
        assert session.log_path is None


class TestWhatAKitActuallySends:
    """Behaviours seen on a kit on 2026-09-27 that ST's source does not show."""

    def test_an_interpreter_error_fails_at_once(self):
        """Waiting would only turn a named error into a timeout."""
        transport = MockTransport(responder=Scripted("S2LPGetVersion\r\nno such command\r\n>"))
        session = S2lpSession(transport, timeout=5.0)
        session.start()
        with pytest.raises(ProtocolError, match="rejected S2LPGetVersion: no such command"):
            session.execute("S2LPGetVersion")

    def test_an_echo_that_ran_into_the_reply_is_split_off(self):
        """SdkEvalRfboardIdentification's echo arrives cut short and without
        its line end, so the reply starts part-way along the line."""
        transport = MockTransport(responder=Scripted(
            "SdkEvalRfboardIdo{{(SdkEvalRfboardIdentification)} API call...}\r\n>"))
        session = S2lpSession(transport, timeout=1.0)
        session.start()
        reply = session.execute("SdkEvalRfboardIdentification", 0)
        assert reply.command == "SdkEvalRfboardIdentification"
        assert "SdkEvalRfboardIdo" in session.unclaimed

    def test_the_prompt_is_not_kept_as_an_unexpected_line(self, session):
        session.execute("S2LPGetVersion")
        session.execute("S2LPGetVersion")
        assert ">" not in session.unclaimed

    def test_unclaimed_lines_are_bounded(self, session):
        for _ in range(UNCLAIMED_LIMIT + 10):
            session.unclaimed.append("echo")
        assert len(session.unclaimed) == UNCLAIMED_LIMIT

    def test_the_port_timeout_is_set_once(self, simulator, monkeypatch):
        """Changing it per read reconfigures a serial port, and on Windows that
        lost bytes from the kit's replies."""
        assignments = []

        def record(transport, value):
            assignments.append(value)
            transport._timeout = float(value)

        monkeypatch.setattr(MockTransport, "timeout",
                            property(lambda transport: transport._timeout, record))
        transport = MockTransport(responder=simulator)
        assignments.clear()
        session = S2lpSession(transport, timeout=1.0)
        session.start()
        for _ in range(5):
            session.execute("S2LPGetVersion")
        assert assignments == [READ_POLL]
