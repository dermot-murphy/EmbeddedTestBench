"""Pass/fail limit checking.

Traces to: RUN-FR-020 .. RUN-FR-023, SWE4-UT-LIMITS.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner.limits import Limit


class TestConstruction:
    def test_min_and_max_aliases(self):
        limit = Limit.from_mapping({"min": 1, "max": 2})
        assert limit.minimum == 1.0 and limit.maximum == 2.0

    def test_nominal_alias(self):
        assert Limit.from_mapping({"nominal": 5, "tolerance": 1}).equals == 5.0

    def test_unknown_keys_are_ignored(self):
        """Expectations carry name/unit/scale alongside the limit keys."""
        assert Limit.from_mapping({"max": 2, "name": "x", "unit": "s"}).maximum == 2.0

    def test_no_bound_is_rejected(self):
        with pytest.raises(SpecError, match="at least one of"):
            Limit.from_mapping({"unit": "s"})

    def test_tolerance_without_nominal_is_rejected(self):
        with pytest.raises(SpecError, match="only meaningful alongside equals"):
            Limit(maximum=1.0, tolerance=0.1)

    def test_two_tolerance_forms_are_rejected(self):
        with pytest.raises(SpecError, match="not both"):
            Limit(equals=1.0, tolerance=0.1, tolerance_percent=1.0)

    def test_inverted_bounds_are_rejected(self):
        with pytest.raises(SpecError, match="above its maximum"):
            Limit(minimum=10.0, maximum=1.0)

    def test_non_numeric_is_rejected(self):
        with pytest.raises(SpecError, match="must be a number"):
            Limit.from_mapping({"max": "loud"})

    def test_non_mapping_is_rejected(self):
        with pytest.raises(SpecError, match="must be a mapping"):
            Limit.from_mapping([1, 2])


class TestChecking:
    def test_maximum(self):
        limit = Limit(maximum=20.0)
        assert limit.check(9.0).passed
        assert limit.check(20.0).passed
        assert not limit.check(20.1).passed
        assert "above the maximum" in limit.check(25.0).reason

    def test_minimum(self):
        limit = Limit(minimum=1.0)
        assert limit.check(1.0).passed
        assert "below the minimum" in limit.check(0.5).reason

    def test_two_sided(self):
        limit = Limit(minimum=1.0, maximum=2.0)
        assert limit.check(1.5).passed
        assert not limit.check(0.9).passed
        assert not limit.check(2.1).passed

    def test_absolute_tolerance(self):
        limit = Limit(equals=10.0, tolerance=0.5)
        assert limit.check(10.5).passed
        assert limit.check(9.5).passed
        assert not limit.check(10.6).passed

    def test_percentage_tolerance(self):
        limit = Limit(equals=1.0e-6, tolerance_percent=1.0)
        assert limit.check(1.005e-6).passed
        assert not limit.check(1.02e-6).passed
        assert "outside +/-" in limit.check(1.02e-6).reason

    def test_exact_equality(self):
        limit = Limit(equals=4.0)
        assert limit.check(4.0).passed
        assert "!= required" in limit.check(4.1).reason

    def test_nan_fails_rather_than_passing(self):
        assert not Limit(maximum=1.0).check(float("nan")).passed

    def test_none_fails(self):
        assert "not a number" in Limit(maximum=1.0).check(None).reason


class TestRendering:
    @pytest.mark.parametrize(
        "limit,text",
        [
            (Limit(maximum=20.0), "<= 20"),
            (Limit(minimum=1.0), ">= 1"),
            (Limit(minimum=1.0, maximum=2.0), ">= 1, <= 2"),
            (Limit(equals=10.0, tolerance=0.5), "= 10 +/- 0.5"),
            (Limit(equals=10.0, tolerance_percent=1.0), "= 10 +/- 1%"),
            (Limit(equals=4.0), "= 4"),
        ],
    )
    def test_text(self, limit, text):
        assert limit.text == text
