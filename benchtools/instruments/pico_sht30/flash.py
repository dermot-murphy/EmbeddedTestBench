"""Reflash the Pico 2 thermometer without pressing BOOTSEL.

The RP2350's boot ROM accepts a new image as a UF2 file copied onto the
``RP2350`` mass-storage drive it presents in its USB bootloader. Getting there
normally means holding BOOTSEL while plugging the board in. This module gets
there over the USB link instead, copies the image, and then checks that the
build now running is the one that was copied:

1. **Into the bootloader.** If an ``RP2350`` drive is already present, the Pico
   is there already - the case for a blank board. Otherwise the running
   thermometer is sent ``bootsel``. If the port does not answer the protocol,
   the port is opened at 1200 baud and closed: the Pico SDK's USB stdio reboots
   into the bootloader on that line rate (``PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE``,
   on by default in SDK 2.1.1 when the application does not use TinyUSB
   directly, which this firmware does not).
2. **Copy.** The UF2 is checked first - its blocks, and that it is built for an
   RP2350 - and then written to the drive. The Pico reboots when the last block
   lands, and the drive goes away.
3. **Verify.** The serial port comes back, ``ver`` is read, and its title,
   version and build date are compared with the image. The build date is taken
   from the image itself: the firmware stores it as an ISO 8601 string, so a
   matching ``built=`` proves that the running image is the copied one, not an
   older build of the same version.

What this cannot do: reach a Pico whose firmware has crashed, or never
enumerates on USB. That still needs the BOOTSEL button or an SWD probe.

The operating system is reached only through a small set of seams (drive
discovery, the copy, the 1200-baud touch, opening the thermometer, the clock),
so every path is tested without a Pico, and :class:`SimulatedRp2350` plays the
board for ``sim://``.

Traces to: PICO-FR-070 .. PICO-FR-076, PICO-DD-FLASH.
"""

from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import string
import struct
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from ...core.errors import BenchToolsError, InstrumentError
from ...core.transport.mock import MockTransport
from .constants import TITLE
from .simulator import SimulatedPicoSht30
from .thermometer import FirmwareInfo, PicoSht30

__all__ = [
    "FlashError",
    "FlashResult",
    "PicoFlasher",
    "SimulatedRp2350",
    "Uf2Image",
    "candidate_roots",
    "find_bootloader_drives",
    "find_pico_ports",
    "touch_1200",
]

# ---------------------------------------------------------------------------
# UF2, as the Pico SDK defines it (src/common/boot_uf2_headers/include/boot/uf2.h)
# ---------------------------------------------------------------------------
UF2_BLOCK_SIZE = 512
UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_NOT_MAIN_FLASH = 0x00000001
UF2_FLAG_FAMILY_ID_PRESENT = 0x00002000

RP2040_FAMILY_ID = 0xE48BFF56
ABSOLUTE_FAMILY_ID = 0xE48BFF57
DATA_FAMILY_ID = 0xE48BFF58
RP2350_ARM_S_FAMILY_ID = 0xE48BFF59
RP2350_RISCV_FAMILY_ID = 0xE48BFF5A
RP2350_ARM_NS_FAMILY_ID = 0xE48BFF5B

#: Family IDs, by the names picotool uses.
FAMILY_NAMES: Dict[int, str] = {
    RP2040_FAMILY_ID: "rp2040",
    ABSOLUTE_FAMILY_ID: "absolute",
    DATA_FAMILY_ID: "data",
    RP2350_ARM_S_FAMILY_ID: "rp2350-arm-s",
    RP2350_RISCV_FAMILY_ID: "rp2350-riscv",
    RP2350_ARM_NS_FAMILY_ID: "rp2350-arm-ns",
}

#: What an RP2350 boot ROM will take. An SDK 2.x build for the RP2350 can carry
#: an ``absolute`` block ahead of its image, so that family is accepted too.
RP2350_FAMILIES = frozenset(
    (RP2350_ARM_S_FAMILY_ID, RP2350_RISCV_FAMILY_ID, RP2350_ARM_NS_FAMILY_ID,
     ABSOLUTE_FAMILY_ID, DATA_FAMILY_ID)
)

#: The file every UF2 bootloader drive carries, and the board it names.
INFO_FILE = "INFO_UF2.TXT"
BOARD_ID = "RP2350"

#: USB vendor ID of Raspberry Pi; the SDK's CDC stdio uses it.
RASPBERRY_PI_VID = 0x2E8A

