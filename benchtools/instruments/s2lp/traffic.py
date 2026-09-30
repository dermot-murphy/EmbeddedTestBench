"""Sending and receiving, for the S2-LP development kit driver.

Split from :mod:`s2lp` so that the driver's register and configuration
handling and its traffic can each be read on their own. :class:`TrafficMixin`
is not used alone: :class:`~.s2lp.S2lpDevkit` provides the session, the board
clock, the packet log and the register access it relies on.

Three things matter on a real kit, and each was found on one:

* **The radio's interrupt has to be routed first.** ST's send and receive
  commands wait for an interrupt that, out of reset, reaches nothing.
  :meth:`TrafficMixin.prepare_traffic` routes it, once per session.
* **The packet handler has to be set up.** Out of reset the radio's TX source
  is a PN9 test pattern, so a send transmits that indefinitely and never the
  payload. A send is refused until TXSOURCE is the FIFO.
* **The packet length has to match what is sent.** The radio sends exactly
  PCKTLEN bytes; given fewer it waits in TX for the rest, indefinitely.
* **Nothing the firmware starts ends by itself.** A receive waits for as long
  as it takes, so every wait here is the host's, and ends with a stop.

Traces to: S2LP-FR-040 .. S2LP-FR-046, S2LP-DD-TRAFFIC.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Union

from ...analysis.samples import SampleSet
from ...core.errors import (
    ConfigurationError,
    InstrumentError,
    MeasurementError,
    TransportTimeoutError,
)
from .constants import MAX_PAYLOAD, Strobe
from . import registers as reg
from .kepler import decode_kepler_frame
from .packets import Capture, Packet, packet_from_reply, rssi_dbm_from_register
from .preamble import PreambleMeasurement, check_preamble
from .session import STOP_ACK

__all__ = ["TrafficMixin", "IRQ_GPIO", "TRAFFIC_IRQS", "FRAME_REGISTERS", "ANY_LENGTH"]

#: Registers a stream reads after each frame by default: AFC correction, PQI,
#: carrier sense with SQI, and the RSSI level. They are read in one command.
FRAME_REGISTERS = ("AFC_CORR", "LINK_QUALIF2", "LINK_QUALIF1", "RSSI_LEVEL")

#: ``S2LPGetNBytes`` length that means "one packet, whatever its length": ST's
#: receive takes the packet-by-packet path, ending on data-ready, for 0xFFFF.
ANY_LENGTH = 0xFFFF

#: PQI's register. Reading it needs the PQI check on (QI.PQI_TH > 0): with the
#: check off it reads 0 whatever was sent (#89).
PQI_REGISTER = "LINK_QUALIF2"

#: The PQI threshold set when PQI is wanted and the check is off.
PQI_THRESHOLD = 1

#: ``S2LPGetNBytesBatch`` count for "until stopped", as ST's GUI sends it.
BATCH_FOREVER = 0xFFFFFFFF

#: A wait with no timeout, in seconds: a year.
FOREVER_S = 365 * 86400.0

#: The S2-LP GPIO the board takes its interrupt from. GPIO3 worked on a
#: NUCLEO-L053R8 kit on 2026-09-27. GPIO0 did not, but the radio was stuck in
#: TX at the time, so whether GPIO0 is wired is not established.
IRQ_GPIO = 3

#: ``S2LPGpioInit`` arguments: digital output, low power; the nIRQ signal. The
#: mode is the GPIO_MODE register field's own encoding (1 input, 2 output low
#: power, 3 output high power). The CLI's help text numbers them one lower,
#: and following it makes the pin an input: on a kit that read back as
#: GPIO3_CONF = 0x01 and no interrupt ever reached the board.
GPIO_OUTPUT_LOW_POWER = 2
GPIO_NIRQ = 0

#: PCKTCTRL1.TXSOURCE for "send what is in the FIFO". Its power-on value is 3,
#: a PN9 test pattern, which the radio sends indefinitely while the FIFO waits.
TX_SOURCE_FIFO = 0

#: The interrupts ST's send and receive loops wait for: RX data ready, RX data
#: discarded, TX data sent, CRC error, valid sync and RX timeout. The FIFO
#: thresholds they need they enable themselves.
TRAFFIC_IRQS = 0x00000001 | 0x00000002 | 0x00000004 | 0x00000010 | 0x00002000 | 0x10000000


class TrafficMixin:
    """Transmit, receive and capture. See the module docstring."""

    _traffic_ready = False
    _receive_ready = False

    def prepare_traffic(self, gpio: int = IRQ_GPIO) -> None:
        """Route the radio's interrupt to the board, so traffic can complete.

        ST's send and receive commands wait for an interrupt from the radio,
        and out of reset nothing routes one to the board. This puts the radio's
        nIRQ on *gpio*, enables the board's interrupt input on that line, and
        unmasks the interrupts the firmware waits for - then reads the board's
        pin, which must be high: nIRQ is active low, and a line that reads low
        here is not connected, or is already asserted, and would never deliver
        the edge the firmware waits for. It writes the GPIO and IRQ_MASK
        registers, so it runs once per session, on the first send or receive,
        not on connecting.

        :raises InstrumentError: if the line does not read high at the board.
        """
        self._session.execute("S2LPGpioInit", int(gpio), GPIO_OUTPUT_LOW_POWER, GPIO_NIRQ)
        self._session.execute("S2LPIrq", TRAFFIC_IRQS, 1)
        self._session.execute("S2LPIrqGetStatus")          # reading clears it
        self._session.execute("S2MGpioIrqConfiguration", int(gpio), 1)
        self._check_interrupt_line(gpio, "after routing")
        self._traffic_ready = True

    def clear_interrupt(self, gpio: int = IRQ_GPIO) -> None:
        """Clear the radio's pending interrupts, and confirm its line is high again.

        Stopping a receive part-way leaves interrupts pending in IRQ_STATUS,
        and while they are pending nIRQ stays asserted. The next send or
        receive then waits for an edge that never comes, and hears nothing
        (seen on the kit, #99: IRQ_STATUS ``09607003`` after a stop). Reading
        IRQ_STATUS clears it. Done before every send and receive after the
        first; the first is covered by :meth:`prepare_traffic`.

        :raises InstrumentError: if the line still reads low.
        """
        self._session.execute("S2LPIrqGetStatus")          # reading clears it
        self._check_interrupt_line(gpio, "after clearing IRQ_STATUS")

    def _check_interrupt_line(self, gpio: int, when: str) -> None:
        """Raise unless the board reads the radio's nIRQ line high."""
        level = self._session.execute("S2MGpioGetValue", int(gpio)).hex_number("value")
        if level != 1:
            raise InstrumentError(
                "the radio's interrupt line (GPIO%d) reads %d at the board %s; "
                "it should idle high. Traffic would wait forever for an "
                "interrupt that cannot arrive." % (gpio, level, when)
            )

    def _check_tx_source(self) -> None:
        """Refuse to send while the radio's TX source is not its FIFO."""
        source = self.read_field("PCKTCTRL1", "TXSOURCE")
        if source != TX_SOURCE_FIFO:
            raise ConfigurationError(
                "PCKTCTRL1.TXSOURCE is %d, not 0 (the FIFO). 3 is a PN9 test "
                "pattern and the radio's power-on value: it would transmit that "
                "indefinitely and never send the payload. Set up the packet "
                "handler first (configure_packets, or a register file)." % source
            )

    def _ready_for_traffic(self) -> None:
        if not self._traffic_ready:
            self.prepare_traffic()
        else:
            self.clear_interrupt()

    def prepare_receive(self) -> None:
        """Set up receiving the way ST's S2-LP DK GUI does before it listens.

        Read from the kit while the GUI was receiving (#87): it makes the RX
        timeout infinite (``S2LPTimerSetRxTimeoutUs 0``, which ST's firmware
        implements as ``SET_INFINITE_RX_TIMEOUT``) and turns the low-power
        receive off (``S2LPGetBatchLP 0``). Out of reset TIMERS5 is 1, a finite
        RX timer. Done once per session, on the first receive.
        """
        self._ready_for_traffic()
        self._session.execute("S2LPTimerSetRxTimeoutUs", 0)
        self._session.execute("S2LPGetBatchLP", 0)
        self._receive_ready = True

    def _ready_for_receive(self) -> None:
        if not self._receive_ready:
            self.prepare_receive()
        else:
            self.clear_interrupt()

    def transmit(self, data: Union[bytes, str], note: str = "",
                 timeout: Optional[float] = None) -> Packet:
        """Send one packet, and record it.

        The packet handler's length is set to the payload's first, if it
        differs: the radio sends exactly that many bytes, and given fewer it
        waits in TX for the rest. The firmware acknowledges after the radio has
        finished sending; the acknowledgement carries no timer, so the packet
        has a host time only.

        :raises ConfigurationError: if the radio's TX source is not its FIFO.
        :raises InstrumentError: if the radio never reports the packet sent.
            The send is stopped and the radio taken out of TX first, so the
            board is usable afterwards.
        """
        payload = self._payload(data)
        self._ready_for_traffic()
        self._check_tx_source()
        if len(payload) != self._payload_length:
            self.set_payload_length(len(payload))
        self._session.send("S2LPSendNBytes", payload)
        try:
            self._session.read_reply(
                timeout=timeout if timeout is not None else self._session.timeout,
                command="S2LPSendNBytes", expect="S2LPSendNBytes")
        except TransportTimeoutError:
            self._session.stop()
            self.strobe(Strobe.ABORT)
            self.strobe(Strobe.FLUSH_TX_FIFO)
            raise InstrumentError(
                "the radio did not report the packet sent. The send was "
                "stopped and the radio aborted. Check that nothing has "
                "re-routed its interrupt (prepare_traffic)."
            ) from None
        return self._record(Packet(direction="tx", data=payload, note=note))

    @staticmethod
    def _payload(data: Union[bytes, str]) -> bytes:
        """A payload the firmware's command can carry, or a clear refusal."""
        payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        if not payload:
            raise ConfigurationError("there is no such thing as an empty transmission")
        if len(payload) > MAX_PAYLOAD:
            raise ConfigurationError(
                "%d bytes is more than the firmware's command carries (%d). "
                "Send it in parts." % (len(payload), MAX_PAYLOAD)
            )
        return payload

    def transmit_batch(
        self, data: Union[bytes, str], count: int, interval_ms: int = 100
    ) -> List[Packet]:
        """Send the same packet *count* times, *interval_ms* apart.

        The timing is the board's, not the host's: the loop runs in the firmware,
        so the interval is not at the mercy of the USB link. The firmware
        acknowledges each packet as it goes and the batch at the end, so each
        packet is recorded when its own acknowledgement arrives.
        """
        payload = self._payload(data)
        self._ready_for_traffic()
        self._check_tx_source()
        if len(payload) != self._payload_length:
            self.set_payload_length(len(payload))
        self._session.send("S2LPSendNBytesBatch", int(interval_ms), int(count), payload)
        timeout = max(self._session.timeout, interval_ms / 1000.0 + 5.0)
        sent: List[Packet] = []
        while True:
            reply = self._session.read_reply(timeout=timeout, command="S2LPSendNBytesBatch")
            if reply.command == "S2LPSendNBytes":
                sent.append(self._record(Packet(
                    direction="tx", data=payload,
                    note="batch %d of %d" % (len(sent) + 1, count))))
            elif reply.command in ("S2LPSendNBytesBatch", STOP_ACK):
                return sent

    def receive(
        self, length: Optional[int] = None, timeout: Optional[float] = None
    ) -> Optional[Packet]:
        """Arm the radio and wait for one packet of *length* bytes.

        ST's firmware has no time limit of its own, so when *timeout* runs out
        the receive is stopped on the board; otherwise the board would still be
        listening and the next command would be lost.

        :returns: The packet, or ``None`` if none arrived or the firmware
            rejected it (a rejection is still logged). ``None`` means nothing
            was heard *while listening*, not that the air was quiet.
        """
        wanted = int(length or self._payload_length or self.payload_length)
        self._ready_for_receive()
        self._session.send("S2LPGetNBytes", wanted)
        try:
            reply = self._session.read_reply(
                timeout=timeout if timeout is not None else self._session.timeout,
                command="S2LPGetNBytes",
            )
        except TransportTimeoutError:
            replies = self._session.stop()
            reply = next((r for r in replies if r.command == "S2LPGetNBytes"), None)
            if reply is None:
                return None
        packet = packet_from_reply(reply, self._clock)
        if packet is None:
            return None
        self._record(packet)
        return packet if packet.ok else None

    #: How :meth:`stream` can receive.
    STREAM_MODES = ("batch", "polled")

    def stream(  # pylint: disable=too-many-arguments
        self,
        decoder: Optional[Callable[[bytes], Dict[str, Any]]] = None,
        *,
        count: Optional[int] = None,
        timeout: Optional[float] = None,
        until: Optional[Callable[[], bool]] = None,
        mode: str = "batch",
        registers: Optional[Sequence[str]] = None,
    ) -> Iterator[Packet]:
        """Receive frames for as long as asked, and yield each as it arrives.

        Each frame is decoded with *decoder* when one is given, written to the
        packet log, and then yielded. A rejected reception (CRC, filter) is
        yielded too, with its error code; a payload the decoder cannot read is
        yielded with ``decode_error`` set and its raw bytes intact. However the
        stream ends - count, time, *until*, or the caller simply stopping
        iterating - the board is stopped.

        :param mode: How to receive.

            * ``"batch"`` (the default) - start ST's receive loop once
              (``S2LPGetNBytesBatch``), as ST's own GUI does, with
              ``S2LPGetNBytesReportAll`` on so the board re-arms the radio
              before printing each report. No host round trip falls in a gap,
              so close repeats are caught. Each frame carries the firmware's
              fields: RSSI, AGC word, CRC, addresses, sequence number, length.
              Registers cannot be read per frame while the loop runs.
            * ``"polled"`` - one ``S2LPGetNBytes`` per frame, then *registers*
              read straight after it (by default AFC correction, PQI, SQI with
              carrier sense, and RSSI, which the firmware does not report). The
              radio is deaf for the register read and a command round trip
              after every frame: on the bench, gaps under about 105 ms were
              missed.
        :param registers: Polled mode only: the registers to read after each
            frame.
        :param count: Stop after this many receptions.
        :param timeout: Stop after this many seconds.
        :param until: Stop when this returns true; it is checked while waiting,
            so a stream can be ended from another thread.
        :raises ConfigurationError: for an unknown mode, or registers asked
            for in batch mode.
        """
        if mode not in self.STREAM_MODES:
            raise ConfigurationError(
                "%r is not a stream mode; they are %s" % (mode, ", ".join(self.STREAM_MODES)))
        if mode == "batch" and registers:
            raise ConfigurationError(
                "registers cannot be read per frame while ST's receive loop runs; "
                "use mode=\"polled\" for them, at the cost of missing close frames")
        self._ready_for_receive()
        if mode == "batch":
            return self._stream_batch(decoder, count, timeout, until)
        return self._stream_polled(decoder, count, timeout, until,
                                   FRAME_REGISTERS if registers is None else registers)

    @staticmethod
    def _remaining(started: float, timeout: Optional[float]) -> Optional[float]:
        return None if timeout is None else timeout - (time.monotonic() - started)

    def _stream_batch(self, decoder, count, timeout, until) -> Iterator[Packet]:
        """ST's receive loop, reports read as they arrive."""
        started = time.monotonic()
        self._session.execute("S2LPGetNBytesReportAll", 1)
        self._session.send("S2LPGetNBytesBatch", 0, int(count) if count else BATCH_FOREVER)
        running = True
        received = 0
        try:
            while True:
                reply = self._next_batch_reply(started, timeout, until)
                if reply is None:
                    break                           # time is up, or until() said so
                if reply.command == "S2LPGetNBytesBatch":
                    running = False                 # the board ended the loop
                    return
                packet = self._frame_from(reply, decoder)
                if packet is None:
                    continue
                received += 1
                if count and received >= count:
                    running = not self._read_loop_end()
                yield self._record(packet)
                if not running:
                    return
            # Ended by the host: stop the board, and yield what arrived meanwhile.
            running = False
            for packet in self._stop_and_collect(decoder):
                yield self._record(packet)
        finally:
            if running:
                # The caller stopped iterating. Stop the board; anything that
                # arrived meanwhile still goes to the packet log.
                for packet in self._stop_and_collect(decoder):
                    self._record(packet)

    def _next_batch_reply(self, started: float, timeout: Optional[float],
                          until: Optional[Callable[[], bool]]):
        """The loop's next reply, or ``None`` when the host should end it."""
        remaining = self._remaining(started, timeout)
        if (remaining is not None and remaining <= 0) or (until is not None and until()):
            return None
        try:
            return self._session.read_reply(
                timeout=remaining if remaining is not None else FOREVER_S,
                command="S2LPGetNBytesBatch", cancel=until)
        except TransportTimeoutError:
            return None

    def _read_loop_end(self) -> bool:
        """Read the loop's closing reply after its last counted frame.

        Read before that frame is handed over, so a caller that stops there
        leaves nothing running and nothing unread.
        """
        try:
            self._session.read_reply(timeout=2.0, expect="S2LPGetNBytesBatch",
                                     command="S2LPGetNBytesBatch")
            return True
        except TransportTimeoutError:
            return False

    def _frame_from(self, reply, decoder) -> Optional[Packet]:
        packet = packet_from_reply(reply, self._clock)
        if packet is not None:
            self._annotate(packet, [], decoder)
        return packet

    def _stop_and_collect(self, decoder) -> List[Packet]:
        """Stop the board, and turn the reports that came with the stop into frames."""
        frames = (self._frame_from(reply, decoder) for reply in self._session.stop())
        return [packet for packet in frames if packet is not None]

    def _stream_polled(self, decoder, count, timeout, until, registers) -> Iterator[Packet]:
        """One receive per frame, with registers read after each.

        When PQI is among the registers and the radio's PQI check is off, the
        check is switched on for the stream and QI put back afterwards: with it
        off PQI reads 0, which would look like a result.
        """
        addresses = sorted(reg.lookup(name).address for name in registers)
        restore_qi = self._enable_pqi() if reg.lookup(PQI_REGISTER).address in addresses else None
        started = time.monotonic()
        received = 0
        try:
            while count is None or received < count:
                remaining = self._remaining(started, timeout)
                if (remaining is not None and remaining <= 0) or (until is not None and until()):
                    return
                self._session.send("S2LPGetNBytes", ANY_LENGTH)
                try:
                    reply = self._session.read_reply(
                        timeout=remaining if remaining is not None else FOREVER_S,
                        command="S2LPGetNBytes", cancel=until)
                except TransportTimeoutError:
                    replies = self._session.stop()
                    reply = next((r for r in replies if r.command == "S2LPGetNBytes"), None)
                    if reply is None:
                        return
                packet = packet_from_reply(reply, self._clock)
                if packet is None:
                    continue
                received += 1
                self._annotate(packet, addresses, decoder)
                yield self._record(packet)
        finally:
            if restore_qi is not None:
                self.write_register("QI", restore_qi)

    def _enable_pqi(self) -> Optional[int]:
        """Switch the PQI check on if it is off; return QI to restore, or None."""
        qi = self.read_register("QI")
        if reg.lookup("QI").field("PQI_TH").extract(qi):
            return None
        self.write_field("QI", "PQI_TH", PQI_THRESHOLD)
        return qi

    def measure_preamble(
        self,
        source: Optional[str] = None,
        count: Optional[int] = None,
        timeout: float = 120.0,
        decoder: Callable[[bytes], Dict[str, Any]] = decode_kepler_frame,
    ) -> Dict[str, PreambleMeasurement]:
        """Measure transmitters' preamble lengths from PQI, per source.

        Receives in polled mode - PQI is read after each frame - with the PQI
        check on. Frames are attributed by the decoder's ``sensor_id``.

        :param source: Only count frames from this source, e.g. ``"5C1712"``.
        :param count: Stop after this many frames from *source* (or from anyone).
        :returns: Source to its :class:`~.preamble.PreambleMeasurement`.
        """
        results: Dict[str, PreambleMeasurement] = {}
        frames = 0
        for packet in self.stream(decoder=decoder, timeout=timeout, mode="polled",
                                  registers=(PQI_REGISTER, "LINK_QUALIF1", "RSSI_LEVEL")):
            if not packet.ok:
                continue
            who = str((packet.decoded or {}).get("sensor_id", "unknown"))
            if source is not None and who != source:
                continue
            results.setdefault(who, PreambleMeasurement(who)).pqi.append(packet.extra["pqi"])
            frames += 1
            if count is not None and frames >= count:
                break
        return results

    def kepler_samples(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        field: str,
        source: Optional[str] = None,
        frame_type: Optional[str] = None,
        count: int = 5,
        timeout: float = 60.0,
        scale: float = 1.0,
        unit: str = "",
        decoder: Callable[[bytes], Dict[str, Any]] = decode_kepler_frame,
    ) -> SampleSet:
        """Take *field* from the next *count* frames *source* sends.

        A Kepler sensor sends each frame several times, and each reading here
        is one transmission, not one copy of it. The copies are told apart by
        their repeat number, which the decoder reads from wherever the frame
        type keeps it (byte 8, or byte 9 behind TWF's and CONFIG's permute
        control byte). A copy starts a new transmission when its repeat number
        is not higher than the last one's. The bytes cannot be compared
        instead: 5C1712 clears ALIVE_STATUS's "SI updated" bit after the first
        copy, so the copies of one ALIVE differ (#95). One case is counted as
        one transmission when it was two: only an early copy of one heard, then
        only later copies of the next.

        :param field: A key of the decoded frame, e.g. ``temperature_c``.
        :param source: Only frames from this sensor, e.g. ``"5C1712"``.
        :param frame_type: Only frames of this type, e.g. ``"ALIVE"``.
        :param timeout: Seconds to wait for all *count*. Fewer is returned
            rather than raised, with ``count`` saying how many came.
        :param scale: Multiplies each value.
        :raises MeasurementError: if a matching frame has no *field*, which is
            a specification naming the wrong field rather than a result.

        Traces to: S2LP-FR-072.
        """
        samples = SampleSet(name=field, unit=unit, requested=int(count))
        started = time.monotonic()
        last_repeat: Optional[int] = None
        for packet in self.stream(decoder=decoder, timeout=timeout,
                                  until=lambda: samples.count >= samples.requested):
            decoded = packet.decoded or {}
            if not packet.ok or not decoded:
                continue
            if source is not None and str(decoded.get("sensor_id")) != source:
                continue
            if frame_type is not None and decoded.get("type") != frame_type:
                continue
            repeat = (decoded.get("frame") or {}).get("repeat")
            same = repeat is not None and last_repeat is not None and repeat > last_repeat
            last_repeat = repeat
            if same:
                continue
            if field not in decoded:
                raise MeasurementError(
                    "a %s frame from %s has no field %r; it has %s"
                    % (decoded.get("type"), decoded.get("sensor_id"), field,
                       ", ".join(sorted(decoded))))
            samples.add(float(decoded[field]) * float(scale),
                        source=bytes(packet.data).hex(" ").upper(),
                        at=time.monotonic() - started)
            if samples.complete:
                break
        return samples

    def kepler_frame(
        self,
        frame_type: str,
        source: Optional[str] = None,
        timeout: float = 60.0,
        decoder: Callable[[bytes], Dict[str, Any]] = decode_kepler_frame,
    ) -> Dict[str, Any]:
        """The decode of the next *frame_type* frame *source* sends, whole.

        For a frame whose fields are compared with each other or with text -
        a VERSION frame's version string and SHA against ``RD VERSION`` and
        ``RD SHA`` (#102) - where :meth:`kepler_samples`, which takes one
        number from each of several frames, does not fit. The first copy heard
        is returned; the copies of one transmission carry the same fields.

        :param frame_type: The type, e.g. ``"VERSION"``.
        :param source: Only frames from this sensor, e.g. ``"5C1712"``.
        :returns: The decoded fields, plus ``raw``: the payload in hex.
        :raises MeasurementError: if no such frame arrives within *timeout*.

        Traces to: S2LP-FR-073.
        """
        for packet in self.stream(decoder=decoder, timeout=timeout):
            decoded = packet.decoded or {}
            if not packet.ok or decoded.get("type") != frame_type:
                continue
            if source is not None and str(decoded.get("sensor_id")) != source:
                continue
            frame = dict(decoded)
            frame["raw"] = bytes(packet.data).hex(" ").upper()
            return frame
        raise MeasurementError(
            "no %s frame%s in %g s"
            % (frame_type, "" if source is None else " from %s" % source, timeout))

    def check_preamble(self, expected_pairs: int, source: str, count: Optional[int] = None,
                       timeout: float = 120.0, tolerance_pairs: int = 2) -> Dict[str, Any]:
        """Measure *source*'s preamble and compare it with *expected_pairs*.

        :returns: The check as a dictionary: ``verdict`` (pass, fail or
            unmeasurable), ``passed``, ``max_pqi``, ``expected_pqi``,
            ``preamble_bits`` and the reason.
        """
        measured = self.measure_preamble(source=source, count=count, timeout=timeout)
        measurement = measured.get(source, PreambleMeasurement(source))
        return check_preamble(measurement, expected_pairs, tolerance_pairs).as_dict()

    def _annotate(self, packet: Packet, addresses: List[int],
                  decoder: Optional[Callable[[bytes], Dict[str, Any]]]) -> None:
        """Add the registers read after *packet*, and its decode."""
        if addresses:
            start = addresses[0]
            values = self.read_registers(start, addresses[-1] - start + 1)
            for address in addresses:
                packet.registers[reg.BY_ADDRESS[address].name] = values[address - start]
            regs = packet.registers
            if "RSSI_LEVEL" in regs:
                packet.rssi_dbm = rssi_dbm_from_register(regs["RSSI_LEVEL"])
            if "LINK_QUALIF2" in regs:
                packet.extra["pqi"] = regs["LINK_QUALIF2"]
            if "LINK_QUALIF1" in regs:
                packet.extra["sqi"] = regs["LINK_QUALIF1"] & 0x7F
                packet.extra["carrier_sense"] = regs["LINK_QUALIF1"] >> 7
            if "AFC_CORR" in regs:
                value = regs["AFC_CORR"]
                packet.extra["afc_corr"] = value - 256 if value & 0x80 else value
        if decoder is not None and packet.ok:
            try:
                packet.decoded = decoder(packet.data)
            except Exception as exc:  # pylint: disable=broad-except
                packet.decode_error = str(exc) or type(exc).__name__

    def capture(
        self,
        count: int = 10,
        timeout: float = 30.0,
        length: Optional[int] = None,
        continuous: bool = True,
        attempts: Optional[int] = None,
    ) -> Capture:
        """Receive up to *count* packets, and record every one.

        :param continuous: Let ST's batch loop re-arm the radio, with
            ``S2LPGetNBytesReportAll`` on so it re-arms *before* printing each
            report rather than after. Gaps remain (see
            :attr:`Capture.is_continuous`), but no USB round trip is in them.
            With ``continuous=False`` the host re-arms between packets.
        :param attempts: Polled capture only: how many times to arm the radio
            before giving up.
        """
        wanted = int(length or self._payload_length or self.payload_length)
        started = time.monotonic()
        capture = Capture(requested=int(count), rearm="firmware" if continuous else "host")
        if continuous:
            self._capture_batch(capture, started, timeout)
        else:
            self._capture_polled(capture, started, timeout, wanted, attempts)
        capture.duration_s = time.monotonic() - started
        return capture

    def _capture_batch(self, capture: Capture, started: float, timeout: float) -> None:
        """Let ST's batch loop receive, and read its reports as they come."""
        self._ready_for_receive()
        self._session.execute("S2LPGetNBytesReportAll", 1)
        self._session.send("S2LPGetNBytesBatch", 0, capture.requested)
        finished = False
        receptions = 0
        while not finished and time.monotonic() - started < timeout:
            try:
                replies = [self._session.read_reply(
                    timeout=max(0.01, timeout - (time.monotonic() - started)),
                    command="S2LPGetNBytesBatch")]
            except TransportTimeoutError:
                replies = self._session.stop()
                capture.stopped_early = True
                finished = True
            for reply in replies:
                if reply.command == "S2LPGetNBytesBatch":
                    finished = True
                    continue
                packet = packet_from_reply(reply, self._clock)
                if packet is None:
                    continue
                receptions += 1
                self._record(packet)
                (capture.packets if packet.ok else capture.rejected).append(packet)
        capture.gaps = max(0, receptions - 1)

    def _capture_polled(self, capture: Capture, started: float, timeout: float,
                        length: int, attempts: Optional[int]) -> None:
        """Arm the radio from the host once per packet."""
        count = capture.requested
        limit = int(attempts) if attempts else max(2 * count, count + 8)
        listens = 0
        while (capture.count < count and listens < limit
               and time.monotonic() - started < timeout):
            packet = self.receive(
                length=length,
                timeout=max(0.01, timeout - (time.monotonic() - started)))
            listens += 1
            if packet is not None:
                capture.packets.append(packet)
        # Every arm after the first is preceded by an interval in which the
        # radio was not listening. That is what a gap is.
        capture.gaps = max(0, listens - 1)
        capture.stopped_early = capture.count < count

    def stop(self) -> None:
        """End a capture or a batch transmission early."""
        self._session.stop()
