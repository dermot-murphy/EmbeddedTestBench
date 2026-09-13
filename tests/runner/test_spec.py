"""Test specification parsing and validation.

A specification is authored by hand, so every malformed form must produce a
message that says what to fix.

Traces to: RUN-FR-010 .. RUN-FR-014, SWE4-UT-SPEC.
"""

from __future__ import annotations

import json

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner.spec import Step, TestSpec, load_spec

MINIMAL = {
    "name": "Suite",
    "tests": [{"name": "T1", "steps": [{"do": "scope.identity"}]}],
}


class TestSpecParsing:
    def test_minimal_specification(self):
        spec = TestSpec.from_mapping(MINIMAL)
        assert spec.name == "Suite"
        assert len(spec.tests) == 1
        assert spec.tests[0].steps[0].action == "scope.identity"

    def test_instruments_used_is_collected_from_every_section(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "setup": [{"do": "psu.identity"}],
            "teardown": [{"do": "dmm.identity"}],
            "tests": [{"name": "T", "steps": [{"do": "scope.identity"}, {"do": "sleep"}]}],
        })
        assert spec.instruments_used == ["dmm", "psu", "scope"]

    def test_builtin_action_is_not_an_instrument(self):
        spec = TestSpec.from_mapping({
            "name": "S", "tests": [{"name": "T", "steps": [{"do": "sleep"}]}],
        })
        assert spec.instruments_used == []

    def test_declared_instrument_drivers(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "instruments": {"probe": "jlink", "scope": "tek3014b"},
            "tests": [{"name": "T", "steps": [{"do": "probe.identity"}]}],
        })
        assert spec.instrument_drivers == {"probe": "jlink", "scope": "tek3014b"}

    def test_instrument_drivers_default_to_empty(self):
        assert TestSpec.from_mapping(MINIMAL).instrument_drivers == {}

    def test_instruments_block_must_be_a_mapping(self):
        with pytest.raises(SpecError, match="mapping of alias to driver"):
            TestSpec.from_mapping(dict(MINIMAL, instruments=["probe"]))

    def test_requirements_accept_a_string_or_a_list(self):
        assert TestSpec.from_mapping(dict(MINIMAL, requirements="R1")).requirements == ("R1",)
        assert TestSpec.from_mapping(
            dict(MINIMAL, requirements=["R1", "R2"])
        ).requirements == ("R1", "R2")

    def test_case_requirements_list_is_joined(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "requirements": ["R1", "R2"],
                       "steps": [{"do": "scope.identity"}]}],
        })
        assert spec.tests[0].requirement == "R1, R2"

    def test_skip_is_carried(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "skip": True, "skip_reason": "no fixture",
                       "steps": [{"do": "scope.identity"}]}],
        })
        assert spec.tests[0].skip and spec.tests[0].skip_reason == "no fixture"

    @pytest.mark.parametrize("bad,message", [
        ({}, "no name"),
        ({"name": "S"}, "contains no tests"),
        ({"name": "S", "tests": [{"steps": []}]}, "has no name"),
        ({"name": "S", "tests": [{"name": "T", "steps": []}]}, "has no steps"),
        ({"name": "S", "tests": [{"name": "T", "steps": [{}]}]}, "has no 'do' action"),
        ({"name": "S", "tests": "nope"}, "must be a list"),
        ([], "must be a mapping"),
    ])
    def test_malformed_specifications_are_reported(self, bad, message):
        with pytest.raises(SpecError, match=message):
            TestSpec.from_mapping(bad)


