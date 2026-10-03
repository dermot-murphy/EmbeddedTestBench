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

**Timestamps are the board's microsecond timer**, read when the firmware prints
a report - not a radio timestamp. Good enough to order packets and to time a
sequence; not good enough to characterise a protocol's timing, and this driver
never presents it as if it were.

**A frequency the band cannot reach is refused.** The radio will accept a
setting outside the board's filter and matching network, transmit into it, and
report exactly what it was told - while almost nothing comes out of the antenna.
The firmware does not say which board it is on, so the band is checked only
when the caller names the board; otherwise only the synthesiser's own range is.

Traces to: S2LP-FR-001 .. S2LP-FR-060, S2LP-FR-080, S2LP-FR-084, S2LP-ARC-001, S2LP-DD-S2LP,
S2LP-DD-CONFIG.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ...core.errors import ConfigurationError, InstrumentError, ProtocolError
from ...core.events import log_event
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.paths import input_paths
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
    AFTER_SHUTDOWN_EXIT,
    BOARDS,
    DEFAULT_BAUDRATE,
    DEFAULT_TIMEOUT,
    DEFAULT_XTAL_HZ,
    MANUFACTURER,
    MAX_PAYLOAD,
    MODEL,
    CRC_MODES,
    Modulation,
    Strobe,
    SYNTH_BANDS,
)
from .eeprom import BoardEeprom, parse_page0
from .packets import (
    BoardClock,
    Packet,
    PacketLog,
)
from .session import S2lpSession
from .simulator import SimulatedS2lp
from .traffic import TrafficMixin

__all__ = ["S2lpDevkit"]



