"""The firmware a simulated J-Link target runs: its symbols, flow and identity.

Split from :mod:`.simulator` (#349), which re-exports every name here. A
:class:`SimulatedFirmware` declares the ordered ``flow`` of source locations the
program passes through, with a cumulative cycle count at each; the simulator
advances along it.

Traces to: JLINK-FR-090, JLINK-DD-SIM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

__all__ = [
    "SimulatedSymbol", "SimulatedFirmware", "DEFAULT_FIRMWARE", "DEVICE_ID_ADDRESS",
    "DEVICE_ID_VALID", "SIMULATED_DEVICE_ID", "SIMULATED_DEVICE_ID_VALIDITY",
]


@dataclass
class SimulatedSymbol:
    """A variable the simulated firmware exposes.

    :param address: Address in target memory.
    :param size: Size in bytes.
    :param value: Value reported by expression evaluation. An ``int`` is also
        written into simulated memory so a raw memory read agrees with it.
    :param type_name: C type name, as GDB would report.
    """

    address: int
    size: int = 4
    value: Any = 0
    type_name: str = "int"


@dataclass
class SimulatedFirmware:  # pylint: disable=too-many-instance-attributes
    """The program the simulated target is running.

    :param flow: Ordered locations execution passes through. Repeat a location
        to model a loop.
    :param cycles_at: Cumulative DWT cycle count on reaching each location.
    :param symbols: Variables, by name.
    :param locations: Address of each named location.
    :param stacks: Call stack at a location, innermost frame first, as
        ``(function, file, line)`` tuples.
    :param rtt_at: RTT lines the target emits on reaching a location.
    :param rtt_responses: Reply the target sends for a line written to RTT.
    :param itm_at: ITM ``(channel, value)`` written on reaching a location,
        for the SWO timing method.
    :param sections: Flash sections as ``name -> (address, size)``.
    :param core_clock_hz: Core clock, used to convert cycles to seconds.
    :param memory: Bytes present in the part rather than in the program, by
        address - an identity record programmed at manufacture, for instance.
    """

    path: str = "firmware.elf"
    flow: List[str] = field(default_factory=list)
    cycles_at: Dict[str, int] = field(default_factory=dict)
    symbols: Dict[str, SimulatedSymbol] = field(default_factory=dict)
    locations: Dict[str, int] = field(default_factory=dict)
    stacks: Dict[str, List[Tuple[str, str, int]]] = field(default_factory=dict)
    rtt_at: Dict[str, List[str]] = field(default_factory=dict)
    rtt_responses: Dict[str, str] = field(default_factory=dict)
    itm_at: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    sections: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    core_clock_hz: float = 64.0e6
    #: Bytes in target memory that are not variables of the program: an
    #: identifier programmed into the part at manufacture, a lock byte, a
    #: calibration record. Address to the raw bytes at it - raw, because such a
    #: record has its own layout and byte order, and writing it as a word here
    #: would bake this model's guess about that into the fixture.
    memory: Dict[int, bytes] = field(default_factory=dict)

    def address_of(self, location: str) -> int:
        """Return the address of *location*, inventing a stable one if unknown."""
        if location in self.locations:
            return self.locations[location]
        # A stable synthetic address, so an unlisted location still behaves
        # consistently across calls rather than differing each time.
        return 0x08000000 + (abs(hash(location)) % 0x10000) * 2


#: Where the simulated part keeps its identity record: nRF52 UICR
#: ``CUSTOMER[0]``. A real part reads 0xFFFFFFFF here until someone programs it,
#: which is an invalid record by the rule below.
DEVICE_ID_ADDRESS = 0x10001080

#: The first byte of that record says whether the rest of it means anything:
#: **zero is valid**. A part that was never programmed reads 0xFF here, so the
#: unprogrammed case fails the same check as a corrupted one.
DEVICE_ID_VALID = 0x00
SIMULATED_DEVICE_ID_VALIDITY = DEVICE_ID_VALID

#: The three bytes after it are the identifier, most significant first - the
#: order they are printed in, and the order the board advertises them in. This
#: one renders as ``0A1B2C``, which is in the name of the device the simulated
#: dongle advertises, so a specification that reads the identifier off the part
#: and then goes looking for that board works end to end with no hardware.
SIMULATED_DEVICE_ID = 0x0A1B2C


def _default_firmware() -> SimulatedFirmware:
    """A small firmware exercising every feature the driver offers.

    Cycle counts are chosen so intervals are exact round numbers at 64 MHz:
    ``sensor_start`` to ``sensor_done`` is 64 000 cycles, i.e. exactly 1.000 ms.
    """
    return SimulatedFirmware(
        path="firmware.elf",
        flow=[
            "main.c:100",          # main entered
            "sensor.c:40",         # sensor_start
            "sensor.c:75",         # sensor_done
            "main.c:130",          # loop body
            "sensor.c:40",         # second iteration
            "sensor.c:75",
            "main.c:130",
        ],
        cycles_at={
            "main.c:100": 1_000,
            "sensor.c:40": 5_000,
            "sensor.c:75": 69_000,     # 64 000 cycles after sensor.c:40 => 1.000 ms
            "main.c:130": 70_000,
        },
        locations={
            "main": 0x08000400,
            "main.c:100": 0x08000400,
            "main.c:130": 0x08000460,
            "sensor_start": 0x08001200,
            "sensor.c:40": 0x08001200,
            "sensor_done": 0x080012C0,
            "sensor.c:75": 0x080012C0,
        },
        symbols={
            "sensor_count": SimulatedSymbol(0x20000100, 4, 7, "uint32_t"),
            "sensor_mv": SimulatedSymbol(0x20000104, 4, 1234, "uint32_t"),
            "device_state": SimulatedSymbol(0x20000108, 4, 2, "enum state_t"),
            "firmware_version": SimulatedSymbol(0x2000010C, 8, "1.4.2", "char [8]"),
            "timer_start": SimulatedSymbol(0x20000120, 4, 5_000, "uint32_t"),
            "timer_end": SimulatedSymbol(0x20000124, 4, 69_000, "uint32_t"),
        },
        stacks={
            "sensor.c:75": [
                ("sensor_done", "sensor.c", 75),
                ("sensor_read", "sensor.c", 120),
                ("main", "main.c", 130),
            ],
            "sensor.c:40": [
                ("sensor_start", "sensor.c", 40),
                ("main", "main.c", 100),
            ],
        },
        rtt_at={
            "sensor.c:40": ["sensor: start"],
            "sensor.c:75": ["sensor: done mv=1234", "sensor: count=7"],
            "main.c:130": ["main: loop"],
        },
        rtt_responses={
            "version": "1.4.2",
            "status": "ok",
            "reset": "resetting",
        },
        itm_at={
            "sensor.c:40": (1, 0xAA),
            "sensor.c:75": (1, 0xBB),
        },
        sections={
            ".text": (0x08000000, 0x4000),
            ".rodata": (0x08004000, 0x200),
            ".data": (0x20000000, 0x180),
        },
        memory={
            # The identity record: a validity byte, then three identifier bytes
            # in address order. It is not a variable of the program - it is
            # programmed once, at manufacture, and outlives any image flashed
            # over it, which is exactly why a test reads it to find out which
            # board it has.
            DEVICE_ID_ADDRESS: (
                bytes([SIMULATED_DEVICE_ID_VALIDITY])
                + SIMULATED_DEVICE_ID.to_bytes(3, "big")
            ),
        },
    )


#: The firmware used when a simulator is created without one.
DEFAULT_FIRMWARE = _default_firmware
