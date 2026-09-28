"""A simulated S2-LP development kit, answering ST's CLI protocol.

The model is of a **register file with a radio attached to it**, not a set of
canned replies. Writing PCKTCTRL3 changes what ``S2LPGetPktFrmt`` answers;
strobing ``FLUSH_RX_FIFO`` empties the FIFO; a packet queued on the simulated
air is delivered to exactly one receive and is then gone. That is what makes
the tests above it worth running: a driver that writes to the wrong address, or
reads a register it never wrote, fails here rather than on the bench.

**The replies are the kit's, not ST's documentation.** Every reply shape here
was recorded from a NUCLEO-L053R8 kit running ST's CLI firmware (S2-LP library
1.3.5) on 2026-09-27, or, for the commands that could not be exercised without
a transmitter, taken from the ``responsePrintf`` format strings in ST's source
for that firmware. So the simulator echoes each command, names it in
parentheses, answers getters in a ``value`` tag written in hex, and ends with a
``>`` prompt that has no line end.

Behaviours modelled because they are the ones that mislead:

* **A receive waits for as long as it takes.** ``S2LPGetNBytes`` with nothing on
  the air sends nothing back at all, as the firmware does; only the stop
  character ends it.
* **A stop character sent to an idle board is not harmless.** It stays in the
  command buffer and turns the next command into ``no such command``.
* **Packets arriving while the radio is not armed are lost.** The simulated
  air holds them only while a receive is in progress, which is what makes the
  gap between polled receives visible in a test instead of only on the bench.
* **Send and receive wait for an interrupt nothing routes by default.** Until
  the radio's nIRQ is on GPIO3, the board is listening on that line, and the
  interrupt is unmasked, a send or receive never finishes - as on the kit.
* **A payload shorter than the packet length never finishes sending.** The
  radio waits in TX for the bytes it was told to expect.
* **Out of reset the radio sends a PN9 test pattern, not its FIFO.**
  PCKTCTRL1.TXSOURCE powers up as 3; until the packet handler is set up a send
  never finishes and the payload never goes.

Traces to: S2LP-FR-050, S2LP-DD-SIM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .constants import AFTER_SHUTDOWN_EXIT, DEFAULT_BOARD, FIFO_SIZE, Modulation, Strobe
from .registers import BY_ADDRESS, REGISTERS, lookup

__all__ = ["SimulatedS2lp"]

#: ST's receive error codes, from the firmware's source.
RX_TIMEOUT = 0x01
RX_CRC_ERROR = 0x02

#: Microseconds the simulated board clock advances per command.
_TICK_US = 1_000

#: The S2-LP GPIO the kit takes its interrupt from, and the interrupts that
#: complete a send and a receive.
IRQ_GPIO = 3
TX_DATA_SENT = 0x00000004
RX_DATA_READY = 0x00000001

#: Registers the receive path updates, by address.
_PQI, _SQI, _RSSI_LEVEL, _RX_LEN1, _RX_LEN0 = 0x9F, 0xA0, 0xA2, 0xA4, 0xA5


def _rssi_byte(dbm: float) -> int:
    """dBm to the RSSI_LEVEL register value: dBm = value / 2 - 146."""
    return max(0, min(255, int(round((float(dbm) + 146.0) * 2.0))))


def _list(values) -> str:
    """ST's ``0x%x`` list: two uppercase digits, comma separated."""
    return ",".join("0x%02X" % value for value in values)


@dataclass
class _Arrival:
    """A packet on the simulated air."""

    data: bytes
    rssi_dbm: float
    pqi: int
    sqi: int
    error: int


