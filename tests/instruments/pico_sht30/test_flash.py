"""Reflashing the Pico 2 thermometer with no BOOTSEL press.

Every path runs against :class:`SimulatedRp2350` or stand-in seams; no Pico,
drive or serial port is needed.

Traces to: PICO-FR-070 .. PICO-FR-076, SWE4-UT-PICOFLASH.
"""

from __future__ import annotations

import json
import os
import struct

import pytest

from benchtools.instruments.pico_sht30 import (
    FlashError,
    PicoFlasher,
    SimulatedRp2350,
    Uf2Image,
)
from benchtools.instruments.pico_sht30 import flash as flash_module
from benchtools.instruments.pico_sht30.cli import main

VERSION = "V1.00.0002"
SHA = "abc1234"
THERMOMETER = (b"Pico 2 SHT30 Temperature Sensor\x00(c) 2026 Dermot Murphy\x00"
               + VERSION.encode() + b"\x00" + SHA.encode() + b"\x00")


def make_uf2(payload: bytes = THERMOMETER, family: int = flash_module.RP2350_ARM_S_FAMILY_ID,
             absolute_block: bool = True) -> bytes:
    """A UF2 file as an SDK 2.x RP2350 build lays it out."""
    chunks = [payload[i:i + 256] for i in range(0, len(payload), 256)] or [b""]
    entries = ([(flash_module.ABSOLUTE_FAMILY_ID, b"\xff" * 256)] if absolute_block else [])
    entries += [(family, chunk) for chunk in chunks]
    blocks = []
    for number, (fam, chunk) in enumerate(entries):
        header = struct.pack(
            "<8I", flash_module.UF2_MAGIC_START0, flash_module.UF2_MAGIC_START1,
            flash_module.UF2_FLAG_FAMILY_ID_PRESENT, 0x10000000 + 256 * number, len(chunk),
            number, len(entries), fam,
        )
        body = chunk.ljust(476, b"\x00")
        blocks.append(header + body + struct.pack("<I", flash_module.UF2_MAGIC_END))
    return b"".join(blocks)


@pytest.fixture
def uf2(tmp_path):
    path = tmp_path / "pico_sht30.uf2"
    path.write_bytes(make_uf2())
    return str(path)


@pytest.fixture
def board():
    simulated = SimulatedRp2350()
    yield simulated
    simulated.close()


def instant(**kwargs) -> dict:
    """Seams for a clock that advances one second per poll, without sleeping."""
    now = [0.0]

    def sleep(seconds):
        now[0] += max(seconds, 1.0)

    kwargs.setdefault("clock", lambda: now[0])
    kwargs.setdefault("sleep", sleep)
    return kwargs


# ---------------------------------------------------------------------------
# The image
# ---------------------------------------------------------------------------
def test_image_is_parsed(uf2):
    image = Uf2Image.load(uf2)
    assert image.blocks == 2
    assert image.family_names == ["absolute", "rp2350-arm-s"]
    assert image.for_rp2350
    assert image.is_thermometer
    assert image.version == VERSION
    assert image.sha == SHA


def test_not_a_whole_number_of_blocks():
    with pytest.raises(FlashError, match="not a UF2"):
        Uf2Image.parse(b"\x00" * 100)


def test_bad_magic():
    data = bytearray(make_uf2())
    data[0] ^= 0xFF
    with pytest.raises(FlashError, match="magic"):
        Uf2Image.parse(bytes(data))


def test_missing_file(tmp_path):
    with pytest.raises(FlashError, match="cannot read"):
        Uf2Image.load(str(tmp_path / "nothing.uf2"))


def test_rp2040_image_is_refused(tmp_path, board):
    path = tmp_path / "rp2040.uf2"
    path.write_bytes(make_uf2(family=flash_module.RP2040_FAMILY_ID, absolute_block=False))
    assert not Uf2Image.load(str(path)).for_rp2350
    with pytest.raises(FlashError, match="rp2040"):
        board.flasher(**instant()).flash(str(path))
    assert board.flashes == 0


def test_other_firmware_needs_any_image(tmp_path, board):
    path = tmp_path / "micropython.uf2"
    path.write_bytes(make_uf2(payload=b"MicroPython\x00"))
    with pytest.raises(FlashError, match="--any-image"):
        board.flasher(**instant()).flash(str(path))
    result = board.flasher(**instant()).flash(str(path), any_image=True)
    assert board.flashes == 1
    assert result.after is None
    assert "not the thermometer" in result.notes[0]


