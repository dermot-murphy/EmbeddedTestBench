"""What the Pico 2 + SHT30-D thermometer is, and what its protocol says.

The command and error tables mirror ``firmware/pico_sht30/include/protocol.h``.
A test parses that header and compares it with these tables
(``tests/instruments/pico_sht30/test_firmware_protocol.py``), so the two cannot
drift apart unnoticed.

Traces to: PICO-FR-001 .. PICO-FR-005, PICO-FR-040, PICO-DD-CONST.
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "MANUFACTURER",
    "MODEL",
    "NAME",
    "COPYRIGHT",
    "PROTOCOL_VERSION",
    "RD_OPTIONS",
    "RD_ERROR",
    "SENSOR",
    "DEFAULT_ADDRESS",
    "DEFAULT_BAUDRATE",
    "COMMANDS",
    "ERRORS",
    "ERROR_NO_SENSOR",
    "ERROR_CRC",
    "ERROR_BUS",
    "STATUS_BITS",
    "TEMPERATURE_RANGE",
    "TEMPERATURE_ACCURACY",
    "HUMIDITY_ACCURACY",
    "raw_to_celsius",
    "raw_to_percent",
    "milli_to_centi_text",
]

MANUFACTURER = "Raspberry Pi"
MODEL = "Pico 2"

#: What ``rd name`` and ``rd copyright`` report; ``firmware_version.h``.
NAME = "Pico 2 SHT30 Temperature Sensor"
COPYRIGHT = "(c) 2026 Dermot Murphy"

#: Protocol revision this driver speaks; ``PROTO_VERSION`` in protocol.h. The
#: firmware does not report it: ``rd name`` identifies the firmware instead.
PROTOCOL_VERSION = "2.0"

#: The options ``rd`` answers, in the order ``rd`` documents them.
RD_OPTIONS = ("name", "copyright", "version", "sha", "temperature")

#: The value ``rd temperature`` reports when there is no reading, and that a
#: ``NAK`` carries.
RD_ERROR = "Error"

#: Sensor part on the DollaTek SHT30-D module.
SENSOR = "SHT30-DIS"

#: 7-bit I2C address with the module's ADDR pin low.
DEFAULT_ADDRESS = 0x44

#: USB CDC ignores the line rate; a value is needed only to open the port.
DEFAULT_BAUDRATE = 115200

#: ``{command: (min_args, max_args)}`` from PROTO_COMMAND_TABLE.
COMMANDS: Dict[str, Tuple[int, int]] = {
    "help": (0, 0),
    "rd": (1, 1),
    "status": (0, 0),
    "sreset": (0, 0),
    "ecureset": (0, 0),
    "bootsel": (0, 0),
}

#: ``{code: symbol}`` from PROTO_ERROR_TABLE.
ERRORS: Dict[int, str] = {
    0: "PROTO_ERR_NONE",
    1: "PROTO_ERR_UNKNOWN",
    2: "PROTO_ERR_ARGS",
    3: "PROTO_ERR_TOO_LONG",
    4: "PROTO_ERR_NO_SENSOR",
    5: "PROTO_ERR_CRC",
    6: "PROTO_ERR_BUS",
}

ERROR_NO_SENSOR = 4
ERROR_CRC = 5
ERROR_BUS = 6

#: SHT3x status register bits (Sensirion datasheet, table 17).
STATUS_BITS: Dict[str, int] = {
    "alert_pending": 0x8000,
    "heater_on": 0x2000,
    "rh_alert": 0x0800,
    "t_alert": 0x0400,
    "reset_detected": 0x0010,
    "command_failed": 0x0002,
    "write_crc_failed": 0x0001,
}

#: What the SHT30 can report at all, in degrees Celsius.
TEMPERATURE_RANGE: Tuple[float, float] = (-45.0, 130.0)

#: Typical accuracy from the datasheet: +/-0.2 C (0..65 C), +/-2 %RH (10..90 %RH).
TEMPERATURE_ACCURACY = 0.2
HUMIDITY_ACCURACY = 2.0

_FULL_SCALE = 65535


def raw_to_celsius(raw: int) -> float:
    """Convert a raw temperature word exactly as the firmware does.

    Integer arithmetic, rounded to the nearest milli-degree; the simulator uses
    it so that its readings are ones the firmware could produce.
    """
    return ((175000 * int(raw) + _FULL_SCALE // 2) // _FULL_SCALE - 45000) / 1000.0


def raw_to_percent(raw: int) -> float:
    """Convert a raw humidity word exactly as the firmware does."""
    return ((100000 * int(raw) + _FULL_SCALE // 2) // _FULL_SCALE) / 1000.0


def milli_to_centi_text(milli: int) -> str:
    """Format milli-degrees as ``rd temperature`` does: two places, half away from zero.

    ``22848`` -> ``"22.85"``, ``-1235`` -> ``"-1.24"``, ``-4`` -> ``"0.00"``.
    """
    magnitude = (abs(int(milli)) + 5) // 10
    sign = "-" if milli < 0 and magnitude else ""
    return "%s%d.%02d" % (sign, magnitude // 100, magnitude % 100)
