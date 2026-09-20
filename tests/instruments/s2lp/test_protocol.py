"""ST's CLI line protocol.

The firmware's replies are ASCII with braces and tags, and its arguments have
declared widths. These tests pin both halves, including the one that bit: a tag
the firmware writes in hex has no ``0x`` in front of it.

Traces to: S2LP-FR-001 .. S2LP-FR-004, SWE4-UT-S2LPPROTO.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ProtocolError
from benchtools.instruments.s2lp.constants import COMMANDS
from benchtools.instruments.s2lp.protocol import (
    format_bytes,
    format_command,
    parse_pairs,
    parse_reply,
)

READ_REPLY = [
    "{{SdkEvalSpiReadRegisters} API callback...",
    "{regs_list: 0x00,0x0A,0x01,0xA2}",
    "{timer:000004D2}",
    "}",
]

RECEIVE_REPLY = [
    "{{S2LPGetNBytes} API call...",
    "{error:00}",
    "{rssi:D4}",
    "{bytes: 0x68,0x69}",
    "{timer:0000ABCD}",
    "}",
]


class TestFormattingCommands:
    def test_a_command_with_no_arguments(self):
        assert format_command("S2LPRadioGetInfo") == "S2LPRadioGetInfo"

    def test_integer_arguments(self):
        assert format_command("SdkEvalSpiReadRegisters", 0x2E, 4) == \
            "SdkEvalSpiReadRegisters 46 4"

    def test_a_byte_string_is_written_in_braces(self):
        assert format_command("S2LPSendNBytes", b"\x08\xa1") == "S2LPSendNBytes {08 A1}"

    def test_an_empty_byte_string_is_still_an_argument(self):
        assert format_bytes(b"") == "{}"

    def test_text_is_quoted_rather_than_hexed(self):
        assert format_command("S2LPSendNBytes", "ping") == 'S2LPSendNBytes "ping"'

    def test_a_quote_inside_text_is_refused(self):
        with pytest.raises(ProtocolError, match="quote"):
            format_command("S2LPSendNBytes", 'say "hi"')

    def test_an_unknown_command_lists_what_exists(self):
        with pytest.raises(ProtocolError, match="SdkEvalSpiReadRegisters"):
            format_command("ReadRegisters", 0, 1)

    def test_the_wrong_number_of_arguments_is_caught_here(self):
        """Rather than as a terse firmware error that names no argument."""
        with pytest.raises(ProtocolError, match="takes 2 argument"):
            format_command("SdkEvalSpiReadRegisters", 0x2E)

    @pytest.mark.parametrize("value", [256, -1, 1000])
    def test_a_value_too_wide_for_its_declared_type(self, value):
        with pytest.raises(ProtocolError, match="does not fit"):
            format_command("SdkEvalSpiCommandStrobes", value)

    def test_the_widths_are_the_firmware_s_own(self):
        """u is one byte, v is two, w is four - ST's letters, not ours."""
        assert format_command("S2LPPktBasicSetPayloadLength", 65535)
        with pytest.raises(ProtocolError):
            format_command("S2LPPktBasicSetPayloadLength", 65536)
        assert format_command("S2LPRadioSetFrequencyBase", 915_000_000)

    def test_every_command_in_the_table_has_a_usable_type_string(self):
        for name, letters in COMMANDS.items():
            assert set(letters) <= set("uvwsb"), name


class TestParsingReplies:
    def test_the_command_name_comes_out(self):
        assert parse_reply(READ_REPLY).command == "SdkEvalSpiReadRegisters"

    def test_tags_come_out_by_name(self):
        reply = parse_reply(READ_REPLY)
        assert reply.has("regs_list") and reply.has("timer")

    def test_a_list_of_numbers(self):
        assert parse_reply(READ_REPLY).numbers("regs_list") == [0x00, 0x0A, 0x01, 0xA2]

    def test_a_one_line_reply_parses_the_same_way(self):
        reply = parse_reply(["{{SdkEvalSpiWriteRegisters} API call...{timer:00000001}}"])
        assert reply.command == "SdkEvalSpiWriteRegisters"
        assert reply.hex_number("timer") == 1

    def test_a_hex_tag_has_no_0x_in_front_of_it(self):
        """The firmware writes %x. Read as decimal, D4 is 4 - a plausible RSSI
        that is wrong by 104 dB, which is exactly the kind of number that gets
        into a report."""
        reply = parse_reply(RECEIVE_REPLY)
        assert reply.hex_number("rssi") == 0xD4
        assert reply.hex_number("timer") == 0xABCD
        assert reply.hex_number("error") == 0

    def test_a_hex_tag_that_is_not_hex_is_reported(self):
        reply = parse_reply(["{{X} a...", "{rssi:oops}", "}"])
        with pytest.raises(ProtocolError, match="hexadecimal"):
            reply.hex_number("rssi")

    def test_bytes_come_out_as_a_payload(self):
        assert parse_reply(RECEIVE_REPLY).numbers("bytes") == [0x68, 0x69]

    def test_an_absent_tag_says_what_was_there_instead(self):
        """Guessing would put an invented number into a report."""
        with pytest.raises(ProtocolError, match="regs_list"):
            parse_reply(RECEIVE_REPLY).text("regs_list")

    def test_an_absent_tag_with_a_default_does_not_raise(self):
        assert parse_reply(RECEIVE_REPLY).number("nothing", 7) == 7
        assert parse_reply(RECEIVE_REPLY).numbers("nothing") == []

    def test_every_line_is_kept_verbatim(self):
        """A log that omits what the tooling did not recognise cannot explain
        why it ignored it."""
        reply = parse_reply(READ_REPLY + ["something unexpected"])
        assert "something unexpected" in reply.raw
        assert len(reply.lines) == 5

    def test_a_repeated_tag_keeps_the_last_value(self):
        reply = parse_reply(["{{X} a...", "{rssi:01}", "{rssi:02}", "}"])
        assert reply.hex_number("rssi") == 2

    def test_a_reply_with_no_tags_is_still_a_reply(self):
        reply = parse_reply(["Command error"])
        assert reply.tags == {} and reply.raw == "Command error"

    def test_as_dict_carries_the_command_and_its_tags(self):
        summary = parse_reply(RECEIVE_REPLY).as_dict()
        assert summary["command"] == "S2LPGetNBytes"
        assert summary["rssi"] == "D4"


class TestNumbers:
    @pytest.mark.parametrize(
        "text,expected",
        [("0x00,0x0A", [0, 10]), ("1,2,3", [1, 2, 3]), ("", []),
         ("0x68, 0x69", [0x68, 0x69]), ("0xFF", [255])],
    )
    def test_parse_pairs(self, text, expected):
        assert parse_pairs(text) == expected
