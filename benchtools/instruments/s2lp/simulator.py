"""A simulated S2-LP development kit, answering ST's CLI protocol.

The model is of a **register file with a radio attached to it**, not a set of
canned replies. Writing PCKTCTRL3 changes what ``S2LPGetPktFrmt`` answers;
strobing ``FLUSH_RX_FIFO`` empties the FIFO; a packet queued on the simulated
air is delivered to exactly one receive call and is then gone. That is what
makes the tests above it worth running: a driver that writes to the wrong
address, or reads a register it never wrote, fails here rather than on the
bench.

Two behaviours are modelled because they are the ones that mislead:

* **A receive call that finds nothing** answers with a non-zero error after its
  timeout, exactly as the firmware does. It does not hang, and it does not
  return an empty packet - an empty packet and no packet are different facts.
* **Packets arriving while the radio is not armed are lost.** The simulated air
  holds them only while a receive is in progress, which is what makes the gap
  between polled receives visible in a test instead of only on the bench.

Traces to: S2LP-FR-050, S2LP-DD-SIM.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .constants import DEFAULT_BOARD, FIFO_SIZE, Modulation, Strobe
from .registers import BY_ADDRESS, REGISTERS

__all__ = ["SimulatedS2lp"]

#: The simulator's own error codes for a receive that produced nothing. The
#: firmware's codes are not published in the CLI source, so these are the
#: simulator's, and the driver treats any non-zero code the same way.
RX_TIMEOUT = 0x01
RX_CRC_ERROR = 0x02


def _rssi_byte(dbm: float) -> int:
    """dBm to the RSSI_LEVEL register value: dBm = value / 2 - 146."""
    return max(0, min(255, int(round((float(dbm) + 146.0) * 2.0))))


class SimulatedS2lp:
    """A simulated kit board. Satisfies ``Responder``.

    :param board: What ``SdkEvalRfboardIdentification`` should report.
    :param loopback: Deliver every transmitted packet back to the next receive,
        so a single simulated board can exercise both directions.
    """

    #: What the motherboard and the radio report as their versions.
    BOARD_VERSION = "3.2.1"
    LIBRARY_VERSION = "S2LP_Library_v1.4.0"
    S2LP_VERSION = 0x91

    def __init__(self, board: str = DEFAULT_BOARD, loopback: bool = False) -> None:
        self.board = board
        self.loopback = bool(loopback)
        self.command_log: List[str] = []
        self.registers: Dict[int, int] = {}
        self.transmitted: List[bytes] = []
        #: Packets waiting on the air, as ``(payload, rssi dBm)``.
        self.inbound: List[Tuple[bytes, float]] = []
        #: Packets that arrived while nothing was listening.
        self.missed = 0
        self.stopped = False
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Power-on state: every register at its documented reset value."""
        self.registers = {register.address: register.reset for register in REGISTERS}
        self.tx_fifo = bytearray()
        self.rx_fifo = bytearray()
        self.frequency_hz = 915_000_000
        self.modulation = Modulation.GFSK_2_BT1
        self.data_rate_bps = 38_400
        self.deviation_hz = 20_000
        self.bandwidth_hz = 100_000
        self.xtal_hz = 50_000_000
        self.power_dbm = 12.0
        self.payload_length = 20
        self.rx_timeout_us = 1_000_000
        self.irq_mask = 0
        self.timer_ms = 0
        self.transmitted = []
        self.inbound = []
        self.missed = 0
        self.stopped = False

    # ------------------------------------------------------------------
    # The air
    # ------------------------------------------------------------------
    def queue_packet(self, data: bytes, rssi_dbm: float = -70.0) -> None:
        """Put a packet on the air for the next receive to find."""
        self.inbound.append((bytes(data), float(rssi_dbm)))

    def arrive_while_deaf(self, data: bytes) -> None:
        """A packet that arrives while the radio is not armed.

        It is counted and dropped, which is what the hardware does and what the
        driver must not present as "nothing was transmitted".
        """
        self.missed += 1

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one command line."""
        text = message.decode("ascii", errors="replace").strip()
        if not text:
            return None
        if text == "S":                       # the stop character, not a command
            self.stopped = True
            return None
        self.command_log.append(text)
        name, arguments = self._split(text)
        handler = getattr(self, "_cmd_" + name.lower(), None)
        if handler is None:
            # ST's interpreter answers an unknown command with an error line.
            return b"Command error\r\n"
        reply = handler(arguments)
        return None if reply is None else reply.encode("ascii")

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

    def _tick(self, milliseconds: int = 1) -> int:
        self.timer_ms = (self.timer_ms + int(milliseconds)) & 0xFFFFFFFF
        return self.timer_ms

    def _ok(self, name: str) -> str:
        """ST's one-line acknowledgement."""
        return "{{%s} API call...{timer:%08X}}\r\n" % (name, self._tick())

    # ------------------------------------------------------------------
    # Motherboard commands
    # ------------------------------------------------------------------
    def _cmd_sdkevalspireadregisters(self, arguments: List[str]) -> str:
        address = self._number(arguments[0])
        count = self._number(arguments[1])
        pairs = []
        for offset in range(count):
            current = (address + offset) & 0xFF
            pairs.append("0x%02X,0x%02X" % (current, self.registers.get(current, 0)))
        return (
            "{{SdkEvalSpiReadRegisters} API callback...\r\n"
            "{regs_list: %s}\r\n{timer:%08X}\r\n}\r\n" % (",".join(pairs), self._tick())
        )

    def _cmd_sdkevalspiwriteregisters(self, arguments: List[str]) -> str:
        address = self._number(arguments[0])
        for offset, value in enumerate(self._payload(arguments[1])):
            current = (address + offset) & 0xFF
            register = BY_ADDRESS.get(current)
            if register is not None and not register.writable:
                continue              # the radio ignores a write to a read-only register
            self.registers[current] = value
        return self._ok("SdkEvalSpiWriteRegisters")

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
        return self._ok("SdkEvalSpiCommandStrobes")

    def _cmd_sdkevalspireadfifo(self, arguments: List[str]) -> str:
        count = min(self._number(arguments[0]), len(self.rx_fifo))
        data, self.rx_fifo = self.rx_fifo[:count], self.rx_fifo[count:]
        values = ",".join("0x%02X" % byte for byte in data)
        return (
            "{{SdkEvalSpiReadFifo} API callback...\r\n"
            "{bytes: %s}\r\n{timer:%08X}\r\n}\r\n" % (values, self._tick())
        )

    def _cmd_sdkevalspiwritefifo(self, arguments: List[str]) -> str:
        payload = self._payload(arguments[0])[:FIFO_SIZE]
        self.tx_fifo.extend(payload)
        return self._ok("SdkEvalSpiWriteFifo")

    def _cmd_sdkevalrfboardidentification(self, arguments: List[str]) -> str:
        requested = self._number(arguments[0])
        if requested:
            self.xtal_hz = requested
        return (
            "{{SdkEvalRfboardIdentification} API callback...\r\n"
            "{board: %s}\r\n{xtal: %d}\r\n{timer:%08X}\r\n}\r\n"
            % (self.board, self.xtal_hz, self._tick())
        )

    def _cmd_sdkevalgetversion(self, _arguments: List[str]) -> str:
        return (
            "{{SdkEvalGetVersion} API callback...\r\n"
            "{version: %s}\r\n{timer:%08X}\r\n}\r\n" % (self.BOARD_VERSION, self._tick())
        )

    def _cmd_sdkevalsdn(self, arguments: List[str]) -> str:
        """Shutdown. Leaving it is a power-on reset, so registers go to default.

        This is the only thing here that restores register defaults, because on
        the part it is the only thing that does: SRES explicitly does not.
        What is on the air, and what was transmitted, are not the radio's state
        and survive - a log of what happened is not undone by a power cycle.
        """
        if self._number(arguments[0]):
            air, sent, missed = list(self.inbound), list(self.transmitted), self.missed
            self.reset()
            self.inbound, self.transmitted, self.missed = air, sent, missed
        return self._ok("SdkEvalSdn")

    def _cmd_sdkevalledhandler(self, _arguments: List[str]) -> str:
        return self._ok("SdkEvalLedHandler")

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
         self.deviation_hz, self.bandwidth_hz, xtal) = (
            self._number(a) for a in arguments[:6])
        self._set_modulation(modulation)
        if xtal:
            self.xtal_hz = xtal
        return self._ok("S2LPRadioInit")

    def _cmd_s2lpradiogetinfo(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPRadioGetInfo} API callback...\r\n"
            "{frequency: %d}\r\n{modulation: 0x%02X}\r\n{datarate: %d}\r\n"
            "{fdev: %d}\r\n{bandwidth: %d}\r\n{timer:%08X}\r\n}\r\n"
            % (self.frequency_hz, self.modulation, self.data_rate_bps,
               self.deviation_hz, self.bandwidth_hz, self._tick())
        )

    def _cmd_s2lpradiosetfrequencybase(self, arguments: List[str]) -> str:
        self.frequency_hz = self._number(arguments[0])
        return self._ok("S2LPRadioSetFrequencyBase")

    def _cmd_s2lpradiogetfrequencybase(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPRadioGetFrequencyBase} API callback...\r\n"
            "{frequency: %d}\r\n{timer:%08X}\r\n}\r\n" % (self.frequency_hz, self._tick())
        )

    def _cmd_s2lpradiosetmodulation(self, arguments: List[str]) -> str:
        self._set_modulation(self._number(arguments[0]))
        return self._ok("S2LPRadioSetModulation")

    def _cmd_s2lpradiogetmodulation(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPRadioGetModulation} API callback...\r\n"
            "{modulation: 0x%02X}\r\n{timer:%08X}\r\n}\r\n" % (self.modulation, self._tick())
        )

    def _cmd_s2lpradiosetpaleveldbm(self, arguments: List[str]) -> str:
        self.power_dbm = float(self._number(arguments[0]))
        return self._ok("S2LPRadioSetPALeveldBm")

    def _cmd_s2lpradiogetpaleveldbm(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPRadioGetPALeveldBm} API callback...\r\n"
            "{power: %d}\r\n{timer:%08X}\r\n}\r\n" % (int(self.power_dbm), self._tick())
        )

    def _cmd_s2lpradiogetxtalfrequency(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPRadioGetXtalFrequency} API callback...\r\n"
            "{xtal: %d}\r\n{timer:%08X}\r\n}\r\n" % (self.xtal_hz, self._tick())
        )

    def _cmd_s2lpqigetrssidbm(self, _arguments: List[str]) -> str:
        rssi = self.inbound[0][1] if self.inbound else -110.0
        return (
            "{{S2LPQiGetRssidBm} API callback...\r\n"
            "{rssi: %d}\r\n{timer:%08X}\r\n}\r\n" % (int(rssi), self._tick())
        )

    def _cmd_s2lpgetversion(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPGetVersion} API callback...\r\n"
            "{version: 0x%02X}\r\n{timer:%08X}\r\n}\r\n" % (self.S2LP_VERSION, self._tick())
        )

    def _cmd_s2lpgetlibversion(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPGetLibVersion} API callback...\r\n"
            "{version: %s}\r\n{timer:%08X}\r\n}\r\n" % (self.LIBRARY_VERSION, self._tick())
        )

    # ------------------------------------------------------------------
    # Packet handler
    # ------------------------------------------------------------------
    def _cmd_s2lppktbasicinit(self, arguments: List[str]) -> str:
        return self._ok("S2LPPktBasicInit")

    def _cmd_s2lppktbasicgetinfo(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPPktBasicGetInfo} API callback...\r\n"
            "{payload_length: %d}\r\n{timer:%08X}\r\n}\r\n"
            % (self.payload_length, self._tick())
        )

    def _cmd_s2lppktbasicsetpayloadlength(self, arguments: List[str]) -> str:
        self.payload_length = self._number(arguments[0])
        return self._ok("S2LPPktBasicSetPayloadLength")

    def _cmd_s2lppktbasicgetpayloadlength(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPPktBasicGetPayloadLength} API callback...\r\n"
            "{payload_length: %d}\r\n{timer:%08X}\r\n}\r\n"
            % (self.payload_length, self._tick())
        )

    def _cmd_s2lpgetpktfrmt(self, _arguments: List[str]) -> str:
        register = self.registers.get(0x2E, 0)
        return (
            "{{S2LPGetPktFrmt} API callback...\r\n"
            "{format: %d}\r\n{timer:%08X}\r\n}\r\n" % ((register >> 6) & 0x03, self._tick())
        )

    def _cmd_s2lptimersetrxtimeoutus(self, arguments: List[str]) -> str:
        self.rx_timeout_us = self._number(arguments[0])
        return self._ok("S2LPTimerSetRxTimeoutUs")

    def _cmd_s2lptimergetrxtimeout(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPTimerGetRxTimeout} API callback...\r\n"
            "{timeout: %d}\r\n{timer:%08X}\r\n}\r\n" % (self.rx_timeout_us, self._tick())
        )

    def _cmd_s2lpirq(self, arguments: List[str]) -> str:
        code, enable = self._number(arguments[0]), self._number(arguments[1])
        self.irq_mask = (self.irq_mask | code) if enable else (self.irq_mask & ~code)
        return self._ok("S2LPIrq")

    def _cmd_s2lpirqgetstatus(self, _arguments: List[str]) -> str:
        return (
            "{{S2LPIrqGetStatus} API callback...\r\n"
            "{irq: 0x%08X}\r\n{timer:%08X}\r\n}\r\n" % (self.irq_mask, self._tick())
        )

    def _cmd_s2lpgetnbytesreportall(self, _arguments: List[str]) -> str:
        return self._ok("S2LPGetNBytesReportAll")

    # ------------------------------------------------------------------
    # Traffic
    # ------------------------------------------------------------------
    def _transmit(self, payload: bytes) -> None:
        self.transmitted.append(payload)
        if self.loopback:
            self.inbound.append((payload, -40.0))

    def _cmd_s2lpsendnbytes(self, arguments: List[str]) -> str:
        self._transmit(self._payload(arguments[0]))
        self._tick(2)
        return "{{S2LPSendNBytes} API call...}\r\n"

    def _cmd_s2lpsendnbytesbatch(self, arguments: List[str]) -> str:
        period_ms = self._number(arguments[0])
        count = self._number(arguments[1])
        payload = self._payload(arguments[2])
        for _ in range(count):
            if self.stopped:
                break
            self._transmit(payload)
            self._tick(max(1, period_ms))
        return "{{S2LPSendNBytesBatch} API call...{timer:%08X}}\r\n" % self.timer_ms

    def _receive_one(self) -> str:
        """One receive, in the firmware's reply shape."""
        self._tick(2)
        if not self.inbound:
            return (
                "{{S2LPGetNBytes} API call...\r\n{error:%02X}\r\n{rssi:%02X}\r\n"
                "{timer:%08X}\r\n}\r\n" % (RX_TIMEOUT, _rssi_byte(-110.0), self.timer_ms)
            )
        payload, rssi = self.inbound.pop(0)
        values = ",".join("0x%02X" % byte for byte in payload)
        return (
            "{{S2LPGetNBytes} API call...\r\n{error:00}\r\n{rssi:%02X}\r\n"
            "{bytes: %s}\r\n{timer:%08X}\r\n}\r\n"
            % (_rssi_byte(rssi), values, self.timer_ms)
        )

    def _cmd_s2lpgetnbytes(self, _arguments: List[str]) -> str:
        return self._receive_one()

    def _cmd_s2lpgetnbytesbatch(self, arguments: List[str]) -> str:
        """Stay in a capture loop, one reply per packet, as the firmware does."""
        count = self._number(arguments[1])
        replies = []
        for _ in range(count):
            if self.stopped:
                self.stopped = False
                break
            replies.append(self._receive_one())
        return "".join(replies)
