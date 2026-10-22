"""The simulated bench's shared state: its supply and its sensors.

Each simulated instrument is built on its own, from a ``sim://`` resource, and
knows nothing of the others. What they have in common on a real bench - the
sensor they all talk to, and the supply it runs from - is kept here, once per
process, so that a voltage set on the simulated supply is the battery the
simulated sensor reports, and a command sent over the simulated dongle changes
what the simulated probe's RTT log says.

The supply is the most recently built simulated GPD-3303D still alive; a test
that builds several gets the last. ``reset_world`` forgets everything, for a
test that must start clean.

Traces to: BLE-DD-SIMWORLD.
"""

from __future__ import annotations

import weakref
from typing import Callable, Dict, Optional

from .kepler import KEPLER_5C1712_ID, KeplerSensorModel

__all__ = ["kepler_sensor", "register_supply", "reset_world", "rtt_source", "supply_volts"]

#: The channel 5C1712 is wired to on the bench (``kepler_battery.yaml``).
SENSOR_SUPPLY_CHANNEL = 2

_sensors: Dict[int, KeplerSensorModel] = {}
_supply: Optional["weakref.ref"] = None


def register_supply(simulator) -> None:
    """Make *simulator* the supply the simulated sensor is powered from.

    Held weakly: a supply nothing else uses any more powers nothing.
    """
    global _supply  # pylint: disable=global-statement
    _supply = weakref.ref(simulator)


def supply_volts(channel: int = SENSOR_SUPPLY_CHANNEL) -> Optional[float]:
    """The volts at *channel* of the simulated supply, or None without one.

    An output that is switched off reads 0 V, as the sensor would see it.
    """
    simulator = _supply() if _supply is not None else None
    if simulator is None:
        return None
    return float(simulator.terminal_volts(channel))


def kepler_sensor(sensor_id: int = KEPLER_5C1712_ID) -> KeplerSensorModel:
    """The simulated Kepler sensor with this identifier, made on first use."""
    if sensor_id not in _sensors:
        _sensors[sensor_id] = KeplerSensorModel(sensor_id=sensor_id, supply=supply_volts)
    return _sensors[sensor_id]


#: What a simulated probe can be wired to, by the name a bench file gives:
#: the target whose RTT log it then reads.
RTT_TARGETS = {"kepler-5c1712": KEPLER_5C1712_ID}


def rtt_source(target: str) -> Callable[[], str]:
    """The periodic RTT line of the simulated *target*, e.g. ``kepler-5C1712``.

    :raises ValueError: for a target nothing simulates.
    """
    key = target.strip().lower()
    if key not in RTT_TARGETS:
        raise ValueError("no simulated target %r; there is %s"
                         % (target, ", ".join(sorted(RTT_TARGETS))))
    sensor_id = RTT_TARGETS[key]
    return lambda: kepler_sensor(sensor_id).rtt_line()


def reset_world() -> None:
    """Forget the supply and every sensor."""
    global _supply  # pylint: disable=global-statement
    _supply = None
    _sensors.clear()