#: The line rate that the SDK's USB stdio takes as "reboot into the bootloader".
MAGIC_BAUD_RATE = 1200

#: ``firmware_version.h`` injects the build date as ISO 8601 UTC, and the image
#: stores it as a NUL-terminated string.
_BUILD_DATE = re.compile(rb"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\x00")

#: Seconds allowed for each wait, by default.
DEFAULT_BOOTLOADER_TIMEOUT = 15.0
DEFAULT_REBOOT_TIMEOUT = 15.0
DEFAULT_PORT_TIMEOUT = 20.0
_POLL_INTERVAL = 0.25


class FlashError(InstrumentError):
    """The Pico could not be reflashed, or the result could not be confirmed."""


#: Largest payload a 512-byte block can hold: 32 bytes of header, 4 of trailer.
_MAX_PAYLOAD = UF2_BLOCK_SIZE - 32 - 4


def _parse_block(block: bytes, index: int, path: str):
    """Check one block; return its family ID (or ``None``) and its main-flash bytes."""
    start0, start1, flags, _address, size, _number, _total, family = struct.unpack_from(
        "<8I", block, 0
    )
    (end,) = struct.unpack_from("<I", block, UF2_BLOCK_SIZE - 4)
    if (start0, start1, end) != (UF2_MAGIC_START0, UF2_MAGIC_START1, UF2_MAGIC_END):
        raise FlashError("%s: block %d has bad UF2 magic numbers" % (path, index))
    if size > _MAX_PAYLOAD:
        raise FlashError("%s: block %d claims %d payload bytes" % (path, index, size))
    content = b"" if flags & UF2_FLAG_NOT_MAIN_FLASH else block[32:32 + size]
    return (family if flags & UF2_FLAG_FAMILY_ID_PRESENT else None), content


# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Uf2Image:
    """A UF2 file, checked block by block.

    :ivar families: The family IDs its blocks carry.
    :ivar payload: The bytes of every main-flash block, in file order; searched
        for the title and build date.
    """

    path: str
    data: bytes
    blocks: int
    families: frozenset
    payload: bytes

    @classmethod
    def load(cls, path: str) -> "Uf2Image":
        """Read and check *path*.

        :raises FlashError: if the file is missing, is not a UF2, or has a
            malformed block.
        """
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            raise FlashError("cannot read %s: %s" % (path, exc)) from exc
        return cls.parse(data, path)

    @classmethod
    def parse(cls, data: bytes, path: str = "<memory>") -> "Uf2Image":
        """Check *data* as a UF2 file."""
        if not data or len(data) % UF2_BLOCK_SIZE:
            raise FlashError(
                "%s is not a UF2 file: %d bytes is not a whole number of %d-byte blocks"
                % (path, len(data), UF2_BLOCK_SIZE)
            )
        families = set()
        payload = bytearray()
        count = len(data) // UF2_BLOCK_SIZE
        for index in range(count):
            family, content = _parse_block(
                data[index * UF2_BLOCK_SIZE:(index + 1) * UF2_BLOCK_SIZE], index, path
            )
            if family is not None:
                families.add(family)
            payload += content
        return cls(path, bytes(data), count, frozenset(families), bytes(payload))

    @property
    def family_names(self) -> List[str]:
        """The families, by name, sorted."""
        return sorted(FAMILY_NAMES.get(f, "0x%08X" % f) for f in self.families)

    @property
    def for_rp2350(self) -> bool:
        """``True`` if an RP2350 boot ROM would accept every block."""
        return bool(self.families) and self.families <= RP2350_FAMILIES

    @property
    def is_thermometer(self) -> bool:
        """``True`` if the image carries the thermometer firmware's title."""
        return TITLE.encode("ascii") + b"\x00" in self.payload

    @property
    def built(self) -> str:
        """The build date stored in the image, or ``""`` if not exactly one."""
        found = set(_BUILD_DATE.findall(self.payload))
        return found.pop().decode("ascii") if len(found) == 1 else ""

    def as_dict(self) -> Dict[str, object]:
        """What the image is, JSON-ready."""
        return {
            "path": self.path,
            "bytes": len(self.data),
            "blocks": self.blocks,
            "families": self.family_names,
            "thermometer": self.is_thermometer,
            "built": self.built,
        }


