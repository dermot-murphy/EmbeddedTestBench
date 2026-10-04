"""What the TTi 1604 is, and what its serial protocol says.

The 1604 is a 4-3/4 digit (40 000 count) true-RMS bench multimeter. It has no
command language in the usual sense: the RS-232 link carries **single ASCII
characters that stand for front-panel key presses**, and in remote mode the
meter streams a ten-byte binary frame after every measurement. There is no
query, no ``*IDN?`` and no error queue.

Three facts here decide whether a reading is true, and each of them is a way a
naive implementation reports a number that is not:

**The host powers the interface through the handshake lines.** The RS-232 side
is fully opto-isolated from the measurement system and draws its power from
DTR and RTS: DTR must be asserted (+9 V) and RTS must *not* be (-9 V). Open the
port with a serial library's defaults and the interface is unpowered - the
meter answers nothing, and every obvious diagnosis (wrong rate, bad cable, dead
meter) is wrong. See :data:`DTR_ASSERTED` and :data:`RTS_ASSERTED`.

**A frame is only meaningful from its start.** Byte 0 of every frame is a
carriage return. Because the meter streams continuously, a reader that simply
takes the next ten bytes can land mid-frame, and the five display digits then
decode against the wrong positions. The result is not an error - it is a
plausible wrong number. See :data:`FRAME_START`.

**The digits are a seven-segment bitmap, not a character code.** Each digit
byte has the decimal point in bit 0 and the seven segments in bits 1 to 7, so
the value is read from the *shape* on the display. That is why the meter can
send ``OFL`` down the same five bytes that normally carry a number, and why a
decoder must be prepared for a reading that is not a number at all.

Sources
-------
* *1604 Instruction Manual* (Issue 12) - interface, pinout, 9600 baud, reading
  rate, 40 000 counts, OFL. Read directly.
* *TTi 1604 Serial Control* - key characters, frame layout, field bit
  positions, as supplied by the project owner.
* *1604 Remote Control Commands and Logging Data Format*, V.1 23.04.98,
  amended 03.08.01 (Thurlby Thandar) - the manufacturer's own note, kept in
  ``docs/dmm/reference/``. Where it and the summary above disagree on a bit
  position, the manufacturer's note is followed (#115).
* *1604 Instruction Manual* specification tables - the full scale and
  resolution of every range, in :data:`RANGES`.
* ``ddland/pythoncode`` ``tti1604/tti1604.py`` (MIT, Copyright (c) 2022 Derek
  Land) - a working implementation, used here to corroborate the segment
  patterns, the field bit positions and the DTR/RTS requirement. No code from
  it is reproduced; the protocol facts it demonstrates are recorded below in
  this project's own form.

Traces to: DMM-FR-001 .. DMM-FR-033, DMM-DD-CONST.
"""

from __future__ import annotations

from typing import Dict, NamedTuple, Optional, Tuple

__all__ = [
    "MODEL",
    "MANUFACTURER",
    "DEFAULT_BAUDRATE",
    "BYTESIZE",
    "PARITY",
    "STOPBITS",
    "DTR_ASSERTED",
    "RTS_ASSERTED",
    "FRAME_LENGTH",
    "FRAME_START",
    "INDEX_RANGE",
    "INDEX_FUNCTION",
    "INDEX_SIGN",
    "INDEX_FIRST_DIGIT",
    "INDEX_LAST_DIGIT",
    "INDEX_STATUS",
    "DIGIT_COUNT",
    "DISPLAY_COUNTS",
    "READING_INTERVAL",
    "ECHO_TIMEOUT",
    "SETTLING_TIME",
    "KEYS",
    "REMOTE",
    "LOCAL",
    "SEGMENT_PATTERNS",
    "DECIMAL_POINT_BIT",
    "MEASUREMENT_TYPES",
    "RANGE_DESCRIPTIONS",
    "FUNCTION_BITS",
    "STATUS_BITS",
    "SIGN_BIT",
    "OVERRANGE_TEXT",
    "CONFIRM_TIMEOUT",
    "READ_POLL",
    "GATE_TIME",
    "MeterRange",
    "RANGES",
    "FREQUENCY_RANGES",
    "find_range",
]

MODEL = "1604"
MANUFACTURER = "Thurlby Thandar Instruments"

# --- the link -------------------------------------------------------------

#: The meter's only line rate. It is not selectable.
DEFAULT_BAUDRATE = 9600
BYTESIZE = 8
PARITY = "N"
STOPBITS = 1

#: DTR must be asserted and RTS must not be: together they power the
#: opto-isolated interface. These are not flow control, and getting them wrong
#: presents as a meter that is simply not there.
DTR_ASSERTED = True
RTS_ASSERTED = False

# --- the frame ------------------------------------------------------------

FRAME_LENGTH = 10
#: Byte 0 of every frame. The only thing that says where a frame begins.
FRAME_START = 0x0D

