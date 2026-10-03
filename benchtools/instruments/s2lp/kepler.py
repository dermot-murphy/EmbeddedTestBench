"""Decoding the Kepler (Kappa X) sensor's sub-GHz frames.

The sensor sends plaintext frames through an S2-LP: basic packets, a 32-bit sync
word (0xB19C0CA7 sensor to gateway), a one-byte length, a one-byte address and
a 16-bit CRC checked by the radio. What reaches the FIFO - and so what this
module decodes - is the payload.

Every layout here is the sensor firmware's, read from the reference project:
offsets and sizes from ``API_RADIO_TRANSPORT_CONTENT_TABLE`` and
``API_RADIO_TRANSPORT_CYCLIC_TABLE`` in ``config/common/api_radio_transport_cfg.h``,
encodings from the ``API_Radio_Field_Load_*`` functions in
``api/radio/api_radio_field.c``. Multi-byte integers are big-endian, except
FFT2's maximum bin amplitude, a native (little-endian) float32.

**Units are converted only where the firmware defines them**: temperature in
0.1 °C, battery in 20 mV steps. Vibration figures (RMS acceleration, velocity,
peak-to-peak), the scale code, waveform samples and FFT bins are the counts the
sensor sends. TWF and CONFIG contents are permuted by the sensor (KEP-SWE3-006)
and are reported as sent, not un-permuted.

**The layout depends on the sensor's firmware.** It is keyed on RF_CAP (byte 4);
these layouts are RF_CAP 6. A frame with another RF_CAP is still decoded, with a
warning, because V10 (RF_CAP 4) frames differ.

Traces to: S2LP-FR-070, S2LP-DD-KEPLER.
"""

from __future__ import annotations

import struct
from typing import Any, Callable, Dict, List

from .kepler_tables import (
    PCB_VERSIONS, PRODUCTS, SENSOR_PHASES, name_config, odr_hz, reset_reasons,
)

__all__ = ["decode_kepler_frame", "KeplerFrameError", "FRAME_TYPES", "RF_CAPABILITY"]

#: The frame layout this module decodes.
RF_CAPABILITY = 6

#: PL_TYPE (byte 7) to frame name, and the payload length the sensor sends.
#: RESPONSE is variable in length; the figure is its minimum.
FRAME_TYPES: Dict[int, tuple] = {
    2: ("VERSION", 83),
    3: ("ALIVE", 35),
    4: ("TWF", 100),
    5: ("CONFIG", 21),
    6: ("FFT", 97),
    7: ("FFT2", 105),
    8: ("CMD", 15),
    9: ("RESPONSE", 14),
}

#: CMD_PARAM values, from the sensor's configuration header.
CMD_PARAMS = {
    0x0001: "REQ_LORES", 0x0002: "REQ_HIRES", 0x0003: "GENERAL",
    0x8001: "ACK_SYNC_LORES", 0x8002: "ACK_SYNC_HIRES", 0x8003: "ACK_CONFIG",
    0x7F01: "NACK_SYNC_LORES", 0x7F02: "NACK_SYNC_HIRES", 0x7F03: "NACK_CONFIG",
}

#: RESPONSE_PARAM values.
RESPONSE_PARAMS = {1: "SYNC_LORES", 2: "SYNC_HIRES", 3: "CONFIG"}


class KeplerFrameError(ValueError):
    """A payload that is not a Kepler frame this module can decode."""


def _u16(data: bytes, offset: int) -> int:
    return (data[offset] << 8) | data[offset + 1]


def _s16(data: bytes, offset: int) -> int:
    value = _u16(data, offset)
    return value - 0x10000 if value & 0x8000 else value


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _text(data: bytes, start: int, size: int) -> str:
    return data[start:start + size].split(b"\x00", 1)[0].decode("ascii", errors="replace")


def _environment(data: bytes, temperature: int, battery: int) -> Dict[str, Any]:
    return {
        "temperature_c": _s16(data, temperature) / 10.0,
        "battery_mv": data[battery] * 20,
    }


