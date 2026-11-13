"""Ranges, timebases and channel names, against what the bench unit reported.

Traces to: PSCOPE-FR-003, PSCOPE-FR-005, SWE4-UT-PSCOPECONST.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.picoscope3000.constants import (
    RANGES,
    Channel,
    range_for_volts,
    sample_interval_s,
    status_text,
    timebase_for,
)


@pytest.mark.parametrize("timebase, nanoseconds", [
    (0, 1), (1, 2), (2, 4), (3, 8), (4, 16), (5, 24), (10, 64), (127, 1000), (252, 2000),
])
def test_interval_matches_the_bench_unit(timebase, nanoseconds):
    # Values ps3000aGetTimebase2 returned on the 3405D on 2026-11-13.
    assert sample_interval_s(timebase) == pytest.approx(nanoseconds * 1e-9)


@pytest.mark.parametrize("interval, timebase", [
    (1e-9, 0), (3e-9, 1), (4e-9, 2), (8e-9, 3), (1e-6, 127), (2e-6, 252), (1.5e-6, 189),
    (1e-12, 0),
])
def test_timebase_for_is_not_faster_than_asked_except_below_1ns(interval, timebase):
    assert timebase_for(interval) == timebase
    if interval >= 1e-9:
        assert sample_interval_s(timebase) <= interval * (1 + 1e-9)


def test_timebase_for_refuses_nonsense():
    with pytest.raises(ValueError):
        timebase_for(0)
    with pytest.raises(ValueError):
        sample_interval_s(-1)


def test_ranges_are_the_ten_the_unit_accepts():
    assert sorted(RANGES) == list(range(1, 11))
    assert RANGES[1] == 0.02 and RANGES[10] == 20.0


@pytest.mark.parametrize("volts, index", [(0.02, 1), (0.03, 2), (1.0, 6), (1.2, 7), (20, 10),
                                          (-3.0, 8)])
def test_range_for_volts_rounds_up(volts, index):
    assert range_for_volts(volts) == index


def test_range_beyond_20_v_is_refused():
    with pytest.raises(ValueError, match="largest"):
        range_for_volts(25)


@pytest.mark.parametrize("given", [1, "A", "a", " a ", "1", Channel.A])
def test_channel_names(given):
    assert Channel.parse(given) is Channel.A


def test_channel_numbers_and_indices():
    assert [channel.sdk_index for channel in Channel] == [0, 1, 2, 3]
    assert [channel.number for channel in Channel] == [1, 2, 3, 4]
    with pytest.raises(ValueError):
        Channel.parse(5)
    with pytest.raises(ValueError):
        Channel.parse("E")


def test_status_text_names_only_what_was_seen():
    assert "no PicoScope" in status_text(3)
    assert status_text(0x1234) == "0x1234"
