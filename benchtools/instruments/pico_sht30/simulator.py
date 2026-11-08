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

The frequency generator is modelled too: the same settings, limits, routine
statuses and restart rule, and the same integer arithmetic for the frequency
it reports. A finite run becomes ``Complete`` once enough time has passed on
:attr:`SimulatedPicoSht30.clock`, which a test may replace.

Traces to: PICO-FR-050, PICO-FR-086, PICO-DD-SIM.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Dict, List, Optional

from .constants import (
    COMMANDS,
    COPYRIGHT,
    ERROR_BUS,
    ERROR_CRC,
    ERROR_NO_SENSOR,
    ABORTED,
    COMPLETE,
    FGEN_CHANNELS,
    FGEN_DEFAULT_CHANNEL,
    FGEN_FREQ_RANGE_MHZ,
    FGEN_GPIO_CHANNEL,
    FGEN_SAMPLE_RATE_MHZ,
    FGEN_WAVES,
    NAME,
    NOT_STARTED,
    RUNNING,
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
    ("rd", "read one value: name, copyright, version, sha, temperature, "
           "freq, freq2, wave, duty, amp, ratio, cycles"),
    ("wr", "write a generator setting: freq, freq2, wave, duty, amp, ratio, cycles"),
    ("routine", "routine freq start|abort|results [channel], or routine all abort"),
    ("status", "the SHT30 status register"),
    ("sreset", "soft-reset the SHT30"),
    ("ecureset", "reboot the Pico"),
    ("bootsel", "reboot into the USB bootloader, to accept a UF2"),
)

#: Longest command line the firmware accepts, excluding the terminator.
_MAX_LINE = 63

_UINT32_MAX = 0xFFFFFFFF
_DECIMAL = re.compile(r"^(\d*)(?:\.(\d*))?$")

#: System clock, and the PWM divider's limits in sixteenths; fgen.c.
_SYS_CLOCK_HZ = 150000000
_PWM_DIV_ONE = 16
_PWM_DIV_MAX = 4095
_PWM_COUNT_MAX = 65536

_DEFAULTS: Dict[str, object] = {
    "freq": 1000000, "freq2": 2000000, "wave": "square", "duty": 50000,
    "amp": 100000, "ratio": 500, "cycles": 0,
}


def parse_milli(text: str, allow_kilo: bool) -> Optional[int]:
    """Thousandths from a decimal, as the firmware parses it, or ``None``."""
    body = text
    multiplier = 1
    if allow_kilo and body[-1:] in ("k", "K"):
        body = body[:-1]
        multiplier = 1000
    match = _DECIMAL.match(body)
    if match is None:
        return None
    whole, fraction = match.group(1), match.group(2) or ""
    if not (whole or fraction) or len(fraction) > 3:
        return None
    value = int((whole + fraction.ljust(3, "0")) or "0") * multiplier
    return value if value <= _UINT32_MAX else None


