"""A simulated Kepler sensor (Sensoteq Kappa X), as the bench's sensor 5C1712.

One model, read by every simulated instrument that touches the sensor: the
dongle hears its replies over BLE, the probe reads its RTT log, and the S2-LP
kit will receive its frames (#122). A command that changes the sensor -
``WR PREAMBLE-LENGTH``, ``ECURESET HARD`` - therefore changes what the others
see, as it does on the bench.

Where each reply format comes from (#121):

- ``ACK RD VERSION = V11.00.0000-95-gc051f3665``, ``ACK RD SHA = c051f3665``,
  ``ACK RD ID = 0x5C1712``, ``ACK RD BATTERY = 2789mV``,
  ``ACK RD TEMPERATURE = 21187mC``, ``ACK ECURESET HARD``: captured from
  5C1712 running V11.00.0000-95 in the 2026-10-04 qualification
  (``docs/aspice/qualification/2026-10-04``). That firmware echoes the command
  as it was sent and writes the unit straight after the number.
- ``ACK WR ALIVE-PERIOD 10 Secs``: the reply ``kepler_battery.yaml`` and
  ``kepler_temperature.yaml`` check for, and in Kepler bench traces of the
  same firmware generation.
- ``MCU Temperature: 21000mC``: the RTT line, from the same qualification
  (``qs01.events.jsonl``).
- The ranges of ``WR ALIVE-PERIOD`` (10-900 s, default 600) and
  ``WR PREAMBLE-LENGTH`` (32-1023, default 32), and the ``OUT OF RANGE``
  refusal: the sensor firmware's parameter table, ``api_param_cfg.h``.

Open items, assumed rather than captured, and marked so in BLE-DD-KEPLERSIM:

- ``ACK RD BATTERY-LOADED = <n>mV`` and ``ACK WR PREAMBLE-LENGTH <n> Pairs``
  are taken from later firmware (V11.01), which lowercases the echo and puts a
  space before the unit, and written in the V11.00 style.
- The loaded battery reads 20 mV below the unloaded one, and the MCU 3.5 C
  above the machine temperature (seen as 2.5-4.75 C on 5C1712).
- An unknown command answers ``NACK Invalid Command``.

Traces to: BLE-DD-KEPLERSIM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

__all__ = [
    "KEPLER_5C1712_ADDRESS",
    "KEPLER_5C1712_ID",
    "KEPLER_5C1712_NAME",
    "KeplerSensorModel",
]

#: The bench's sensor under test, as the specifications name it.
KEPLER_5C1712_ID = 0x5C1712
KEPLER_5C1712_ADDRESS = "D1:8D:3B:4C:19:96"
#: The name V11.00.0000 advertises: the firmware tag, cut to 23 characters by
#: that generation's advertising payload.
KEPLER_5C1712_NAME = "KAPPA_5C1712_V11.00.00"

#: RESETREAS.SREQ: the reset reason a ``ECURESET HARD`` leaves.
RESET_REASON_SOFT = 4

_WRITE = re.compile(r"^WR\s+(ALIVE-PERIOD|PREAMBLE-LENGTH)\s+(\S+)$", re.IGNORECASE)


@dataclass
class KeplerSensorModel:  # pylint: disable=too-many-instance-attributes
    """What a Kepler sensor reports, and the state its commands change.

    :param supply: Reads the volts the sensor is powered from, or None when
        nothing simulated feeds it; the battery then reads *battery_mv*. On the
        simulated bench it is the simulated supply's channel 2, which is how
        ``kepler_battery.yaml`` wires 5C1712.
    """

    sensor_id: int = KEPLER_5C1712_ID
    version: str = "V11.00.0000-95-gc051f3665"
    sha: str = "c051f3665"
    battery_mv: int = 3300
    loaded_drop_mv: int = 20
    temperature_mc: int = 21187
    mcu_above_machine_mc: int = 3500
    alive_period_s: int = 600
    preamble_length: int = 32
    reset_reason: int = 1
    resets: int = 0
    supply: Optional[Callable[[], Optional[float]]] = None

    #: Accepted ranges, from the sensor firmware's parameter table.
    ALIVE_PERIOD_RANGE = (10, 900)
    PREAMBLE_LENGTH_RANGE = (32, 1023)

    # ------------------------------------------------------------------
    def battery_now_mv(self) -> int:
        """The battery as the sensor measures it: its supply, when it has one."""
        volts = self.supply() if self.supply is not None else None
        if volts is None:
            return int(self.battery_mv)
        return int(round(volts * 1000.0))

    def mcu_temperature_mc(self) -> int:
        """The MCU die temperature, which RTT reports and BLE does not."""
        return int(self.temperature_mc + self.mcu_above_machine_mc)

    def rtt_line(self) -> str:
        """One line of the sensor's RTT log, as it writes it once a second."""
        return "MCU Temperature: %dmC" % self.mcu_temperature_mc()

    def reset(self) -> None:
        """A software reset: what ``ECURESET HARD`` does after it answers."""
        self.resets += 1
        self.reset_reason = RESET_REASON_SOFT

    # ------------------------------------------------------------------
    def respond(self, request: str) -> str:
        """The sensor's reply to one BLE console command."""
        text = " ".join(request.split())
        word = text.upper()
        readings = {
            "RD VERSION": self.version,
            "RD SHA": self.sha,
            "RD ID": "0x%06X" % self.sensor_id,
            "RD BATTERY": "%dmV" % self.battery_now_mv(),
            "RD BATTERY-LOADED": "%dmV" % (self.battery_now_mv() - self.loaded_drop_mv),
            "RD TEMPERATURE": "%dmC" % self.temperature_mc,
        }
        if word in readings:
            return "ACK %s = %s" % (text, readings[word])
        if word == "ECURESET HARD":
            return "ACK %s" % text
        match = _WRITE.match(text)
        if match:
            return self._write(text, match.group(1).upper(), match.group(2))
        return "NACK Invalid Command"

    def _write(self, text: str, parameter: str, value: str) -> str:
        if not value.isdigit():
            return "NACK %s INVALID VALUE" % text
        number = int(value)
        if parameter == "ALIVE-PERIOD":
            low, high = self.ALIVE_PERIOD_RANGE
            unit = "Secs"
        else:
            low, high = self.PREAMBLE_LENGTH_RANGE
            unit = "Pairs"
        if not low <= number <= high:
            return "NACK %s OUT OF RANGE" % text
        if parameter == "ALIVE-PERIOD":
            self.alive_period_s = number
        else:
            self.preamble_length = number
        return "ACK %s %s" % (text, unit)
