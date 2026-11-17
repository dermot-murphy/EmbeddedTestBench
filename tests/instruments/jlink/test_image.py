"""Reading what an image file writes: Intel HEX and ELF.

Traces to: JLINK-FR-008, SWE4-UT-JLINKIMAGE.
"""

from __future__ import annotations

import struct

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.instruments.jlink.image import read_elf, read_image, read_intel_hex


def record(kind: int, offset: int, payload: bytes) -> str:
    """One Intel HEX record, with its checksum."""
    body = bytes([len(payload), offset >> 8, offset & 0xFF, kind]) + payload
    return ":" + (body + bytes([(-sum(body)) & 0xFF])).hex().upper()


EOF_RECORD = ":00000001FF"


def elf(segments) -> bytes:
    """A minimal 32-bit little-endian ELF holding *segments*, each
    ``(type, paddr, vaddr, data)``."""
    header_size, entry_size = 52, 32
    offset = header_size + entry_size * len(segments)
    headers, payload = b"", b""
    for kind, paddr, vaddr, data in segments:
        headers += struct.pack("<8I", kind, offset + len(payload), vaddr, paddr,
                               len(data), len(data), 5, 4)
        payload += data
    ident = b"\x7fELF" + bytes([1, 1, 1]) + bytes(9)
    header = ident + struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, 0, header_size, 0, 0,
                                 header_size, entry_size, len(segments), 0, 0, 0)
    return header + headers + payload


class TestIntelHex:
    def test_data_records_become_one_contiguous_range(self):
        text = "\n".join([record(0, 0x0000, b"\x01\x02"), record(0, 0x0002, b"\x03"),
                          EOF_RECORD])
        ranges = read_intel_hex(text)
        assert [(item.address, item.data) for item in ranges] == [(0, b"\x01\x02\x03")]

    def test_a_gap_starts_a_new_range(self):
        text = "\n".join([record(0, 0x0000, b"\xaa"), record(0, 0x0010, b"\xbb"), EOF_RECORD])
        assert [(item.address, item.data) for item in read_intel_hex(text)] == [
            (0x0000, b"\xaa"), (0x0010, b"\xbb")]

    def test_extended_linear_address_places_uicr(self):
        """The V11 image's UICR record is how 0x10001014 got programmed (#69)."""
        text = "\n".join([record(4, 0, b"\x10\x00"), record(0, 0x1014, b"\x00\x80\x0f\x00"),
                          EOF_RECORD])
        ranges = read_intel_hex(text)
        assert [(item.name, item.address, item.data) for item in ranges] == [
            ("0x10001014", 0x10001014, b"\x00\x80\x0f\x00")]

    def test_extended_segment_address(self):
        text = "\n".join([record(2, 0, b"\x10\x00"), record(0, 0x0004, b"\x55"), EOF_RECORD])
        assert read_intel_hex(text)[0].address == 0x10004

    def test_start_address_records_write_nothing(self):
        text = "\n".join([record(5, 0, b"\x00\x00\x0a\x81"), record(0, 0, b"\x01"), EOF_RECORD])
        assert [item.data for item in read_intel_hex(text)] == [b"\x01"]

    def test_nothing_after_end_of_file_is_read(self):
        text = "\n".join([record(0, 0, b"\x01"), EOF_RECORD, record(0, 0x100, b"\x02")])
        assert len(read_intel_hex(text)) == 1

    def test_a_bad_checksum_is_refused(self):
        good = record(0, 0, b"\x01\x02")
        bad = good[:-2] + ("%02X" % ((int(good[-2:], 16) + 1) & 0xFF))
        with pytest.raises(ConfigurationError, match="checksum"):
            read_intel_hex(bad)

    def test_an_unknown_record_type_is_refused(self):
        with pytest.raises(ConfigurationError, match="record type 07"):
            read_intel_hex(record(7, 0, b"\x00"))

    def test_a_line_that_is_not_a_record_is_refused(self):
        with pytest.raises(ConfigurationError, match="line 1"):
            read_intel_hex("hello")


class TestElf:
    def test_loadable_segments_at_their_load_address(self):
        """.data lives in RAM but is programmed into flash: the physical
        address is where the bytes go."""
        content = elf([(1, 0x00001000, 0x00001000, b"\x11" * 8),
                       (1, 0x00002000, 0x20000000, b"\x22" * 4)])
        ranges = read_elf(content)
        assert [(item.address, item.data) for item in ranges] == [
            (0x1000, b"\x11" * 8), (0x2000, b"\x22" * 4)]
        assert ranges[0].name == "segment 0"

    def test_segments_without_file_bytes_or_not_loadable_are_skipped(self):
        content = elf([(1, 0x1000, 0x1000, b""), (4, 0x3000, 0x3000, b"\x33"),
                       (1, 0x4000, 0x4000, b"\x44")])
        assert [item.address for item in read_elf(content)] == [0x4000]

    def test_a_64_bit_elf_is_refused(self):
        content = bytearray(elf([(1, 0, 0, b"\x00")]))
        content[4] = 2
        with pytest.raises(ConfigurationError, match="32-bit little-endian"):
            read_elf(bytes(content))


class TestReadImage:
    def test_the_format_is_chosen_by_content(self, tmp_path):
        hex_file = tmp_path / "app.hex"
        hex_file.write_text(record(0, 0, b"\x01") + "\n" + EOF_RECORD + "\n")
        elf_file = tmp_path / "app.elf"
        elf_file.write_bytes(elf([(1, 0x8000, 0x8000, b"\x02")]))
        assert read_image(str(hex_file))[0].data == b"\x01"
        assert read_image(str(elf_file))[0].address == 0x8000

    def test_a_raw_binary_is_refused(self, tmp_path):
        path = tmp_path / "app.bin"
        path.write_bytes(b"\x00\x01\x02")
        with pytest.raises(ConfigurationError, match="raw binary"):
            read_image(str(path))

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(ConfigurationError, match="no such image"):
            read_image(str(tmp_path / "absent.hex"))
