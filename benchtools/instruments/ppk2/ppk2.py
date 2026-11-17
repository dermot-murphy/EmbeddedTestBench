"""Driver for the Nordic Power Profiler Kit II (PPK2).

The PPK2 measures the current a device draws, 100 000 times a second, from
under a microamp to about 1 A. It works in one of two modes:

* **source** - it is the device's supply, at a voltage the driver sets
  (0.8 V to 5.0 V), and measures what the device draws;
* **ammeter** - an outside supply drives the device through it, and it
  measures the current on the way.

Its DUT power switch connects the device: in source mode it switches the
kit's own supply on and off, in ammeter mode the path from the outside
supply. Eight logic inputs, D0 to D7, are sampled with the current, so a
test can mark the part of a recording it cares about with a GPIO.

The driver measures for a stated time and returns every sample, as a
:class:`~.measurement.Measurement`: the average current, the peak, the
charge, and the pulses with their widths and charges.

**Safety.** A source-mode kit powers whatever is wired to it. The driver
never switches the DUT power, the mode or the voltage on its own: connecting
reads the kit and stops a measurement left running, nothing else. Switching
the mode turns the DUT power off first. ``voltage_limit``, from the bench
file, caps the voltage :meth:`Ppk2.set_voltage` accepts, and
:meth:`Ppk2.power_on` refuses a source-mode kit set above it.

Traces to: PPK-FR-001, PPK-FR-002, PPK-FR-005 .. PPK-FR-007, PPK-FR-009,
PPK-FR-012, PPK-NFR-001, PPK-ARC-001, PPK-DD-DRIVER.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ...core.errors import (
    ConfigurationError,
    ConnectionFailedError,
    InstrumentError,
    TransportTimeoutError,
)
from ...core.events import log_event, log_reading
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    BAUDRATE,
    DEFAULT_TIMEOUT,
    MANUFACTURER,
    MAX_DURATION,
    METADATA_END,
    METADATA_TIMEOUT,
    MODE_NAMES,
    MODE_SOURCE,
    MODEL,
    MODES,
    REENUMERATE_WAIT,
    SAMPLE_BYTES,
    SAMPLE_PERIOD,
    SAMPLE_RATE,
    STOP_SETTLE,
    USB_PRODUCT_ID,
    USB_VENDOR_ID,
    VOLTAGE_RANGE,
)
from .measurement import Measurement
from .protocol import (
    Calibration,
    SampleDecoder,
    metadata_command,
    millivolts,
    mode_command,
    parse_metadata,
    regulator_command,
    running_command,
    start_command,
    stop_command,
)
from .simulator import SimulatedPpk2

__all__ = ["Ppk2", "find_ppk2_ports"]

#: Seconds one read waits while samples stream. The kit sends every few
#: milliseconds, so a read this long with nothing is a kit that stopped.
_STREAM_READ = 0.5


def find_ppk2_ports() -> List[Dict[str, str]]:
    """Every PPK2 on this PC: ``{"port", "serial_number", "description"}`` each.

    Found by USB identity (:data:`~.constants.USB_VENDOR_ID`,
    :data:`~.constants.USB_PRODUCT_ID`). Needs pyserial; without it, none.
    """
    try:
        from serial.tools import list_ports  # pylint: disable=import-outside-toplevel
    except ImportError:  # pragma: no cover - environment dependent
        return []
    found = []
    for info in list_ports.comports():
        if info.vid == USB_VENDOR_ID and info.pid == USB_PRODUCT_ID:
            found.append({"port": info.device, "serial_number": info.serial_number or "",
                          "description": info.description or ""})
    return sorted(found, key=lambda item: item["port"])


def _resolve_port(resource: str, wait: float = REENUMERATE_WAIT) -> str:
    """The serial port a ``ppk2://`` resource names.

    ``ppk2://`` is the only PPK2 on the PC; ``ppk2://<serial number>`` is the
    one with that USB serial number. A port's name changes when the kit moves
    to another USB socket; its serial number does not. A kit closed a moment
    ago is off USB for under a second, so it is waited for up to *wait*
    seconds.
    """
    wanted = resource[len("ppk2://"):].strip().upper()
    deadline = time.monotonic() + wait
    while True:
        kits = find_ppk2_ports()
        if wanted:
            kits = [kit for kit in kits if kit["serial_number"].upper() == wanted]
        if kits or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    if len(kits) == 1:
        return kits[0]["port"]
    if not kits:
        raise ConnectionFailedError(
            "no PPK2%s is plugged in. `benchtools ppk2 list` shows the kits this PC sees."
            % (" with serial number %s" % wanted if wanted else ""))
    raise ConfigurationError(
        "%d PPK2s are plugged in (%s); name one: ppk2://<serial number>"
        % (len(kits), ", ".join("%s on %s" % (kit["serial_number"], kit["port"])
                                for kit in kits)))


class Ppk2(Instrument):  # pylint: disable=too-many-instance-attributes
    """A Nordic Power Profiler Kit II.

    :param transport: The kit's serial link, not yet open.
    :param resource: The resource as given, for the identity.
    :param voltage_limit: The highest voltage :meth:`set_voltage` accepts,
        and that :meth:`power_on` lets a source-mode kit switch on at.
    :param spike_filter: Smooth the samples after the kit changes current
        range, as Nordic's Power Profiler app does.
    :param timeout: Seconds a measurement may run beyond its duration
        before it is given up.

    Example::

        from benchtools.instruments.ppk2 import Ppk2

        with Ppk2.connect("ppk2://", voltage_limit=3.3) as ppk:
            ppk.set_mode("source")
            ppk.set_voltage(3.0)
            ppk.power_on()
            result = ppk.measure(1.0, threshold=0.001)
            print(result.summary(), result.pulses.mean_width)
            ppk.power_off()
    """

    SIMULATOR_CLASS = SimulatedPpk2
    MODEL_NAME = MODEL
    EVENT_SOURCE = "PPK"

    #: Seconds between samples.
    SAMPLE_PERIOD = SAMPLE_PERIOD

    def __init__(  # pylint: disable=too-many-arguments
        self,
        transport: Transport,
        resource: str = "sim://",
        *,
        voltage_limit: float = VOLTAGE_RANGE[1],
        spike_filter: bool = True,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(auto_check_errors=False)
        low, high = VOLTAGE_RANGE
        if not low <= float(voltage_limit) <= high:
            raise ConfigurationError("voltage_limit must be %.1f V to %.1f V, not %r"
                                     % (low, high, voltage_limit))
        self._transport = transport
        self._resource = resource
        self.voltage_limit = float(voltage_limit)
        self.spike_filter = bool(spike_filter)
        self._timeout = float(timeout)
        self._metadata: Dict[str, Any] = {}
        self._calibration = Calibration()
        self._mode: Optional[int] = None
        self._vdd_mv = 0
        self._powered: Optional[bool] = None
        self._adopt(transport)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(  # pylint: disable=too-many-arguments
        cls,
        resource: str = "sim://",
        timeout: float = DEFAULT_TIMEOUT,
        *,
        voltage_limit: float = VOLTAGE_RANGE[1],
        spike_filter: bool = True,
        initialise: bool = True,
    ) -> "Ppk2":
        """Open a PPK2.

        :param resource: ``ppk2://`` for the only kit on the PC,
            ``ppk2://<serial number>`` for one kit, a port (``COM5``,
            ``/dev/ttyACM0``, ``serial://COM5``) or ``sim://``.
        :param timeout: Seconds a measurement may run beyond its duration.
        :param voltage_limit: The highest voltage the driver will set or
            switch a source-mode kit on at. A bench file sets it to what the
            wired device takes.
        """
        text = str(resource or "").strip()
        lowered = text.lower()
        if not text or lowered.startswith("sim") or lowered.startswith("mock"):
            target = "sim://"
        elif lowered.startswith("ppk2://"):
            target = "serial://%s" % _resolve_port(text)
        elif "://" in text:
            target = text
        else:
            target = "serial://%s" % text
        transport = open_transport(
            target, timeout=timeout, open_now=False,
            responder_factory=SimulatedPpk2,
            **({"baudrate": BAUDRATE} if target.startswith("serial://") else {}))
        kit = cls(transport, resource=text or "sim://", voltage_limit=voltage_limit,
                  spike_filter=spike_filter, timeout=timeout)
        if initialise:
            try:
                kit.initialise()
            except Exception:
                kit.close()
                raise
        return kit

    def _open(self) -> None:
        # Closing the port takes the kit off USB for under a second while it
        # enumerates again (seen on the bench kit, 2026-11-14), so a port
        # closed a moment ago is retried rather than reported missing.
        deadline = time.monotonic() + REENUMERATE_WAIT
        while not self._transport.is_open:
            try:
                self._transport.open()
            except ConnectionFailedError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)

    def _post_open(self) -> None:
        # A measurement left running by a session that died streams into the
        # metadata reply, so stop it and drop what it sent before asking.
        self._send(stop_command())
        time.sleep(STOP_SETTLE)
        self._transport.discard_input()
        self._read_metadata()

    def _close(self) -> None:
        if self._transport.is_open:
            try:
                self._send(stop_command())
            finally:
                self._transport.close()

    @property
    def is_open(self) -> bool:
        return self._transport.is_open

    def _read_identity(self) -> InstrumentIdentity:
        hardware = self._metadata.get("hw", "")
        port = self._resource or "sim://"
        return InstrumentIdentity(
            raw="%s,%s,%s,HW %s" % (MANUFACTURER, MODEL, port, hardware),
            manufacturer=MANUFACTURER, model=MODEL, serial_number=port,
            firmware="HW %s" % hardware)

    def _send(self, command: bytes) -> None:
        self._logger.debug(">> %s", command.hex(" "))
        self._transport.write(command, append_terminator=False)

    # ------------------------------------------------------------------
    # What the kit reports
    # ------------------------------------------------------------------
    def _read_metadata(self) -> Dict[str, Any]:
        """Ask the kit for its metadata, and take its calibration, mode and voltage.

        Asked once, on opening: the bench kit answers only the first request
        after the port opens, and ignores the rest until it is opened again
        (2026-11-14). The driver keeps the mode and voltage it sets itself
        from then on.

        :raises InstrumentError: if the text does not end within
            :data:`~.constants.METADATA_TIMEOUT` seconds.
        """
        self._send(metadata_command())
        text = bytearray()
        deadline = time.monotonic() + METADATA_TIMEOUT
        saved = self._transport.timeout
        self._transport.timeout = 0.2
        try:
            while METADATA_END not in text:
                if time.monotonic() > deadline:
                    raise InstrumentError(
                        "the PPK2 did not finish its metadata within %.0f s; it sent %r"
                        % (METADATA_TIMEOUT, bytes(text[:200])))
                try:
                    text += self._transport.read_available()
                except TransportTimeoutError:
                    continue
        finally:
            self._transport.timeout = saved
        meta = parse_metadata(bytes(text).decode("ascii", errors="replace"))
        self._metadata = meta
        self._calibration = Calibration.from_metadata(meta)
        if meta.get("mode") in MODE_NAMES:
            self._mode = int(meta["mode"])
        if isinstance(meta.get("vdd"), int):
            self._vdd_mv = int(meta["vdd"])
        self._logger.info("PPK2 hardware %s, %s mode, %d mV, calibrated %s",
                          meta.get("hw"), self.mode, self._vdd_mv, meta.get("calibrated"))
        return dict(meta)

    @property
    def metadata(self) -> Dict[str, Any]:
        """The metadata the kit sent when it was opened, keys lower case.

        Its ``mode`` and ``vdd`` are those at opening; :attr:`mode` and
        :attr:`volts` follow what the driver has set since.
        """
        return dict(self._metadata)

    @property
    def calibration(self) -> Calibration:
        """The calibration the kit's metadata gave."""
        return self._calibration

    @property
    def mode(self) -> str:
        """``source`` or ``ammeter``; ``unknown`` before the kit said."""
        return MODE_NAMES.get(self._mode, "unknown") if self._mode is not None else "unknown"

    @property
    def volts(self) -> float:
        """The regulator voltage, in volts."""
        return self._vdd_mv / 1000.0

    @property
    def powered(self) -> Optional[bool]:
        """Whether the DUT power is on: ``None`` until this driver switched it.

        The kit cannot be asked, so this is what the driver last sent.
        """
        return self._powered

    def info(self) -> Dict[str, Any]:
        """What the kit is and how it is set, as a dictionary."""
        return {
            "model": MODEL, "resource": self._resource, "hardware": self._metadata.get("hw"),
            "calibrated": self._metadata.get("calibrated"), "mode": self.mode,
            "volts": self.volts, "voltage_limit": self.voltage_limit,
            "powered": self._powered, "spike_filter": self.spike_filter,
            "sample_rate": SAMPLE_RATE,
        }

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> str:
        """Select ``source`` or ``ammeter`` mode; return the mode.

        The DUT power is switched off first, and left off: switch it on with
        :meth:`power_on` once the mode and voltage are right.
        """
        name = str(mode).strip().lower()
        if name not in MODES:
            raise ConfigurationError("mode must be %s, not %r" % (" or ".join(MODES), mode))
        self.power_off()
        self._send(mode_command(MODES[name]))
        self._mode = MODES[name]
        log_event(self._logger, "ppk_mode", "PPK2 mode %s" % name, {"mode": name})
        return name

    def set_voltage(self, volts: float) -> float:
        """Set the regulator to *volts*; return the volts set.

        In source mode this is the device's supply. It must be within the
        kit's range and not above :attr:`voltage_limit`.
        """
        value = float(volts)
        if value > self.voltage_limit:
            raise ConfigurationError(
                "%g V is above this bench's PPK2 voltage limit, %g V (voltage_limit)"
                % (value, self.voltage_limit))
        try:
            command = regulator_command(value)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        self._send(command)
        self._vdd_mv = millivolts(value)
        log_event(self._logger, "ppk_voltage", "PPK2 regulator %.3f V" % self.volts,
                  {"volts": self.volts})
        return self.volts

    def power(self, on: bool) -> bool:
        """Switch the DUT power on or off; return the state set.

        Switching on is refused until the mode is known, and, in source
        mode, until the voltage is known and within :attr:`voltage_limit`.
        Switching off is never refused.
        """
        state = bool(on)
        if state and self._mode is None:
            raise ConfigurationError(
                "the PPK2's mode is not known; set_mode before switching the DUT power on")
        if state and self._mode == MODE_SOURCE and not (
                VOLTAGE_RANGE[0] <= self.volts <= self.voltage_limit):
            raise ConfigurationError(
                "the PPK2 is set to %g V, outside this bench's limit of %g V or not "
                "known; set_voltage first" % (self.volts, self.voltage_limit))
        self._send(running_command(state))
        self._powered = state
        log_event(self._logger, "ppk_power", "PPK2 DUT power %s" % ("on" if state else "off"),
                  {"on": state, "mode": self.mode, "volts": self.volts})
        return state

    def power_on(self) -> bool:
        """Switch the DUT power on."""
        return self.power(True)

    def power_off(self) -> bool:
        """Switch the DUT power off."""
        return self.power(False)

    # ------------------------------------------------------------------
    # Measuring
    # ------------------------------------------------------------------
    def measure(self, duration: float, threshold: Optional[float] = None,
                release: Optional[float] = None, line: Optional[int] = None) -> Measurement:
        """Record *duration* seconds of samples.

        :param duration: Seconds, at most :data:`~.constants.MAX_DURATION`.
        :param threshold: Amps: the result's ``pulses`` are the stretches at
            or above it.
        :param release: Amps a pulse falls below to end; *threshold* if not
            given.
        :param line: Logic input 0 to 7: the result's ``pulses`` are the
            stretches it is high. Give this or *threshold*, not both.
        :raises InstrumentError: if the kit stops sending before the
            duration is recorded.
        """
        seconds = float(duration)
        if not 0 < seconds <= MAX_DURATION:
            raise ConfigurationError("duration must be above 0 s and at most %g s, not %r"
                                     % (MAX_DURATION, duration))
        try:
            result = Measurement(mode=self.mode, volts=self.volts, threshold=threshold,
                                 release=release, line=line)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        wanted = int(round(seconds * SAMPLE_RATE))
        raw = self._record(wanted * SAMPLE_BYTES, seconds)
        decoder = SampleDecoder(self._calibration, self._vdd_mv, self.spike_filter)
        decoder.feed(raw)
        result.amps = decoder.amps[:wanted]
        result.logic = decoder.logic[:wanted]
        result.lost = decoder.lost
        self._report(result)
        return result

    def average_current(self, duration: float) -> float:
        """The average current over *duration* seconds, in amps."""
        result = self.measure(duration)
        return result.average if result.average is not None else 0.0

    def _record(self, size: int, seconds: float) -> bytes:
        """Start sampling, read *size* bytes, stop. Raw bytes, decoded later.

        Decoding takes longer than the kit takes to send, so the bytes are
        kept and decoded once sampling has stopped.
        """
        self._transport.discard_input()
        raw = bytearray()
        saved = self._transport.timeout
        self._transport.timeout = _STREAM_READ
        deadline = time.monotonic() + seconds + self._timeout
        self._send(start_command())
        try:
            while len(raw) < size:
                try:
                    raw += self._transport.read_available()
                except TransportTimeoutError as exc:
                    raise InstrumentError(
                        "the PPK2 stopped sending after %d of %d samples"
                        % (len(raw) // SAMPLE_BYTES, size // SAMPLE_BYTES)) from exc
                if time.monotonic() > deadline:
                    raise InstrumentError(
                        "the PPK2 sent %d of %d samples in %.1f s"
                        % (len(raw) // SAMPLE_BYTES, size // SAMPLE_BYTES,
                           seconds + self._timeout))
        finally:
            self._send(stop_command())
            time.sleep(STOP_SETTLE)
            self._transport.discard_input()
            self._transport.timeout = saved
        return bytes(raw[:size])

    def _report(self, result: Measurement) -> None:
        figures = result.as_dict()
        log_event(self._logger, "ppk_measurement", "PPK2 %s" % result.summary(), figures)
        if result.average is not None:
            log_reading(self._logger, "current", result.average, "A", mode=result.mode,
                        volts=result.volts, duration=result.duration)
