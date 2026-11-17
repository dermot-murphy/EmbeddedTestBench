"""The simulated device that prints a script of lines.

Traces to: SER-FR-010, SWE4-UT-SERSIM.
"""

from __future__ import annotations

import time

import pytest

from benchtools.instruments.serial_capture.simulator import (
    DEFAULT_SCRIPT,
    SimulatedSerialDevice,
)


def test_silent_until_restarted():
    device = SimulatedSerialDevice(["A"], interval=0.0)
    assert device.poll() == b""
    device.restart()
    assert device.poll() == b"A\r\n"
    assert device.poll() == b""
    assert device.sent == 1


def test_lines_come_at_their_interval():
    device = SimulatedSerialDevice(["A", "B"], interval=0.5)
    device.restart()
    assert device.poll() == b""
    time.sleep(0.6)
    assert device.poll() == b"A\r\n"
    assert device.poll() == b""


def test_restart_replays_the_script():
    device = SimulatedSerialDevice(["A"], interval=0.0)
    device.restart()
    device.poll()
    device.restart()
    assert device.poll() == b"A\r\n"


def test_default_script():
    assert SimulatedSerialDevice().lines == list(DEFAULT_SCRIPT)


def test_writes_are_ignored_and_kept():
    device = SimulatedSerialDevice()
    assert device.respond(b"hello\n") is None
    assert device.received == bytearray(b"hello\n")


def test_negative_interval():
    with pytest.raises(ValueError):
        SimulatedSerialDevice(interval=-1)
