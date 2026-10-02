"""Decoding a TTi 1604 measurement frame.

This module is pure: it turns ten bytes into a :class:`Reading` and knows
nothing about serial ports. That separation is deliberate - frame decoding is
where a wrong number comes from, and it should be testable without a meter,
a port, or a simulator.

Traces to: DMM-FR-010 .. DMM-FR-028, DMM-DD-PROTO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from ...core.errors import ProtocolError
from .constants import (
    AC_BIT,
    DECIMAL_POINT_BIT,
    DIGIT_COUNT,
    FRAME_LENGTH,
    FRAME_START,
    FREQUENCY_RANGES,
    FUNCTION_BITS,
    INDEX_FIRST_DIGIT,
    INDEX_FUNCTION,
    INDEX_RANGE,
    INDEX_SIGN,
    INDEX_STATUS,
    MEASUREMENT_TYPES,
    OVERRANGE_TEXT,
    RANGE_DESCRIPTIONS,
    SEGMENT_PATTERNS,
    SIGN_BIT,
    STATUS_BITS,
    UNIT_SCALE,
    find_range,
)

__all__ = [
    "Reading",
    "FrameAssembler",
    "decode",
    "find_frame_start",
    "frame_problem",
    "resistance_scale",
    "digits_text",
    "unit_and_scale",
]


@dataclass(frozen=True)
class Reading:  # pylint: disable=too-many-instance-attributes
    """One measurement, as the meter's display showed it.

    :param value: The measurement in SI units - volts, amps, ohms or hertz -
        or ``None`` when the display did not show a number. Overrange is the
        usual reason; a blanked display during a range change is another.
    :param unit: SI unit of :attr:`value`.
    :param text: What the display actually read, sign and decimal point
        included. Kept because it is the evidence for :attr:`value`, and
        because it is the only thing that survives when the display is
        showing letters.
    :param measurement: ``volts``, ``amps``, ``ohms``, ``continuity`` ...
    :param ac: True for an AC measurement, False for DC.
    :param range_index: The meter's range selection, 0 to 5.
    :param range_description: What that range means, for a report.
    :param overrange: The input was too great for the range. The measurement
        is not a number and must not be treated as one.
    :param flags: Function annunciators - ``touch_hold``, ``min_max``,
        ``hertz``, ``null``, ``auto_range``.
    :param status: Display state - ``hold``, ``showing_minimum``,
        ``showing_maximum``, ``continuity_buzzer`` and so on.
    :param raw: The frame this was decoded from.
    """

    value: Optional[float]
    unit: str
    text: str
    measurement: str
    ac: bool
    range_index: int
    range_description: str
    overrange: bool
    flags: Dict[str, bool] = field(default_factory=dict)
    status: Dict[str, bool] = field(default_factory=dict)
    raw: bytes = b""
    problem: str = ""
    range_label: str = ""

    @property
    def function(self) -> str:
        """What the meter is measuring, as one word a test can name.

        ``dc_volts``, ``ac_milliamps``, ``ohms``, ``frequency`` and so on. This
        is what the driver checks after a key press to confirm the meter
        followed it (DMM-FR-029).
        """
        if self.flags.get("hertz"):
            return "frequency"
        if self.measurement in ("ohms", "continuity", "diode"):
            return self.measurement
        return "%s_%s" % ("ac" if self.ac else "dc", self.measurement)

    @property
    def is_live(self) -> bool:
        """A number that is the input's value now: not overrange, not held."""
        return self.value is not None and not self.held

    @property
    def held(self) -> bool:
        """The display is frozen, so this reading may not be current.

        True for Hold, Touch-Hold, or while the display is showing the stored
        minimum or maximum. A held value is a real measurement, but it is not
        necessarily *this moment's* measurement, and a test that treats it as
        live is measuring the past.
        """
        return bool(
            self.status.get("hold")
            or self.flags.get("touch_hold")
            or self.status.get("showing_minimum")
            or self.status.get("showing_maximum")
        )

    def __str__(self) -> str:
        if self.overrange:
            return "overrange (%s)" % self.measurement
        if self.value is None:
            return "%s (%s)" % (self.text or "blank", self.measurement)
        return "%g %s%s" % (self.value, self.unit, " AC" if self.ac else "")


def find_frame_start(buffer: bytes) -> int:
    """Index of the first frame start in *buffer*, or -1.

    The meter streams without pause, so a reader that takes the next ten bytes
    has no idea whether it is looking at a frame or at the tail of one and the
    head of the next. Only the carriage return at byte 0 says where a frame
    begins.
    """
    return buffer.find(bytes([FRAME_START]))


