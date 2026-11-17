"""The PPK2's wire format: commands out, metadata and samples in.

Nothing here touches a port. :func:`parse_metadata` reads the kit's metadata
text, :class:`Calibration` holds the per-range constants it carries, and
:class:`SampleDecoder` turns the 32-bit words the kit streams into amps and
logic levels, as Nordic's Power Profiler app does: the same formula, the same
spike filter after a range change, the same sample counter.

Traces to: PPK-FR-002 .. PPK-FR-004, PPK-DD-PROTOCOL.
"""

from __future__ import annotations

import math
import struct
from array import array
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .constants import (
    ADC_BITS,
    ADC_MULT,
    CMD_AVERAGE_START,
    CMD_AVERAGE_STOP,
    CMD_DEVICE_RUNNING_SET,
    CMD_GET_METADATA,
    CMD_REGULATOR_SET,
    CMD_SET_POWER_MODE,
    COUNTER_MASK,
    COUNTER_SHIFT,
    DEFAULT_MODIFIERS,
    LOGIC_MASK,
    LOGIC_SHIFT,
    MODE_NAMES,
    RANGE_MASK,
    RANGE_SHIFT,
    RANGES,
    SAMPLE_BYTES,
    SPIKE_ALPHA,
    SPIKE_ALPHA_TOP,
    SPIKE_SAMPLES,
    VOLTAGE_RANGE,
)

__all__ = [
    "parse_metadata",
    "Calibration",
    "SampleDecoder",
    "split_word",
    "metadata_command",
    "start_command",
    "stop_command",
    "running_command",
    "mode_command",
    "regulator_command",
    "millivolts",
]


def parse_metadata(text: str) -> Dict[str, Any]:
    """The kit's metadata, ``Name: value`` per line up to ``END``, as a dict.

    Keys are lower case, as Nordic's app reads them (``r0``, ``vdd``,
    ``mode``, ``hw``). A whole number is an ``int``, any other number a
    ``float``, ``-nan`` is ``None``, and anything else is kept as text.
    """
    meta: Dict[str, Any] = {}
    for line in text.replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line == "END":
            continue
        name, separator, value = line.partition(":")
        if not separator:
            continue
        meta[name.strip().lower()] = _value(value.strip())
    return meta


