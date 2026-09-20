"""The command/reply session.

Two behaviours here are not in the protocol and are easy to get wrong: knowing
where a reply ends, and stopping a capture that is already running.

Traces to: S2LP-FR-001 .. S2LP-FR-004, S2LP-FR-045, SWE4-UT-S2LPSESSION.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import TransportTimeoutError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import S2lpSession


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
            responder=Scripted("boot banner\r\n{{X} a...{timer:00000001}}\r\n")
        )
        session = S2lpSession(transport, timeout=1.0)
        session.start()
        session.execute("SdkEvalGetVersion")
        assert "boot banner" in session.unclaimed
        session.close()

    def test_nested_braces_do_not_end_the_reply_early(self, session):
        transport = MockTransport(
            responder=Scripted("{{X} a...\r\n{tag: {inner}}\r\n{timer:1}\r\n}\r\n")
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
        session.stop()
        assert simulator.stopped is True
        session.close()

    def test_stopping_is_logged(self, session, tmp_path):
        path = session.log_to(str(tmp_path / "s.log"))
        session.stop()
        assert "(stop)" in open(path, encoding="utf-8").read()


class TestCollecting:
    def test_it_yields_each_reply_as_it_arrives(self, simulator):
        for index in range(3):
            simulator.queue_packet(bytes([index]))
        session = S2lpSession(MockTransport(responder=simulator), timeout=2.0)
        session.start()
        session.send("S2LPGetNBytesBatch", 0, 3)
        replies = list(session.collect(3, timeout=2.0))
        assert len(replies) == 3
        assert replies[0].numbers("bytes") == [0]
        session.close()

    def test_a_batch_cut_short_returns_what_arrived(self, simulator):
        """A capture that was cut short is a fact the caller needs, not an
        exception to handle."""
        simulator.queue_packet(b"\x01")
        session = S2lpSession(MockTransport(responder=simulator), timeout=0.3)
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
