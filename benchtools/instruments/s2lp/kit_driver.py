"""The S2-LP kit driver's side of the ETB kit firmware (#84).

:class:`KitFirmwareMixin` is not used alone: :class:`~.s2lp.S2lpDevkit`
provides the transport, the session, the board clock and the register access,
and :class:`~.traffic.TrafficMixin` the stream's bookkeeping. It holds what
differs on the ETB firmware: choosing the session on connecting, identifying
the board, and a stream in which the board re-arms the radio itself. The line
protocol is :mod:`.kit_firmware`'s.

Traces to: S2LP-FR-098 .. S2LP-FR-100, S2LP-DD-KITHOST.
"""

from __future__ import annotations

import time
from typing import Dict, Iterator, List, Optional

from ...core.errors import InstrumentError
from ...core.instrument import InstrumentIdentity
from .constants import MANUFACTURER, MODEL
from .kit_firmware import KIT_PROTOCOL, KitRecord, KitSession, probe
from .packets import Packet
from .session import S2lpSession

__all__ = ["KitFirmwareMixin"]

#: The register that holds PQI, which reads 0 unless the PQI check is on.
_PQI_REGISTER = "LINK_QUALIF2"


class KitFirmwareMixin:
    """Connecting to, identifying and receiving on the ETB kit firmware."""

    # ------------------------------------------------------------------
    # Connecting
    # ------------------------------------------------------------------
    def _choose_session(self) -> None:
        """Talk to the board through the session its firmware needs.

        A board left receiving by the ETB firmware is stopped, so connecting
        leaves nothing running; nothing else is changed.
        """
        choice = self._facts["firmware"]
        if choice == "st":
            return
        identity = probe(self._session)
        if identity is None:
            if choice == "kit":
                raise InstrumentError(
                    "the board did not answer id as the ETB kit firmware does; "
                    "it may be running ST's CLI firmware (firmware=\"st\")")
            if isinstance(self._session, KitSession):
                session = S2lpSession(self._transport, timeout=self._session.timeout)
                session.adopt_log(self._session)
                self._session = session
                self._adopt(session)
            return
        if identity.protocol != KIT_PROTOCOL:
            raise InstrumentError(
                "the board runs %s %s with line protocol %d; this driver speaks %d"
                % (identity.name, identity.version, identity.protocol, KIT_PROTOCOL))
        self._session = KitSession(self._session, identity)
        self._adopt(self._session)
        if self._session.stat().get("running"):
            self._session.note("the board was left receiving: stopping it")
            self._session.rx_stop()

    @property
    def kit_firmware(self) -> bool:
        """Whether the board runs the ETB kit firmware rather than ST's."""
        return isinstance(self._session, KitSession)

    @property
    def kit_counters(self) -> Dict[str, int]:
        """The kit firmware's counters from the last ``rx stop``.

        ``frames``, ``rejects``, ``overflows`` (records the board could not
        queue) and ``deaf_max_us`` (the longest time from a reception's
        interrupt to the radio armed again). Empty on ST's firmware, or before
        a stream has ended.
        """
        session = self._session
        return dict(session.last_counters) if isinstance(session, KitSession) else {}

    def _shutdown(self, held: bool) -> None:
        """Hold the radio in shutdown, or release it, on either firmware."""
        if isinstance(self._session, KitSession):
            self._session.shutdown(held)
        else:
            self._session.execute("SdkEvalSdn", 1 if held else 0)

    def _read_kit_identity(self, session: KitSession) -> InstrumentIdentity:
        """Identify the ETB kit firmware and the radio.

        The radio's part number and version are read from DEVICE_INFO1/0. The
        crystal, ST's library version and the board EEPROM are not available:
        the first two are ST's firmware's, and the EEPROM is not read by the
        ETB firmware. So a board named by the caller is not checked here.
        """
        part, silicon = self.read_registers("DEVICE_INFO1", 2)
        if part != 0x03:
            raise InstrumentError(
                "the radio reports part number 0x%02X; an S2-LP is 0x03" % part)
        identity = session.identity
        firmware = "%s %s" % (identity.name, identity.version)
        self._facts.update(library="", silicon=silicon, xtal_hz=0, eeprom=None)
        raw = "%s,%s,S2-LP 0x%02X,%s,protocol %d" % (
            MANUFACTURER, self._board or MODEL, silicon, firmware, identity.protocol)
        return InstrumentIdentity(raw=raw, manufacturer=MANUFACTURER,
                                  model=self._board or MODEL, serial_number="",
                                  firmware=firmware)

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------
    def _stream_kit(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
            self, session: KitSession, decoder, count, timeout, until,
            registers) -> Iterator[Packet]:
        """Receive on the ETB kit firmware: it re-arms the radio itself.

        A gap in the records' sequence numbers is a record the board could not
        queue; the next packet carries how many in ``extra["lost_before"]``,
        and the count is noted in the session log. However the stream ends,
        the board is stopped and its counters kept (:attr:`kit_counters`).
        Records the caller did not take are set aside, as a batch stream's
        are, for ``dut_frame(since_last=True)`` (#293).
        """
        names = [register.name for register in registers]
        restore_qi = self._enable_pqi() if _PQI_REGISTER in names else None
        started = time.monotonic()
        received = 0
        expected_seq = [0, 0]           # the next number, and the lost so far
        # Set before the start, so a start that fails still stops the board
        # and puts QI back: an idle board answers "rx stop" (#348 review).
        running = True
        try:
            session.rx_start([register.address for register in registers])
            while count is None or received < count:
                remaining = self._remaining(started, timeout)
                if (remaining is not None and remaining <= 0) or (until is not None and until()):
                    break
                record = session.next_record(remaining, cancel=until)
                if record is None:
                    break
                received += 1
                yield self._record(self._kit_packet(record, names, decoder, expected_seq))
            running = False
            packets, stopped_at = self._stop_kit(session, names, decoder, expected_seq,
                                                 restore_qi)
            try:
                while packets and (count is None or received < count):
                    received += 1
                    yield self._record(packets.pop(0))
            finally:
                self._put_aside(packets, stopped_at)
        finally:
            if running:
                self._put_aside(*self._stop_kit(session, names, decoder, expected_seq,
                                                restore_qi))

    def _stop_kit(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, session: KitSession, names: List[str], decoder,
            expected_seq: List[int], restore_qi: Optional[int]):
        """Stop the kit receiving; the packets it still held, and the command count after.

        QI is put back before the count is taken, so the count dates from the
        end of the stream. A stop the board does not answer leaves it
        receiving, and a receiving board refuses register writes, so QI cannot
        be put back then: that is noted in the log, the error raised, and
        :meth:`stop` tries the stop again (#348 review).
        Records the board could not queue after the last one it sent show in
        no gap, only in the ``overflows`` counter: they are noted.
        """
        try:
            leftover, counters = session.rx_stop()
        except Exception:
            if restore_qi is not None:
                session.note("the board did not stop: QI left with the PQI check on "
                             "(0x%02X to restore)" % restore_qi)
            raise
        if restore_qi is not None:
            self.write_register("QI", restore_qi)
        session.note("kit receive ended: %s" % " ".join(
            "%s=%d" % item for item in sorted(counters.items())))
        packets = [self._kit_packet(record, names, decoder, expected_seq) for record in leftover]
        unseen = counters.get("overflows", 0) - expected_seq[1]
        if unseen > 0:
            session.note("%d record(s) lost after the last one sent" % unseen)
        return packets, session.commands_sent

    def _kit_packet(self, record: KitRecord, names: List[str], decoder,
                    expected_seq: List[int]) -> Packet:
        """A kit firmware record as a packet: registers read, decoded."""
        packet = Packet(direction="rx", data=record.payload if record.kind == "f" else b"",
                        board_time_us=self._clock.unwrap(record.time_us),
                        error=0 if record.kind == "f" else (record.irq or 1))
        packet.extra["seq"] = record.seq
        if record.kind == "r":
            packet.extra["irq_status"] = record.irq
        lost = record.seq - expected_seq[0]
        if lost > 0:
            packet.extra["lost_before"] = lost
            expected_seq[1] += lost
            self._session.note("%d record(s) lost before seq %d" % (lost, record.seq))
        expected_seq[0] = record.seq + 1
        for name, value in zip(names, record.registers):
            packet.registers[name] = value
        self._interpret_registers(packet)
        self._annotate(packet, [], decoder)
        return packet
