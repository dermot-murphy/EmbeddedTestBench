"""Addressing values inside a step's return value.

Traces to: RUN-FR-013, RUN-FR-016, SWE4-UT-RESOLVE.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner.resolve import (
    Reference,
    parse_references,
    resolve_path,
    resolve_references,
)


@dataclass
class Result:
    spread: float = 9e-9
    skews: dict = None

    def __post_init__(self):
        if self.skews is None:
            self.skews = {1: 0.0, 2: 4e-9, 3: 9e-9}

    @property
    def worst(self) -> float:
        return max(self.skews.values())

    def as_float(self) -> float:
        return self.spread


class TestResolution:
    def test_empty_path_is_the_whole_result(self):
        assert resolve_path(2.5, "") == 2.5

    def test_attribute(self):
        assert resolve_path(Result(), "spread") == 9e-9

    def test_property(self):
        assert resolve_path(Result(), "worst") == 9e-9

    def test_zero_argument_method_is_called(self):
        assert resolve_path(Result(), "as_float") == 9e-9

    def test_tuple_index_then_attribute(self):
        assert resolve_path((None, Result()), "1.spread") == 9e-9

    def test_negative_index(self):
        assert resolve_path((None, Result()), "-1.spread") == 9e-9

    def test_dict_key_as_string(self):
        assert resolve_path({"a": Result()}, "a.spread") == 9e-9

    def test_dict_with_integer_keys_from_a_yaml_string(self):
        """A spec gives keys as text; a channel-keyed dict uses ints."""
        assert resolve_path((None, Result()), "1.skews.2") == 4e-9

    def test_deep_path(self):
        assert resolve_path({"r": (None, Result())}, "r.1.skews.3") == 9e-9


class TestErrors:
    def test_missing_attribute_names_the_path(self):
        with pytest.raises(SpecError, match="cannot resolve 'nope'"):
            resolve_path(Result(), "nope")

    def test_index_out_of_range(self):
        with pytest.raises(SpecError, match="out of range"):
            resolve_path((1, 2), "5")

    def test_empty_element(self):
        with pytest.raises(SpecError, match="empty element"):
            resolve_path(Result(), "spread..x")

    def test_missing_dict_key(self):
        with pytest.raises(SpecError, match="cannot resolve"):
            resolve_path({"a": 1}, "b")


class TestHowMany:
    """`length` on a step that returned a collection.

    Without it, "the scan found a device" could only be written as an
    expectation on element 0 - which *errors* on an empty list instead of
    failing a limit, and "nothing was found" is a test result rather than a
    broken bench.

    Traces to: RUN-FR-013.
    """

    def test_a_list(self):
        assert resolve_path([1, 2, 3], "length") == 3

    def test_an_empty_list_is_zero_rather_than_an_error(self):
        assert resolve_path([], "length") == 0

    def test_a_mapping_key_of_that_name_still_wins(self):
        """A driver that returns a dict with a 'length' key means that key."""
        assert resolve_path({"length": 9}, "length") == 9

    def test_count_is_not_borrowed_from_list(self):
        """`list.count` exists and means something else entirely; asking for it
        must not silently call it."""
        with pytest.raises(SpecError):
            resolve_path([1, 2, 3], "count")


class TestReferences:
    """Values carried from one step to a later one.

    A bench test is rarely a list of independent actions: the identifier read
    off a part decides which radio to connect to. Writing that identifier into
    the specification instead would make the test assert its own input.

    Traces to: RUN-FR-016.
    """

    def test_a_saved_value_is_resolved(self):
        reference = Reference.from_mapping({"from": "sensor_id"})
        assert reference.resolve({"sensor_id": 7}) == 7

    def test_a_path_into_a_saved_value(self):
        reference = Reference.from_mapping({"from": "build.version"})
        saved = {"build": Result()}
        assert reference.resolve({"build": {"version": "1.4.2"}}) == "1.4.2"
        assert saved  # the dataclass form is covered by resolve_path itself

    def test_a_format_renders_the_value(self):
        """The thing on the wire is often a rendering of the value rather than
        the value: an identifier appears in a device name as hex."""
        reference = Reference.from_mapping({"from": "id", "format": "{:06X}"})
        assert reference.resolve({"id": 0x0A1B2C}) == "0A1B2C"
        assert reference.resolve({"id": 1}) == "000001"
        assert Reference.from_mapping(
            {"from": "id", "format": "node-{:04d}"}
        ).resolve({"id": 7}) == "node-0007"

    def test_a_reference_to_a_step_that_has_not_run_says_what_has(self):
        """The likeliest mistake, and invisible in the specification itself."""
        reference = Reference.from_mapping({"from": "later"})
        with pytest.raises(SpecError, match="saved so far: earlier"):
            reference.resolve({"earlier": 1})

    def test_a_reference_with_no_name_is_refused(self):
        with pytest.raises(SpecError, match="must name a saved value"):
            Reference.from_mapping({"from": "  "})

    def test_an_unknown_key_is_refused(self):
        with pytest.raises(SpecError, match="only 'from' and 'format'"):
            Reference.from_mapping({"from": "id", "fromat": "typo"})

    def test_a_format_that_cannot_be_applied_names_the_value(self):
        reference = Reference.from_mapping({"from": "id", "format": "{:02X}"})
        with pytest.raises(SpecError, match="cannot be applied"):
            reference.resolve({"id": "not a number"})

    def test_references_are_found_wherever_they_are_written(self):
        parsed = parse_references(
            {"name": {"from": "id"}, "list": [1, {"from": "other"}], "plain": 5}
        )
        assert isinstance(parsed["name"], Reference)
        assert isinstance(parsed["list"][1], Reference)
        assert parsed["plain"] == 5

    def test_resolving_replaces_them_in_place(self):
        parsed = parse_references({"name": {"from": "id", "format": "{:06X}"}})
        assert resolve_references(parsed, {"id": 2}) == {"name": "000002"}

    def test_an_ordinary_mapping_is_left_alone(self):
        """A step argument that happens to be a mapping is not a reference."""
        arguments = {"limits": {"min": 1, "max": 2}}
        assert parse_references(arguments) == arguments
