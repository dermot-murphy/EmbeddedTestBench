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

**The air (#122).** What the sensors transmit is on an air clock, in seconds,
that only a listening receiver moves: when a simulated S2-LP is receiving and
has nothing to report, it moves the clock on to the next transmission
(:meth:`Air.next_transmission`). A sensor's 10 s alive period therefore costs a
test nothing, and nothing is sent while no receiver listens, so no frame is
lost between two receives that a bench would have lost. The gap between
receives is modelled by the S2-LP simulator itself, not here.

Traces to: BLE-DD-SIMWORLD.
"""

from __future__ import annotations

import weakref
from typing import Callable, Dict, List, Optional, Sequence

from .kepler import KEPLER_5C1712_ID, KeplerSensorModel, Transmission

__all__ = ["Air", "air", "air_time", "kepler_sensor", "register_supply", "reset_world",
           "rtt_source", "supply_volts"]

#: The channel 5C1712 is wired to on the bench (``kepler_battery.yaml``).
SENSOR_SUPPLY_CHANNEL = 2

_sensors: Dict[int, KeplerSensorModel] = {}
#: The supply, held weakly: a supply nothing else uses any more powers nothing.
_SUPPLY: Dict[str, "weakref.ref"] = {}
#: The air clock, in seconds.
_AIR = {"now": 0.0}


def air_time() -> float:
    """The air clock, in seconds."""
    return _AIR["now"]


def register_supply(simulator) -> None:
    """Make *simulator* the supply the simulated sensor is powered from.

    The latest one built wins.
    """
    _SUPPLY["supply"] = weakref.ref(simulator)


def supply_volts(channel: int = SENSOR_SUPPLY_CHANNEL) -> Optional[float]:
    """The volts at *channel* of the simulated supply, or None without one.

    An output that is switched off reads 0 V, as the sensor would see it.
    """
    held = _SUPPLY.get("supply")
    simulator = held() if held is not None else None
    if simulator is None:
        return None
    return float(simulator.terminal_volts(channel))


def kepler_sensor(sensor_id: int = KEPLER_5C1712_ID) -> KeplerSensorModel:
    """The simulated Kepler sensor with this identifier, made on first use."""
    if sensor_id not in _sensors:
        _sensors[sensor_id] = KeplerSensorModel(sensor_id=sensor_id, supply=supply_volts,
                                                clock=air_time)
    return _sensors[sensor_id]


#: What a simulated instrument can be wired to, by the name a bench file
#: gives: the probe reads the target's RTT log, the S2-LP kit hears its radio.
TARGETS = {"kepler-5c1712": KEPLER_5C1712_ID}


def _target(target: str) -> int:
    """The sensor a target name stands for.

    :raises ValueError: for a target nothing simulates.
    """
    key = target.strip().lower()
    if key not in TARGETS:
        raise ValueError("no simulated target %r; there is %s"
                         % (target, ", ".join(sorted(TARGETS))))
    return TARGETS[key]


def rtt_source(target: str) -> Callable[[], str]:
    """The periodic RTT line of the simulated *target*, e.g. ``kepler-5C1712``.

    :raises ValueError: for a target nothing simulates.
    """
    sensor_id = _target(target)
    return lambda: kepler_sensor(sensor_id).rtt_line()


class Air:  # pylint: disable=too-few-public-methods  # one question: what comes next
    """The transmitters one simulated receiver is in range of."""

    def __init__(self, sensor_ids: Sequence[int]) -> None:
        self.sensor_ids: List[int] = list(sensor_ids)

    def next_transmission(self) -> Optional[Transmission]:
        """The next copy of a frame any of them sends, with the clock moved to it.

        None if none of them will transmit.
        """
        due = [(at, sensor_id) for sensor_id in self.sensor_ids
               for at in [kepler_sensor(sensor_id).next_transmission_at()] if at is not None]
        if not due:
            return None
        at, sensor_id = min(due)
        _AIR["now"] = max(_AIR["now"], at)
        return kepler_sensor(sensor_id).transmit()


def air(targets: Sequence[str]) -> Air:
    """What a receiver wired to the simulated *targets* hears.

    :raises ValueError: for a target nothing simulates.
    """
    return Air([_target(target) for target in targets])


def reset_world() -> None:
    """Forget the supply, every sensor, and the air clock."""
    _SUPPLY.clear()
    _sensors.clear()
    _AIR["now"] = 0.0
