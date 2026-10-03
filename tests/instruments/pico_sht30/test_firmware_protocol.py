"""The firmware and the driver must agree about the protocol.

``firmware/pico_sht30/include/protocol.h`` is the contract; this test parses it
and ``firmware_version.h`` as text and compares them with the driver's
constants. No toolchain is needed.

Traces to: PICO-FR-001, PICO-FR-002, PICO-NFR-004, SWE4-UT-PICOFWPROTO.
"""

from __future__ import annotations

import pathlib
import re

from benchtools.instruments.pico_sht30 import constants

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIRMWARE = ROOT / "firmware" / "pico_sht30"
PROTOCOL_H = FIRMWARE / "include" / "protocol.h"
VERSION_H = FIRMWARE / "include" / "firmware_version.h"
BOARD_H = FIRMWARE / "include" / "board_config.h"


def _table(name: str) -> str:
    text = PROTOCOL_H.read_text()
    start = text.index("#define %s" % name)
    body = []
    for line in text[start:].splitlines()[1:]:
        body.append(line)
        if not line.rstrip().endswith("\\"):
            break
    return "\n".join(body)


def _define(path: pathlib.Path, name: str) -> str:
    match = re.search(r'#define\s+%s\s+"([^"]*)"' % name, path.read_text())
    assert match, "%s not defined in %s" % (name, path.name)
    return match.group(1)


def test_commands_agree():
    firmware = {
        name: (int(low), int(high))
        for name, low, high in re.findall(
            r"X\((\w+),\s*(\d+),\s*(\d+),", _table("PROTO_COMMAND_TABLE")
        )
    }
    assert firmware == constants.COMMANDS


def test_errors_agree():
    firmware = {
        int(code): symbol
        for symbol, code in re.findall(r"X\((\w+),\s*(\d+)U?,", _table("PROTO_ERROR_TABLE"))
    }
    assert firmware == constants.ERRORS


def test_protocol_version_agrees():
    assert _define(PROTOCOL_H, "PROTO_VERSION") == constants.PROTOCOL_VERSION


def test_sensor_agrees():
    assert _define(PROTOCOL_H, "PROTO_SENSOR") == constants.SENSOR


def test_name_and_copyright_agree():
    assert _define(VERSION_H, "FIRMWARE_NAME") == constants.NAME
    assert _define(VERSION_H, "FIRMWARE_COPYRIGHT") == constants.COPYRIGHT


def test_version_is_semantic():
    """V<major>.<minor, 2 digits>.<patch, 4 digits>, e.g. V1.00.0000."""
    assert re.fullmatch(r"V\d+\.\d{2}\.\d{4}", _define(VERSION_H, "FIRMWARE_VERSION"))


def test_default_address_agrees():
    match = re.search(r"#define\s+BOARD_SHT30_ADDRESS\s+0x([0-9A-Fa-f]+)U", BOARD_H.read_text())
    assert match and int(match.group(1), 16) == constants.DEFAULT_ADDRESS


def test_firmware_sources_use_tabs():
    """House style: C is indented with tabs."""
    offenders = []
    for path in sorted(FIRMWARE.rglob("*.[ch]")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.match(r"^ {2,}\S", line) and not line.lstrip().startswith("*"):
                offenders.append("%s:%d" % (path.relative_to(ROOT), number))
    assert not offenders, "space-indented C lines:\n  " + "\n  ".join(offenders)


def test_firmware_uses_no_stdio_formatting():
    """MISRA C:2012 Rule 21.6: no printf family in the firmware."""
    for path in sorted((FIRMWARE / "src").glob("*.c")):
        text = path.read_text()
        assert not re.search(r"\b(s?n?printf|sscanf|fprintf)\s*\(", text), path.name
