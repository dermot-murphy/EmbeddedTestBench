"""What the TTi 1604 is, and what its interface documents say.

Every number here is transcribed from the instrument's own documents, which
are kept beside the design notes in ``docs/dmm/reference/``:

* *Instruction Manual* - ranges, resolutions, reading rate, key behaviour.
* *Remote Control Commands and Logging Data Format*, V.1 23.04.98, amended
  03.08.01 - the link settings, the key characters and the reading frame.

Where the two disagree, or where the remote-control note is silent, the value
chosen is stated beside it and the question is listed as a bench confirmation
item in ``docs/dmm/TTi1604_Notes.md`` (DMM-OPEN-nn).

Traces to: DMM-FR-001 .. DMM-FR-023, DMM-DD-CONST.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = [
    "MANUFACTURER",
    "MODEL",
    "BAUDRATE",
    "DTR_LEVEL",
    "RTS_LEVEL",
    "ECHO_TIMEOUT",
    "SEND_ATTEMPTS",
    "READING_INTERVAL",
    "SETTLE_TIMEOUT",
    "FRAME_START",
    "FRAME_LENGTH",
    "Key",
    "Function",
    "MeterRange",
    "UNITS_CODES",
    "FUNCTION_CODING",
    "FUNCTION_KEYS",
    "FUNCTION_UNIT",
    "DISPLAY_FACTOR",
    "RANGES",
    "FREQUENCY_RANGES",
    "SEGMENTS",
    "SELECTABLE_FUNCTIONS",
    "CURRENT_FUNCTIONS",
    "find_range",
]

MANUFACTURER = "THURLBY THANDAR"
MODEL = "1604"

# ---------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------
#: 9600 baud, 1 start, 8 data, 1 stop, no parity. Fixed: the meter has no
#: setting for it.
BAUDRATE = 9600

#: The meter's RS-232 output is opto-isolated and takes its power from the
#: host: DTR "must be set to +9V (logic 0)" and RTS "must be set to -9V
#: (logic 1)". On the wire, a positive level is an *asserted* control line, so
#: DTR is held asserted and RTS negated. With either wrong the meter is
#: silent, which looks exactly like a broken cable.
DTR_LEVEL = True
RTS_LEVEL = False

#: "If a response is not seen within 300ms then the command must be resent."
ECHO_TIMEOUT = 0.3

#: How many times a key is sent before the driver gives up. The note sets no
#: number; five is 1.5 s of silence, well past anything a working link does.
SEND_ATTEMPTS = 5

#: 2.5 readings per second, from the manual's specification.
READING_INTERVAL = 0.4

#: How long a function or range change may take to show in the readings. The
#: note says a key typically takes 1 - 2 s to act; this allows twice that.
SETTLE_TIMEOUT = 4.0

#: Every reading frame starts with a carriage return.
FRAME_START = 0x0D

#: Characters in a frame: CR, range, function, sign, five digits, status. The
#: note also calls the string "null-terminated"; a NUL after the ten bytes is
#: accepted and ignored rather than required (DMM-OPEN-01).
FRAME_LENGTH = 10


class Key:
    """The characters that stand for the meter's front-panel keys.

    Each is acknowledged by the meter echoing it back. The Ohms key's name is
    lost from the published note's character set; ``'i'`` is the only
    character left for it and the manual's key list agrees.
    """

    UP = "a"
    DOWN = "b"
    AUTO = "c"
    AMPS = "d"
    MILLIAMPS = "e"
    VOLTS = "f"
    OPERATE = "g"
    OHMS = "i"
    HERTZ = "j"
    SHIFT = "k"
    AC = "l"
    DC = "m"
    MILLIVOLTS = "n"
    REMOTE = "u"
    LOCAL = "v"

    ALL = ("a", "b", "c", "d", "e", "f", "g", "i", "j", "k", "l", "m", "n", "u", "v")


class Function:
    """What the meter is measuring, as one word a test can name."""

    DC_VOLTS = "dc_volts"
    AC_VOLTS = "ac_volts"
    DC_MILLIVOLTS = "dc_millivolts"
    AC_MILLIVOLTS = "ac_millivolts"
    DC_MILLIAMPS = "dc_milliamps"
    AC_MILLIAMPS = "ac_milliamps"
    DC_AMPS = "dc_amps"
    AC_AMPS = "ac_amps"
    OHMS = "ohms"
    FREQUENCY = "frequency"
    CONTINUITY = "continuity"
    DIODE = "diode"


#: Bits 0 - 2 of the range character. 5 is resistance: the Ohm sign did not
#: survive in the published note, but the ranges listed against it (400 to
#: 40 M) are the resistance ranges.
UNITS_CODES: Dict[int, str] = {
    1: "mV",
    2: "V",
    3: "mA",
    4: "A",
    5: "ohm",
    6: "continuity",
    7: "diode",
}

#: (units code, AC bit) for every function the frame can report without the
#: Hz flag.
FUNCTION_CODING: Dict[Tuple[int, bool], str] = {
    (1, False): Function.DC_MILLIVOLTS,
    (1, True): Function.AC_MILLIVOLTS,
    (2, False): Function.DC_VOLTS,
    (2, True): Function.AC_VOLTS,
    (3, False): Function.DC_MILLIAMPS,
    (3, True): Function.AC_MILLIAMPS,
    (4, False): Function.DC_AMPS,
    (4, True): Function.AC_AMPS,
    (5, False): Function.OHMS,
    (5, True): Function.OHMS,
    (6, False): Function.CONTINUITY,
    (6, True): Function.CONTINUITY,
    (7, False): Function.DIODE,
    (7, True): Function.DIODE,
}

#: The keys that select each function from any other, in order. The manual:
#: "V followed by DC to set DC Volts".
FUNCTION_KEYS: Dict[str, Tuple[str, ...]] = {
    Function.DC_VOLTS: (Key.VOLTS, Key.DC),
    Function.AC_VOLTS: (Key.VOLTS, Key.AC),
    Function.DC_MILLIVOLTS: (Key.MILLIVOLTS, Key.DC),
    Function.AC_MILLIVOLTS: (Key.MILLIVOLTS, Key.AC),
    Function.DC_MILLIAMPS: (Key.MILLIAMPS, Key.DC),
    Function.AC_MILLIAMPS: (Key.MILLIAMPS, Key.AC),
    Function.DC_AMPS: (Key.AMPS, Key.DC),
    Function.AC_AMPS: (Key.AMPS, Key.AC),
    Function.OHMS: (Key.OHMS,),
}

#: Functions a caller may select. Continuity and diode test are reached with
#: SHIFT and a key the published note does not name, so they are decoded when
#: the operator selects them but not selectable from here (DMM-OPEN-05).
SELECTABLE_FUNCTIONS: Tuple[str, ...] = tuple(FUNCTION_KEYS) + (Function.FREQUENCY,)

#: Functions that put the meter's current shunt across its input. Selecting one
#: with the leads across a voltage source blows a fuse, so the driver never
#: selects one the caller did not name (DMM-NFR-002).
CURRENT_FUNCTIONS: Tuple[str, ...] = (
    Function.DC_MILLIAMPS,
    Function.AC_MILLIAMPS,
    Function.DC_AMPS,
    Function.AC_AMPS,
)

#: The SI unit every value is reported in.
FUNCTION_UNIT: Dict[str, str] = {
    Function.DC_VOLTS: "V",
    Function.AC_VOLTS: "V",
    Function.DC_MILLIVOLTS: "V",
    Function.AC_MILLIVOLTS: "V",
    Function.DC_MILLIAMPS: "A",
    Function.AC_MILLIAMPS: "A",
    Function.DC_AMPS: "A",
    Function.AC_AMPS: "A",
    Function.OHMS: "ohm",
    Function.FREQUENCY: "Hz",
    Function.CONTINUITY: "ohm",
    Function.DIODE: "V",
}

#: What one displayed unit is in SI, for the functions whose display unit the
#: frame states outright.
DISPLAY_FACTOR: Dict[int, float] = {1: 1e-3, 2: 1.0, 3: 1e-3, 4: 1.0, 7: 1.0}


@dataclass(frozen=True)
class MeterRange:
    """One measurement range.

    :param code: The value in bits 4 - 6 of the range character.
    :param label: As the manual names it.
    :param full_scale: The range's span in SI units.
    :param resolution: The value of one count in SI units, from the manual's
        specification tables.
    :param limit: The magnitude above which the meter shows OFL, where the
        manual gives one that is not the full scale.
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

    @property
    def counts(self) -> int:
        """Counts at full scale: 40,000 on DC, 4,000 on AC."""
        return int(round(self.full_scale / self.resolution))


