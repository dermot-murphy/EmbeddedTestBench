"""Nordic Secure DFU over BLE: the host's half of a firmware update (#244).

The dongle carries bytes to a target in its bootloader - a Control Point
write that is answered by notification, and Packet writes that are not (BLE-
DD-DFU). This module runs the procedure over those two operations: for the
init packet and then the firmware, *select* the object type, *create* each
object, write it, check the target's CRC of everything received so far, and
*execute* it. It is Nordic's procedure (nRF5 SDK 17 ``nrf_dfu_req_handler``),
as ``nrfutil dfu ble`` runs it.

A refusal is a result, not an exception: a test of a bootloader asserts that
a wrongly signed package is refused with ``InvalidObject``, or a package for
another board with the extended error ``HwVersionFailure``. Only a target that
stops answering, or answers out of turn, raises.

Data lost on the link is sent again, as nrfutil does: each Packet Receipt
Notification is checked against what was sent, and an object whose receipt
or final CRC does not match is created and sent again, a bounded number of
times (#271). An nRF5 SDK 15.2 bootloader at the minimum ATT MTU dropped one
20-byte piece of 5C1712's first data object, and said so in its receipts.

Traces to: BLE-FR-121, BLE-DD-DFUHOST.
"""

from __future__ import annotations

import enum
import io
import json
import struct
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ...core.errors import ConfigurationError, InstrumentError

__all__ = [
    "DfuError",
    "DfuImage",
    "DfuResult",
    "ExtendedError",
    "ObjectType",
    "Opcode",
    "ResultCode",
    "SecureDfu",
    "load_package",
]


class Opcode(enum.IntEnum):
    """Control Point opcodes the procedure uses."""

    CREATE = 0x01
    RECEIPT_NOTIF_SET = 0x02
    CRC_GET = 0x03
    EXECUTE = 0x04
    SELECT = 0x06
    RESPONSE = 0x60


class ObjectType(enum.IntEnum):
    """What an object holds."""

    COMMAND = 0x01          # the init packet
    DATA = 0x02             # the firmware


class ResultCode(enum.IntEnum):
    """The third byte of every Control Point response."""

    INVALID = 0x00
    SUCCESS = 0x01
    OP_CODE_NOT_SUPPORTED = 0x02
    INVALID_PARAMETER = 0x03
    INSUFFICIENT_RESOURCES = 0x04
    INVALID_OBJECT = 0x05
    UNSUPPORTED_TYPE = 0x07
    OPERATION_NOT_PERMITTED = 0x08
    OPERATION_FAILED = 0x0A
    EXTENDED_ERROR = 0x0B

    @property
    def text(self) -> str:
        """The name a test compares with: ``Success``, ``InvalidObject``..."""
        return "".join(part.capitalize() for part in self.name.split("_")).replace(
            "OpCode", "Opcode")


class ExtendedError(enum.IntEnum):
    """The byte after ``EXTENDED_ERROR``: why a valid-looking object was refused."""

    NO_ERROR = 0x00
    INVALID_ERROR_CODE = 0x01
    WRONG_COMMAND_FORMAT = 0x02
    UNKNOWN_COMMAND = 0x03
    INIT_COMMAND_INVALID = 0x04
    FW_VERSION_FAILURE = 0x05
    HW_VERSION_FAILURE = 0x06
    SD_VERSION_FAILURE = 0x07
    SIGNATURE_MISSING = 0x08
    WRONG_HASH_TYPE = 0x09
    HASH_FAILED = 0x0A
    WRONG_SIGNATURE_TYPE = 0x0B
    VERIFICATION_FAILED = 0x0C
    INSUFFICIENT_SPACE = 0x0D

    @property
    def text(self) -> str:
        """``FwVersionFailure``, ``HwVersionFailure``, ``SdVersionFailure``..."""
        return "".join(part.capitalize() for part in self.name.split("_"))


class DfuError(InstrumentError):
    """The target stopped answering, or answered out of turn."""


