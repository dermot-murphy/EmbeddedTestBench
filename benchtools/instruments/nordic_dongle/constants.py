"""The dongle's command set, events, errors and envelope.

Every name here also appears in the firmware's ``include/protocol.h``, and
``tests/instruments/nordic_dongle/test_firmware_protocol.py`` parses that header
and compares the two. A command added to one side and forgotten on the other is
then a failing test rather than an "unknown command" at the bench.

Traces to: BLE-FR-001, BLE-FR-070, BLE-DD-CONST.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

__all__ = [
    "PROTOCOL_VERSION",
    "COMMANDS",
    "EVENTS",
    "DongleError",
    "AddressType",
    "ScanFilter",
    "DongleLimits",
    "DONGLE_LIMITS",
    "DEFAULT_BAUDRATE",
    "DEFAULT_SCAN_MS",
    "DEFAULT_COMMAND_TIMEOUT",
]

#: Protocol revision this driver speaks. Checked against the dongle's reply to
#: ``ver``: a dongle running older firmware is reported at connection time, not
#: discovered halfway through a measurement.
#:
#: Compared by major version. A differing *minor* version means one side has
#: commands the other does not - reported, and survivable, because the missing
#: ones fail individually with "unknown command". A differing *major* version
#: means a command means something different, which is not survivable.
PROTOCOL_VERSION = "1.1"

#: Commands the firmware accepts, with the argument bounds it enforces.
COMMANDS: Dict[str, Tuple[int, int]] = {
    "ver": (0, 0),
    "scan": (1, 5),
    "list": (0, 0),
    "select": (1, 1),
    "selected": (0, 0),
    "connect": (0, 1),
    "disconnect": (0, 0),
    "uart": (1, 1),
    "cmd": (1, 1),
    "adv": (1, 2),
    "time": (0, 0),
    "reset": (0, 0),
    "dfu": (0, 0),
}

#: Unsolicited event names, without the leading ``+``.
EVENTS: Tuple[str, ...] = ("adv", "sensor", "rx", "conn", "disc", "scan", "drop")

#: Line rate. A USB CDC port ignores it; it is set for the sake of converters
#: that do not.
DEFAULT_BAUDRATE = 115200

#: Default scan duration in milliseconds.
DEFAULT_SCAN_MS = 3000

#: Default time to wait for a sensor's reply to a command, in seconds. Longer
#: than the firmware's own 2 s timeout, so the dongle's more informative
#: "the sensor did not reply" wins over a host-side timeout.
DEFAULT_COMMAND_TIMEOUT = 3.0


class DongleError(enum.IntEnum):
    """Error codes the firmware returns in an ``err`` reply."""

    NONE = 0
    UNKNOWN = 1
    ARGS = 2
    VALUE = 3
    STATE = 4
    NO_SENSOR = 5
    NOT_CONNECTED = 6
    BUSY = 7
    TIMEOUT = 8
    TOO_LONG = 9
    BLE = 10

    @classmethod
    def coerce(cls, value) -> "DongleError":
        """Return the member for *value*, or :attr:`UNKNOWN` for a code this
        driver has not met - a newer firmware must not crash an older host."""
        try:
            return cls(int(value))
        except (ValueError, TypeError):
            return cls.UNKNOWN


class AddressType(enum.IntEnum):
    """BLE address types, as the SoftDevice numbers them.

    Carried everywhere the address is, because an address alone does not say
    whether it is public or random, and connecting with the wrong type simply
    never finds the device.
    """

    PUBLIC = 0
    RANDOM_STATIC = 1
    RANDOM_PRIVATE_RESOLVABLE = 2
    RANDOM_PRIVATE_NON_RESOLVABLE = 3

    @classmethod
    def coerce(cls, value) -> "AddressType":
        try:
            return cls(int(value))
        except (ValueError, TypeError):
            return cls.RANDOM_STATIC


@dataclass
class ScanFilter:
    """What to keep while scanning.

    Filtering happens in the firmware rather than here. Forwarding every packet
    from a busy room over USB is what causes the drops that would then be
    misread as the sensor missing an advertising event.

    :param name: Substring of the advertised name.
    :param address: Exact address, ``AA:BB:CC:DD:EE:FF``.
    :param active: Request scan responses. Costs airtime and makes the dongle
        transmit, so it is off unless the name is only in the scan response.
    :param min_rssi: Reject anything weaker, in dBm. ``None`` for no limit.
    """

    name: Optional[str] = None
    address: Optional[str] = None
    active: bool = False
    min_rssi: Optional[int] = None

    def as_arguments(self) -> Tuple[str, ...]:
        """Render as ``key=value`` tokens for the ``scan start`` command."""
        arguments = []
        if self.name:
            if " " in self.name:
                raise ValueError(
                    "a scan name filter cannot contain a space: the link is a "
                    "space-separated line protocol. Filter on a word of the "
                    "name, or filter on the address."
                )
            arguments.append("name=%s" % self.name)
        if self.address:
            arguments.append("addr=%s" % self.address)
        if self.active:
            arguments.append("active=1")
        if self.min_rssi is not None:
            arguments.append("rssi=%d" % int(self.min_rssi))
        return tuple(arguments)


@dataclass
class DongleLimits:
    """The firmware's capability envelope, as data rather than in code.

    These mirror the ``PROTO_MAX_*`` figures in ``protocol.h``. Held here so the
    driver refuses an impossible request with a clear message instead of letting
    the firmware truncate it silently.
    """

    model: str = "PCA10059"
    max_sensors: int = 16
    max_payload_bytes: int = 96
    max_name_length: int = 24
    max_line_bytes: int = 256
    #: One microsecond, the resolution of the dongle's timestamp clock.
    timestamp_resolution_s: float = 1.0e-6
    #: What the host clock resolves, for the cross-check figures. USB polling
    #: plus scheduling; a millisecond is the honest figure, not the 1 us that
    #: ``time.perf_counter`` will happily print.
    host_resolution_s: float = 1.0e-3

    @property
    def max_hex_payload(self) -> int:
        """Longest hex string the ``uart`` and ``cmd`` commands accept."""
        return self.max_payload_bytes * 2


#: The envelope of the firmware in this repository.
DONGLE_LIMITS = DongleLimits()
