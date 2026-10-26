"""Names and arithmetic behind the Kepler frames: CONFIG parameters, permutation (#151).

:mod:`.kepler` decodes the bytes. This module says what they mean where a
number alone does not: which configuration parameter a CONFIG slot carries
and in what unit, what a reset-reason bit or a PCB code is called, how a
waveform's samples were permuted on the air, and what ODR a TWF frame's
frequency code stands for.

Ported from the Kepler project's rf_monitor (``tools/test_bench/test_bench.py``
here), and checked against the sensor firmware at V11.00.0000-96-g25a54b97a
(``software/source`` of the reference project), which is the authority:

* the 60 configuration parameters in order, 5 to a CONFIG frame, 12 frames,
  from ``APP_Normal_ParamsSaveToRadio`` (``app_normal.c``). rf_monitor named
  parameters 5 and 6 "Transit Wait Time" and "Transit Wake Time"; the firmware
  sends TRANSIT_MAX_TIME and TRANSIT_WAIT_TIME, and those are used here;
* which parameter a slot carries under each permutation method, from
  ``api_radio_field.c``: none ``mux*5 + slot``, distance ``mux + slot*12``,
  polynomial ``Permute_PolyAnySize(60, mux*5 + slot, repeat)``;
* the polynomial itself and its constants, from ``utils/permute.c``;
* a waveform's sample order, from ``API_Vibration_PacketGet``: none
  ``packet*32 + slot``, distance ``packet + slot*(N/32)``, polynomial
  ``Permute_Poly(N, packet*32 + slot, repeat)`` - so under the polynomial
  method the repeats of one packet carry different samples;
* the compressed ODR code, from ``API_Vibration_CompressOdr``: an ODR above
  30 000 Hz is sent divided by 10 with bit 15 set.

Traces to: S2LP-FR-081 .. S2LP-FR-083, S2LP-DD-KEPLER.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "CONFIG_PARAMETERS", "CONFIG_FRAMES", "CONFIG_PER_FRAME", "permute_poly",
    "permute_poly_any_size", "config_parameter", "name_config", "twf_sample",
    "odr_hz", "reset_reasons", "PCB_VERSIONS", "SENSOR_PHASES", "PRODUCTS",
]

#: CONFIG frames in a configuration, and parameters in each.
CONFIG_FRAMES = 12
CONFIG_PER_FRAME = 5

_SCALING = {0: "AUTO", 1: "LOWEST", 2: "LOW", 3: "MEDIUM", 4: "HIGHEST"}
_TRIGGER = {0: "ALWAYS", 1: "ACCWAVE", 2: "ACCRMS", 3: "VELRSS", 4: "PK2PK"}
_PERMUTE = {0: "Distance", 1: "None", 2: "Polynomial", 3: "Reserved"}
_SHORT_CAPTURE = {0: "RMS", 1: "FFT"}

#: Each configuration parameter in the order the firmware sends them:
#: (name, unit, enumeration or None). Index is the parameter number, 0..59.
CONFIG_PARAMETERS = [
    ("Seek Machine On", "s", None), ("Delay Confirm", "s", None),
    ("Confirm Machine", "s", None), ("Transmit TWF", "s", None), ("Return Idle", "s", None),
    ("Transit Max Time", "s", None), ("Transit Wait Time", "s", None),
    ("TWFA ODR", "Hz", None), ("TWFA X Sampling", "", None), ("TWFA Y Sampling", "", None),
    ("TWFA Z Sampling", "", None), ("TWFB ODR", "Hz", None), ("TWFB X Sampling", "", None),
    ("TWFB Y Sampling", "", None), ("TWFB Z Sampling", "", None),
    ("TWFA Scaling", "", _SCALING), ("Machine ACC Threshold", "", None),
    ("Machine Peaks Threshold", "mg", None), ("Machine ACC Detect", "", None),
    ("Wakeup Idle Count", "", None),
    ("Sample Delay Count", "", None), ("Machine ON Confirm Count", "", None),
    ("Machine Pk2Pk Threshold", "", None), ("Post Sample Interval", "s", None),
    ("Battery Sample Delay", "ms", None),
    ("Machine VEL Threshold", "mm/s", None), ("Trigger Method", "", _TRIGGER),
    ("RMS Min Frequency", "Hz", None), ("TWFA Enable", "", "enable"),
    ("TWFB Enable", "", "enable"),
    ("TWFB Samples", "", None), ("TWFA Samples", "", None), ("RMS ODR", "Hz", None),
    ("RMS Samples", "", None), ("TWFA X Enable", "", "enable"),
    ("TWFA Y Enable", "", "enable"), ("TWFA Z Enable", "", "enable"),
    ("TWFB X Enable", "", "enable"), ("TWFB Y Enable", "", "enable"),
    ("TWFB Z Enable", "", "enable"),
    ("Alive Period", "s", None), ("FFT Enable", "", "enable"),
    ("FFT3 Axis Enable", "", None), ("FFT3 First Bin", "", None), ("FFT3 Last Bin", "", None),
    ("Sync Enable", "", "enable"), ("Sync Retry", "", None), ("Sync Max Wait", "x10 ms", None),
    ("DC Offset Enable", "", "enable"), ("Preamble Length", "pairs", None),
    ("Ignore Duration", "s", None), ("Frames Per Packet", "frames", None),
    ("TWFB Scaling", "", _SCALING), ("Permute Method", "", _PERMUTE), ("FFT ODR", "Hz", None),
    ("FFT Samples", "", None), ("FFT Scaling", "", _SCALING), ("Listen Enable", "", "enable"),
    ("Short Capture", "", _SHORT_CAPTURE), ("FFT Machine Off Count", "", {0: "Always"}),
]

#: PCB version byte (VERSION frame) for product 3.
PCB_VERSIONS = {0: "V2", 1: "V3", 2: "V4", 3: "V4X", 4: "V5"}

#: Product ID byte.
PRODUCTS = {0: "Kappa GEN1", 1: "Tau GEN1", 2: "Chi GEN1", 3: "Kappa GEN2", 4: "Tau GEN2",
            5: "Chi GEN2", 6: "Tempus"}

#: ALIVE status phase, bits 5:2.
SENSOR_PHASES = {0: "Init", 1: "Peaks", 2: "Detect", 3: "Delay", 4: "Confirm",
                 5: "Transmit", 6: "Wait", 7: "Test", 8: "Transit"}

#: nRF52840 POWER.RESETREAS bits.
_RESET_BITS = {0: "Reset pin", 1: "Watchdog", 2: "Soft reset", 3: "CPU lockup",
               16: "Wakeup from System OFF by GPIO", 17: "Wakeup from System OFF by LPCOMP",
               18: "Wakeup from System OFF by debug interface", 19: "Wakeup from System OFF by NFC",
               20: "Wakeup from System OFF by VBUS"}

_POLY_A0 = (1735, 1730, 1729, 1733, 1731, 1743, 1734, 1736)
_POLY_A1 = (5059, 5077, 6151, 6607, 5051, 8179, 4093, 8081)
_POLY_A2 = 2
_POLY_A3 = 6
_MAX_SEQUENCE = 16384

#: Permute Control bits 4:3 and TWF param bits 3:2, by name.
METHOD_DISTANCE, METHOD_NONE, METHOD_POLY = "distance", "none", "polynomial"


def permute_poly(size: int, index: int, version: int = 0) -> int:
    """``Permute_Poly``: the sample that slot *index* of a *size* sequence carries.

    *size* is a power of two; *version* (0..7) selects the constants. Out of
    range, the firmware returns *index* unchanged, and so does this.
    """
    if version >= len(_POLY_A0) or index >= size:
        return index
    mask = size - 1
    power = index
    result = (_POLY_A1[version] * power + _POLY_A0[version]) & mask
    power = (power * index) & mask
    result += _POLY_A2 * power
    power = (power * index) & mask
    result += _POLY_A3 * power
    return result & mask


def permute_poly_any_size(size: int, index: int, version: int = 0) -> Optional[int]:
    """``Permute_PolyAnySize``: round up to a power of two and walk the cycle
    until the value is inside the sequence; ``None`` where the firmware fails."""
    if index >= size or version >= len(_POLY_A0):
        return None
    rounded = 1
    while rounded < size:
        rounded *= 2
    if rounded > _MAX_SEQUENCE:
        return None
    candidate = index
    for _ in range(rounded):
        candidate = permute_poly(rounded, candidate, version)
        if candidate < size:
            return candidate
    return None


def config_parameter(mux: int, slot: int, method: str, repeat: int) -> Optional[int]:
    """Which parameter (0..59) slot *slot* of CONFIG frame *mux* carries.

    *repeat* is the frame's 0-based repeat number, the polynomial's version.
    ``None`` when it cannot be known - the firmware would not have sent it.
    """
    total = CONFIG_FRAMES * CONFIG_PER_FRAME
    linear = mux * CONFIG_PER_FRAME + slot
    if not 0 <= linear < total:
        return None
    if method == METHOD_NONE:
        return linear
    if method == METHOD_DISTANCE:
        return mux + slot * CONFIG_FRAMES
    if method == METHOD_POLY:
        return permute_poly_any_size(total, linear, repeat)
    return None


def _show(value: int, kind: Any) -> Any:
    if kind == "enable":
        return "Enabled" if value else "Disabled"
    if isinstance(kind, dict):
        return kind.get(value, value)
    return value


def name_config(mux: int, values: List[int], method: str, repeat: int) -> List[Dict[str, Any]]:
    """Each of a CONFIG frame's five values with its parameter's number, name and unit."""
    named = []
    for slot, value in enumerate(values):
        index = config_parameter(mux, slot, method, repeat)
        if index is None:
            named.append({"slot": slot, "parameter": None, "name": None, "value": value,
                          "unit": "", "shown": value})
            continue
        name, unit, kind = CONFIG_PARAMETERS[index]
        named.append({"slot": slot, "parameter": index, "name": name, "value": value,
                      "unit": unit, "shown": _show(value, kind)})
    return named


def twf_sample(method: str, packet: int, slot: int, total: int, repeat: int = 0) -> int:
    """The waveform sample slot *slot* of packet *packet* carries, of *total*.

    *total* is the axis's sample count, packets of 32. Under the polynomial
    method *repeat* is the frame's 0-based repeat number.
    """
    linear = packet * 32 + slot
    if method == METHOD_DISTANCE:
        return packet + slot * (total // 32)
    if method == METHOD_POLY:
        return permute_poly(total, linear, repeat)
    return linear


def odr_hz(code: int) -> int:
    """The output data rate a TWF frame's frequency code stands for."""
    return (code & 0x7FFF) * 10 if code & 0x8000 else code


def reset_reasons(value: int) -> List[str]:
    """The names of the bits set in a VERSION frame's reset reason."""
    names = [name for bit, name in sorted(_RESET_BITS.items()) if value & (1 << bit)]
    unknown = value & ~sum(1 << bit for bit in _RESET_BITS)
    if unknown:
        names.append("unknown bits 0x%08X" % unknown)
    return names
