"""High-level driver for the Tektronix TDS3014B oscilloscope.

This is the module callers use. It owns the TDS3000 SCPI vocabulary, validates
settings against the instrument's capability envelope *before* they reach the
wire, and turns raw responses into typed results.

Everything that is not specific to this instrument comes from
:class:`~benchtools.core.scpi.ScpiInstrument`: the link lifecycle, command and
query primitives, identification, and error checking. It knows nothing about
how bytes reach the instrument - that is the transport's job - which is why the
same code drives a real scope over VXI-11, a VISA session, or the built-in
simulator.

Typical use::

    from benchtools.instruments.tek3014b import Tek3014B

    with Tek3014B.connect("192.168.1.50") as scope:
        scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0)
        scope.configure_channel(2, volts_per_div=1.0, position_div=0.0)
        scope.set_time_per_div(100e-9)
        scope.configure_edge_trigger(source=1, level=1.4)
        waveforms = scope.capture_single([1, 2])
        print(scope.measure_period(1))

Traces to: SCOPE-FR-010 .. SCOPE-FR-081, SCOPE-ARC-001, SCOPE-DD-SCOPE.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from ...analysis.measure import (
    SpreadResult,
    measure_channel_spread,
    measure_period as analyse_period,
)
from ...analysis.waveform import Waveform, WaveformPreamble, waveforms_to_csv
from ...core.errors import (
    AcquisitionTimeoutError,
    ConfigurationError,
    MeasurementError,
    ProtocolError,
)
from ...core.scpi import ScpiInstrument, parse_ieee_block
from ...core.transport.base import Transport
from ...core.validation import validate_channel, validate_channels, validate_range
from .simulator import SimulatedTDS3014B
from .constants import (
    INVALID_MEASUREMENT,
    AcquisitionMode,
    Bandwidth,
    Coupling,
    DataEncoding,
    DelayDirection,
    EdgeDirection,
    HardcopyLayout,
    HardcopyPalette,
    ImageFormat,
    MeasurementType,
    ModelLimits,
    Slope,
    StopAfter,
    TDS3014B_LIMITS,
    TriggerMode,
    TriggerSource,
    TriggerState,
)

__all__ = ["Tek3014B", "ChannelSetup"]


#: Fields fetched from the ``WFMPre`` subsystem, in the order they are queried.
_PREAMBLE_FIELDS = ("XINCR", "XZERO", "PT_OFF", "YMULT", "YZERO", "YOFF", "NR_PT")

#: Encodings whose raw codes are signed.
_SIGNED_ENCODINGS = (DataEncoding.RIBINARY, DataEncoding.SRIBINARY)


@dataclass
class ChannelSetup:
    """Declarative vertical setup for one input.

    Any field left as ``None`` is not sent, so an existing front-panel setting
    is preserved.

    :param channel: Input number, 1 to 4.
    :param enabled: Display (and therefore digitise) the channel.
    :param volts_per_div: Vertical sensitivity in volts per division.
    :param position_div: Vertical position in divisions; positive moves the
        trace up. This is the screen position, and it does not change the
        voltage the input sees.
    :param offset_v: Vertical offset in volts, subtracted at the input.
    :param coupling: Input coupling.
    :param bandwidth: Input bandwidth limit.
    """

    channel: int
    enabled: bool = True
    volts_per_div: Optional[float] = None
    position_div: Optional[float] = None
    offset_v: Optional[float] = None
    coupling: Optional[Union[Coupling, str]] = None
    bandwidth: Optional[Union[Bandwidth, str]] = None


class Tek3014B(ScpiInstrument):
    """Driver for a TDS3014B (and the wider TDS3000/TDS3000B/C family).

    :param transport: An open or unopened
        :class:`~tek3014b.transport.base.Transport`.
    :param limits: Capability envelope used to validate settings.
    :param auto_check_errors: Query the instrument's event queue after each
        configuration operation and raise :class:`~tek3014b.errors.InstrumentError`
        if it reported anything. Costs one round trip per operation; turn it
        off for maximum throughput once a sequence is known-good.
    :param owns_transport: Close the transport when :meth:`close` is called.
    """

    #: Supplies the instrument model for a ``sim://`` resource, so the shared
    #: transport layer needs no knowledge of this instrument.
    SIMULATOR_CLASS = SimulatedTDS3014B

    MODEL_NAME = "TDS3014B"
    EVENT_SOURCE = "SCOPE"

    def __init__(
        self,
        transport: Transport,
        limits: ModelLimits = TDS3014B_LIMITS,
        auto_check_errors: bool = True,
        owns_transport: bool = True,
    ) -> None:
        super().__init__(
            transport,
            auto_check_errors=auto_check_errors,
            owns_transport=owns_transport,
        )
        self._limits = limits

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _post_open(self) -> None:
        """Put the instrument's response formatting into a known state.

        Turns off command headers and verbose mode so queries return bare
        values, then clears the status and event queues via the base class.
        Deliberately does **not** reset the front-panel setup; call
        :meth:`reset` for that.
        """
        self._write("HEADER OFF;:VERBOSE OFF")
        super()._post_open()

    @property
    def limits(self) -> ModelLimits:
        """The capability envelope used for validation."""
        return self._limits

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def read_event_queue(self) -> List[Tuple[int, str]]:
        """Drain the instrument's event queue using ``ALLEv?``.

        Tektronix instruments return every pending event in one response,
        rather than requiring ``SYSTem:ERRor?`` to be polled until empty, so the
        SCPI-standard implementation in the base class is replaced here.

        :returns: ``(code, description)`` pairs; empty when nothing was
            reported. Reading the queue clears it, as on the instrument.
        """
        response = self._query("ALLEV?")
        events: List[Tuple[int, str]] = []
        for entry in response.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            code_text, _, description = entry.partition(",")
            try:
                code = int(code_text)
            except ValueError:
                continue
            if code == 0:
                continue
            events.append((code, description.strip().strip('"')))
        return events

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_channel(self, channel: int) -> int:
        return validate_channel(channel, self._limits.channels, self._limits.model)

    def _validate_channels(self, channels: Optional[Iterable[int]]) -> List[int]:
        if channels is None:
            return list(self._limits.channels)
        return validate_channels(channels, self._limits.channels, self._limits.model)

    @staticmethod
    def _validate_range(name: str, value: float, bounds, unit: str = "") -> float:
        return validate_range(name, value, bounds, unit)


    # ------------------------------------------------------------------
    # Vertical (channel) control
    # ------------------------------------------------------------------
    def enable_channel(self, channel: int, enabled: bool = True) -> None:
        """Show or hide a channel.

        A hidden channel is not digitised, so it cannot be captured or
        measured; enabling is therefore a prerequisite for both.
        """
        number = self._validate_channel(channel)
        self._write("SELECT:CH%d %s" % (number, "ON" if enabled else "OFF"))

    def is_channel_enabled(self, channel: int) -> bool:
        """Return ``True`` when *channel* is displayed."""
        number = self._validate_channel(channel)
        return self._query_int("SELECT:CH%d?" % number) == 1

    def enabled_channels(self) -> List[int]:
        """Return the channels currently displayed, in ascending order."""
        return [c for c in self._limits.channels if self.is_channel_enabled(c)]

    def configure_channel(
        self,
        channel: int,
        enabled: bool = True,
        volts_per_div: Optional[float] = None,
        position_div: Optional[float] = None,
        offset_v: Optional[float] = None,
        coupling: Optional[Union[Coupling, str]] = None,
        bandwidth: Optional[Union[Bandwidth, str]] = None,
    ) -> None:
        """Apply a complete vertical setup to one channel in a single message.

        Every setting is validated against the model's capability envelope
        before anything is sent, so an out-of-range request fails cleanly
        rather than leaving the channel half-configured.

        :param channel: Input number, 1 to 4.
        :param enabled: Display the channel.
        :param volts_per_div: Vertical sensitivity, 1 mV/div to 10 V/div.
        :param position_div: Screen position in divisions, -5 to +5.
        :param offset_v: Input offset in volts.
        :param coupling: ``AC``, ``DC`` or ``GND``.
        :param bandwidth: ``TWENTY``, ``ONEFIFTY`` or ``FULL``.
        :raises ConfigurationError: if any value is outside the envelope.
        """
        number = self._validate_channel(channel)
        parts = ["SELECT:CH%d %s" % (number, "ON" if enabled else "OFF")]

        if volts_per_div is not None:
            value = self._validate_range(
                "volts/div", volts_per_div, self._limits.volts_per_div_range, " V/div"
            )
            parts.append("CH%d:SCALE %.6E" % (number, value))

        if position_div is not None:
            value = self._validate_range(
                "vertical position", position_div, self._limits.position_div_range, " div"
            )
            parts.append("CH%d:POSITION %.6E" % (number, value))

        if offset_v is not None:
            value = self._validate_range(
                "vertical offset", offset_v, self._limits.offset_volts_range, " V"
            )
            parts.append("CH%d:OFFSET %.6E" % (number, value))

        if coupling is not None:
            parts.append("CH%d:COUPLING %s" % (number, Coupling.coerce(coupling).value))

        if bandwidth is not None:
            limit = Bandwidth.coerce(bandwidth)
            if limit not in self._limits.bandwidth_options:
                raise ConfigurationError(
                    "bandwidth limit %s is not available on the %s; supported: %s"
                    % (limit.value, self._limits.model,
                       ", ".join(option.value for option in self._limits.bandwidth_options))
                )
            parts.append("CH%d:BANDWIDTH %s" % (number, limit.value))

        self._write(";:".join(parts))
        self._after_configuration()

    def apply_setup(self, setups: Sequence[ChannelSetup]) -> None:
        """Apply several :class:`ChannelSetup` objects in order.

        Convenience for configuring all four inputs from a test definition.
        """
        for setup in setups:
            self.configure_channel(
                setup.channel,
                enabled=setup.enabled,
                volts_per_div=setup.volts_per_div,
                position_div=setup.position_div,
                offset_v=setup.offset_v,
                coupling=setup.coupling,
                bandwidth=setup.bandwidth,
            )

    def get_channel_setup(self, channel: int) -> ChannelSetup:
        """Read back the current vertical setup of *channel*."""
        number = self._validate_channel(channel)
        response = self._query(
            "SELECT:CH{0}?;:CH{0}:SCALE?;:CH{0}:POSITION?;:CH{0}:OFFSET?;"
            ":CH{0}:COUPLING?;:CH{0}:BANDWIDTH?".format(number)
        )
        fields = [field.strip() for field in response.split(";")]
        if len(fields) < 6:
            raise ProtocolError(
                "expected 6 fields from the channel %d setup query, got %r" % (number, response)
            )
        return ChannelSetup(
            channel=number,
            enabled=fields[0] in ("1", "ON"),
            volts_per_div=float(fields[1]),
            position_div=float(fields[2]),
            offset_v=float(fields[3]),
            coupling=Coupling.coerce(fields[4]),
            bandwidth=Bandwidth.coerce(fields[5]),
        )

    def set_volts_per_div(self, channel: int, volts_per_div: float) -> None:
        """Set the vertical sensitivity of *channel* in volts per division."""
        number = self._validate_channel(channel)
        value = self._validate_range(
            "volts/div", volts_per_div, self._limits.volts_per_div_range, " V/div"
        )
        self._write("CH%d:SCALE %.6E" % (number, value))

    def get_volts_per_div(self, channel: int) -> float:
        """Return the vertical sensitivity of *channel* in volts per division."""
        return self._query_float("CH%d:SCALE?" % self._validate_channel(channel))

    def set_position(self, channel: int, position_div: float) -> None:
        """Set the screen position of *channel* in divisions from centre."""
        number = self._validate_channel(channel)
        value = self._validate_range(
            "vertical position", position_div, self._limits.position_div_range, " div"
        )
        self._write("CH%d:POSITION %.6E" % (number, value))

    def get_position(self, channel: int) -> float:
        """Return the screen position of *channel* in divisions."""
        return self._query_float("CH%d:POSITION?" % self._validate_channel(channel))

    # ------------------------------------------------------------------
    # Horizontal control
    # ------------------------------------------------------------------
    def set_time_per_div(self, seconds_per_div: float) -> None:
        """Set the main time base in seconds per division."""
        value = self._validate_range(
            "time/div", seconds_per_div, self._limits.seconds_per_div_range, " s/div"
        )
        self._write("HORIZONTAL:MAIN:SCALE %.6E" % value)
        self._after_configuration()

    def get_time_per_div(self) -> float:
        """Return the main time base in seconds per division."""
        return self._query_float("HORIZONTAL:MAIN:SCALE?")

    def set_horizontal_delay(self, seconds: float) -> None:
        """Set the delay between the trigger and the record's reference point."""
        self._write("HORIZONTAL:DELAY:TIME %.6E" % float(seconds))

    def set_record_length(self, points: int) -> None:
        """Set the acquisition record length in points."""
        value = int(points)
        if value not in self._limits.record_lengths:
            raise ConfigurationError(
                "record length %d is not supported by the %s; valid lengths are %s"
                % (value, self._limits.model,
                   ", ".join(str(n) for n in self._limits.record_lengths))
            )
        self._write("HORIZONTAL:RECORDLENGTH %d" % value)
        self._after_configuration()

    def get_record_length(self) -> int:
        """Return the acquisition record length in points."""
        return self._query_int("HORIZONTAL:RECORDLENGTH?")

    # ------------------------------------------------------------------
    # Trigger control
    # ------------------------------------------------------------------
    def configure_edge_trigger(
        self,
        source: Union[int, str, TriggerSource] = 1,
        level: float = 0.0,
        slope: Union[Slope, str] = Slope.RISE,
        coupling: Union[Coupling, str] = Coupling.DC,
        mode: Union[TriggerMode, str] = TriggerMode.NORMAL,
    ) -> None:
        """Set up an A-event edge trigger in one message.

        ``NORMAL`` mode is the default because a repeatable capture should wait
        for a real trigger rather than free-run; use ``AUTO`` when you want the
        scope to sweep regardless, for example while setting up.

        :param source: Channel number, or a :class:`~tek3014b.constants.TriggerSource`.
        :param level: Trigger level in volts.
        :param slope: ``RISE`` or ``FALL``.
        :param coupling: Trigger coupling.
        :param mode: ``AUTO`` or ``NORMAL``.
        """
        if isinstance(source, int):
            trigger_source = TriggerSource.from_channel(self._validate_channel(source))
        else:
            trigger_source = TriggerSource.coerce(source)
        level_value = self._validate_range(
            "trigger level", level, self._limits.trigger_level_range, " V"
        )
        self._write(
            "TRIGGER:A:TYPE EDGE"
            ";:TRIGGER:A:EDGE:SOURCE %s"
            ";:TRIGGER:A:EDGE:SLOPE %s"
            ";:TRIGGER:A:EDGE:COUPLING %s"
            ";:TRIGGER:A:LEVEL %.6E"
            ";:TRIGGER:A:MODE %s"
            % (
                trigger_source.value,
                Slope.coerce(slope).value,
                Coupling.coerce(coupling).value,
                level_value,
                TriggerMode.coerce(mode).value,
            )
        )
        self._after_configuration()

    def set_trigger_level(self, level: float) -> None:
        """Set the A-event trigger level in volts."""
        value = self._validate_range(
            "trigger level", level, self._limits.trigger_level_range, " V"
        )
        self._write("TRIGGER:A:LEVEL %.6E" % value)

    def get_trigger_level(self) -> float:
        """Return the A-event trigger level in volts."""
        return self._query_float("TRIGGER:A:LEVEL?")

    def trigger_state(self) -> TriggerState:
        """Return the instrument's current trigger state."""
        return TriggerState.coerce(self._query("TRIGGER:STATE?"))

    def force_trigger(self) -> None:
        """Force an immediate trigger, whether or not the condition is met."""
        self._write("TRIGGER FORCE")

    # ------------------------------------------------------------------
    # Acquisition control
    # ------------------------------------------------------------------
    def set_acquisition_mode(
        self,
        mode: Union[AcquisitionMode, str] = AcquisitionMode.SAMPLE,
        average_count: Optional[int] = None,
    ) -> None:
        """Select the acquisition mode and, for averaging, the count."""
        chosen = AcquisitionMode.coerce(mode)
        parts = ["ACQUIRE:MODE %s" % chosen.value]
        if average_count is not None:
            count = int(average_count)
            if count not in self._limits.average_counts:
                raise ConfigurationError(
                    "average count %d is not supported; valid counts are %s"
                    % (count, ", ".join(str(n) for n in self._limits.average_counts))
                )
            parts.append("ACQUIRE:NUMAVG %d" % count)
        self._write(";:".join(parts))
        self._after_configuration()

    def run(self, continuous: bool = True) -> None:
        """Start acquiring.

        :param continuous: Free-run (``RUNSTop``); ``False`` acquires a single
            sequence and stops.
        """
        stop_after = StopAfter.RUN_STOP if continuous else StopAfter.SEQUENCE
        self._write("ACQUIRE:STOPAFTER %s;:ACQUIRE:STATE RUN" % stop_after.value)

    def stop(self) -> None:
        """Stop acquiring."""
        self._write("ACQUIRE:STATE STOP")

    def is_busy(self) -> bool:
        """Return ``True`` while the instrument is acquiring."""
        return self._query_int("BUSY?") == 1

    def wait_for_acquisition(self, timeout: float = 10.0, poll_interval: float = 0.02) -> None:
        """Block until the current acquisition completes.

        :param timeout: Maximum time to wait, in seconds.
        :param poll_interval: Seconds between ``BUSY?`` polls. The instrument
            is polled rather than using ``*OPC?`` because on this family
            ``*OPC?`` returns as soon as the command is parsed, not when the
            acquisition finishes.
        :raises AcquisitionTimeoutError: if the acquisition does not complete,
            which in ``NORMAL`` trigger mode usually means no trigger occurred.
        """
        if timeout <= 0.0:
            raise ValueError("timeout must be positive, got %r" % (timeout,))
        deadline = time.monotonic() + timeout
        while True:
            if not self.is_busy():
                return
            if time.monotonic() >= deadline:
                raise AcquisitionTimeoutError(
                    "acquisition did not complete within %.3f s; in NORMAL trigger "
                    "mode this usually means the trigger condition never occurred "
                    "(trigger state: %s)" % (timeout, self._safe_trigger_state())
                )
            time.sleep(poll_interval)

    def _safe_trigger_state(self) -> str:
        try:
            return self.trigger_state().value
        except Exception:  # pragma: no cover - diagnostic path only
            return "unknown"

    def single(self, timeout: float = 10.0, poll_interval: float = 0.02) -> None:
        """Arm a single-sequence acquisition and wait for it to complete."""
        self._write("ACQUIRE:STOPAFTER SEQUENCE;:ACQUIRE:STATE RUN")
        self.wait_for_acquisition(timeout=timeout, poll_interval=poll_interval)

    # ------------------------------------------------------------------
    # Waveform capture
    # ------------------------------------------------------------------
    def _read_preamble(self, source: str, start_index: int) -> WaveformPreamble:
        query = ";:".join("WFMPRE:%s?" % field for field in _PREAMBLE_FIELDS)
        response = self._query(query)
        fields = [field.strip() for field in response.split(";")]
        if len(fields) != len(_PREAMBLE_FIELDS):
            raise ProtocolError(
                "expected %d preamble fields, got %d: %r"
                % (len(_PREAMBLE_FIELDS), len(fields), response)
            )
        try:
            values = [float(field) for field in fields]
        except ValueError as exc:
            raise ProtocolError("unparsable waveform preamble %r" % response) from exc

        return WaveformPreamble(
            x_increment=values[0],
            x_zero=values[1],
            point_offset=values[2],
            y_multiplier=values[3],
            y_zero=values[4],
            y_offset=values[5],
            point_count=int(values[6]),
            start_index=start_index,
        )

    def _read_curve_payload(self) -> bytes:
        """Read a ``CURVe?`` response and return its payload, header removed.

        The declared block length is read explicitly rather than reading until
        end-of-message, which keeps the transfer correct on transports with no
        end-of-message indication, such as a raw socket.

        The returned bytes are the payload only. They must **not** be passed
        through the block parser again: binary sample data can contain the
        ``#`` byte and would be misread as a second block header.
        """
        self._write("CURVE?")
        first = self._transport.read_exactly(1)
        if first != b"#":
            # Not a block: fall back to reading the whole message (ASCII
            # encoding, or an error string).
            remainder = self._transport.read_message(strip_terminator=True)
            return first + remainder
        digits_field = self._transport.read_exactly(1)
        if not digits_field.isdigit():
            raise ProtocolError("malformed curve block header #%r" % digits_field)
        digits = int(digits_field)
        if digits == 0:
            return parse_ieee_block(b"#0" + self._transport.read_raw())
        length_field = self._transport.read_exactly(digits)
        if not length_field.isdigit():
            raise ProtocolError("malformed curve block length %r" % length_field)
        return self._transport.read_exactly(int(length_field))

    def capture(
        self,
        channels: Optional[Iterable[int]] = None,
        encoding: Union[DataEncoding, str] = DataEncoding.RIBINARY,
        width: int = 1,
        start: int = 1,
        stop: Optional[int] = None,
    ) -> Dict[int, Waveform]:
        """Transfer the current acquisition from one or more channels.

        The instrument is *not* re-armed: this reads whatever is in acquisition
        memory. Use :meth:`capture_single` to trigger and then read, which is
        what you want when comparing timing between channels.

        :param channels: Channels to read; defaults to those currently displayed.
        :param encoding: Transfer encoding. Binary is roughly five times more
            compact than ASCII on the wire.
        :param width: Bytes per point, 1 (8-bit, the digitiser's native
            resolution) or 2 (16-bit, meaningful only in average mode).
        :param start: First record point, 1-based.
        :param stop: Last record point; defaults to the full record.
        :returns: Mapping of channel number to :class:`~tek3014b.waveform.Waveform`.
        :raises ConfigurationError: for an invalid channel, width or range.
        """
        chosen = DataEncoding.coerce(encoding)
        if width not in (1, 2):
            raise ConfigurationError("data width must be 1 or 2 bytes, got %r" % (width,))
        if start < 1:
            raise ConfigurationError("start must be at least 1, got %r" % (start,))

        if channels is None:
            requested = self.enabled_channels()
            if not requested:
                raise ConfigurationError(
                    "no channel is displayed, so there is nothing to capture; "
                    "enable at least one channel first"
                )
        else:
            requested = self._validate_channels(channels)

        last = int(stop) if stop is not None else self.get_record_length()
        if last < start:
            raise ConfigurationError("stop (%d) must not be less than start (%d)" % (last, start))

        self._write(
            "DATA:ENCDG %s;:DATA:WIDTH %d;:DATA:START %d;:DATA:STOP %d"
            % (chosen.value, width, start, last)
        )

        signed = chosen in _SIGNED_ENCODINGS
        results: Dict[int, Waveform] = {}
        for channel in requested:
            source = "CH%d" % channel
            self._write("DATA:SOURCE %s" % source)
            preamble = self._read_preamble(source, start_index=start - 1)
            payload = self._read_curve_payload()
            if chosen is DataEncoding.ASCII:
                results[channel] = Waveform.from_ascii(
                    source=source, text=payload, preamble=preamble
                )
            else:
                results[channel] = Waveform.from_payload(
                    source=source, payload=payload, preamble=preamble,
                    width=width, signed=signed,
                )
            record = results[channel]
            if record.is_clipped:
                self._logger.warning(
                    "%s is clipped: %d of %d samples are at the digitiser rail. "
                    "Increase volts/div or move the channel position, otherwise "
                    "amplitude and threshold-based timing results will be wrong.",
                    source, record.clipped_sample_count, len(record),
                )
            self._logger.debug("captured %d points from %s", len(record), source)

        if self.auto_check_errors:
            self.check_errors()
        return results

    def capture_single(
        self,
        channels: Optional[Iterable[int]] = None,
        timeout: float = 10.0,
        **capture_kwargs,
    ) -> Dict[int, Waveform]:
        """Arm one acquisition, wait for the trigger, then transfer the record.

        All requested channels come from the *same* acquisition, so their
        relative timing is directly comparable - which is what makes a
        cross-channel skew measurement valid.
        """
        self.single(timeout=timeout)
        return self.capture(channels=channels, **capture_kwargs)

    # ------------------------------------------------------------------
    # Instrument-side measurements
    # ------------------------------------------------------------------
    def measure(
        self,
        measurement: Union[MeasurementType, str],
        source1: Union[int, str] = 1,
        source2: Optional[Union[int, str]] = None,
        edge1: Union[EdgeDirection, str] = EdgeDirection.RISE,
        edge2: Union[EdgeDirection, str] = EdgeDirection.RISE,
        direction: Union[DelayDirection, str] = DelayDirection.FORWARDS,
        settle: float = 0.0,
    ) -> float:
        """Take one immediate measurement using the instrument's own engine.

        :param measurement: Measurement type.
        :param source1: Primary source channel number or name.
        :param source2: Secondary source, required for ``DELAY`` and ``PHASE``.
        :param edge1: Edge of *source1* used by a delay measurement.
        :param edge2: Edge of *source2* used by a delay measurement.
        :param direction: Search direction for a delay measurement.
        :param settle: Seconds to wait after configuring before reading, to let
            the instrument's measurement engine refresh.
        :returns: The measured value, in the units given by :meth:`measure_units`.
        :raises MeasurementError: if the instrument reports its invalid-data
            sentinel, which means it could not compute the value - typically an
            undisplayed channel or no complete cycle on screen.
        """
        kind = MeasurementType.coerce(measurement)
        parts = [
            "MEASUREMENT:IMMED:TYPE %s" % kind.value,
            "MEASUREMENT:IMMED:SOURCE1 %s" % self._source_name(source1),
        ]
        if source2 is not None:
            parts.append("MEASUREMENT:IMMED:SOURCE2 %s" % self._source_name(source2))
        if kind is MeasurementType.DELAY:
            if source2 is None:
                raise ConfigurationError("a DELAY measurement needs source2")
            parts.append("MEASUREMENT:IMMED:DELAY:EDGE1 %s" % EdgeDirection.coerce(edge1).value)
            parts.append("MEASUREMENT:IMMED:DELAY:EDGE2 %s" % EdgeDirection.coerce(edge2).value)
            parts.append(
                "MEASUREMENT:IMMED:DELAY:DIRECTION %s" % DelayDirection.coerce(direction).value
            )
        self._write(";:".join(parts))
        if settle > 0.0:
            time.sleep(settle)

        value = self._query_float("MEASUREMENT:IMMED:VALUE?")
        if abs(value) >= INVALID_MEASUREMENT * 0.99:
            raise MeasurementError(
                "the instrument could not compute %s on %s; check that the "
                "channel is displayed and that a complete cycle is on screen"
                % (kind.value, self._source_name(source1))
            )
        return value

    def measure_units(self) -> str:
        """Return the units of the most recently configured immediate measurement."""
        return self._query("MEASUREMENT:IMMED:UNITS?").strip().strip('"')

    def _source_name(self, source: Union[int, str]) -> str:
        if isinstance(source, int):
            return "CH%d" % self._validate_channel(source)
        return str(source).upper()

    def measure_period(self, channel: int = 1, **kwargs) -> float:
        """Return the period of *channel* in seconds, measured by the instrument."""
        return self.measure(MeasurementType.PERIOD, source1=channel, **kwargs)

    def measure_frequency(self, channel: int = 1, **kwargs) -> float:
        """Return the frequency of *channel* in hertz, measured by the instrument."""
        return self.measure(MeasurementType.FREQUENCY, source1=channel, **kwargs)

    def measure_amplitude(self, channel: int = 1, **kwargs) -> float:
        """Return the amplitude of *channel* in volts, measured by the instrument."""
        return self.measure(MeasurementType.AMPLITUDE, source1=channel, **kwargs)

    def measure_rise_time(self, channel: int = 1, **kwargs) -> float:
        """Return the 10-90% rise time of *channel* in seconds."""
        return self.measure(MeasurementType.RISE, source1=channel, **kwargs)

    def measure_delay(
        self,
        from_channel: int,
        to_channel: int,
        from_edge: Union[EdgeDirection, str] = EdgeDirection.RISE,
        to_edge: Union[EdgeDirection, str] = EdgeDirection.RISE,
        direction: Union[DelayDirection, str] = DelayDirection.FORWARDS,
        **kwargs,
    ) -> float:
        """Return the delay from *from_channel* to *to_channel*, in seconds.

        The instrument's delay measurement takes exactly two sources. For the
        timing spread across three or four channels use
        :meth:`measure_channel_spread`, which works from one simultaneous
        capture instead.
        """
        return self.measure(
            MeasurementType.DELAY,
            source1=from_channel,
            source2=to_channel,
            edge1=from_edge,
            edge2=to_edge,
            direction=direction,
            **kwargs,
        )

    def measure_summary(self, channel: int = 1) -> Dict[str, float]:
        """Return a set of common measurements for *channel*.

        Measurements the instrument cannot compute are omitted rather than
        failing the whole summary.
        """
        wanted = (
            MeasurementType.FREQUENCY,
            MeasurementType.PERIOD,
            MeasurementType.AMPLITUDE,
            MeasurementType.PEAK_TO_PEAK,
            MeasurementType.MEAN,
            MeasurementType.RMS,
            MeasurementType.RISE,
            MeasurementType.FALL,
            MeasurementType.POSITIVE_WIDTH,
            MeasurementType.POSITIVE_DUTY,
        )
        summary: Dict[str, float] = {}
        for kind in wanted:
            try:
                summary[kind.value.lower()] = self.measure(kind, source1=channel)
            except (MeasurementError, ProtocolError):
                self._logger.debug("instrument could not measure %s on CH%d", kind.value, channel)
        return summary

    # ------------------------------------------------------------------
    # Host-side analysis built on a capture
    # ------------------------------------------------------------------
    def measure_channel_spread(
        self,
        channels: Sequence[int],
        direction: Union[EdgeDirection, str] = EdgeDirection.RISE,
        percent: float = 50.0,
        absolute_threshold: Optional[float] = None,
        edge_index: int = 0,
        reference: Optional[int] = None,
        timeout: float = 10.0,
        waveforms: Optional[Mapping[int, Waveform]] = None,
        **capture_kwargs,
    ) -> Tuple[Dict[int, Waveform], SpreadResult]:
        """Capture *channels* together and report how far apart they switch.

        This is the N-channel answer the instrument's own two-source delay
        measurement cannot give. Because one acquisition digitises every
        channel on a common time base, the reported spread is a genuine
        measurement of relative timing.

        :param channels: At least two channels, all of which must be displayed.
        :param direction: ``RISE`` for going high, ``FALL`` for going low.
        :param percent: Threshold as a percentage of each channel's own
            amplitude; 50% by default.
        :param absolute_threshold: Fixed threshold in volts for every channel,
            overriding *percent*. Use this when the channels must be compared
            against one logic threshold rather than their own mid-points.
        :param edge_index: Which edge after the trigger to use, 0 for the first.
        :param reference: Channel the skews are reported against; defaults to
            the earliest.
        :param waveforms: Analyse these previously captured records instead of
            taking a new acquisition.
        :returns: ``(waveforms, spread)``.
        """
        selected = self._validate_channels(channels)
        if len(selected) < 2:
            raise ConfigurationError(
                "a timing spread needs at least two channels, got %d" % len(selected)
            )
        records = (
            dict(waveforms)
            if waveforms is not None
            else self.capture_single(selected, timeout=timeout, **capture_kwargs)
        )
        spread = measure_channel_spread(
            records,
            direction=direction,
            percent=percent,
            absolute_threshold=absolute_threshold,
            edge_index=edge_index,
            reference=reference,
        )
        return records, spread

    def measure_period_host(self, channel: int = 1, timeout: float = 10.0, **kwargs):
        """Capture *channel* and measure every period in the record host-side.

        Unlike :meth:`measure_period`, this returns statistics over all the
        periods in the record - mean, min, max, standard deviation and
        peak-to-peak jitter - rather than a single value.
        """
        number = self._validate_channel(channel)
        records = self.capture_single([number], timeout=timeout)
        return records, analyse_period(records[number], **kwargs)

    # ------------------------------------------------------------------
    # Screen capture
    # ------------------------------------------------------------------
    def screenshot(
        self,
        path: str,
        image_format: Union[ImageFormat, str] = ImageFormat.PNG,
        palette: Union[HardcopyPalette, str] = HardcopyPalette.COLOR,
        layout: Union[HardcopyLayout, str] = HardcopyLayout.LANDSCAPE,
        timeout: Optional[float] = 30.0,
        verify_format: bool = True,
    ) -> str:
        """Capture the instrument's screen and write it to *path*.

        The hardcopy port is switched to the command interface so the image is
        streamed back over this link rather than to a printer or a floppy.

        Screen capture can take several seconds, so the transport timeout is
        raised for the duration and restored afterwards.

        :param path: Destination file. If it has no suffix, one matching the
            format is appended.
        :param image_format: Image format; PNG by default.
        :param palette: ``COLOR``, ``INKSAVER`` or ``BLACKANDWHITE``.
        :param layout: Page orientation.
        :param timeout: I/O timeout for the transfer, in seconds.
        :param verify_format: Read the format back and fall back to
            ``BMPCOLOR`` if the instrument did not accept the request. Older
            firmware does not offer every format.
        :returns: The path written.
        """
        chosen = ImageFormat.coerce(image_format)
        self._write(
            "HARDCOPY:PORT GPIB;:HARDCOPY:FORMAT %s;:HARDCOPY:PALETTE %s;:HARDCOPY:LAYOUT %s"
            % (
                chosen.value,
                HardcopyPalette.coerce(palette).value,
                HardcopyLayout.coerce(layout).value,
            )
        )

        if verify_format:
            actual = self._query("HARDCOPY:FORMAT?").strip().upper()
            if actual != chosen.value.upper():
                self._logger.warning(
                    "instrument did not accept hardcopy format %s (reports %s); "
                    "falling back to BMPCOLOR",
                    chosen.value, actual or "nothing",
                )
                chosen = ImageFormat.BMP_COLOR
                self._write("HARDCOPY:FORMAT %s" % chosen.value)

        previous_timeout = self._transport.timeout
        if timeout is not None:
            self._transport.timeout = timeout
        try:
            self._write("HARDCOPY START")
            image = self._transport.read_raw()
        finally:
            self._transport.timeout = previous_timeout

        if not image:
            raise ProtocolError(
                "the instrument returned no hardcopy data; check that the "
                "hardcopy port is set to the command interface"
            )

        root, suffix = os.path.splitext(path)
        destination = path if suffix else root + chosen.suffix
        directory = os.path.dirname(os.path.abspath(destination))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(destination, "wb") as handle:
            handle.write(image)
        self._logger.info("wrote %d bytes of %s hardcopy to %s",
                          len(image), chosen.value, destination)
        return destination

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    @staticmethod
    def save_csv(waveforms: Mapping[int, Waveform], path: str) -> str:
        """Write captured channels to a single CSV with a shared time column."""
        return waveforms_to_csv(dict(waveforms), path)
