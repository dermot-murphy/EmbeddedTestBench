"""The synthetic device's frames: see the package docstring.

Traces to: SWE4-UT-PLUGINS (the synthetic test plugin).
"""

from __future__ import annotations

from typing import Any, Dict

TYPES = {1: "READING", 2: "HELLO"}


def decode_synthetic_frame(payload: bytes) -> Dict[str, Any]:
    """Decode one synthetic frame; :class:`ValueError` if it is not one."""
    data = bytes(payload)
    if len(data) != 7 or data[0] != 0xA5 or data[1] not in TYPES:
        raise ValueError("not a synthetic frame: %s" % data.hex())
    return {
        "type": TYPES[data[1]],
        "sensor_id": "%04X" % ((data[2] << 8) | data[3]),
        "frame": {"repeat": data[4]},
        "value": (data[5] << 8) | data[6],
    }


def synthetic_frame(frame_type: int, sender: int, repeat: int, value: int) -> bytes:
    """A synthetic frame's bytes, for the tests."""
    return bytes([0xA5, frame_type, sender >> 8, sender & 0xFF, repeat, value >> 8, value & 0xFF])