class SimulatedS2lp:
    """A simulated kit board. Satisfies ``Responder``.

    :param board: Recorded for a test's convenience. The firmware never reports
        it, and neither does the simulator.
    :param loopback: Deliver every transmitted packet back to the next receive,
        so a single simulated board can exercise both directions.
    """

    #: What the motherboard and the radio report, as the kit did.
    BOARD_VERSION = 0x80
    LIBRARY_VERSION = 0x00010305
    PART_NUMBER = 0x03
    S2LP_VERSION = 0xC1
    XTAL_HZ = 49_999_561

    def __init__(self, board: str = DEFAULT_BOARD, loopback: bool = False) -> None:
        self.board = board
        self.loopback = bool(loopback)
        self.command_log: List[str] = []
        self.registers: Dict[int, int] = {}
        self.transmitted: List[bytes] = []
        #: Packets waiting on the air, as ``(payload, rssi dBm)``.
        self.inbound: List[Tuple[bytes, float]] = []
        self._arrivals: List[_Arrival] = []
        #: Packets that arrived while nothing was listening.
        self.missed = 0
        self.stopped = False
        #: A stop character sent while nothing was running, waiting to spoil
        #: the next command.
        self.stray_stop = False
        self.report_all = False
        #: GPIOs on which the board is listening for an interrupt.
        self.board_irq_lines = set()
        #: What the board is busy doing: ``None``, ``"get"`` or ``"batch"``.
        self._busy: Optional[str] = None
        self._batch_left = 0
        self.timer_us = 0
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Power-on state: every register at its documented reset value."""
        self.registers = {register.address: register.reset for register in REGISTERS}
        self.registers[0xF0] = self.PART_NUMBER
        self.registers[0xF1] = self.S2LP_VERSION
        self.tx_fifo = bytearray()
        self.rx_fifo = bytearray()
        self.frequency_hz = 834_608_045
        self.modulation = Modulation.UNMODULATED
        self.data_rate_bps = 36_922
        self.deviation_hz = 19_216
        self.bandwidth_hz = 96_633
        self.power_tenths = [120] * 8
        self.payload_length = 20
        self.irq_status = 0
        self._pending_ack = ""
        self.transmitted = []
        self.inbound = []
        self._arrivals = []
        self.missed = 0
        self.stopped = False
        self._busy = None

    # ------------------------------------------------------------------
    # The air
    # ------------------------------------------------------------------
    def queue_packet(
        self, data: bytes, rssi_dbm: float = -70.0, pqi: int = 24, sqi: int = 30,
        error: int = 0,
    ) -> None:
        """Put a packet on the air for the next receive to find.

        :param error: Make the firmware reject it with this code (2 for a CRC
            failure) instead of delivering it.
        """
        self._arrivals.append(_Arrival(bytes(data), float(rssi_dbm), int(pqi), int(sqi),
                                       int(error)))
        self.inbound.append((bytes(data), float(rssi_dbm)))

    def arrive_while_deaf(self, data: bytes) -> None:
        """A packet that arrives while the radio is not armed.

        It is counted and dropped, which is what the hardware does and what the
        driver must not present as "nothing was transmitted".
        """
        self.missed += 1

    def _take(self) -> Optional[_Arrival]:
        if not self._arrivals:
            return None
        self.inbound.pop(0)
        arrival = self._arrivals.pop(0)
        self.registers[_PQI] = arrival.pqi & 0xFF
        self.registers[_SQI] = arrival.sqi & 0x7F
        self.registers[_RSSI_LEVEL] = _rssi_byte(arrival.rssi_dbm)
        self.registers[_RX_LEN1] = (len(arrival.data) >> 8) & 0xFF
        self.registers[_RX_LEN0] = len(arrival.data) & 0xFF
        return arrival

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one command line, or the stop character."""
        text = message.decode("ascii", errors="replace").strip()
        if text == "S":                       # the stop character, not a command
            return self._stop()
        if self.stray_stop:
            # The stop character sat in the buffer and is now part of this line.
            self.stray_stop = False
            self.command_log.append("S" + text)
            return ("%s\r\nno such command\r\n>" % text).encode("ascii")
        if not text:
            return None
        self.command_log.append(text)
        name, arguments = self._split(text)
        handler = getattr(self, "_cmd_" + name.lower(), None)
        if handler is None:
            return ("%s\r\nno such command\r\n>" % text).encode("ascii")
        reply = handler(arguments) or ""
        # The prompt comes only when the command has finished; a receive still
        # waiting sends its echo and whatever it has reported so far.
        prompt = "" if self._busy else ">"
        return ("%s\r\n%s%s" % (text, reply, prompt)).encode("ascii")

    def poll(self) -> Optional[bytes]:
        """Output the board produces on its own, while busy receiving."""
        if self._busy not in ("get", "batch") or not self._arrivals:
            return None
        if self._busy == "get":
            self._busy = None
            return (self._single_report(self._take()) + ">").encode("ascii")
        output = self._batch_output()
        return (output + ("" if self._busy else ">")).encode("ascii")

    def _stop(self) -> Optional[bytes]:
        if self._busy is None:
            self.stray_stop = True
            return b"S"
        self._busy = None
        self.stopped = True
        self._batch_left = 0
        # An interrupted send prints its own acknowledgement after the stop's.
        pending, self._pending_ack = self._pending_ack, ""
        return ("%s%s>" % (self._call("StopCmd"), pending)).encode("ascii")

    # ------------------------------------------------------------------
    # The interrupt line
    # ------------------------------------------------------------------
    def _irq_mask(self) -> int:
        return ((self.registers[0x50] << 24) | (self.registers[0x51] << 16)
                | (self.registers[0x52] << 8) | self.registers[0x53])

    def route_interrupt(self) -> None:
        """Route the interrupt as the driver's ``prepare_traffic`` does.

        A convenience for tests that drive the simulator directly.
        """
        self.respond(b"S2LPGpioInit %d 2 0" % IRQ_GPIO)
        self.respond(b"S2MGpioIrqConfiguration %d 1" % IRQ_GPIO)
        self.respond(b"S2LPIrq %d 1" % (TX_DATA_SENT | RX_DATA_READY))

    def irq_reaches_board(self, irq: int) -> bool:
        """Whether interrupt *irq* would reach the board's firmware."""
        conf = self.registers.get(IRQ_GPIO, 0)
        routed = (conf & 0xF8) == 0x00 and (conf & 0x03) in (2, 3)     # nIRQ, an output
        return routed and IRQ_GPIO in self.board_irq_lines and bool(self._irq_mask() & irq)

    def _pin_level(self, gpio: int) -> int:
        """What the board reads on the line from radio GPIO *gpio*."""
        conf = self.registers.get(gpio & 3, 0)
        if (conf & 0x03) not in (2, 3):
            return 0                         # not driven: an input, or analogue
        signal = conf & 0xF8
        return 0 if signal == 0xA0 else 1    # GND reads low; nIRQ idles high

    def _cmd_s2mgpiogetvalue(self, arguments: List[str]) -> str:
        return self._value("S2MGpioGetValue", "%02X" % self._pin_level(self._number(arguments[0])))

    def _tx_source(self) -> int:
        return (self.registers.get(0x30, 0) >> 2) & 0x03

    def _cmd_s2lpgpioinit(self, arguments: List[str]) -> str:
        pin, mode, signal = (self._number(a) for a in arguments[:3])
        self.registers[pin & 3] = (signal & 0xF8) | (mode & 0x03)
        return self._call("S2LPGpioInit")

    def _cmd_s2mgpioirqconfiguration(self, arguments: List[str]) -> str:
        line, enable = self._number(arguments[0]), self._number(arguments[1])
        if enable:
            self.board_irq_lines.add(line)
        else:
            self.board_irq_lines.discard(line)
        return self._call("S2MGpioIrqConfiguration")

    @staticmethod
    def _split(text: str) -> Tuple[str, List[str]]:
        """Command name and its arguments, with a brace list kept whole."""
        braced = re.search(r"\{([^}]*)\}", text)
        if braced:
            head = text[: braced.start()].split()
            return head[0], head[1:] + ["{%s}" % braced.group(1)]
        parts = text.split()
        return parts[0], parts[1:]

    @staticmethod
    def _number(argument: str) -> int:
        return int(argument, 0)

    @staticmethod
    def _payload(argument: str) -> bytes:
        """Decode ST's ``{08 A1}`` or ``"text"`` argument."""
        text = argument.strip()
        if text.startswith("{"):
            digits = re.sub(r"[^0-9A-Fa-f]", "", text)
            return bytes.fromhex(digits)
        return text.strip('"').encode("ascii", errors="replace")

    def _tick(self, microseconds: int = _TICK_US) -> int:
        self.timer_us = (self.timer_us + int(microseconds)) & 0xFFFFFFFF
        return self.timer_us

    @staticmethod
    def _call(name: str, tags: str = "") -> str:
        """ST's one-line reply: ``{{(Name)} API call...{tag:value}}``."""
        return "{{(%s)} API call...%s}\r\n" % (name, tags)

    def _value(self, name: str, text: str) -> str:
        return self._call(name, "{value:%s}" % text)

    def _timer(self, name: str) -> str:
        return self._call(name, "{timer:%08X}" % self._tick())

    # ------------------------------------------------------------------
    # Motherboard commands
    # ------------------------------------------------------------------
    def _cmd_sdkevalspireadregisters(self, arguments: List[str]) -> str:
        address = self._number(arguments[0])
        count = self._number(arguments[1])
        values = []
        for offset in range(count):
            current = (address + offset) & 0xFF
            values += [current, self.registers.get(current, 0)]
        return (
            "{{(SdkEvalSpiReadRegisters)} API callback...\r\n"
            "{regs_list: %s}\r\n{timer:%08X}\r\n}\r\n" % (_list(values), self._tick())
        )

    def _cmd_sdkevalspiwriteregisters(self, arguments: List[str]) -> str:
        address = self._number(arguments[0])
        for offset, value in enumerate(self._payload(arguments[1])):
            current = (address + offset) & 0xFF
            register = BY_ADDRESS.get(current)
            if register is not None and not register.writable:
                continue              # the radio ignores a write to a read-only register
            self.registers[current] = value
        return self._timer("SdkEvalSpiWriteRegisters")

    def _cmd_sdkevalspicommandstrobes(self, arguments: List[str]) -> str:
        code = self._number(arguments[0])
        if code == Strobe.RESET:
            # SRES resets the digital section and *not* the SPI registers -
            # ST's own command header says so, and modelling it as a register
            # reset made a driver that used it to get defaults appear to work.
            self.tx_fifo = bytearray()
            self.rx_fifo = bytearray()
        elif code == Strobe.FLUSH_RX_FIFO:
            self.rx_fifo = bytearray()
        elif code == Strobe.FLUSH_TX_FIFO:
            self.tx_fifo = bytearray()
        return self._timer("SdkEvalSpiCommandStrobes")

    def _cmd_sdkevalspireadfifo(self, arguments: List[str]) -> str:
        count = min(self._number(arguments[0]), len(self.rx_fifo))
        data, self.rx_fifo = self.rx_fifo[:count], self.rx_fifo[count:]
        return (
            "{{(SdkEvalSpiReadFifo)} API call...\r\n"
            "{bytes: %s}\r\n{timer:%08X}\r\n}\r\n" % (_list(data), self._tick())
        )

    def _cmd_sdkevalspiwritefifo(self, arguments: List[str]) -> str:
        payload = self._payload(arguments[0])[:FIFO_SIZE]
        self.tx_fifo.extend(payload)
        return self._timer("SdkEvalSpiWriteFifo")

    def _cmd_sdkevalrfboardidentification(self, _arguments: List[str]) -> str:
        # It answers with no tags: which board it found is never reported.
        return self._call("SdkEvalRfboardIdentification")

    def _cmd_sdkevalgetversion(self, _arguments: List[str]) -> str:
        return self._call("SdkEvalGetVersion", " {version:%02X}" % self.BOARD_VERSION)

    def _cmd_sdkevalsdn(self, arguments: List[str]) -> str:
        """Shutdown. Leaving it is a power-on reset, and then ST's settings.

        What is on the air, and what was transmitted, are not the radio's state
        and survive - a log of what happened is not undone by a power cycle.
        """
        if self._number(arguments[0]):
            air, arrivals = list(self.inbound), list(self._arrivals)
            sent, missed = list(self.transmitted), self.missed
            self.reset()
            self.inbound, self._arrivals = air, arrivals
            self.transmitted, self.missed = sent, missed
        else:
            for name, value in AFTER_SHUTDOWN_EXIT.items():
                self.registers[lookup(name).address] = value
        return self._timer("SdkEvalSdn")

    def _cmd_sdkevalledhandler(self, _arguments: List[str]) -> str:
        return self._timer("SdkEvalLedHandler")

    def _cmd_cligettimer(self, _arguments: List[str]) -> str:
        return self._timer("CliGetTimer")

    # ------------------------------------------------------------------
    # Radio commands
    # ------------------------------------------------------------------
    def _set_modulation(self, code: int) -> None:
        """Modulation lives in MOD2's top nibble, so put it there.

        The rest of the synthesis path - the SYNT registers, the datarate
        mantissa and exponent - is not modelled: reproducing the device's
        arithmetic would be reimplementing the radio rather than testing the
        driver. What matters here is that a setting is visible where the
        datasheet says it lives, so a driver reading it back reads a register.
        """
        self.modulation = code
        self.registers[0x10] = (code & 0xF0) | (self.registers.get(0x10, 0) & 0x0F)

    def _cmd_s2lpradioinit(self, arguments: List[str]) -> str:
        (self.frequency_hz, modulation, self.data_rate_bps,
         self.deviation_hz, self.bandwidth_hz) = (
            self._number(a) for a in arguments[:5])
        # ST's handler reads five arguments and ignores the crystal.
        self._set_modulation(modulation)
        return self._call("S2LPRadioInit", "{error:00}")

    def _cmd_s2lpradiogetinfo(self, _arguments: List[str]) -> str:
        return self._call(
            "S2LPRadioGetInfo",
            "{Frequency_base:%08X}{Modulation:%02X}{Data_rate:%08X}"
            "{Frequency_deviation:%08X}{Channel_filter_bandwidth:%08X}"
            "{XTAL_frequency:%08X}"
            % (self.frequency_hz, self.modulation, self.data_rate_bps,
               self.deviation_hz, self.bandwidth_hz, self.XTAL_HZ),
        )

    def _cmd_s2lpradiosetfrequencybase(self, arguments: List[str]) -> str:
        self.frequency_hz = self._number(arguments[0])
        return self._call("S2LPRadioSetFrequencyBase")

    def _cmd_s2lpradiogetfrequencybase(self, _arguments: List[str]) -> str:
        return self._value("S2LPRadioGetFrequencyBase", "%08X" % self.frequency_hz)

    def _cmd_s2lpradiosetmodulation(self, arguments: List[str]) -> str:
        self._set_modulation(self._number(arguments[0]))
        return self._call("S2LPRadioSetModulation")

    def _cmd_s2lpradiogetmodulation(self, _arguments: List[str]) -> str:
        return self._value("S2LPRadioGetModulation", "%02X" % self.modulation)

    def _cmd_s2lpradiosetpaleveldbm(self, arguments: List[str]) -> str:
        index = self._number(arguments[1])
        self.power_tenths[index & 7] = int(arguments[0], 0) * 10
        return self._call("S2LPRadioSetPALeveldBm")

    def _cmd_s2lpradiogetpaleveldbm(self, arguments: List[str]) -> str:
        return self._value("S2LPRadioGetPALeveldBm",
                           "%d" % self.power_tenths[self._number(arguments[0]) & 7])

    def _cmd_s2lpradiogetxtalfrequency(self, _arguments: List[str]) -> str:
        return self._value("S2LPRadioGetXtalFrequency", "%08X" % self.XTAL_HZ)

    def _cmd_s2lpqigetrssidbm(self, _arguments: List[str]) -> str:
        rssi = self._arrivals[0].rssi_dbm if self._arrivals else -146.0
        return self._value("S2LPQiGetRssidBm", "%.1f" % rssi)

    def _cmd_s2lpgetversion(self, _arguments: List[str]) -> str:
        return self._value("S2LPGetVersion",
                           "%02X%02X" % (self.PART_NUMBER, self.S2LP_VERSION))

    def _cmd_s2lpgetlibversion(self, _arguments: List[str]) -> str:
        return self._value("S2LPGetLibVersion", "%08X" % self.LIBRARY_VERSION)

    # ------------------------------------------------------------------
    # Packet handler
    # ------------------------------------------------------------------
    def _cmd_s2lppktbasicinit(self, arguments: List[str]) -> str:
        """Enough of ST's packet setup to matter: CRC, whitening, FEC, and the
        TX source back to the FIFO."""
        values = [self._number(a) for a in arguments[:9]]
        crc, fec, whitening = values[5], values[7], values[8]
        self.registers[0x30] = (crc & 0xE0) | ((whitening & 1) << 4) | (fec & 1)
        self.registers[0x2C] = values[0] & 0xFF
        return self._call("S2LPPktBasicInit")

    def _cmd_s2lppktbasicgetinfo(self, _arguments: List[str]) -> str:
        return self._call(
            "S2LPPktBasicGetInfo",
            "{preamble_length:0010}{sync_length:20}{sync_word:88888888}"
            "{length_mode:00}{length_size:00}{crc_mode:20}{address:00}"
            "{fec:00}{whitening:00}",
        )

    def _cmd_s2lppktbasicsetpayloadlength(self, arguments: List[str]) -> str:
        self.payload_length = self._number(arguments[0])
        return self._call("S2LPPktBasicSetPayloadLength")

    def _cmd_s2lppktbasicgetpayloadlength(self, _arguments: List[str]) -> str:
        return self._value("S2LPPktBasicGetPayloadLength", "%04X" % self.payload_length)

    def _cmd_s2lpgetpktfrmt(self, _arguments: List[str]) -> str:
        register = self.registers.get(0x2E, 0)
        return self._value("S2LPGetPktFrmt", "%02X" % ((register >> 6) & 0x03))

    def _cmd_s2lptimersetrxtimeoutus(self, arguments: List[str]) -> str:
        if self._number(arguments[0]) == 0:
            self.registers[0x46] = 0         # SET_INFINITE_RX_TIMEOUT: TIMERS5 = 0
        return self._call("S2LPTimerSetRxTimeoutUs")

    def _cmd_s2lptimergetrxtimeout(self, _arguments: List[str]) -> str:
        return self._call("S2LPTimerGetRxTimeout",
                          "{period:00000030}{counter:01}{prescaler:00}")

    def _cmd_s2lpgetbatchlp(self, _arguments: List[str]) -> str:
        return self._call("S2LPGetBatchLP")

    def _cmd_s2lpirq(self, arguments: List[str]) -> str:
        mask = self._irq_mask()
        code = self._number(arguments[0])
        mask = (mask | code) if self._number(arguments[1]) else (mask & ~code)
        for offset, address in enumerate((0x50, 0x51, 0x52, 0x53)):
            self.registers[address] = (mask >> (24 - 8 * offset)) & 0xFF
        return self._call("S2LPIrq")

    def _cmd_s2lpirqgetstatus(self, _arguments: List[str]) -> str:
        return self._value("S2LPIrqGetStatus", "%08X" % self.irq_status)

    def _cmd_s2lpgetnbytesreportall(self, arguments: List[str]) -> str:
        self.report_all = bool(self._number(arguments[0]))
        return self._call("S2LPGetNBytesReportAll")

    def _cmd_s2lpgetrcofrequency(self, _arguments: List[str]) -> str:
        return self._value("S2LPGetRcoFrequency", "878C")

    # ------------------------------------------------------------------
    # Traffic
    # ------------------------------------------------------------------
    def _transmit(self, payload: bytes) -> None:
        self.transmitted.append(payload)
        if self.loopback:
            self.queue_packet(payload, -40.0)

    def _cmd_s2lpsendnbytes(self, arguments: List[str]) -> Optional[str]:
        payload = self._payload(arguments[0])
        if self._tx_source() != 0:
            # PN9 goes out indefinitely; the payload never does.
            self._busy, self._pending_ack = "tx", self._call("S2LPSendNBytes")
            return None
        if len(payload) < self.payload_length:
            # The radio waits in TX for bytes that never come.
            self._busy, self._pending_ack = "tx", self._call("S2LPSendNBytes")
            return None
        self._transmit(payload[:self.payload_length])
        self._tick(2 * _TICK_US)
        if not self.irq_reaches_board(TX_DATA_SENT):
            # Sent, but the firmware never hears that it was.
            self._busy, self._pending_ack = "tx", self._call("S2LPSendNBytes")
            return None
        return self._call("S2LPSendNBytes")

    def _cmd_s2lpsendnbytesbatch(self, arguments: List[str]) -> Optional[str]:
        period_ms = self._number(arguments[0])
        count = self._number(arguments[1])
        payload = self._payload(arguments[2])
        if (self._tx_source() != 0 or len(payload) < self.payload_length
                or not self.irq_reaches_board(TX_DATA_SENT)):
            self._busy = "tx"
            return None
        lines = []
        for _ in range(count):
            self._transmit(payload)
            self._tick(max(1, period_ms) * 1000)
            lines.append(self._call("S2LPSendNBytes"))
        lines.append(self._call("S2LPSendNBytesBatch"))
        return "".join(lines)

    def _single_report(self, arrival: _Arrival) -> str:
        """``S2LPGetNBytes`` on its own: error, rssi, bytes, timer."""
        self._tick(2 * _TICK_US)
        lines = ["{{(S2LPGetNBytes)} API call...\r\n",
                 "{error:%02X}\r\n" % arrival.error,
                 "{rssi:%02X}\r\n" % _rssi_byte(arrival.rssi_dbm)]
        if not arrival.error:
            lines.append("{bytes: %s}\r\n" % _list(arrival.data))
        lines.append("{timer:%08X}\r\n}\r\n" % self.timer_us)
        return "".join(lines)

    def _batch_report(self, arrival: _Arrival) -> str:
        """One report from the batch loop: error, bytes, rssi, extras, timer."""
        self._tick(2 * _TICK_US)
        lines = ["{{(S2LPGetNBytes)} API call...\r\n",
                 "{error:%02X}\r\n" % arrival.error]
        if not arrival.error:
            lines.append("{bytes: %s}\r\n" % _list(arrival.data))
        lines.append("{rssi:%02X}\r\n" % _rssi_byte(arrival.rssi_dbm))
        if self.report_all:
            lines.append(
                "{seq_num:00}{nack_rx:00}{source_addr:00}{dest_addr:00}"
                "{agc_word:00}{crc:00000000}{packet_len:%02X}"
                % (len(arrival.data) + 1))
        lines.append("{timer:%08X}\r\n}\r\n" % self.timer_us)
        return "".join(lines)

    def _cmd_s2lpgetnbytes(self, _arguments: List[str]) -> Optional[str]:
        if not self.irq_reaches_board(RX_DATA_READY):
            self._busy = "deaf"              # waits for an interrupt that never comes
            return None
        arrival = self._take()
        if arrival is None:
            self._busy = "get"               # waits until a packet or a stop
            return None
        return self._single_report(arrival)

    def _batch_output(self) -> str:
        out = []
        while self._batch_left and self._arrivals:
            out.append(self._batch_report(self._take()))
            self._batch_left -= 1
        if not self._batch_left:
            self._busy = None
            out.append(self._call("S2LPGetNBytesBatch"))
        return "".join(out)

    def _cmd_s2lpgetnbytesbatch(self, arguments: List[str]) -> Optional[str]:
        """Stay in a capture loop, one report per packet, as the firmware does."""
        self._batch_left = self._number(arguments[1])
        if not self.irq_reaches_board(RX_DATA_READY):
            self._busy = "deaf"
            return None
        self._busy = "batch"
        return self._batch_output()
