"""Driver for the GW Instek GPD-3303D bench power supply.

A linear supply with two programmable 30 V / 3 A channels and an RS-232 (and
USB-serial) command set of its own. It is not a SCPI instrument: it answers
``*IDN?`` and nothing else from IEEE 488.2 - no ``*RST``, no ``*CLS``, no
``SYSTem:ERRor?`` - so this driver takes the transport and lifecycle from
:class:`~benchtools.core.scpi.ScpiInstrument` and replaces the SCPI-specific
parts explicitly.

The supply's **third** output - the fixed 2.5 / 3.3 / 5 V rail - is not driven
from here. It is selected by a front-panel switch, so a driver could neither
set it nor read back what it is set to; see :data:`.constants.CHANNELS`.

Five things about this supply shape the driver, and each of them is a way a
naive implementation reports a number that is not true:

**The output switch is global.** ``OUT1`` and ``OUT0`` switch *both* channels;
the hardware has no per-channel output command. Per-channel control here is
therefore *emulated*: switching a channel off sets its voltage to zero and
remembers the setpoint. That is not the same thing as an open circuit, and
:meth:`output_off` says so - see its docstring before using it as an interlock.

**A channel in current limit is not at the voltage that was set.** ``STATUS?``
reports CV or CC per channel. The driver reads it alongside the measurements
rather than leaving it in a status word, because a reading taken in CC
describes a different circuit from the one the test specified.

**The supply drops commands sent too quickly.** It has a small input buffer and
no flow control, so the driver paces commands (see ``command_interval``). A
dropped command at 9600 baud is silent: the supply answers the next query
perfectly well, and the rail is not where the test believes it is.

**It reads back coarser than it programs.** Setpoints go in to 1 mV and come
back to 0.1 V; currents go in to 1 mA and come back to 10 mA (firmware V1.09,
see :data:`.constants.VOLTAGE_READBACK_RESOLUTION`). Anything comparing a
reading with a setpoint allows for that, or it fails a rail that is fine.

**In series or parallel tracking, CH2 is not its own channel.** The supply
drives it from CH1 and discards setpoints sent to it - without an error, and
without anything in ``STATUS?`` to say it did. The driver refuses to send them
(:meth:`_check_tracking`), because the alternative is a test that configures a
rail, reads back the value it sent, and never learns that the supply ignored it.

Traces to: PSU-FR-001 .. PSU-FR-043, PSU-ARC-001, PSU-DD-PSU.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ...core.errors import ConfigurationError, ProtocolError, TransportTimeoutError
from ...core.instrument import InstrumentIdentity
from ...core.scpi import ScpiInstrument
from ...core.transport.base import Transport
from ...core.transport.factory import open_transport
from .constants import (
    CHANNELS,
    CURRENT_RESOLUTION,
    DEFAULT_BAUDRATE,
    DEFAULT_COMMAND_INTERVAL,
    MAX_CURRENT,
    MAX_VOLTAGE,
    MODEL,
    REPLY_TERMINATOR,
    STATUS_BIT_BEEP,
    STATUS_BIT_OUTPUT,
    STATUS_LEGEND_LINES,
    STATUS_LENGTH,
    TRACKED_CHANNEL,
    TRACKING_MODES,
    VOLTAGE_READBACK_RESOLUTION,
    VOLTAGE_RESOLUTION,
    ChannelMode,
    TrackingMode,
)
from .simulator import SimulatedGpd

__all__ = ["Gpd3303D", "ChannelReading", "SupplyStatus"]



# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChannelReading:
    """Everything one channel is doing, taken together.

    The mode travels with the numbers deliberately. ``voltage`` alone cannot
    tell a reviewer whether the supply was holding the voltage it was asked for
    or holding a current limit instead, and those are different experiments.
    """

    channel: int
    voltage: float
    current: float
    mode: str
    is_on: bool
    voltage_setpoint: float = 0.0
    current_limit: float = 0.0

    @property
    def power(self) -> float:
        """Output power, derived from the two readings, in watts.

        Derived rather than measured: the supply reports volts and amps, and
        their product is the best available figure. It is not a wattmeter
        reading, and at low currents the current reading's own resolution
        dominates it.
        """
        return self.voltage * self.current

    @property
    def in_current_limit(self) -> bool:
        """``True`` when the channel is on and in CC, so the rail is below setpoint.

        Only an energised channel can be limiting. A real supply reports CC for
        both channels while its output switch is open, and that is not a board
        drawing too much current.
        """
        return self.is_on and self.mode == ChannelMode.CONSTANT_CURRENT

    @property
    def regulated(self) -> bool:
        """``True`` when the channel is delivering the voltage it was set to.

        This is the question a test usually means when it asks whether the
        supply is "on": energised, in constant voltage, and within the
        read-back resolution of its setpoint.

        The tolerance is one and a half read-back steps, or 1 %, whichever is
        larger: the setpoint comes back rounded to 0.1 V and the measurement
        truncated to it, so a channel set to 3.600 V and delivering it reads
        ``3.5V`` against a setpoint of ``3.6V``.
        """
        if not self.is_on or self.in_current_limit:
            return False
        return abs(self.voltage - self.voltage_setpoint) <= max(
            1.5 * VOLTAGE_READBACK_RESOLUTION, self.voltage_setpoint * 0.01
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "channel": self.channel,
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "mode": self.mode,
            "is_on": self.is_on,
            "voltage_setpoint": self.voltage_setpoint,
            "current_limit": self.current_limit,
            "in_current_limit": self.in_current_limit,
            "regulated": self.regulated,
        }


@dataclass(frozen=True)
class SupplyStatus:
    """The decoded ``STATUS?`` word, with the raw reply kept beside it.

    The decode follows what a V1.09 supply says about itself in the legend it
    sends after the bits, confirmed on the bench (PSU-OPEN-01): bit 0 first,
    output at bit 6. ``raw`` is what the supply actually said, kept so that a
    supply with other firmware can be checked against it.

    The supply does not report its line rate, so there is no field for it.
    """

    raw: str
    modes: Tuple[str, ...]
    tracking: str
    beep: bool
    output: bool

    def mode(self, channel: int) -> str:
        """CV or CC for *channel*."""
        return self.modes[channel - 1]

    def as_dict(self) -> Dict[str, object]:
        return {
            "raw": self.raw,
            "modes": {index + 1: mode for index, mode in enumerate(self.modes)},
            "tracking": self.tracking,
            "beep": self.beep,
            "output": self.output,
        }


# ---------------------------------------------------------------------------
class Gpd3303D(ScpiInstrument):
    """A GW Instek GPD-3303D two-channel bench supply.

    :param transport: An open or openable link, usually a serial port.
    :param command_interval: Minimum seconds between commands. See the module
        docstring; ``None`` picks 0 for a simulated link and
        :data:`~.constants.DEFAULT_COMMAND_INTERVAL` for a real one.

    Example::

        from benchtools.instruments.gpd3303d import Gpd3303D

        with Gpd3303D.connect("/dev/ttyUSB0") as psu:
            psu.set_voltage(1, 3.3)
            psu.set_current_limit(1, 0.5)
            psu.output_on(1)

            reading = psu.read_channel(1)
            print(reading.voltage, reading.current, reading.mode)
            if reading.in_current_limit:
                raise SystemExit("the board is drawing more than 500 mA")
    """

    SIMULATOR_CLASS = SimulatedGpd
    MODEL_NAME = MODEL
    EVENT_SOURCE = "PSU"

    def __init__(
        self,
        transport: Transport,
        auto_check_errors: bool = False,
        owns_transport: bool = True,
        command_interval: Optional[float] = None,
    ) -> None:
        super().__init__(
            transport,
            auto_check_errors=auto_check_errors,
            owns_transport=owns_transport,
        )
        # Commands go out ending in a line feed, which the supply accepts; its
        # replies end in a carriage return alone.
        transport.read_terminator = REPLY_TERMINATOR
        if command_interval is None:
            command_interval = self._default_command_interval(transport.description)
        self._command_interval = max(0.0, float(command_interval))
        self._last_command = 0.0
        #: Setpoint remembered for a channel this driver switched off, so that
        #: switching it back on restores what the test asked for. Membership is
        #: what "parked" means: a channel is parked if and only if it is in
        #: here. Tracking it separately from the supply's global output switch
        #: would be two facts that can disagree, and they did.
        self._parked: Dict[int, float] = {}

    @staticmethod
    def _default_command_interval(description: str) -> float:
        """Pace a real link; do not pace one that has no input buffer.

        A simulated or loopback link cannot overrun, and 50 ms per command
        would cost a test suite minutes for a hazard that is not there.
        """
        text = (description or "").lower()
        if "sim" in text or "loop://" in text or "mock" in text:
            return 0.0
        return DEFAULT_COMMAND_INTERVAL

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(
        cls,
        resource: str = "sim://",
        timeout: float = 5.0,
        baudrate: int = DEFAULT_BAUDRATE,
        command_interval: Optional[float] = None,
        initialise: bool = True,
        **kwargs,
    ) -> "Gpd3303D":
        """Open a supply.

        :param resource: ``/dev/ttyUSB0``, ``COM4``, ``serial://COM4:57600``,
            ``socket://terminal-server:4002`` or ``sim://``. A bare port name
            is taken as a serial port, not as a host name.
        :param baudrate: Line rate, when the resource does not carry one. The
            supply's own rate is set from its front panel and reported by
            :meth:`status`; they must agree.
        """
        target = cls._normalise_resource(resource)
        transport = open_transport(
            target,
            timeout=timeout,
            open_now=False,
            responder_factory=cls.SIMULATOR_CLASS,
            **({"baudrate": baudrate} if target.startswith("serial://") else {}),
        )
        instrument = cls(transport, command_interval=command_interval, **kwargs)
        if initialise:
            try:
                instrument.initialise()
            except Exception:
                instrument.close()
                raise
        return instrument

    @staticmethod
    def _normalise_resource(resource: str) -> str:
        """Accept a bare port name as a serial port rather than a host name."""
        text = (resource or "").strip()
        if not text:
            return "sim://"
        lowered = text.lower()
        if "://" in text or lowered in ("sim", "mock"):
            return text
        return "serial://%s" % text

    def _post_open(self) -> None:
        """Learn what the supply is, and change nothing about what it is doing.

        Connecting to a supply that is powering a board must not disturb the
        board, so this identifies it and reads its status and stops there. No
        channel starts out parked: the driver has not switched anything off,
        and a supply whose output switch happens to be open is not the same
        thing as a channel this driver zeroed.
        """
        self.identify()
        self.status()
        self._parked.clear()

    def _read_identity(self) -> InstrumentIdentity:
        """``*IDN?``, the one IEEE 488.2 query this supply answers.

        A GPD answers ``GW INSTEK,GPD-3303D,SN:EW000000,V2.00``. The serial
        number carries an ``SN:`` prefix that is part of the label, not part of
        the number, so it is removed here rather than in every report.
        """
        identity = InstrumentIdentity.from_idn(self._query("*IDN?"))
        if identity.serial_number.upper().startswith("SN:"):
            identity.serial_number = identity.serial_number[3:].strip()
        return identity

    def reset(self, settle: float = 0.2) -> None:
        """Put the supply in a safe state.

        The GPD has no ``*RST``. "Safe" here means what it means at a bench:
        both channels off and at zero volts, current limits untouched. The
        limits are left alone on purpose - they are the protection the operator
        set for the board that is connected, and a reset that silently raised
        them would be the opposite of safe.
        """
        # Written directly rather than through set_voltage: a safe state must
        # be reachable in every tracking mode, and in series or parallel the
        # slaved channel refuses a setpoint. Zeroing channel 1 zeroes both.
        for channel in CHANNELS:
            self._write("VSET%d:0.000" % channel)
        self.all_outputs_off()
        self._parked.clear()
        if settle > 0:
            time.sleep(settle)

    # ------------------------------------------------------------------
    # Primitive I/O
    # ------------------------------------------------------------------
    def _pace(self) -> None:
        """Hold off until the supply's input buffer has certainly drained."""
        if self._command_interval <= 0.0:
            return
        remaining = self._command_interval - (time.monotonic() - self._last_command)
        if remaining > 0:
            time.sleep(remaining)

    def _write(self, command: str) -> None:
        """Send one command, no faster than the supply can take them."""
        self._pace()
        super()._write(command)
        self._last_command = time.monotonic()

    def _query(self, command: str) -> str:
        """Send one query, paced, and return the reply with its whitespace off."""
        self._pace()
        response = super()._query(command)
        self._last_command = time.monotonic()
        return response

    @staticmethod
    def _parse_reading(text: str, command: str) -> float:
        """Read a number from a reply that may carry its unit.

        ``VOUT1?`` answers ``3.000V`` and ``ISET1?`` answers ``0.500``,
        depending on the firmware revision, so the unit is stripped rather than
        assumed absent.
        """
        cleaned = text.strip().rstrip("AVavW ").strip()
        try:
            return float(cleaned)
        except ValueError as exc:
            raise ProtocolError(
                "expected a number from %r, got %r" % (command, text)
            ) from exc

    def _query_reading(self, command: str) -> float:
        return self._parse_reading(self._query(command), command)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @staticmethod
    def _check_channel(channel: int) -> int:
        if channel not in CHANNELS:
            raise ConfigurationError(
                "%s has channels %s, not %r"
                % (MODEL, " and ".join(str(item) for item in CHANNELS), channel)
            )
        return int(channel)

    def _check_tracking(self, channel: int) -> None:
        """Refuse to program a channel the supply is slaving to another.

        In series and parallel tracking the supply drives CH2 from CH1. It
        accepts ``VSET2:`` and ``ISET2:`` and does nothing with them: no error,
        nothing in ``STATUS?``, and a read-back of CH2 that agrees with
        whatever CH1 is doing. A test that set CH2 in tracking mode would
        therefore be measuring CH1's setting under CH2's name.

        The mode is read from the supply at the moment of the write rather
        than cached, because it is a front-panel switch: it can move between
        one command and the next, and a cached answer would be a guess about
        hardware nobody was watching.

        A mode the status word does not decode to one of the three documented
        values is **warned about and allowed**. Refusing would turn an
        unrecognised status bit - the bit order is a bench confirmation item,
        PSU-OPEN-01 - into a driver that cannot set anything at all.

        This guards the per-channel output switch as well as the setpoints,
        because that switch is *emulated by programming the channel to zero
        volts*: if the supply discards a setpoint sent to this channel, it
        discards the "off" too, and the driver would report a rail switched off
        while it followed channel 1 at whatever the test last asked for.

        The global switch (:meth:`all_outputs_on`, :meth:`all_outputs_off`) and
        :meth:`reset` are deliberately **not** guarded: they act on the supply's
        real output switch and on channel 1, so they work in every mode. A safe
        state must never be unreachable.

        Traces to: PSU-FR-006.
        """
        if channel != TRACKED_CHANNEL:
            return
        mode = self.status().tracking
        if mode == TrackingMode.INDEPENDENT:
            return
        if mode == TrackingMode.UNKNOWN:
            self._logger.warning(
                "the supply's tracking mode did not decode, so whether channel "
                "%d is slaved to channel 1 is unknown; the setting is being "
                "sent anyway and may be discarded by the supply",
                channel,
            )
            return
        raise ConfigurationError(
            "channel %d cannot be set or switched on its own while the supply "
            "is in %s tracking: it follows channel 1, and the supply would "
            "accept the setting and discard it. Use channel 1, or switch the "
            "supply to independent tracking on the front panel."
            % (channel, mode)
        )

    @staticmethod
    def _quantise(value: float, resolution: float) -> float:
        """Round to the supply's programming step, as the supply itself will.

        Done here so that the value returned from a setter is the one the
        supply applies, free of the float noise of the arithmetic. It is not
        what the supply reads back: that is coarser - see
        :data:`~.constants.VOLTAGE_READBACK_RESOLUTION`.
        """
        return round(round(value / resolution) * resolution, 6)

    @staticmethod
    def _check_range(value: float, limit: float, quantity: str, unit: str) -> float:
        """Refuse a setting the supply would reject.

        The supply sends no reply to a setting it rejects: it keeps the
        previous setpoint and records ``Data out of range.`` for ``ERR?``,
        which the driver does not poll by default. A test that asked for 35 V
        would carry on at whatever the channel was set to before.
        """
        number = float(value)
        if number < 0.0 or number > limit:
            raise ConfigurationError(
                "%s of %g %s is outside what a %s can deliver (0 to %g %s); "
                "the supply would reject it, keep its previous setting, and "
                "say so only through ERR?"
                % (quantity, number, unit, MODEL, limit, unit)
            )
        return number

    # ------------------------------------------------------------------
    # Setting
    # ------------------------------------------------------------------
    def set_voltage(self, channel: int, volts: float) -> float:
        """Set a channel's output voltage, in volts.

        Returns the value sent, rounded to the supply's 1 mV programming step.

        On a channel that is switched **off** this updates the remembered
        setpoint instead of the live one, so that setting a voltage never
        energises a rail as a side effect; :meth:`output_on` applies it.

        Raises :class:`~benchtools.core.errors.ConfigurationError` for a
        channel the supply is slaving to another - see :meth:`_check_tracking`.
        A parked channel is refused too: the value could not take effect while
        the supply is tracking, and pretending otherwise would put a setpoint
        in the driver that the hardware will never honour.
        """
        channel = self._check_channel(channel)
        wanted = self._check_range(volts, MAX_VOLTAGE, "a voltage", "V")
        wanted = self._quantise(wanted, VOLTAGE_RESOLUTION)
        self._check_tracking(channel)
        if channel in self._parked:
            self._parked[channel] = wanted
            self._logger.debug("channel %d is parked; %.3f V held until it is switched on",
                       channel, wanted)
            return wanted
        self._write("VSET%d:%.3f" % (channel, wanted))
        self._after_configuration()
        return wanted

    def set_current_limit(self, channel: int, amps: float) -> float:
        """Set a channel's current limit, in amps.

        The limit applies whether or not the channel is switched on: it is the
        protection for whatever is connected, and it is never parked.

        Raises :class:`~benchtools.core.errors.ConfigurationError` for a
        channel the supply is slaving to another - see :meth:`_check_tracking`.
        """
        channel = self._check_channel(channel)
        wanted = self._check_range(amps, MAX_CURRENT, "a current limit", "A")
        wanted = self._quantise(wanted, CURRENT_RESOLUTION)
        self._check_tracking(channel)
        self._write("ISET%d:%.3f" % (channel, wanted))
        self._after_configuration()
        return wanted

    def configure_channel(
        self,
        channel: int,
        volts: float,
        current_limit: float,
        output: Optional[bool] = None,
    ) -> ChannelReading:
        """Set a channel's voltage and limit in one step, and read it back.

        The order matters: the current limit is set **first**, so a channel
        coming up at a new voltage is never briefly protected by the previous
        test's limit.
        """
        channel = self._check_channel(channel)
        self.set_current_limit(channel, current_limit)
        self.set_voltage(channel, volts)
        if output is not None:
            self.set_output(channel, output)
        return self.read_channel(channel)

    # ------------------------------------------------------------------
    # Reading back
    # ------------------------------------------------------------------
    def voltage_setpoint(self, channel: int) -> float:
        """The voltage the channel is set to deliver, in volts.

        For a channel switched off this is the remembered setpoint - what the
        channel will deliver when it is switched on - not the zero currently
        programmed. The distinction is the whole point of the emulation.

        Read from the supply, it comes back to 0.1 V: a channel set to
        3.250 V reports 3.3 V.
        """
        channel = self._check_channel(channel)
        if channel in self._parked:
            return self._parked[channel]
        return self._query_reading("VSET%d?" % channel)

    def current_limit(self, channel: int) -> float:
        """The channel's current limit, in amps."""
        return self._query_reading("ISET%d?" % self._check_channel(channel))

    def measure_voltage(self, channel: int) -> float:
        """Measure the channel's output voltage, in volts."""
        return self._query_reading("VOUT%d?" % self._check_channel(channel))

    def measure_current(self, channel: int) -> float:
        """Measure the channel's output current, in amps."""
        return self._query_reading("IOUT%d?" % self._check_channel(channel))

    def measure_power(self, channel: int) -> float:
        """Output power in watts, derived from the two readings.

        The supply has no wattmeter; this is volts times amps, read one after
        the other rather than simultaneously. On a changing load the two
        readings are not of the same instant.
        """
        channel = self._check_channel(channel)
        return self.measure_voltage(channel) * self.measure_current(channel)

    def read_channel(self, channel: int) -> ChannelReading:
        """Everything about one channel: measurements, setpoints and mode.

        One call, so that the numbers and the CV/CC mode that qualifies them
        come from the same moment rather than from whenever each was asked for.
        """
        channel = self._check_channel(channel)
        status = self.status()
        return ChannelReading(
            channel=channel,
            voltage=self.measure_voltage(channel),
            current=self.measure_current(channel),
            mode=status.mode(channel),
            is_on=status.output and channel not in self._parked,
            voltage_setpoint=self.voltage_setpoint(channel),
            current_limit=self.current_limit(channel),
        )

    def read_all(self) -> List[ChannelReading]:
        """A :class:`ChannelReading` for every channel."""
        return [self.read_channel(channel) for channel in CHANNELS]

    def channel_mode(self, channel: int) -> str:
        """``"CV"`` or ``"CC"`` for *channel*."""
        return self.status().mode(self._check_channel(channel))

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def status(self) -> SupplyStatus:
        """Decode ``STATUS?``.

        Accepts the reply in both forms: eight characters with nothing between
        them, as the programming manual prints it, and eight space-separated
        fields followed by two lines of legend, as firmware V1.09 sends it.
        Bits the supply reports as ``X`` are not used.

        :raises ProtocolError: if the reply is not eight bits - which usually
            means the line rate is wrong, and is worth saying plainly rather
            than decoding into nonsense.
        """
        raw = self._query("STATUS?").strip()
        spaced = " " in raw
        if spaced:
            self._read_status_legend()
        fields = raw.split() if spaced else list(raw)
        if len(fields) != STATUS_LENGTH or any(
            field.upper() not in ("0", "1", "X") for field in fields
        ):
            raise ProtocolError(
                "expected %d status bits from STATUS?, got %r. Check the line "
                "rate matches the supply's own setting (Utility > Baud)."
                % (STATUS_LENGTH, raw)
            )
        flags = [field == "1" for field in fields]
        modes = tuple(
            ChannelMode.CONSTANT_VOLTAGE if flags[index] else ChannelMode.CONSTANT_CURRENT
            for index in range(len(CHANNELS))
        )
        # Bit 2 is the left digit, as the supply's own legend writes it.
        tracking = (flags[2] << 1) | flags[3]
        return SupplyStatus(
            raw=raw,
            modes=modes,
            tracking=TRACKING_MODES.get(tracking, TrackingMode.UNKNOWN),
            beep=flags[STATUS_BIT_BEEP],
            output=flags[STATUS_BIT_OUTPUT],
        )

    def _read_status_legend(self) -> None:
        """Read the legend a V1.09 supply sends after its ``STATUS?`` bits.

        It has to be read rather than discarded: at 9600 baud it is still
        arriving when the next command goes out, and it would be taken as the
        reply to that command and the one after. A supply that sends spaced
        bits and no legend is tolerated, at the cost of one timeout.
        """
        for _ in range(STATUS_LEGEND_LINES):
            try:
                line = self._transport.read_message()
            except TransportTimeoutError:
                self._logger.warning("the supply sent no legend after STATUS?; "
                             "expected %d lines", STATUS_LEGEND_LINES)
                return
            text = line.decode("ascii", errors="replace").strip()
            if not text.lower().startswith("bit"):
                raise ProtocolError(
                    "expected the STATUS? legend after the status bits, got %r"
                    % text
                )

    def read_event_queue(self) -> List[Tuple[int, str]]:
        """Ask the supply whether it rejected anything.

        The GPD has no SCPI error queue; ``ERR?`` reports the last complaint and
        clears it. Its exact wording is a bench confirmation item
        (PSU-OPEN-02), so anything that is not recognisably "no error" is
        reported verbatim rather than parsed into a code.
        """
        try:
            message = self._query("ERR?").strip()
        except ProtocolError:  # pragma: no cover - defensive
            return []
        if not message or message.lower().startswith(("no error", "none", "0")):
            return []
        return [(1, message)]

    # ------------------------------------------------------------------
    # Output switching
    # ------------------------------------------------------------------
    def output_on(self, channel: int) -> None:
        """Energise one channel.

        Restores the setpoint the channel was parked at, then switches the
        supply's output on. Because the switch is global, this energises the
        other channel too if it was not parked at zero - which is the honest
        behaviour of the hardware, and why :meth:`output_off` parks rather than
        disconnects.

        Refused for a channel the supply is slaving to another; use
        :meth:`all_outputs_on`, which acts on the real switch.
        """
        channel = self._check_channel(channel)
        self._check_tracking(channel)
        parked = self._parked.pop(channel, None)
        if parked is not None:
            self._write("VSET%d:%.3f" % (channel, parked))
        self._write("OUT1")
        self._after_configuration()

    def output_off(self, channel: int) -> None:
        """Switch one channel off, as far as this supply can.

        **This is not an isolator.** The GPD-3303D has one output switch for
        both channels, so a single channel is switched off by programming it to
        zero volts: the terminals are at 0 V with the current limit unchanged,
        not open circuit. A channel switched off this way will still sink
        current from a board powered by something else, and it is not a safety
        interlock.

        When every channel has been switched off, the supply's real output
        switch is opened too, so "all off" means what it says.

        Refused for a channel the supply is slaving to another: programming
        that channel to zero would be discarded, and the rail would follow
        channel 1 while the driver called it off. Use :meth:`all_outputs_off`,
        which opens the switch itself.
        """
        channel = self._check_channel(channel)
        self._check_tracking(channel)
        if channel not in self._parked:
            self._parked[channel] = self.voltage_setpoint(channel)
        self._write("VSET%d:0.000" % channel)
        if all(number in self._parked for number in CHANNELS):
            self._write("OUT0")
        self._after_configuration()

    def set_output(self, channel: int, on: bool) -> None:
        """Switch *channel* on or off. See :meth:`output_off` for the caveat."""
        if on:
            self.output_on(channel)
        else:
            self.output_off(channel)

    def is_output_on(self, channel: int) -> bool:
        """``True`` when *channel* is energised.

        Both conditions must hold: the supply's output switch is closed, and
        this channel is not parked at zero.
        """
        channel = self._check_channel(channel)
        return self.status().output and channel not in self._parked

    def all_outputs_on(self) -> None:
        """Close the supply's output switch, energising every unparked channel."""
        for channel in CHANNELS:
            parked = self._parked.pop(channel, None)
            if parked is not None:
                self._write("VSET%d:%.3f" % (channel, parked))
        self._write("OUT1")
        self._after_configuration()

    def all_outputs_off(self) -> None:
        """Open the supply's output switch. This one really does switch off.

        Setpoints are left as they are, and a channel already parked stays
        parked: this opens the switch, it does not forget what the test asked
        for.
        """
        self._write("OUT0")
        self._after_configuration()

    @property
    def output(self) -> bool:
        """``True`` while the supply's output switch is closed."""
        return self.status().output

    @property
    def tracking(self) -> str:
        """``independent``, ``series`` or ``parallel``."""
        return self.status().tracking
