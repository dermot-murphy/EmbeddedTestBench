"""The Nordic BLE dongle as a bench instrument.

What it is for: making a sensor's radio behaviour assertable. Four things the
bench needs and cannot get from a phone app:

* **Scan and select.** Find the sensors in range, pick the one under test, and
  keep that choice for the rest of the suite.
* **Command and response over BLE UART.** Drive the sensor's console the way
  firmware does, and read what it answers.
* **Time until response.** Measured on the dongle's microsecond clock, with the
  connection interval reported beside it so the figure can be read correctly.
* **Advertising profile.** Every beacon timestamped at the radio, so intervals,
  gaps and duty cycle are about the sensor rather than about USB.

It is not a SCPI instrument, so it implements
:class:`~benchtools.core.instrument.Instrument` directly - the same seam the
J-Link probe uses.

Traces to: BLE-FR-001 .. BLE-FR-062, BLE-ARC-001, BLE-DD-DONGLE.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Union

from ...core.errors import (
    BenchToolsError,
    ConfigurationError,
    InstrumentError,
    MeasurementError,
)
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_SCAN_MS,
    DONGLE_LIMITS,
    PROTOCOL_VERSION,
    AddressType,
    DongleLimits,
    ScanFilter,
)
from .latency import LatencySource, ResponseSample, ResponseTiming
from .profile import AdvertisingEvent, AdvertisingProfile
from .protocol import (
    Event,
    address_type_of,
    encode_payload,
    format_address,
    from_hex,
    normalise_address,
)
from .session import DongleCommandError, DongleSession
from .simulator import SimulatedDongle

__all__ = ["NordicDongle", "Sensor"]

_LOG = logging.getLogger(__name__)


@dataclass
class Sensor:
    """One device seen while scanning.

    :param index: Position in the dongle's table, which is what ``select``
        takes.
    :param seen: Advertising reports from this address during the scan.
    """

    address: str
    name: str = ""
    address_type: AddressType = AddressType.RANDOM_STATIC
    rssi: int = 0
    index: int = 0
    seen: int = 0

    @property
    def qualified_address(self) -> str:
        """Address with its type, which is what connecting needs."""
        return format_address(self.address, int(self.address_type))

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "address": self.address,
            "address_type": int(self.address_type),
            "name": self.name,
            "rssi": self.rssi,
            "seen": self.seen,
        }

    def __str__(self) -> str:
        return "%d: %s %-12s %4d dBm" % (
            self.index, self.address, self.name or "(no name)", self.rssi
        )


class NordicDongle(Instrument):
    """A Nordic nRF52840 dongle running the BenchTools bench firmware.

    :param transport: An open transport to the dongle's serial port.
    :param timeout: Default seconds to wait for a reply.
    :param limits: The firmware's capability envelope.
    :param auto_check_errors: Unused here; the link reports every failure in
        its reply, so there is no error queue to poll.
    """

    SIMULATOR_CLASS = SimulatedDongle
    MODEL_NAME = "Nordic dongle"

    def __init__(
        self,
        transport: Transport,
        timeout: float = 5.0,
        limits: Optional[DongleLimits] = None,
        auto_check_errors: bool = True,
    ) -> None:
        super().__init__(auto_check_errors=auto_check_errors)
        self._transport = transport
        self._limits = limits if limits is not None else DONGLE_LIMITS
        self._session = DongleSession(transport, timeout=timeout)
        self._sensors: List[Sensor] = []
        self._selected: Optional[Sensor] = None
        self._connected = False
        self._connection_interval_us = 0
        self._firmware_protocol = ""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    @classmethod
    def connect(
        cls,
        resource: str = "sim://",
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 5.0,
        log_path: Optional[str] = None,
        limits: Optional[DongleLimits] = None,
        initialise: bool = True,
        **_ignored,
    ) -> "NordicDongle":
        """Open a dongle.

        :param resource: ``sim://`` for the simulator, or a serial port:
            ``COM5``, ``serial://COM5``, ``/dev/ttyACM0``,
            ``serial://socket://bench-pc:4001`` for a port published over TCP,
            which is how a container reaches a dongle on another machine.
        :param baudrate: Line rate. A USB CDC port ignores it.
        :param log_path: Start logging the session to this file immediately, so
            the connection dialogue is in the log too.
        :param initialise: Open the link and identify. False to construct
            without talking to it.
        """
        target = cls._normalise_resource(resource)
        transport = open_transport(
            target,
            timeout=timeout,
            open_now=False,
            responder_factory=cls.SIMULATOR_CLASS,
            **({"baudrate": baudrate} if target.startswith("serial://") else {}),
        )
        instrument = cls(transport, timeout=timeout, limits=limits)
        if log_path:
            instrument._session.log_to(log_path)
        if initialise:
            instrument.initialise()
        return instrument

    @staticmethod
    def _normalise_resource(resource: str) -> str:
        """Accept a bare port name as a serial port rather than a host name.

        Without this, ``COM5`` would be parsed as a network host, because that
        is the sensible default for instruments generally and exactly wrong for
        this one.
        """
        text = (resource or "").strip()
        if not text:
            return "sim://"
        lowered = text.lower()
        if "://" in text or lowered in ("sim", "mock"):
            return text
        return "serial://%s" % text

    @property
    def transport(self) -> Transport:
        """The link to the dongle."""
        return self._transport

    def _open(self) -> None:
        self.transport.open()
        self._session.start()

    def _close(self) -> None:
        try:
            if self._connected:
                self._session.execute("disconnect", allow_error=True, timeout=1.0)
        except BenchToolsError:                 # pragma: no cover - best effort
            _LOG.debug("could not disconnect cleanly", exc_info=True)
        self._session.close()
        self.transport.close()

    @property
    def is_open(self) -> bool:
        return self.transport.is_open

    def _post_open(self) -> None:
        """Identify the firmware and check it speaks a protocol we know."""
        identity = self._read_identity()
        self._identity = identity
        if self._firmware_protocol and self._firmware_protocol != PROTOCOL_VERSION:
            raise InstrumentError(
                "the dongle speaks protocol %s and this driver speaks %s. "
                "Rebuild and reflash firmware/nordic_dongle, or use a driver "
                "of the matching version."
                % (self._firmware_protocol, PROTOCOL_VERSION)
            )

    def _read_identity(self) -> InstrumentIdentity:
        reply = self._session.execute("ver")
        fields = reply.fields
        self._firmware_protocol = fields.get("proto", "")
        # "ok Nordic PCA10059 proto=1.0 uptime_us=... dropped=..." - the first
        # two tokens are positional, so they arrive as valueless keys.
        positional = [key for key, value in fields.items() if value == ""]
        manufacturer = positional[0] if positional else "Nordic"
        model = positional[1] if len(positional) > 1 else self._limits.model
        return InstrumentIdentity(
            raw=reply.raw[3:] if reply.raw.startswith("ok ") else reply.raw,
            manufacturer=manufacturer,
            model=model,
            serial_number="",
            firmware=self._firmware_protocol,
        )

    # ------------------------------------------------------------------
    @property
    def session(self) -> DongleSession:
        """The command session, for anything this driver does not wrap."""
        return self._session

    @property
    def limits(self) -> DongleLimits:
        """The firmware's capability envelope."""
        return self._limits

    @property
    def protocol_version(self) -> str:
        """The protocol version the dongle reported."""
        return self._firmware_protocol

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def start_log(self, path: str) -> str:
        """Log every line of the session to a text file.

        Both directions, host-timestamped, flushed per line. This is the record
        a measurement is defended with, so it includes the lines the driver
        ignored as well as the ones it acted on.
        """
        return self._session.log_to(path)

    def stop_log(self) -> None:
        """Stop logging. Idempotent."""
        self._session.stop_log()

    def log_note(self, text: str) -> None:
        """Write a comment into the log."""
        self._session.note(text)

    @property
    def log_path(self) -> Optional[str]:
        """Where the session is being logged, if it is."""
        return self._session.log_path

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def scan(
        self,
        duration: float = DEFAULT_SCAN_MS / 1000.0,
        name: Optional[str] = None,
        address: Optional[str] = None,
        active: bool = False,
        min_rssi: Optional[int] = None,
    ) -> List[Sensor]:
        """Scan for sensors and return what was found.

        :param duration: Seconds to scan.
        :param name: Keep only names containing this text.
        :param address: Keep only this address.
        :param active: Request scan responses. Needed when the name is only in
            the scan response, and it makes the dongle transmit.
        :param min_rssi: Reject anything weaker than this, in dBm.
        """
        if duration <= 0.0:
            raise ConfigurationError("scan duration must be positive, got %r" % (duration,))

        scan_filter = ScanFilter(
            name=name,
            address=normalise_address(address) if address else None,
            active=active,
            min_rssi=min_rssi,
        )
        milliseconds = int(duration * 1000.0)
        self._session.discard_events()
        self._session.execute("scan", "start", milliseconds, *scan_filter.as_arguments())
        try:
            # The scan ends when the *dongle* says it ended: the firmware stops
            # on its own timeout and reports it. Waiting for that rather than
            # for the host's clock keeps the window on the clock that the radio
            # is actually on - and lets a simulated scan complete as fast as it
            # can be read instead of sleeping for the duration.
            self._session.collect(
                duration + 1.0,
                stop=lambda event: event.name == "scan" and event.get("state") == "stopped",
            )
        finally:
            self._session.execute("scan", "stop", allow_error=True)

        return self.refresh_sensors()

    def refresh_sensors(self) -> List[Sensor]:
        """Re-read the dongle's sensor table."""
        self._session.take_events("sensor")     # discard any stale entries
        self._session.execute("list")
        found = [self._sensor_from_event(event) for event in self._session.take_events("sensor")]
        self._sensors = sorted(found, key=lambda sensor: sensor.index)
        return list(self._sensors)

    @staticmethod
    def _sensor_from_event(event: Event) -> Sensor:
        return Sensor(
            index=event.integer("idx"),
            address=event.get("addr"),
            address_type=AddressType.coerce(event.integer("type", 1)),
            rssi=event.integer("rssi"),
            seen=event.integer("seen"),
            name=event.get("name"),
        )

    @property
    def sensors(self) -> List[Sensor]:
        """Sensors from the last scan."""
        return list(self._sensors)

    def find_sensor(self, text: str) -> Optional[Sensor]:
        """A sensor from the last scan, by address or by name."""
        for sensor in self._sensors:
            if sensor.name == text:
                return sensor
        try:
            wanted = normalise_address(text)
        except BenchToolsError:
            return None
        for sensor in self._sensors:
            if sensor.address.upper() == wanted:
                return sensor
        return None

    def select(self, sensor: Union[int, str, Sensor]) -> Sensor:
        """Choose the sensor later commands apply to.

        :param sensor: A :class:`Sensor`, its index in the last scan, its
            address, or its advertised name.
        """
        if isinstance(sensor, Sensor):
            target: Union[int, str] = sensor.qualified_address
        elif isinstance(sensor, int):
            target = sensor
        else:
            known = self.find_sensor(sensor)
            if known is not None:
                target = known.qualified_address
            else:
                # Not in the table: an address is still usable, a name is not,
                # because only the scan can turn a name into an address.
                target = format_address(normalise_address(sensor), None)

        reply = self._session.execute("select", target)
        chosen = Sensor(
            address=reply.fields.get("addr", ""),
            address_type=AddressType.coerce(reply.fields.get("type", 1)),
            name=reply.fields.get("name", ""),
            index=sensor if isinstance(sensor, int) else 0,
        )
        known = self.find_sensor(chosen.address) if chosen.address else None
        if known is not None:
            chosen.rssi = known.rssi
            chosen.seen = known.seen
            chosen.index = known.index
        self._selected = chosen
        return chosen

    @property
    def selected(self) -> Optional[Sensor]:
        """The sensor chosen by :meth:`select`."""
        return self._selected

    def _require_selected(self) -> Sensor:
        if self._selected is None:
            raise ConfigurationError(
                "no sensor is selected. Call scan() then select(...) first, or "
                "select an address directly."
            )
        return self._selected

    # ------------------------------------------------------------------
    # Connection to the sensor
    # ------------------------------------------------------------------
    def open_link(self, timeout: float = 10.0) -> Sensor:
        """Connect to the selected sensor and wait for its UART service.

        :raises InstrumentError: if the sensor does not become ready in time.
        """
        sensor = self._require_selected()
        self._session.execute("connect")
        try:
            ready = self._session.wait_for_event(
                "conn",
                timeout=timeout,
                match=lambda event: event.get("state") == "ready",
            )
        except BenchToolsError as exc:
            raise InstrumentError(
                "connected to %s but its UART service did not become ready "
                "within %.1f s. Check the sensor advertises Nordic's UART "
                "service and is not already connected to something else."
                % (sensor.address, timeout)
            ) from exc
        self._connected = True
        # The connection interval comes from the event, not from a later query:
        # it is the floor under every latency measured on this link, and a
        # latency reported without it cannot be read correctly.
        self._connection_interval_us = ready.integer("interval_us", 0)
        if self._connection_interval_us == 0:
            for earlier in self._session.take_events("conn"):
                self._connection_interval_us = earlier.integer("interval_us", 0)
                if self._connection_interval_us:
                    break
        return sensor

    def close_link(self) -> None:
        """Disconnect from the sensor. Idempotent."""
        reply = self._session.execute("disconnect", allow_error=True)
        self._connected = False
        self._connection_interval_us = 0
        if not reply.ok and reply.error is not None and reply.error.name != "NOT_CONNECTED":
            raise DongleCommandError("disconnect", reply.error, reply.text)

    @property
    def is_linked(self) -> bool:
        """True while connected to a sensor."""
        return self._connected

    @property
    def connection_interval_us(self) -> int:
        """The connection interval, which bounds every latency measured."""
        return self._connection_interval_us

    # ------------------------------------------------------------------
    # UART over BLE
    # ------------------------------------------------------------------
    def write(self, payload: Union[str, bytes]) -> int:
        """Send bytes to the sensor without waiting for a reply.

        :returns: Bytes written.
        """
        encoded = self._encode(payload)
        reply = self._session.execute("uart", encoded)
        return int(reply.fields.get("len", 0))

    def command(
        self,
        request: Union[str, bytes],
        timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ) -> ResponseSample:
        """Send a command and wait for the sensor's reply, timing both.

        The dongle times the radio exchange on its microsecond clock; this
        method also records the host's own round trip, which includes USB. The
        two are kept separately because quoting the second as the first would
        report a millisecond of host scheduling as sensor latency.

        :raises InstrumentError: if the sensor does not reply.
        """
        encoded = self._encode(request)
        started = time.perf_counter()
        reply = self._session.execute("cmd", encoded, timeout=timeout + 1.0)
        elapsed = time.perf_counter() - started

        self._session.take_events("rx")         # the reply is in the ok line
        interval = reply.fields.get("interval_us")
        if interval:
            self._connection_interval_us = int(interval)

        return ResponseSample(
            request=request if isinstance(request, str) else from_hex(encoded).hex(),
            response=from_hex(reply.fields.get("data", "")),
            dongle_us=int(reply.fields["dt_us"]) if "dt_us" in reply.fields else None,
            host_s=elapsed,
            transmitted_us=int(reply.fields["t_tx"]) if "t_tx" in reply.fields else None,
            received_us=int(reply.fields["t_rx"]) if "t_rx" in reply.fields else None,
        )

    def measure_response_time(
        self,
        request: Union[str, bytes],
        repeat: int = 1,
        timeout: float = DEFAULT_COMMAND_TIMEOUT,
        source: Union[LatencySource, str] = LatencySource.DONGLE,
    ) -> ResponseTiming:
        """Time a command, repeated, and return the statistics.

        :param repeat: Exchanges to perform. More than one is usually right: a
            single figure cannot show the spread that a connection interval
            imposes.
        :param source: Which clock to take the statistics from.
        """
        if repeat < 1:
            raise ConfigurationError("repeat must be at least 1, got %r" % (repeat,))
        chosen = source if isinstance(source, LatencySource) else LatencySource(str(source).upper())

        samples = [self.command(request, timeout=timeout) for _ in range(int(repeat))]
        return ResponseTiming(
            samples=samples,
            source=chosen,
            connection_interval_us=self._connection_interval_us,
            request=request if isinstance(request, str) else repr(request),
        )

    def _encode(self, payload: Union[str, bytes]) -> str:
        encoded = encode_payload(payload)
        if len(encoded) > self._limits.max_hex_payload:
            raise ConfigurationError(
                "payload is %d bytes; the firmware accepts at most %d "
                "(PROTO_MAX_PAYLOAD). Split it, or raise the limit in the "
                "firmware and reflash."
                % (len(encoded) // 2, self._limits.max_payload_bytes)
            )
        return encoded

    # ------------------------------------------------------------------
    # Advertising profile
    # ------------------------------------------------------------------
    def measure_advertising_profile(
        self,
        duration: float = 10.0,
        address: Optional[str] = None,
        expected_interval: Optional[float] = None,
        on_event: Optional[Callable[[AdvertisingEvent], None]] = None,
    ) -> AdvertisingProfile:
        """Capture advertising events and derive the profile.

        The capture window is measured on the *dongle's* clock, which is the
        same clock the intervals are measured on. The host's wall clock bounds
        it as well, so a sensor that goes silent still ends the capture.

        :param duration: Seconds of advertising to capture.
        :param address: Address to profile; the selected sensor by default.
        :param expected_interval: The sensor's nominal interval in seconds,
            when the specification names one. Given rather than inferred, the
            missed-event arithmetic is against the specification instead of
            against the sensor's own behaviour.
        :param on_event: Called for each advertising event as it arrives.
        """
        if duration <= 0.0:
            raise ConfigurationError("duration must be positive, got %r" % (duration,))

        target = address or self._require_selected().qualified_address
        plain = normalise_address(target)

        self._session.discard_events()
        self._session.execute("scan", "start", int(duration * 1000.0) + 1000, "addr=%s" % plain)
        self._session.execute("adv", "start", target)
        try:
            events = self._capture(duration, on_event)
        finally:
            self._session.execute("adv", "stop", allow_error=True)
            self._session.execute("scan", "stop", allow_error=True)

        statistics_reply = self._session.execute("adv", "stats", allow_error=True)
        radio_events = None
        dropped = 0
        if statistics_reply.ok:
            radio_events = int(statistics_reply.fields.get("received", 0))
            dropped = int(statistics_reply.fields.get("dropped", 0))

        span = 0.0
        if len(events) > 1:
            span = events[-1].timestamp_s - events[0].timestamp_s

        return AdvertisingProfile(
            events=events,
            address=plain,
            duration_s=span if span > 0.0 else duration,
            expected_interval_s=expected_interval,
            radio_events=radio_events,
            dongle_dropped=max(dropped, self._session.dropped_notices),
        )

    def _capture(
        self,
        duration: float,
        on_event: Optional[Callable[[AdvertisingEvent], None]],
    ) -> List[AdvertisingEvent]:
        """Collect advertising events until *duration* has passed on the dongle."""
        collected: List[AdvertisingEvent] = []
        first_us: Optional[int] = None
        wall_deadline = time.monotonic() + duration

        def keep(event: Event) -> bool:
            """Record an advertising event; true once the window is covered."""
            nonlocal first_us
            if event.name != "adv":
                return False
            advertising = self._advertising_from_event(event)
            if first_us is None:
                first_us = advertising.timestamp_us
            collected.append(advertising)
            if on_event is not None:
                on_event(advertising)
            return ((advertising.timestamp_us - first_us) / 1.0e6) >= duration

        while time.monotonic() < wall_deadline:
            remaining = max(wall_deadline - time.monotonic(), 0.01)
            before = len(collected)
            self._session.collect(min(0.25, remaining), stop=keep)
            if collected and first_us is not None:
                span = (collected[-1].timestamp_us - first_us) / 1.0e6
                if span >= duration:
                    break
            if len(collected) == before and not self._session.pending_events:
                continue

        for event in self._session.take_events("adv"):
            keep(event)
        return collected

    @staticmethod
    def _advertising_from_event(event: Event) -> AdvertisingEvent:
        return AdvertisingEvent(
            timestamp_us=event.timestamp_us or 0,
            address=event.get("addr"),
            address_type=AddressType.coerce(event.integer("type", 1)),
            rssi=event.integer("rssi"),
            channel=event.integer("ch"),
            scan_response=bool(event.integer("pdu")),
            name=event.get("name"),
            payload=from_hex(event.get("data")) if event.get("data") else b"",
            host_time=event.host_time,
        )

    # ------------------------------------------------------------------
    # Miscellany
    # ------------------------------------------------------------------
    def dongle_time_us(self) -> int:
        """The dongle's microsecond timestamp now.

        Useful for relating a host-side action to the dongle's timeline: take
        it either side of the action and the dongle's own view of when it
        happened is bracketed.
        """
        reply = self._session.execute("time")
        return int(reply.fields.get("t", 0))

    def reset(self) -> None:
        """Reset the dongle's firmware and forget local state."""
        self._session.execute("reset", allow_error=True, timeout=2.0)
        self._sensors = []
        self._selected = None
        self._connected = False
        self._connection_interval_us = 0

    def read_event_queue(self) -> List[str]:
        """Unsolicited events queued but not consumed.

        The dongle has no error queue - every failure arrives in the reply to
        the command that caused it - so this returns the event backlog, which
        is what a caller actually wants to inspect after a step.
        """
        return [event.raw for event in self._session.take_events()]
