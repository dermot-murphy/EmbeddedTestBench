"""A simulated Power Profiler Kit II, on a virtual clock.

It answers the commands the driver sends as the kit does, and while sampling
streams 32-bit words, 100 000 per second of *virtual* time: a read with a
timeout takes no real time, so a test measures a second in a few
milliseconds and still gets exactly 100 000 samples.

The device it powers draws :attr:`SimulatedPpk2.base_current`, with a pulse
of :attr:`~SimulatedPpk2.pulse_current` for :attr:`~SimulatedPpk2.pulse_width`
every :attr:`~SimulatedPpk2.pulse_interval`, and logic input D0 high during
each pulse. It draws nothing while the kit's DUT power is off.

Traces to: PPK-FR-010, PPK-DD-SIM.
"""

from __future__ import annotations

import struct
from typing import List, Optional

from ...core.errors import TransportTimeoutError
from .constants import (
    ADC_BITS,
    CMD_AVERAGE_START,
    CMD_AVERAGE_STOP,
    CMD_DEVICE_RUNNING_SET,
    CMD_GET_METADATA,
    CMD_REGULATOR_SET,
    CMD_SET_POWER_MODE,
    CMD_TRIGGER_SET,
    COUNTER_MASK,
    COUNTER_SHIFT,
    DEFAULT_MODIFIERS,
    LOGIC_SHIFT,
    MODE_AMMETER,
    MODE_SOURCE,
    RANGE_SHIFT,
    RANGES,
    SAMPLE_PERIOD,
)
from .protocol import Calibration

__all__ = ["SimulatedPpk2", "CHUNK_SAMPLES"]

#: Samples one read returns while sampling: 10 ms of them.
CHUNK_SAMPLES = 1000

#: Bytes each opcode takes, itself included.
_LENGTHS = {
    CMD_TRIGGER_SET: 3,
    CMD_AVERAGE_START: 1,
    CMD_AVERAGE_STOP: 1,
    CMD_DEVICE_RUNNING_SET: 2,
    CMD_REGULATOR_SET: 3,
    CMD_SET_POWER_MODE: 2,
    CMD_GET_METADATA: 1,
}


class SimulatedPpk2:  # pylint: disable=too-many-instance-attributes
    """The kit, as the driver sees it through a mock transport."""

    #: Hardware number the metadata reports.
    HW = 1

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Power-on state: source mode, 3.3 V, DUT off, not sampling."""
        self.mode = MODE_SOURCE
        self.vdd_mv = 3300
        self.running = False
        self.sampling = False
        self.clock = 0.0
        self.counter = 0
        self.calibration = Calibration()
        #: Amps drawn between pulses while powered.
        self.base_current = 20e-6
        #: Amps drawn during a pulse.
        self.pulse_current = 5e-3
        #: Seconds a pulse lasts.
        self.pulse_width = 0.005
        #: Seconds from one pulse's start to the next.
        self.pulse_interval = 0.1
        #: Samples the next chunk leaves out halfway through, the counter
        #: running on, as a real link that dropped data would.
        self.lose_samples = 0
        #: Every command received, as bytes, oldest first.
        self.received: List[bytes] = []
        #: Bytes of a command split across two writes.
        self._partial = b""

    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Act on each command in *message*; answer only ``GET_METADATA``."""
        data = self._partial + bytes(message)
        reply: Optional[bytes] = None
        index = 0
        while index < len(data):
            length = _LENGTHS.get(data[index], 1)
            if index + length > len(data):
                break
            command = data[index:index + length]
            index += length
            self.received.append(command)
            answer = self._command(command)
            if answer is not None:
                reply = (reply or b"") + answer
        self._partial = data[index:]
        return reply

    def _command(self, command: bytes) -> Optional[bytes]:
        opcode = command[0]
        if opcode == CMD_GET_METADATA:
            return self.metadata().encode("ascii")
        if opcode == CMD_AVERAGE_START:
            self.sampling = True
        elif opcode == CMD_AVERAGE_STOP:
            self.sampling = False
        elif opcode == CMD_DEVICE_RUNNING_SET:
            self.running = bool(command[1])
        elif opcode == CMD_REGULATOR_SET:
            self.vdd_mv = (command[1] << 8) | command[2]
        elif opcode == CMD_SET_POWER_MODE and command[1] in (MODE_AMMETER, MODE_SOURCE):
            self.mode = command[1]
        return None

    def metadata(self) -> str:
        """The metadata text, in the kit's order and form."""
        lines = ["Calibrated: 0"]
        for key in ("r", "gs", "gi", "o"):
            lines += ["%s%d: %.4f" % (key.upper(), index, value)
                      for index, value in enumerate(DEFAULT_MODIFIERS[key])]
        lines += ["VDD: %d" % self.vdd_mv, "HW: %d" % self.HW, "mode: %d" % self.mode]
        for key in ("s", "i"):
            lines += ["%s%d: %.9f" % (key.upper(), index, value)
                      for index, value in enumerate(DEFAULT_MODIFIERS[key])]
        lines += ["UG%d: %.2f" % (index, value)
                  for index, value in enumerate(DEFAULT_MODIFIERS["ug"])]
        lines += ["IA: 0", "END", ""]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def poll(self) -> bytes:
        """The next chunk of samples, or nothing when not sampling."""
        return self._chunk() if self.sampling else b""

    def poll_within(self, timeout: float) -> bytes:
        """The next chunk of samples; time out, as a real read would, if none.

        :raises TransportTimeoutError: when not sampling, having moved the
            clock on by *timeout*.
        """
        if not self.sampling:
            self.clock += timeout
            raise TransportTimeoutError(
                "the simulated PPK2 sent nothing within %.3f s" % timeout)
        return self._chunk()

    def current_at(self, seconds: float) -> float:
        """Amps the simulated device draws at *seconds* on the clock."""
        if not self.running:
            return 0.0
        into = seconds % self.pulse_interval if self.pulse_interval > 0 else 0.0
        return self.pulse_current if into < self.pulse_width else self.base_current

    def _chunk(self) -> bytes:
        words = bytearray()
        for index in range(CHUNK_SAMPLES):
            if index == CHUNK_SAMPLES // 2:
                while self.lose_samples > 0:
                    self.lose_samples -= 1
                    self._advance()
            amps = self.current_at(self.clock)
            current_range = self._range(amps)
            adc = self.calibration.adc(current_range, amps, self.vdd_mv) // 4
            logic = 1 if amps == self.pulse_current and self.running else 0
            word = (adc | (current_range << RANGE_SHIFT) | (self.counter << COUNTER_SHIFT)
                    | (logic << LOGIC_SHIFT))
            words += struct.pack("<I", word)
            self._advance()
        return bytes(words)

    def _advance(self) -> None:
        self.clock += SAMPLE_PERIOD
        self.counter = (self.counter + 1) & COUNTER_MASK

    def _range(self, amps: float) -> int:
        """The most sensitive range whose ADC reading for *amps* is in scale."""
        for current_range in range(RANGES):
            if self.calibration.adc(current_range, amps, self.vdd_mv) < ADC_BITS * 4 * 0.9:
                return current_range
        return RANGES - 1