INDEX_RANGE = 1
INDEX_FUNCTION = 2
INDEX_SIGN = 3
INDEX_FIRST_DIGIT = 4
INDEX_LAST_DIGIT = 8
INDEX_STATUS = 9
DIGIT_COUNT = INDEX_LAST_DIGIT - INDEX_FIRST_DIGIT + 1

#: Display resolution: 4-3/4 digits. Load-bearing for the ohms scaling, where
#: the top range shows 40 000 kilohms rather than 40 megohms.
DISPLAY_COUNTS = 40000

#: Published reading rate, 2.5 readings per second. Polling faster returns the
#: same measurement again rather than a new one.
READING_INTERVAL = 0.4

#: A command is echoed back; if the echo has not arrived within this long, the
#: command was lost and is sent again.
ECHO_TIMEOUT = 0.3

#: How long the meter takes to act on a key press and settle, worst case.
SETTLING_TIME = 2.0

#: How long one read of the link waits before the driver checks its own
#: deadline again. Fixed, and set on the transport once: pyserial reconfigures
#: the port on every change of timeout, and on Windows that loses bytes in
#: flight (TB-SWE3-002 LL-07), so the driver never varies it per read.
READ_POLL = 0.05

#: How long a function or range change may take to show in the readings. The
#: manufacturer's note says a key typically takes 1 - 2 s to act; this allows
#: twice that before the driver reports that the meter did not follow.
CONFIRM_TIMEOUT = 4.0

#: Seconds per reading when measuring frequency, by the 10 s gate flag. The
#: meter reads once per gate, not 2.5 times a second, so every wait for a
#: frequency reading must allow for it (#115).
GATE_TIME: Dict[bool, float] = {False: 1.0, True: 10.0}

# --- key presses ----------------------------------------------------------

#: The character that stands for each front-panel key. There is no 'h'.
KEYS: Dict[str, str] = {
    "up": "a",
    "down": "b",
    "auto": "c",
    "amps": "d",
    "milliamps": "e",
    "volts": "f",
    "operate": "g",
    "ohms": "i",
    "hertz": "j",
    "shift": "k",
    "ac": "l",
    "dc": "m",
    "millivolts": "n",
}

#: Enter remote mode. Until this is sent the meter streams nothing at all.
REMOTE = "u"
#: Return the meter to local (front-panel) control.
LOCAL = "v"

# --- the display ----------------------------------------------------------

#: Bit 0 of a digit byte is the decimal point, not a segment.
DECIMAL_POINT_BIT = 0x01

#: Seven-segment bit patterns, with the decimal point masked off.
#:
#: The layout is bit 7 = top, 6 = top right, 5 = bottom right, 4 = bottom,
#: 3 = bottom left, 2 = top left, 1 = middle. ``8`` is every segment lit
#: (0xFE) and ``0`` is that less the middle (0xFC), which is how the map was
#: checked. ``9`` is drawn without its bottom segment, as this display does.
SEGMENT_PATTERNS: Dict[int, str] = {
    0xFC: "0",
    0x60: "1",
    0xDA: "2",
    0xF2: "3",
    0x66: "4",
    0xB6: "5",
    0xBE: "6",
    0xE0: "7",
    0xFE: "8",
    0xE6: "9",
    0xEE: "A",
    0x9C: "C",
    0x7A: "D",
    0x9E: "E",
    0x8E: "F",
    0x8C: "R",
    0x1E: "T",
    0x7C: "U",
    0x1C: "L",
    0x02: "",          # middle segment alone: a blanked digit
    0x00: "",          # nothing lit
}

#: What the meter shows when the input is too great for the range. The letter
#: O is drawn with the same segments as a zero, so it arrives as "0FL".
OVERRANGE_TEXT = "0FL"

# --- the range byte -------------------------------------------------------

#: Bits 0 to 2 of the range byte: what is being measured.
MEASUREMENT_TYPES: Dict[int, str] = {
    1: "millivolts",
    2: "volts",
    3: "milliamps",
    4: "amps",
    5: "ohms",
    6: "continuity",
    7: "diode",
}

#: Bits 4 to 6 of the range byte, by measurement type where it differs.
RANGE_DESCRIPTIONS: Dict[int, str] = {
    0: "400 ohm",
    1: "4 kohm / 4 V / 4 mA dc / 1 mA ac",
    2: "40 kohm / 40 V / 10 A",
    3: "400 kohm / 400 V / 400 mA / 400 mV",
    4: "4 Mohm / 750 V ac / 1000 V dc",
    5: "40 Mohm",
}

#: Bit 3 of the range byte.
AC_BIT = 0x08

# --- the function and status bytes ---------------------------------------

#: Bit positions in the function byte (byte 2).
#:
#: T-Hold is bit 1, as the manufacturer's note gives it. It was bit 0 here
#: until #115; bit 0 is not used by the meter.
FUNCTION_BITS: Dict[str, int] = {
    "touch_hold": 1,
    "min_max": 2,
    "hertz": 4,
    "null": 5,
    "auto_range": 6,
}

