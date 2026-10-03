"""A simulated Pico 2 + SHT30-D thermometer.

The model is the *firmware*, not the sensor alone. It answers the same command
lines with the same reply shapes, and it takes its numbers the same way: the
ambient temperature is quantised to a raw 16-bit word, converted to
milli-degrees with the firmware's integer arithmetic, and reported by
``rd temperature`` to two places, rounded half away from zero. A driver that
assumed any other rounding would disagree with the simulator, as it would with
the firmware.

Fault injection covers the three ways a real reading fails: no sensor on the
bus, a corrupted frame, and a bus that times out. Each makes ``rd temperature``
answer ``Error``, never a stale value, which is the firmware's contract; the
commands that keep the ``ok``/``err`` form (``status``, ``sreset``) answer
``err`` with the firmware's code.

Traces to: PICO-FR-050, PICO-DD-SIM.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from .constants import (
    COMMANDS,
    COPYRIGHT,
    ERROR_BUS,
    ERROR_CRC,
    ERROR_NO_SENSOR,
    NAME,
    RD_ERROR,
    STATUS_BITS,
    milli_to_centi_text,
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
    ("rd", "read one value: name, copyright, version, sha, temperature"),
    ("status", "the SHT30 status register"),
    ("sreset", "soft-reset the SHT30"),
    ("ecureset", "reboot the Pico"),
    ("bootsel", "reboot into the USB bootloader, to accept a UF2"),
)

#: Longest command line the firmware accepts, excluding the terminator.
_MAX_LINE = 63


def celsius_to_raw(celsius: float) -> int:
    """The raw word the sensor would send for *celsius*, clamped to range."""
    raw = round((float(celsius) + 45.0) * 65535.0 / 175.0)
    return max(0, min(65535, int(raw)))


def raw_to_milli(raw: int) -> int:
    """Milli-degrees from a raw word, with the firmware's integer arithmetic."""
    return (175000 * int(raw) + 65535 // 2) // 65535 - 45000


class SimulatedPicoSht30:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """A Pico 2 running the thermometer firmware, with an SHT30 attached.

    Satisfies :class:`~benchtools.core.simulator.Responder`.

    :param temperature: Ambient temperature, degrees Celsius.
    :param version: What ``rd version`` reports.
    :param sha: What ``rd sha`` reports: the commit the image was built from.
    """

    DEFAULT_VERSION = "V1.00.0000"
    DEFAULT_SHA = "0c0ffee"

    def __init__(
        self,
        temperature: float = 22.5,
        version: str = DEFAULT_VERSION,
        sha: str = DEFAULT_SHA,
        name: str = NAME,
    ) -> None:
        self.temperature = float(temperature)
        self.version = version
        self.sha = sha
        self.name = name
        self.copyright = COPYRIGHT
        #: Fault injection. ``sensor_present`` False makes every sensor command
        #: fail as "the sensor did not acknowledge"; ``corrupt_next`` makes the
        #: next one fail its CRC; ``bus_timeout`` makes every one time out.
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
        #: Called after ``bootsel`` is answered, for a board model that
        #: presents the bootloader drive.
        self.on_bootloader: Optional[Callable[[], None]] = None

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
        if handler is None or name not in COMMANDS:
            return [self._error(1)]
        low, high = COMMANDS[name]
        if not low <= len(arguments) <= high:
            return [self._error(2)]
        return handler(*arguments)

    def _sensor_fault(self) -> Optional[int]:
        if self.bus_timeout:
            return ERROR_BUS
        if not self.sensor_present:
            return ERROR_NO_SENSOR
        if self.corrupt_next:
            self.corrupt_next = False
            return ERROR_CRC
        return None

    # ------------------------------------------------------------------
    def _cmd_help(self) -> List[str]:
        return ["# %s - %s" % item for item in _HELP] + ["ok"]

    def _cmd_rd(self, option: str) -> List[str]:
        values = {
            "name": lambda: self.name,
            "copyright": lambda: self.copyright,
            "version": lambda: self.version,
            "sha": lambda: self.sha,
            "temperature": self._temperature_text,
        }
        if option not in values:
            return ["NAK rd %s = %s" % (option, RD_ERROR)]
        return ["ACK rd %s = %s" % (option, values[option]())]

    def _temperature_text(self) -> str:
        if self._sensor_fault() is not None:
            return RD_ERROR
        self.measurements += 1
        return milli_to_centi_text(raw_to_milli(celsius_to_raw(self.temperature)))

    def _cmd_status(self) -> List[str]:
        fault = self._sensor_fault()
        if fault:
            return [self._error(fault)]
        return ["ok status=0x%04X" % self.status_word]

    def _cmd_sreset(self) -> List[str]:
        fault = self._sensor_fault()
        if fault:
            return [self._error(fault)]
        self.status_word = STATUS_BITS["reset_detected"]
        return ["ok"]

    def _cmd_ecureset(self) -> List[str]:
        self.reboots += 1
        return ["ok"]

    def _cmd_bootsel(self) -> List[str]:
        self.bootloader_requests += 1
        if self.on_bootloader is not None:
            self.on_bootloader()
        return ["ok"]
