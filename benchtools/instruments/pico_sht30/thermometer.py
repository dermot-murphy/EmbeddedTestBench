"""Driver for the Raspberry Pi Pico 2 + DollaTek SHT30-D bench thermometer.

The Pico runs ``firmware/pico_sht30`` and appears as a USB CDC serial port.
It speaks a line protocol, one command per line and one reply per command, in
two forms:

* ``rd <option>`` reads one value and is answered ``ACK rd <option> = <value>``,
  or ``NAK rd <option> = Error`` for an option the firmware does not know. The
  options are ``name``, ``copyright``, ``version``, ``sha`` and ``temperature``.
* The control commands (``status``, ``sreset``, ``ecureset``, ``bootsel``) are
  answered ``ok ...`` or ``err <code> <text>``, values as ``key=value`` tokens.

**A failed reading is an error, never a stale value.** When the firmware cannot
read the sensor - it does not acknowledge, a frame fails its CRC, or the bus
times out - ``rd temperature`` answers ``Error``, and the driver raises
:class:`NoReadingError`, so that a test cannot mistake "no reading" for "same
as last time".

Traces to: PICO-FR-040 .. PICO-FR-048, PICO-ARC-001, PICO-DD-DRIVER.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ...core.errors import InstrumentError, ProtocolError
from ...core.events import log_reading
from ...core.instrument import InstrumentIdentity
from ...core.scpi import ScpiInstrument
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    DEFAULT_BAUDRATE,
    ERRORS,
    MANUFACTURER,
    MODEL,
    NAME,
    RD_ERROR,
    STATUS_BITS,
)
from .simulator import SimulatedPicoSht30

__all__ = [
    "PicoSht30",
    "FirmwareInfo",
    "Reading",
    "SensorStatus",
    "SensorError",
    "NoReadingError",
    "RdRefusedError",
]

#: Informational lines (``help`` only) are skipped when looking for a reply.
_INFO_PREFIX = "#"

#: Lines read while looking for a reply before giving up.
_MAX_SKIPPED_LINES = 32

#: ``ACK rd temperature = 22.85``: the verdict, the option and the value.
_RD_REPLY = re.compile(r"^(ACK|NAK) rd (\S+) = (.*)$")

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


class RdRefusedError(InstrumentError):
    """The firmware answered ``NAK``: it does not know the ``rd`` option."""


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


def parse_fields(reply: str) -> Dict[str, str]:
    """Split the ``key=value`` tokens of an ``ok`` reply into a dictionary."""
    fields: Dict[str, str] = {}
    for token in reply.split()[1:]:
        key, _, value = token.partition("=")
        fields[key] = value
    return fields


# ---------------------------------------------------------------------------
class PicoSht30(ScpiInstrument):
    """A Pico 2 + SHT30-D thermometer.

    Example::

        from benchtools.instruments.pico_sht30 import PicoSht30

        with PicoSht30.connect("/dev/ttyACM0") as thermometer:
            info = thermometer.firmware_info()
            print(info.name, info.version, info.sha)
            print("%.2f C" % thermometer.temperature())
    """

    SIMULATOR_CLASS = SimulatedPicoSht30
    MODEL_NAME = "%s SHT30-D thermometer" % MODEL
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
    ) -> "PicoSht30":
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

    def rd(self, option: str) -> str:  # pylint: disable=invalid-name
        """Send ``rd <option>`` and return the value of its ``ACK``.

        :raises RdRefusedError: if the firmware answered ``NAK``.
        :raises SensorError: if it answered ``err`` (a malformed command).
        :raises ProtocolError: if the reply is for another option, or is
            neither ``ACK`` nor ``NAK``.
        """
        command = "rd %s" % option
        reply = self._send(command)
        match = _RD_REPLY.match(reply)
        if match is None:
            if reply.startswith("err "):
                parts = reply.split(" ", 2)
                raise SensorError(int(parts[1]) if parts[1].isdigit() else -1,
                                  parts[2] if len(parts) > 2 else "", command)
            raise ProtocolError("unexpected reply to %r: %r" % (command, reply))
        verdict, echoed, value = match.groups()
        if echoed != option:
            raise ProtocolError("reply to %r is for %r: %r" % (command, echoed, reply))
        if verdict == "NAK":
            raise RdRefusedError("%r refused: %s" % (command, reply))
        return value

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