# ---------------------------------------------------------------------------
# Operating system seams
# ---------------------------------------------------------------------------
def candidate_roots(system: Optional[str] = None) -> List[str]:
    """Where a removable drive can be mounted on this operating system.

    :raises FlashError: on an operating system with no rule here.
    """
    system = system or platform.system()
    if system == "Windows":
        # A: and B: are skipped: probing an empty floppy drive can stall.
        return ["%s:\\" % letter for letter in string.ascii_uppercase[2:]]
    if system == "Linux":
        patterns = ("/media/*/*", "/run/media/*/*", "/media/*", "/mnt/*")
    elif system == "Darwin":
        patterns = ("/Volumes/*",)
    else:
        raise FlashError(
            "finding the RP2350 drive is not supported on %s; pass --drive" % system
        )
    roots: List[str] = []
    for pattern in patterns:
        roots.extend(sorted(glob.glob(pattern)))
    return roots


def _is_bootloader_drive(root: str) -> bool:
    try:
        with open(os.path.join(root, INFO_FILE), "r", encoding="ascii", errors="replace") as handle:
            text = handle.read(1024)
    except OSError:
        return False
    return any(
        line.split(":", 1)[1].strip() == BOARD_ID
        for line in text.splitlines()
        if line.lower().startswith("board-id:")
    )


def find_bootloader_drives(roots: Optional[Sequence[str]] = None) -> List[str]:
    """The mounted drives that are an RP2350 in its USB bootloader."""
    if roots is None:
        roots = candidate_roots()
    return [root for root in roots if os.path.isdir(root) and _is_bootloader_drive(root)]


def find_pico_ports() -> List[str]:
    """Serial ports whose USB vendor is Raspberry Pi. Needs pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise FlashError(
            "finding the Pico's port needs pyserial (pip install benchtools[serial]); "
            "or pass the port with -r"
        ) from exc
    return sorted(p.device for p in list_ports.comports() if p.vid == RASPBERRY_PI_VID)


def touch_1200(port: str) -> Optional[str]:
    """Open *port* at 1200 baud and close it: the SDK's reboot-to-bootloader.

    The Pico reboots the moment it sees the line rate, often while the host is
    still configuring the port, and Windows then reports "a device attached to
    the system is not functioning". That is the reset working, so an error here
    is returned as a note rather than raised; whether the reset worked is
    decided by the bootloader drive appearing, or not, afterwards.
    """
    try:
        import serial
    except ImportError as exc:
        raise FlashError("the 1200-baud reset needs pyserial") from exc
    note = None
    try:
        link = serial.Serial(port, baudrate=MAGIC_BAUD_RATE)
        link.close()
    except (serial.SerialException, OSError) as exc:
        note = "the 1200-baud reset on %s reported: %s" % (port, exc)
    return note


def copy_image(image: Uf2Image, drive: str) -> str:
    """Write *image* onto *drive*; return the path written.

    The Pico reboots as the last block lands and the drive disappears, which
    some systems report as a failed close. A failure is therefore an error only
    if the drive is still there.
    """
    target = os.path.join(drive, os.path.basename(image.path) or "image.uf2")
    try:
        with open(target, "wb") as handle:
            handle.write(image.data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        if os.path.isdir(drive):
            raise FlashError("copying %s to %s failed: %s" % (image.path, drive, exc)) from exc
    return target


def _open_thermometer(port: str) -> PicoSht30:
    return PicoSht30.connect(port, timeout=2.0)


# ---------------------------------------------------------------------------
@dataclass
class FlashResult:  # pylint: disable=too-many-instance-attributes
    """What a flash did, and whether the result was confirmed."""

    image: Uf2Image
    drive: str = ""
    method: str = ""
    port: str = ""
    before: Optional[FirmwareInfo] = None
    after: Optional[FirmwareInfo] = None
    checks: Dict[str, Dict[str, object]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` when every check that could be made passed."""
        return all(check["ok"] for check in self.checks.values())

    def as_dict(self) -> Dict[str, object]:
        """The whole result, JSON-ready."""
        return {
            "ok": self.ok,
            "image": self.image.as_dict(),
            "drive": self.drive,
            "method": self.method,
            "port": self.port,
            "before": self.before.as_dict() if self.before else None,
            "after": self.after.as_dict() if self.after else None,
            "checks": self.checks,
            "notes": self.notes,
        }


