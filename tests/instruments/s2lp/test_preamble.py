"""PQI as a measure of preamble length.

The expectation, 2 x pairs - 1 capped at 255, is from the kit (#87, #89): a
64-bit preamble read 63, a 256-bit preamble read 255.

Traces to: S2LP-FR-049, SWE4-UT-S2LPPREAMBLE.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.s2lp.preamble import (
    PQI_CEILING,
    PreambleMeasurement,
    check_preamble,
    expected_pqi,
)


class TestExpectedPqi:
    @pytest.mark.parametrize("pairs,pqi", [(32, 63), (48, 95), (100, 199), (127, 253),
                                           (128, 255), (1023, 255)])
    def test_two_per_pair_less_one_up_to_the_ceiling(self, pairs, pqi):
        assert expected_pqi(pairs) == pqi

    def test_the_measured_points(self):
        """Measured on the kit: 32 pairs read 63, 48 pairs read 95."""
        assert (expected_pqi(32), expected_pqi(48)) == (63, 95)


class TestMeasurement:
    def test_the_best_frame_is_the_measurement(self):
        measured = PreambleMeasurement("5C1712", [40, 63, 55])
        assert (measured.max_pqi, measured.preamble_bits, measured.preamble_pairs) == (63, 64, 32)
        assert not measured.saturated

    def test_the_ceiling_is_flagged(self):
        assert PreambleMeasurement("x", [PQI_CEILING]).saturated

    def test_no_frames(self):
        measured = PreambleMeasurement("x")
        assert measured.max_pqi is None and measured.preamble_bits is None


class TestCheck:
    def test_a_match_passes(self):
        assert check_preamble(PreambleMeasurement("s", [63]), 32).passed

    def test_a_few_pairs_short_passes_within_tolerance(self):
        assert check_preamble(PreambleMeasurement("s", [60]), 32, tolerance_pairs=2).passed

    def test_more_than_the_tolerance_short_fails(self):
        check = check_preamble(PreambleMeasurement("s", [50]), 32, tolerance_pairs=2)
        assert check.verdict == "fail" and "shorter" in check.reason

    def test_longer_than_set_fails(self):
        check = check_preamble(PreambleMeasurement("s", [95]), 32)
        assert check.verdict == "fail" and "longer" in check.reason

    def test_at_the_ceiling_is_unmeasurable_not_a_pass(self):
        """128 pairs or more all read 255: a pass would claim more than PQI shows."""
        check = check_preamble(PreambleMeasurement("s", [255]), 128)
        assert check.verdict == "unmeasurable" and not check.passed

    def test_nothing_heard_is_unmeasurable(self):
        check = check_preamble(PreambleMeasurement("s"), 32)
        assert check.verdict == "unmeasurable" and "no frame" in check.reason

    def test_the_result_carries_the_figures(self):
        result = check_preamble(PreambleMeasurement("s", [63]), 32).as_dict()
        assert result["expected_pqi"] == 63 and result["max_pqi"] == 63
        assert result["preamble_bits"] == 64
