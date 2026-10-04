"""Parameters named once at the top of a specification (#95).

Traces to: RUN-FR-058, SWE4-UT-PARAMS.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner.bench import BenchConfig
from benchtools.runner.runner import BenchRunner
from benchtools.runner.report import format_markdown
from benchtools.runner.spec import TestSpec, substitute_parameters


def spec(parameters, expect, arguments=None):
    return TestSpec.from_mapping({
        "name": "Suite",
        "parameters": parameters,
        "tests": [{"name": "T", "steps": [
            {"do": "dongle.protocol_is_compatible", "expect": [expect]}
            if arguments is None else
            {"do": "dongle.command", "with": arguments, "expect": [expect]}]}],
    })


class TestSubstitution:
    def test_a_bound_and_a_tolerance_come_from_parameters(self):
        loaded = TestSpec.from_mapping({
            "name": "Suite",
            "parameters": {"limit": 2.0, "tolerance": 5.0, "count": 3},
            "tests": [{"name": "T", "steps": [
                {"do": "a.b", "with": {"count": {"param": "count"}}, "save": "x"},
                {"do": "a.c", "expect": [
                    {"name": "spread", "max": {"param": "limit"}},
                    {"name": "mean", "equals": {"from": "x.mean"},
                     "tolerance": {"param": "tolerance"}}]}]}],
        })
        first, second = loaded.tests[0].steps
        assert first.arguments == {"count": 3}
        assert second.expectations[0].limit.maximum == 2.0
        assert second.expectations[1].tolerance == 5.0
        assert loaded.parameters == {"limit": 2.0, "tolerance": 5.0, "count": 3}

    def test_a_parameter_can_be_rendered_into_text(self):
        data = {"request": {"param": "period", "format": "WR ALIVE-PERIOD {}"}}
        assert substitute_parameters(data, {"period": 10}) == {"request": "WR ALIVE-PERIOD 10"}

    def test_an_undefined_parameter_names_those_defined(self):
        with pytest.raises(SpecError, match="names no parameter.*defines count, limit"):
            substitute_parameters({"max": {"param": "limt"}}, {"limit": 2, "count": 5})

    def test_parameters_must_be_single_values(self):
        with pytest.raises(SpecError, match="single value"):
            spec({"limits": [1, 2]}, {"name": "x", "equals": 1})

    def test_a_mapping_that_only_looks_like_one_is_left_alone(self):
        data = {"param": "x", "other": 1}
        assert substitute_parameters(data, {"x": 5}) == data

    def test_a_spec_without_parameters_is_unchanged(self):
        loaded = TestSpec.from_mapping(
            {"name": "S", "tests": [{"name": "T", "steps": [{"do": "a.b"}]}]})
        assert loaded.parameters == {}


def test_the_record_and_the_report_show_the_values_used():
    loaded = spec({"expected": 1}, {"name": "compatible", "equals": {"param": "expected"}})
    config = BenchConfig.simulated(loaded.instruments_used, driver="ble-dongle")
    runner = BenchRunner.from_config(config)
    try:
        run = runner.run(loaded)
    finally:
        runner.close()
    assert run.passed == 1
    assert run.as_dict()["parameters"] == {"expected": 1}
    assert "| Parameters | expected = 1 |" in format_markdown(run)
