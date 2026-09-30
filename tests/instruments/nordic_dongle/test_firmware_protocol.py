"""The firmware and the driver must agree about the protocol.

``firmware/nordic_dongle/include/protocol.h`` is the contract. The firmware
builds its dispatch table from it; this test parses the same header and checks
the driver's constants against it. A command added on one side and forgotten on
the other then fails here, rather than at a bench as "unknown command" - which
is the failure mode a two-language interface produces if nobody watches it.

Nothing here compiles or runs the firmware: no toolchain is needed. It reads the
source as text, which is what makes it a test the build can run everywhere.

Traces to: BLE-FR-001, BLE-FR-080, BLE-NFR-003, SWE4-UT-BLEFW.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from benchtools.instruments.nordic_dongle import constants

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIRMWARE = ROOT / "firmware" / "nordic_dongle"
PROTOCOL_H = FIRMWARE / "include" / "protocol.h"
CMD_PARSER_C = FIRMWARE / "src" / "cmd_parser.c"


def _header() -> str:
    assert PROTOCOL_H.exists(), "missing firmware header: %s" % PROTOCOL_H
    return PROTOCOL_H.read_text()


def _table(name: str) -> str:
    """Return the body of a ``#define <name> \\`` continuation table."""
    text = _header()
    start = text.index("#define %s" % name)
    body = []
    for line in text[start:].splitlines()[1:]:
        body.append(line)
        if not line.rstrip().endswith("\\"):
            break
    return "\n".join(body)


def firmware_commands():
    """``{name: (min_args, max_args)}`` from PROTO_COMMAND_TABLE."""
    found = {}
    for name, minimum, maximum in re.findall(
        r"X\((\w+),\s*(\d+),\s*(\d+),", _table("PROTO_COMMAND_TABLE")
    ):
        found[name] = (int(minimum), int(maximum))
    return found


def firmware_events():
    return tuple(re.findall(r"X\((\w+),", _table("PROTO_EVENT_TABLE")))


def firmware_errors():
    return {
        symbol: int(code)
        for symbol, code in re.findall(r"X\((PROTO_ERR_\w+),\s*(\d+),", _table("PROTO_ERROR_TABLE"))
    }


class TestCommands:
    def test_the_header_defines_commands(self):
        """Guard against the parsing silently finding nothing."""
        assert len(firmware_commands()) >= 10

    def test_the_driver_knows_every_firmware_command(self):
        missing = sorted(set(firmware_commands()) - set(constants.COMMANDS))
        assert not missing, (
            "the firmware accepts %s, which the driver's COMMANDS does not list"
            % ", ".join(missing)
        )

    def test_the_driver_invents_no_command(self):
        extra = sorted(set(constants.COMMANDS) - set(firmware_commands()))
        assert not extra, (
            "the driver lists %s, which the firmware does not implement; it "
            "would answer 'unknown command'" % ", ".join(extra)
        )

    def test_argument_bounds_agree(self):
        firmware = firmware_commands()
        wrong = [
            "%s: firmware %s, driver %s" % (name, firmware[name], bounds)
            for name, bounds in constants.COMMANDS.items()
            if firmware.get(name) != bounds
        ]
        assert not wrong, "argument bounds disagree:\n  " + "\n  ".join(wrong)

    def test_every_command_has_a_handler_in_the_firmware(self):
        """A documented command with no implementation answers 'unknown'."""
        source = CMD_PARSER_C.read_text()
        attached = set(re.findall(r'\{\s*"(\w+)",\s*command_\w+\s*\}', source))
        missing = sorted(set(firmware_commands()) - attached)
        assert not missing, (
            "no handler is attached in cmd_parser.c for: %s" % ", ".join(missing)
        )


