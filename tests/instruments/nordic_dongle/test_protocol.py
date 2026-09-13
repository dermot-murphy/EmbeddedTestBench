"""The dongle's line protocol.

Traces to: BLE-FR-001, SWE4-UT-BLEPROTO.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.nordic_dongle.constants import AddressType, DongleError
from benchtools.instruments.nordic_dongle.protocol import (
    DongleProtocolError,
    Event,
    Reply,
    address_type_of,
    encode_payload,
    format_address,
    from_hex,
    normalise_address,
    parse_fields,
    parse_line,
    to_hex,
)


class TestReplies:
    def test_bare_ok(self):
        reply = parse_line("ok")
        assert isinstance(reply, Reply) and reply.ok and reply.fields == {}

    def test_ok_with_fields(self):
        reply = parse_line("ok scanning=1 ms=3000")
        assert reply.ok
        assert reply.fields == {"scanning": "1", "ms": "3000"}

    def test_error_carries_code_and_text(self):
        reply = parse_line("err 6 not connected")
        assert reply.ok is False
        assert reply.error is DongleError.NOT_CONNECTED
        assert reply.text == "not connected"

    def test_an_unknown_error_code_does_not_crash_the_driver(self):
        """Newer firmware may invent a code this driver has not met."""
        assert parse_line("err 99 something new").error is DongleError.UNKNOWN

    def test_error_without_text(self):
        assert parse_line("err 2").error is DongleError.ARGS

    def test_the_raw_line_is_kept(self):
        assert parse_line("ok t=5").raw == "ok t=5"


class TestEvents:
    def test_an_advertising_event(self):
        event = parse_line("+adv t=1234567 addr=E4:1C:7B:02:9A:11 rssi=-62 ch=37 data=020106")
        assert isinstance(event, Event)
        assert event.name == "adv"
        assert event.timestamp_us == 1234567
        assert event.get("addr") == "E4:1C:7B:02:9A:11"
        assert event.integer("rssi") == -62

    def test_an_empty_value_is_kept(self):
        """A sensor that advertises no name sends name= and that is a fact."""
        event = parse_line("+sensor t=1 idx=0 name= rssi=-90")
        assert event.get("name") == ""
        assert "name" in event.fields

    def test_a_hex_value_is_not_mangled(self):
        event = parse_line("+disc t=9 reason=0x16")
        assert event.integer("reason") == 0x16

    def test_a_missing_integer_falls_back(self):
        assert parse_line("+scan t=1 state=started").integer("count", 7) == 7

    def test_an_unparsable_integer_falls_back(self):
        assert parse_line("+adv t=1 rssi=strong").integer("rssi", -1) == -1

    def test_a_missing_timestamp_is_none(self):
        assert parse_line("+scan state=started").timestamp_us is None

    def test_a_malformed_timestamp_is_none(self):
        assert parse_line("+scan t=soon").timestamp_us is None


class TestNonProtocolLines:
    @pytest.mark.parametrize("line", ["", "   ", "\n", "SEGGER banner", "ready."])
    def test_ignored(self, line):
        """A dongle may print something before anyone is listening."""
        assert parse_line(line) is None


class TestFields:
    def test_value_containing_an_equals(self):
        assert parse_fields("data=a=b")["data"] == "a=b"

    def test_token_without_a_value_is_kept(self):
        """"ok Nordic PCA10059 proto=1.0" carries two positional tokens."""
        fields = parse_fields("Nordic PCA10059 proto=1.0")
        assert fields["Nordic"] == "" and fields["PCA10059"] == ""
        assert fields["proto"] == "1.0"


class TestHex:
    def test_round_trip(self):
        assert from_hex(to_hex(b"\x00\xff\x10")) == b"\x00\xff\x10"

    def test_text_is_encoded_as_utf8(self):
        assert encode_payload("version") == b"version".hex()

    def test_bytes_are_encoded_directly(self):
        assert encode_payload(b"\x01\x02") == "0102"

    def test_bad_hex_names_the_value(self):
        with pytest.raises(DongleProtocolError, match="where hex was expected"):
            from_hex("nothex")

    def test_odd_length_hex_is_rejected(self):
        with pytest.raises(DongleProtocolError):
            from_hex("abc")


class TestAddresses:
    def test_normalised_to_upper_case(self):
        assert normalise_address("e4:1c:7b:02:9a:11") == "E4:1C:7B:02:9A:11"

    def test_a_type_suffix_is_dropped_from_the_address(self):
        assert normalise_address("E4:1C:7B:02:9A:11/1") == "E4:1C:7B:02:9A:11"

    def test_the_type_can_be_read_back(self):
        assert address_type_of("E4:1C:7B:02:9A:11/0") is AddressType.PUBLIC
        assert address_type_of("E4:1C:7B:02:9A:11") is None

    def test_formatting_appends_the_type(self):
        assert format_address("e4:1c:7b:02:9a:11", 1) == "E4:1C:7B:02:9A:11/1"

    @pytest.mark.parametrize(
        "text", ["", "not an address", "E4:1C:7B:02:9A", "E4:1C:7B:02:9A:11:22", "GG:1C:7B:02:9A:11"]
    )
    def test_a_malformed_address_says_what_was_expected(self, text):
        with pytest.raises(DongleProtocolError, match="six colon-separated octets"):
            normalise_address(text)
