"""Message framing and buffering in the transport base class.

Traces to: SWE1-NFR-005, SWE4-UT-TRANSPORT.
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
