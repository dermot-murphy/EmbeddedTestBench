"""SWO / ITM trace stream decoding.

The Instrumentation Trace Macrocell lets firmware write a value to one of 32
stimulus ports; the Serial Wire Output pin carries those writes off-chip with
timestamps. Unlike a breakpoint, this does not stop the core, so it is the only
method here that measures how long code takes when running *freely*.

Packet framing follows the ARMv7-M architecture reference manual, Appendix D
(ITM and DWT packet protocol). Implemented:

* Synchronisation packets (a run of zero bytes then ``0x80``).
* Overflow (``0x70``) - recorded, because a dropped packet invalidates the
  timestamps that follow and a silent loss would corrupt a measurement.
* Local timestamps, formats 1 and 2. These are **deltas**, not absolute.
* Software source packets - the instrumentation a test actually reads.
* Hardware source, global timestamp and extension packets - recognised and
  skipped, so an unexpected packet does not desynchronise the stream.

.. warning::
   Local timestamps count cycles of the trace clock *after* the TPIU prescaler,
   not necessarily core cycles. :class:`ItmDecoder` therefore takes a
   ``prescaler`` and the conversion is only as right as that value. The packet
   framing here is verified against synthesised streams; the timestamp scaling
   must be confirmed on a bench against a known interval before timing results
   from this method are trusted. See JLINK-OPEN-03.

Traces to: JLINK-FR-064, JLINK-DD-SWO.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

__all__ = ["ItmEvent", "ItmDecoder", "SwoStream"]

_LOG = logging.getLogger(__name__)

#: Overflow packet header.
_OVERFLOW = 0x70
#: Byte that ends a synchronisation run.
_SYNC_END = 0x80


@dataclass(frozen=True)
class ItmEvent:
    """One software-source write seen in the trace stream.

    :param port: ITM stimulus port the firmware wrote to (0-31).
    :param value: The value written.
    :param size: Width of the write in bytes.
    :param timestamp: Accumulated trace-clock ticks when it was seen, or
        ``None`` if no timestamp had arrived yet.
    :param after_overflow: ``True`` when an overflow was seen since the previous
        event, meaning packets were dropped and the timestamp cannot be trusted.
    """

    port: int
    value: int
    size: int
    timestamp: Optional[int] = None
    after_overflow: bool = False


class ItmDecoder:
    """Incremental decoder for an SWO byte stream.

    Fed bytes as they arrive; emits :class:`ItmEvent` objects for software
    source writes. Being incremental matters: SWO arrives in arbitrary chunks
    and a packet is routinely split across two reads.

    :param prescaler: Trace-clock prescaler, used to convert timestamp ticks to
        core cycles. See the module warning.
    """

    def __init__(self, prescaler: int = 1) -> None:
        if prescaler < 1:
            raise ValueError("prescaler must be at least 1, got %r" % (prescaler,))
        self.prescaler = int(prescaler)
        self._buffer = bytearray()
        self._timestamp = 0
        self._pending_overflow = False
        self._synchronised = True
        #: Number of overflow packets seen, i.e. how often trace data was lost.
        self.overflows = 0
        #: Every decoded event, in order.
        self.events: List[ItmEvent] = []

    # ------------------------------------------------------------------
    @property
    def timestamp_ticks(self) -> int:
        """Accumulated timestamp ticks."""
        return self._timestamp

    @property
    def timestamp_cycles(self) -> int:
        """Accumulated timestamp converted to core cycles by the prescaler."""
        return self._timestamp * self.prescaler

    def reset(self) -> None:
        """Discard all state, as at the start of a measurement."""
        self._buffer = bytearray()
        self._timestamp = 0
        self._pending_overflow = False
        self.overflows = 0
        self.events = []

    # ------------------------------------------------------------------
    def feed(self, data: bytes) -> List[ItmEvent]:
        """Decode *data* and return the events it completed.

        Bytes forming an incomplete packet are retained for the next call.
        """
        self._buffer += data
        produced: List[ItmEvent] = []
        while True:
            consumed, event = self._decode_one()
            if consumed == 0:
                break
            if event is not None:
                produced.append(event)
                self.events.append(event)
        return produced

    # ------------------------------------------------------------------
    def _decode_one(self):
        """Decode one packet from the front of the buffer.

        :returns: ``(bytes_consumed, event_or_None)``; ``(0, None)`` when the
            buffer does not yet hold a complete packet.
        """
        if not self._buffer:
            return 0, None
        header = self._buffer[0]

        # Synchronisation: a run of zeros terminated by 0x80.
        if header == 0x00:
            index = 0
            while index < len(self._buffer) and self._buffer[index] == 0x00:
                index += 1
            if index >= len(self._buffer):
                return 0, None                      # run may continue
            if self._buffer[index] == _SYNC_END:
                del self._buffer[: index + 1]
                self._synchronised = True
                return index + 1, None
            # Zeros not followed by 0x80: discard them and resynchronise.
            del self._buffer[:index]
            return index, None

        if header == _OVERFLOW:
            del self._buffer[:1]
            self.overflows += 1
            self._pending_overflow = True
            _LOG.warning("ITM overflow: trace data was lost")
            return 1, None

        # A packet is a source packet when the 2-bit size field, header[1:0], is
        # non-zero; size 00 identifies a protocol packet. Testing bit 0 alone -
        # an easy mistake - misclassifies every 2-byte source packet (size 10)
        # as protocol, silently dropping all 16-bit instrumentation.
        if header & 0x03 == 0:
            return self._decode_protocol(header)

        return self._decode_source(header)

    # ------------------------------------------------------------------
    def _decode_protocol(self, header: int):
        low_nibble = header & 0x0F

        # Local timestamp format 2: single byte, 0b0TTT0000, TS in bits 6:4.
        if low_nibble == 0x00 and header & 0x80 == 0:
            ticks = (header >> 4) & 0x07
            del self._buffer[:1]
            self._timestamp += ticks
            return 1, None

        # Local timestamp format 1: header 0b11xx0000, then 1-4 payload bytes
        # each carrying 7 bits, continuation flagged by bit 7.
        if low_nibble == 0x00 and header & 0xC0 == 0xC0:
            ticks = 0
            shift = 0
            index = 1
            while True:
                if index >= len(self._buffer):
                    return 0, None                  # payload incomplete
                byte = self._buffer[index]
                ticks |= (byte & 0x7F) << shift
                shift += 7
                index += 1
                if byte & 0x80 == 0 or shift >= 28:
                    break
            del self._buffer[:index]
            self._timestamp += ticks
            return index, None

        # Extension packet: bit 2 set, bit 0 clear. Payload continues while
        # bit 7 is set.
        if header & 0x0B == 0x08:
            index = 1
            if header & 0x80:
                while True:
                    if index >= len(self._buffer):
                        return 0, None
                    byte = self._buffer[index]
                    index += 1
                    if byte & 0x80 == 0:
                        break
            del self._buffer[:index]
            return index, None

        # Global timestamp packets (0x94, 0xB4) carry a continued payload.
        if header in (0x94, 0xB4):
            index = 1
            while True:
                if index >= len(self._buffer):
                    return 0, None
                byte = self._buffer[index]
                index += 1
                if byte & 0x80 == 0:
                    break
            del self._buffer[:index]
            return index, None

        # Unrecognised protocol packet: drop one byte and keep going rather than
        # abandoning the stream. A single bad byte should not end a trace.
        del self._buffer[:1]
        _LOG.debug("skipping unrecognised ITM protocol header 0x%02X", header)
        return 1, None

    def _decode_source(self, header: int):
        # header[1:0]: 01 = 1 byte, 10 = 2 bytes, 11 = 4 bytes.
        size = {1: 1, 2: 2, 3: 4}[header & 0x03]
        if len(self._buffer) < 1 + size:
            return 0, None                          # payload incomplete
        port = (header >> 3) & 0x1F
        is_hardware = bool(header & 0x04)
        payload = bytes(self._buffer[1 : 1 + size])
        del self._buffer[: 1 + size]
        value = int.from_bytes(payload, "little")
        if is_hardware:
            # DWT event, PC sample or similar. Recognised so the stream stays in
            # sync, but not surfaced: this decoder exists to read instrumentation.
            return 1 + size, None
        event = ItmEvent(
            port=port,
            value=value,
            size=size,
            timestamp=self._timestamp,
            after_overflow=self._pending_overflow,
        )
        self._pending_overflow = False
        return 1 + size, event

    # ------------------------------------------------------------------
    def events_on_port(self, port: int) -> List[ItmEvent]:
        """Every decoded event written to *port*."""
        return [event for event in self.events if event.port == port]

    @staticmethod
    def encode_software_event(port: int, value: int, size: int = 1) -> bytes:
        """Build a software source packet. Used by tests and the simulator."""
        if size not in (1, 2, 4):
            raise ValueError("size must be 1, 2 or 4, got %r" % (size,))
        size_code = {1: 1, 2: 2, 4: 3}[size]
        header = ((port & 0x1F) << 3) | size_code
        return bytes([header]) + int(value).to_bytes(size, "little")

    @staticmethod
    def encode_local_timestamp(ticks: int) -> bytes:
        """Build a local timestamp packet. Used by tests and the simulator."""
        if 1 <= ticks <= 6:
            return bytes([(ticks & 0x07) << 4])
        out = bytearray([0xC0])
        remaining = int(ticks)
        while True:
            byte = remaining & 0x7F
            remaining >>= 7
            if remaining:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                break
        return bytes(out)


class SwoStream:
    """Reads raw SWO bytes from the J-Link GDB Server and decodes them.

    The server republishes the trace stream on its SWO port (2332 by default).
    Reading it is the same shape as reading RTT: a non-blocking socket drained on
    demand, so no thread is needed and collection is deterministic.

    :param host: Host running the GDB Server.
    :param port: SWO port.
    :param prescaler: Trace clock prescaler, passed to the decoder.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 2332, prescaler: int = 1) -> None:
        self._host = host
        self._port = int(port)
        self.decoder = ItmDecoder(prescaler=prescaler)
        self._socket = None

    def open(self) -> None:
        """Connect to the SWO port."""
        import socket as _socket

        from ...core.errors import ConnectionFailedError

        if self._socket is not None:
            return
        try:
            self._socket = _socket.create_connection((self._host, self._port), timeout=5.0)
        except OSError as exc:
            raise ConnectionFailedError(
                "cannot reach SWO on %s:%d: %s. The GDB Server publishes SWO only "
                "after 'monitor swo start', and the SWO pin must be wired."
                % (self._host, self._port, exc)
            ) from exc
        self._socket.setblocking(False)

    def close(self) -> None:
        """Disconnect. Idempotent."""
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def poll(self) -> List[ItmEvent]:
        """Read whatever has arrived and return the events it completed."""
        import select as _select

        if self._socket is None:
            return []
        collected = bytearray()
        while True:
            try:
                readable, _, _ = _select.select([self._socket], [], [], 0)
            except (OSError, ValueError):  # pragma: no cover - socket closed
                break
            if not readable:
                break
            try:
                chunk = self._socket.recv(65536)
            except BlockingIOError:  # pragma: no cover
                break
            except OSError:  # pragma: no cover
                break
            if not chunk:
                break
            collected += chunk
        return self.decoder.feed(bytes(collected)) if collected else []

    def collect(self, port: int, count: int, timeout: float = 10.0) -> List[ItmEvent]:
        """Collect *count* events from stimulus *port*, or as many as arrive.

        :param timeout: Seconds to keep reading.
        """
        import time as _time

        deadline = _time.monotonic() + timeout
        found: List[ItmEvent] = []
        while len(found) < count and _time.monotonic() < deadline:
            for event in self.poll():
                if event.port == port:
                    found.append(event)
            if len(found) < count:
                _time.sleep(0.005)
        return found

    def __enter__(self) -> "SwoStream":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False
