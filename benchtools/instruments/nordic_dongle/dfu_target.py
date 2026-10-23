"""A simulated Secure DFU bootloader, for the simulated dongle to update (#244).

It answers the Control Point as an nRF5 SDK 17 bootloader does - select,
create, CRC, execute - and keeps what it receives, so a test can check that a
package arrived whole. It does not decode an init packet: a refusal a real
bootloader would make after validating one (a wrong key, another board,
a downgrade) is configured with *refuse_init*, and the simulator returns it at
the init packet's execute, which is where the real one does.

Traces to: BLE-FR-121, BLE-DD-DFUSIM.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .dfu import ObjectType, Opcode, ResultCode

__all__ = ["SimulatedBootloader"]

#: The largest data object the bootloader accepts; the SDK's flash page.
DATA_OBJECT_MAX = 4096
#: The largest init packet it accepts.
COMMAND_OBJECT_MAX = 512


@dataclass
class SimulatedBootloader:  # pylint: disable=too-many-instance-attributes
    """A target in its bootloader.

    :param refuse_init: ``(result, extended)`` to answer the init packet's
        execute with, e.g. ``(0x05, None)`` for ``InvalidObject`` or
        ``(0x0B, 0x06)`` for the extended error ``HwVersionFailure``.
    :param refuse_firmware: The same, for the first firmware object's execute.
    :param corrupt: Report a CRC one off, as a link that lost a byte would.
    """

    refuse_init: Optional[Tuple[int, Optional[int]]] = None
    refuse_firmware: Optional[Tuple[int, Optional[int]]] = None
    corrupt: bool = False
    prn_supported: bool = False
    #: What arrived and was executed: init packets, and firmware images.
    init_packets: List[bytes] = field(default_factory=list)
    firmware: List[bytes] = field(default_factory=list)
    requests: List[bytes] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._kind = ObjectType.COMMAND
        self._command = b""
        self._data = b""
        self._object_size = 0
        self._object_start = 0
        self.packets = 0

    # ------------------------------------------------------------------
    def packet(self, data: bytes) -> None:
        """A Packet write: bytes of the current object."""
        self.packets += 1
        if self._kind is ObjectType.COMMAND:
            self._command += data
        else:
            self._data += data

    def control(self, request: bytes) -> bytes:
        """A Control Point write, and the notification that answers it."""
        self.requests.append(bytes(request))
        opcode = request[0]
        handler = {
            Opcode.SELECT: self._select,
            Opcode.CREATE: self._create,
            Opcode.CRC_GET: self._crc,
            Opcode.EXECUTE: self._execute,
            Opcode.RECEIPT_NOTIF_SET: self._prn,
        }.get(opcode)
        if handler is None:
            return self._answer(opcode, ResultCode.OP_CODE_NOT_SUPPORTED)
        return handler(request)

    # ------------------------------------------------------------------
    @staticmethod
    def _answer(opcode: int, code: int, payload: bytes = b"",
                extended: Optional[int] = None) -> bytes:
        tail = bytes([extended]) if extended is not None else payload
        return bytes([Opcode.RESPONSE, opcode, code]) + tail

    def _prn(self, request: bytes) -> bytes:
        if not self.prn_supported:
            return self._answer(request[0], ResultCode.OP_CODE_NOT_SUPPORTED)
        return self._answer(request[0], ResultCode.SUCCESS)

    def _select(self, request: bytes) -> bytes:
        kind = ObjectType(request[1])
        if kind is ObjectType.COMMAND:
            body = struct.pack("<III", COMMAND_OBJECT_MAX, len(self._command),
                               zlib.crc32(self._command) & 0xFFFFFFFF)
        else:
            body = struct.pack("<III", DATA_OBJECT_MAX, len(self._data),
                               zlib.crc32(self._data) & 0xFFFFFFFF)
        return self._answer(request[0], ResultCode.SUCCESS, body)

    def _create(self, request: bytes) -> bytes:
        kind = ObjectType(request[1])
        size = struct.unpack("<I", request[2:6])[0]
        limit = COMMAND_OBJECT_MAX if kind is ObjectType.COMMAND else DATA_OBJECT_MAX
        if size > limit:
            return self._answer(request[0], ResultCode.INSUFFICIENT_RESOURCES)
        self._kind = kind
        self._object_size = size
        if kind is ObjectType.COMMAND:
            self._command = b""
            self._data = b""
        self._object_start = len(self._data)
        return self._answer(request[0], ResultCode.SUCCESS)

    def _crc(self, request: bytes) -> bytes:
        received = self._command if self._kind is ObjectType.COMMAND else self._data
        crc = zlib.crc32(received) & 0xFFFFFFFF
        if self.corrupt:
            crc ^= 1
        return self._answer(request[0], ResultCode.SUCCESS,
                            struct.pack("<II", len(received), crc))

    def _execute(self, request: bytes) -> bytes:
        if self._kind is ObjectType.COMMAND:
            if self.refuse_init is not None:
                code, extended = self.refuse_init
                return self._answer(request[0], code, extended=extended)
            self.init_packets.append(self._command)
            return self._answer(request[0], ResultCode.SUCCESS)
        if self.refuse_firmware is not None and self._object_start == 0:
            code, extended = self.refuse_firmware
            return self._answer(request[0], code, extended=extended)
        if not self.firmware or self._object_start == 0:
            self.firmware.append(b"")
        self.firmware[-1] = self._data
        return self._answer(request[0], ResultCode.SUCCESS)
