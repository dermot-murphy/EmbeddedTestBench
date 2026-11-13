"""PicoScope 3000D series constants: ranges, timebases, SDK enumerations.

Every number here was either read off the bench's PicoScope 3405D MSO through
the ``ps3000a`` SDK on 2026-11-13 (marked *measured*), or taken from Pico
Technology's specification page for the 3000 series (marked *spec page*).
The few SDK enumeration values that could be checked neither way are marked
*SDK header, unverified*; ``docs/picoscope3000/PicoScope3000_Notes.md`` lists
them, as ETB-RISK-004 requires.

Traces to: PSCOPE-FR-001 .. PSCOPE-FR-012, PSCOPE-DD-CONST.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Union

from ...core.enums import ScpiEnum

__all__ = [
    "MODEL",
    "Channel",
    "Coupling",
    "ThresholdDirection",
    "DigitalDirection",
    "WaveType",
    "RANGES",
    "RANGE_VOLTS",
    "DIGITAL_PORTS",
    "DIGITAL_BITS",
    "STATUS_NAMES",
    "POWER_STATUSES",
    "UnitInfo",
    "ModelLimits",
    "PS3405D_LIMITS",
    "sample_interval_s",
    "timebase_for",
    "range_for_volts",
    "status_text",
]

#: Name used in messages before the unit has identified itself.
MODEL = "PicoScope 3000"


class Channel(ScpiEnum):
    """Analogue input, by the letter on the front panel."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"

    @property
    def sdk_index(self) -> int:
        """The SDK's ``PS3000A_CHANNEL`` value: A is 0."""
        return "ABCD".index(self.value)

    @property
    def number(self) -> int:
        """The channel as a number, A is 1, the form the analysis uses."""
        return self.sdk_index + 1

    @classmethod
    def parse(cls, channel: Union[int, str, "Channel"]) -> "Channel":
        """Accept ``1``..``4``, ``"A"``..``"D"`` (any case) or a :class:`Channel`.

        :raises ValueError: for anything else.
        """
        if isinstance(channel, cls):
            return channel
        if isinstance(channel, int) and not isinstance(channel, bool):
            if 1 <= channel <= 4:
                return cls("ABCD"[channel - 1])
            raise ValueError("channel %d is not 1 to 4" % channel)
        text = str(channel).strip().upper()
        if text.isdigit():
            return cls.parse(int(text))
        return cls.coerce(text)


class Coupling(ScpiEnum):
    """Input coupling. The value is the SDK's ``PS3000A_COUPLING``."""

    AC = "AC"
    DC = "DC"

    @property
    def code(self) -> int:
        """``PS3000A_AC`` is 0, ``PS3000A_DC`` 1 (DC measured on 2026-11-13)."""
        return {"AC": 0, "DC": 1}[self.value]


class ThresholdDirection(ScpiEnum):
    """Analogue trigger direction, ``PS3000A_THRESHOLD_DIRECTION``."""

    ABOVE = "ABOVE"
    BELOW = "BELOW"
    RISE = "RISE"
    FALL = "FALL"
    EITHER = "EITHER"

    @property
    def code(self) -> int:
        """SDK value. ``RISE`` (2) was measured: the trace crossed upwards at
        t = 0. The rest are the SDK header's order, unverified."""
        return ("ABOVE", "BELOW", "RISE", "FALL", "EITHER").index(self.value)


class DigitalDirection(ScpiEnum):
    """Digital trigger condition on one bit, ``PS3000A_DIGITAL_DIRECTION``."""

    DONT_CARE = "DONT_CARE"
    LOW = "LOW"
    HIGH = "HIGH"
    RISE = "RISE"
    FALL = "FALL"
    EITHER = "EITHER"

    @property
    def code(self) -> int:
        """SDK value, in the SDK header's order (unverified)."""
        return ("DONT_CARE", "LOW", "HIGH", "RISE", "FALL", "EITHER").index(self.value)


class WaveType(ScpiEnum):
    """Signal generator built-in waveform, ``PS3000A_WAVE_TYPE``."""

    SINE = "SINE"
    SQUARE = "SQUARE"
    TRIANGLE = "TRIANGLE"
    RAMP_UP = "RAMP_UP"
    RAMP_DOWN = "RAMP_DOWN"
    SINC = "SINC"
    GAUSSIAN = "GAUSSIAN"
    HALF_SINE = "HALF_SINE"
    DC_VOLTAGE = "DC_VOLTAGE"

    @property
    def code(self) -> int:
        """SDK value, in the SDK header's order (unverified)."""
        return [member.value for member in WaveType].index(self.value)


#: ``PS3000A_RANGE`` index to full-scale volts (+/-). Indices 1 to 10 are the
#: ones the 3405D accepts: ``ps3000aGetAnalogueOffset`` refused 0 (10 mV) and
#: 11 (50 V) with status 0x0F (measured). The spec page agrees: "+/-20 mV to
#: +/-20 V full scale in 10 ranges".
RANGES: Dict[int, float] = {
    1: 0.02, 2: 0.05, 3: 0.1, 4: 0.2, 5: 0.5,
    6: 1.0, 7: 2.0, 8: 5.0, 9: 10.0, 10: 20.0,
}

#: Full-scale volts, ascending.
RANGE_VOLTS: Tuple[float, ...] = tuple(RANGES[index] for index in sorted(RANGES))

