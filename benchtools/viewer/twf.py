"""rf_monitor's TWF screen: a time waveform reassembled from its packets, and its spectrum (#154).

A sensor sends a time waveform (TWF) as a sequence of TWF frames, 32 samples
each, possibly permuted (S2LP-FR-082). :class:`TwfAssembler` gathers them per
sensor, buffer (TWFA or TWFB) and axis, places every sample where the
firmware's permutation says it belongs, and gives the waveform in mg against
time and its spectrum.

Where this differs from rf_monitor, the sensor firmware decided (#151):

* **The buffer** is the frame's own: param bits 9:8 say TWFB (``twfb``), where
  rf_monitor guessed, alternating A and B as sequences completed.
* **The scale** is the TWF scale, param bits 13:12 - full scale
  ``8 << twf_scale`` g - where rf_monitor used the SI scale (bits 11:10),
  which describes the SI values, not the samples.
* **The sample rate** is decoded from the frame's ODR code (``odr_hz``), which
  rf_monitor took as Hz even when bit 15 marks a rate divided by ten.

A sample no frame carried is ``None``: the plot has a gap there. For the
spectrum the gaps are filled by straight lines between their neighbours (the
ends held), a Hann window is applied, and the magnitude of each bin is
``|X(k)| * 2 / N`` in mg at ``k * ODR / N`` Hz, as rf_monitor computed it. The
transform is NumPy's when NumPy is installed, else a plain-Python one that
gives the same numbers.

Traces to: VIEW-FR-034 .. VIEW-FR-036, VIEW-DD-TWF.
"""

from __future__ import annotations

import cmath
import math
from typing import Any, Dict, List, Optional, Tuple

from ..instruments.s2lp.kepler_tables import twf_sample

__all__ = ["TwfAssembler", "spectrum", "fill_gaps", "SAMPLES_PER_PACKET"]

SAMPLES_PER_PACKET = 32
_METHODS = {0: "distance", 1: "none", 2: "polynomial"}


def fill_gaps(values: List[Optional[float]]) -> List[float]:
    """*values* with each run of ``None`` replaced by a straight line between its
    neighbours; a run at either end takes the nearest value. All ``None``: zeros."""
    known = [index for index, value in enumerate(values) if value is not None]
    if not known:
        return [0.0] * len(values)
    out = list(values)
    for index in range(known[0]):
        out[index] = values[known[0]]
    for index in range(known[-1] + 1, len(values)):
        out[index] = values[known[-1]]
    for left, right in zip(known, known[1:]):
        for index in range(left + 1, right):
            fraction = (index - left) / (right - left)
            out[index] = values[left] + (values[right] - values[left]) * fraction
    return [float(value) for value in out]