def _value(text: str) -> Any:
    if text.lower() in ("-nan", "nan"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _number(value: Any, default: float) -> float:
    """*value* as a float; *default* for one missing, zero or not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value:
        return default
    return float(value)


@dataclass(frozen=True)
class Calibration:
    """The per-range constants that turn an ADC count into amps.

    Each is a tuple of five, one per current range. The kit's metadata gives
    them; a value it does not give, or gives as ``-nan``, keeps Nordic's
    default (:data:`~.constants.DEFAULT_MODIFIERS`).
    """

    r: Tuple[float, ...] = DEFAULT_MODIFIERS["r"]
    gs: Tuple[float, ...] = DEFAULT_MODIFIERS["gs"]
    gi: Tuple[float, ...] = DEFAULT_MODIFIERS["gi"]
    o: Tuple[float, ...] = DEFAULT_MODIFIERS["o"]
    s: Tuple[float, ...] = DEFAULT_MODIFIERS["s"]
    i: Tuple[float, ...] = DEFAULT_MODIFIERS["i"]
    ug: Tuple[float, ...] = DEFAULT_MODIFIERS["ug"]

    @classmethod
    def from_metadata(cls, meta: Dict[str, Any]) -> "Calibration":
        """The calibration *meta* (from :func:`parse_metadata`) carries.

        As in Nordic's app, a value of zero also keeps the default: the app
        takes ``meta[key] || default``.
        """
        values = {}
        for key, defaults in DEFAULT_MODIFIERS.items():
            values[key] = tuple(_number(meta.get("%s%d" % (key, index)), default)
                                for index, default in enumerate(defaults))
        return cls(**values)

    def amps(self, current_range: int, adc: int, vdd_mv: float) -> float:
        """The current, in amps, an ADC reading *adc* (already times 4) means."""
        k = current_range
        raw = (adc - self.o[k]) * (ADC_MULT / self.r[k])
        return self.ug[k] * (raw * (self.gs[k] * raw + self.gi[k])
                             + (self.s[k] * (vdd_mv / 1000.0) + self.i[k]))

    def adc(self, current_range: int, amps: float, vdd_mv: float) -> int:
        """The ADC reading (times 4) that :meth:`amps` reads as *amps*.

        For the simulator. It inverts the formula with the quadratic term
        and returns the nearest reading the kit can send.
        """
        k = current_range
        target = amps / self.ug[k] - (self.s[k] * (vdd_mv / 1000.0) + self.i[k])
        if self.gs[k]:
            disc = self.gi[k] ** 2 + 4.0 * self.gs[k] * target
            raw = (-self.gi[k] + math.sqrt(max(disc, 0.0))) / (2.0 * self.gs[k])
        else:
            raw = target / self.gi[k]
        count = raw / (ADC_MULT / self.r[k]) + self.o[k]
        return max(0, min(ADC_BITS, int(round(count / 4.0)))) * 4


def split_word(word: int) -> Tuple[int, int, int, int]:
    """A streamed sample's parts: ``(adc, range, counter, logic)``.

    *adc* is the 14-bit reading times 4, as the formula takes it; *range* is
    capped at the top range, as Nordic's app does.
    """
    adc = (word & ADC_BITS) * 4
    current_range = min((word >> RANGE_SHIFT) & RANGE_MASK, RANGES - 1)
    counter = (word >> COUNTER_SHIFT) & COUNTER_MASK
    logic = (word >> LOGIC_SHIFT) & LOGIC_MASK
    return adc, current_range, counter, logic


@dataclass
class SampleDecoder:  # pylint: disable=too-many-instance-attributes
    """Turns the kit's byte stream into currents and logic levels.

    Feed it every byte read while sampling, in order, with :meth:`feed`; it
    keeps a word split across two reads. :attr:`amps` and :attr:`logic` grow
    by one entry per sample. :attr:`lost` counts samples the counter says
    never arrived - at least that many: the counter is six bits, so a gap of
    exactly 64 reads as none; they are not filled in, so the time base closes up across
    a gap, and a measurement with any lost reports it.

    :param calibration: The kit's calibration.
    :param vdd_mv: The regulator voltage, which the formula takes.
    :param spike_filter: Smooth the samples after a range change, as Nordic's
        app does by default.
    """

    calibration: Calibration
    vdd_mv: float
    spike_filter: bool = True
    amps: array = field(default_factory=lambda: array("d"))
    logic: array = field(default_factory=lambda: array("B"))
    lost: int = 0

    def __post_init__(self) -> None:
        self._remainder = b""
        self._expected: Optional[int] = None
        self._rolling: Optional[float] = None
        self._rolling_top: Optional[float] = None
        self._previous_range: Optional[int] = None
        self._after_spike = 0
        self._in_range = 0

    def feed(self, data: bytes) -> int:
        """Decode *data*; return how many samples it completed."""
        data = self._remainder + bytes(data)
        whole = len(data) - len(data) % SAMPLE_BYTES
        self._remainder = data[whole:]
        count = 0
        for (word,) in struct.iter_unpack("<I", data[:whole]):
            self._sample(word)
            count += 1
        return count

    @property
    def count(self) -> int:
        """Samples decoded so far."""
        return len(self.amps)

    def _sample(self, word: int) -> None:
        adc, current_range, counter, logic = split_word(word)
        if self._expected is not None and counter != self._expected:
            self.lost += (counter - self._expected) & COUNTER_MASK
        self._expected = (counter + 1) & COUNTER_MASK
        value = self.calibration.amps(current_range, adc, self.vdd_mv)
        if self.spike_filter:
            value = self._filter(current_range, value)
        self.amps.append(value)
        self.logic.append(logic)

    def _filter(self, current_range: int, value: float) -> float:
        """Nordic's spike filter (``getAdcResult``), sample by sample."""
        before, before_top = self._rolling, self._rolling_top
        self._rolling = value if before is None else (
            SPIKE_ALPHA * value + (1.0 - SPIKE_ALPHA) * before)
        self._rolling_top = value if before_top is None else (
            SPIKE_ALPHA_TOP * value + (1.0 - SPIKE_ALPHA_TOP) * before_top)
        if self._previous_range is None:
            self._previous_range = current_range
        if self._previous_range != current_range or self._after_spike > 0:
            if self._previous_range != current_range:
                self._in_range = 0
                self._after_spike = SPIKE_SAMPLES
            else:
                self._in_range += 1
            if current_range == RANGES - 1:
                if self._in_range < 2:
                    self._rolling, self._rolling_top = before, before_top
                value = self._rolling_top if self._rolling_top is not None else value
            else:
                value = self._rolling if self._rolling is not None else value
            self._after_spike -= 1
        self._previous_range = current_range
        return value


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------
def metadata_command() -> bytes:
    """Ask for the metadata text."""
    return bytes([CMD_GET_METADATA])


def start_command() -> bytes:
    """Start streaming samples."""
    return bytes([CMD_AVERAGE_START])


def stop_command() -> bytes:
    """Stop streaming samples."""
    return bytes([CMD_AVERAGE_STOP])


def running_command(on: bool) -> bytes:
    """Switch the DUT's power: the kit's supply (source) or its path (ammeter)."""
    return bytes([CMD_DEVICE_RUNNING_SET, 1 if on else 0])


def mode_command(mode: int) -> bytes:
    """Select ammeter (1) or source (2) mode."""
    if mode not in MODE_NAMES:
        raise ValueError("mode must be one of %s, got %r" % (sorted(MODE_NAMES), mode))
    return bytes([CMD_SET_POWER_MODE, mode])


def millivolts(volts: float) -> int:
    """*volts* in whole millivolts, checked against the regulator's range."""
    low, high = VOLTAGE_RANGE
    value = float(volts)
    if not low <= value <= high:
        raise ValueError("the PPK2 sources %.1f V to %.1f V, not %g V" % (low, high, value))
    return int(round(value * 1000.0))


def regulator_command(volts: float) -> bytes:
    """Set the regulator: millivolts, high byte first."""
    mv = millivolts(volts)
    return bytes([CMD_REGULATOR_SET, (mv >> 8) & 0xFF, mv & 0xFF])
