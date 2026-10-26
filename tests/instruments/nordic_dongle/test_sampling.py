"""One command repeated, and a number taken from each reply (#95).

Traces to: BLE-FR-117, BLE-FR-122, SWE4-UT-BLESAMPLE.
"""

from __future__ import annotations

import time
import types

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError, MeasurementError


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


class _Clock:
    """A clock the dongle module reads instead of the real one, so the poll
    schedule is tested exactly, not against how loaded the machine is."""

    def __init__(self):
        self.now = 0.0
        self.sent = []

    def perf_counter(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(seconds, 0.0)


def _replies(monkeypatch, linked, texts, delay=0.0):
    """Make each command answer with the next of *texts*, then the last again,
    *delay* seconds after it is sent, on a clock of the test's own."""
    queue = list(texts)
    clock = _Clock()
    monkeypatch.setattr("benchtools.instruments.nordic_dongle.dongle.time", clock)

    def answer(request, **kwargs):  # pylint: disable=unused-argument
        clock.sent.append(clock.now)
        clock.now += delay
        return types.SimpleNamespace(text=queue.pop(0) if len(queue) > 1 else queue[0])
    monkeypatch.setattr(linked, "command", answer)
    return clock


class TestPollStates:
    """The states a polled reply goes through, in order (#242). Traces to: BLE-FR-122."""

    def test_repeated_states_are_kept_once_in_order(self, linked, monkeypatch):
        _replies(monkeypatch, linked, ["DETECT", "DETECT", "IGNORE", "IGNORE", "DETECT"],
                 delay=0.1)
        result = linked.poll_states("rd phase", interval=1.0, duration=4.0)
        assert result["states"] == ["DETECT", "IGNORE", "DETECT"]
        assert result["sequence"] == "DETECT,IGNORE,DETECT" and result["count"] == 3
        assert result["polls"] == 5 and result["unmatched"] == 0 and result["skipped"] == 0
        assert result["times"] == [0.1, 2.1, 4.1]

    def test_a_pattern_takes_the_state_and_skips_replies_it_does_not_match(self, linked,
                                                                           monkeypatch):
        _replies(monkeypatch, linked, ["PHASE = DETECT", "NACK", "PHASE = IGNORE"])
        result = linked.poll_states("rd phase", interval=1.0, duration=2.0,
                                    pattern=r"PHASE = (\w+)")
        assert result["states"] == ["DETECT", "IGNORE"] and result["unmatched"] == 1

    def test_the_polls_are_sent_at_each_interval(self, linked, monkeypatch):
        clock = _replies(monkeypatch, linked, ["A"], delay=0.3)
        assert linked.poll_states("rd phase", interval=1.0, duration=2.0)["polls"] == 3
        assert clock.sent == [0.0, 1.0, 2.0]

    def test_a_slow_reply_skips_the_polls_it_overran_and_sends_none_late(self, linked,
                                                                         monkeypatch):
        clock = _replies(monkeypatch, linked, ["A"], delay=2.5)
        result = linked.poll_states("rd", interval=1.0, duration=4.0)
        assert clock.sent == [0.0, 3.0]
        assert result["polls"] == 2 and result["skipped"] == 3

    def test_a_reply_that_ends_as_the_next_poll_is_due_does_not_skip_it(self, linked,
                                                                        monkeypatch):
        clock = _replies(monkeypatch, linked, ["A"], delay=1.0)
        result = linked.poll_states("rd", interval=1.0, duration=2.0)
        assert clock.sent == [0.0, 1.0, 2.0] and result["skipped"] == 0

    def test_the_real_clock_is_used_when_nothing_replaces_it(self, linked):
        started = time.perf_counter()
        result = linked.poll_states("temp", interval=0.2, duration=0.2)
        assert result["states"] == ["23.5"] and time.perf_counter() - started >= 0.2
    @pytest.mark.parametrize("options, message", [
        ({"interval": 0}, "interval must be a positive number"),
        ({"interval": float("nan")}, "interval must be a positive number"),
        ({"duration": float("nan")}, "duration must be a finite number"),
        ({"duration": float("inf")}, "duration must be a finite number"),
        ({"duration": -1}, "duration must be a finite number"),
        ({"pattern": "("}, "not a regular expression"),
    ])
    def test_bad_options_are_refused(self, linked, options, message):
        with pytest.raises(ConfigurationError, match=message):
            linked.poll_states("rd phase", **options)



class TestPollStatesSchedule:
    """Review of #306: the schedule, and what a bad poll does. Traces to: BLE-FR-122."""

    def test_the_last_poll_is_not_lost_to_rounding(self, linked, monkeypatch):
        _replies(monkeypatch, linked, ["A"])
        monkeypatch.setattr("benchtools.instruments.nordic_dongle.dongle._sleep_until",
                            lambda due: None)
        assert linked.poll_states("rd", interval=0.1, duration=0.3)["polls"] == 4

    def test_a_duration_of_zero_is_one_poll(self, linked, monkeypatch):
        _replies(monkeypatch, linked, ["A"])
        assert linked.poll_states("rd", interval=1.0, duration=0)["polls"] == 1

    def test_a_failed_command_is_counted_and_the_states_are_kept(self, linked, monkeypatch):
        answers = iter(["A", None, "B"])

        def flaky(request, **kwargs):  # pylint: disable=unused-argument
            text = next(answers)
            if text is None:
                raise InstrumentError("the sensor did not reply")
            return types.SimpleNamespace(text=text)
        monkeypatch.setattr(linked, "command", flaky)
        monkeypatch.setattr("benchtools.instruments.nordic_dongle.dongle._sleep_until",
                            lambda due: None)
        result = linked.poll_states("rd", interval=1.0, duration=2.0)
        assert result["states"] == ["A", "B"] and result["failed"] == 1 and result["polls"] == 2

    def test_a_group_that_took_no_part_is_unmatched(self, linked, monkeypatch):
        _replies(monkeypatch, linked, ["PHASE"])
        result = linked.poll_states("rd", interval=1.0, duration=0, pattern=r"PHASE( = \w+)?")
        assert result["states"] == [] and result["unmatched"] == 1
