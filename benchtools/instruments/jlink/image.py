"""What an image file puts where: Intel HEX and ELF, read on the host.

The ``segger`` backend has no GDB, so nothing reads an image's sections for
it. ``JLink.exe`` programs a file and verifies its own write, but a report that
says only "O.K." is the kind of answer issue #69 taught this driver not to
trust: ``monitor flash erase`` said O.K. and erased nothing. So the backend
reads the image here, knows each range it holds, and compares each range with
what the target reads back afterwards - the same per-range verdict GDB's
``compare-sections`` gives the ``gdb`` backend.

Only the parts of the formats an image for a Cortex-M uses are read:

* Intel HEX: data (00), end of file (01), extended segment address (02) and
  extended linear address (04). Start addresses (03, 05) say where to run, not
  what to write, and are skipped. Every record's checksum is checked.
* ELF: 32-bit, little-endian, the ``PT_LOAD`` program headers with bytes in
  the file, placed at their physical (load) address - where flash holds them,
  which for ``.data`` is not where the program uses them.

A raw binary is refused, as the ``gdb`` backend refuses it: it holds no
addresses (JLink_Integration_Notes §5).

Traces to: JLINK-FR-008, JLINK-DD-IMAGE.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Dict, List

from ...core.errors import ConfigurationError

__all__ = ["ImageRange", "read_image", "read_intel_hex", "read_elf"]


@dataclass(frozen=True)
class ImageRange:
    """One contiguous run of bytes an image writes.

    :param name: How a report names it: the ELF segment's index, or the HEX
        run's start address.
    :param address: First byte's address on the target.
    :param data: The bytes.
    """

    name: str
    address: int
    data: bytes

    @property
    def end(self) -> int:
        """One past the last byte."""
        return self.address + len(self.data)


def read_image(path: str) -> List[ImageRange]:
    """The ranges *path* writes, by its format: ELF by its magic number,
    otherwise Intel HEX by its first character.

    :raises ConfigurationError: for a missing file, a format that is neither,
        or a file that does not parse.
    """
    if not os.path.isfile(path):
        raise ConfigurationError("no such image file: %s" % path)
    with open(path, "rb") as handle:
        content = handle.read()
    if content[:4] == b"\x7fELF":
        return read_elf(content, path)
    if content.lstrip()[:1] == b":":
        return read_intel_hex(content.decode("ascii", errors="replace"), path)
    raise ConfigurationError(
        "%s is neither an ELF nor an Intel HEX file. A raw binary holds no "
        "addresses, so it is not flashed by this driver." % path
    )


def _record(line: str, number: int, path: str) -> bytes:
    """One Intel HEX record's bytes, its length and checksum checked."""
    if not line.startswith(":"):
        raise ConfigurationError("%s line %d is not an Intel HEX record" % (path, number))
    try:
        record = bytes.fromhex(line[1:])
    except ValueError as exc:
        raise ConfigurationError(
            "%s line %d holds a character that is not hex" % (path, number)) from exc
    if len(record) < 5 or len(record) != record[0] + 5:
        raise ConfigurationError("%s line %d has the wrong length" % (path, number))
    if sum(record) & 0xFF:
        raise ConfigurationError("%s line %d fails its checksum" % (path, number))
    return record


#: Record types that move the base address, and by how far to shift it.
_BASE_SHIFT = {0x02: 4, 0x04: 16}


def read_intel_hex(text: str, path: str = "<hex>") -> List[ImageRange]:
    """Parse Intel HEX *text* into contiguous ranges, lowest address first."""
    memory: Dict[int, int] = {}
    base = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        record = _record(line, number, path)
        count, offset, kind = record[0], (record[1] << 8) | record[2], record[3]
        payload = record[4:4 + count]
        if kind == 0x00:
            for index, byte in enumerate(payload):
                memory[base + offset + index] = byte
        elif kind == 0x01:
            break
        elif kind in _BASE_SHIFT:
            base = int.from_bytes(payload, "big") << _BASE_SHIFT[kind]
        elif kind not in (0x03, 0x05):
            raise ConfigurationError(
                "%s line %d has record type %02X, which Intel HEX does not define"
                % (path, number, kind))
    return _runs(memory)


def _runs(memory: Dict[int, int]) -> List[ImageRange]:
    """Contiguous runs of the bytes in *memory*."""
    runs: List[List[int]] = []
    for address in sorted(memory):
        if runs and address == runs[-1][0] + len(runs[-1]) - 1:
            runs[-1].append(memory[address])
        else:
            runs.append([address, memory[address]])
    return [ImageRange("0x%08x" % run[0], run[0], bytes(run[1:])) for run in runs]


#: ELF program header type of a loadable segment.
_PT_LOAD = 1


def read_elf(content: bytes, path: str = "<elf>") -> List[ImageRange]:
    """The loadable segments of a 32-bit little-endian ELF image."""
    if len(content) < 52 or content[4] != 1 or content[5] != 1:
        raise ConfigurationError(
            "%s is not a 32-bit little-endian ELF file, which a Cortex-M image is"
            % path)
    phoff, = struct.unpack_from("<I", content, 28)
    phentsize, phnum = struct.unpack_from("<HH", content, 42)
    ranges: List[ImageRange] = []
    for index in range(phnum):
        start = phoff + index * phentsize
        if start + 32 > len(content):
            raise ConfigurationError("%s is truncated in its program headers" % path)
        # p_type, p_offset, p_vaddr, p_paddr, p_filesz, ...
        header = struct.unpack_from("<8I", content, start)
        if header[0] != _PT_LOAD or header[4] == 0:
            continue
        offset, size = header[1], header[4]
        if offset + size > len(content):
            raise ConfigurationError("%s is truncated in segment %d" % (path, index))
        ranges.append(ImageRange("segment %d" % index, header[3],
                                 bytes(content[offset:offset + size])))
    ranges.sort(key=lambda item: item.address)
    return ranges
