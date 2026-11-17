"""The Power Profiler Kit II's serial protocol, as Nordic's own software uses it.

The PPK2 is a USB CDC device. The host sends one command per write: an opcode
byte and its arguments. The kit answers only ``GET_METADATA``, with text; while
sampling it streams one 32-bit little-endian word per sample, 100 000 a second.

Every value here was read from Nordic's Power Profiler app,
``NordicSemiconductor/pc-nrfconnect-ppk`` (``src/constants.ts``,
``src/device/serialDevice.ts``, ``src/device/abstractDevice.ts`` and
``src/actions/deviceActions.ts``), on 2026-11-14 (#342), and checked against
the bench's kit where it could be. ``docs/ppk2/PPK2_Notes.md`` gives the
protocol command by command.

Traces to: PPK-FR-001, PPK-FR-002, PPK-DD-CONST.
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "MANUFACTURER",
    "MODEL",
    "USB_VENDOR_ID",
    "USB_PRODUCT_ID",
    "BAUDRATE",
    "DEFAULT_TIMEOUT",
    "SAMPLE_RATE",
    "SAMPLE_PERIOD",
    "SAMPLE_BYTES",
    "CMD_TRIGGER_SET",
    "CMD_AVERAGE_START",
    "CMD_AVERAGE_STOP",
    "CMD_DEVICE_RUNNING_SET",
    "CMD_REGULATOR_SET",
    "CMD_SET_POWER_MODE",
    "CMD_GET_METADATA",
    "MODE_AMMETER",
    "MODE_SOURCE",
    "MODES",
    "MODE_NAMES",
    "VOLTAGE_RANGE",
    "METADATA_END",
    "METADATA_TIMEOUT",
    "ADC_MULT",
    "ADC_BITS",
    "RANGE_SHIFT",
    "RANGE_MASK",
    "COUNTER_SHIFT",
    "COUNTER_MASK",
    "LOGIC_SHIFT",
    "LOGIC_MASK",
    "RANGES",
    "DEFAULT_MODIFIERS",
    "SPIKE_ALPHA",
    "SPIKE_ALPHA_TOP",
    "SPIKE_SAMPLES",
    "LINES",
    "MAX_DURATION",
    "STOP_SETTLE",
    "REENUMERATE_WAIT",
]

#: Who makes it.
MANUFACTURER = "Nordic Semiconductor"

#: The model name ``identify()`` reports.
MODEL = "Power Profiler Kit II"

#: The PPK2's USB identity (Windows names its port "nRF Connect USB CDC ACM").
USB_VENDOR_ID = 0x1915
USB_PRODUCT_ID = 0xC00A

#: Line rate Nordic's app opens the port at. A CDC port ignores it; it is
#: given so the port opens the same way.
BAUDRATE = 115200

#: Seconds to wait for a reply when the bench file gives no timeout.
DEFAULT_TIMEOUT = 5.0

#: Samples a second while sampling: one every 10 microseconds.
SAMPLE_RATE = 100000

#: Seconds between samples.
SAMPLE_PERIOD = 1.0 / SAMPLE_RATE

#: Bytes per streamed sample.
SAMPLE_BYTES = 4

# Opcodes. Nordic's app sends the ones below; the rest of its table is not
# used by this driver.
CMD_TRIGGER_SET = 0x01
CMD_AVERAGE_START = 0x06
CMD_AVERAGE_STOP = 0x07
CMD_DEVICE_RUNNING_SET = 0x0C
CMD_REGULATOR_SET = 0x0D
CMD_SET_POWER_MODE = 0x11
CMD_GET_METADATA = 0x19

#: ``SET_POWER_MODE`` arguments, and the metadata's ``mode``. Ammeter mode
#: measures a current an outside supply drives through the kit; source mode
#: is the kit's own supply, a source-measure unit.
MODE_AMMETER = 1
MODE_SOURCE = 2

#: Mode names a caller gives, to the argument the kit takes.
MODES: Dict[str, int] = {"ammeter": MODE_AMMETER, "source": MODE_SOURCE}

#: The argument the kit takes, to its name.
MODE_NAMES: Dict[int, str] = {value: name for name, value in MODES.items()}

#: Volts the kit's regulator can be set to: ``vddRange`` in Nordic's app,
#: 800 to 5000 mV.
VOLTAGE_RANGE: Tuple[float, float] = (0.8, 5.0)

#: The metadata text ends with this line.
METADATA_END = b"END"

#: Seconds to wait for the whole metadata text.
METADATA_TIMEOUT = 3.0

#: Volts per ADC count before the range's resistor: ``adcMult``.
ADC_MULT = 1.8 / 163840

# A streamed sample, bit by bit: ADC 14 bits at 0 (counts of 4), the current
# range 3 bits at 14, a sample counter 6 bits at 18, the eight logic inputs at
# 24 (``MEAS_ADC``, ``MEAS_RANGE``, ``MEAS_COUNTER``, ``MEAS_LOGIC``).
ADC_BITS = 0x3FFF
RANGE_SHIFT = 14
RANGE_MASK = 0x7
COUNTER_SHIFT = 18
COUNTER_MASK = 0x3F
LOGIC_SHIFT = 24
LOGIC_MASK = 0xFF

#: Current ranges the kit switches between by itself, 0 the most sensitive.
RANGES = 5

#: The calibration Nordic's app starts from, replaced by each value the kit's
#: metadata gives: per range, the shunt ``r``, gain slope ``gs``, gain
#: intercept ``gi``, offset ``o``, supply slope ``s``, supply intercept ``i``
#: and user gain ``ug``.
DEFAULT_MODIFIERS: Dict[str, Tuple[float, ...]] = {
    "r": (1031.64, 101.65, 10.15, 0.94, 0.043),
    "gs": (1.0, 1.0, 1.0, 1.0, 1.0),
    "gi": (1.0, 1.0, 1.0, 1.0, 1.0),
    "o": (0.0, 0.0, 0.0, 0.0, 0.0),
    "s": (0.0, 0.0, 0.0, 0.0, 0.0),
    "i": (0.0, 0.0, 0.0, 0.0, 0.0),
    "ug": (1.0, 1.0, 1.0, 1.0, 1.0),
}

# The spike filter Nordic's app applies after the kit changes range: for
# ``SPIKE_SAMPLES`` samples a rolling average replaces the reading, with
# weight ``SPIKE_ALPHA`` (``SPIKE_ALPHA_TOP`` in the top range).
SPIKE_ALPHA = 0.18
SPIKE_ALPHA_TOP = 0.06
SPIKE_SAMPLES = 3

#: The logic inputs, D0 to D7.
LINES = 8

#: The longest measurement, in seconds. Every sample is kept, nine bytes
#: each (the current and the logic inputs), so two minutes is about 108 MB.
MAX_DURATION = 120.0

#: Seconds to let the stream drain after ``AVERAGE_STOP`` before its last
#: samples are thrown away.
STOP_SETTLE = 0.05

#: Seconds to wait for a kit that is off USB. Closing its port takes the
#: bench kit off USB for about 0.7 s while it enumerates again; its settings
#: are kept (seen 2026-11-14, #342).
REENUMERATE_WAIT = 3.0