def digits_text(frame: bytes) -> str:
    """The five display digits as characters, decimal point included.

    Each digit byte carries the decimal point in bit 0 and a seven-segment
    pattern in the rest. An unrecognised pattern is rendered ``?`` rather than
    dropped: a decoder that silently discards what it cannot read turns
    ``1.234`` into ``1234``.
    """
    out = []
    for offset in range(DIGIT_COUNT):
        byte = frame[INDEX_FIRST_DIGIT + offset]
        pattern = byte & ~DECIMAL_POINT_BIT & 0xFF
        character = SEGMENT_PATTERNS.get(pattern)
        out.append("?" if character is None else character)
        if byte & DECIMAL_POINT_BIT:
            out.append(".")
    return "".join(out)


def frame_problem(frame: bytes) -> str:
    """Why *frame* is not one the meter would send, or ``""`` if it is.

    Length and a leading carriage return are not enough. The meter streams
    without gaps, so a reader that joins part-way through a frame can find a
    carriage return that is not a frame start - and the ten bytes after it
    decode to a plausible wrong number. Every display byte must also be a
    pattern the meter draws, the units field must name a measurement, and the
    display can carry at most one decimal point. A candidate that fails is not
    a frame, and :class:`FrameAssembler` looks again from the next byte
    (DMM-FR-028).
    """
    if len(frame) != FRAME_LENGTH:
        return "a frame is %d bytes, got %d" % (FRAME_LENGTH, len(frame))
    if frame[0] != FRAME_START:
        return "a frame starts with 0x%02X, got 0x%02X" % (FRAME_START, frame[0])
    if (frame[INDEX_RANGE] & 0x07) not in MEASUREMENT_TYPES:
        return "range byte 0x%02X names no measurement" % frame[INDEX_RANGE]
    points = 0
    for offset in range(DIGIT_COUNT):
        byte = frame[INDEX_FIRST_DIGIT + offset]
        if (byte & ~DECIMAL_POINT_BIT & 0xFF) not in SEGMENT_PATTERNS:
            return "display byte %d is 0x%02X, not a pattern the meter draws" % (offset, byte)
        points += byte & DECIMAL_POINT_BIT
    if points > 1:
        return "the display has %d decimal points" % points
    return ""


def resistance_scale(range_index: int, text: str) -> Optional[float]:
    """Ohms per displayed unit, derived rather than assumed, or ``None``.

    The frame does not carry the k or M annunciator. The manual gives each
    range's resolution in ohms, and the display's last digit is worth
    ``10**-decimals`` displayed units, so their ratio is the multiplier. It
    must come out at 1, 1 000 or 1 000 000; anything else means the display
    does not fit the range, and no number is better than a guessed one
    (DMM-FR-016).
    """
    meter_range = find_range(5, False, range_index)
    if meter_range is None:
        return None
    _whole, point, fraction = text.lstrip("-").partition(".")
    decimals = len(fraction) if point else 0
    ratio = meter_range.resolution / (10.0 ** -decimals)
    for multiplier in (1.0, 1e3, 1e6):
        if abs(ratio / multiplier - 1.0) < 1e-6:
            return multiplier
    return None


def unit_and_scale(measurement_type: int, range_index: int, hertz: bool) -> Tuple[str, float]:
    """SI unit and the factor from displayed number to that unit.

    Frequency is a mode rather than a measurement type: with Hz selected the
    display reads hertz whatever the input jack says, so the flag wins.

    Ohms is the awkward one. The meter displays kilohms on every range except
    the 400 ohm one - including the 40 Mohm range, which reads 40 000 kohm
    because the display has 40 000 counts. A single factor of 1000 is therefore
    right for ranges 1 to 5, which is only obvious once the count is known.
    """
    if hertz:
        return "Hz", 1.0
    if measurement_type == 5:                       # ohms
        return "ohm", 1.0 if range_index == 0 else 1e3
    if measurement_type == 6:                       # continuity
        return "ohm", 1.0
    unit, scale = UNIT_SCALE.get(measurement_type, ("", 1.0))
    return unit, scale


