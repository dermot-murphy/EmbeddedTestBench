"""A simulated Pico 2 + SHT30-D thermometer.

The model is the *firmware*, not the sensor alone. It answers the same command
lines with the same reply shapes, and it takes its numbers the same way: the
ambient temperature is quantised to a raw 16-bit word, and the reported value is
computed from that word with the firmware's integer arithmetic. A driver that
checked the reported value against the raw word would therefore pass here only
if it did the conversion the way the firmware does.

Fault injection covers the three ways a real reading fails: no sensor on the
bus, a corrupted frame, and a bus that times out. Each makes ``temp`` answer
``err``, never a stale value, which is the firmware's contract.

Traces to: PICO-FR-050, PICO-DD-SIM.
"""

from __future__ import annotations

from typing import List, Optional

from .constants import (
    DEFAULT_ADDRESS,
    ERROR_BUS,
    ERROR_CRC,
    ERROR_NO_SENSOR,
    PROTOCOL_VERSION,
    SENSOR,
    STATUS_BITS,
    TITLE,
    raw_to_celsius,
    raw_to_percent,
)

__all__ = ["SimulatedPicoSht30"]

_ERROR_TEXT = {
    1: "unknown command",
    2: "wrong number of arguments",
    3: "line too long",
    ERROR_NO_SENSOR: "the sensor did not acknowledge",
    ERROR_CRC: "the sensor checksum did not match",
    ERROR_BUS: "I2C bus timeout",
}

_HELP = (
    ("help", "list the commands"),
    ("ver", "identity: title, firmware version, build date, protocol, board id"),
    ("temp", "single-shot high-repeatability measurement: temperature and humidity"),
    ("status", "the SHT30 status register"),
    ("sreset", "soft-reset the SHT30"),
    ("reset", "reboot the Pico"),
    ("bootsel", "reboot into the USB bootloader, to accept a UF2"),
)

#: Longest command line the firmware accepts, excluding the terminator.
_MAX_LINE = 63


def celsius_to_raw(celsius: float) -> int:
    """The raw word the sensor would send for *celsius*, clamped to range."""
    raw = round((float(celsius) + 45.0) * 65535.0 / 175.0)
    return max(0, min(65535, int(raw)))


def percent_to_raw(percent: float) -> int:
    """The raw word the sensor would send for *percent* RH, clamped to range."""
    raw = round(float(percent) * 65535.0 / 100.0)
    return max(0, min(65535, int(raw)))


class SimulatedPicoSht30:
    """A Pico 2 running the thermometer firmware, with an SHT30 attached.

    Satisfies :class:`~benchtools.core.simulator.Responder`.

    :param temperature: Ambient temperature, degrees Celsius.
    :param humidity: Relative humidity, percent.
    :param version: Firmware version reported by ``ver``.
    """

    DEFAULT_SERIAL = "E6614C311B7F2A21"
    DEFAULT_BUILT = "2026-09-30T00:00:00Z"

    def __init__(
        self,
        temperature: float = 22.5,
        humidity: float = 45.0,
        version: str = "1.0.0",
        title: str = TITLE,
        serial: Optional[str] = None,
    ) -> None:
        self.temperature = float(temperature)
        self.humidity = float(humidity)
        self.version = version
        self.title = title
        self.serial = serial or self.DEFAULT_SERIAL
        self.built = self.DEFAULT_BUILT
        self.uptime_s = 0
        #: Fault injection. ``sensor_present`` False makes every sensor command
        #: answer "err 4"; ``corrupt_next`` makes the next one answer "err 5";
        #: ``bus_timeout`` makes every one answer "err 6".
        self.sensor_present = True
        self.corrupt_next = False
        self.bus_timeout = False
        #: The status register. Bit 4 (reset detected) is set at power-up,
        #: as it is on the part.
        self.status_word = STATUS_BITS["reset_detected"]
        self.command_log: List[str] = []
        self.reboots = 0
        self.bootloader_requests = 0
        self.measurements = 0

    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one command line, as the firmware does."""
        text = message.decode("ascii", errors="replace").replace("\r", "").strip("\n")
        if not text.strip():
            return None
        self.command_log.append(text.strip())
        if len(text) > _MAX_LINE:
            return self._encode([self._error(3)])
        return self._encode(self._dispatch(text.split()))

    @staticmethod
    def _encode(lines: List[str]) -> bytes:
        return "".join(line + "\n" for line in lines).encode("ascii")

    @staticmethod
    def _error(code: int) -> str:
        return "err %d %s" % (code, _ERROR_TEXT[code])

    def _dispatch(self, tokens: List[str]) -> List[str]:
        name, arguments = tokens[0], tokens[1:]
        handler = getattr(self, "_cmd_%s" % name, None)
        if handler is None:
            return [self._error(1)]
        if arguments:
            return [self._error(2)]
        return handler()

    def _sensor_fault(self) -> Optional[str]:
        if self.bus_timeout:
            return self._error(ERROR_BUS)
        if not self.sensor_present:
            return self._error(ERROR_NO_SENSOR)
        if self.corrupt_next:
            self.corrupt_next = False
            return self._error(ERROR_CRC)
        return None

    # ------------------------------------------------------------------
    def _cmd_help(self) -> List[str]:
        return ["# %s - %s" % item for item in _HELP] + ["ok"]

    def _cmd_ver(self) -> List[str]:
        return [
            "ok title=%s fw=%s built=%s proto=%s board=pico2 serial=%s "
            "sensor=%s addr=0x%02X uptime_s=%d"
            % (self.title, self.version, self.built, PROTOCOL_VERSION, self.serial,
               SENSOR, DEFAULT_ADDRESS, self.uptime_s)
        ]

    def _cmd_temp(self) -> List[str]:
        fault = self._sensor_fault()
        if fault:
            return [fault]
        self.measurements += 1
        raw_t = celsius_to_raw(self.temperature)
        raw_rh = percent_to_raw(self.humidity)
        return [
            "ok t=%.3f rh=%.3f raw_t=0x%04X raw_rh=0x%04X"
            % (raw_to_celsius(raw_t), raw_to_percent(raw_rh), raw_t, raw_rh)
        ]

    def _cmd_status(self) -> List[str]:
        fault = self._sensor_fault()
        if fault:
            return [fault]
        return ["ok status=0x%04X" % self.status_word]

    def _cmd_sreset(self) -> List[str]:
        fault = self._sensor_fault()
        if fault:
            return [fault]
        self.status_word = STATUS_BITS["reset_detected"]
        return ["ok"]

    def _cmd_reset(self) -> List[str]:
        self.reboots += 1
        self.uptime_s = 0
        return ["ok"]

    def _cmd_bootsel(self) -> List[str]:
        self.bootloader_requests += 1
        return ["ok"]