def _frame_count(value: int) -> Dict[str, int]:
    """``((repeat_index + 1) << 4) | frames_per_packet`` (api_radio_llc.c)."""
    return {"repeat": (value >> 4) - 1, "frames_per_packet": value & 0x0F}


def _permute(value: int) -> Dict[str, Any]:
    method = (value >> 3) & 0x03
    return {"permute_method": {0: "distance", 1: "none", 2: "polynomial"}.get(method, method)}


def _xyz(data: bytes, offset: int, signed: bool = False) -> List[int]:
    read = _s16 if signed else _u16
    return [read(data, offset + 2 * axis) for axis in range(3)]


def _version(data: bytes) -> Dict[str, Any]:
    fields = {"frame": _frame_count(data[8]),
              "sha": _text(data, 9, 7),
              "version": _text(data, 16, 53),
              "reset_reason": _u32(data, 73),
              "reset_reasons": reset_reasons(_u32(data, 73)),
              "battery_loaded_mv": data[77] * 20,
              "pcb_version": data[78],
              "pcb": PCB_VERSIONS.get(data[78], "unknown (%d)" % data[78])
                     if data[3] == 3 else "unknown (%d)" % data[78],
              "temperature_c": _s16(data, 79) / 10.0,
              "ticks": _u16(data, 81)}
    return fields


def _alive(data: bytes) -> Dict[str, Any]:
    status = data[34]
    fields = {"frame": _frame_count(data[8])}
    fields.update(_environment(data, 9, 11))
    fields.update({
        "ticks": _u16(data, 12),
        "si_scale": data[14],
        "acc_rms": _xyz(data, 15),
        "velocity": _xyz(data, 21),
        "peak_to_peak": _xyz(data, 27),
        "ble_connected": data[33],
        "status": {"si_updated": bool(status & 0x01), "live": bool(status & 0x02),
                   "phase": (status >> 2) & 0x0F,
                   "phase_name": SENSOR_PHASES.get((status >> 2) & 0x0F, "unknown"),
                   "install_assist": bool(status & 0x80)},
    })
    if status & 0x80:
        fields["apdu"] = "INSTALL_ASSIST"
    return fields


def _twf(data: bytes) -> Dict[str, Any]:
    param = _u16(data, 13)
    fields = {"frame": _frame_count(data[9])}
    fields.update(_permute(data[8]))
    fields.update(_environment(data, 10, 12))
    fields.update({
        "param": {"raw": param, "axis": param >> 14, "twf_scale": (param >> 12) & 3,
                  "si_scale": (param >> 10) & 3, "twfb": (param >> 8) & 3,
                  "si_type": (param >> 5) & 7, "permute": (param >> 2) & 3,
                  "rescale": param & 3},
        "freq_code": _u16(data, 15),
        "odr_hz": odr_hz(_u16(data, 15)),
        "axis": "XYZ"[param >> 14] if param >> 14 < 3 else "?",
        "packet_number": _u16(data, 17),
        "packet_count": _u16(data, 19),
        "ticks": _u16(data, 21),
        "si": _xyz(data, 23),
        "samples": [_s16(data, 29 + 2 * index) for index in range(32)],
        "time_taken_us": _u32(data, 93),
        "group_id": data[97],
        "sync_attribute": _u16(data, 98),
    })
    return fields


def _config(data: bytes) -> Dict[str, Any]:
    fields = {"frame": _frame_count(data[9])}
    fields.update(_permute(data[8]))
    fields.update({"mux": data[10], "values": [_u16(data, 11 + 2 * slot) for slot in range(5)]})
    # Which parameter each slot carries depends on the permutation, and under
    # the polynomial on the frame's repeat number (kepler_tables, #151).
    fields["parameters"] = name_config(fields["mux"], fields["values"],
                                       str(fields["permute_method"]),
                                       max(0, fields["frame"]["repeat"]))
    return fields


