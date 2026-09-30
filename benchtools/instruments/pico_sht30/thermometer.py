"""Driver for the Raspberry Pi Pico 2 + DollaTek SHT30-D bench thermometer.

The Pico runs ``firmware/pico_sht30`` and appears as a USB CDC serial port.
It speaks a line protocol: one command per line, one ``ok ...`` or
``err <code> <text>`` reply per command, values as ``key=value`` tokens.

Two things shape this driver, and both are about not reporting a number that
is not true:

**A failed reading is an error, never a stale value.** The firmware answers
``err`` when the sensor does not acknowledge, when a frame fails its CRC, or
when the bus times out. The driver raises :class:`SensorError` for each, with
the firmware's code, so a test cannot mistake "no reading" for "same as last
time".

**The reported value is checked against the raw word.** ``temp`` carries both
the converted temperature and the 16-bit word it came from. The driver
recomputes one from the other with the firmware's own integer arithmetic and
refuses a reply in which they disagree - which is what a corrupted USB line or
a firmware conversion defect would look like.

Traces to: PICO-FR-040 .. PICO-FR-046, PICO-ARC-001, PICO-DD-DRIVER.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ...core.errors import InstrumentError, ProtocolError
from ...core.instrument import InstrumentIdentity
from ...core.scpi import ScpiInstrument
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    DEFAULT_BAUDRATE,
    ERRORS,
    MANUFACTURER,
    MODEL,
    PROTOCOL_VERSION,
    STATUS_BITS,
    raw_to_celsius,
    raw_to_percent,
)
from .simulator import SimulatedPicoSht30

__all__ = ["PicoSht30", "FirmwareInfo", "Reading", "SensorStatus", "SensorError"]

_LOG = logging.getLogger(__name__)

#: Largest disagreement tolerated between a reported value and the value
#: recomputed from its raw word. The firmware prints three decimals of an exact
#: thousandth, so anything beyond rounding noise is a real disagreement.
_CROSS_CHECK_TOLERANCE = 0.0015

#: Informational lines (``help`` only) are skipped when looking for a reply.
_INFO_PREFIX = "#"

#: Lines read while looking for a reply before giving up.
_MAX_SKIPPED_LINES = 32


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


@dataclass(frozen=True)
class FirmwareInfo:
    """Everything ``ver`` reports."""

    title: str
    version: str
    built: str
    protocol: str
    board: str
    serial: str
    sensor: str
    address: int
    uptime_s: int

    @property
    def build_date_is_utc(self) -> bool:
        """``False`` for an IDE build whose date is the compiler's local time."""
        return not self.built.startswith("local:")

    def as_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "version": self.version,
            "built": self.built,
            "protocol": self.protocol,
            "board": self.board,
            "serial": self.serial,
            "sensor": self.sensor,
            "address": "0x%02X" % self.address,
            "uptime_s": self.uptime_s,
        }


