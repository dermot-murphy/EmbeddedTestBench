"""Bench test tooling: instrument drivers, analysis, and a test runner.

Layout
------
``benchtools.core``
    Instrument-agnostic foundations: the transport layer (VXI-11, raw socket,
    PyVISA, in-process simulator), SCPI plumbing, validation and the simulator
    harness. Nothing here knows about any particular instrument.
``benchtools.analysis``
    Analysis of captured records: waveform scaling and export, level and edge
    detection, period statistics, N-channel timing spread, plotting.
``benchtools.instruments``
    One subpackage per instrument. Currently
    :mod:`benchtools.instruments.tek3014b` (oscilloscope) and
    :mod:`benchtools.instruments.generic` (anything answering ``*IDN?``).
``benchtools.runner``
    The bench test runner: declarative test specifications executed against a
    bench of instruments, producing pass/fail reports.

No VISA installation is required anywhere: VXI-11 is implemented directly on
the standard library, so the package has no mandatory third-party dependencies.

Traces to: CORE-ARC-001, ANA-ARC-001, INST-ARC-001, RUN-ARC-001.
"""

__version__ = "4.0.0"

__all__ = ["__version__", "core", "analysis", "instruments", "runner"]
