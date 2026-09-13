"""Driver for the ST S2-LP development kit, over USB.

The kit runs **ST's own CLI firmware** - the firmware the S2-LP DK GUI drives -
so this driver is a host-side client of that interface rather than a reason to
write new firmware. What it adds is what the GUI does not: register names and
bit fields instead of hex, packets as records instead of screen text, and two
logs that can be read afterwards by somebody who was not in the room.

Three things it is careful about, because each is a way a capture misleads:

**Reception is polled.** ``S2LPGetNBytes`` arms the radio, waits, and returns.
Between one call and the next the radio is not listening, and a packet arriving
in that gap is not lost so much as *invisible* - nothing anywhere records that
it happened. :meth:`capture` therefore counts how many times it re-armed and
puts that in the result, so "nothing was transmitted" and "we were not
listening" stay distinguishable. :meth:`capture` with ``continuous=True`` keeps
the board in its own loop and has no gaps at all; prefer it.

**Timestamps are the board's millisecond timer**, not a radio timestamp. Good
enough to order packets and to time a sequence; not good enough to characterise
a protocol's timing, and this driver never presents it as if it were.

**A frequency the band cannot reach is refused.** The radio will accept a
setting outside the board's filter and matching network, transmit into it, and
report exactly what it was told - while almost nothing comes out of the antenna.

Traces to: S2LP-FR-001 .. S2LP-FR-060, S2LP-ARC-001, S2LP-DD-S2LP, S2LP-DD-CONFIG.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ...core.errors import ConfigurationError, InstrumentError, ProtocolError
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from . import registers as reg
from .configuration import (
    ConfigurationCheck,
    RegisterConfiguration,
    format_register_file,
    load_register_file,
)
from .constants import (
    BOARDS,
    DEFAULT_BAUDRATE,
    DEFAULT_BOARD,
    DEFAULT_TIMEOUT,
    DEFAULT_XTAL_HZ,
    MANUFACTURER,
    MAX_PAYLOAD,
    MODEL,
    Modulation,
    Strobe,
)
from .packets import Capture, Packet, PacketLog
from .session import S2lpSession
from .simulator import SimulatedS2lp

__all__ = ["S2lpDevkit", "rssi_dbm_from_register", "rssi_register_from_dbm"]

_LOG = logging.getLogger(__name__)


def rssi_dbm_from_register(value: int) -> float:
    """RSSI_LEVEL to dBm, by the datasheet's conversion: dBm = value/2 - 146."""
    return (int(value) / 2.0) - 146.0


def rssi_register_from_dbm(dbm: float) -> int:
    """dBm back to a RSSI_LEVEL value, for a threshold setting."""
    return max(0, min(255, int(round((float(dbm) + 146.0) * 2.0))))