def test_ambiguous_sha_is_not_compared(tmp_path, board):
    path = tmp_path / "two_shas.uf2"
    path.write_bytes(make_uf2(THERMOMETER + b"\x00deadbee\x00"))
    assert Uf2Image.load(str(path)).sha == ""
    result = board.flasher(**instant()).flash(str(path))
    assert result.ok
    assert "sha" not in result.checks
    assert any("commit SHA" in note for note in result.notes)


def test_missing_version_is_not_compared(tmp_path, board):
    path = tmp_path / "no_version.uf2"
    path.write_bytes(make_uf2(b"Pico 2 SHT30 Temperature Sensor\x00" + SHA.encode() + b"\x00"))
    result = board.flasher(**instant()).flash(str(path))
    assert result.ok
    assert "version" not in result.checks
    assert any("version string" in note for note in result.notes)


# ---------------------------------------------------------------------------
# The whole flash, against the simulated board
# ---------------------------------------------------------------------------
def test_success_from_running_firmware(uf2, board):
    result = board.flasher(**instant()).flash(uf2)
    assert result.ok
    assert result.method == "bootsel"
    assert board.firmware.bootloader_requests == 1
    assert board.flashes == 1
    assert result.before.sha == board.firmware.DEFAULT_SHA
    assert result.after.sha == SHA
    assert result.after.version == VERSION
    assert set(result.checks) == {"name", "version", "sha"}
    assert not board.in_bootloader


def test_success_from_bootloader(uf2):
    blank = SimulatedRp2350(in_bootloader=True)
    try:
        result = blank.flasher(**instant()).flash(uf2)
    finally:
        blank.close()
    assert result.ok
    assert result.method == "already-in-bootloader"
    assert result.before is None
    assert blank.firmware.bootloader_requests == 0


def test_version_mismatch_is_reported_not_raised(uf2, board):
    result = board.flasher(**instant()).flash(uf2, expect_version="V2.00.0000")
    assert not result.ok
    assert result.checks["version"] == {"expected": "V2.00.0000", "actual": VERSION,
                                        "ok": False}


def test_build_mismatch_is_reported(uf2, board):
    def stale_copy(image, drive):
        target = board.copy(image, drive)
        board.firmware.sha = "0ld0ld0"   # the old image kept running
        return target

    result = board.flasher(**instant(copy=stale_copy)).flash(uf2)
    assert not result.ok
    assert result.checks["sha"]["actual"] == "0ld0ld0"


def test_falls_back_to_1200_baud_when_the_protocol_does_not_answer(uf2, board):
    touched = []

    def mute(_port):
        raise flash_module.InstrumentError("no reply")

    def touch(port):
        touched.append(port)
        board.touch(port)

    opens = iter([mute, board.open_thermometer])

    def open_thermometer(port):
        return next(opens)(port)

    result = board.flasher(
        **instant(open_thermometer=open_thermometer, touch=touch)
    ).flash(uf2)
    assert touched == ["sim://"]
    assert result.method == "1200-baud"
    assert result.ok


def test_bootloader_timeout(uf2, board):
    board.firmware.on_bootloader = None   # answers bootsel, never reboots
    with pytest.raises(FlashError, match="timed out after 3 s waiting for the RP2350"):
        board.flasher(**instant(bootloader_timeout=3)).flash(uf2)
    assert board.flashes == 0


def test_no_drive_and_no_port(uf2):
    flasher = PicoFlasher(port=None, find_drives=lambda: [], **instant())
    with pytest.raises(FlashError, match="no RP2350 drive is present and no port"):
        flasher.flash(uf2)


def test_two_drives_need_drive_option(uf2):
    flasher = PicoFlasher(port=None, find_drives=lambda: ["D:\\", "E:\\"], **instant())
    with pytest.raises(FlashError, match="pass --drive"):
        flasher.flash(uf2)


def test_copy_failure(uf2, board):
    def failing_copy(_image, _drive):
        raise FlashError("copying failed: disk full")

    with pytest.raises(FlashError, match="disk full"):
        board.flasher(**instant(copy=failing_copy)).flash(uf2)


def test_drive_that_never_goes_away(uf2, board):
    with pytest.raises(FlashError, match="go away"):
        board.flasher(**instant(copy=lambda image, drive: drive)).flash(uf2)


def test_port_that_never_comes_back(uf2, board):
    def dead(_port):
        raise flash_module.InstrumentError("no reply")

    opens = iter([board.open_thermometer])

    def open_thermometer(port):
        return next(opens, dead)(port)

    flasher = board.flasher(**instant(open_thermometer=open_thermometer, port_timeout=2))
    with pytest.raises(FlashError, match="thermometer to answer"):
        flasher.flash(uf2)


