"""The ``ps3000a`` SDK, reached through :mod:`ctypes`.

The PicoScope is not a message-based instrument: there is no command text on
a wire, only C calls into Pico Technology's driver library. This module is the
seam. :class:`Ps3000aSdk` turns each call the driver needs into a Python
method with Python types, and turns a non-zero ``PICO_STATUS`` into an
exception. :class:`~.simulator.SimulatedPs3000a` offers the same methods, so
the driver above it cannot tell which one it has.

No Pico Python package is needed. The library comes with PicoScope 7 or the
PicoSDK; :func:`find_library` looks in the usual places, and a bench file can
name the folder (``sdk_path``).

Traces to: PSCOPE-FR-001, PSCOPE-FR-002, PSCOPE-NFR-001, PSCOPE-DD-SDK.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from ...core.errors import ConnectionFailedError, InstrumentError, OptionalDependencyError
from .constants import DIGITAL_PORTS, POWER_STATUSES, status_text

__all__ = ["Ps3000aSdk", "find_library", "check", "BlockData"]

_c16, _c32, _u32, _f32 = ctypes.c_int16, ctypes.c_int32, ctypes.c_uint32, ctypes.c_float

#: Where the library is looked for, after ``sdk_path`` and ``PICOSDK_PATH``.
_WINDOWS_FOLDERS = (
    r"C:\Program Files\Pico Technology\SDK\lib",
    r"C:\Program Files\Pico Technology\PicoScope*",
)


class BlockData:  # pylint: disable=too-few-public-methods
    """Raw codes from one block capture, before any scaling.

    :param analog: Channel index (A = 0) to signed ADC codes.
    :param digital: Port number (0 or 1) to codes; the low 8 bits are the
        port's bits, bit 0 being D0 (or D8).
    :param overflow: Bit *n* set when channel index *n* went over range.
    """

    def __init__(self, analog: Dict[int, List[int]], digital: Dict[int, List[int]],
                 overflow: int) -> None:
        self.analog = analog
        self.digital = digital
        self.overflow = overflow


def check(status: int, what: str) -> None:
    """Raise :class:`InstrumentError` unless *status* is ``PICO_OK``."""
    if status != 0:
        raise InstrumentError("%s failed: status %s" % (what, status_text(status)),
                              events=[(status, what)])


def _candidates(sdk_path: Optional[str]) -> List[str]:
    """Files that might be the library, in the order to try them."""
    name = "ps3000a.dll" if sys.platform == "win32" else (
        "libps3000a.dylib" if sys.platform == "darwin" else "libps3000a.so")
    folders: List[str] = []
    for folder in (sdk_path, os.environ.get("PICOSDK_PATH")):
        if folder:
            folders.append(folder)
            folders.append(os.path.join(folder, "lib"))
    if sys.platform == "win32":
        for pattern in _WINDOWS_FOLDERS:
            folders.extend(sorted(glob.glob(pattern)))
    else:
        folders.extend(("/opt/picoscope/lib", "/usr/local/lib",
                        "/Library/Frameworks/PicoSDK.framework/Libraries/libps3000a"))
    found = [os.path.join(folder, name) for folder in folders
             if os.path.isfile(os.path.join(folder, name))]
    system = ctypes.util.find_library("ps3000a")
    if system:
        found.append(system)
    return found


def find_library(sdk_path: Optional[str] = None) -> str:
    """Return the path of the ``ps3000a`` library.

    :raises OptionalDependencyError: when it is nowhere to be found.
    """
    found = _candidates(sdk_path)
    if not found:
        raise OptionalDependencyError(
            "the PicoScope ps3000a library was not found. Install PicoScope 7 or "
            "the PicoSDK, or name its folder with sdk_path or PICOSDK_PATH"
        )
    return found[0]


class Ps3000aSdk:
    """One open PicoScope 3000A/3000D unit, through the C library.

    :param serial: Open this serial number; ``None`` opens the first unit.
    :param sdk_path: Folder holding the library.
    :param library: An already-loaded library, for tests.
    """

    def __init__(self, serial: Optional[str] = None, sdk_path: Optional[str] = None,
                 library=None) -> None:
        self._serial = serial or None
        self._sdk_path = sdk_path
        self._lib = library
        self._handle = _c16(0)
        #: ctypes buffers kept alive between SetDataBuffer and GetValues.
        self._buffers: List[object] = []

    # ------------------------------------------------------------------
    def _load(self):
        if self._lib is None:
            path = find_library(self._sdk_path)
            folder = os.path.dirname(path)
            if folder and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(folder)  # its own dependencies live beside it
            loader = ctypes.WinDLL if sys.platform == "win32" else ctypes.CDLL
            self._lib = loader(path)
        return self._lib

    @property
    def is_open(self) -> bool:
        """``True`` while a unit is open."""
        return self._handle.value > 0

    def open(self) -> None:
        """Open the unit, confirming the power source if it asks."""
        lib = self._load()
        serial = self._serial.encode("ascii") if self._serial else None
        status = lib.ps3000aOpenUnit(ctypes.byref(self._handle), serial)
        if status in POWER_STATUSES and self._handle.value > 0:
            status = lib.ps3000aChangePowerSource(self._handle, _u32(status))
        if status != 0 or self._handle.value <= 0:
            self._handle = _c16(0)
            raise ConnectionFailedError(
                "could not open PicoScope%s: status %s"
                % (" " + self._serial if self._serial else "", status_text(status))
            )

    def close(self) -> None:
        """Close the unit. Never raises."""
        if self.is_open and self._lib is not None:
            try:
                self._lib.ps3000aStop(self._handle)
            finally:
                self._lib.ps3000aCloseUnit(self._handle)
        self._handle = _c16(0)
        self._buffers = []

    # ------------------------------------------------------------------
    def unit_info(self, key: int) -> str:
        """``ps3000aGetUnitInfo`` for *key*; ``""`` when the unit has none."""
        text = ctypes.create_string_buffer(80)
        length = _c16()
        status = self._lib.ps3000aGetUnitInfo(self._handle, text, _c16(80),
                                              ctypes.byref(length), _u32(key))
        return text.value.decode("ascii", errors="replace") if status == 0 else ""

    def maximum_value(self) -> int:
        """The ADC code at positive full scale."""
        value = _c16()
        check(self._lib.ps3000aMaximumValue(self._handle, ctypes.byref(value)),
              "ps3000aMaximumValue")
        return value.value

    def analogue_offset_limits(self, range_index: int, coupling: int) -> Tuple[float, float]:
        """``(lowest, highest)`` analogue offset in volts for a range."""
        high, low = _f32(), _f32()
        check(self._lib.ps3000aGetAnalogueOffset(self._handle, range_index, coupling,
                                                 ctypes.byref(high), ctypes.byref(low)),
              "ps3000aGetAnalogueOffset")
        return low.value, high.value

    def set_channel(self, index: int, enabled: bool, coupling: int, range_index: int,
                    offset_v: float) -> None:
        """``ps3000aSetChannel``."""
        check(self._lib.ps3000aSetChannel(self._handle, index, int(enabled), coupling,
                                          range_index, _f32(offset_v)),
              "ps3000aSetChannel(%s)" % "ABCD"[index])

    def set_digital_port(self, port: int, enabled: bool, level: int) -> None:
        """``ps3000aSetDigitalPort``; *level* is -32767..32767 for -5..5 V."""
        check(self._lib.ps3000aSetDigitalPort(self._handle, DIGITAL_PORTS[port],
                                              int(enabled), _c16(level)),
              "ps3000aSetDigitalPort(%d)" % port)

    def timebase(self, timebase: int, samples: int) -> Tuple[float, int]:
        """``(interval in seconds, most samples)`` for *timebase* as set up now."""
        interval_ns, most = _f32(), _c32()
        check(self._lib.ps3000aGetTimebase2(self._handle, _u32(timebase), _c32(samples),
                                            ctypes.byref(interval_ns), _c16(1),
                                            ctypes.byref(most), _u32(0)),
              "ps3000aGetTimebase2(%d)" % timebase)
        return interval_ns.value * 1e-9, most.value

    def set_simple_trigger(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, enabled: bool, source: int, threshold: int,
            direction: int, delay: int, auto_ms: int) -> None:
        """``ps3000aSetSimpleTrigger``; *threshold* in ADC codes."""
        check(self._lib.ps3000aSetSimpleTrigger(self._handle, _c16(int(enabled)), source,
                                                _c16(threshold), direction, _u32(delay),
                                                _c16(auto_ms)),
              "ps3000aSetSimpleTrigger")

    def set_digital_trigger(self, directions: Sequence[Tuple[int, int]], auto_ms: int) -> None:
        """Trigger on digital bits only: each ``(bit, direction code)`` must hold."""

        class Direction(ctypes.Structure):  # pylint: disable=too-few-public-methods
            """``PS3000A_DIGITAL_CHANNEL_DIRECTIONS``."""
            _fields_ = [("channel", _c32), ("direction", _c32)]

        class Conditions(ctypes.Structure):  # pylint: disable=too-few-public-methods
            """``PS3000A_TRIGGER_CONDITIONS_V2``: 1 is TRUE, 0 DON'T CARE."""
            _fields_ = [(name, _c32) for name in (
                "channelA", "channelB", "channelC", "channelD",
                "external", "aux", "pulseWidthQualifier", "digital")]

        lib = self._lib
        # Clear any analogue trigger first, so only the digital condition counts.
        check(lib.ps3000aSetSimpleTrigger(self._handle, _c16(0), 0, _c16(0), 0, _u32(0),
                                          _c16(0)), "ps3000aSetSimpleTrigger(off)")
        conditions = Conditions(digital=1)
        check(lib.ps3000aSetTriggerChannelConditionsV2(self._handle, ctypes.byref(conditions),
                                                       _c16(1)),
              "ps3000aSetTriggerChannelConditionsV2")
        array = (Direction * len(directions))(*[Direction(bit, code)
                                                for bit, code in directions])
        check(lib.ps3000aSetTriggerDigitalPortProperties(self._handle, array,
                                                         _c16(len(directions))),
              "ps3000aSetTriggerDigitalPortProperties")
        check(lib.ps3000aSetTriggerChannelProperties(self._handle, None, _c16(0), _c16(0),
                                                     _c32(auto_ms)),
              "ps3000aSetTriggerChannelProperties")

    def run_block(self, pre: int, post: int, timebase: int) -> None:
        """``ps3000aRunBlock``, polled with :meth:`is_ready`."""
        indisposed = _c32()
        check(self._lib.ps3000aRunBlock(self._handle, _c32(pre), _c32(post), _u32(timebase),
                                        _c16(1), ctypes.byref(indisposed), _u32(0),
                                        None, None),
              "ps3000aRunBlock")

    def is_ready(self) -> bool:
        """``True`` once the block is captured."""
        ready = _c16(0)
        check(self._lib.ps3000aIsReady(self._handle, ctypes.byref(ready)), "ps3000aIsReady")
        return bool(ready.value)

    def stop(self) -> None:
        """``ps3000aStop``."""
        check(self._lib.ps3000aStop(self._handle), "ps3000aStop")

    def get_values(self, samples: int, channels: Sequence[int],
                   ports: Sequence[int]) -> BlockData:
        """Fetch the codes of a finished block for *channels* and *ports*."""
        lib = self._lib
        self._buffers = []
        analog: Dict[int, object] = {}
        digital: Dict[int, object] = {}
        for index in channels:
            buffer = (_c16 * samples)()
            check(lib.ps3000aSetDataBuffer(self._handle, index, buffer, _c32(samples),
                                           _u32(0), 0), "ps3000aSetDataBuffer")
            analog[index] = buffer
        for port in ports:
            buffer = (_c16 * samples)()
            check(lib.ps3000aSetDataBuffer(self._handle, DIGITAL_PORTS[port], buffer,
                                           _c32(samples), _u32(0), 0),
                  "ps3000aSetDataBuffer(port %d)" % port)
            digital[port] = buffer
        self._buffers = list(analog.values()) + list(digital.values())
        got, overflow = _u32(samples), _c16(0)
        check(lib.ps3000aGetValues(self._handle, _u32(0), ctypes.byref(got), _u32(1), 0,
                                   _u32(0), ctypes.byref(overflow)), "ps3000aGetValues")
        count = got.value
        return BlockData(
            {index: list(buffer[:count]) for index, buffer in analog.items()},
            {port: [code & 0xFF for code in buffer[:count]] for port, buffer in digital.items()},
            overflow.value,
        )

    def set_siggen(self, offset_uv: int, pk_to_pk_uv: int, wave: int,
                   frequency_hz: float) -> None:
        """``ps3000aSetSigGenBuiltInV2``: a continuous built-in waveform."""
        check(self._lib.ps3000aSetSigGenBuiltInV2(
            self._handle, _c32(offset_uv), _u32(pk_to_pk_uv), wave,
            ctypes.c_double(frequency_hz), ctypes.c_double(frequency_hz),
            ctypes.c_double(0.0), ctypes.c_double(0.0),
            0, 0, _u32(0), _u32(0), 0, 0, _c16(0)),
              "ps3000aSetSigGenBuiltInV2")
