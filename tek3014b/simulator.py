"""Behavioural simulator of a TDS3014B oscilloscope.

The simulator answers the exact SCPI command set the driver emits, keeps
instrument state, synthesises waveform records and produces a real PNG for
hardcopy requests. It exists so that every layer of the driver above the
socket can be verified without hardware, which is what makes the unit test
suite reproducible in CI.

Signals are described analytically by :class:`ChannelSignal`, so the values the
simulator returns from the ``MEASUrement`` subsystem are computed from the
model parameters rather than from the sampled record. Host-side analysis can
therefore be checked against an independent reference instead of against
itself.

Traces to: SWE1-FR-090, SWE2-ARC-006, SWE3-DD-SIM, SWE4-UT-ENV.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import INVALID_MEASUREMENT

__all__ = ["ChannelSignal", "SimulatedTDS3014B", "make_png"]

#: Digitiser levels per vertical division on the TDS3000 family.
LEVELS_PER_DIVISION = 25.0

_DEFAULT_IDN = "TEKTRONIX,TDS 3014B,0,CF:91.1CT FV:v3.41 TDS3FFT:v1.00 TDS3TRG:v1.00"


def make_png(width: int = 160, height: int = 120) -> bytes:
    """Return a small but structurally valid truecolour PNG.

    Used as the simulated hardcopy image. The content is a graticule-like
    pattern so that a human opening the file can see it came from the
    simulator rather than from an instrument.
    """
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type 0 (None)
        for x in range(width):
            on_graticule = (x % (width // 10) == 0) or (y % (height // 8) == 0)
            if on_graticule:
                rows += bytes((60, 60, 60))
            else:
                rows += bytes((16, 16, 24))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


@dataclass
class ChannelSignal:
    """Analytic description of the signal present on one input.

    :param frequency: Repetition rate in hertz.
    :param amplitude: Peak-to-peak amplitude in volts.
    :param baseline: Low level in volts.
    :param duty: High-time fraction of the period, in ``0 < duty < 1``.
    :param rise_time: 0-100% transition time in seconds.
    :param fall_time: 100-0% transition time in seconds.
    :param delay: Time by which this channel's rising edge lags the trigger.
    :param present: When ``False`` the input is flat at ``baseline``.
    """

    frequency: float = 1.0e6
    amplitude: float = 2.0
    baseline: float = 0.0
    duty: float = 0.5
    rise_time: float = 2.0e-9
    fall_time: float = 2.0e-9
    delay: float = 0.0
    present: bool = True

    @property
    def period(self) -> float:
        """Signal period in seconds."""
        return 1.0 / self.frequency

    @property
    def high(self) -> float:
        """High level in volts."""
        return self.baseline + self.amplitude

    def value_at(self, t: float) -> float:
        """Return the ideal signal voltage at time *t* (seconds from trigger)."""
        if not self.present:
            return self.baseline
        period = self.period
        phase = (t - self.delay) % period
        high_end = self.duty * period
        if phase < self.rise_time:
            return self.baseline + self.amplitude * (phase / self.rise_time)
        if phase < high_end:
            return self.high
        if phase < high_end + self.fall_time:
            return self.high - self.amplitude * ((phase - high_end) / self.fall_time)
        return self.baseline


class SimulatedTDS3014B:
    """In-memory model of the instrument's SCPI interface.

    :param signals: Optional mapping of channel number to :class:`ChannelSignal`.
    :param idn: Identification string returned by ``*IDN?``.
    :param busy_polls: Number of ``BUSY?`` queries a sequence acquisition stays
        busy for, used to exercise the driver's polling loop.
    :param trigger_occurs: When ``False``, a ``NORMAL``-mode sequence
        acquisition never completes, which exercises the timeout path.
    """

    def __init__(
        self,
        signals: Optional[Dict[int, ChannelSignal]] = None,
        idn: str = _DEFAULT_IDN,
        busy_polls: int = 2,
        trigger_occurs: bool = True,
    ) -> None:
        self.idn = idn
        self.busy_polls = int(busy_polls)
        self.trigger_occurs = bool(trigger_occurs)
        self.signals: Dict[int, ChannelSignal] = signals or {
            1: ChannelSignal(delay=0.0),
            2: ChannelSignal(delay=4.0e-9),
            3: ChannelSignal(delay=9.0e-9),
            4: ChannelSignal(delay=1.0e-9),
        }
        #: Every command the simulator has received, in order. Tests assert on it.
        self.command_log: List[str] = []
        self.events: List[Tuple[int, str]] = []
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Return the model to its power-on defaults."""
        self.displayed = {1: True, 2: False, 3: False, 4: False}
        self.scale = {ch: 1.0 for ch in (1, 2, 3, 4)}
        self.position = {ch: 0.0 for ch in (1, 2, 3, 4)}
        self.offset = {ch: 0.0 for ch in (1, 2, 3, 4)}
        self.coupling = {ch: "DC" for ch in (1, 2, 3, 4)}
        self.bandwidth = {ch: "FULL" for ch in (1, 2, 3, 4)}
        self.probe = {ch: 1.0 for ch in (1, 2, 3, 4)}

        self.time_per_div = 1.0e-6
        self.horizontal_delay = 0.0
        self.record_length = 10000

        self.trigger_source = "CH1"
        self.trigger_slope = "RISE"
        self.trigger_coupling = "DC"
        self.trigger_level = 1.0
        self.trigger_mode = "AUTO"
        self.trigger_type = "EDGE"

        self.acquire_mode = "SAMPLE"
        self.num_avg = 16
        self.stop_after = "RUNSTOP"
        self.acquire_state = 0
        self._busy_remaining = 0

        self.data_source = "CH1"
        self.data_encoding = "RIBINARY"
        self.data_width = 1
        self.data_start = 1
        self.data_stop = 10000

        self.measurement_type = "PERIOD"
        self.measurement_source1 = "CH1"
        self.measurement_source2 = "CH2"
        self.measurement_edge1 = "RISE"
        self.measurement_edge2 = "RISE"
        self.measurement_direction = "FORWARDS"

        self.hardcopy_port = "GPIB"
        self.hardcopy_format = "PNG"
        self.hardcopy_layout = "PORTRAIT"
        self.hardcopy_palette = "COLOR"

        self.header_enabled = False
        self.verbose_enabled = False
        self.esr = 0
        self.events = []
        self._binary_reply: Optional[bytes] = None

    # ------------------------------------------------------------------
    # Waveform synthesis
    # ------------------------------------------------------------------
    @property
    def sample_interval(self) -> float:
        """Seconds between record points."""
        return (self.time_per_div * 10.0) / float(self.record_length)

    @property
    def trigger_point(self) -> float:
        """Record index of the trigger, used as ``PT_OFF``."""
        return self.record_length / 2.0

    def preamble(self, channel: int) -> Dict[str, float]:
        """Return the ``WFMPRE`` values the instrument would report."""
        y_mult = self.scale[channel] / LEVELS_PER_DIVISION
        if self.data_width == 2:
            y_mult /= 256.0
        return {
            "XINCR": self.sample_interval,
            "XZERO": -self.horizontal_delay,
            "PT_OFF": self.trigger_point,
            "YMULT": y_mult,
            "YZERO": self.offset[channel],
            "YOFF": self.position[channel] * LEVELS_PER_DIVISION * (256.0 if self.data_width == 2 else 1.0),
            "NR_PT": float(self.data_stop - self.data_start + 1),
        }

    def curve_codes(self, channel: int) -> List[int]:
        """Return the raw digitiser codes the instrument would transfer."""
        pre = self.preamble(channel)
        signal = self.signals.get(channel, ChannelSignal(present=False))
        limit = 32767 if self.data_width == 2 else 127
        codes = []
        for index in range(self.data_start - 1, self.data_stop):
            t = pre["XZERO"] + pre["XINCR"] * (index - pre["PT_OFF"])
            volts = signal.value_at(t)
            raw = int(round((volts - pre["YZERO"]) / pre["YMULT"] + pre["YOFF"]))
            codes.append(max(-limit - 1, min(limit, raw)))
        return codes

    def curve(self, channel: int) -> bytes:
        """Return the raw ``CURVe?`` payload for *channel* (no block header)."""
        fmt = ">h" if self.data_width == 2 else ">b"
        samples = bytearray()
        for raw in self.curve_codes(channel):
            samples += struct.pack(fmt, raw)
        return bytes(samples)

    # ------------------------------------------------------------------
    # Measurement synthesis
    # ------------------------------------------------------------------
    def _channel_number(self, source: str) -> Optional[int]:
        if source.startswith("CH") and source[2:].isdigit():
            number = int(source[2:])
            if number in self.signals:
                return number
        return None

    def measurement_value(self) -> float:
        """Return ``MEASUrement:IMMed:VALue?`` computed from the signal model."""
        channel = self._channel_number(self.measurement_source1)
        if channel is None or not self.displayed.get(channel, False):
            return INVALID_MEASUREMENT
        signal = self.signals[channel]
        if not signal.present:
            return INVALID_MEASUREMENT

        kind = self.measurement_type
        if kind == "PERIOD":
            return signal.period
        if kind == "FREQUENCY":
            return signal.frequency
        if kind in ("PK2PK", "AMPLITUDE"):
            return signal.amplitude
        if kind in ("HIGH", "MAXIMUM"):
            return signal.high
        if kind in ("LOW", "MINIMUM"):
            return signal.baseline
        if kind == "MEAN":
            return signal.baseline + signal.amplitude * signal.duty
        if kind == "RISE":
            return signal.rise_time * 0.8
        if kind == "FALL":
            return signal.fall_time * 0.8
        if kind == "PWIDTH":
            return signal.duty * signal.period
        if kind == "NWIDTH":
            return (1.0 - signal.duty) * signal.period
        if kind == "PDUTY":
            return signal.duty * 100.0
        if kind == "NDUTY":
            return (1.0 - signal.duty) * 100.0
        if kind == "RMS":
            high = signal.high
            low = signal.baseline
            return (signal.duty * high * high + (1.0 - signal.duty) * low * low) ** 0.5
        if kind == "DELAY":
            second = self._channel_number(self.measurement_source2)
            if second is None or not self.displayed.get(second, False):
                return INVALID_MEASUREMENT
            reference = self.signals[channel]
            target = self.signals[second]
            start = reference.delay + (0.0 if self.measurement_edge1 == "RISE"
                                       else reference.duty * reference.period)
            stop = target.delay + (0.0 if self.measurement_edge2 == "RISE"
                                   else target.duty * target.period)
            return stop - start
        return INVALID_MEASUREMENT

    def measurement_units(self) -> str:
        """Return ``MEASUrement:IMMed:UNIts?`` for the configured type."""
        if self.measurement_type in ("FREQUENCY",):
            return "Hz"
        if self.measurement_type in ("PDUTY", "NDUTY", "POVERSHOOT", "NOVERSHOOT", "PHASE"):
            return "%"
        if self.measurement_type in ("PERIOD", "RISE", "FALL", "PWIDTH", "NWIDTH", "DELAY", "BURST"):
            return "s"
        return "V"

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Process one raw SCPI message and return the raw reply.

        This is the entry point used by :class:`~tek3014b.transport.mock.MockTransport`.
        Text replies are encoded as ASCII and terminated with a line feed;
        binary replies (``CURVe?`` and ``HARDCopy STARt``) are returned
        verbatim, exactly as the instrument would stream them.
        """
        self._binary_reply = None
        text = self.handle(message.decode("ascii", errors="replace").strip())
        if self._binary_reply is not None:
            return self._binary_reply
        if text is None:
            return None
        return text.encode("ascii") + b"\n"

    def handle(self, message: str) -> Optional[str]:
        """Process one (possibly compound) SCPI message.

        :returns: The response string, or ``None`` when nothing is to be sent.
        """
        responses = []
        for element in message.split(";"):
            element = element.strip().lstrip(":")
            if not element:
                continue
            self.command_log.append(element)
            reply = self._dispatch(element)
            if reply is not None:
                responses.append(reply)
        return ";".join(responses) if responses else None

    def _dispatch(self, element: str) -> Optional[str]:
        upper = element.upper()
        head, _, argument = element.partition(" ")
        head = head.upper()
        argument = argument.strip()

        handler = getattr(self, "_cmd_" + _slug(head), None)
        if handler is not None:
            return handler(argument)

        # Channel-scoped commands: CH<n>:<setting>
        if head.startswith("CH") and ":" in head:
            channel_text, _, tail = head.partition(":")
            if channel_text[2:].isdigit():
                return self._channel_command(int(channel_text[2:]), tail, argument)

        self.events.append((113, 'Undefined header; command "%s"' % element))
        self.esr |= 0x20
        return None if not upper.endswith("?") else ""

    # -- IEEE 488.2 mandated ------------------------------------------
    def _cmd_IDN_Q(self, _argument: str) -> str:
        return self.idn

    def _cmd_RST(self, _argument: str) -> None:
        self.reset()
        return None

    def _cmd_CLS(self, _argument: str) -> None:
        self.events = []
        self.esr = 0
        return None

    def _cmd_OPC_Q(self, _argument: str) -> str:
        return "1"

    def _cmd_ESR_Q(self, _argument: str) -> str:
        value = self.esr
        self.esr = 0
        return str(value)

    def _cmd_STB_Q(self, _argument: str) -> str:
        return "0" if not self.events else "32"

    def _cmd_ALLEV_Q(self, _argument: str) -> str:
        if not self.events:
            return '0,"No events to report - queue empty"'
        text = ";".join('%d,"%s"' % item for item in self.events)
        self.events = []
        return text

    def _cmd_EVQTY_Q(self, _argument: str) -> str:
        return str(len(self.events))

    def _cmd_HEADER(self, argument: str) -> None:
        self.header_enabled = argument.upper() in ("ON", "1")
        return None

    def _cmd_VERBOSE(self, argument: str) -> None:
        self.verbose_enabled = argument.upper() in ("ON", "1")
        return None

    def _cmd_BUSY_Q(self, _argument: str) -> str:
        if self._busy_remaining > 0:
            self._busy_remaining -= 1
            if self._busy_remaining == 0 and self.trigger_occurs:
                self.acquire_state = 0
            return "1"
        if self.acquire_state == 1 and self.stop_after == "SEQUENCE" and not self.trigger_occurs:
            return "1"
        return "0"

    # -- Vertical -------------------------------------------------------
    def _cmd_SELECT_CH1(self, argument: str):
        return self._select(1, argument)

    def _cmd_SELECT_CH2(self, argument: str):
        return self._select(2, argument)

    def _cmd_SELECT_CH3(self, argument: str):
        return self._select(3, argument)

    def _cmd_SELECT_CH4(self, argument: str):
        return self._select(4, argument)

    def _cmd_SELECT_CH1_Q(self, _a: str) -> str:
        return "1" if self.displayed[1] else "0"

    def _cmd_SELECT_CH2_Q(self, _a: str) -> str:
        return "1" if self.displayed[2] else "0"

    def _cmd_SELECT_CH3_Q(self, _a: str) -> str:
        return "1" if self.displayed[3] else "0"

    def _cmd_SELECT_CH4_Q(self, _a: str) -> str:
        return "1" if self.displayed[4] else "0"

    def _select(self, channel: int, argument: str) -> None:
        self.displayed[channel] = argument.upper() in ("ON", "1")
        return None

    def _channel_command(self, channel: int, tail: str, argument: str) -> Optional[str]:
        if channel not in (1, 2, 3, 4):
            self.events.append((222, "Data out of range; no channel %d" % channel))
            return None
        query = tail.endswith("?")
        name = tail[:-1] if query else tail
        table = {
            "SCALE": (self.scale, float),
            "SCA": (self.scale, float),
            "POSITION": (self.position, float),
            "POS": (self.position, float),
            "OFFSET": (self.offset, float),
            "OFFS": (self.offset, float),
            "COUPLING": (self.coupling, str),
            "COUP": (self.coupling, str),
            "BANDWIDTH": (self.bandwidth, str),
            "BAN": (self.bandwidth, str),
            "PROBE": (self.probe, float),
        }
        if name not in table:
            self.events.append((113, "Undefined header; CH%d:%s" % (channel, tail)))
            return "" if query else None
        store, kind = table[name]
        if query:
            value = store[channel]
            return _format(value) if kind is float else str(value)
        if name == "PROBE":
            self.events.append((100, "Command error; CH:PROBE is query only"))
            return None
        store[channel] = float(argument) if kind is float else argument.upper()
        return None

    # -- Horizontal -----------------------------------------------------
    def _cmd_HORIZONTAL_MAIN_SCALE(self, argument: str) -> None:
        self.time_per_div = float(argument)
        return None

    def _cmd_HORIZONTAL_MAIN_SCALE_Q(self, _a: str) -> str:
        return _format(self.time_per_div)

    def _cmd_HORIZONTAL_DELAY_TIME(self, argument: str) -> None:
        self.horizontal_delay = float(argument)
        return None

    def _cmd_HORIZONTAL_DELAY_TIME_Q(self, _a: str) -> str:
        return _format(self.horizontal_delay)

    def _cmd_HORIZONTAL_RECORDLENGTH(self, argument: str) -> None:
        self.record_length = int(float(argument))
        self.data_stop = self.record_length
        return None

    def _cmd_HORIZONTAL_RECORDLENGTH_Q(self, _a: str) -> str:
        return str(self.record_length)

    # -- Trigger --------------------------------------------------------
    def _cmd_TRIGGER_A_TYPE(self, argument: str) -> None:
        self.trigger_type = argument.upper()
        return None

    def _cmd_TRIGGER_A_EDGE_SOURCE(self, argument: str) -> None:
        self.trigger_source = argument.upper()
        return None

    def _cmd_TRIGGER_A_EDGE_SOURCE_Q(self, _a: str) -> str:
        return self.trigger_source

    def _cmd_TRIGGER_A_EDGE_SLOPE(self, argument: str) -> None:
        self.trigger_slope = argument.upper()
        return None

    def _cmd_TRIGGER_A_EDGE_SLOPE_Q(self, _a: str) -> str:
        return self.trigger_slope

    def _cmd_TRIGGER_A_EDGE_COUPLING(self, argument: str) -> None:
        self.trigger_coupling = argument.upper()
        return None

    def _cmd_TRIGGER_A_EDGE_COUPLING_Q(self, _a: str) -> str:
        return self.trigger_coupling

    def _cmd_TRIGGER_A_LEVEL(self, argument: str) -> None:
        self.trigger_level = float(argument)
        return None

    def _cmd_TRIGGER_A_LEVEL_Q(self, _a: str) -> str:
        return _format(self.trigger_level)

    def _cmd_TRIGGER_A_MODE(self, argument: str) -> None:
        self.trigger_mode = argument.upper()
        return None

    def _cmd_TRIGGER_A_MODE_Q(self, _a: str) -> str:
        return self.trigger_mode

    def _cmd_TRIGGER_STATE_Q(self, _a: str) -> str:
        if self.acquire_state == 0:
            return "SAVE"
        if self._busy_remaining > 0:
            return "READY"
        return "TRIGGER" if self.trigger_occurs else "READY"

    def _cmd_TRIGGER(self, argument: str) -> None:
        if argument.upper() == "FORCE":
            self._busy_remaining = 0
            self.acquire_state = 0
        return None

    # -- Acquisition ----------------------------------------------------
    def _cmd_ACQUIRE_MODE(self, argument: str) -> None:
        self.acquire_mode = argument.upper()
        return None

    def _cmd_ACQUIRE_MODE_Q(self, _a: str) -> str:
        return self.acquire_mode

    def _cmd_ACQUIRE_NUMAVG(self, argument: str) -> None:
        self.num_avg = int(float(argument))
        return None

    def _cmd_ACQUIRE_NUMAVG_Q(self, _a: str) -> str:
        return str(self.num_avg)

    def _cmd_ACQUIRE_STOPAFTER(self, argument: str) -> None:
        self.stop_after = argument.upper()
        return None

    def _cmd_ACQUIRE_STOPAFTER_Q(self, _a: str) -> str:
        return self.stop_after

    def _cmd_ACQUIRE_STATE(self, argument: str) -> None:
        token = argument.upper()
        if token in ("RUN", "1", "ON"):
            self.acquire_state = 1
            self._busy_remaining = self.busy_polls if self.trigger_occurs else 0
        else:
            self.acquire_state = 0
            self._busy_remaining = 0
        return None

    def _cmd_ACQUIRE_STATE_Q(self, _a: str) -> str:
        return str(self.acquire_state)

    # -- Waveform transfer ----------------------------------------------
    def _cmd_DATA_SOURCE(self, argument: str) -> None:
        self.data_source = argument.upper()
        return None

    def _cmd_DATA_SOURCE_Q(self, _a: str) -> str:
        return self.data_source

    def _cmd_DATA_ENCDG(self, argument: str) -> None:
        self.data_encoding = argument.upper()
        return None

    def _cmd_DATA_ENCDG_Q(self, _a: str) -> str:
        return self.data_encoding

    def _cmd_DATA_WIDTH(self, argument: str) -> None:
        self.data_width = int(float(argument))
        return None

    def _cmd_DATA_WIDTH_Q(self, _a: str) -> str:
        return str(self.data_width)

    def _cmd_DATA_START(self, argument: str) -> None:
        self.data_start = int(float(argument))
        return None

    def _cmd_DATA_STOP(self, argument: str) -> None:
        self.data_stop = min(int(float(argument)), self.record_length)
        return None

    def _wfmpre_field(self, field_name: str) -> str:
        channel = self._channel_number(self.data_source)
        if channel is None:
            return "0"
        return _format(self.preamble(channel)[field_name])

    def _cmd_WFMPRE_XINCR_Q(self, _a: str) -> str:
        return self._wfmpre_field("XINCR")

    def _cmd_WFMPRE_XZERO_Q(self, _a: str) -> str:
        return self._wfmpre_field("XZERO")

    def _cmd_WFMPRE_PT_OFF_Q(self, _a: str) -> str:
        return self._wfmpre_field("PT_OFF")

    def _cmd_WFMPRE_YMULT_Q(self, _a: str) -> str:
        return self._wfmpre_field("YMULT")

    def _cmd_WFMPRE_YZERO_Q(self, _a: str) -> str:
        return self._wfmpre_field("YZERO")

    def _cmd_WFMPRE_YOFF_Q(self, _a: str) -> str:
        return self._wfmpre_field("YOFF")

    def _cmd_WFMPRE_NR_PT_Q(self, _a: str) -> str:
        return str(int(float(self._wfmpre_field("NR_PT"))))

    def _cmd_WFMPRE_XUNIT_Q(self, _a: str) -> str:
        return '"s"'

    def _cmd_WFMPRE_YUNIT_Q(self, _a: str) -> str:
        return '"V"'

    # -- Waveform data --------------------------------------------------
    def _cmd_CURVE_Q(self, _a: str) -> None:
        channel = self._channel_number(self.data_source)
        if self.data_encoding == "ASCII":
            codes = self.curve_codes(channel) if channel is not None else []
            self._binary_reply = (
                ",".join(str(code) for code in codes).encode("ascii") + b"\n"
            )
            return None
        payload = self.curve(channel) if channel is not None else b""
        count = str(len(payload)).encode("ascii")
        header = b"#" + str(len(count)).encode("ascii") + count
        self._binary_reply = header + payload + b"\n"
        return None

    # -- Measurement ----------------------------------------------------
    def _cmd_MEASUREMENT_IMMED_TYPE(self, argument: str) -> None:
        self.measurement_type = argument.upper()
        return None

    def _cmd_MEASUREMENT_IMMED_TYPE_Q(self, _a: str) -> str:
        return self.measurement_type

    def _cmd_MEASUREMENT_IMMED_SOURCE1(self, argument: str) -> None:
        self.measurement_source1 = argument.upper()
        return None

    def _cmd_MEASUREMENT_IMMED_SOURCE2(self, argument: str) -> None:
        self.measurement_source2 = argument.upper()
        return None

    def _cmd_MEASUREMENT_IMMED_DELAY_EDGE1(self, argument: str) -> None:
        self.measurement_edge1 = argument.upper()
        return None

    def _cmd_MEASUREMENT_IMMED_DELAY_EDGE2(self, argument: str) -> None:
        self.measurement_edge2 = argument.upper()
        return None

    def _cmd_MEASUREMENT_IMMED_DELAY_DIRECTION(self, argument: str) -> None:
        self.measurement_direction = argument.upper()
        return None

    def _cmd_MEASUREMENT_IMMED_VALUE_Q(self, _a: str) -> str:
        return _format(self.measurement_value())

    def _cmd_MEASUREMENT_IMMED_UNITS_Q(self, _a: str) -> str:
        return '"%s"' % self.measurement_units()

    # -- Hardcopy -------------------------------------------------------
    def _cmd_HARDCOPY_PORT(self, argument: str) -> None:
        self.hardcopy_port = argument.upper()
        return None

    def _cmd_HARDCOPY_FORMAT(self, argument: str) -> None:
        token = argument.upper()
        if token not in ("PNG", "TIFF", "BMP", "BMPCOLOR", "JPEG", "PCX", "PCXCOLOR", "RLE", "EPSIMAGE"):
            self.events.append((222, "Data out of range; unsupported hardcopy format"))
            return None
        self.hardcopy_format = token
        return None

    def _cmd_HARDCOPY_FORMAT_Q(self, _a: str) -> str:
        return self.hardcopy_format

    def _cmd_HARDCOPY_LAYOUT(self, argument: str) -> None:
        self.hardcopy_layout = argument.upper()
        return None

    def _cmd_HARDCOPY_PALETTE(self, argument: str) -> None:
        self.hardcopy_palette = argument.upper()
        return None

    def _cmd_HARDCOPY(self, argument: str) -> None:
        if argument.upper() != "START":
            self.events.append((113, "Undefined header; HARDCOPY %s" % argument))
            return None
        if self.hardcopy_port != "GPIB":
            # A real instrument would send the image to the selected port
            # instead of back over the command link, leaving the caller hanging.
            self.events.append((2244, "Hardcopy port is not the command interface"))
            return None
        self._binary_reply = make_png()
        return None


def _slug(head: str) -> str:
    """Map a SCPI header to the suffix of its handler method name."""
    text = head.upper().replace("*", "")
    if text.endswith("?"):
        text = text[:-1] + "_Q"
    return text.replace(":", "_")


def _format(value: float) -> str:
    """Format a float the way the instrument does (NR3, 6 significant digits)."""
    return "%.6E" % float(value)