#: Analogue offset limit for each range, +/- volts (measured with
#: ``ps3000aGetAnalogueOffset``, DC coupling).
OFFSET_LIMITS: Dict[int, float] = {
    1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25,
    5: 2.5, 6: 2.5, 7: 2.5,
    8: 20.0, 9: 20.0, 10: 20.0,
}

#: Digital port number (0 = D0..D7, 1 = D8..D15) to the SDK's
#: ``PS3000A_DIGITAL_PORT0`` / ``PORT1`` value (both accepted, measured).
DIGITAL_PORTS: Dict[int, int] = {0: 0x80, 1: 0x81}

#: Digital bits per port.
DIGITAL_BITS = 8

#: Status codes whose meaning was seen on the bench. Anything else is
#: reported by number; the SDK header's names are not repeated from memory.
STATUS_NAMES: Dict[int, str] = {
    0x00: "OK",
    0x03: "no PicoScope found (or it is in use by another program)",
    0x0E: "timebase not available with the channels enabled",
    0x0F: "voltage range not available on this model",
}

#: Statuses ``ps3000aOpenUnit`` returns when the unit opened but wants its
#: power source confirmed; ``ps3000aChangePowerSource`` takes the same code.
#: SDK header values, unverified: the bench unit opened with 0 on USB 2.0.
POWER_STATUSES = (0x119, 0x11A, 0x11E)


def status_text(status: int) -> str:
    """``"0x0E (timebase not available ...)"``, or the bare number."""
    name = STATUS_NAMES.get(status)
    return "0x%X (%s)" % (status, name) if name else "0x%X" % status


class UnitInfo:  # pylint: disable=too-few-public-methods
    """``PICO_INFO`` keys for ``ps3000aGetUnitInfo`` (0 to 5 read on the bench)."""

    DRIVER_VERSION = 0
    USB_VERSION = 1
    HARDWARE_VERSION = 2
    VARIANT = 3
    SERIAL = 4
    CAL_DATE = 5
    KERNEL_VERSION = 6
    DIGITAL_HARDWARE_VERSION = 7
    ANALOGUE_HARDWARE_VERSION = 8
    FIRMWARE_VERSION_1 = 9
    FIRMWARE_VERSION_2 = 10


def sample_interval_s(timebase: int) -> float:
    """Seconds between samples for *timebase* on the 3000D series.

    ``2**n`` ns for n below 3, then ``(n - 2) * 8`` ns. Measured with
    ``ps3000aGetTimebase2`` for n = 0 to 5, 10, 127 and 252.
    """
    if timebase < 0:
        raise ValueError("timebase must not be negative")
    if timebase < 3:
        return (1 << timebase) * 1e-9
    return (timebase - 2) * 8e-9


def timebase_for(interval_s: float) -> int:
    """The timebase whose interval is closest to, and not above, *interval_s*.

    An interval below 1 ns gives timebase 0. Whether the unit accepts the
    timebase depends on the channels enabled; the driver asks it.
    """
    if interval_s <= 0:
        raise ValueError("sample interval must be positive")
    best = 0
    for timebase in range(3):
        if sample_interval_s(timebase) <= interval_s * (1 + 1e-9):
            best = timebase
    if interval_s >= sample_interval_s(3) * (1 - 1e-9):
        best = max(3, int(interval_s / 8e-9 + 1e-9) + 2)
    return best


def range_for_volts(volts: float) -> int:
    """The ``PS3000A_RANGE`` index of the smallest range covering +/-*volts*.

    :raises ValueError: when *volts* exceeds the largest range.
    """
    wanted = abs(float(volts))
    for index in sorted(RANGES):
        if RANGES[index] >= wanted * (1 - 1e-9):
            return index
    raise ValueError(
        "+/-%g V is beyond the largest input range, +/-%g V" % (wanted, RANGE_VOLTS[-1])
    )


@dataclass(frozen=True)
class ModelLimits:  # pylint: disable=too-many-instance-attributes
    """What one model can do. Defaults are the PicoScope 3405D MSO."""

    model: str = "3405DMSO"
    channel_count: int = 4
    #: Spec page: 100 MHz for the 3405D.
    analogue_bandwidth_hz: float = 100e6
    #: Spec page: 1 GS/s with one channel; measured: timebase 0 refused with
    #: two channels enabled.
    max_sample_rate_hz: float = 1e9
    #: Measured: ``ps3000aGetTimebase2`` maxSamples with channel A only.
    max_samples: int = 268435200
    #: Spec page: 16 channels in 2 ports; both ports enabled (measured).
    digital_ports: int = 2
    #: Spec page: threshold range +/-5 V.
    digital_threshold_v: float = 5.0
    #: Spec page: 8 bits. Measured: ``ps3000aMaximumValue`` is 32512.
    max_adc: int = 32512
    #: Spec page: function generator DC to 1 MHz.
    siggen_max_frequency_hz: float = 1e6
    #: Spec page: output within +/-2 V overall.
    siggen_max_volts: float = 2.0
    #: Spec page: no digital or pattern outputs on the 3000D MSO.
    digital_outputs: int = 0

    @property
    def channels(self) -> Tuple["Channel", ...]:
        """The analogue channels this model has."""
        return tuple(Channel("ABCD"[index]) for index in range(self.channel_count))


#: The bench's unit, serial HT415/0202.
PS3405D_LIMITS = ModelLimits()
