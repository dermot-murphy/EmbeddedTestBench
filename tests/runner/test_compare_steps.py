"""Limits that compare readings: text forms, bounds from saved values, compute (#242).

Traces to: RUN-FR-067 .. RUN-FR-070, SWE4-UT-COMPARE.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import MeasurementError, SpecError
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.limits import TextLimit
from benchtools.runner.results import Status
from benchtools.runner.runner import BUILTIN_ACTIONS
from benchtools.runner.spec import Expectation, TestSpec


def expect(**limit):
    return Expectation.from_mapping(dict({"name": "x", "measure": ""}, **limit), 0)


class TestTextForms:
    def test_equals_ignoring_case(self):
        limit = expect(equals="V11.02.0000-abc", ignore_case=True).limit
        assert limit.check("v11.02.0000-ABC").passed
        assert not TextLimit("V11").check("v11").passed
        assert limit.text.endswith(", ignoring case")

    def test_one_of_text_and_numbers(self):
        limit = expect(one_of=["DETECT", "IGNORE", 3]).limit
        assert limit.check("IGNORE").passed and limit.check("3.0").passed
        assert not limit.check("detect").passed
        assert expect(one_of=["DETECT"], ignore_case=True).limit.check("detect").passed
        assert 'is not one of "DETECT"' in expect(one_of=["DETECT"]).limit.check("X").reason

    def test_matches_is_a_whole_match_with_a_reason(self):
        limit = expect(matches=r"V\d+\.\d{2}\.\d{4}", reason="the build number changes").limit
        assert limit.check(" V11.02.0000 ").passed
        assert not limit.check("V11.02.0000-dirty").passed
        assert limit.text == r"matches /V\d+\.\d{2}\.\d{4}/ (the build number changes)"
        assert expect(matches="ok", reason="r", ignore_case=True).limit.check("OK").passed

    @pytest.mark.parametrize("limit, message", [
        ({"matches": "x"}, "needs a reason"),
        ({"matches": "x", "reason": "  "}, "needs a reason"),
        ({"matches": "(", "reason": "r"}, "not a regular expression"),
        ({"one_of": []}, "one of equals, matches or one_of|one_of must be a list"),
        ({"one_of": "abc"}, "one_of must be a list"),
        ({"equals": "a", "matches": "a", "reason": "r"}, "exactly one of"),
        ({"one_of": ["a"], "max": 2}, "cannot also declare a tolerance or a bound"),
        ({"max": 2, "ignore_case": True}, "apply only to a text limit"),
        ({"max": 2, "reason": "why"}, "apply only to a text limit"),
    ])
    def test_a_malformed_text_limit_is_a_load_error(self, limit, message):
        with pytest.raises(SpecError, match=message):
            expect(**limit)

    def test_exact_stays_the_default(self):
        assert not expect(equals="ABC").limit.check("abc").passed


class TestBoundsFromSavedValues:
    def test_a_maximum_from_a_saved_reading(self):
        expectation = expect(max={"from": "unloaded"})
        assert expectation.limit is None and expectation.deferred is not None
        limit = expectation.limit_against({"unloaded": 3.30})
        assert limit.check(3.30).passed and not limit.check(3.31).passed

    def test_a_saved_bound_beside_a_stated_one(self):
        limit = expect(min=3.0, max={"from": "unloaded"}).limit_against({"unloaded": 3.3})
        assert limit.minimum == 3.0 and limit.maximum == 3.3

    def test_a_bound_read_off_a_reply_as_text(self):
        limit = expect(min={"from": "reply"}).limit_against({"reply": b"2.5"})
        assert limit.minimum == 2.5

    def test_a_saved_bound_that_is_not_a_number_is_an_error(self):
        with pytest.raises(SpecError, match="cannot bound with 'DETECT'"):
            expect(max={"from": "phase"}).limit_against({"phase": "DETECT"})

    def test_one_of_with_a_saved_item(self):
        limit = expect(one_of=[{"from": "first"}, "IGNORE"]).limit_against({"first": "DETECT"})
        assert limit.check("DETECT").passed and limit.check("IGNORE").passed

    def test_a_tolerance_cannot_take_a_saved_value(self):
        with pytest.raises(SpecError, match="tolerance cannot take a value"):
            expect(equals=1.0, tolerance={"from": "x"})

    def test_equals_from_a_saved_reply_ignoring_case(self):
        limit = expect(equals={"from": "rd_version"}, ignore_case=True).limit_against(
            {"rd_version": "V11.02.0000-ABC"})
        assert limit.check("v11.02.0000-abc").passed


class TestCompute:
    compute = staticmethod(BUILTIN_ACTIONS["compute"])

    @pytest.mark.parametrize("operation, expected", [
        ("difference", -0.25), ("absolute_difference", 0.25), ("sum", 6.75),
        ("product", 11.375), ("ratio", 3.25 / 3.5)])
    def test_each_operation(self, operation, expected):
        assert self.compute(operation, 3.25, "3.5") == pytest.approx(expected)

    def test_an_unknown_operation_names_those_offered(self):
        with pytest.raises(SpecError, match="absolute_difference, difference, product"):
            self.compute("mean", 1, 2)

    def test_a_value_that_is_not_a_number(self):
        with pytest.raises(SpecError, match="b is 'NACK'"):
            self.compute("sum", 1, b"NACK")

    def test_a_ratio_to_zero_is_a_measurement_error(self):
        with pytest.raises(MeasurementError, match="ratio of 1 to zero"):
            self.compute("ratio", 1, 0)


def test_a_loaded_battery_no_higher_than_unloaded_in_a_run():
    """OT-A-31's shape: two readings saved, one bounded by the other, and their
    difference computed and checked."""
    spec = TestSpec.from_mapping({"name": "battery", "tests": [{"name": "loaded", "steps": [
        {"do": "sleep", "with": {"seconds": 0}, "save": "unloaded"},
        {"do": "sleep", "with": {"seconds": 0}, "save": "loaded",
         "expect": [{"name": "no_higher", "measure": "", "max": {"from": "unloaded"}}]},
        {"do": "compute", "with": {"operation": "difference", "a": {"from": "unloaded"},
                                   "b": {"from": "loaded"}},
         "expect": [{"name": "drop", "measure": "", "min": 0.0, "max": 0.2}]},
        {"do": "sleep", "with": {"seconds": 0},
         "expect": [{"name": "above", "measure": "", "min": {"from": "unloaded"},
                     "max": 1.0}]},
    ]}]})
    with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
        record = runner.run(spec)
    measured = {m.name: m for step in record.cases[0].steps for m in step.measurements}
    assert measured["no_higher"].status is Status.PASS
    assert measured["no_higher"].limit == "<= 0"
    assert measured["drop"].status is Status.PASS and measured["drop"].value == 0.0
    assert measured["above"].status is Status.PASS


class TestRoundOneOfReview:
    """Findings of the first review of #306."""

    def test_a_saved_bound_that_is_not_finite_is_an_error(self):
        with pytest.raises(SpecError, match="not a finite number"):
            expect(min={"from": "n"}).limit_against({"n": float("nan")})
        with pytest.raises(SpecError, match="not a finite number"):
            expect(max={"from": "n"}).limit_against({"n": "inf"})

    @pytest.mark.parametrize("a, b, message", [
        ("nan", 1, "a is 'nan', not a finite number"),
        (1, float("inf"), "b is inf, not a finite number"),
    ])
    def test_compute_refuses_values_that_are_not_finite(self, a, b, message):
        with pytest.raises(SpecError, match=message):
            BUILTIN_ACTIONS["compute"]("difference", a, b)

    def test_compute_refuses_a_result_that_is_not_finite(self):
        with pytest.raises(MeasurementError, match="product of .* is inf"):
            BUILTIN_ACTIONS["compute"]("product", 1e200, 1e200)

    @pytest.mark.parametrize("item, message", [
        (True, "quote ON, OFF"), (None, "not a text or a number"),
        ([1], "not a text or a number"), (float("nan"), "not a finite number")])
    def test_a_one_of_item_that_is_not_text_or_a_number_is_refused(self, item, message):
        with pytest.raises(SpecError, match=message):
            expect(one_of=["A", item])

    def test_a_saved_one_of_item_read_off_a_link_is_text(self):
        limit = expect(one_of=[{"from": "reply"}]).limit_against({"reply": b"ON"})
        assert limit.check("ON").passed

    @pytest.mark.parametrize("text", ["1_0", "1e1", "0x0A", " "])
    def test_only_a_plainly_written_number_equals_a_number(self, text):
        assert not expect(one_of=[10]).limit.check(text).passed
        assert expect(one_of=[10]).limit.check("10.0").passed

    @pytest.mark.parametrize("extra", [{"scale": 2}, {"format": "{:X}"}])
    def test_scale_and_format_do_not_apply_to_text(self, extra):
        with pytest.raises(SpecError, match="scale and format"):
            expect(one_of=["A"], **extra)

    def test_equals_and_nominal_together_are_refused(self):
        with pytest.raises(SpecError, match="both equals and nominal"):
            expect(equals=1, nominal=1)

    def test_a_reading_above_the_saved_bound_fails_and_says_by_how_much(self):
        spec = TestSpec.from_mapping({"name": "b", "tests": [{"name": "t", "steps": [
            {"do": "compute", "with": {"operation": "sum", "a": 1, "b": 1}, "save": "two"},
            {"do": "compute", "with": {"operation": "sum", "a": 2, "b": 1},
             "expect": [{"name": "no_higher", "measure": "", "max": {"from": "two"}}]},
        ]}]})
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            record = runner.run(spec)
        [measured] = record.cases[0].steps[1].measurements
        assert measured.status is Status.FAIL and measured.reason == "3 is above the maximum 2"

    def test_an_unresolved_saved_limit_is_described_not_none(self):
        spec = TestSpec.from_mapping({"name": "b", "tests": [{"name": "t", "steps": [
            {"do": "sleep", "with": {"seconds": 0},
             "expect": [{"name": "x", "measure": "", "max": {"from": "never"}}]}]}]})
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            record = runner.run(spec)
        [measured] = record.cases[0].steps[0].measurements
        assert measured.status is Status.ERROR and "None" not in measured.limit


class TestRoundTwoOfReview:
    """Findings of the second review of #306."""

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), "nan", "-inf"])
    def test_a_bound_written_as_not_a_finite_number_is_a_load_error(self, value):
        with pytest.raises(SpecError, match="must be a finite number"):
            expect(max=value)

    @pytest.mark.parametrize("limit, message", [
        ({"min": {"from": "x"}, "ignore_case": True}, "apply only to a text limit"),
        ({"one_of": [{"from": "x"}], "max": 2}, "cannot also declare a tolerance or a bound"),
        ({"min": {"from": "x"}, "max": "high"}, "must be a number"),
    ])
    def test_a_malformed_limit_with_a_saved_value_is_still_a_load_error(self, limit, message):
        with pytest.raises(SpecError, match=message):
            expect(**limit)

    def test_an_empty_text_in_one_of_is_a_value_like_any_other(self):
        limit = expect(one_of=["", "OK"]).limit
        assert limit.check("").passed and limit.check("OK").passed