class TestStepParsing:
    def test_args_is_an_alias_for_with(self):
        step = Step.from_mapping({"do": "scope.x", "args": {"a": 1}}, 0)
        assert step.arguments == {"a": 1}

    def test_action_is_an_alias_for_do(self):
        assert Step.from_mapping({"action": "scope.x"}, 0).action == "scope.x"

    def test_save_is_carried(self):
        assert Step.from_mapping({"do": "scope.x", "save": "w"}, 0).save == "w"

    def test_single_expectation_may_be_inline(self):
        step = Step.from_mapping({"do": "scope.x", "expect": {"max": 1.0}}, 0)
        assert len(step.expectations) == 1

    def test_arguments_must_be_a_mapping(self):
        with pytest.raises(SpecError, match="arguments must be a mapping"):
            Step.from_mapping({"do": "scope.x", "with": [1, 2]}, 0)


class TestExpectationParsing:
    def test_defaults(self):
        step = Step.from_mapping({"do": "scope.x", "expect": [{"max": 1.0}]}, 0)
        expectation = step.expectations[0]
        assert expectation.name == "value"
        assert expectation.measure == ""
        assert expectation.scale == 1.0

    def test_name_defaults_to_the_measure_path(self):
        step = Step.from_mapping({"do": "x.y", "expect": [{"measure": "1.spread", "max": 1}]}, 0)
        assert step.expectations[0].name == "1.spread"

    def test_display_unit_defaults_to_unit(self):
        step = Step.from_mapping({"do": "x.y", "expect": [{"unit": "s", "max": 1}]}, 0)
        assert step.expectations[0].display_unit == "s"

    def test_expectation_without_a_limit_is_rejected(self):
        with pytest.raises(SpecError, match="declares no limit"):
            Step.from_mapping({"do": "x.y", "expect": [{"name": "v"}]}, 0)

    def test_zero_scale_is_rejected(self):
        with pytest.raises(SpecError, match="scale of zero"):
            Step.from_mapping({"do": "x.y", "expect": [{"max": 1, "scale": 0}]}, 0)

    def test_non_numeric_scale_is_rejected(self):
        with pytest.raises(SpecError, match="non-numeric scale"):
            Step.from_mapping({"do": "x.y", "expect": [{"max": 1, "scale": "big"}]}, 0)


class TestLoading:
    def test_json_needs_no_third_party_package(self, tmp_path):
        path = tmp_path / "spec.json"
        path.write_text(json.dumps(MINIMAL))
        assert load_spec(str(path)).name == "Suite"

    def test_yaml_when_available(self, tmp_path):
        pytest.importorskip("yaml")
        path = tmp_path / "spec.yaml"
        path.write_text(
            "name: Suite\ntests:\n  - name: T1\n    steps:\n      - do: scope.identity\n"
        )
        assert load_spec(str(path)).name == "Suite"

    def test_missing_file_is_reported(self):
        with pytest.raises(SpecError, match="no such specification file"):
            load_spec("/nonexistent/spec.yaml")

    def test_invalid_json_is_reported(self, tmp_path):
        path = tmp_path / "spec.json"
        path.write_text("{not json")
        with pytest.raises(SpecError, match="not valid JSON"):
            load_spec(str(path))

    def test_invalid_yaml_is_reported(self, tmp_path):
        pytest.importorskip("yaml")
        path = tmp_path / "spec.yaml"
        path.write_text("name: [unclosed\n")
        with pytest.raises(SpecError, match="not valid YAML"):
            load_spec(str(path))

    def test_source_is_recorded(self, tmp_path):
        path = tmp_path / "spec.json"
        path.write_text(json.dumps(MINIMAL))
        assert load_spec(str(path)).source == str(path)

    @pytest.mark.parametrize(
        "name,aliases",
        [("clock_skew.yaml", ["scope"]), ("firmware_timing.yaml", ["probe"]),
         ("sensor_rails.yaml", ["psu"]), ("dongle_firmware.yaml", ["dongle"])],
    )
    def test_shipped_specifications_are_valid(self, name, aliases):
        """The examples in specs/ must stay loadable as the API changes."""
        import pathlib

        pytest.importorskip("yaml")
        root = pathlib.Path(__file__).resolve().parents[2]
        spec = load_spec(str(root / "specs" / name))
        assert spec.instruments_used == aliases
        assert len(spec.tests) >= 3
