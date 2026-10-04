"""Repeated readings and their statistics (#95).

Traces to: ANA-FR-022, SWE4-UT-SAMPLES.
"""

from __future__ import annotations

import pytest

from benchtools.analysis.samples import SampleSet, extract_number
from benchtools.core.errors import MeasurementError


class TestExtractNumber:
    def test_the_first_group_is_the_number(self):
        assert extract_number("ACK RD TEMPERATURE = 26125mC", r"= (-?\d+)mC") == 26125.0

    def test_a_negative_and_a_decimal(self):
        assert extract_number("t=-2.5 C") == -2.5

    def test_no_match_is_none(self):
        assert extract_number("NACK Invalid Command", r"= (-?\d+)mC") is None

    def test_a_pattern_without_a_group_is_refused(self):
        with pytest.raises(MeasurementError, match="no group"):
            extract_number("26125mC", r"\d+mC")

    def test_a_group_that_is_not_a_number_is_refused(self):
        with pytest.raises(MeasurementError, match="not a number"):
            extract_number("mode NORMAL", r"mode (\w+)")


class TestSampleSet:
    def test_statistics(self):
        samples = SampleSet(name="t", unit="C", requested=3)
        for value in (26.0, 26.5, 25.5):
            samples.add(value)
        assert (samples.count, samples.minimum, samples.maximum) == (3, 25.5, 26.5)
        assert samples.mean == pytest.approx(26.0)
        assert samples.spread == pytest.approx(1.0)
        assert samples.complete

    def test_a_short_set_says_so_and_keeps_its_readings(self):
        samples = SampleSet(requested=5)
        samples.add(1.0)
        assert not samples.complete and samples.count == 1 and samples.mean == 1.0

    def test_an_empty_set_has_no_statistics(self):
        samples = SampleSet(requested=5)
        assert samples.mean is None and samples.spread is None and samples.minimum is None

    def test_as_dict_keeps_what_each_reading_came_from(self):
        samples = SampleSet(name="RD TEMPERATURE", unit="C", requested=1)
        samples.add(26.125, source="ACK RD TEMPERATURE = 26125mC", at=0.0)
        record = samples.as_dict()
        assert record["values"] == [26.125]
        assert record["sources"] == ["ACK RD TEMPERATURE = 26125mC"]
        assert record["spread"] == 0.0 and record["complete"] is True