class S2lpDevkit(Instrument):
    """An S2-LP development kit running ST's CLI firmware.

    :param transport: The link to the board, usually its USB serial port.
    :param board: Which kit this is. Read from the board when it will say.
    :param timeout: Seconds to wait for a reply.

    Example::

        from benchtools.instruments.s2lp import S2lpDevkit

        with S2lpDevkit.connect("/dev/ttyACM0", log_path="s2lp.log",
                                packet_log="packets.jsonl") as radio:
            radio.configure_radio(frequency_hz=915_000_000, data_rate_bps=38_400)
            radio.transmit(b"ping")

            capture = radio.capture(count=10, timeout=30.0)
            print(capture.describe())
            for packet in capture.packets:
                print(packet)
    """

    SIMULATOR_CLASS = SimulatedS2lp
    MODEL_NAME = MODEL

    def __init__(
        self,
        transport: Transport,
        board: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(auto_check_errors=False)
        self._transport = transport
        self._session = S2lpSession(transport, timeout=timeout)
        self._board = board
        self._xtal_hz = 0
        self._packet_log: Optional[PacketLog] = None
        self._payload_length = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(
        cls,
        resource: str = "sim://",
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        board: str = "",
        log_path: Optional[str] = None,
        packet_log: Optional[str] = None,
        initialise: bool = True,
        **kwargs,
    ) -> "S2lpDevkit":
        """Open a kit.

        :param resource: ``/dev/ttyACM0``, ``COM7``, ``serial://COM7``,
            ``serial://socket://bench-pc:4003`` or ``sim://``. A bare port name
            is taken as a serial port, not as a host name.
        :param log_path: Raw session log - every line, both directions.
        :param packet_log: Structured packet log, as JSON Lines.
        """
        target = cls._normalise_resource(resource)
        transport = open_transport(
            target,
            timeout=timeout,
            open_now=False,
            responder_factory=cls.SIMULATOR_CLASS,
            **({"baudrate": baudrate} if target.startswith("serial://") else {}),
        )
        instrument = cls(transport, board=board, timeout=timeout, **kwargs)
        if log_path:
            instrument._session.log_to(log_path)
        if packet_log:
            instrument.start_packet_log(packet_log)
        if initialise:
            try:
                instrument.initialise()
            except Exception:
                instrument.close()
                raise
        return instrument

    @staticmethod
    def _normalise_resource(resource: str) -> str:
        """Accept a bare port name as a serial port rather than a host name."""
        text = (resource or "").strip()
        if not text:
            return "sim://"
        if "://" in text or text.lower() in ("sim", "mock"):
            return text
        return "serial://%s" % text

    def _open(self) -> None:
        self._session.start()

    def _close(self) -> None:
        self.stop_packet_log()
        self._session.close()
        self._transport.close()

    @property
    def is_open(self) -> bool:
        return self._transport.is_open

    def _post_open(self) -> None:
        """Ask the board what it is. Nothing is configured here.

        Connecting must not retune a radio somebody left set up: identification
        is a read, and every setting is an explicit call.
        """
        self.identify()

    def _read_identity(self) -> InstrumentIdentity:
        """Identify the board through the firmware's own identification call."""
        reply = self._session.execute("SdkEvalRfboardIdentification", DEFAULT_XTAL_HZ)
        board = reply.text("board", "").strip()
        if board:
            self._board = board
        self._xtal_hz = reply.number("xtal", 0)

        firmware = ""
        try:
            firmware = self._session.execute("SdkEvalGetVersion").text("version", "")
        except (ProtocolError, InstrumentError):      # an older CLI build
            _LOG.debug("the board did not report a motherboard version")

        raw = "%s,%s,XTAL %d Hz,%s" % (MANUFACTURER, self._board or MODEL,
                                       self._xtal_hz, firmware)
        return InstrumentIdentity(
            raw=raw,
            manufacturer=MANUFACTURER,
            model=self._board or MODEL,
            serial_number="",
            firmware=firmware,
        )

    def reset(self, settle: float = 0.2) -> None:
        """Reset the radio's digital section (the ``SRES`` strobe).

        The SPI registers survive this, as they do on the part; use
        :meth:`restore_defaults` to put them back to their reset values.
        """
        self.strobe(Strobe.RESET)
        if settle > 0:
            time.sleep(settle)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def session(self) -> S2lpSession:
        return self._session

    @property
    def board(self) -> str:
        """Which kit board this is, as it identified itself."""
        return self._board or DEFAULT_BOARD

    @property
    def band(self) -> Tuple[int, int]:
        """The board's usable frequency range, in hertz."""
        return BOARDS.get(self.board, BOARDS[DEFAULT_BOARD])

    @property
    def xtal_hz(self) -> int:
        """The crystal the firmware detected, in hertz."""
        return self._xtal_hz

    @property
    def log_path(self) -> Optional[str]:
        return self._session.log_path

    @property
    def packet_log_path(self) -> Optional[str]:
        return self._packet_log.path if self._packet_log else None

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def start_log(self, path: str) -> str:
        """Record every line in both directions to *path*."""
        return self._session.log_to(path)

    def stop_log(self) -> None:
        self._session.stop_log()

    def log_note(self, text: str) -> None:
        """Write a comment into both logs, so a capture carries its context."""
        self._session.note(text)
        if self._packet_log is not None:
            self._packet_log.note(text)

    def start_packet_log(self, path: str) -> str:
        """Record every packet, in and out, as JSON Lines."""
        self.stop_packet_log()
        self._packet_log = PacketLog(path)
        return path

    def stop_packet_log(self) -> None:
        if self._packet_log is not None:
            self._packet_log.close()
            self._packet_log = None

    def _record(self, packet: Packet) -> Packet:
        if self._packet_log is not None:
            self._packet_log.write(packet)
        return packet

    # ------------------------------------------------------------------
    # Registers
    # ------------------------------------------------------------------
    def read_registers(self, start: Union[int, str], count: int = 1) -> List[int]:
        """Read *count* registers from *start*, by name or address."""
        address = reg.lookup(start).address if isinstance(start, str) else int(start)
        if count < 1 or count > 256 - address:
            raise ConfigurationError(
                "cannot read %d register(s) from 0x%02X; the map ends at 0xFF"
                % (count, address)
            )
        reply = self._session.execute("SdkEvalSpiReadRegisters", address, count)
        pairs = reply.numbers("regs_list")
        if len(pairs) != 2 * count:
            raise ProtocolError(
                "asked for %d register(s) from 0x%02X and got %d value(s): %s"
                % (count, address, len(pairs) // 2, reply.text("regs_list", ""))
            )
        # The firmware interleaves address and value; check the addresses rather
        # than assume them, so a mis-framed reply cannot become a wrong reading.
        for index in range(count):
            reported = pairs[2 * index]
            if reported != (address + index) & 0xFF:
                raise ProtocolError(
                    "the board answered with register 0x%02X where 0x%02X was asked for"
                    % (reported, (address + index) & 0xFF)
                )
        return [pairs[2 * index + 1] for index in range(count)]

    def read_register(self, which: Union[int, str]) -> int:
        """One register, by name (``"PCKTCTRL3"``) or address (``0x2E``)."""
        return self.read_registers(which, 1)[0]

    def write_registers(self, start: Union[int, str], values: Sequence[int]) -> None:
        """Write consecutive registers from *start*."""
        register = reg.lookup(start)
        payload = bytes(int(value) & 0xFF for value in values)
        if not payload:
            raise ConfigurationError("no values to write to %s" % register)
        if not register.writable:
            raise ConfigurationError(
                "%s is read-only on this device; writing it would be ignored "
                "and the read-back would not show it" % register
            )
        self._session.execute("SdkEvalSpiWriteRegisters", register.address, payload)

    def write_register(self, which: Union[int, str], value: int) -> None:
        """One register, by name or address."""
        self.write_registers(which, [value])

    def read_all_registers(self) -> Dict[int, int]:
        """Every documented register, as address to value.

        Read as contiguous runs rather than one at a time: 123 registers in a
        handful of commands instead of 123 round trips, which on a 115200 baud
        link is the difference between instant and not.
        """
        values: Dict[int, int] = {}
        for start, count in reg.contiguous_runs():
            for offset, value in enumerate(self.read_registers(start, count)):
                values[start + offset] = value
        return values

    def dump_registers(self, values: Optional[Dict[int, int]] = None) -> str:
        """Every register, named, with its non-zero fields decoded.

        This is the output that makes a register dump reviewable: a wall of hex
        says nothing, and ``PCKTCTRL3 = 0x20  PCKT_FRMT=0`` says what the radio
        was set up to do.
        """
        if values is None:
            values = self.read_all_registers()
        return "\n".join(reg.describe(values))

    def registers_differing_from_reset(
        self, values: Optional[Dict[int, int]] = None
    ) -> Dict[str, Tuple[int, int]]:
        """Registers that are not at their reset value: name to (reset, value).

        The short answer to "what has this radio been configured to do?".
        """
        if values is None:
            values = self.read_all_registers()
        differing = {}
        for address, value in sorted(values.items()):
            register = reg.BY_ADDRESS.get(address)
            if register is not None and value != register.reset:
                differing[register.name] = (register.reset, value)
        return differing

    def read_field(self, register: Union[int, str], field: str) -> int:
        """One named bit field, e.g. ``read_field("PCKTCTRL3", "PCKT_FRMT")``."""
        entry = reg.lookup(register)
        return entry.field(field).extract(self.read_register(entry.address))

    def write_field(self, register: Union[int, str], field: str, value: int) -> int:
        """Change one bit field, leaving the rest of the register alone.

        Read, modify, write - so the other fields keep their values rather than
        being zeroed, which is the mistake this method exists to prevent.

        :returns: The new whole-register value.
        """
        entry = reg.lookup(register)
        current = self.read_register(entry.address)
        try:
            updated = entry.field(field).insert(current, value)
        except ValueError as exc:
            raise ConfigurationError("%s.%s: %s" % (entry.name, field, exc)) from exc
        self.write_register(entry.address, updated)
        return updated

    def strobe(self, what: Union[int, str]) -> None:
        """Send a command strobe, by name (``"tx"``) or opcode (``0x60``)."""
        if isinstance(what, str):
            key = what.strip().lower()
            if key not in Strobe.BY_NAME:
                raise ConfigurationError(
                    "%r is not a command strobe; they are %s"
                    % (what, ", ".join(sorted(Strobe.BY_NAME)))
                )
            code = Strobe.BY_NAME[key]
        else:
            code = int(what)
        self._session.execute("SdkEvalSpiCommandStrobes", code)

    def restore_defaults(self) -> None:
        """Write every writable register back to its documented reset value."""
        for start, count in reg.contiguous_runs():
            addresses = [start + offset for offset in range(count)]
            block: List[int] = []
            block_start = None
            for address in addresses + [None]:
                register = reg.BY_ADDRESS.get(address) if address is not None else None
                if register is not None and register.writable:
                    if block_start is None:
                        block_start = address
                    block.append(register.reset)
                elif block:
                    self.write_registers(block_start, block)
                    block, block_start = [], None

    # ------------------------------------------------------------------
    # Register values from a file
    # ------------------------------------------------------------------
    @staticmethod
    def load_configuration(
        source: Union[str, RegisterConfiguration]
    ) -> RegisterConfiguration:
        """Read a register file, or pass one already loaded straight through.

        Accepting both means a specification can name a path and a Python caller
        can hand over a configuration it built or edited, without two methods
        that do the same thing.
        """
        if isinstance(source, RegisterConfiguration):
            return source
        return load_register_file(str(source))

    def apply_configuration(
        self, source: Union[str, RegisterConfiguration], verify: bool = True
    ) -> ConfigurationCheck:
        """Write the register values a file asks for, and check they took.

        Written in the file's own order, because some settings only take effect
        when written after another and a file that works should be applied the
        way it was written. Consecutive registers are still sent together.

        :param verify: Read the registers back afterwards. On by default: a
            write to this radio is acknowledged by the firmware, not by the
            radio, so "the command was accepted" and "the register holds the
            value" are different facts.
        :raises InstrumentError: if a register did not take the value asked for,
            naming every one that differs.
        """
        configuration = self.load_configuration(source)
        for address, values in self._runs_of(configuration):
            self.write_registers(address, values)

        if not verify:
            return ConfigurationCheck(source=configuration.source,
                                      checked=len(configuration))
        check = self.verify_configuration(configuration)
        if not check.matches:
            raise InstrumentError(
                "the radio did not take the configuration in %s: %s"
                % (configuration.source or "the file", check.describe())
            )
        return check

    @staticmethod
    def _runs_of(configuration: RegisterConfiguration):
        """Group a configuration's settings into consecutive blocks, in order."""
        runs = []
        for setting in configuration:
            if runs and setting.address == runs[-1][0] + len(runs[-1][1]):
                runs[-1][1].append(setting.value)
            else:
                runs.append((setting.address, [setting.value]))
        return runs

    def verify_configuration(
        self, source: Union[str, RegisterConfiguration], strict: bool = False
    ) -> ConfigurationCheck:
        """Check the radio against the register values a file asks for.

        :param strict: Also require that every register the file does **not**
            name is at its reset value. The two modes answer different
            questions: without it, "is what this test needs set?"; with it, "is
            the radio in exactly this configuration and nothing else?" - which
            catches a setting left behind by whatever ran before.
        """
        configuration = self.load_configuration(source)
        wanted = configuration.as_map()
        values = self.read_all_registers() if strict else {
            address: value
            for start, count in reg.contiguous_runs(list(wanted))
            for address, value in zip(range(start, start + count),
                                      self.read_registers(start, count))
        }

        check = ConfigurationCheck(
            source=configuration.source, checked=len(configuration), strict=bool(strict)
        )
        for setting in configuration:
            actual = values.get(setting.address)
            if actual != setting.value:
                check.mismatches[setting.name] = (setting.value, actual if actual is not None else -1)

        if strict:
            for address, actual in sorted(values.items()):
                if address in wanted:
                    continue
                register = reg.BY_ADDRESS.get(address)
                if register is not None and register.writable and actual != register.reset:
                    check.unexpected[register.name] = (register.reset, actual)
        return check

    def save_configuration(
        self, path: str, title: str = "", only_changed: bool = True
    ) -> str:
        """Write the radio's current registers out as a register file.

        So a radio configured by hand - or by the vendor's GUI - can be captured
        and replayed. Read-only registers are left out: a file naming one cannot
        be applied, and a captured configuration that cannot be applied is a
        trap rather than a record.

        :returns: The path written.
        """
        values = self.read_all_registers()
        text = format_register_file(
            values,
            title=title or "captured from %s on %s" % (self.board, self._transport.description),
            only_changed=only_changed,
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    # ------------------------------------------------------------------
    # Radio configuration
    # ------------------------------------------------------------------
    def _check_frequency(self, hertz: int) -> int:
        low, high = self.band
        value = int(hertz)
        if not low <= value <= high:
            raise ConfigurationError(
                "%.3f MHz is outside the %s band this board is built for "
                "(%.1f to %.1f MHz). The radio would accept it and transmit "
                "into a filter and matching network that do not pass it."
                % (value / 1e6, self.board, low / 1e6, high / 1e6)
            )
        return value

    def configure_radio(
        self,
        frequency_hz: int,
        data_rate_bps: int = 38_400,
        modulation: Union[int, str] = Modulation.GFSK_2_BT1,
        deviation_hz: int = 20_000,
        bandwidth_hz: int = 100_000,
        xtal_hz: int = DEFAULT_XTAL_HZ,
    ) -> Dict[str, int]:
        """Set up the analogue radio section, and read it back.

        :returns: What the radio says it is set to afterwards - not what it was
            asked for. The two differ whenever a setting is not reachable, and
            the read-back is the one worth recording.
        """
        code = self._modulation_code(modulation)
        self._session.execute(
            "S2LPRadioInit",
            self._check_frequency(frequency_hz),
            code,
            int(data_rate_bps),
            int(deviation_hz),
            int(bandwidth_hz),
            int(xtal_hz),
        )
        return self.radio_info()

    @staticmethod
    def _modulation_code(modulation: Union[int, str]) -> int:
        if isinstance(modulation, str):
            key = modulation.strip().lower()
            if key not in Modulation.BY_NAME:
                raise ConfigurationError(
                    "%r is not a modulation this radio has; they are %s"
                    % (modulation, ", ".join(sorted(Modulation.BY_NAME)))
                )
            return Modulation.BY_NAME[key]
        return int(modulation)

    def radio_info(self) -> Dict[str, int]:
        """Frequency, modulation, data rate, deviation and bandwidth."""
        reply = self._session.execute("S2LPRadioGetInfo")
        code = reply.number("modulation", 0)
        return {
            "frequency_hz": reply.number("frequency", 0),
            "modulation": code,
            "modulation_name": Modulation.name_of(code),
            "data_rate_bps": reply.number("datarate", 0),
            "deviation_hz": reply.number("fdev", 0),
            "bandwidth_hz": reply.number("bandwidth", 0),
        }

    @property
    def frequency_hz(self) -> int:
        """The carrier the radio is tuned to, in hertz."""
        return self._session.execute("S2LPRadioGetFrequencyBase").number("frequency")

    def set_frequency(self, hertz: int) -> int:
        """Tune the radio. Refuses a frequency this board cannot reach."""
        self._session.execute("S2LPRadioSetFrequencyBase", self._check_frequency(hertz))
        return self.frequency_hz

    @property
    def modulation(self) -> str:
        """The modulation in use, by name."""
        code = self._session.execute("S2LPRadioGetModulation").number("modulation")
        return Modulation.name_of(code)

    def set_modulation(self, modulation: Union[int, str]) -> str:
        self._session.execute("S2LPRadioSetModulation", self._modulation_code(modulation))
        return self.modulation

    @property
    def power_dbm(self) -> float:
        """Output power, in dBm."""
        return float(self._session.execute("S2LPRadioGetPALeveldBm", 0).number("power"))

    def set_power_dbm(self, dbm: float, index: int = 7) -> float:
        """Set the output power. The index is the PA ramp step ST's API takes."""
        self._session.execute("S2LPRadioSetPALeveldBm", int(round(dbm)), int(index))
        return self.power_dbm

    @property
    def rssi_dbm(self) -> float:
        """Signal strength now, in dBm - the channel, not a packet."""
        return float(self._session.execute("S2LPQiGetRssidBm").number("rssi"))

    @property
    def payload_length(self) -> int:
        """Payload length the packet handler expects, in bytes."""
        value = self._session.execute("S2LPPktBasicGetPayloadLength").number("payload_length")
        self._payload_length = value
        return value

    def set_payload_length(self, length: int) -> int:
        if not 0 < int(length) <= MAX_PAYLOAD:
            raise ConfigurationError(
                "a payload of %d byte(s) is outside what the packet handler "
                "carries (1 to %d)" % (length, MAX_PAYLOAD)
            )
        self._session.execute("S2LPPktBasicSetPayloadLength", int(length))
        self._payload_length = int(length)
        return self._payload_length

    # ------------------------------------------------------------------
    # Traffic
    # ------------------------------------------------------------------
    def transmit(self, data: Union[bytes, str], note: str = "") -> Packet:
        """Send one packet, and record it."""
        payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        if not payload:
            raise ConfigurationError("there is no such thing as an empty transmission")
        if len(payload) > MAX_PAYLOAD:
            raise ConfigurationError(
                "%d bytes is more than the firmware's command carries (%d). "
                "Send it in parts." % (len(payload), MAX_PAYLOAD)
            )
        started = time.monotonic()
        self._session.execute("S2LPSendNBytes", payload)
        return self._record(
            Packet(direction="tx", data=payload, note=note,
                   board_time_ms=int((time.monotonic() - started) * 1000))
        )

    def transmit_batch(
        self, data: Union[bytes, str], count: int, interval_ms: int = 100
    ) -> List[Packet]:
        """Send the same packet *count* times, *interval_ms* apart.

        The timing is the board's, not the host's: the loop runs in the firmware,
        so the interval is not at the mercy of the USB link.
        """
        payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        self._session.execute(
            "S2LPSendNBytesBatch", int(interval_ms), int(count), payload,
            timeout=max(self._session.timeout, count * interval_ms / 1000.0 + 5.0),
        )
        return [self._record(Packet(direction="tx", data=payload,
                                    note="batch %d of %d" % (index + 1, count)))
                for index in range(count)]

    def receive(self, length: Optional[int] = None, timeout: Optional[float] = None) -> Optional[Packet]:
        """Arm the radio and wait for one packet.

        :returns: The packet, or ``None`` if none arrived before the radio's
            own timeout. ``None`` means nothing was heard *while listening* - it
            does not mean the air was quiet.
        """
        wanted = int(length or self._payload_length or self.payload_length)
        reply = self._session.execute(
            "S2LPGetNBytes", wanted,
            timeout=timeout if timeout is not None else max(self._session.timeout, 2.0),
        )
        error = reply.hex_number("error", 0)
        if error:
            return None
        data = bytes(reply.numbers("bytes"))
        return self._record(
            Packet(
                direction="rx",
                data=data,
                rssi_dbm=rssi_dbm_from_register(reply.hex_number("rssi", 0)),
                board_time_ms=reply.hex_number("timer", 0),
                error=error,
            )
        )

    def capture(
        self,
        count: int = 10,
        timeout: float = 30.0,
        length: Optional[int] = None,
        continuous: bool = True,
        attempts: Optional[int] = None,
    ) -> Capture:
        """Receive up to *count* packets, and record every one.

        :param continuous: Keep the board in its own capture loop, so the radio
            is armed for the whole capture. This is the honest way to capture:
            with ``continuous=False`` the host re-arms between packets and
            anything arriving in those gaps is never seen by anything.
        :param attempts: Polled capture only: how many times to arm the radio
            before giving up. Bounded because an arm that finds nothing can
            return immediately, and an unbounded loop would spend the timeout
            re-arming thousands of times and call the result a capture.
        """
        wanted = int(length or self._payload_length or self.payload_length)
        started = time.monotonic()
        capture = Capture(requested=int(count))

        if continuous:
            self._session.send("S2LPGetNBytesBatch", 0, int(count))
            for reply in self._session.collect(int(count), timeout=timeout,
                                               per_reply_timeout=timeout):
                packet = self._packet_from(reply)
                if packet is not None:
                    capture.packets.append(self._record(packet))
                if time.monotonic() - started > timeout:
                    break
            if capture.count < count:
                self._session.stop()
                capture.stopped_early = True
        else:
            limit = int(attempts) if attempts else max(2 * int(count), int(count) + 8)
            listens = 0
            while (capture.count < count and listens < limit
                   and time.monotonic() - started < timeout):
                packet = self.receive(length=wanted, timeout=timeout)
                listens += 1
                if packet is not None:
                    capture.packets.append(packet)
            # Every arm after the first is preceded by an interval in which the
            # radio was not listening. That is what a gap is.
            capture.gaps = max(0, listens - 1)
            capture.stopped_early = capture.count < count

        capture.duration_s = time.monotonic() - started
        return capture

    def _packet_from(self, reply) -> Optional[Packet]:
        """One reply from a capture loop, as a packet - or ``None`` for a miss."""
        if not reply.has("bytes"):
            return None
        if reply.hex_number("error", 0):
            return None
        return Packet(
            direction="rx",
            data=bytes(reply.numbers("bytes")),
            rssi_dbm=rssi_dbm_from_register(reply.hex_number("rssi", 0)),
            board_time_ms=reply.hex_number("timer", 0),
        )

    def stop(self) -> None:
        """End a capture or a batch transmission early."""
        self._session.stop()