def decode(frame: bytes) -> Reading:  # pylint: disable=too-many-locals
    """Turn one ten-byte frame into a :class:`Reading`.

    :raises ProtocolError: The frame is the wrong length or does not start
        where a frame starts. Both mean the reader has lost sync, and the
        digits in hand belong to no single measurement.
    """
    if len(frame) != FRAME_LENGTH:
        raise ProtocolError(
            "a 1604 frame is %d bytes, got %d. The reader is out of step with "
            "the meter's stream." % (FRAME_LENGTH, len(frame))
        )
    if frame[0] != FRAME_START:
        raise ProtocolError(
            "a 1604 frame starts with 0x%02X, this one starts with 0x%02X. "
            "Decoding it would put the display digits in the wrong columns and "
            "produce a plausible wrong number." % (FRAME_START, frame[0])
        )

    range_byte = frame[INDEX_RANGE]
    measurement_type = range_byte & 0x07
    ac = bool(range_byte & AC_BIT)
    range_index = (range_byte >> 4) & 0x07

    flags = {name: bool(frame[INDEX_FUNCTION] & (1 << bit)) for name, bit in FUNCTION_BITS.items()}
    status = {name: bool(frame[INDEX_STATUS] & (1 << bit)) for name, bit in STATUS_BITS.items()}

    text = digits_text(frame)
    negative = bool(frame[INDEX_SIGN] & SIGN_BIT)
    if negative:
        text = "-" + text

    overrange = OVERRANGE_TEXT in text.upper().replace(".", "")
    unit, scale = unit_and_scale(measurement_type, range_index, flags["hertz"])
    problem = ""
    if measurement_type == 5 and not flags["hertz"] and not overrange:
        derived = resistance_scale(range_index, text)
        if derived is None:
            problem = (
                "the resistance display %r does not fit the %s range's resolution, "
                "so its multiplier cannot be derived (DMM-OPEN-08)"
                % (text, RANGE_DESCRIPTIONS.get(range_index, "unknown"))
            )
        else:
            scale = derived

    value = None  # type: Optional[float]
    if not overrange and not problem:
        try:
            value = float(text) * scale
        except ValueError:
            value = None

    if flags["hertz"]:
        meter_range = FREQUENCY_RANGES[status["gate_ten_seconds"]]
    else:
        meter_range = find_range(measurement_type, ac, range_index)

    return Reading(
        value=value,
        unit=unit,
        text=text,
        measurement=MEASUREMENT_TYPES.get(measurement_type, "unknown"),
        ac=ac,
        range_index=range_index,
        range_description=RANGE_DESCRIPTIONS.get(range_index, "unknown"),
        overrange=overrange,
        flags=flags,
        status=status,
        raw=bytes(frame),
        problem=problem,
        range_label=meter_range.label if meter_range is not None else "",
    )


class FrameAssembler:
    """Separate measurement frames from everything else in the byte stream.

    The meter streams frames continuously in remote mode, and it also echoes
    every key character it is sent. Those two things share one direction of one
    serial link, so an echo arrives interleaved with measurement data.

    Picking the echo out by looking for its character is not safe: the digit
    bytes are seven-segment patterns, and some of them collide with the key
    characters exactly. ``0x61`` is the pattern for a ``1`` with its decimal
    point, and it is also ``'a'``, the Up key. A reader scanning for ``'a'``
    would find one inside a perfectly ordinary reading of 1.0 volts.

    So frames are extracted first - they are self-delimiting, ten bytes from a
    carriage return - and whatever is left over is echo. That way the two are
    told apart by structure rather than by value.

    Traces to: DMM-FR-026, DMM-FR-028, DMM-DD-PROTO.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._residue = bytearray()
        #: Carriage returns passed over because the ten bytes after them were
        #: not a frame - a count for diagnosing a noisy link.
        self.resynchronised = 0

    def feed(self, data: bytes) -> None:
        """Add newly received bytes."""
        self._buffer.extend(data)

    def frames(self) -> list:
        """Take every complete frame currently buffered.

        Bytes before a frame start, and any byte that cannot begin one, are
        moved to :meth:`residue` rather than discarded.
        """
        found = []
        while True:
            start = find_frame_start(self._buffer)
            if start < 0:
                self._residue.extend(self._buffer)
                self._buffer.clear()
                break
            if start > 0:
                self._residue.extend(self._buffer[:start])
                del self._buffer[:start]
            if len(self._buffer) < FRAME_LENGTH:
                break                      # a frame in progress; wait for the rest
            candidate = bytes(self._buffer[:FRAME_LENGTH])
            if frame_problem(candidate):
                # A carriage return that does not start a frame: the stream
                # was joined part-way through one. Look again from the next
                # byte rather than decode garbage.
                self._residue.append(self._buffer[0])
                del self._buffer[0]
                self.resynchronised += 1
                continue
            found.append(candidate)
            del self._buffer[:FRAME_LENGTH]
        return found

    def residue(self) -> bytes:
        """Take the bytes that were not part of a frame - the echoes.

        Call :meth:`frames` first: that is what separates the two. Extracting
        frames here as a convenience would silently discard them, because this
        method returns only the leftovers.
        """
        out = bytes(self._residue)
        self._residue.clear()
        return out

    def clear(self) -> None:
        """Forget everything held: a fresh start after discarding input."""
        self._buffer.clear()
        self._residue.clear()

    def pending(self) -> int:
        """How many bytes of an incomplete frame are held."""
        return len(self._buffer)
