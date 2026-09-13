"""Instrument-agnostic analysis of captured records.

Everything here operates on :class:`~benchtools.analysis.waveform.Waveform`
objects, never on a live instrument. That makes analysis deterministic,
replayable from stored CSV, and unit-testable against synthesised signals with
exactly known timing - and it means the same code serves an oscilloscope, a
logic analyser, or any other instrument that yields time-aligned records.

Traces to: ANA-ARC-001, ANA-ARC-002.
"""

from .measure import (
    EdgeCrossing,
    PeriodResult,
    SignalLevels,
    SpreadResult,
    estimate_levels,
    find_crossings,
    measure_channel_spread,
    measure_period,
    measure_pulse_width,
    measure_rise_time,
    threshold_for,
)
from .plotting import matplotlib_available, plot_waveforms
from .waveform import Waveform, WaveformPreamble, decode_curve, parse_ieee_block, waveforms_to_csv

__all__ = [
    "Waveform",
    "WaveformPreamble",
    "decode_curve",
    "parse_ieee_block",
    "waveforms_to_csv",
    "EdgeCrossing",
    "SignalLevels",
    "PeriodResult",
    "SpreadResult",
    "estimate_levels",
    "threshold_for",
    "find_crossings",
    "measure_period",
    "measure_pulse_width",
    "measure_rise_time",
    "measure_channel_spread",
    "plot_waveforms",
    "matplotlib_available",
]