class S2lpDevkit(TrafficMixin, Instrument):
    """An S2-LP development kit running ST's CLI firmware.

    :param transport: The link to the board, usually its USB serial port.
    :param board: Which kit this is, one of :data:`~.constants.BOARDS`. The
        firmware does not report it, so it is the caller's to give; without it
        the board is unknown and only the synthesiser's range is checked.
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
    EVENT_SOURCE = "RF"

    def __init__(
        self,
        transport: Transport,
        board: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(auto_check_errors=False)
        board = (board or "").strip()
        if board and board not in BOARDS:
            raise ConfigurationError(
                "%r is not a kit board this driver knows; they are %s"
                % (board, ", ".join(sorted(BOARDS)))
            )
        self._transport = transport
        self._session = S2lpSession(transport, timeout=timeout)
        self._adopt(transport, self._session)
        self._board = board
        #: What identification read: ST's library version text, the radio's
        #: version byte, the crystal frequency in hertz, and the board EEPROM.
        self._facts: Dict[str, Any] = {"library": "", "silicon": 0, "xtal_hz": 0,
                                       "eeprom": None}
        self._clock = BoardClock()
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
        """Identify the firmware, the radio, its crystal and the board's band.

        ``SdkEvalRfboardIdentification`` sets up the firmware's crystal
        detection, and answers with no tags. The band comes from the board's
        EEPROM instead (#80), and a board named by the caller must agree with it.
        """
        self._session.execute("SdkEvalRfboardIdentification", DEFAULT_XTAL_HZ)
        xtal_hz = self._session.execute("S2LPRadioGetXtalFrequency").hex_number("value")

        library = self._session.execute("S2LPGetLibVersion").hex_number("value")
        library_text = "%d.%d.%d" % ((library >> 16) & 0xFF, (library >> 8) & 0xFF,
                                     library & 0xFF)
        silicon = self._session.execute("S2LPGetVersion").hex_number("value")
        self._facts.update(library=library_text, silicon=silicon & 0xFF, xtal_hz=xtal_hz,
                           eeprom=self._read_eeprom())
        self._check_board_against_eeprom()
        if (silicon >> 8) & 0xFF != 0x03:
            raise InstrumentError(
                "the radio reports part number 0x%02X; an S2-LP is 0x03"
                % ((silicon >> 8) & 0xFF)
            )

        firmware = ""
        try:
            firmware = "%02X" % self._session.execute("SdkEvalGetVersion").hex_number("version")
        except (ProtocolError, InstrumentError):      # an older CLI build
            self._logger.debug("the board did not report a motherboard version")

        raw = "%s,%s,S2-LP 0x%02X,library %s,board %s,XTAL %d Hz" % (
            MANUFACTURER, self._board or MODEL, self._facts["silicon"], self._facts["library"],
            firmware or "?", xtal_hz)
        return InstrumentIdentity(
            raw=raw,
            manufacturer=MANUFACTURER,
            model=self._board or MODEL,
            serial_number="",
            firmware=firmware,
        )

    def _read_eeprom(self) -> Optional[BoardEeprom]:
        """Page 0 of the board's EEPROM, or ``None`` where it cannot be read."""
        try:
            reply = self._session.execute("EepromReadPage", 0, 0, 32)
        except (ProtocolError, InstrumentError):         # a build without the command
            self._logger.debug("the board's EEPROM could not be read")
            return None
        return parse_page0(reply.numbers("Data"))

    def _check_board_against_eeprom(self) -> None:
        eeprom = self._facts["eeprom"]
        if self._board and eeprom is not None and not eeprom.matches(self._board):
            raise ConfigurationError(
                "%s is a %.0f to %.0f MHz board, but this kit's EEPROM says it was "
                "built for %.0f MHz. Name the board that is attached, or none."
                % (self._board, BOARDS[self._board][0] / 1e6, BOARDS[self._board][1] / 1e6,
                   eeprom.band_hz / 1e6))

    @property
    def eeprom(self) -> Optional[BoardEeprom]:
        """What the board's EEPROM said at connection, or ``None``."""
        return self._facts["eeprom"]

    def reset(self, settle: float = 0.2) -> None:
        """Reset the radio's digital section (the ``SRES`` strobe).

        **This does not restore register defaults.** ST's own command header
        describes ``SRES`` as a "reset of all digital part, except SPI
        registers", so a radio reset this way comes back configured exactly as
        it was. For defaults use :meth:`restore_defaults` (write them) or
        :meth:`power_cycle` (a real power-on reset).
        """
        self.strobe(Strobe.RESET)
        if settle > 0:
            time.sleep(settle)

    def power_cycle(self, settle: float = 0.1) -> None:
        """Take the radio through shutdown and back: a power-on reset.

        This is the only operation that returns the bits a register write
        cannot reach. It is also the most disruptive: the radio comes back with
        its crystal restarting.

        **It does not leave every register at its datasheet default.** ST's
        firmware writes some on the way out of shutdown; on a kit, the ten in
        :data:`~.constants.AFTER_SHUTDOWN_EXIT` came back set. Use
        :meth:`restore_defaults` when datasheet defaults are what is wanted.
        """
        self._session.execute("SdkEvalSdn", 1)
        if settle > 0:
            time.sleep(settle)
        self._session.execute("SdkEvalSdn", 0)
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
        """Which kit board this is, as the caller named it; ``""`` if unknown."""
        return self._board

    @property
    def band(self) -> Optional[Tuple[int, int]]:
        """The board's usable frequency range in hertz, or ``None`` if unknown.

        From the board the caller named, or else from the board's EEPROM.
        """
        if self._board:
            return BOARDS.get(self._board)
        eeprom = self._facts["eeprom"]
        return eeprom.band_range_hz if eeprom is not None else None

    @property
    def xtal_hz(self) -> int:
        """The crystal frequency the firmware uses, in hertz."""
        return self._facts["xtal_hz"]

    @property
    def library_version(self) -> str:
        """ST's S2-LP library version in the firmware, e.g. ``"1.3.5"``."""
        return self._facts["library"]

    @property
    def silicon_version(self) -> int:
        """The radio's DEVICE_INFO0 version byte, e.g. ``0xC1``."""
        return self._facts["silicon"]

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
        # Every packet sent or received, as a structured event-log record, so
        # a test run viewer can decode and list the frames without the
        # driver's packet log (#139). Raw lines alone do not carry the decode.
        log_event(self._logger, "rf_packet", "packet %s" % packet, packet.as_dict(),
                  level=logging.DEBUG)
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

    def read_setup(self) -> Dict[str, Any]:
        """The kit's RF setup and every register, also logged as an ``rf_setup`` record.

        What ST's GUI shows on its first screen: the radio's settings, each
        register, the output power and the board's EEPROM. Logged so a reader of
        the event log - the test run viewer's ST GUI page (#157) - has it
        without the kit's port, which belongs to the run.
        """
        max_index = self.read_field("PA_POWER0", "PA_LEVEL_MAX_IDX")
        board = self.eeprom
        setup = {
            "radio": self.radio_info(),
            "registers": self.read_all_registers(),
            "power_dbm": self.power_level_dbm(max_index),
            "eeprom": board.as_dict() if board is not None else None,
        }
        log_event(self._logger, "rf_setup", "RF setup read: %d registers"
                  % len(setup["registers"]),
                  dict(setup, registers={"%d" % address: value for address, value
                                         in setup["registers"].items()}))
        return setup

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
        self,
        values: Optional[Dict[int, int]] = None,
        expected: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Tuple[int, int]]:
        """Writable registers not at their reset value: name to (reset, value).

        The short answer to "what has this radio been configured to do?".
        Read-only registers are left out. They hold status - RSSI, interrupt
        flags, the silicon version - which a live radio never holds at a
        "reset value", so including them made every reset check fail on a kit.

        :param expected: Register name to the value to compare against instead
            of its reset value, for a state that is not the datasheet's.
        """
        if values is None:
            values = self.read_all_registers()
        overrides = expected or {}
        differing = {}
        for address, value in sorted(values.items()):
            register = reg.BY_ADDRESS.get(address)
            if register is None or not register.writable:
                continue
            wanted = overrides.get(register.name, register.reset)
            if value != wanted:
                differing[register.name] = (wanted, value)
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
    @input_paths("source")
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

    #: What ``apply_configuration`` may do before it writes anything.
    RESET_MODES = ("none", "defaults", "power")

    @input_paths("source")
    def apply_configuration(
        self,
        source: Union[str, RegisterConfiguration],
        verify: bool = True,
        reset: Union[bool, str] = "none",
    ) -> ConfigurationCheck:
        """Write the register values a file asks for, and check they took.

        Written in the file's own order, because some settings only take effect
        when written after another and a file that works should be applied the
        way it was written. Consecutive registers are still sent together.

        :param reset: What to do first.

            * ``"none"`` (the default, also ``False``) - write only what the
              file names and leave every other register as it is. What the
              radio was doing before is carried into the test.
            * ``"defaults"`` (also ``True``) - write every writable register
              back to its documented reset value first, so the radio holds
              exactly the file's settings on top of a known state. This is what
              a test usually wants: it is what makes a partial file
              deterministic, and what makes a strict check afterwards mean
              something.
            * ``"power"`` - take the radio through shutdown and back, a real
              power-on reset, before writing. The most disruptive. ST's
              firmware sets ten registers on the way out of shutdown
              (:data:`~.constants.AFTER_SHUTDOWN_EXIT`), so the radio is then at
              the defaults with those ten set, not at the datasheet defaults.

            Either reset is **confirmed** before the file is applied: the
            registers are read back and must actually be in the state the
            reset promises.
            "The reset was commanded" and "the radio is at defaults" are
            different facts, and the second is the one the file is written on
            top of.
        :param verify: Read the registers back afterwards. On by default: a
            write to this radio is acknowledged by the firmware, not by the
            radio, so "the command was accepted" and "the register holds the
            value" are different facts.
        :raises InstrumentError: if the reset did not take, or a register did
            not take the value asked for, naming every one that differs.
        """
        configuration = self.load_configuration(source)
        self._reset_before_configuring(self._reset_mode(reset))
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

    @classmethod
    def _reset_mode(cls, reset: Union[bool, str]) -> str:
        """Normalise the ``reset`` argument, refusing anything else."""
        if reset is True:
            return "defaults"
        if reset is False or reset is None:
            return "none"
        mode = str(reset).strip().lower()
        if mode not in cls.RESET_MODES:
            raise ConfigurationError(
                "%r is not a way to reset this radio; the choices are %s"
                % (reset, ", ".join(cls.RESET_MODES))
            )
        return mode

    def _reset_before_configuring(self, mode: str) -> None:
        """Put the radio at its defaults, and confirm that it is."""
        if mode == "none":
            return
        expected: Dict[str, int] = {}
        if mode == "power":
            self.power_cycle()
            expected = AFTER_SHUTDOWN_EXIT
        else:
            self.restore_defaults()

        remaining = self.registers_differing_from_reset(expected=expected)
        if remaining:
            raise InstrumentError(
                "the radio is not in the state a %s reset leaves it in: %s. "
                "The configuration was not applied, because it would have been "
                "written on top of a state nobody established."
                % (mode, ", ".join(
                    "%s = 0x%02X (expected 0x%02X)" % (name, value, default)
                    for name, (default, value) in sorted(remaining.items())))
            )

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

    @input_paths("source")
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
            title=title or "captured from %s on %s" % (self._board or MODEL,
                                                       self._transport.description),
            only_changed=only_changed,
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    # ------------------------------------------------------------------
    # Radio configuration
    # ------------------------------------------------------------------
    def _check_frequency(self, hertz: int) -> int:
        value = int(hertz)
        if self.band is None:
            if not any(low <= value <= high for low, high in SYNTH_BANDS):
                raise ConfigurationError(
                    "%.3f MHz is outside every range the S2-LP synthesiser "
                    "tunes (%s)" % (value / 1e6, ", ".join(
                        "%.0f to %.0f MHz" % (low / 1e6, high / 1e6)
                        for low, high in SYNTH_BANDS))
                )
            return value
        low, high = self.band
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
        reply = self._session.execute(
            "S2LPRadioInit",
            self._check_frequency(frequency_hz),
            code,
            int(data_rate_bps),
            int(deviation_hz),
            int(bandwidth_hz),
            int(xtal_hz),
        )
        error = reply.hex_number("error", 0)
        if error:
            raise ConfigurationError(
                "the radio refused these settings (S2LPRadioInit error 0x%02X): "
                "%.3f MHz, modulation 0x%02X, %d bps, %d Hz deviation, %d Hz "
                "bandwidth" % (error, frequency_hz / 1e6, code, data_rate_bps,
                               deviation_hz, bandwidth_hz)
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
        """Frequency, modulation, data rate, deviation, bandwidth and crystal.

        Every field is written in hex by the firmware, with no ``0x``.
        """
        reply = self._session.execute("S2LPRadioGetInfo")
        code = reply.hex_number("Modulation")
        return {
            "frequency_hz": reply.hex_number("Frequency_base"),
            "modulation": code,
            "modulation_name": Modulation.name_of(code),
            "data_rate_bps": reply.hex_number("Data_rate"),
            "deviation_hz": reply.hex_number("Frequency_deviation"),
            "bandwidth_hz": reply.hex_number("Channel_filter_bandwidth"),
            "xtal_hz": reply.hex_number("XTAL_frequency"),
        }

    @property
    def frequency_hz(self) -> int:
        """The carrier the radio is tuned to, in hertz."""
        return self._session.execute("S2LPRadioGetFrequencyBase").hex_number("value")

    def set_frequency(self, hertz: int) -> int:
        """Tune the radio. Refuses a frequency this board cannot reach."""
        self._session.execute("S2LPRadioSetFrequencyBase", self._check_frequency(hertz))
        return self.frequency_hz

    @property
    def modulation(self) -> str:
        """The modulation in use, by name."""
        code = self._session.execute("S2LPRadioGetModulation").hex_number("value")
        return Modulation.name_of(code)

    def set_modulation(self, modulation: Union[int, str]) -> str:
        self._session.execute("S2LPRadioSetModulation", self._modulation_code(modulation))
        return self.modulation

    @property
    def power_dbm(self) -> float:
        """Output power of PA slot 0, in dBm."""
        return self.power_level_dbm(0)

    def power_level_dbm(self, index: int) -> float:
        """Output power of one PA slot (0 to 7), in dBm.

        The firmware answers in tenths of a dBm, as signed decimal.
        """
        reply = self._session.execute("S2LPRadioGetPALeveldBm", int(index))
        return reply.number("value") / 10.0

    def set_power_dbm(self, dbm: float, index: int = 7) -> float:
        """Set the output power, in whole dBm, which is all the command takes.

        :param index: The PA slot to set and use as the maximum, 0 to 7.
        :returns: The power the radio reports for that slot afterwards.
        """
        self._session.execute("S2LPRadioSetPALeveldBm", int(round(dbm)), int(index))
        return self.power_level_dbm(index)

    @property
    def rssi_dbm(self) -> float:
        """Signal strength now, in dBm - the channel, not a packet."""
        return self._session.execute("S2LPQiGetRssidBm").real("value")

    @property
    def payload_length(self) -> int:
        """Payload length the packet handler expects, in bytes."""
        value = self._session.execute("S2LPPktBasicGetPayloadLength").hex_number("value")
        self._payload_length = value
        return value

    def configure_packets(  # pylint: disable=too-many-arguments
        self,
        preamble: int = 64,
        sync_bits: int = 32,
        sync_word: int = 0x88888888,
        *,
        variable_length: bool = False,
        crc: Union[int, str] = "8",
        address: bool = False,
        fec: bool = False,
        whitening: bool = False,
    ) -> Dict[str, int]:
        """Set up the basic packet handler (``S2LPPktBasicInit``).

        This is also what sets the radio's TX source to its FIFO; until it, or
        a register file, has done so, the radio sends a PN9 test pattern.

        :param preamble: Written to PREAMBLE_LEN as given; the read-back
            reports the same number.
        :param sync_bits: Sync word length in bits.
        :param variable_length: A length byte after the sync word, rather
            than the fixed PCKTLEN.
        :param crc: A :data:`~.constants.CRC_MODES` name, or its code.
        :returns: What :meth:`packet_info` reads back.
        """
        if isinstance(crc, str):
            if crc not in CRC_MODES:
                raise ConfigurationError(
                    "%r is not a CRC mode; they are %s" % (crc, ", ".join(CRC_MODES)))
            crc = CRC_MODES[crc]
        self._session.execute(
            "S2LPPktBasicInit", int(preamble), int(sync_bits), int(sync_word),
            int(bool(variable_length)), 0, int(crc), int(bool(address)),
            int(bool(fec)), int(bool(whitening)))
        return self.packet_info()

    def packet_info(self) -> Dict[str, int]:
        """The basic packet handler's settings, as the firmware reports them."""
        reply = self._session.execute("S2LPPktBasicGetInfo")
        return {tag: reply.hex_number(tag) for tag in (
            "preamble_length", "sync_length", "sync_word", "length_mode",
            "length_size", "crc_mode", "address", "fec", "whitening")}

    def set_payload_length(self, length: int) -> int:
        if not 0 < int(length) <= MAX_PAYLOAD:
            raise ConfigurationError(
                "a payload of %d byte(s) is outside what the packet handler "
                "carries (1 to %d)" % (length, MAX_PAYLOAD)
            )
        self._session.execute("S2LPPktBasicSetPayloadLength", int(length))
        self._payload_length = int(length)
        return self._payload_length