#: Ranges per function, from the manual's specification tables.
#:
#: The range *codes* come from the remote-control note, which labels the AC
#: current ranges "1 mA" and "100 mA" where the manual's specification says
#: 4 mA and 400 mA. The manual's figures are used (DMM-OPEN-03).
RANGES: Dict[str, Tuple[MeterRange, ...]] = {
    Function.DC_VOLTS: (
        MeterRange(1, "4 V", 4.0, 1e-4),
        MeterRange(2, "40 V", 40.0, 1e-3),
        MeterRange(3, "400 V", 400.0, 1e-2),
        MeterRange(4, "1000 V", 1000.0, 1e-1, limit=1024.0),
    ),
    Function.AC_VOLTS: (
        MeterRange(1, "4 V", 4.0, 1e-3),
        MeterRange(2, "40 V", 40.0, 1e-2),
        MeterRange(3, "400 V", 400.0, 1e-1),
        MeterRange(4, "750 V", 750.0, 1.0, limit=768.0),
    ),
    Function.DC_MILLIVOLTS: (MeterRange(3, "400 mV", 0.4, 1e-5),),
    Function.AC_MILLIVOLTS: (MeterRange(3, "400 mV", 0.4, 1e-4),),
    Function.DC_MILLIAMPS: (
        MeterRange(1, "4 mA", 4e-3, 1e-7),
        MeterRange(3, "400 mA", 0.4, 1e-5),
    ),
    Function.AC_MILLIAMPS: (
        MeterRange(1, "4 mA", 4e-3, 1e-6),
        MeterRange(3, "400 mA", 0.4, 1e-4),
    ),
    Function.DC_AMPS: (MeterRange(2, "10 A", 10.0, 1e-3),),
    Function.AC_AMPS: (MeterRange(2, "10 A", 10.0, 1e-2),),
    Function.OHMS: (
        MeterRange(0, "400 ohm", 400.0, 1e-2),
        MeterRange(1, "4 kohm", 4e3, 1e-1),
        MeterRange(2, "40 kohm", 4e4, 1.0),
        MeterRange(3, "400 kohm", 4e5, 10.0),
        MeterRange(4, "4 Mohm", 4e6, 100.0),
        MeterRange(5, "40 Mohm", 4e7, 1e3),
    ),
    Function.CONTINUITY: (MeterRange(1, "4 kohm", 4e3, 1e-1),),
    Function.DIODE: (MeterRange(1, "4 V", 4.0, 1e-4),),
}