def test_port_found_by_vendor_id(uf2, board):
    flasher = board.flasher(**instant())
    flasher.port = None
    board.firmware.on_bootloader = None
    board.touch("sim://")                       # start in the bootloader
    result = flasher.flash(uf2)
    assert result.port == "sim://"
    assert result.ok


def test_no_verify(uf2, board):
    result = board.flasher(**instant()).flash(uf2, verify=False)
    assert result.after is None
    assert result.notes == ["not verified: --no-verify"]


# ---------------------------------------------------------------------------
# The operating system seams
# ---------------------------------------------------------------------------
def test_drive_is_recognised_by_its_info_file(tmp_path):
    good, other, empty = tmp_path / "good", tmp_path / "other", tmp_path / "empty"
    for path in (good, other, empty):
        path.mkdir()
    (good / "INFO_UF2.TXT").write_text("UF2 Bootloader v1.0\nModel: Raspberry Pi RP2350\n"
                                        "Board-ID: RP2350\n")
    (other / "INFO_UF2.TXT").write_text("UF2 Bootloader v3.0\nBoard-ID: RPI-RP2\n")
    roots = [str(good), str(other), str(empty), str(tmp_path / "absent")]
    assert flash_module.find_bootloader_drives(roots) == [str(good)]


def test_windows_roots():
    roots = flash_module.candidate_roots("Windows")
    assert roots[0] == "C:\\" and roots[-1] == "Z:\\"


def test_linux_roots(monkeypatch):
    monkeypatch.setattr(flash_module.glob, "glob",
                        lambda pattern: ["/media/bench/RP2350"] if pattern == "/media/*/*" else [])
    assert flash_module.candidate_roots("Linux") == ["/media/bench/RP2350"]


def test_macos_roots(monkeypatch):
    monkeypatch.setattr(flash_module.glob, "glob",
                        lambda pattern: ["/Volumes/RP2350"] if pattern == "/Volumes/*" else [])
    assert flash_module.candidate_roots("Darwin") == ["/Volumes/RP2350"]


def test_other_systems_are_unsupported():
    with pytest.raises(FlashError, match="not supported on Plan9"):
        flash_module.candidate_roots("Plan9")


def test_copy_image_writes_the_file(tmp_path, uf2):
    target = flash_module.copy_image(Uf2Image.load(uf2), str(tmp_path))
    with open(target, "rb") as handle:
        assert handle.read() == Uf2Image.load(uf2).data


def test_copy_error_while_drive_remains(tmp_path, uf2):
    drive = tmp_path / "drive"
    (drive / "pico_sht30.uf2").mkdir(parents=True)     # cannot be opened as a file
    with pytest.raises(FlashError, match="copying"):
        flash_module.copy_image(Uf2Image.load(uf2), str(drive))


def test_copy_error_after_the_drive_went_is_not_an_error(tmp_path, uf2):
    flash_module.copy_image(Uf2Image.load(uf2), str(tmp_path / "gone"))


# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------
def test_cli_flash(capsys, uf2):
    status = main(["-r", "sim://", "flash", uf2, "--expect-version", VERSION])
    payload = json.loads(capsys.readouterr().out)
    assert status == 0
    assert payload["ok"] is True
    assert payload["method"] == "bootsel"
    assert payload["after"]["sha"] == SHA


def test_cli_flash_mismatch_exits_1(capsys, uf2):
    assert main(["flash", uf2, "--expect-version", "V9.99.9999"]) == 1
    assert json.loads(capsys.readouterr().out)["checks"]["version"]["ok"] is False


def test_cli_flash_error_exits_1(capsys, tmp_path):
    assert main(["flash", str(tmp_path / "none.uf2")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_simulated_drive_is_removed(board):
    board.touch("sim://")
    assert os.path.isdir(board.drive)
    board.close()
    assert not os.path.isdir(board.drive)


def test_touch_1200_error_is_a_note_not_a_failure(monkeypatch):
    """On Windows the Pico reboots while the port is being configured."""
    import serial

    def vanishing(*_args, **_kwargs):
        raise serial.SerialException("A device attached to the system is not functioning.")

    monkeypatch.setattr(serial, "Serial", vanishing)
    assert "not functioning" in flash_module.touch_1200("COM14")


def test_touch_1200_note_reaches_the_result(uf2, board):
    def mute(_port):
        raise flash_module.InstrumentError("no reply")

    def touch(port):
        board.touch(port)
        return "the 1200-baud reset on sim:// reported: gone"

    opens = iter([mute, board.open_thermometer])

    def open_thermometer(port):
        return next(opens)(port)

    result = board.flasher(**instant(open_thermometer=open_thermometer, touch=touch)).flash(uf2)
    assert result.ok
    assert "reported: gone" in result.notes[-1]
