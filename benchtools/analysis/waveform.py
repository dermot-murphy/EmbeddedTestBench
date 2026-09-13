"""Waveform record decoding, scaling and export.

The instrument returns a waveform as two separate things: a *preamble*
(``WFMPre?``) that describes the axes, and a *curve* (``CURVe?``) that is a
block of raw digitiser codes. This module joins them into a
:class:`Waveform` carrying real seconds and real volts.

Scaling follows the TDS3000 programmer manual exactly:

.. math::

    X_n = \\mathrm{XZEro} + \\mathrm{XINcr} \\times (n - \\mathrm{PT\\_Off})

    Y_n = \\mathrm{YZEro} + \\mathrm{YMUlt} \\times (\\mathrm{raw}_n - \\mathrm{YOFf})

where *n* is the zero-based index of the point within the full acquisition
record, not within the transferred segment - which matters whenever
``DATa:STARt`` is greater than 1.

Generic to any digitising instrument: an oscilloscope record, a logic
analyser capture or a spectrum analyser trace all arrive this way. Only the
standard library is used, so a capture works on a bare Python install.

Traces to: ANA-FR-001 .. ANA-FR-005, ANA-DD-WAVEFORM.
"""

from __future__ import annotations

import array
import csv
import math
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.errors import ProtocolError
from ..core.scpi import parse_ieee_block

__all__ = [
    "WaveformPreamble",
    "Waveform",
    "decode_curve",
    "waveforms_to_csv",
    # Re-exported from benchtools.core.scpi, where it is shared with the
    # instrument drivers that send and receive 488.2 blocks.
    "parse_ieee_block",
]


def decode_curve(payload: bytes, width: int, signed: bool = True) -> List[int]:
    """Decode raw digitiser codes from a binary curve payload.

    :param payload: Block payload, big-endian as sent by the instrument.
    :param width: Bytes per point, 1 or 2.
    :param signed: ``True`` for ``RIBinary``/``SRIbinary``, ``False`` for the
        positive-integer encodings.
    """
    if width not in (1, 2):
        raise ValueError("width must be 1 or 2, got %r" % (width,))
    if len(payload) % width:
        raise ProtocolError(
            "curve payload of %d bytes is not a whole number of %d-byte points"
            % (len(payload), width)
        )

    if width == 1:
        codes = array.array("b" if signed else "B")
        codes.frombytes(payload)
        return codes.tolist()

    codes = array.array("h" if signed else "H")
    codes.frombytes(payload)
    if array.array("h", b"\x00\x01")[0] == 1:
        pass  # already big-endian
    else:
        codes.byteswap()
    return codes.tolist()


@dataclass(frozen=True)
class WaveformPreamble:
    """Axis description returned by the ``WFMPre`` subsystem.

    :param x_increment: Seconds between points.
    :param x_zero: Time of the record origin relative to the trigger.
    :param point_offset: Record index of the trigger point.
    :param y_multiplier: Volts per digitiser code.
    :param y_zero: Vertical offset in volts.
    :param y_offset: Digitiser code corresponding to ``y_zero``.
    :param point_count: Number of points transferred.
    :param start_index: Zero-based index of the first transferred point within
        the full acquisition record.
    """

    x_increment: float
    x_zero: float
    point_offset: float
    y_multiplier: float
    y_zero: float
    y_offset: float
    point_count: int = 0
    start_index: int = 0
    x_unit: str = "s"
    y_unit: str = "V"

    def time_at(self, index: int) -> float:
        """Return the time in seconds of the *index*-th transferred point."""
        absolute = self.start_index + index
        return self.x_zero + self.x_increment * (absolute - self.point_offset)

    def volts_at(self, raw: float) -> float:
        """Convert one raw digitiser code to volts."""
        return self.y_zero + self.y_multiplier * (raw - self.y_offset)

    @property
    def sample_rate(self) -> float:
        """Sample rate in samples per second."""
        if self.x_increment <= 0.0:
            raise ProtocolError("instrument reported a non-positive XINCR")
        return 1.0 / self.x_increment


