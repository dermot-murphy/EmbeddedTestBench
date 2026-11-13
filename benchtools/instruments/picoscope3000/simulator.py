"""A simulated PicoScope 3405D MSO, behind the same methods as the SDK.

:class:`SimulatedPs3000a` stands where :class:`~.sdk.Ps3000aSdk` stands, so
the driver runs unchanged against it. It models what a test relies on:

- each analogue channel sees a signal (a :class:`ChannelSignal`), digitised
  with the range, offset and 8-bit resolution the driver set, clipped at full
  scale with the overflow bit set as the unit does;
- the signal generator output is wired to channel A, which is how the bench
  checks the generator (and how a known signal is made for the acceptance);
- digital bit *n* of port 0 is bit *n* of a counter clocked at 2 kHz, so D0 is
  a 1 kHz square wave and each higher bit half the frequency; port 1 is the
  same counter's next byte;
- edge triggers, analogue or digital, are found in the signal; with no edge
  and no auto-trigger the capture never completes, as on the unit;
- timebases follow the 3000D formula, and the fastest are refused when too
  many channels or ports are on, as the bench unit refused them (measured).

Traces to: PSCOPE-FR-020, PSCOPE-DD-SIM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ...core.errors import InstrumentError
from .constants import (
    DIGITAL_BITS,
    OFFSET_LIMITS,
    RANGES,
    PS3405D_LIMITS,
    UnitInfo,
    WaveType,
    sample_interval_s,
)
from .sdk import BlockData

__all__ = ["SimulatedPs3000a", "ChannelSignal"]


@dataclass
class ChannelSignal:
    """A periodic test signal: ``offset + amplitude * shape(frequency * t)``.

    :param shape: ``SINE``, ``SQUARE``, ``TRIANGLE`` or ``DC``.
    :param amplitude: Volts, half of peak-to-peak.
    """

    shape: str = "DC"
    frequency: float = 1e3
    amplitude: float = 0.0
    offset: float = 0.0

    def __call__(self, when: float) -> float:
        phase = (when * self.frequency) % 1.0
        shape = self.shape.upper()
        if shape in ("SINE", "SIN"):
            unit = math.sin(2 * math.pi * phase)
        elif shape == "SQUARE":
            unit = 1.0 if phase < 0.5 else -1.0
        elif shape == "TRIANGLE":
            unit = 4 * phase - 1 if phase < 0.5 else 3 - 4 * phase
        else:
            unit = 0.0
        return self.offset + self.amplitude * unit


def _default_signals() -> Dict[int, ChannelSignal]:
    return {
        1: ChannelSignal("SINE", 1e3, 1.0),            # replaced by the generator when on
        2: ChannelSignal("SQUARE", 1e3, 1.65, 1.65),   # 0 to 3.3 V logic
        3: ChannelSignal("TRIANGLE", 2e3, 0.5),
        4: ChannelSignal("DC", 0.0, 0.0, 1.2),
    }


#: Counter clock for the simulated digital inputs.
DIGITAL_CLOCK_HZ = 1e3

#: The most samples searched for a trigger edge before giving up.
_TRIGGER_SEARCH = 200000

#: Channels-plus-ports to the fastest timebase the bench unit accepted.
_FASTEST = {1: 0, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}


class SimulatedPs3000a:  # pylint: disable=too-many-instance-attributes
    """The simulated unit. Method names and arguments follow :class:`Ps3000aSdk`.

    :param signals: Channel number (1 = A) to the signal it sees.
    :param serial: The serial number it reports.
    """

    def __init__(self, signals: Optional[Dict[int, ChannelSignal]] = None,
                 serial: str = "SIM/0001") -> None:
        self.signals = _default_signals()
        self.signals.update(signals or {})
        self.serial = serial
        self._open = False
        self.channels: Dict[int, Tuple[bool, int, int, float]] = {
            index: (True, 1, 8, 0.0) for index in range(4)}
        self.ports: Dict[int, Tuple[bool, int]] = {0: (False, 0), 1: (False, 0)}
        self.trigger: Optional[Tuple] = None
        self.siggen: Optional[Tuple[int, int, int, float]] = None
        self._block: Optional[Tuple[int, int, int]] = None
        self._ready = False
        self._t0 = 0.0
        #: Every call made, for tests: ``(method, arguments)``.
        self.calls: List[Tuple[str, tuple]] = []

    # ------------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        """``True`` while open."""
        return self._open

    def open(self) -> None:
        """Open the simulated unit."""
        self.calls.append(("open", ()))
        self._open = True

    def close(self) -> None:
        """Close it."""
        self.calls.append(("close", ()))
        self._open = False

    def unit_info(self, key: int) -> str:
        """What the bench's 3405D MSO reports, with a simulated serial."""
        return {
            UnitInfo.DRIVER_VERSION: "simulated",
            UnitInfo.USB_VERSION: "2.0",
            UnitInfo.HARDWARE_VERSION: "1",
            UnitInfo.VARIANT: PS3405D_LIMITS.model,
            UnitInfo.SERIAL: self.serial,
            UnitInfo.CAL_DATE: "13Nov26",
        }.get(key, "")

    @staticmethod
    def maximum_value() -> int:
        """The 3405D's full-scale code (measured)."""
        return PS3405D_LIMITS.max_adc

    @staticmethod
    def analogue_offset_limits(range_index: int, coupling: int) -> Tuple[float, float]:
        """The limits measured on the bench unit."""
        del coupling
        if range_index not in OFFSET_LIMITS:
            raise InstrumentError("ps3000aGetAnalogueOffset failed: status 0xF",
                                  events=[(0x0F, "range")])
        return -OFFSET_LIMITS[range_index], OFFSET_LIMITS[range_index]

    def set_channel(self, index: int, enabled: bool, coupling: int, range_index: int,
                    offset_v: float) -> None:
        """Record the channel set-up."""
        self.calls.append(("set_channel", (index, enabled, coupling, range_index, offset_v)))
        if range_index not in RANGES:
            raise InstrumentError("ps3000aSetChannel failed: status 0xF", events=[(0x0F, "")])
        self.channels[index] = (bool(enabled), coupling, range_index, float(offset_v))

    def set_digital_port(self, port: int, enabled: bool, level: int) -> None:
        """Record the port set-up."""
        self.calls.append(("set_digital_port", (port, enabled, level)))
        self.ports[port] = (bool(enabled), level)

    def timebase(self, timebase: int, samples: int) -> Tuple[float, int]:
        """Refuse what the bench unit refused; report its memory."""
        on = sum(1 for setup in self.channels.values() if setup[0])
        ports = sum(1 for setup in self.ports.values() if setup[0])
        load = max(1, on + ports)
        if timebase < _FASTEST.get(load, 3):
            raise InstrumentError(
                "ps3000aGetTimebase2(%d) failed: status 0xE (timebase not available "
                "with the channels enabled)" % timebase, events=[(0x0E, "timebase")])
        most = PS3405D_LIMITS.max_samples // _memory_share(on, ports)
        if samples > most:
            raise InstrumentError("ps3000aGetTimebase2(%d) failed: too many samples" % timebase,
                                  events=[(0x0D, "samples")])
        return sample_interval_s(timebase), most

    def set_simple_trigger(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, enabled: bool, source: int, threshold: int,
            direction: int, delay: int, auto_ms: int) -> None:
        """Record an analogue edge trigger."""
        self.calls.append(("set_simple_trigger",
                           (enabled, source, threshold, direction, delay, auto_ms)))
        self.trigger = ("analog", source, threshold, direction, auto_ms) if enabled else None

    def set_digital_trigger(self, directions: Sequence[Tuple[int, int]], auto_ms: int) -> None:
        """Record a digital trigger."""
        self.calls.append(("set_digital_trigger", (tuple(directions), auto_ms)))
        self.trigger = ("digital", tuple(directions), auto_ms)

    def set_siggen(self, offset_uv: int, pk_to_pk_uv: int, wave: int,
                   frequency_hz: float) -> None:
        """Drive the generator, which is wired to channel A."""
        self.calls.append(("set_siggen", (offset_uv, pk_to_pk_uv, wave, frequency_hz)))
        self.siggen = (offset_uv, pk_to_pk_uv, wave, frequency_hz)

    # ------------------------------------------------------------------
    def signal(self, number: int) -> Callable[[float], float]:
        """What channel *number* (1 = A) sees, the generator included."""
        if number == 1 and self.siggen is not None:
            offset_uv, pk_uv, wave, frequency = self.siggen
            shape = {WaveType.SINE.code: "SINE", WaveType.SQUARE.code: "SQUARE",
                     WaveType.TRIANGLE.code: "TRIANGLE"}.get(wave, "DC")
            if wave == WaveType.DC_VOLTAGE.code:
                return ChannelSignal("DC", 0.0, 0.0, offset_uv * 1e-6)
            return ChannelSignal(shape, frequency, pk_uv * 0.5e-6, offset_uv * 1e-6)
        return self.signals[number]

    @staticmethod
    def counter(when: float) -> int:
        """The 16-bit counter on the digital inputs at time *when*."""
        return int(math.floor(when * DIGITAL_CLOCK_HZ * 2)) & 0xFFFF

    def _code(self, index: int, volts: float) -> int:
        _, _, range_index, offset = self.channels[index]
        full = PS3405D_LIMITS.max_adc
        code = int(round((volts + offset) / RANGES[range_index] * full))
        return max(-full, min(full, code))

    def _trigger_time(self, interval: float, pre: int) -> Optional[float]:  # pylint: disable=too-many-locals
        """Seconds of the first trigger edge after the pre-trigger fills."""
        if self.trigger is None:
            return 0.0
        start = pre * interval
        step = min(interval, 1e-6)
        if self.trigger[0] == "analog":
            _, source, threshold, direction, auto_ms = self.trigger
            function = self.signal(source + 1)
            previous = self._code(source, function(start))
            for count in range(1, _TRIGGER_SEARCH):
                when = start + count * step
                code = self._code(source, function(when))
                if _analog_hit(direction, previous, code, threshold):
                    return when
                previous = code
            return start if auto_ms else None
        _, directions, auto_ms = self.trigger
        previous = self.counter(start)
        for count in range(1, _TRIGGER_SEARCH):
            when = start + count * step
            value = self.counter(when)
            if all(_bit_matches((previous >> bit) & 1, (value >> bit) & 1, code)
                   for bit, code in directions):
                return when
            previous = value
        return start if auto_ms else None

    def run_block(self, pre: int, post: int, timebase: int) -> None:
        """Capture at once, or never if no trigger comes."""
        self.calls.append(("run_block", (pre, post, timebase)))
        interval = sample_interval_s(timebase)
        when = self._trigger_time(interval, pre)
        self._block = (pre, post, timebase)
        self._ready = when is not None
        self._t0 = (when or 0.0) - pre * interval

    def is_ready(self) -> bool:
        """Whether the block finished."""
        return self._ready

    def stop(self) -> None:
        """Abandon a capture."""
        self.calls.append(("stop", ()))
        self._ready = False

    def get_values(self, samples: int, channels: Sequence[int],  # pylint: disable=too-many-locals
                   ports: Sequence[int]) -> BlockData:
        """The digitised block."""
        if self._block is None or not self._ready:
            raise InstrumentError("ps3000aGetValues failed: no data", events=[(0x3B, "")])
        pre, post, timebase = self._block
        count = min(samples, pre + post)
        interval = sample_interval_s(timebase)
        times = [self._t0 + index * interval for index in range(count)]
        analog: Dict[int, List[int]] = {}
        overflow = 0
        full = PS3405D_LIMITS.max_adc
        for index in channels:
            function = self.signal(index + 1)
            codes = [self._code(index, function(when)) for when in times]
            if any(abs(code) >= full for code in codes):
                overflow |= 1 << index
            analog[index] = codes
        digital = {port: [(self.counter(when) >> (DIGITAL_BITS * port)) & 0xFF
                          for when in times] for port in ports}
        return BlockData(analog, digital, overflow)


def _memory_share(channels: int, ports: int) -> int:
    """Divisor of the memory, as measured: 1, 2, 4, then 8 with 4 + a port."""
    load = max(1, channels + ports)
    for limit, share in ((1, 1), (2, 2), (4, 4)):
        if load <= limit:
            return share
    return 8


def _analog_hit(direction: int, previous: int, code: int, threshold: int) -> bool:
    """Whether *previous* -> *code* meets threshold direction *direction*."""
    rising = previous < threshold <= code
    falling = previous > threshold >= code
    return {
        0: code > threshold,
        1: code < threshold,
        2: rising,
        3: falling,
        4: rising or falling,
    }.get(direction, False)


def _bit_matches(before: int, after: int, code: int) -> bool:
    """Whether a bit going *before* -> *after* satisfies direction *code*."""
    return {
        0: True,
        1: after == 0,
        2: after == 1,
        3: before == 0 and after == 1,
        4: before == 1 and after == 0,
        5: before != after,
    }[code]