@dataclass
class DfuImage:
    """One image of a package: its init packet and its firmware."""

    kind: str               # softdevice_bootloader, softdevice, bootloader, application
    init_packet: bytes
    firmware: bytes


@dataclass
class DfuResult:  # pylint: disable=too-many-instance-attributes
    """What a DFU attempt came to.

    :param result: The bootloader's verdict on the step that ended it, as text:
        ``Success`` when every image was executed.
    :param extended_error: With ``ExtendedError``, the reason as text, e.g.
        ``HwVersionFailure``; empty otherwise.
    :param stage: Where it ended: ``init`` (the init packet, where version,
        hardware and signature are checked), ``firmware``, or ``done``.
    """

    result: str = ""
    result_code: int = 0
    extended_error: str = ""
    extended_code: Optional[int] = None
    stage: str = ""
    image: str = ""
    images: List[str] = field(default_factory=list)
    bytes_sent: int = 0
    seconds: float = 0.0
    target: str = ""
    retries: int = 0

    @property
    def succeeded(self) -> bool:
        """True when every image was received and executed."""
        return self.result == ResultCode.SUCCESS.text and self.stage == "done"

    def as_dict(self) -> dict:
        """The result as plain data, for a report."""
        return {
            "result": self.result, "result_code": self.result_code,
            "extended_error": self.extended_error, "extended_code": self.extended_code,
            "stage": self.stage, "image": self.image, "images": list(self.images),
            "bytes_sent": self.bytes_sent, "seconds": self.seconds, "target": self.target,
            "retries": self.retries,
        }


#: The order nrfutil sends a package's images in.
IMAGE_ORDER = ("softdevice_bootloader", "softdevice", "bootloader", "application")


def load_package(path: str) -> List[DfuImage]:
    """Read a DFU package: the zip ``nrfutil pkg generate`` writes.

    :raises ConfigurationError: for a file that is not such a package.
    """
    try:
        with zipfile.ZipFile(path) as package:
            manifest = json.loads(package.read("manifest.json").decode("utf-8"))["manifest"]
            images = []
            for kind in IMAGE_ORDER:
                if kind in manifest:
                    entry = manifest[kind]
                    images.append(DfuImage(kind=kind,
                                           init_packet=package.read(entry["dat_file"]),
                                           firmware=package.read(entry["bin_file"])))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise ConfigurationError("%s is not a DFU package: %s" % (path, exc)) from exc
    if not images:
        raise ConfigurationError("%s holds no image to send" % path)
    return images


def package_from_bytes(data: bytes) -> List[DfuImage]:
    """:func:`load_package` for a package already in memory."""
    return load_package(io.BytesIO(data))  # type: ignore[arg-type]


#: Times an object is sent again after its data was found lost (#271).
DEFAULT_RETRIES = 3

#: A receipt: the response header, then the offset and the CRC, 32 bits each.
RECEIPT_LENGTH = 11


class _Lost(Exception):
    """The target did not receive an object as it was sent: send it again."""


class _Refused(Exception):
    """A step the bootloader answered with something other than success."""

    def __init__(self, code: int, extended: Optional[int]) -> None:
        super().__init__(code)
        self.code = code
        self.extended = extended