class TestEventsAndErrors:
    def test_the_driver_knows_every_event(self):
        assert set(firmware_events()) == set(constants.EVENTS)

    def test_error_codes_agree(self):
        firmware = firmware_errors()
        assert len(firmware) >= 10
        for symbol, code in firmware.items():
            name = symbol.replace("PROTO_ERR_", "")
            name = {"NOT_CONN": "NOT_CONNECTED"}.get(name, name)
            if name == "LIMIT":
                continue
            member = getattr(constants.DongleError, name, None)
            assert member is not None, "the driver has no DongleError.%s" % name
            assert int(member) == code, (
                "%s is %d in the firmware and %d in the driver" % (symbol, code, int(member))
            )


class TestEnvelope:
    def test_the_longest_command_line_fits(self):
        """A full payload in hex, with a timeout, is a command the firmware reads whole."""
        limits = constants.DONGLE_LIMITS
        line = "cmd " + "ff" * limits.max_payload_bytes + " timeout=60000"
        assert len(line) + 1 <= limits.max_line_bytes

    def test_the_longest_reply_line_fits(self):
        """At 192 characters a reply over ~60 bytes was cut short (#52)."""
        limits = constants.DONGLE_LIMITS
        top = 18446744073709551615              # the widest 64-bit timestamp
        line = "ok t_tx=%d t_rx=%d dt_us=%d interval_us=%d len=%d data=%s" % (
            top, top, 4294967295, 4294967295, limits.max_payload_bytes,
            "ff" * limits.max_payload_bytes)
        assert len(line) + 1 <= limits.max_event_bytes

    @pytest.mark.parametrize(
        "macro,attribute",
        [
            ("PROTO_MAX_SENSORS", "max_sensors"),
            ("PROTO_MAX_PAYLOAD", "max_payload_bytes"),
            ("PROTO_MAX_NAME", "max_name_length"),
            ("PROTO_MAX_LINE", "max_line_bytes"),
            ("PROTO_MAX_EVENT", "max_event_bytes"),
        ],
    )
    def test_limits_agree(self, macro, attribute):
        """The driver refuses what the firmware would truncate."""
        match = re.search(r"#define\s+%s\s+(\d+)U?" % macro, _header())
        assert match is not None, "the firmware no longer defines %s" % macro
        assert int(match.group(1)) == getattr(constants.DONGLE_LIMITS, attribute)

    def test_protocol_version_agrees(self):
        match = re.search(r'#define\s+PROTO_VERSION\s+"([^"]+)"', _header())
        assert match is not None
        assert match.group(1) == constants.PROTOCOL_VERSION

    def test_model_agrees(self):
        match = re.search(r'#define\s+PROTO_MODEL\s+"([^"]+)"', _header())
        assert match.group(1) == constants.DONGLE_LIMITS.model


class TestFirmwareHygiene:
    """Checks on the firmware sources that do not need a compiler."""

    def sources(self):
        return sorted(
            path
            for pattern in ("*.c", "*.h")
            for path in FIRMWARE.rglob(pattern)
        )

    def test_sources_are_found(self):
        assert len(self.sources()) >= 10

    def test_every_source_declares_its_trace(self):
        offenders = [
            str(path.relative_to(ROOT))
            for path in self.sources()
            if "Traces to" not in path.read_text()
        ]
        assert not offenders, (
            "firmware file(s) with no 'Traces to' line:\n  " + "\n  ".join(offenders)
        )

    def test_no_dynamic_allocation(self):
        """MISRA C:2012 Rule 21.3. A bench tool that fragments its heap at hour
        six of a soak test is worse than one that cannot allocate at all."""
        offenders = []
        for path in self.sources():
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if re.search(r"\b(malloc|calloc|realloc|free)\s*\(", line):
                    offenders.append("%s:%d" % (path.relative_to(ROOT), number))
        assert not offenders, "dynamic allocation in the firmware:\n  " + "\n  ".join(offenders)

    def test_indentation_is_tabs(self):
        """House style for C in this repository: tabs, one tab per level."""
        offenders = []
        for path in self.sources():
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if line.startswith("    ") and not line.lstrip().startswith("*"):
                    offenders.append("%s:%d" % (path.relative_to(ROOT), number))
        assert not offenders, (
            "space-indented line(s) in the firmware:\n  " + "\n  ".join(offenders[:20])
        )