def dac_actual_mhz(freq_mhz: int) -> int:
    """The frequency a DAC channel generates, by the firmware's arithmetic."""
    step = ((freq_mhz << 32) + FGEN_SAMPLE_RATE_MHZ // 2) // FGEN_SAMPLE_RATE_MHZ
    return (step * FGEN_SAMPLE_RATE_MHZ + (1 << 31)) >> 32


def pwm_actual_mhz(freq_mhz: int) -> int:
    """The frequency the GPIO channel generates, by the firmware's arithmetic."""
    clock = _SYS_CLOCK_HZ * _PWM_DIV_ONE * 1000
    total = clock // freq_mhz
    divider = max(_PWM_DIV_ONE, min(_PWM_DIV_MAX, (total + _PWM_COUNT_MAX - 1) // _PWM_COUNT_MAX))
    count = min(_PWM_COUNT_MAX, (total + divider // 2) // divider)
    return (clock // divider + count // 2) // count


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

    DEFAULT_VERSION = "V1.01.0000"
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
        #: Called after ``bootsel`` is answered: the board model in
        #: :mod:`.flash` uses it to present the bootloader drive.
        self.on_bootloader: Optional[Callable[[], None]] = None
        #: Seconds, for timing a finite generator run. A test may replace it.
        self.clock: Callable[[], float] = time.monotonic
        self.settings = {number: dict(_DEFAULTS) for number in FGEN_CHANNELS}
        self.runs: Dict[int, Dict[str, object]] = {}

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

    def _cmd_rd(self, option: str, channel: Optional[str] = None) -> List[str]:
        if option in _DEFAULTS:
            return [self._read_setting(option, channel or str(FGEN_DEFAULT_CHANNEL))]
        if channel is not None:
            return [self._error(2)]
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

    # ------------------------------------------------------------------
    # Frequency generator
    # ------------------------------------------------------------------
    @staticmethod
    def _channel(text: str) -> Optional[int]:
        return int(text) if text.isdigit() and int(text) in FGEN_CHANNELS else None

    @staticmethod
    def _show(setting: str, value: object) -> str:
        if setting in ("wave", "cycles"):
            return str(value)
        return milli_to_centi_text(int(value))  # type: ignore[call-overload]

    def _read_setting(self, setting: str, channel_text: str) -> str:
        channel = self._channel(channel_text)
        if channel is None:
            return "NAK rd %s %s = %s" % (setting, channel_text, RD_ERROR)
        return "ACK rd %s %s = %s" % (setting, channel_text,
                                      self._show(setting, self.settings[channel][setting]))

    @staticmethod
    def _parse_setting(setting: str, text: str, channel: int) -> Optional[object]:
        """The stored form of *text* for *setting*, or ``None`` if refused."""
        gpio = channel == FGEN_GPIO_CHANNEL
        low, high = FGEN_FREQ_RANGE_MHZ
        if setting == "wave":
            return text if text in FGEN_WAVES and (not gpio or text == "square") else None
        if setting == "cycles":
            return int(text) if text.isdigit() and int(text) <= _UINT32_MAX else None
        value = parse_milli(text, setting in ("freq", "freq2"))
        if value is None or (gpio and setting in ("freq2", "amp", "ratio")):
            return None
        limits = {"freq": (low, high), "freq2": (low, high), "duty": (1000, 99000),
                  "amp": (0, 100000), "ratio": (0, 1000)}[setting]
        return value if limits[0] <= value <= limits[1] else None

    def _cmd_wr(self, setting: str, first: str, second: Optional[str] = None) -> List[str]:
        if setting not in _DEFAULTS:
            return ["NAK wr %s = %s" % (setting, RD_ERROR)]
        channel_text = str(FGEN_DEFAULT_CHANNEL) if second is None else first
        value_text = first if second is None else second
        channel = self._channel(channel_text)
        value = None if channel is None else self._parse_setting(setting, value_text, channel)
        if channel is None or value is None:
            return ["NAK wr %s %s = %s" % (setting, channel_text, RD_ERROR)]
        self.settings[channel][setting] = value
        return ["ACK wr %s %s = %s" % (setting, channel_text, self._show(setting, value))]

    def _update_run(self, channel: int) -> Optional[Dict[str, object]]:
        """The channel's run, marked ``Complete`` if its time is up."""
        run = self.runs.get(channel)
        if run is not None and run["status"] == RUNNING and run["cycles"]:
            duration = (  # type: ignore[arg-type]
                float(run["cycles"]) * 1000.0 / float(run["actual"]))
            if self.clock() - float(run["started"]) >= duration:  # type: ignore[arg-type]
                run["status"] = COMPLETE
        return run

    def _start(self, channel: int) -> bool:
        run = self._update_run(channel)
        if run is not None and run["status"] == RUNNING and not run["cycles"]:
            return False
        settings = self.settings[channel]
        actual = (pwm_actual_mhz if channel == FGEN_GPIO_CHANNEL else dac_actual_mhz)(
            int(settings["freq"]))  # type: ignore[call-overload]
        self.runs[channel] = {"status": RUNNING, "cycles": settings["cycles"], "actual": actual,
                              "wave": settings["wave"], "started": self.clock()}
        return True

    def _abort(self, channel: int) -> None:
        run = self._update_run(channel)
        if run is not None and run["status"] == RUNNING:
            run["status"] = ABORTED

    def _abort_all(self) -> None:
        for channel in FGEN_CHANNELS:
            self._abort(channel)

    def _result(self, channel: int) -> str:
        run = self._update_run(channel)
        if run is None:
            return "ACK routine freq results %d = %s" % (channel, NOT_STARTED)
        return "ACK routine freq results %d = %s, %s, %s Hz" % (
            channel, run["status"], run["wave"],
            milli_to_centi_text(int(run["actual"])))  # type: ignore[call-overload]

    def _routine_start(self, channel: Optional[str]) -> List[str]:
        channel_text = channel or str(FGEN_DEFAULT_CHANNEL)
        number = self._channel(channel_text)
        if number is not None and self._start(number):
            return ["ACK routine freq start %s = %s" % (channel_text, RUNNING)]
        return ["NAK routine freq start %s = %s" % (channel_text, RD_ERROR)]

    def _routine_abort(self, channel: Optional[str]) -> List[str]:
        if channel is None:
            self._abort_all()
            return ["ACK routine freq abort = %s" % ABORTED]
        number = self._channel(channel)
        if number is None:
            return ["NAK routine freq abort %s = %s" % (channel, RD_ERROR)]
        self._abort(number)
        return ["ACK routine freq abort %s = %s" % (channel, ABORTED)]

    def _routine_results(self, channel: Optional[str]) -> List[str]:
        if channel is None:
            return [self._result(number) for number in FGEN_CHANNELS]
        number = self._channel(channel)
        if number is None:
            return ["NAK routine freq results %s = %s" % (channel, RD_ERROR)]
        return [self._result(number)]

    def _cmd_routine(self, target: str, verb: str, channel: Optional[str] = None) -> List[str]:
        verbs = {"start": self._routine_start, "abort": self._routine_abort,
                 "results": self._routine_results}
        if target == "freq" and verb in verbs:
            return verbs[verb](channel)
        echo = " ".join(token for token in ("routine", target, verb, channel) if token)
        if target == "all" and verb == "abort" and channel is None:
            self._abort_all()
            return ["ACK %s = %s" % (echo, ABORTED)]
        return ["NAK %s = %s" % (echo, RD_ERROR)]

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