class PicoFlasher:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Put a UF2 onto a Pico 2 over USB, with no button press.

    Every interaction with the operating system goes through a constructor
    argument, so that tests and :class:`SimulatedRp2350` can stand in for it.

    :param port: The thermometer's serial port, or ``None`` to find it by USB
        vendor ID afterwards.
    :param drive: The bootloader drive, or ``None`` to find it.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        port: Optional[str] = None,
        drive: Optional[str] = None,
        *,
        bootloader_timeout: float = DEFAULT_BOOTLOADER_TIMEOUT,
        reboot_timeout: float = DEFAULT_REBOOT_TIMEOUT,
        port_timeout: float = DEFAULT_PORT_TIMEOUT,
        find_drives: Callable[[], List[str]] = find_bootloader_drives,
        find_ports: Callable[[], List[str]] = find_pico_ports,
        open_thermometer: Callable[[str], PicoSht30] = _open_thermometer,
        touch: Callable[[str], Optional[str]] = touch_1200,
        copy: Callable[[Uf2Image, str], str] = copy_image,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.port = port
        self.drive = drive
        self.bootloader_timeout = bootloader_timeout
        self.reboot_timeout = reboot_timeout
        self.port_timeout = port_timeout
        self._find_drives = find_drives
        self._find_ports = find_ports
        self._open = open_thermometer
        self._touch = touch
        self._copy = copy
        self._clock = clock
        self._sleep = sleep

    # ------------------------------------------------------------------
    def flash(
        self,
        path: str,
        expect_version: Optional[str] = None,
        any_image: bool = False,
        verify: bool = True,
    ) -> FlashResult:
        """Flash the UF2 at *path* and confirm what is running afterwards.

        :param expect_version: The ``fw=`` the new image must report.
        :param any_image: Allow an image that is not the thermometer firmware.
            Nothing can then be confirmed afterwards beyond the reboot.
        :param verify: Read ``ver`` afterwards and compare.
        :raises FlashError: if the image is unsuitable, the bootloader or the
            port does not appear in time, or the copy fails. A mismatch after a
            successful copy is not raised: it is in the result's ``checks``.
        """
        image = Uf2Image.load(path)
        if not image.for_rp2350:
            raise FlashError(
                "%s is built for %s, not an RP2350"
                % (path, ", ".join(image.family_names) or "no family")
            )
        if not image.is_thermometer and not any_image:
            raise FlashError(
                "%s does not carry the title %r, so it is not the thermometer firmware; "
                "pass --any-image to flash it anyway" % (path, TITLE)
            )
        result = FlashResult(image=image)

        result.drive = self._enter_bootloader(result)
        self._copy(image, result.drive)
        self._wait_for(lambda: result.drive not in self._find_drives(), self.reboot_timeout,
                       "the %s drive to go away after the copy" % result.drive)

        if verify and image.is_thermometer:
            self._verify(result, image, expect_version)
        else:
            result.notes.append("not verified: the image is not the thermometer firmware"
                                if verify else "not verified: --no-verify")
        return result

    # ------------------------------------------------------------------
    def _wait_for(self, condition: Callable[[], object], timeout: float, what: str):
        deadline = self._clock() + timeout
        while True:
            value = condition()
            if value:
                return value
            if self._clock() >= deadline:
                raise FlashError("timed out after %.0f s waiting for %s" % (timeout, what))
            self._sleep(_POLL_INTERVAL)

    def _one_drive(self, drives: List[str]) -> str:
        if self.drive:
            return self.drive if self.drive in drives else ""
        if len(drives) > 1:
            raise FlashError(
                "more than one RP2350 drive (%s); pass --drive" % ", ".join(drives)
            )
        return drives[0] if drives else ""

    def _enter_bootloader(self, result: FlashResult) -> str:
        drive = self._one_drive(self._find_drives())
        if drive:
            result.method = "already-in-bootloader"
            return drive
        if not self.port:
            raise FlashError("no RP2350 drive is present and no port was given to reboot one")

        try:
            thermometer = self._open(self.port)
        except BenchToolsError as exc:
            result.notes.append("%s did not answer the protocol (%s); used the 1200-baud reset"
                                % (self.port, exc))
            note = self._touch(self.port)
            if note:
                result.notes.append(note)
            result.method = "1200-baud"
        else:
            try:
                result.before = thermometer.firmware_info()
                thermometer.enter_bootloader()
            finally:
                thermometer.close()
            result.method = "bootsel"

        return self._wait_for(lambda: self._one_drive(self._find_drives()),
                              self.bootloader_timeout, "the RP2350 bootloader drive")

    def _port_after(self) -> str:
        if self.port:
            return self.port
        ports = self._wait_for(self._find_ports, self.port_timeout,
                               "a Raspberry Pi serial port")
        if len(ports) > 1:
            raise FlashError("more than one Raspberry Pi serial port (%s); pass -r"
                             % ", ".join(ports))
        return ports[0]

    def _try_open(self, port: str) -> Optional[PicoSht30]:
        try:
            return self._open(port)
        except BenchToolsError:
            return None

    def _verify(self, result: FlashResult, image: Uf2Image,
                expect_version: Optional[str]) -> None:
        result.port = self._port_after()
        thermometer = self._wait_for(lambda: self._try_open(result.port), self.port_timeout,
                                     "the thermometer to answer on %s" % result.port)
        try:
            info = thermometer.firmware_info()
        finally:
            thermometer.close()
        result.after = info

        result.checks["title"] = {"expected": TITLE, "actual": info.title,
                                  "ok": info.title == TITLE}
        if expect_version:
            result.checks["version"] = {"expected": expect_version, "actual": info.version,
                                        "ok": info.version == expect_version}
        if image.built:
            result.checks["built"] = {"expected": image.built, "actual": info.built,
                                      "ok": info.built == image.built}
        else:
            result.notes.append("the image carries no single ISO build date, "
                                "so the build was not compared")