def _fft(data: bytes) -> Dict[str, Any]:
    fields = _environment(data, 8, 10)
    fields.update({"param": _u16(data, 11), "time_taken_us": _u32(data, 13),
                   "si_acc_z": _u16(data, 17), "bins": data[19:97].hex()})
    return fields


def _fft2(data: bytes) -> Dict[str, Any]:
    fields = _environment(data, 8, 10)
    fields.update({"param": _u16(data, 11), "time_taken_us": _u32(data, 13),
                   "max_bin_amplitude": struct.unpack_from("<f", data, 17)[0],
                   "bins": data[21:105].hex()})
    return fields


def _cmd(data: bytes) -> Dict[str, Any]:
    param = _u16(data, 12)
    return {"frame": _frame_count(data[8]), "for_sensor": data[9:12].hex().upper(),
            "cmd_param": param, "cmd": CMD_PARAMS.get(param, "0x%04X" % param),
            "retry": data[14]}


def _response(data: bytes) -> Dict[str, Any]:
    """Gateway to sensor. The parameter is 16 bits at 12-13 and the payload
    starts at 14: a timer (ms for LORES, us for HIRES) and a slot, or up to ten
    {id u16, value u32} pairs for CONFIG (api_radio_transport.c, #151)."""
    param = _u16(data, 12)
    fields: Dict[str, Any] = {
        "gateway_id": data[0:3].hex().upper(), "for_sensor": data[9:12].hex().upper(),
        "response_param": param, "response": RESPONSE_PARAMS.get(param, "0x%04X" % param),
        "body": data[14:].hex()}
    if param in (1, 2) and len(data) >= 19:
        fields["timer"] = _u32(data, 14)
        fields["timer_unit"] = "ms" if param == 1 else "us"
        fields["slot"] = data[18]
    elif param == 3:
        pairs = (len(data) - 14) // 6
        fields["config"] = [{"id": _u16(data, 14 + 6 * pair), "value": _u32(data, 16 + 6 * pair)}
                            for pair in range(min(pairs, 10))]
    return fields


_DECODERS: Dict[int, Callable[[bytes], Dict[str, Any]]] = {
    2: _version, 3: _alive, 4: _twf, 5: _config, 6: _fft, 7: _fft2, 8: _cmd, 9: _response,
}


def decode_kepler_frame(payload: bytes) -> Dict[str, Any]:
    """Decode one Kepler frame payload into a dictionary.

    :raises KeplerFrameError: when the payload is too short for a header, has
        an unknown PL_TYPE, or is shorter than its type's layout. A payload
        longer than its layout is decoded, and the extra bytes are noted.
    """
    data = bytes(payload)
    if len(data) < 8:
        raise KeplerFrameError("%d byte(s) is shorter than the 8-byte header" % len(data))
    pl_type = data[7]
    if pl_type not in FRAME_TYPES:
        raise KeplerFrameError("PL_TYPE %d is not a Kepler frame type" % pl_type)
    name, size = FRAME_TYPES[pl_type]
    if len(data) < size:
        raise KeplerFrameError(
            "a %s frame is %d bytes; this payload is %d" % (name, size, len(data)))

    decoded: Dict[str, Any] = {
        "type": name,
        "pl_type": pl_type,
        "sensor_id": data[0:3].hex().upper(),
        "product_id": data[3],
        "product": PRODUCTS.get(data[3], "unknown (%d)" % data[3]),
        "rf_capability": data[4],
        "type_capability": data[5] >> 3,
        "hw_capability": data[5] & 0x07,
        "fw_capability": data[6],
    }
    decoded.update(_DECODERS[pl_type](data))
    notes = []
    if data[4] != RF_CAPABILITY and pl_type != 9:
        notes.append("RF_CAP %d; these layouts are for RF_CAP %d" % (data[4], RF_CAPABILITY))
    if len(data) > size and pl_type != 9:
        notes.append("%d byte(s) beyond the %s layout" % (len(data) - size, name))
    if notes:
        decoded["warnings"] = notes
    return decoded