#: Bit positions in the status byte (byte 9).
#:
#: Auto-range-set is bit 1, as the manufacturer's note gives it. It was bit 2
#: here until #115; bit 2 is not used by the meter.
STATUS_BITS: Dict[str, int] = {
    "double_beep": 0,
    "auto_range_set": 1,
    "continuity_buzzer": 3,
    "showing_minimum": 4,
    "showing_maximum": 5,
    "hold": 6,
    "gate_ten_seconds": 7,
}

#: Bit 1 of the sign byte (byte 3) is the minus sign.
SIGN_BIT = 0x02

#: Measurement type to (SI unit, factor applied to the displayed number).
#:
#: Ohms is absent because its factor depends on the range: the meter displays
#: kilohms on every range but the 400 ohm one, including the top range, where
#: 40 Mohm is shown as 40 000 kohm. See :func:`.protocol.unit_and_scale`.
UNIT_SCALE: Dict[int, Tuple[str, float]] = {
    1: ("V", 1e-3),
    2: ("V", 1.0),
    3: ("A", 1e-3),
    4: ("A", 1.0),
    7: ("V", 1.0),
}


# --- ranges ---------------------------------------------------------------

class MeterRange(NamedTuple):
    """One measurement range, from the instruction manual's specification.

    :param code: The range field of the range byte, 0 to 5.
    :param label: As the manual names it.
    :param full_scale: The range's span, in SI units.
    :param resolution: The value of one count, in SI units.
    :param limit: The magnitude above which the meter shows OFL, where the
        manual gives one other than the full scale.
    """

    code: int
    label: str
    full_scale: float
    resolution: float
    limit: Optional[float] = None

    @property
    def overload(self) -> float:
        """The magnitude above which this range reads OFL."""
        return self.limit if self.limit is not None else self.full_scale


#: Ranges per (measurement type, AC), in the order Up steps through them.
#:
#: The range codes are the remote-control note's. Its labels for the AC
#: current ranges (1 mA, 100 mA) disagree with the manual's specification
#: (4 mA, 400 mA); the manual's figures are used, and the value is scaled from
#: the display rather than the label, so readings are unaffected.
RANGES: Dict[Tuple[int, bool], Tuple[MeterRange, ...]] = {
    (2, False): (
        MeterRange(1, "4 V", 4.0, 1e-4),
        MeterRange(2, "40 V", 40.0, 1e-3),
        MeterRange(3, "400 V", 400.0, 1e-2),
        MeterRange(4, "1000 V", 1000.0, 1e-1, 1024.0),
    ),
    (2, True): (
        MeterRange(1, "4 V", 4.0, 1e-3),
        MeterRange(2, "40 V", 40.0, 1e-2),
        MeterRange(3, "400 V", 400.0, 1e-1),
        MeterRange(4, "750 V", 750.0, 1.0, 768.0),
    ),
    (1, False): (MeterRange(3, "400 mV", 0.4, 1e-5),),
    (1, True): (MeterRange(3, "400 mV", 0.4, 1e-4),),
    (3, False): (
        MeterRange(1, "4 mA", 4e-3, 1e-7),
        MeterRange(3, "400 mA", 0.4, 1e-5),
    ),
    (3, True): (
        MeterRange(1, "4 mA", 4e-3, 1e-6),
        MeterRange(3, "400 mA", 0.4, 1e-4),
    ),
    (4, False): (MeterRange(2, "10 A", 10.0, 1e-3),),
    (4, True): (MeterRange(2, "10 A", 10.0, 1e-2),),
    (5, False): (
        MeterRange(0, "400 ohm", 400.0, 1e-2),
        MeterRange(1, "4 kohm", 4e3, 1e-1),
        MeterRange(2, "40 kohm", 4e4, 1.0),
        MeterRange(3, "400 kohm", 4e5, 10.0),
        MeterRange(4, "4 Mohm", 4e6, 100.0),
        MeterRange(5, "40 Mohm", 4e7, 1e3),
    ),
}

#: Frequency ranges, chosen by the 10 s gate flag rather than the range code.
#: The manual's text gives the 4 kHz range the 10 s gate and 0.1 Hz
#: resolution; its specification table has the gate times the other way
#: round. The text is followed (DMM-OPEN-06).
FREQUENCY_RANGES: Dict[bool, MeterRange] = {
    False: MeterRange(0, "40 kHz", 4e4, 1.0),
    True: MeterRange(0, "4 kHz", 4e3, 0.1),
}


def find_range(measurement_type: int, ac: bool, code: int) -> Optional[MeterRange]:
    """The range *code* means for a measurement, or ``None`` if none is listed.

    Resistance is the same range whichever coupling the frame reports.
    """
    if measurement_type == 5:
        ac = False
    for candidate in RANGES.get((measurement_type, bool(ac)), ()):
        if candidate.code == code:
            return candidate
    return None