#: Frequency ranges, selected by the gate-time flag rather than the range
#: code. The manual's text gives the 4 kHz range the 10 s gate and 0.1 Hz
#: resolution; its specification table has the gate times the other way round
#: (DMM-OPEN-04). The text is followed.
FREQUENCY_RANGES: Dict[bool, MeterRange] = {
    False: MeterRange(0, "40 kHz", 4e4, 1.0),
    True: MeterRange(0, "4 kHz", 4e3, 0.1),
}

#: Seven-segment patterns of the five display characters. Bit 0 of every
#: pattern is clear; the meter sets it on the character to the left of the
#: decimal point. Code 2 is published as a blank, like 0; it is taken to be
#: the centre segment alone and read as a blank as published.
SEGMENTS: Dict[int, str] = {
    252: "0",
    96: "1",
    218: "2",
    242: "3",
    102: "4",
    182: "5",
    190: "6",
    224: "7",
    254: "8",
    230: "9",
    238: "A",
    156: "C",
    122: "D",
    158: "E",
    142: "F",
    140: "R",
    30: "T",
    124: "U",
    28: "L",
    0: " ",
    2: " ",
}


def find_range(function: str, code: int) -> Optional[MeterRange]:
    """The range *code* means for *function*, or ``None`` if none is listed."""
    for candidate in RANGES.get(function, ()):
        if candidate.code == code:
            return candidate
    return None