# ---------------------------------------------------------------------------
class SimulatedRp2350:
    """A Pico 2 for ``sim://``: the thermometer firmware, and its bootloader.

    ``bootsel`` (or a 1200-baud touch) makes a temporary directory appear as
    the ``RP2350`` drive. A UF2 copied there "boots": the drive goes, and the
    simulated firmware takes the image's build date - and title, if it is not
    the thermometer - so that verification sees what it would on a real board.
    """

    PORT = "sim://"

    def __init__(self, in_bootloader: bool = False) -> None:
        self.firmware = SimulatedPicoSht30()
        self.firmware.on_bootloader = self._enter_bootloader
        self._root = tempfile.mkdtemp(prefix="rp2350-")
        self.drive = os.path.join(self._root, "RP2350")
        self.in_bootloader = False
        self.flashes = 0
        if in_bootloader:
            self._enter_bootloader()

    def _enter_bootloader(self) -> None:
        os.makedirs(self.drive, exist_ok=True)
        with open(os.path.join(self.drive, INFO_FILE), "w", encoding="ascii") as handle:
            handle.write("UF2 Bootloader v1.0\nModel: Raspberry Pi RP2350\nBoard-ID: RP2350\n")
        self.in_bootloader = True

    def find_drives(self) -> List[str]:
        """The bootloader drive, while the board is in its bootloader."""
        return find_bootloader_drives([self.drive])

    def find_ports(self) -> List[str]:
        """The serial port, while the firmware runs."""
        return [] if self.in_bootloader else [self.PORT]

    def open_thermometer(self, _port: str) -> PicoSht30:
        """Connect to the running firmware."""
        if self.in_bootloader:
            raise FlashError("the simulated Pico is in its bootloader: no serial port")
        thermometer = PicoSht30(MockTransport(responder=self.firmware))
        thermometer.initialise()
        return thermometer

    def touch(self, _port: str) -> None:
        """The 1200-baud reset; the simulated board reports nothing."""
        self._enter_bootloader()

    def copy(self, image: Uf2Image, drive: str) -> str:
        """Take the image, then reboot into it."""
        target = copy_image(image, drive)
        self.flashes += 1
        self.firmware.built = image.built or self.firmware.built
        if not image.is_thermometer:
            self.firmware.title = "unknown"
        shutil.rmtree(self.drive, ignore_errors=True)
        self.in_bootloader = False
        return target

    def flasher(self, **kwargs) -> PicoFlasher:
        """A :class:`PicoFlasher` wired to this board; *kwargs* override any seam."""
        seams = {
            "port": self.PORT,
            "find_drives": self.find_drives,
            "find_ports": self.find_ports,
            "open_thermometer": self.open_thermometer,
            "touch": self.touch,
            "copy": self.copy,
        }
        seams.update(kwargs)
        return PicoFlasher(**seams)

    def close(self) -> None:
        """Remove the temporary drive."""
        shutil.rmtree(self._root, ignore_errors=True)