class SecureDfu:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runs Nordic Secure DFU over a Control Point and a Packet characteristic.

    :param control: Writes a Control Point request and returns the notified
        response, or raises if none came within its timeout.
    :param packet: Writes bytes to the Packet characteristic.
    :param chunk: Bytes per Packet write; an ATT MTU of 247 carries 244.
    :param prn: Packets between the bootloader's receipts, for flow control;
        0 for none. Without it, writes at a 7.5 ms interval outran a Kepler
        bootloader's 17 packet buffers and data was lost (#244). The dongle
        waits for each receipt itself.
    :param receipts: Returns the Control Point notifications that arrived
        since it was last called, so that each Packet Receipt Notification is
        checked; None to check only each object's final CRC.
    :param retries: Times an object is created and sent again after its data
        was found lost, before the transfer fails (#271).
    :param on_retry: Called with the reason before each retry, to log it.
    """

    def __init__(self, control: Callable[[bytes, float], bytes],  # pylint: disable=too-many-arguments,too-many-positional-arguments
                 packet: Callable[[bytes], None], chunk: int = 244,
                 execute_timeout: float = 30.0, prn: int = 8,
                 receipts: Optional[Callable[[], List[bytes]]] = None,
                 retries: int = DEFAULT_RETRIES,
                 on_retry: Optional[Callable[[str], None]] = None) -> None:
        if not 1 <= chunk <= 244:
            raise ConfigurationError("a Packet write carries 1 to 244 bytes, not %r" % chunk)
        if retries < 0:
            raise ConfigurationError("retries is 0 or more, not %r" % retries)
        self._control = control
        self._packet = packet
        self._chunk = int(chunk)
        self._execute_timeout = float(execute_timeout)
        self._prn = int(prn)
        self._receipts = receipts
        self._retries = int(retries)
        self._on_retry = on_retry
        self.bytes_sent = 0
        self.retries = 0

    # ------------------------------------------------------------------
    def send_image(self, image: DfuImage) -> Tuple[str, Optional[int], Optional[int]]:
        """Send one image.

        :returns: ``(stage, code, extended)``: ``("done", SUCCESS, None)`` when
            executed, else the stage the bootloader refused and its codes.
        :raises DfuError: if an object was still lost after every retry.
        """
        try:
            self._request(bytes([Opcode.RECEIPT_NOTIF_SET]) + struct.pack("<H", self._prn),
                          allow_unsupported=True)
            self._send_object(ObjectType.COMMAND, image.init_packet, 0)
        except _Refused as refusal:
            return "init", refusal.code, refusal.extended
        try:
            maximum = self._select(ObjectType.DATA)[0]
            for offset in range(0, len(image.firmware), maximum):
                self._send_object(ObjectType.DATA,
                                  image.firmware[offset:offset + maximum], offset,
                                  whole=image.firmware[:offset])
        except _Refused as refusal:
            return "firmware", refusal.code, refusal.extended
        return "done", ResultCode.SUCCESS, None

    # ------------------------------------------------------------------
    def _send_object(self, kind: ObjectType, data: bytes, offset: int,
                     whole: bytes = b"") -> None:
        """Send one object, again while its data is found lost, and execute it.

        Creating the object again makes the bootloader drop what it holds of
        it and start again from the end of the last executed object.
        """
        attempt = 0
        while True:
            try:
                self._write_object(kind, data, offset, whole)
                break
            except _Lost as lost:
                if attempt >= self._retries:
                    raise DfuError("%s; still lost after %d retr%s"
                                   % (lost, attempt, "y" if attempt == 1 else "ies")) from lost
                attempt += 1
                self.retries += 1
                if self._on_retry is not None:
                    self._on_retry("%s object at offset %d, retry %d of %d: %s"
                                   % (kind.name.lower(), offset, attempt, self._retries, lost))
        self._request(bytes([Opcode.EXECUTE]), timeout=self._execute_timeout)

    def _write_object(self, kind: ObjectType, data: bytes, offset: int, whole: bytes) -> None:
        """Create one object, write it, and check that the target received it.

        :raises _Lost: at the first receipt that does not match what was
            sent, or if the CRC of everything received does not.
        """
        if kind is ObjectType.COMMAND:
            self._select(kind)
        self._request(bytes([Opcode.CREATE, kind]) + struct.pack("<I", len(data)))
        self._take_receipts()
        sent = whole + data
        acknowledged = offset
        for start in range(0, len(data), self._chunk):
            piece = data[start:start + self._chunk]
            self._packet(piece)
            self.bytes_sent += len(piece)
            acknowledged = self._check_receipts(sent, offset + start + len(piece), acknowledged)
        received, crc = struct.unpack("<II", self._request(bytes([Opcode.CRC_GET]))[:8])
        expected = zlib.crc32(sent) & 0xFFFFFFFF
        if received != offset + len(data) or crc != expected:
            raise _Lost("the target received %d byte(s) with CRC 0x%08x; %d with CRC "
                        "0x%08x were sent" % (received, crc, offset + len(data), expected))

    def _take_receipts(self) -> List[bytes]:
        """The notifications since the last call; none without a source."""
        return self._receipts() if self._receipts is not None else []

    def _check_receipts(self, sent: bytes, end: int, acknowledged: int) -> int:
        """Check each receipt that arrived against the bytes *sent* so far.

        A receipt's offset must move past the last one's, and not past *end*,
        and its CRC must be that of the first offset bytes sent. Other
        notifications are ignored.

        :returns: The offset the last good receipt acknowledged.
        :raises _Lost: at the first receipt that does not match.
        """
        for notification in self._take_receipts():
            if (len(notification) < RECEIPT_LENGTH or notification[0] != Opcode.RESPONSE
                    or notification[1] != Opcode.CRC_GET):
                continue
            if notification[2] != ResultCode.SUCCESS:
                raise _Lost("a receipt reported result 0x%02x" % notification[2])
            received, crc = struct.unpack("<II", notification[3:RECEIPT_LENGTH])
            if not acknowledged < received <= end:
                raise _Lost("a receipt reported offset %d after offset %d, with %d sent"
                            % (received, acknowledged, end))
            expected = zlib.crc32(sent[:received]) & 0xFFFFFFFF
            if crc != expected:
                raise _Lost("a receipt at offset %d reported CRC 0x%08x; 0x%08x was sent"
                            % (received, crc, expected))
            acknowledged = received
        return acknowledged

    def _select(self, kind: ObjectType) -> Tuple[int, int, int]:
        """``(max_size, offset, crc)`` of the target's current object of *kind*."""
        payload = self._request(bytes([Opcode.SELECT, kind]))
        return struct.unpack("<III", payload[:12])

    def _request(self, request: bytes, timeout: float = 10.0,
                 allow_unsupported: bool = False) -> bytes:
        """Write a Control Point request; return the response's payload.

        :raises _Refused: if the bootloader answered with anything but success.
        :raises DfuError: if the response is malformed or answers another request.
        """
        response = self._control(request, timeout)
        if len(response) < 3 or response[0] != Opcode.RESPONSE or response[1] != request[0]:
            raise DfuError("the target answered %s to the request %s"
                           % (response.hex() or "nothing", request.hex()))
        code = response[2]
        if code == ResultCode.SUCCESS:
            return response[3:]
        if allow_unsupported and code == ResultCode.OP_CODE_NOT_SUPPORTED:
            return b""
        extended = response[3] if code == ResultCode.EXTENDED_ERROR and len(response) > 3 else None
        raise _Refused(code, extended)


def result_text(code: Optional[int], extended: Optional[int]) -> Tuple[str, str]:
    """``(result, extended_error)`` as text, for codes a bootloader returned."""
    try:
        result = ResultCode(code).text if code is not None else ""
    except ValueError:
        result = "Unknown(0x%02x)" % code
    if extended is None:
        return result, ""
    try:
        return result, ExtendedError(extended).text
    except ValueError:
        return result, "Unknown(0x%02x)" % extended


def run_images(dfu: SecureDfu, images: List[DfuImage],
               before_each: Callable[[DfuImage, int], None],
               after_each: Callable[[DfuImage, int], None]) -> DfuResult:
    """Send *images* in turn, calling *before_each* (connect) and *after_each*
    (disconnect) around each; stop at the first refusal."""
    started = time.monotonic()
    result = DfuResult(images=[image.kind for image in images])
    for index, image in enumerate(images):
        result.image = image.kind
        before_each(image, index)
        try:
            stage, code, extended = dfu.send_image(image)
        finally:
            after_each(image, index)
        result.stage = stage
        result.result_code = int(code)
        result.result, result.extended_error = result_text(code, extended)
        result.extended_code = extended
        if stage != "done":
            break
    result.bytes_sent = dfu.bytes_sent
    result.retries = dfu.retries
    result.seconds = time.monotonic() - started
    return result


#: The codes, by name, for a reader of a report.
RESULT_NAMES: Dict[int, str] = {code.value: code.text for code in ResultCode}