@dataclass(frozen=True)
class Reading:
    """One measurement, with the raw words it came from."""

    temperature: float
    humidity: float
    raw_temperature: int
    raw_humidity: int
    timestamp: float

    def as_dict(self) -> Dict[str, object]:
        return {
            "temperature_c": self.temperature,
            "humidity_pct": self.humidity,
            "raw_temperature": "0x%04X" % self.raw_temperature,
            "raw_humidity": "0x%04X" % self.raw_humidity,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class SensorStatus:
    """The decoded SHT3x status register."""

    raw: int

    def flag(self, name: str) -> bool:
        return bool(self.raw & STATUS_BITS[name])

    def as_dict(self) -> Dict[str, object]:
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
            print(info.title, info.version)
            print("%.2f C" % thermometer.temperature())
    """

    SIMULATOR_CLASS = SimulatedPicoSht30
    MODEL_NAME = "%s SHT30-D thermometer" % MODEL

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
    def connect(
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
        """Identify the thermometer, and check it speaks this protocol.

        No ``*CLS``: the firmware is not SCPI, and would answer it with
        ``err 1``. A protocol revision whose major number differs from the one
        this driver was written for is refused rather than half-understood.
        """
        info = self.firmware_info(refresh=True)
        if info.protocol.split(".")[0] != PROTOCOL_VERSION.split(".")[0]:
            raise ProtocolError(
                "thermometer speaks protocol %s; this driver speaks %s"
                % (info.protocol, PROTOCOL_VERSION)
            )
        self.identify(refresh=True)

    # ------------------------------------------------------------------
    # Primitive I/O
    # ------------------------------------------------------------------
    def _read_reply(self, command: str) -> str:
        """Read lines until the reply to *command*, skipping ``#`` lines."""
        for _ in range(_MAX_SKIPPED_LINES):
            line = self._transport.read_message().decode("ascii", errors="replace").strip()
            _LOG.debug("<< %s", line)
            if not line or line.startswith(_INFO_PREFIX):
                continue
            return line
        raise ProtocolError("no reply to %r among %d lines" % (command, _MAX_SKIPPED_LINES))

    def execute(self, command: str) -> Dict[str, str]:
        """Send *command* and return the fields of its ``ok`` reply.

        :raises SensorError: if the firmware answered ``err``.
        :raises ProtocolError: if it answered neither ``ok`` nor ``err``.
        """
        _LOG.debug(">> %s", command)
        self._transport.write(command.encode("ascii"))
        reply = self._read_reply(command)
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

    @staticmethod
    def _field(fields: Dict[str, str], key: str, command: str) -> str:
        if key not in fields:
            raise ProtocolError("%r reply has no %r field: %r" % (command, key, fields))
        return fields[key]

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def firmware_info(self, refresh: bool = False) -> FirmwareInfo:
        """The title, version and the rest of what ``ver`` reports."""
        if self._info is None or refresh:
            fields = self.execute("ver")
            try:
                self._info = FirmwareInfo(
                    title=self._field(fields, "title", "ver"),
                    version=self._field(fields, "fw", "ver"),
                    built=fields.get("built", ""),
                    protocol=self._field(fields, "proto", "ver"),
                    board=fields.get("board", ""),
                    serial=fields.get("serial", ""),
                    sensor=fields.get("sensor", ""),
                    address=int(fields.get("addr", "0x0"), 16),
                    uptime_s=int(fields.get("uptime_s", "0")),
                )
            except ValueError as exc:
                raise ProtocolError("malformed 'ver' reply: %r" % fields) from exc
        return self._info

    @property
    def title(self) -> str:
        """The product title the firmware reports."""
        return self.firmware_info().title

    @property
    def version(self) -> str:
        """The firmware version, e.g. ``1.0.0``."""
        return self.firmware_info().version

    def _read_identity(self) -> InstrumentIdentity:
        info = self.firmware_info()
        return InstrumentIdentity(
            raw="%s %s (built %s)" % (info.title, info.version, info.built),
            manufacturer=MANUFACTURER,
            model="%s/%s" % (MODEL, info.sensor or "SHT30"),
            serial_number=info.serial,
            firmware="%s (built %s)" % (info.version, info.built) if info.built else info.version,
        )

    def read_event_queue(self) -> List[Tuple[int, str]]:
        """The firmware has no error queue: every failure is in its reply."""
        return []

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------
    def read(self) -> Reading:
        """Take one measurement: temperature and humidity.

        :raises SensorError: if the sensor is absent, the frame failed its
            CRC, or the bus timed out.
        :raises ProtocolError: if the reported values disagree with their raw
            words.
        """
        fields = self.execute("temp")
        try:
            temperature = float(self._field(fields, "t", "temp"))
            humidity = float(self._field(fields, "rh", "temp"))
            raw_t = int(self._field(fields, "raw_t", "temp"), 16)
            raw_rh = int(self._field(fields, "raw_rh", "temp"), 16)
        except ValueError as exc:
            raise ProtocolError("malformed 'temp' reply: %r" % fields) from exc

        for label, reported, expected in (
            ("temperature", temperature, raw_to_celsius(raw_t)),
            ("humidity", humidity, raw_to_percent(raw_rh)),
        ):
            if abs(reported - expected) > _CROSS_CHECK_TOLERANCE:
                raise ProtocolError(
                    "%s %.3f does not match its raw word (which gives %.3f)"
                    % (label, reported, expected)
                )
        return Reading(temperature, humidity, raw_t, raw_rh, time.time())

    def temperature(self) -> float:
        """The temperature now, in degrees Celsius."""
        return self.read().temperature

    def humidity(self) -> float:
        """The relative humidity now, in percent."""
        return self.read().humidity

    def status(self) -> SensorStatus:
        """The sensor's status register."""
        fields = self.execute("status")
        try:
            return SensorStatus(int(self._field(fields, "status", "status"), 16))
        except ValueError as exc:
            raise ProtocolError("malformed 'status' reply: %r" % fields) from exc

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------
    def soft_reset_sensor(self) -> None:
        """Soft-reset the SHT30; the Pico keeps running."""
        self.execute("sreset")

    def reset(self, settle: float = 0.0) -> None:  # type: ignore[override]
        """Reboot the Pico. The USB port re-enumerates; reconnect afterwards."""
        self.execute("reset")
        self._info = None
        if settle > 0:
            time.sleep(settle)

    def enter_bootloader(self) -> None:
        """Reboot into the USB bootloader, ready for a new ``.uf2``."""
        self.execute("bootsel")
        self._info = None
