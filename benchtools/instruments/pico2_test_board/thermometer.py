"""Driver for the Raspberry Pi Pico 2 + DollaTek SHT30-D bench thermometer.

The Pico runs ``firmware/pico2_test_board`` and appears as a USB CDC serial port.
It speaks a line protocol, one command per line and one reply per command, in
two forms:

* ``rd <option>`` reads one value and is answered ``ACK rd <option> = <value>``,
  or ``NAK rd <option> = Error`` for an option the firmware does not know. The
  options are ``name``, ``copyright``, ``version``, ``sha``, ``temperature``
  and the LEDs ``led-red``, ``led-yellow`` and ``led-green`` (``on``/``off``).
* ``wr <led> on|off`` switches an LED and is answered
  ``ACK wr <led> = <state read back>``, or ``NAK wr <led> = Error`` for a
  value other than ``on`` or ``off`` (#328). ``wr`` of any other option is a
  generator setting (below).
* The control commands (``status``, ``sreset``, ``ecureset``, ``bootsel``) are
  answered ``ok ...`` or ``err <code> <text>``, values as ``key=value`` tokens.
* The frequency generator is controlled in the style of UDS: ``wr`` stores a
  setting, ``rd`` reads it back and ``routine`` starts, stops and reports it.
  Each is answered ``ACK <command> = <value>`` or ``NAK <command> = Error``.

**A failed reading is an error, never a stale value.** When the firmware cannot
read the sensor - it does not acknowledge, a frame fails its CRC, or the bus
times out - ``rd temperature`` answers ``Error``, and the driver raises
:class:`NoReadingError`, so that a test cannot mistake "no reading" for "same
as last time".

Traces to: PICO-FR-040 .. PICO-FR-049, PICO-FR-085, PICO-ARC-001, PICO-DD-DRIVER.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from ...core.errors import InstrumentError, ProtocolError
from ...core.events import log_reading
from ...core.instrument import InstrumentIdentity
from ...core.scpi import ScpiInstrument
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    DEFAULT_BAUDRATE,
    ERRORS,
    FGEN_CHANNELS,
    FGEN_DEFAULT_CHANNEL,
    FGEN_SETTINGS,
    LED_OFF,
    LED_ON,
    LED_OPTIONS,
    MANUFACTURER,
    MODEL,
    NAME,
    RD_ERROR,
    STATUS_BITS,
    led_option,
)
from .simulator import SimulatedPico2TestBoard

__all__ = [
    "Pico2TestBoard",
    "FirmwareInfo",
    "Reading",
    "SensorStatus",
    "SensorError",
    "NoReadingError",
    "RdRefusedError",
    "CommandRefusedError",
    "FreqStatus",
    "WrRefusedError",
]

#: Informational lines (``help`` only) are skipped when looking for a reply.
_INFO_PREFIX = "#"

#: Lines read while looking for a reply before giving up.
_MAX_SKIPPED_LINES = 32

#: ``ACK wr freq 1 = 1000.00``: the verdict, the command echoed and the value.
_ACK_REPLY = re.compile(r"^(ACK|NAK) (.+?) = (.*)$")

#: ``Running, sine, 999.98 Hz``, or a status with nothing after it.
_RESULT_VALUE = re.compile(r"^([^,]+)(?:, (\w+), (\d+\.\d{2}) Hz)?$")

#: A value on the link: a number, or text such as ``20k`` or ``sine``.
ValueType = Union[int, float, str]

#: What ``rd temperature`` reports when it has a reading: two decimal places.
_TEMPERATURE = re.compile(r"^-?\d+\.\d{2}$")


class SensorError(InstrumentError):
    """The firmware answered ``err``.

    :ivar code: The protocol error code; see :data:`.constants.ERRORS`.
    """

    def __init__(self, code: int, text: str, command: str) -> None:
        super().__init__(
            "%r failed: err %d %s" % (command, code, text), [(code, text)]
        )
        self.code = code
        self.text = text
        self.command = command

    @property
    def symbol(self) -> str:
        """The protocol.h name of the error, e.g. ``PROTO_ERR_NO_SENSOR``."""
        return ERRORS.get(self.code, "unknown")


class NoReadingError(InstrumentError):
    """``rd temperature`` answered ``Error``: the sensor could not be read."""


class CommandRefusedError(InstrumentError):
    """The firmware answered ``NAK``: a value out of range, an unknown setting,
    or a routine that cannot start."""


class RdRefusedError(CommandRefusedError):
    """The firmware answered ``NAK``: it does not know the ``rd`` option."""


class WrRefusedError(CommandRefusedError):
    """The firmware answered ``NAK`` to ``wr``: an unknown option or value."""


@dataclass(frozen=True)
class FirmwareInfo:
    """What ``rd name``, ``rd copyright``, ``rd version`` and ``rd sha`` report."""

    name: str
    copyright: str
    version: str
    sha: str

    def as_dict(self) -> Dict[str, object]:
        """The identity as a JSON-ready dictionary."""
        return {
            "name": self.name,
            "copyright": self.copyright,
            "version": self.version,
            "sha": self.sha,
        }


@dataclass(frozen=True)
class Reading:
    """One temperature measurement, as ``rd temperature`` reported it."""

    temperature: float
    text: str
    timestamp: float

    def as_dict(self) -> Dict[str, object]:
        """The reading as a JSON-ready dictionary."""
        return {
            "temperature_c": self.temperature,
            "text": self.text,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class SensorStatus:
    """The decoded SHT3x status register."""

    raw: int

    def flag(self, name: str) -> bool:
        """``True`` if status bit *name* (a key of ``STATUS_BITS``) is set."""
        return bool(self.raw & STATUS_BITS[name])

    def as_dict(self) -> Dict[str, object]:
        """The raw word and every decoded flag, JSON-ready."""
        payload: Dict[str, object] = {"raw": "0x%04X" % self.raw}
        payload.update({name: self.flag(name) for name in STATUS_BITS})
        return payload


@dataclass(frozen=True)
class FreqStatus:
    """One channel's line from ``routine freq results``.

    :ivar status: ``Not Started``, ``Running``, ``Aborted`` or ``Complete``.
    :ivar wave: The waveform last generated; ``None`` if ``Not Started``.
    :ivar frequency: The frequency last generated, in hertz; ``None`` if
        ``Not Started``.
    """

    channel: int
    status: str
    wave: Optional[str]
    frequency: Optional[float]

    def as_dict(self) -> Dict[str, object]:
        """The status as a JSON-ready dictionary."""
        return {
            "channel": self.channel,
            "status": self.status,
            "wave": self.wave,
            "frequency_hz": self.frequency,
        }


def format_value(value: ValueType) -> str:
    """A value as the link writes it: at most three places, no exponent."""
    if isinstance(value, str):
        return value
    text = "%.3f" % float(value)
    return text.rstrip("0").rstrip(".")


def parse_fields(reply: str) -> Dict[str, str]:
    """Split the ``key=value`` tokens of an ``ok`` reply into a dictionary."""
    fields: Dict[str, str] = {}
    for token in reply.split()[1:]:
        key, _, value = token.partition("=")
        fields[key] = value
    return fields


# ---------------------------------------------------------------------------
class Pico2TestBoard(ScpiInstrument):  # pylint: disable=too-many-public-methods
    """A Pico 2 + SHT30-D thermometer.

    Example::

        from benchtools.instruments.pico2_test_board import Pico2TestBoard

        with Pico2TestBoard.connect("/dev/ttyACM0") as thermometer:
            info = thermometer.firmware_info()
            print(info.name, info.version, info.sha)
            print("%.2f C" % thermometer.temperature())
    """

    SIMULATOR_CLASS = SimulatedPico2TestBoard
    MODEL_NAME = "PICO2 Test Board"
    EVENT_SOURCE = "TEMP"

    def __init__(
        self,
        transport: Transport,
        auto_check_errors: bool = False,
        owns_transport: bool = True,
    ) -> None:
        super().__init__(
            transport,
            auto_check_errors=auto_check_errors,
            owns_transport=owns_transport,
        )
        self._info: FirmwareInfo = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(  # pylint: disable=arguments-differ
        cls,
        resource: str = "sim://",
        timeout: float = 2.0,
        baudrate: int = DEFAULT_BAUDRATE,
        initialise: bool = True,
        **kwargs,
    ) -> "Pico2TestBoard":
        """Open a thermometer.

        :param resource: ``/dev/ttyACM0``, ``COM5``, ``serial://COM5`` or
            ``sim://``. A bare port name is taken as a serial port.
        :param baudrate: Needed to open the port; USB CDC ignores it.
        """
        target = cls._normalise_resource(resource)
        transport = open_transport(
            target,
            timeout=timeout,
            open_now=False,
            responder_factory=cls.SIMULATOR_CLASS,
            **({"baudrate": baudrate} if target.startswith("serial://") else {}),
        )
        instrument = cls(transport, **kwargs)
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

    def _post_open(self) -> None:
        """Identify the thermometer, and check that it is this firmware.

        No ``*CLS``: the firmware is not SCPI, and would answer it with
        ``err 1``. A device that answers ``rd name`` with another name is
        refused rather than half-understood.
        """
        info = self.firmware_info(refresh=True)
        if info.name != NAME:
            raise ProtocolError("device reports name %r, not %r" % (info.name, NAME))
        self.identify(refresh=True)

    # ------------------------------------------------------------------
    # Primitive I/O
    # ------------------------------------------------------------------
    def _read_reply(self, command: str) -> str:
        """Read lines until the reply to *command*, skipping ``#`` lines."""
        for _ in range(_MAX_SKIPPED_LINES):
            line = self._transport.read_message().decode("ascii", errors="replace").strip()
            self._logger.debug("<< %s", line)
            if not line or line.startswith(_INFO_PREFIX):
                continue
            return line
        raise ProtocolError("no reply to %r among %d lines" % (command, _MAX_SKIPPED_LINES))

    def _send(self, command: str) -> str:
        self._logger.debug(">> %s", command)
        self._transport.write(command.encode("ascii"))
        return self._read_reply(command)

    def execute(self, command: str) -> Dict[str, str]:
        """Send a control *command* and return the fields of its ``ok`` reply.

        :raises SensorError: if the firmware answered ``err``.
        :raises ProtocolError: if it answered neither ``ok`` nor ``err``.
        """
        reply = self._send(command)
        if reply == "ok" or reply.startswith("ok "):
            return parse_fields(reply)
        if reply.startswith("err "):
            parts = reply.split(" ", 2)
            try:
                code = int(parts[1])
            except (IndexError, ValueError) as exc:
                raise ProtocolError("malformed error reply to %r: %r" % (command, reply)) from exc
            raise SensorError(code, parts[2] if len(parts) > 2 else "", command)
        raise ProtocolError("unexpected reply to %r: %r" % (command, reply))

    def rd(  # pylint: disable=invalid-name
        self, option: str, channel: Optional[int] = None
    ) -> str:
        """Send ``rd <option> [<channel>]`` and return the value of its ``ACK``.

        A generator setting is reported for *channel*, channel 1 if ``None``.

        :raises RdRefusedError: if the firmware answered ``NAK``.
        :raises SensorError: if it answered ``err`` (a malformed command).
        :raises ProtocolError: if the reply is for another option, or is
            neither ``ACK`` nor ``NAK``.
        """
        command = "rd %s" % option
        expected = option
        if channel is not None:
            command = "%s %d" % (command, channel)
            expected = "%s %d" % (option, channel)
        elif option in FGEN_SETTINGS:
            expected = "%s %d" % (option, FGEN_DEFAULT_CHANNEL)
        return self._acknowledged(command, self._send(command), "rd %s" % expected,
                                  RdRefusedError)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def firmware_info(self, refresh: bool = False) -> FirmwareInfo:
        """The name, copyright, version and commit SHA of the firmware."""
        if self._info is None or refresh:
            self._info = FirmwareInfo(
                name=self.rd("name"),
                copyright=self.rd("copyright"),
                version=self.rd("version"),
                sha=self.rd("sha"),
            )
        return self._info

    @property
    def name(self) -> str:
        """What ``rd name`` reports."""
        return self.firmware_info().name

    @property
    def version(self) -> str:
        """The firmware version, e.g. ``V1.00.0000``."""
        return self.firmware_info().version

    @property
    def sha(self) -> str:
        """The commit the firmware was built from, seven hex digits."""
        return self.firmware_info().sha

    def _read_identity(self) -> InstrumentIdentity:
        info = self.firmware_info()
        return InstrumentIdentity(
            raw="%s %s (%s)" % (info.name, info.version, info.sha),
            manufacturer=MANUFACTURER,
            model="%s/SHT30" % MODEL,
            serial_number="",
            firmware="%s (%s)" % (info.version, info.sha),
        )

    def read_event_queue(self) -> List[Tuple[int, str]]:
        """The firmware has no error queue: every failure is in its reply."""
        return []

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------
    def read(self) -> Reading:
        """Take one measurement with ``rd temperature``.

        :raises NoReadingError: if the firmware answered ``Error``.
        :raises ProtocolError: if the value is not a number to two places.
        """
        text = self.rd("temperature")
        if text == RD_ERROR:
            raise NoReadingError("rd temperature: the sensor could not be read")
        if not _TEMPERATURE.match(text):
            raise ProtocolError("rd temperature: %r is not degrees to two places" % text)
        log_reading(self._logger, "temperature", float(text), "degC", text=text)
        return Reading(float(text), text, time.time())

    def temperature(self) -> float:
        """The temperature now, in degrees Celsius."""
        return self.read().temperature

    def status(self) -> SensorStatus:
        """The sensor's status register."""
        fields = self.execute("status")
        try:
            return SensorStatus(int(self._field(fields, "status", "status"), 16))
        except ValueError as exc:
            raise ProtocolError("malformed 'status' reply: %r" % fields) from exc

    @staticmethod
    def _field(fields: Dict[str, str], key: str, command: str) -> str:
        if key not in fields:
            raise ProtocolError("%r reply has no %r field: %r" % (command, key, fields))
        return fields[key]

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # LEDs (#328)
    # ------------------------------------------------------------------
    def led(self, colour: str) -> bool:
        """Whether LED *colour* (``red``, ``yellow`` or ``green``) is lit.

        :raises ValueError: for another colour, before anything is sent.
        :raises ProtocolError: if the firmware reports neither ``on`` nor ``off``.
        """
        option = led_option(colour)
        return self._led_state(option, self.rd(option))

    def set_led(self, colour: str, lit: bool) -> bool:
        """Light (*lit* True) or extinguish LED *colour*; return the state read back.

        The argument is *lit*, not *on*: YAML reads a bare ``on`` key as
        ``True``, so a test sequence could not name it (#330).

        :raises ValueError: for another colour, before anything is sent.
        :raises ProtocolError: if the state read back is not the one written.
        """
        option = led_option(colour)
        wanted = LED_ON if lit else LED_OFF
        state = self._led_state(option, self.wr(option, wanted))
        if state != bool(lit):
            raise ProtocolError("wr %s %s: the LED reads back %s"
                                % (option, wanted, LED_ON if state else LED_OFF))
        return state

    @staticmethod
    def _led_state(option: str, value: str) -> bool:
        if value not in (LED_ON, LED_OFF):
            raise ProtocolError("%s: %r is neither %r nor %r" % (option, value, LED_ON, LED_OFF))
        return value == LED_ON

    def soft_reset_sensor(self) -> None:
        """Soft-reset the SHT30; the Pico keeps running."""
        self.execute("sreset")

    def reset(self, settle: float = 0.0) -> None:  # type: ignore[override]
        """Reboot the Pico (``ecureset``). The port re-enumerates; reconnect afterwards."""
        self.execute("ecureset")
        self._info = None
        if settle > 0:
            time.sleep(settle)

    def enter_bootloader(self) -> None:
        """Reboot into the USB bootloader, ready for a new ``.uf2``."""
        self.execute("bootsel")
        self._info = None

    # ------------------------------------------------------------------
    # Frequency generator
    # ------------------------------------------------------------------
    @staticmethod
    def _acknowledged(command: str, reply: str, expected: str,
                      refused=CommandRefusedError) -> str:
        """The value of an ``ACK`` to *command*, which must echo *expected*.

        :raises CommandRefusedError: (or *refused*, a subclass of it) if the
            firmware answered ``NAK``.
        :raises SensorError: if it answered ``err`` (a malformed command).
        :raises ProtocolError: if the reply is for another command, or is
            neither ``ACK`` nor ``NAK``.
        """
        match = _ACK_REPLY.match(reply)
        if match is None:
            if reply.startswith("err "):
                parts = reply.split(" ", 2)
                raise SensorError(int(parts[1]) if parts[1].isdigit() else -1,
                                  parts[2] if len(parts) > 2 else "", command)
            raise ProtocolError("unexpected reply to %r: %r" % (command, reply))
        verdict, echoed, value = match.groups()
        if echoed != expected:
            raise ProtocolError("reply to %r is for %r: %r" % (command, echoed, reply))
        if verdict == "NAK":
            raise refused("%r refused: %s" % (command, reply))
        return value

    def wr(  # pylint: disable=invalid-name
        self, setting: str, value: ValueType, channel: Optional[int] = None
    ) -> str:
        """Send ``wr`` and return the value the ``ACK`` reports.

        For an LED (``led-red``, ``led-yellow``, ``led-green``; #328) this is
        ``wr <led> on|off``, with no channel, and the value is the state read
        back after the write. For a generator setting it is
        ``wr <setting> <channel> <value>``, *channel* 1 if ``None``, and the
        value is the one stored; a number may be given as text with a ``k``
        suffix for a frequency, so ``wr("freq", "1.5k")`` is the same as
        ``wr("freq", 1500)``. A setting takes effect at the next start.

        :raises WrRefusedError: if the firmware answered ``NAK``: an unknown
            option, or a value the LED or the channel cannot use.
        :raises ValueError: for a channel given with an LED, before sending.
        """
        if setting in LED_OPTIONS and channel is not None:
            raise ValueError("%s takes no channel" % setting)
        if setting not in FGEN_SETTINGS and channel is None:
            # An LED, or an option the firmware will NAK as it was sent.
            command = "wr %s %s" % (setting, format_value(value))
            expected = "wr %s" % setting
        else:
            channel = FGEN_DEFAULT_CHANNEL if channel is None else channel
            command = "wr %s %d %s" % (setting, channel, format_value(value))
            expected = "wr %s %d" % (setting, channel)
        return self._acknowledged(command, self._send(command), expected, WrRefusedError)

    def freq_start(self, channel: int = FGEN_DEFAULT_CHANNEL) -> None:
        """Start *channel* with its stored settings.

        :raises CommandRefusedError: if it is running continuously.
        """
        command = "routine freq start %d" % channel
        self._acknowledged(command, self._send(command), command)

    def start_freq(  # pylint: disable=too-many-arguments
        self,
        channel: int,
        freq: ValueType,
        cycles: Optional[int] = None,
        wave: str = "square",
        **options: ValueType,
    ) -> None:
        """Write the settings of *channel* and start it.

        :param freq: The frequency in hertz, or text such as ``"1.5k"``.
        :param cycles: Cycles to generate; ``None`` runs until aborted.
        :param wave: ``square``, ``sine``, ``triangle``, ``sawtooth`` or
            ``sine2``.
        :param options: Other settings to write first: ``duty``, ``amp``,
            ``freq2`` and ``ratio``.
        :raises CommandRefusedError: if a value is refused, or if *channel* is
            running continuously.
        """
        self.wr("wave", wave, channel)
        self.wr("freq", freq, channel)
        self.wr("cycles", 0 if cycles is None else cycles, channel)
        for setting, value in options.items():
            self.wr(setting, value, channel)
        self.freq_start(channel)

    def abort_freq(self, channel: Optional[int] = None) -> None:
        """Stop *channel*, or every channel if ``None``."""
        command = "routine freq abort"
        if channel is not None:
            command = "%s %d" % (command, channel)
        self._acknowledged(command, self._send(command), command)

    def abort_all(self) -> None:
        """Stop every running routine, of every kind."""
        command = "routine all abort"
        self._acknowledged(command, self._send(command), command)

    def _parse_status(self, command: str, reply: str, channel: int) -> FreqStatus:
        value = self._acknowledged(command, reply, "routine freq results %d" % channel)
        match = _RESULT_VALUE.match(value)
        if match is None:
            raise ProtocolError("malformed reply to %r: %r" % (command, reply))
        status, wave, frequency = match.groups()
        return FreqStatus(channel, status, wave, None if frequency is None else float(frequency))

    def freq_status(
        self, channel: Optional[int] = None
    ) -> Union[FreqStatus, List[FreqStatus]]:
        """The status of *channel*, or a list with every channel if ``None``."""
        if channel is not None:
            command = "routine freq results %d" % channel
            return self._parse_status(command, self._send(command), channel)
        command = "routine freq results"
        replies = [self._send(command)]
        replies.extend(self._read_reply(command) for _ in FGEN_CHANNELS[1:])
        return [self._parse_status(command, reply, number)
                for reply, number in zip(replies, FGEN_CHANNELS)]
