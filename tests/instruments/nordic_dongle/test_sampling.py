"""One command repeated, and a number taken from each reply (#95).

Traces to: BLE-FR-117, SWE4-UT-BLESAMPLE.
"""

from __future__ import annotations

import time

import pytest

from benchtools.core.errors import MeasurementError


def test_each_reply_gives_one_reading(linked):
    samples = linked.sample_command("temp", count=3, interval=0.0, unit="C")
    assert samples.values == [23.5, 23.5, 23.5]
    assert samples.sources == ["23.5", "23.5", "23.5"]
    assert samples.spread == 0.0 and samples.complete and samples.unit == "C"


def test_scale_converts_the_unit(linked):
    samples = linked.sample_command("battery", count=1, interval=0.0, scale=0.01)
    assert samples.values == [pytest.approx(0.97)]


def test_readings_are_spaced_by_the_interval(linked):
    # perf_counter, as sample_command uses: time.monotonic is a 15.6 ms tick on
    # Windows before Python 3.13, which made these bounds fail by one tick (#214).
    started = time.perf_counter()
    samples = linked.sample_command("temp", count=3, interval=0.2)
    assert time.perf_counter() - started >= 0.4
    assert samples.times[2] - samples.times[0] >= 0.39


def test_no_command_is_sent_before_it_is_due_when_a_sleep_ends_early(linked, monkeypatch):
    """A sleep may return before the time asked for; the command still waits (#214)."""
    sent = []
    command = linked.command
    real_sleep = time.sleep

    def record(request, **kwargs):
        sent.append(time.perf_counter())
        return command(request, **kwargs)

    monkeypatch.setattr(linked, "command", record)
    monkeypatch.setattr(time, "sleep", lambda seconds: real_sleep(seconds / 2))
    started = time.perf_counter()
    linked.sample_command("temp", count=3, interval=0.2)
    assert [at - started >= 0.2 * index for index, at in enumerate(sent)] == [True] * 3


def test_a_reply_without_a_number_is_an_error_naming_it(linked):
    with pytest.raises(MeasurementError, match="'OK 1024'|no number"):
        linked.sample_command("rd version", pattern=r"OK (\d+)x", count=1, interval=0.0)
