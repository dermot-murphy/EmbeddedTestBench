"""The GDB/MI session layer.

Traces to: JLINK-FR-002, SWE4-UT-GDBSESSION.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import TransportTimeoutError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.jlink.session import GdbError, GdbMiSession


class ScriptedResponder:
    """Returns a canned reply per command, for exercising the session alone."""

    idn = "SCRIPT,SCRIPT,0,0"

    def __init__(self, replies):
        self.replies = dict(replies)
        self.seen = []

    def respond(self, message: bytes):
        text = message.decode()
        index = 0
        while index < len(text) and text[index].isdigit():
            index += 1
        token, command = text[:index], text[index:]
        self.seen.append(command)
        template = self.replies.get(command.strip())
        if template is None:
            return ('%s^error,msg="unscripted: %s"\n(gdb)\n' % (token, command.strip())).encode()
        return (template.replace("{t}", token) + "\n").encode()


def session_for(replies, timeout=1.0):
    responder = ScriptedResponder(replies)
    instance = GdbMiSession(MockTransport(responder=responder), timeout=timeout)
    instance.start()
    return instance, responder


class TestCommands:
    def test_result_is_returned(self, session):
        record = session.execute("-gdb-set confirm off")
        assert record.message == "done"

    def test_token_is_sent_and_matched(self, session):
        session.execute("-gdb-set confirm off")
        session.execute("-gdb-set pagination off")
        log = session.transport.responder.command_log
        assert log[-1] == "-gdb-set pagination off"

    def test_error_raises_with_gdb_message(self, session):
        with pytest.raises(GdbError, match="No symbol"):
            session.execute('-data-evaluate-expression "nope"')

    def test_error_can_be_returned_instead(self, session):
        record = session.execute('-data-evaluate-expression "nope"', allow_error=True)
        assert record.is_error and "No symbol" in record.error_message

    def test_gdb_error_names_the_command(self):
        instance, _ = session_for({})
        try:
            with pytest.raises(GdbError) as info:
                instance.execute("-something")
            assert "-something" in str(info.value)
        finally:
            instance.close()

    def test_timeout_names_the_command(self):
        instance, _ = session_for({"-slow": ""}, timeout=0.1)
        try:
            with pytest.raises(TransportTimeoutError, match=r"-slow"):
                instance.execute("-slow")
        finally:
            instance.close()


class TestConsoleCommands:
    def test_console_output_is_captured(self, session):
        result = session.execute_console("compare-sections")
        assert any("Section .text" in line for line in result.lines)
        assert "matched" in result

    def test_quotes_are_escaped(self, session):
        """An unescaped quote would truncate the command GDB receives."""
        session.execute_console('monitor say "hello"', allow_error=True)
        sent = session.transport.responder.command_log[-1]
        assert '\\"hello\\"' in sent

    def test_console_result_text_joins_lines(self, session):
        assert "\n" in session.execute_console("compare-sections").text


class TestAsyncRecords:
    def test_stopped_is_buffered_then_consumed(self, session):
        session.execute("-target-select extended-remote sim:0", allow_error=True)
        session.execute("-break-insert sensor.c:40")
        session.execute("-exec-continue")
        results = session.wait_for_stop(timeout=1.0)
        assert results["reason"] == "breakpoint-hit"

    def test_a_stopped_already_buffered_is_returned_immediately(self, session):
        """No race between the target halting and the wait being made."""
        session.execute("-target-select extended-remote sim:0", allow_error=True)
        session.execute("-break-insert sensor.c:40")
        session.execute("-exec-continue")
        session.pending_async()                   # force it into the buffer
        assert session.wait_for_stop(timeout=0.2)["reason"] == "breakpoint-hit"

    def test_async_survives_an_intervening_command(self):
        """The transport discards buffered bytes on write; async records must
        already have been drained, or a *stopped is lost."""
        instance, _ = session_for(
            {
                "-exec-continue": '{t}^running\n(gdb)\n*stopped,reason="breakpoint-hit"\n(gdb)',
                "-gdb-set x": "{t}^done\n(gdb)",
            }
        )
        try:
            instance.execute("-exec-continue")
            instance.execute("-gdb-set x")        # would discard the buffer
            assert instance.wait_for_stop(timeout=0.2)["reason"] == "breakpoint-hit"
        finally:
            instance.close()

    def test_clear_async_discards_stale_notifications(self, session):
        session.execute("-target-select extended-remote sim:0", allow_error=True)
        session.execute("-break-insert sensor.c:40")
        session.execute("-exec-continue")
        session.clear_async()
        with pytest.raises(TransportTimeoutError):
            session.wait_for_stop(timeout=0.1)

    def test_pending_async_can_be_filtered(self, session):
        session.execute("-target-select extended-remote sim:0", allow_error=True)
        session.execute("-break-insert sensor.c:40")
        session.execute("-exec-continue")
        assert session.pending_async("stopped")
        assert session.pending_async("never-happens") == []

    def test_missing_notification_times_out(self, session):
        with pytest.raises(TransportTimeoutError, match="stopped"):
            session.wait_for_stop(timeout=0.1)


class TestDiagnostics:
    def test_console_and_log_output_are_kept(self, session):
        session.execute_console("compare-sections")
        assert "Section" in session.console_output

    def test_timeout_setter_rejects_zero(self, session):
        with pytest.raises(ValueError, match="timeout"):
            session.timeout = 0.0

    def test_timeout_is_settable(self, session):
        session.timeout = 3.0
        assert session.timeout == 3.0