def _fft(values: List[complex]) -> List[complex]:
    """Radix-2 FFT of a power-of-two length; plain Python."""
    size = len(values)
    if size == 1:
        return list(values)
    even, odd = _fft(values[0::2]), _fft(values[1::2])
    out = [0j] * size
    for index in range(size // 2):
        twiddle = cmath.exp(-2j * math.pi * index / size) * odd[index]
        out[index] = even[index] + twiddle
        out[index + size // 2] = even[index] - twiddle
    return out


def _dft_magnitudes(values: List[float]) -> List[float]:
    """|X(k)| for k = 0 .. N/2, NumPy's rfft when available."""
    try:
        import numpy  # pylint: disable=import-outside-toplevel
    except ImportError:
        numpy = None
    if numpy is not None:
        return [float(value) for value in numpy.abs(numpy.fft.rfft(numpy.asarray(values)))]
    size = len(values)
    if size & (size - 1):
        # Not a power of two: a direct transform, slower but the same numbers.
        return [abs(sum(values[n] * cmath.exp(-2j * math.pi * k * n / size)
                        for n in range(size))) for k in range(size // 2 + 1)]
    transformed = _fft([complex(value) for value in values])
    return [abs(transformed[k]) for k in range(size // 2 + 1)]


def spectrum(values: List[Optional[float]], odr: float) -> List[Tuple[float, float]]:
    """``(Hz, mg)`` per bin of a waveform sampled at *odr*: gaps filled, Hann window,
    ``|X(k)| * 2 / N`` - rf_monitor's computation."""
    size = len(values)
    if size < 2 or odr <= 0:
        return []
    filled = fill_gaps(values)
    window = [0.5 - 0.5 * math.cos(2 * math.pi * n / (size - 1)) for n in range(size)]
    magnitudes = _dft_magnitudes([filled[n] * window[n] for n in range(size)])
    return [(round(k * odr / size, 6), round(magnitude * 2 / size, 6))
            for k, magnitude in enumerate(magnitudes)]


class _Capture:  # pylint: disable=too-many-instance-attributes
    """One waveform being gathered: a buffer, an axis, a sequence of packets."""

    def __init__(self, total: int, method: str, scale: int, odr: int, t: float) -> None:
        self.total = total
        self.method = method
        self.scale = scale
        self.odr = odr
        self.started = t
        self.updated = t
        self.frames: Dict[Tuple[int, int], List[int]] = {}

    @property
    def packets(self) -> int:
        """Packets heard, by number, whatever their version."""
        return len({packet for packet, _version in self.frames})

    @property
    def complete(self) -> bool:
        """Whether every packet has been heard."""
        return self.packets >= self.total

    def waveform(self) -> List[Optional[float]]:
        """Every sample in mg, where the permutation says it belongs; ``None`` if unheard."""
        size = self.total * SAMPLES_PER_PACKET
        values: List[Optional[float]] = [None] * size
        mg_per_count = (8 << self.scale) * 1000.0 / 32767.0
        for (packet, version), samples in sorted(self.frames.items()):
            for slot, raw in enumerate(samples):
                index = twf_sample(self.method, packet, slot, size, version)
                if 0 <= index < size:
                    values[index] = round(raw * mg_per_count, 4)
        return values


class TwfAssembler:
    """Waveforms per sensor, buffer and axis: the one being gathered and the last complete."""

    def __init__(self) -> None:
        self.current: Dict[Tuple[str, str, str], _Capture] = {}
        self.complete: Dict[Tuple[str, str, str], _Capture] = {}

    def feed(self, frame: Dict[str, Any]) -> bool:
        """Take one received frame as :class:`RfFrames` lists it; ``True`` if a TWF."""
        decoded, sensor, when = frame.get("decoded"), frame.get("sensor_id"), frame.get("t")
        if not decoded or decoded.get("type") != "TWF" or not sensor:
            return False
        param = decoded.get("param") or {}
        key = (sensor, "B" if param.get("twfb") else "A", decoded.get("axis", "?"))
        total = int(decoded.get("packet_count") or 0)
        packet = int(decoded.get("packet_number", 0))
        if total <= 0 or packet >= total:
            return False
        method = str(decoded.get("permute_method", "none"))
        capture = self.current.get(key)
        if capture is None or capture.total != total or capture.method != method or \
                (packet == 0 and capture.complete):
            capture = _Capture(total, method, int(param.get("twf_scale", 0)),
                               int(decoded.get("odr_hz") or 0), when or 0.0)
            self.current[key] = capture
        version = max(0, (decoded.get("frame") or {}).get("repeat", 0))
        # Under the polynomial each repeat carries different samples; otherwise
        # the copies are the same and the last one stands.
        capture.frames[(packet, version if method == "polynomial" else 0)] = \
            list(decoded.get("samples") or [])
        capture.updated = when or capture.updated
        if capture.complete:
            self.complete[key] = capture
        return True

    def view(self, sensor: str = "", buffer: str = "A", axis: str = "X") -> Dict[str, Any]:
        """The waveform, its spectrum and the reception figures for one buffer and axis.

        The capture being gathered is shown while it is; otherwise the last
        complete one. A buffer with nothing falls back to the other, as
        rf_monitor's did.
        """
        sensors = sorted({key[0] for key in self.current})
        chosen = sensor if sensor in sensors else (sensors[0] if sensors else "")
        axis = axis.upper() if axis.upper() in ("X", "Y", "Z") else "X"
        buffer = "B" if buffer.upper() == "B" else "A"
        capture = self.current.get((chosen, buffer, axis))
        if capture is None:
            other = "A" if buffer == "B" else "B"
            if (chosen, other, axis) in self.current:
                buffer = other
                capture = self.current[(chosen, buffer, axis)]
        if capture is None:
            return {"sensors": sensors, "sensor": chosen, "buffer": buffer, "axis": axis,
                    "capture": None}
        values = capture.waveform()
        period_ms = 1000.0 / capture.odr if capture.odr else 0.0
        received = sum(1 for value in values if value is not None)
        percent = 100.0 * capture.packets / capture.total
        signal = ("Excellent" if percent >= 99 else "Good" if percent >= 95 else
                  "Fair" if percent >= 80 else "Poor")
        return {
            "sensors": sensors, "sensor": chosen, "buffer": buffer, "axis": axis,
            "capture": {
                "complete": capture.complete, "packets": capture.packets,
                "total_packets": capture.total, "missed": capture.total - capture.packets,
                "percent": round(percent, 1), "signal": signal, "samples": len(values),
                "samples_received": received, "odr_hz": capture.odr,
                "full_scale_mg": (8 << capture.scale) * 1000, "method": capture.method,
                "duration_ms": round(period_ms * (len(values) - 1), 3),
                "resolution_hz": round(capture.odr / len(values), 6) if values else None,
                "started": capture.started, "updated": capture.updated,
            },
            # A sample no frame carried is None, so the plot has a gap there.
            "waveform": [[round(index * period_ms, 6), value]
                         for index, value in enumerate(values)],
            "spectrum": [list(point) for point in spectrum(values, capture.odr)],
        }
