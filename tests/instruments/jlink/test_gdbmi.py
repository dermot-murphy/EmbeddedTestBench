"""GDB/MI record parsing.

The three cases worth the most here are the ones a naive parser gets wrong: a
list of repeated results, C-string escapes, and output that is not MI at all.

Traces to: JLINK-FR-001, SWE4-UT-GDBMI.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ProtocolError
from benchtools.instruments.jlink.gdbmi import (
    AsyncRecord,
    PromptRecord,
    RecordKind,
    ResultRecord,
    StreamRecord,
    parse_line,
    parse_value,
    unescape_cstring,
)


class TestResultRecords:
    def test_bare_done(self):
        record = parse_line("^done")
        assert isinstance(record, ResultRecord)
        assert record.message == "done" and record.results == {}

    def test_token_is_returned(self):
        assert parse_line("42^done").token == 42

    def test_no_token_is_none(self):
        assert parse_line("^done").token is None

    def test_results_are_parsed(self):
        record = parse_line('^done,bkpt={number="1",addr="0x08000123",line="42"}')
        assert record.results["bkpt"]["number"] == "1"
        assert record.results["bkpt"]["addr"] == "0x08000123"

    def test_error_exposes_the_message(self):
        record = parse_line('^error,msg="No symbol \\"foo\\" in current context."')
        assert record.is_error
        assert record.error_message == 'No symbol "foo" in current context.'

    def test_running_and_connected(self):
        assert parse_line("^running").message == "running"
        assert parse_line("^connected").message == "connected"

    def test_error_flag_is_false_for_done(self):
        assert parse_line("^done").is_error is False


class TestAsyncRecords:
    def test_stopped(self):
        record = parse_line('*stopped,reason="breakpoint-hit",bkptno="2"')
        assert isinstance(record, AsyncRecord)
        assert record.kind is RecordKind.EXEC
        assert record.message == "stopped"
        assert record.results["bkptno"] == "2"

    def test_notify_and_status_kinds(self):
        assert parse_line('=thread-group-added,id="i1"').kind is RecordKind.NOTIFY
        assert parse_line('+download,section=".text"').kind is RecordKind.STATUS


class TestStreamRecords:
    @pytest.mark.parametrize(
        "line,kind",
        [
            ('~"console"', RecordKind.CONSOLE),
            ('@"target"', RecordKind.TARGET),
            ('&"log"', RecordKind.LOG),
        ],
    )
    def test_kinds(self, line, kind):
        record = parse_line(line)
        assert isinstance(record, StreamRecord) and record.kind is kind

    def test_text_is_unescaped(self):
        assert parse_line(r'~"Loading section .text\n"').text == "Loading section .text\n"

    def test_unquoted_stream_text_is_kept(self):
        """Some builds emit unquoted text; losing it would lose diagnostics."""
        assert parse_line("~not quoted").text == "not quoted"


class TestListsOfResults:
    def test_repeated_key_yields_every_entry(self):
        """The trap: a dict here keeps only the last frame, so a backtrace of
        three frames silently becomes one."""
        record = parse_line(
            '^done,stack=[frame={level="0",func="a"},frame={level="1",func="b"},'
            'frame={level="2",func="c"}]'
        )
        stack = record.results["stack"]
        assert len(stack) == 3
        assert [frame["func"] for frame in stack] == ["a", "b", "c"]

    def test_list_of_bare_values(self):
        assert parse_value('["r0","r1","r2"]') == ["r0", "r1", "r2"]

    def test_mixed_names_keep_their_keys(self):
        value = parse_value('[a={x="1"},b={x="2"}]')
        assert value == [{"a": {"x": "1"}}, {"b": {"x": "2"}}]

    def test_empty_list_and_tuple(self):
        assert parse_value("[]") == []
        assert parse_value("{}") == {}

    def test_nested_structures(self):
        value = parse_value('{a=[{b="1"},{b="2"}],c={d="3"}}')
        assert value["a"] == [{"b": "1"}, {"b": "2"}]
        assert value["c"]["d"] == "3"

    def test_repeated_top_level_name_is_kept(self):
        record = parse_line('^done,frame={level="0"},frame={level="1"}')
        assert isinstance(record.results["frame"], list)
        assert len(record.results["frame"]) == 2


class TestEscapes:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (r"a\nb", "a\nb"),
            (r"a\tb", "a\tb"),
            (r"a\rb", "a\rb"),
            (r"\\", "\\"),
            (r"\"", '"'),
            (r"\101\102", "AB"),
            (r"C:\\project\\main.c", r"C:\project\main.c"),
        ],
    )
    def test_unescape(self, raw, expected):
        assert unescape_cstring(raw) == expected

    def test_unknown_escape_is_passed_through(self):
        """GDB does the same, and it keeps Windows paths readable."""
        assert unescape_cstring(r"\q") == r"\q"

    def test_trailing_backslash_does_not_crash(self):
        assert unescape_cstring("abc\\") == "abc\\"


class TestMalformedAndNonMi:
    def test_prompt(self):
        assert isinstance(parse_line("(gdb)"), PromptRecord)

    @pytest.mark.parametrize("line", ["", "   ", "some GDB banner", "123"])
    def test_non_mi_lines_are_ignored(self, line):
        """A stray line must not abandon the session: it carries no information."""
        assert parse_line(line) is None

    def test_unterminated_string_is_rejected(self):
        with pytest.raises(ProtocolError, match="unterminated"):
            parse_value('"no closing quote')

    def test_malformed_value_is_rejected(self):
        with pytest.raises(ProtocolError, match="malformed MI value"):
            parse_value("bare")

    def test_trailing_text_is_rejected(self):
        with pytest.raises(ProtocolError, match="trailing text"):
            parse_value('"a" junk')
