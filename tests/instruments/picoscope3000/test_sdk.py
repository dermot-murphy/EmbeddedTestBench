"""The ctypes seam, against a fake library: status handling and library search.

The real library is exercised on the bench (ETB-SWE4-001, hardware cases);
here only what does not need it.

Traces to: PSCOPE-FR-001, PSCOPE-NFR-001, SWE4-UT-PSCOPESDK.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import (
    ConnectionFailedError,
    InstrumentError,
    OptionalDependencyError,
)
from benchtools.instruments.picoscope3000 import sdk as sdk_module
from benchtools.instruments.picoscope3000.sdk import Ps3000aSdk, check, find_library


class FakeLibrary:
    """Answers the calls Ps3000aSdk makes with fixed statuses."""

    def __init__(self, open_status=0, handle=1, power_status=0):
        self.open_status = open_status
        self.handle = handle
        self.power_status = power_status
        self.calls = []

    def ps3000aOpenUnit(self, handle_ref, serial):  # pylint: disable=invalid-name
        self.calls.append(("open", serial))
        handle_ref._obj.value = self.handle
        return self.open_status

    def ps3000aChangePowerSource(self, _handle, status):  # pylint: disable=invalid-name
        self.calls.append(("power", status.value))
        return self.power_status

    def ps3000aStop(self, _handle):  # pylint: disable=invalid-name
        self.calls.append(("stop",))
        return 0

    def ps3000aCloseUnit(self, _handle):  # pylint: disable=invalid-name
        self.calls.append(("close",))
        return 0

    def ps3000aMaximumValue(self, _handle, value_ref):  # pylint: disable=invalid-name
        value_ref._obj.value = 32512
        return 0

    def ps3000aSetChannel(self, *args):  # pylint: disable=invalid-name
        self.calls.append(("channel",) + args[1:5])
        return 0x0F


def test_open_passes_the_serial_and_closes():
    library = FakeLibrary()
    unit = Ps3000aSdk(serial="HT415/0202", library=library)
    unit.open()
    assert unit.is_open
    assert library.calls[0] == ("open", b"HT415/0202")
    assert unit.maximum_value() == 32512
    unit.close()
    assert not unit.is_open
    assert library.calls[-2:] == [("stop",), ("close",)]


def test_power_source_is_confirmed_when_asked():
    library = FakeLibrary(open_status=0x11E)
    unit = Ps3000aSdk(library=library)
    unit.open()
    assert ("power", 0x11E) in library.calls


def test_not_found_is_a_connection_failure():
    unit = Ps3000aSdk(library=FakeLibrary(open_status=3, handle=-1))
    with pytest.raises(ConnectionFailedError, match="no PicoScope found"):
        unit.open()
    assert not unit.is_open


def test_a_refused_call_raises_with_its_status():
    unit = Ps3000aSdk(library=FakeLibrary())
    unit.open()
    with pytest.raises(InstrumentError, match="ps3000aSetChannel.A. failed: status 0xF"):
        unit.set_channel(0, True, 1, 11, 0.0)


def test_check():
    check(0, "anything")
    with pytest.raises(InstrumentError) as raised:
        check(0x0E, "ps3000aGetTimebase2(0)")
    assert raised.value.events == ((0x0E, "ps3000aGetTimebase2(0)"),)


def test_library_found_in_the_named_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(sdk_module.ctypes.util, "find_library", lambda name: None)
    monkeypatch.delenv("PICOSDK_PATH", raising=False)
    monkeypatch.setattr(sdk_module, "_WINDOWS_FOLDERS", ())
    name = "ps3000a.dll" if sdk_module.sys.platform == "win32" else (
        "libps3000a.dylib" if sdk_module.sys.platform == "darwin" else "libps3000a.so")
    (tmp_path / name).write_bytes(b"")
    assert find_library(str(tmp_path)) == str(tmp_path / name)


def test_missing_library_says_what_to_install(tmp_path, monkeypatch):
    monkeypatch.setattr(sdk_module, "_candidates", lambda path: [])
    with pytest.raises(OptionalDependencyError, match="PicoScope 7 or the PicoSDK"):
        find_library(str(tmp_path))