@dataclass
class Waveform:
    """A scaled acquisition record from one channel.

    :param source: Source name as reported to the instrument, e.g. ``"CH1"``.
    :param times: Time of each point in seconds, relative to the trigger.
    :param volts: Voltage of each point.
    :param raw: Raw digitiser codes, retained for traceability and re-scaling.
    :param preamble: The axis description used to produce *times* and *volts*.
    """

    source: str
    times: List[float]
    volts: List[float]
    raw: List[int] = field(default_factory=list)
    preamble: Optional[WaveformPreamble] = None
    #: Raw code at which the digitiser saturates. The TDS3000 digitiser spans
    #: roughly +/-5.1 divisions, so a code at or beyond this means the trace
    #: ran off the top or bottom of the graticule and the sample is not a
    #: faithful measurement of the input.
    full_scale_code: int = 127

    def __len__(self) -> int:
        return len(self.volts)

    def __post_init__(self) -> None:
        if len(self.times) != len(self.volts):
            raise ValueError(
                "times and volts must be the same length (%d vs %d)"
                % (len(self.times), len(self.volts))
            )

    @classmethod
    def from_codes(
        cls,
        source: str,
        codes: Sequence[int],
        preamble: WaveformPreamble,
        width: int = 1,
    ) -> "Waveform":
        """Build a waveform from already-decoded digitiser codes."""
        times = [preamble.time_at(index) for index in range(len(codes))]
        volts = [preamble.volts_at(code) for code in codes]
        return cls(
            source=source,
            times=times,
            volts=volts,
            raw=list(codes),
            preamble=preamble,
            full_scale_code=127 if width == 1 else 127 * 256,
        )

    @classmethod
    def from_payload(
        cls,
        source: str,
        payload: bytes,
        preamble: WaveformPreamble,
        width: int = 1,
        signed: bool = True,
    ) -> "Waveform":
        """Build a waveform from a curve payload whose block header is gone.

        Use this when the caller has already consumed the IEEE 488.2 header -
        as the driver does, because it reads the declared length off the wire.
        Running the header parser over a payload again is unsafe: binary sample
        data can legitimately contain the ``#`` byte (0x23) and would then be
        mistaken for a block header.
        """
        codes = decode_curve(payload, width=width, signed=signed)
        return cls.from_codes(source, codes, preamble, width=width)

    @classmethod
    def from_block(
        cls,
        source: str,
        block: bytes,
        preamble: WaveformPreamble,
        width: int = 1,
        signed: bool = True,
    ) -> "Waveform":
        """Build a waveform from a complete ``CURVe?`` response.

        *block* must still carry its IEEE 488.2 header; the payload is
        extracted using the declared length. For a payload that has already
        been de-framed use :meth:`from_payload`.
        """
        return cls.from_payload(
            source, parse_ieee_block(block), preamble, width=width, signed=signed
        )

    @classmethod
    def from_ascii(
        cls,
        source: str,
        text: bytes,
        preamble: WaveformPreamble,
    ) -> "Waveform":
        """Build a waveform from an ``ASCIi``-encoded curve response.

        The instrument returns comma-separated digitiser codes rather than a
        binary block.
        """
        payload = text.decode("ascii", errors="replace").strip()
        if payload.startswith("#"):
            payload = parse_ieee_block(text).decode("ascii", errors="replace").strip()
        codes = []
        for field in payload.split(","):
            field = field.strip()
            if not field:
                continue
            try:
                codes.append(int(float(field)))
            except ValueError as exc:
                raise ProtocolError(
                    "unparsable ASCII curve value %r" % field
                ) from exc
        return cls.from_codes(source, codes, preamble, width=1)

    # ------------------------------------------------------------------
    @property
    def duration(self) -> float:
        """Time span of the record in seconds."""
        return (self.times[-1] - self.times[0]) if len(self.times) > 1 else 0.0

    @property
    def sample_interval(self) -> float:
        """Seconds between points."""
        if self.preamble is not None:
            return self.preamble.x_increment
        if len(self.times) > 1:
            return self.times[1] - self.times[0]
        raise ProtocolError("cannot determine the sample interval of a 1-point record")

    @property
    def clipped_sample_count(self) -> int:
        """Number of samples sitting at the digitiser rail.

        A non-zero count means the trace left the graticule vertically. Level
        estimation, and therefore every threshold-based timing measurement, is
        unreliable on a clipped record: reduce volts/division or move the
        channel's position and capture again.
        """
        if not self.raw:
            return 0
        limit = self.full_scale_code
        return sum(1 for code in self.raw if code >= limit or code <= -limit)

    @property
    def is_clipped(self) -> bool:
        """``True`` when any sample is at the digitiser rail."""
        return self.clipped_sample_count > 0

    @property
    def minimum(self) -> float:
        """Most negative sample, in volts."""
        return min(self.volts)

    @property
    def maximum(self) -> float:
        """Most positive sample, in volts."""
        return max(self.volts)

    @property
    def peak_to_peak(self) -> float:
        """Peak-to-peak amplitude in volts."""
        return self.maximum - self.minimum

    @property
    def mean(self) -> float:
        """Arithmetic mean of the record, in volts."""
        return math.fsum(self.volts) / len(self.volts)

    def value_at(self, when: float) -> float:
        """Return the linearly interpolated voltage at time *when*.

        Times outside the record are clamped to its first or last sample.
        """
        if not self.times:
            raise ValueError("waveform is empty")
        if when <= self.times[0]:
            return self.volts[0]
        if when >= self.times[-1]:
            return self.volts[-1]
        step = self.sample_interval
        position = (when - self.times[0]) / step
        lower = int(position)
        upper = min(lower + 1, len(self.volts) - 1)
        fraction = position - lower
        return self.volts[lower] + (self.volts[upper] - self.volts[lower]) * fraction

    def to_csv(self, path: str, include_raw: bool = False) -> str:
        """Write the record as CSV with a ``time_s``/``volts`` header.

        :param include_raw: Also emit the raw digitiser code per point.
        :returns: The path written.
        """
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            header = ["time_s", "%s_volts" % self.source.lower()]
            if include_raw and self.raw:
                header.append("raw_code")
            writer.writerow(header)
            for index in range(len(self.volts)):
                row = ["%.12g" % self.times[index], "%.9g" % self.volts[index]]
                if include_raw and self.raw:
                    row.append(str(self.raw[index]))
                writer.writerow(row)
        return path


def waveforms_to_csv(waveforms: Dict[int, Waveform], path: str) -> str:
    """Write several channels to one CSV with a shared time column.

    All records must share a time base, which is the case whenever they come
    from the same acquisition.

    :param waveforms: Mapping of channel number to :class:`Waveform`.
    :param path: Destination file.
    :returns: The path written.
    """
    if not waveforms:
        raise ValueError("no waveforms to write")
    channels = sorted(waveforms)
    lengths = {len(waveforms[channel]) for channel in channels}
    if len(lengths) != 1:
        raise ValueError("channels have different record lengths: %s" % sorted(lengths))

    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    reference = waveforms[channels[0]]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s"] + ["ch%d_volts" % channel for channel in channels])
        for index in range(len(reference)):
            writer.writerow(
                ["%.12g" % reference.times[index]]
                + ["%.9g" % waveforms[channel].volts[index] for channel in channels]
            )
    return path
