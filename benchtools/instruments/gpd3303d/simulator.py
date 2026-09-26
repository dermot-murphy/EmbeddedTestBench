"""A simulated GPD-3303D.

The model is a *supply with a load on it*, not a set of registers that echo
back what was written. That distinction is what makes the simulator worth
having: a channel whose load draws more than its current limit falls into CC
and its voltage drops, exactly as the bench does, so a driver that ignores the
CC/CV mode fails a test here rather than on the rig.

What is modelled: the command grammar and its replies, per-channel setpoints,
the single global output switch, a resistive load per channel, constant-current
fallback, the status word, the supply's refusal of an out-of-range value, and
the three tracking modes - including the part that matters, which is that a
setpoint sent to the slaved channel is **accepted and discarded**.

The replies are shaped like a real supply's (firmware V1.09, checked on the
bench): each ends in a carriage return alone, readings come back to 0.1 V and
0.01 A, and ``STATUS?`` is eight space-separated fields followed by two lines
of legend.

What is not: the fixed 2.5 / 3.3 / 5 V rail, which no command reaches; the
front panel; the timing of the supply's own regulation loop; and the read-back
truncation that makes a real unloaded 3.600 V channel measure ``3.5V`` - this
model rounds.

Traces to: PSU-FR-006, PSU-FR-050, PSU-DD-SIM.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .constants import (
    CHANNELS,
    MAX_CURRENT,
    MAX_VOLTAGE,
    MODEL,
    REPLY_TERMINATOR,
    STATUS_BIT_BEEP,
    STATUS_BIT_OUTPUT,
    STATUS_LENGTH,
    TRACKED_CHANNEL,
    TRACKING_MODES,
    ChannelMode,
    TrackingMode,
)

__all__ = ["SimulatedGpd", "SimulatedChannel"]


class SimulatedChannel:
    """One output, with whatever is connected to it.

    :param load_ohms: Resistance across the terminals. ``None`` is an open
        circuit, which is the default because an unloaded supply is the
        uninteresting case that most tests want.
    """

    def __init__(self, load_ohms: Optional[float] = None) -> None:
        self.voltage_setpoint = 0.0
        self.current_limit = 0.0
        self.load_ohms = load_ohms

    def output(self, energised: bool) -> Dict[str, float]:
        """What the terminals are doing now.

        A real supply is a voltage source until the current it would have to
        deliver exceeds the limit; then it becomes a current source at that
        limit, and the voltage is whatever the load makes of it. That is the
        whole of constant-current operation, and it is two lines here.
        """
        if not energised:
            # A real supply reports CC for both channels while its output
            # switch is open.
            return {"voltage": 0.0, "current": 0.0, "mode": ChannelMode.CONSTANT_CURRENT}
        if self.voltage_setpoint <= 0.0:
            return {"voltage": 0.0, "current": 0.0, "mode": ChannelMode.CONSTANT_VOLTAGE}
        if not self.load_ohms:
            return {
                "voltage": self.voltage_setpoint,
                "current": 0.0,
                "mode": ChannelMode.CONSTANT_VOLTAGE,
            }
        wanted = self.voltage_setpoint / self.load_ohms
        if wanted <= self.current_limit:
            return {
                "voltage": self.voltage_setpoint,
                "current": wanted,
                "mode": ChannelMode.CONSTANT_VOLTAGE,
            }
        return {
            "voltage": self.current_limit * self.load_ohms,
            "current": self.current_limit,
            "mode": ChannelMode.CONSTANT_CURRENT,
        }


class SimulatedGpd:
    """A GPD-3303D that answers its own command set.

    Satisfies :class:`~benchtools.core.simulator.Responder`, so it is reachable
    through ``sim://`` like every other simulated instrument. It is not built on
    :class:`~benchtools.core.simulator.SimulatedInstrument`: that class splits
    messages on ``;`` and on a space, which is SCPI's grammar and not this
    supply's - ``VSET1:3.300`` is one command, not a header and a sub-system.

    :param load_ohms: Load on each channel, by channel number.
    """

    DEFAULT_IDN = "GW INSTEK,%s,SN:SIM00000,V1.09" % MODEL

    #: The beeper, on as a supply leaves the factory. Tracking is per
    #: instance, because a test changes it.
    BEEP = True

    #: What a V1.09 supply sends after the eight ``STATUS?`` fields, verbatim.
    STATUS_LEGEND = (
        "bit0:(CH1)0=CC,1=CV;bit1:(CH2)0=CC,1=CV;"
        "bit23=(TRACK)01=INDEP,11=SER,10=PAR;",
        "bit4:(BEEP)0=OFF,1=ON;bit6:(OUT)0=OFF,1=ON;",
    )

    #: The two status bits for each tracking mode, bit 2 first, from
    #: :data:`.constants.TRACKING_MODES` so that the simulator and the driver
    #: cannot disagree about which pattern means what.
    _TRACKING_BITS = {name: bits for bits, name in TRACKING_MODES.items()}

    #: The digit is not restricted to a channel number: ``OUT0`` and ``OUT1``
    #: use the same position for the switch state, and a command naming a
    #: channel that does not exist must be *refused*, not unparsed.
    _PATTERN = re.compile(r"^(?P<name>[A-Z*]+)(?P<digit>\d)?(?P<tail>[:?].*)?$", re.I)

    def __init__(
        self,
        idn: Optional[str] = None,
        load_ohms: Optional[Dict[int, float]] = None,
        tracking: str = TrackingMode.INDEPENDENT,
    ) -> None:
        self.idn = idn if idn is not None else self.DEFAULT_IDN
        self.command_log: List[str] = []
        self.channels = {
            number: SimulatedChannel((load_ohms or {}).get(number)) for number in CHANNELS
        }
        #: The single output switch, which is what the hardware really has.
        self.output = False
        #: Independent, series or parallel. On the bench this is a front-panel
        #: switch as well as a command, so a test may set it either way.
        self.tracking = tracking
        self.last_error = ""
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Power-on state: output off, both channels at zero.

        Tracking is left alone: on the supply it is a switch position, and a
        power cycle does not move it.
        """
        self.output = False
        self.last_error = ""
        for channel in self.channels.values():
            channel.voltage_setpoint = 0.0
            channel.current_limit = 0.0

    def set_load(self, channel: int, ohms: Optional[float]) -> None:
        """Connect a resistive load to *channel*, or ``None`` for open circuit."""
        self.channels[channel].load_ohms = ohms

    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one command line, as the supply does."""
        text = message.decode("ascii", errors="replace").strip()
        if not text:
            return None
        self.command_log.append(text)
        reply = self._dispatch(text)
        return None if reply is None else reply.encode("ascii") + REPLY_TERMINATOR

    # ------------------------------------------------------------------
    def _dispatch(self, text: str) -> Optional[str]:
        match = self._PATTERN.match(text)
        if match is None:
            return self._refuse(text)
        name = match.group("name").upper().lstrip("*")
        channel = int(match.group("digit")) if match.group("digit") else None
        tail = (match.group("tail") or "").strip()
        query = tail.startswith("?")
        argument = tail[1:].strip() if tail.startswith(":") else ""

        handler = getattr(self, "_cmd_%s%s" % (name.lower(), "_q" if query else ""), None)
        if handler is None:
            return self._refuse(text)
        return handler(channel, argument)

    def _refuse(self, text: str) -> Optional[str]:
        """Record a rejected command.

        The supply does not answer a command it did not understand, which is
        why a driver that misspells one sees a timeout rather than an error.
        Recording it here lets a test assert on the thing the hardware only
        reveals through ``ERR?``.
        """
        self.last_error = 'Command Error, "%s"' % text
        return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _cmd_idn_q(self, _channel, _argument) -> str:
        return self.idn

    def _cmd_vset(self, channel, argument) -> None:
        self._set(channel, argument, "voltage_setpoint", MAX_VOLTAGE)
        return None

    def _cmd_iset(self, channel, argument) -> None:
        self._set(channel, argument, "current_limit", MAX_CURRENT)
        return None

    def _cmd_track(self, channel, _argument) -> None:
        """``TRACK0``, ``TRACK1``, ``TRACK2``: independent, series, parallel."""
        modes = {0: TrackingMode.INDEPENDENT, 1: TrackingMode.SERIES,
                 2: TrackingMode.PARALLEL}
        if channel not in modes:
            self.last_error = "Command Error, no tracking mode %s" % channel
            return None
        self.tracking = modes[channel]
        if self.tracking != TrackingMode.INDEPENDENT:
            self._follow()
        return None

    def _follow(self) -> None:
        """Slave the tracked channel to channel 1, as the supply does."""
        master = self.channels[CHANNELS[0]]
        slaved = self.channels[TRACKED_CHANNEL]
        slaved.voltage_setpoint = master.voltage_setpoint
        slaved.current_limit = master.current_limit

    def _set(self, channel, argument, attribute: str, limit: float) -> None:
        if channel not in self.channels:
            self.last_error = "Command Error, no channel %s" % channel
            return
        if channel == TRACKED_CHANNEL and self.tracking != TrackingMode.INDEPENDENT:
            # The behaviour the driver refuses to depend on: the supply takes
            # the command, does nothing, and reports nothing. No error is
            # recorded here because the hardware records none - that silence
            # is the whole point.
            return
        try:
            value = float(argument)
        except ValueError:
            self.last_error = 'Data Error, "%s"' % argument
            return
        # The supply clamps rather than refusing, which is exactly why the
        # driver range-checks before sending: this is the behaviour it is
        # protecting a test from.
        clamped = min(max(value, 0.0), limit)
        if clamped != value:
            self.last_error = "Data Out of Range"
        setattr(self.channels[channel], attribute, clamped)
        if self.tracking != TrackingMode.INDEPENDENT:
            self._follow()

    def _reading(self, channel, quantity: str) -> Optional[float]:
        """One channel's figure, or ``None`` for a channel that does not exist."""
        if channel not in self.channels:
            self.last_error = "Command Error, no channel %s" % channel
            return None
        return self.channels[channel].output(self.output)[quantity]

    def _cmd_vset_q(self, channel, _argument) -> Optional[str]:
        if channel not in self.channels:
            return self._refuse("VSET%s?" % channel)
        return "%.1fV" % self.channels[channel].voltage_setpoint

    def _cmd_iset_q(self, channel, _argument) -> Optional[str]:
        if channel not in self.channels:
            return self._refuse("ISET%s?" % channel)
        return "%.2fA" % self.channels[channel].current_limit

    def _cmd_vout_q(self, channel, _argument) -> Optional[str]:
        value = self._reading(channel, "voltage")
        return None if value is None else "%.1fV" % value

    def _cmd_iout_q(self, channel, _argument) -> Optional[str]:
        value = self._reading(channel, "current")
        return None if value is None else "%.2fA" % value

    def _cmd_out(self, channel, _argument) -> None:
        """``OUT1`` and ``OUT0``: one switch for both channels."""
        self.output = channel == 1
        return None

    def _cmd_status_q(self, _channel, _argument) -> str:
        """Eight fields, bit 0 first, then the legend - as V1.09 answers.

        Bits 5 and 7 are reported as ``X``, as the supply reports them.
        """
        bits = [
            "1" if self.channels[number].output(self.output)["mode"]
            == ChannelMode.CONSTANT_VOLTAGE else "0"
            for number in CHANNELS
        ]
        # A mode this simulator has no bit pattern for reports 0b00, which is
        # undocumented, rather than claiming independent. A test that sets a
        # state the model does not know about should see the driver's handling
        # of an undecodable status word, not a comfortable default.
        pattern = self._TRACKING_BITS.get(self.tracking, 0b00)
        bits += [str((pattern >> 1) & 0b1), str(pattern & 0b1)]
        bits += ["X"] * (STATUS_LENGTH - len(bits))
        bits[STATUS_BIT_BEEP] = "1" if self.BEEP else "0"
        bits[STATUS_BIT_OUTPUT] = "1" if self.output else "0"
        terminator = REPLY_TERMINATOR.decode("ascii")
        return terminator.join((" ".join(bits),) + self.STATUS_LEGEND)

    def _cmd_err_q(self, _channel, _argument) -> str:
        message = self.last_error or "No Error."
        self.last_error = ""
        return message

    def _cmd_beep(self, channel, _argument) -> None:
        type(self).BEEP = channel == 1
        return None
