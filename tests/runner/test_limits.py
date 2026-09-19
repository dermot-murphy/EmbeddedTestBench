"""Pass/fail limit checking.

Traces to: RUN-FR-020 .. RUN-FR-025, SWE4-UT-LIMITS.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner.limits import Limit, TextLimit
from benchtools.runner.results import Status
from benchtools.runner.spec import Expectation


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


class TestTextLimits:
    """Exact-match limits on a value that is text.

    "The firmware reports the version that was flashed onto it" is a bench test
    like any other, and before this there was no way to state it: every limit
    went through float(), so a version string was an error rather than a
    verdict.

    Traces to: RUN-FR-024.
    """

    def test_it_passes_on_an_exact_match(self):
        assert TextLimit("1.4.2").check("1.4.2").passed

    def test_it_fails_on_anything_else_and_shows_both(self):
        outcome = TextLimit("1.4.2").check("1.3.9")
        assert not outcome.passed
        assert "1.3.9" in outcome.reason and "1.4.2" in outcome.reason

    def test_surrounding_space_does_not_decide_a_test(self):
        """A reply off a serial link carries whatever the firmware printed."""
        assert TextLimit("1.4.2").check("  1.4.2 ").passed

    def test_a_prefix_is_not_a_match(self):
        """Looser matching would pass 1.4.20 for 1.4.2, which is the failure
        this exists to catch."""
        assert not TextLimit("1.4.2").check("1.4.20").passed

    def test_nothing_measured_is_a_failure_not_a_crash(self):
        outcome = TextLimit("1.4.2").check(None)
        assert not outcome.passed and "no value" in outcome.reason

    def test_the_limit_reads_as_itself_in_a_report(self):
        assert TextLimit("1.4.2").text == '= "1.4.2"'

    def test_a_specification_declaring_text_gets_one(self):
        expectation = Expectation.from_mapping({"name": "v", "equals": "1.4.2"}, 0)
        assert isinstance(expectation.limit, TextLimit)

    def test_text_cannot_carry_a_tolerance(self):
        with pytest.raises(SpecError, match="cannot also"):
            Expectation.from_mapping(
                {"name": "v", "equals": "1.4.2", "tolerance": 0.1}, 0
            )


class TestLimitsTakenFromAnEarlierStep:
    """A limit that names a value an earlier step saved.

    Traces to: RUN-FR-016, RUN-FR-024.
    """

    def test_text_taken_from_a_saved_result(self):
        expectation = Expectation.from_mapping(
            {"name": "v", "measure": "text", "equals": {"from": "build.version"}}, 0
        )
        limit = expectation.limit_against({"build": {"version": "1.4.2"}})
        assert isinstance(limit, TextLimit) and limit.check("1.4.2").passed

    def test_a_number_taken_from_a_saved_result(self):
        expectation = Expectation.from_mapping(
            {"name": "n", "equals": {"from": "earlier"}}, 0
        )
        assert expectation.limit_against({"earlier": 5}).check(5.0).passed

    def test_a_tolerance_applies_to_the_taken_value(self):
        expectation = Expectation.from_mapping(
            {"name": "n", "equals": {"from": "earlier"}, "tolerance": 0.5}, 0
        )
        limit = expectation.limit_against({"earlier": 5})
        assert limit.check(5.4).passed and not limit.check(5.6).passed

    def test_a_tolerance_against_text_is_refused_when_it_resolves(self):
        """It cannot be caught at load time: what the name refers to is not
        known until the step that saves it has run."""
        expectation = Expectation.from_mapping(
            {"name": "v", "equals": {"from": "build"}, "tolerance": 0.5}, 0
        )
        with pytest.raises(SpecError, match="declares a tolerance"):
            expectation.limit_against({"build": "1.4.2"})

    def test_a_reference_cannot_also_declare_a_bound(self):
        with pytest.raises(SpecError, match="use one or the other"):
            Expectation.from_mapping(
                {"name": "n", "equals": {"from": "earlier"}, "min": 1}, 0
            )

    def test_bytes_compare_as_the_text_they_carry(self):
        expectation = Expectation.from_mapping(
            {"name": "v", "equals": {"from": "build"}}, 0
        )
        limit = expectation.limit_against({"build": b"1.4.2"})
        assert isinstance(limit, TextLimit) and limit.check("1.4.2").passed


class TestHowAValueIsReported:
    """`format` renders the value for the record without changing the check.

    An identifier read off a part is unreadable in decimal: 662316 and 0A1B2C
    are the same value and only one of them can be compared with what is
    printed on the board. The limit is still a limit on the number.

    Traces to: RUN-FR-025.
    """

    def check(self, value, **fields):
        """Run one expectation through the runner's own checking."""
        from benchtools.runner.bench import Bench, BenchConfig
        from benchtools.runner.runner import BenchRunner

        data = {"name": "identifier"}
        data.update(fields)
        runner = BenchRunner(Bench(BenchConfig.simulated([])))
        return runner._check_expectation(value, Expectation.from_mapping(data, 0))

    def test_the_value_is_rendered(self):
        measured = self.check(0x0A1B2C, format="{:06X}", minimum=1)
        assert measured.value == "0A1B2C"

    def test_the_number_is_kept_beside_it(self):
        measured = self.check(0x0A1B2C, format="{:06X}", minimum=1)
        assert measured.raw_value == 0x0A1B2C
        assert measured.as_dict()["raw_value"] == 0x0A1B2C

    def test_the_bounds_are_rendered_the_same_way(self):
        """Hex beside decimal bounds would be worse than either alone."""
        measured = self.check(0x0A1B2C, format="{:06X}", minimum=1, maximum=0xFFFFFE)
        assert measured.limit == ">= 000001, <= FFFFFE"

    def test_a_nominal_and_its_window_too(self):
        measured = self.check(16, format="0x{:X}", nominal=16, tolerance=2)
        assert measured.limit == "= 0x10 +/- 0x2"

    def test_the_limit_still_applies_to_the_number(self):
        measured = self.check(0, format="{:06X}", minimum=1)
        assert measured.status is Status.FAIL
        assert measured.value == "000000"

    def test_scaling_happens_before_rendering(self):
        measured = self.check(2.0, format="{:d} ns", scale=1.0e9, minimum=1)
        assert measured.value == "2000000000 ns"

    def test_a_format_that_cannot_be_applied_is_an_error(self):
        """Not a quiet fallback to the number: that would hide a broken
        specification behind a result that looks right."""
        measured = self.check(1.5, format="{:06X}", minimum=1)
        assert measured.status is Status.ERROR
        assert "cannot be applied" in measured.reason

    def test_without_it_nothing_changes(self):
        measured = self.check(3.5, minimum=1)
        assert measured.value == 3.5 and "raw_value" not in measured.as_dict()
