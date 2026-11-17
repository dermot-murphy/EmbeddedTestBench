"""The magnitude spectrum of a sampled waveform that may have gaps (#154, #303).

A waveform received over the air can lack samples: a packet lost leaves a run
of ``None``. :func:`spectrum` fills each gap with a straight line between its
neighbours (the ends held), applies a Hann window and gives the magnitude of
each bin, ``|X(k)| * 2 / N``, at ``k * rate / N`` - the computation of the
Kepler project's rf_monitor, which a device plugin's waveform panel uses. The
transform is NumPy's when NumPy is installed, else a plain-Python one that
gives the same numbers.

This module was part of the viewer's TWF screen; the device-specific part, how
a waveform is reassembled from its frames, moved into the device's plugin
(#303).

Traces to: VIEW-FR-036, VIEW-DD-TWF.
"""

from __future__ import annotations

import cmath
import math
from typing import List, Optional, Tuple

__all__ = ["fill_gaps", "spectrum"]


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


def spectrum(values: List[Optional[float]], rate: float) -> List[Tuple[float, float]]:
    """``(Hz, magnitude)`` per bin of a waveform sampled at *rate* Hz: gaps
    filled, Hann window, ``|X(k)| * 2 / N`` - rf_monitor's computation. The
    magnitude is in the waveform's own unit."""
    size = len(values)
    if size < 2 or rate <= 0:
        return []
    filled = fill_gaps(values)
    window = [0.5 - 0.5 * math.cos(2 * math.pi * n / (size - 1)) for n in range(size)]
    magnitudes = _dft_magnitudes([filled[n] * window[n] for n in range(size)])
    return [(round(k * rate / size, 6), round(magnitude * 2 / size, 6))
            for k, magnitude in enumerate(magnitudes)]
