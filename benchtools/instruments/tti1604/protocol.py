"""Decoding a TTi 1604 measurement frame.

This module is pure: it turns ten bytes into a :class:`Reading` and knows
nothing about serial ports. That separation is deliberate - frame decoding is
where a wrong number comes from, and it should be testable without a meter,
a port, or a simulator.

Traces to: DMM-FR-010 .. DMM-FR-026, DMM-DD-PROTO.
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
)

__all__ = [
    "Reading",
    "FrameAssembler",
    "decode",
    "find_frame_start",
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


def decode(frame: bytes) -> Reading:
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

    value = None  # type: Optional[float]
    if not overrange:
        try:
            value = float(text) * scale
        except ValueError:
            value = None

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

    Traces to: DMM-FR-027 .. DMM-FR-032, DMM-DD-PROTO.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._residue = bytearray()

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
            found.append(bytes(self._buffer[:FRAME_LENGTH]))
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

    def pending(self) -> int:
        """How many bytes of an incomplete frame are held."""
        return len(self._buffer)
