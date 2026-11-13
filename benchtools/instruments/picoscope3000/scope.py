"""PicoScope 3000D series MSO driver: four analogue channels, 16 digital.

Quick start::

    from benchtools.instruments.picoscope3000 import PicoScope3000

    with PicoScope3000.connect("pico://") as scope:        # or "sim://"
        scope.configure_channel("A", range_volts=2.0)
        scope.configure_digital_port(0, threshold=1.5)
        scope.set_sample_interval(2e-6)
        scope.set_record_length(10000)
        scope.configure_edge_trigger("A", level=0.0, slope="RISE")
        block = scope.capture()
        block.analog[1].peak_to_peak          # volts, a Waveform
        block.digital[0].volts[:8]            # D0, as 0.0 / 1.0

Every analogue record is a :class:`~benchtools.analysis.waveform.Waveform` in
seconds and volts, keyed by channel number (A is 1), the same form the
TDS3014B driver returns, so the analysis helpers take either. A digital bit is
a :class:`Waveform` too, of 0.0 and 1.0, with ``y_unit`` ``"bit"``: a 0.5
threshold finds its edges.

The scope is not a message-based instrument. It is reached through the
``ps3000a`` C library (:mod:`.sdk`), which a ``sim://`` resource replaces
with :class:`~.simulator.SimulatedPs3000a`.

Traces to: PSCOPE-ARC-001, PSCOPE-FR-001 .. PSCOPE-FR-020, PSCOPE-DD-SCOPE.
"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from ...analysis.measure import SpreadResult, measure_channel_spread
from ...analysis.waveform import Waveform, WaveformPreamble, waveforms_to_csv
from ...core.errors import AcquisitionTimeoutError, ConfigurationError
from ...core.instrument import Instrument, InstrumentIdentity
from .constants import (
    DIGITAL_BITS,
    MODEL,
    PS3405D_LIMITS,
    RANGES,
    Channel,
    Coupling,
    DigitalDirection,
    ModelLimits,
    ThresholdDirection,
    UnitInfo,
    WaveType,
    range_for_volts,
    sample_interval_s,
    timebase_for,
)
from .sdk import Ps3000aSdk
from .simulator import SimulatedPs3000a

__all__ = ["PicoScope3000", "ChannelSetup", "BlockCapture"]

ChannelLike = Union[int, str, Channel]


@dataclass
class ChannelSetup:
    """One analogue channel as the driver last set it."""

    channel: Channel
    enabled: bool = True
    range_volts: float = 5.0
    coupling: Coupling = Coupling.DC
    offset: float = 0.0


@dataclass
class BlockCapture:
    """One block: analogue and digital records on a common time base.

    :param analog: Channel number (A = 1) to its record.
    :param digital: Bit number (D0 = 0 .. D15 = 15) to its record of 0/1.
    :param overrange: Channel numbers that went beyond the range.
    """

    analog: Dict[int, Waveform] = field(default_factory=dict)
    digital: Dict[int, Waveform] = field(default_factory=dict)
    sample_interval: float = 0.0
    timebase: int = 0
    overrange: Tuple[int, ...] = ()

    def bits(self, bit: int) -> List[int]:
        """Bit *bit* as a list of 0 and 1."""
        return [int(value) for value in self.digital[bit].volts]

    def to_csv(self, path: str) -> str:
        """Write every record to one CSV: ``time_s``, ``A_volts``.., ``D0``..

        :returns: The path written.
        """
        records = [(waveform.source + "_volts", waveform, "%.9g")
                   for _, waveform in sorted(self.analog.items())]
        records += [(waveform.source, waveform, "%d")
                    for _, waveform in sorted(self.digital.items())]
        if not records:
            raise ValueError("the capture holds no records")
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        reference = records[0][1]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time_s"] + [name for name, _, _ in records])
            for index in range(len(reference)):
                writer.writerow(["%.12g" % reference.times[index]] + [
                    form % waveform.volts[index] for _, waveform, form in records])
        return path


class PicoScope3000(Instrument):  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """A PicoScope 3000D series MSO, through the ``ps3000a`` SDK.

    Construct with :meth:`connect`. Settings are held in the driver and sent
    to the unit as they are made; a capture checks the timebase against what
    is enabled before it starts.
    """

    SIMULATOR_CLASS = None  # not a Responder: sim:// is handled in connect()
    MODEL_NAME = MODEL
    EVENT_SOURCE = "PSCOPE"

    def __init__(self, sdk, limits: ModelLimits = PS3405D_LIMITS,
                 timeout: float = 10.0) -> None:
        super().__init__(auto_check_errors=False)
        self.sdk = sdk
        self._limits = limits
        self.timeout = float(timeout)
        self._max_adc = limits.max_adc
        self._channels: Dict[Channel, ChannelSetup] = {
            channel: ChannelSetup(channel, enabled=channel is Channel.A)
            for channel in limits.channels}
        self._ports: Dict[int, Tuple[bool, float]] = {
            port: (False, 1.5) for port in range(limits.digital_ports)}
        self._timebase = timebase_for(1e-6)
        self._samples = 10000
        self._pre_trigger = 0.2

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(  # pylint: disable=too-many-arguments
        cls,
        resource: str = "sim://",
        timeout: float = 10.0,
        sdk_path: Optional[str] = None,
        initialise: bool = True,
        simulated_signals: Optional[Mapping[int, object]] = None,
    ) -> "PicoScope3000":
        """Open a scope.

        :param resource: ``pico://`` for the first unit, ``pico://<serial>``
            for one unit (``pico://HT415/0202``), or ``sim://``.
        :param timeout: Seconds a capture may wait for its trigger, at most.
        :param sdk_path: Folder holding the ``ps3000a`` library, when it is
            not where PicoScope 7 or the PicoSDK put it.
        :param simulated_signals: ``sim://`` only: channel number to a
            :class:`~.simulator.ChannelSignal`.
        """
        text = str(resource or "").strip()
        if text.lower().startswith("sim"):
            sdk = SimulatedPs3000a(dict(simulated_signals or {}))
        elif text.lower().startswith("pico://") or text.lower() in ("pico", "usb", "usb://"):
            serial = text[len("pico://"):] if text.lower().startswith("pico://") else ""
            sdk = Ps3000aSdk(serial=serial or None, sdk_path=sdk_path)
        else:
            raise ConfigurationError(
                "a PicoScope resource is pico://, pico://<serial> or sim://, not %r" % resource)
        scope = cls(sdk, timeout=timeout)
        if initialise:
            try:
                scope.initialise()
            except Exception:
                scope.close()
                raise
        return scope

    def _open(self) -> None:
        if not self.sdk.is_open:
            self.sdk.open()

    def _post_open(self) -> None:
        self._max_adc = self.sdk.maximum_value()
        self._logger.info("opened %s", self.identify())
        for setup in self._channels.values():
            self._send_channel(setup)
        for port, (enabled, threshold) in self._ports.items():
            self.sdk.set_digital_port(port, enabled, self._level(threshold))
        self.sdk.set_simple_trigger(False, 0, 0, ThresholdDirection.RISE.code, 0, 0)

    def _close(self) -> None:
        self.sdk.close()

    @property
    def is_open(self) -> bool:
        return self.sdk.is_open

    def _read_identity(self) -> InstrumentIdentity:
        info = self.sdk.unit_info
        model = info(UnitInfo.VARIANT)
        serial = info(UnitInfo.SERIAL)
        driver = info(UnitInfo.DRIVER_VERSION)
        raw = "Pico Technology,PicoScope %s,%s,driver %s" % (model, serial, driver)
        return InstrumentIdentity(raw, "Pico Technology", "PicoScope " + model, serial,
                                  "driver " + driver)

    def unit_info(self) -> Dict[str, str]:
        """Everything the unit says about itself, by name."""
        names = {"driver": UnitInfo.DRIVER_VERSION, "usb": UnitInfo.USB_VERSION,
                 "hardware": UnitInfo.HARDWARE_VERSION, "variant": UnitInfo.VARIANT,
                 "serial": UnitInfo.SERIAL, "calibration_date": UnitInfo.CAL_DATE}
        return {name: self.sdk.unit_info(key) for name, key in names.items()}

    @property
    def limits(self) -> ModelLimits:
        """The model's capability envelope."""
        return self._limits

    # ------------------------------------------------------------------
    # Analogue channels
    # ------------------------------------------------------------------
    def _channel(self, channel: ChannelLike) -> Channel:
        try:
            resolved = Channel.parse(channel)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        if resolved not in self._channels:
            raise ConfigurationError("%s has no channel %s" % (self._limits.model, resolved.value))
        return resolved

    def _send_channel(self, setup: ChannelSetup) -> None:
        self.sdk.set_channel(setup.channel.sdk_index, setup.enabled, setup.coupling.code,
                             range_for_volts(setup.range_volts), setup.offset)

    def configure_channel(  # pylint: disable=too-many-arguments
        self,
        channel: ChannelLike,
        range_volts: Optional[float] = None,
        coupling: Union[Coupling, str, None] = None,
        offset: Optional[float] = None,
        enabled: bool = True,
    ) -> ChannelSetup:
        """Set one analogue channel. Unnamed settings keep their value.

        :param range_volts: The full scale, +/- volts. Rounded up to the next
            range the scope has: 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20.
        :param coupling: ``DC`` or ``AC``.
        :param offset: Volts added to the input before it is digitised, so
            the channel reads the input around ``-offset``. Its limit depends on
            the range: +/-0.25 V up to 0.2 V, +/-2.5 V up to 2 V, +/-20 V above.
        :returns: The channel's set-up as sent.
        """
        resolved = self._channel(channel)
        setup = self._channels[resolved]
        new = ChannelSetup(
            resolved,
            enabled=bool(enabled),
            range_volts=setup.range_volts if range_volts is None else float(range_volts),
            coupling=setup.coupling if coupling is None else Coupling.coerce(coupling),
            offset=setup.offset if offset is None else float(offset),
        )
        try:
            index = range_for_volts(new.range_volts)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        new.range_volts = RANGES[index]
        low, high = self.sdk.analogue_offset_limits(index, new.coupling.code)
        if not low - 1e-9 <= new.offset <= high + 1e-9:
            raise ConfigurationError(
                "offset %g V is outside %g to %g V on the +/-%g V range"
                % (new.offset, low, high, new.range_volts))
        self._send_channel(new)
        self._channels[resolved] = new
        return new

    def enable_channel(self, channel: ChannelLike, enabled: bool = True) -> None:
        """Switch one analogue channel on or off, keeping its settings."""
        setup = self._channels[self._channel(channel)]
        self.configure_channel(setup.channel, enabled=enabled)

    def get_channel_setup(self, channel: ChannelLike) -> ChannelSetup:
        """The channel's set-up as last sent."""
        return self._channels[self._channel(channel)]

    def enabled_channels(self) -> List[int]:
        """Numbers (A = 1) of the analogue channels that are on."""
        return [setup.channel.number for setup in self._channels.values() if setup.enabled]

    # ------------------------------------------------------------------
    # Digital inputs
    # ------------------------------------------------------------------
    def _level(self, threshold: float) -> int:
        limit = self._limits.digital_threshold_v
        if abs(threshold) > limit + 1e-9:
            raise ConfigurationError("digital threshold %g V is beyond +/-%g V"
                                     % (threshold, limit))
        return int(round(threshold / limit * 32767))

    def configure_digital_port(self, port: int, enabled: bool = True,
                               threshold: float = 1.5) -> None:
        """Switch a digital port on: 0 is D0..D7, 1 is D8..D15.

        :param threshold: Logic threshold in volts, within +/-5 V.
        """
        if port not in self._ports:
            raise ConfigurationError("digital port %r is not 0 or 1" % (port,))
        level = self._level(float(threshold))
        self.sdk.set_digital_port(port, bool(enabled), level)
        self._ports[port] = (bool(enabled), float(threshold))

    def enabled_ports(self) -> List[int]:
        """The digital ports that are on."""
        return [port for port, (enabled, _) in self._ports.items() if enabled]

    # ------------------------------------------------------------------
    # Timebase
    # ------------------------------------------------------------------
    def set_timebase(self, timebase: int) -> float:
        """Use SDK timebase *timebase*; returns its sample interval in seconds."""
        if int(timebase) < 0:
            raise ConfigurationError("timebase must not be negative")
        self._timebase = int(timebase)
        return sample_interval_s(self._timebase)

    def set_sample_interval(self, seconds: float) -> float:
        """Use the fastest timebase not faster than *seconds* per sample.

        :returns: The interval used, which may be shorter than asked.
        """
        try:
            return self.set_timebase(timebase_for(float(seconds)))
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc

    @property
    def sample_interval(self) -> float:
        """Seconds between samples at the current timebase."""
        return sample_interval_s(self._timebase)

    def set_record_length(self, samples: int, pre_trigger: Optional[float] = None) -> None:
        """Capture *samples* points, *pre_trigger* (0 to 1) of them before it."""
        if int(samples) < 2:
            raise ConfigurationError("a record needs at least 2 samples")
        if pre_trigger is not None and not 0.0 <= float(pre_trigger) <= 1.0:
            raise ConfigurationError("pre_trigger is a fraction from 0 to 1")
        self._samples = int(samples)
        if pre_trigger is not None:
            self._pre_trigger = float(pre_trigger)

    def get_record_length(self) -> int:
        """Points per capture."""
        return self._samples

    # ------------------------------------------------------------------
    # Trigger
    # ------------------------------------------------------------------
    def configure_edge_trigger(  # pylint: disable=too-many-arguments
        self,
        source: ChannelLike = "A",
        level: float = 0.0,
        slope: Union[str, ThresholdDirection] = "RISE",
        auto_ms: int = 0,
        delay_samples: int = 0,
    ) -> None:
        """Trigger on an analogue channel crossing *level* volts.

        :param slope: ``RISE``, ``FALL``, ``EITHER``, ``ABOVE`` or ``BELOW``.
        :param auto_ms: Capture anyway after this many milliseconds without
            a trigger; 0 waits for the trigger (until the capture's timeout).
        """
        channel = self._channel(source)
        setup = self._channels[channel]
        if not -setup.range_volts <= level + setup.offset <= setup.range_volts:
            raise ConfigurationError(
                "trigger level %g V is outside channel %s's range" % (level, channel.value))
        direction = ThresholdDirection.coerce(slope)
        threshold = int(round((level + setup.offset) / setup.range_volts * self._max_adc))
        self.sdk.set_simple_trigger(True, channel.sdk_index, threshold, direction.code,
                                    int(delay_samples), int(auto_ms))

    def configure_digital_trigger(self, conditions: Mapping[int, Union[str, DigitalDirection]],
                                  auto_ms: int = 0) -> None:
        """Trigger when every named bit meets its condition at once.

        :param conditions: Bit (0 to 15) to ``RISE``, ``FALL``, ``EITHER``,
            ``HIGH`` or ``LOW``, e.g. ``{0: "RISE", 3: "HIGH"}``.
        """
        if not conditions:
            raise ConfigurationError("a digital trigger needs at least one bit")
        pairs = []
        for bit, condition in conditions.items():
            bit = int(bit)
            if not 0 <= bit < DIGITAL_BITS * self._limits.digital_ports:
                raise ConfigurationError("digital bit %d is not 0 to 15" % bit)
            if not self._ports[bit // DIGITAL_BITS][0]:
                raise ConfigurationError("D%d's port %d is off" % (bit, bit // DIGITAL_BITS))
            pairs.append((bit, DigitalDirection.coerce(condition).code))
        self.sdk.set_digital_trigger(pairs, int(auto_ms))

    def disable_trigger(self) -> None:
        """Capture at once, untriggered."""
        self.sdk.set_simple_trigger(False, 0, 0, ThresholdDirection.RISE.code, 0, 0)

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------
    def capture(self, timeout: Optional[float] = None) -> BlockCapture:
        """Capture one block of every enabled channel and port.

        :raises AcquisitionTimeoutError: when no trigger came within *timeout*.
        :raises InstrumentError: when the unit refuses the timebase or length
            with what is enabled; the message says which.
        """
        channels = [setup.channel for setup in self._channels.values() if setup.enabled]
        ports = self.enabled_ports()
        if not channels and not ports:
            raise ConfigurationError("no channel or digital port is enabled")
        interval, _ = self.sdk.timebase(self._timebase, self._samples)
        pre = int(round(self._samples * self._pre_trigger))
        self.sdk.run_block(pre, self._samples - pre, self._timebase)
        limit = self.timeout if timeout is None else float(timeout)
        deadline = time.monotonic() + limit
        while not self.sdk.is_ready():
            if time.monotonic() > deadline:
                self.sdk.stop()
                raise AcquisitionTimeoutError(
                    "no trigger within %.3g s; check the trigger, or set auto_ms" % limit)
            time.sleep(0.005)
        data = self.sdk.get_values(self._samples, [c.sdk_index for c in channels], ports)
        return self._scale(data, channels, ports, interval, pre)

    def _scale(self, data, channels: Sequence[Channel], ports: Sequence[int],  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
               interval: float, pre: int) -> BlockCapture:
        block = BlockCapture(sample_interval=interval, timebase=self._timebase)
        for channel in channels:
            setup = self._channels[channel]
            codes = data.analog[channel.sdk_index]
            preamble = WaveformPreamble(
                x_increment=interval, x_zero=0.0, point_offset=float(pre),
                y_multiplier=setup.range_volts / self._max_adc, y_zero=-setup.offset,
                y_offset=0.0, point_count=len(codes))
            record = Waveform.from_codes(channel.value, codes, preamble)
            record.full_scale_code = self._max_adc
            block.analog[channel.number] = record
        for port in ports:
            codes = data.digital[port]
            for offset in range(DIGITAL_BITS):
                bit = port * DIGITAL_BITS + offset
                preamble = WaveformPreamble(
                    x_increment=interval, x_zero=0.0, point_offset=float(pre),
                    y_multiplier=1.0, y_zero=0.0, y_offset=0.0,
                    point_count=len(codes), y_unit="bit")
                values = [(code >> offset) & 1 for code in codes]
                record = Waveform.from_codes("D%d" % bit, values, preamble)
                record.full_scale_code = 2  # a bit is never "clipped"
                block.digital[bit] = record
        block.overrange = tuple(channel.number for channel in channels
                                if data.overflow & (1 << channel.sdk_index))
        if block.overrange:
            self._logger.warning("channel(s) %s over range", ", ".join(
                "ABCD"[number - 1] for number in block.overrange))
        return block

    def capture_single(self, channels: Optional[Iterable[ChannelLike]] = None,
                       timeout: Optional[float] = None) -> Dict[int, Waveform]:
        """Capture and return the analogue records only, as the TDS3014B does.

        :param channels: Return only these (they must be enabled).
        """
        block = self.capture(timeout=timeout)
        if channels is None:
            return block.analog
        wanted = [self._channel(channel).number for channel in channels]
        missing = [number for number in wanted if number not in block.analog]
        if missing:
            raise ConfigurationError("channel(s) %s are not enabled" % ", ".join(
                "ABCD"[number - 1] for number in missing))
        return {number: block.analog[number] for number in wanted}

    def measure_channel_spread(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        channels: Sequence[ChannelLike],
        direction: str = "RISE",
        percent: float = 50.0,
        absolute_threshold: Optional[float] = None,
        edge_index: int = 0,
        reference: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[Dict[int, Waveform], SpreadResult]:
        """Capture *channels* together and report how far apart they switch.

        The same step as the TDS3014B's, so a specification runs on either.
        """
        if len(list(channels)) < 2:
            raise ConfigurationError("a timing spread needs at least two channels")
        records = self.capture_single(channels, timeout=timeout)
        return records, measure_channel_spread(
            records, direction=direction, percent=percent,
            absolute_threshold=absolute_threshold, edge_index=edge_index,
            reference=reference)

    @staticmethod
    def save_csv(waveforms: Mapping[int, Waveform], path: str) -> str:
        """Write records captured together to one CSV."""
        return waveforms_to_csv(dict(waveforms), path)

    # ------------------------------------------------------------------
    # Signal generator
    # ------------------------------------------------------------------
    def set_signal_generator(
        self,
        waveform: Union[str, WaveType] = "SINE",
        frequency: float = 1e3,
        amplitude_pp: float = 1.0,
        offset: float = 0.0,
    ) -> None:
        """Run the built-in generator continuously.

        :param amplitude_pp: Peak-to-peak volts.
        :param offset: Volts. Offset plus half the amplitude stays within
            +/-2 V, and the frequency within 0 to 1 MHz (spec page).
        """
        wave = WaveType.coerce(waveform)
        limit = self._limits.siggen_max_volts
        if amplitude_pp < 0 or abs(offset) + amplitude_pp / 2 > limit + 1e-9:
            raise ConfigurationError(
                "%g V peak-to-peak at %g V offset leaves the generator's +/-%g V"
                % (amplitude_pp, offset, limit))
        if not 0 <= frequency <= self._limits.siggen_max_frequency_hz:
            raise ConfigurationError("generator frequency %g Hz is outside 0 to %g Hz"
                                     % (frequency, self._limits.siggen_max_frequency_hz))
        self.sdk.set_siggen(int(round(offset * 1e6)), int(round(amplitude_pp * 1e6)),
                            wave.code, float(frequency))

    def signal_generator_off(self) -> None:
        """Drive the generator output to 0 V DC."""
        self.sdk.set_siggen(0, 0, WaveType.DC_VOLTAGE.code, 0.0)
