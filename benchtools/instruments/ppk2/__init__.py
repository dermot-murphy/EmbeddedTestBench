"""Nordic Power Profiler Kit II (PPK2): current, charge and pulses (#342).

The PPK2 supplies a device (source mode) or sits in its supply line
(ammeter mode) and measures the current it draws, 100 000 times a second,
with eight logic inputs sampled alongside. The driver speaks the kit's own
serial protocol, as Nordic's Power Profiler app does; no Nordic package is
needed, only pyserial.

Traces to: PPK-FR-001 .. PPK-FR-012, PPK-NFR-001, PPK-ARC-001.
"""

from .constants import MAX_DURATION, MODEL, SAMPLE_PERIOD, SAMPLE_RATE, VOLTAGE_RANGE
from .measurement import Measurement, Pulse, PulseResult, find_pulses
from .ppk2 import Ppk2, find_ppk2_ports
from .protocol import Calibration, SampleDecoder, parse_metadata
from .simulator import SimulatedPpk2

__all__ = [
    "Ppk2",
    "SimulatedPpk2",
    "Measurement",
    "Pulse",
    "PulseResult",
    "Calibration",
    "SampleDecoder",
    "find_pulses",
    "find_ppk2_ports",
    "parse_metadata",
    "MODEL",
    "SAMPLE_RATE",
    "SAMPLE_PERIOD",
    "MAX_DURATION",
    "VOLTAGE_RANGE",
]
