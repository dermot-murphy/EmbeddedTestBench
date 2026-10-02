"""Message framing and buffering in the transport base class.

Traces to: SWE1-NFR-005, CORE-FR-061, CORE-FR-062, SWE4-UT-TRANSPORT.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from benchtools.core.errors import ProtocolError, TransportError, TransportTimeoutError
from benchtools.core.transport.base import Transport


class ScriptedTransport(Transport):
    """Returns a fixed script of ``(data, end)`` chunks, for framing tests."""

    def __init__(self, chunks: List[Tuple[bytes, bool]], **kwargs) -> None:
        super().__init__(**kwargs)
        self.chunks = list(chunks)
        self.sent: List[bytes] = []

    def _open_link(self) -> None:
        pass

    def _close_link(self) -> None:
        pass

    def _send(self, data: bytes) -> None:
        self.sent.append(data)

    def _recv_chunk(self, max_bytes: int):
        if not self.chunks:
            return b"", True
        return self.chunks.pop(0)


class TestFraming:
    def test_read_message_strips_the_terminator(self):
        link = ScriptedTransport([(b"1.0E-6\n", True)]).open()
        assert link.read_message() == b"1.0E-6"

    def test_read_message_reassembles_chunks(self):
        link = ScriptedTransport([(b"TEKTRO", False), (b"NIX\n", True)]).open()
        assert link.read_message() == b"TEKTRONIX"

    def test_read_message_stops_at_the_terminator_before_end(self):
        """A second response already in the buffer is not consumed by the first read."""
        link = ScriptedTransport([(b"first\nsecond\n", True)]).open()
        assert link.read_message() == b"first"
        assert link.read_message() == b"second"

    def test_read_message_can_keep_the_terminator(self):
        link = ScriptedTransport([(b"value\n", True)]).open()
        assert link.read_message(strip_terminator=False) == b"value\n"

    def test_read_exactly_crosses_chunk_boundaries(self):
        link = ScriptedTransport([(b"ab", False), (b"cd", False), (b"ef", True)]).open()
        assert link.read_exactly(5) == b"abcde"
        assert link.read_exactly(1) == b"f"

    def test_read_exactly_allows_the_terminator_inside_binary_data(self):
        """Binary curve payloads may legitimately contain 0x0A."""
        link = ScriptedTransport([(b"\x01\n\x03\x04", True)]).open()
        assert link.read_exactly(4) == b"\x01\n\x03\x04"

    def test_read_exactly_rejects_a_short_response(self):
        link = ScriptedTransport([(b"abc", True)]).open()
        with pytest.raises(ProtocolError, match="truncated|after 3 of 10"):
            link.read_exactly(10)

    def test_read_exactly_rejects_a_negative_count(self):
        link = ScriptedTransport([]).open()
        with pytest.raises(ValueError):
            link.read_exactly(-1)

    def test_read_raw_returns_everything_including_terminators(self):
        link = ScriptedTransport([(b"\x89PNG\r\n", False), (b"\x1a\n", True)]).open()
        assert link.read_raw() == b"\x89PNG\r\n\x1a\n"


class TestWriteBehaviour:
    def test_terminator_is_appended_once(self):
        link = ScriptedTransport([]).open()
        link.write(b"*IDN?")
        link.write(b"*CLS\n")
        assert link.sent == [b"*IDN?\n", b"*CLS\n"]

    def test_write_discards_a_stale_response(self):
        """A leftover response must not be mistaken for the next answer."""
        link = ScriptedTransport([(b"stale\n", True), (b"fresh\n", True)]).open()
        link.write(b"FIRST?")
        link._fill()                      # buffer the stale response
        link.write(b"SECOND?")            # should clear it
        assert link.read_message() == b"fresh"

    def test_a_write_can_keep_a_reply_already_arriving(self):
        """The S2-LP's stop character interrupts a stream still being read;
        what already arrived is the start of a reply, not a stale one."""
        link = ScriptedTransport([(b"part", False), (b"ial\n", True)]).open()
        link.write(b"GO")
        link._fill()                      # half a line has arrived
        link.write(b"S", append_terminator=False, keep_buffer=True)
        assert link.read_message() == b"partial"

    def test_replies_can_end_differently_from_commands(self):
        """A GPD-3303D takes commands ending in LF and ends its replies in CR."""
        link = ScriptedTransport([(b"3.6V\rbit0\r", True)], read_terminator=b"\r").open()
        link.write(b"VSET1?")
        assert link.sent == [b"VSET1?\n"]
        assert link.read_message() == b"3.6V"
        assert link.read_message() == b"bit0"

    def test_the_read_terminator_defaults_to_the_write_terminator(self):
        link = ScriptedTransport([], terminator=b"\r\n")
        assert link.read_terminator == b"\r\n"
        link.read_terminator = b"\r"
        assert link.read_terminator == b"\r"

    def test_str_command_is_encoded(self):
        link = ScriptedTransport([]).open()
        link.write("*RST")
        assert link.sent == [b"*RST\n"]


class TestLifecycle:
    def test_io_before_open_is_rejected(self):
        link = ScriptedTransport([])
        with pytest.raises(TransportError, match="not open"):
            link.write(b"*IDN?")

    def test_open_and_close_are_idempotent(self):
        link = ScriptedTransport([])
        link.open()
        link.open()
        assert link.is_open
        link.close()
        link.close()
        assert not link.is_open

    def test_context_manager_closes(self):
        link = ScriptedTransport([])
        with link:
            assert link.is_open
        assert not link.is_open

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValueError):
            ScriptedTransport([], timeout=0.0)
        link = ScriptedTransport([])
        with pytest.raises(ValueError):
            link.timeout = -1.0

    def test_starved_link_times_out(self):
        """A chunk of no data and no END means the instrument stopped answering."""

        class Silent(ScriptedTransport):
            def _recv_chunk(self, max_bytes: int):
                return b"", False

        link = Silent([]).open()
        with pytest.raises(TransportTimeoutError):
            link.read_message()

    def test_default_read_stb_uses_the_query(self):
        link = ScriptedTransport([(b"16\n", True)]).open()
        assert link.read_stb() == 16

    def test_unparsable_stb_is_reported(self):
        link = ScriptedTransport([(b"oops\n", True)]).open()
        with pytest.raises(ProtocolError):
            link.read_stb()


class TestStreamReading:
    """For instruments that speak without being asked (CORE-FR-061, #115)."""

    def test_read_available_returns_what_has_arrived(self):
        link = ScriptedTransport([(b"\rab", False), (b"cd", False)])
        link.open()
        assert link.read_available() == b"\rab"
        assert link.read_available() == b"cd"

    def test_read_available_is_not_stopped_by_an_earlier_end_of_message(self):
        """A stream has no end: the next byte is always worth asking for."""
        link = ScriptedTransport([(b"one", True), (b"two", True)])
        link.open()
        assert link.read_available() == b"one"
        assert link.read_available() == b"two"

    def test_read_available_returns_buffered_bytes_first(self):
        link = ScriptedTransport([(b"x\nrest", False)])
        link.open()
        assert link.read_message() == b"x"
        assert link.read_available() == b"rest"

    def test_read_available_times_out_on_a_silent_link(self):
        link = ScriptedTransport([(b"", False)])
        link.open()
        with pytest.raises(TransportTimeoutError):
            link.read_available()

    def test_read_raw_never_returns_on_a_link_without_end_of_message(self):
        """Why read_available exists: this is the #115 failure, in miniature."""
        link = ScriptedTransport([(b"\r\x21", False), (b"", False)])
        link.open()
        with pytest.raises(TransportTimeoutError):
            link.read_raw()

    def test_discard_input_drops_unread_bytes_and_counts_them(self):
        link = ScriptedTransport([(b"a\nbcd", False), (b"new\n", False)])
        link.open()
        assert link.read_message() == b"a"
        assert link.discard_input() == 3
        assert not link.has_buffered_data
        assert link.read_message() == b"new"

    def test_a_virtual_clock_simulator_is_given_the_read_timeout(self):
        """CORE-FR-062: what is due later than the timeout is not delivered."""
        from benchtools.core.transport.mock import MockTransport

        class Clocked:
            def __init__(self):
                self.asked = []

            def respond(self, _message):
                return None

            def poll_within(self, timeout):
                self.asked.append(timeout)
                if timeout < 1.0:
                    raise TransportTimeoutError("nothing due")
                return b"tick"

        responder = Clocked()
        link = MockTransport(responder=responder, timeout=0.5)
        link.open()
        with pytest.raises(TransportTimeoutError):
            link.read_available()
        link.timeout = 2.0
        assert link.read_available() == b"tick"
        assert responder.asked == [0.5, 2.0]
        assert link.discard_input() == 0
