"""Addressing values inside a step's return value.

Traces to: RUN-FR-013, SWE4-UT-RESOLVE.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from benchtools.core.errors import SpecError
from benchtools.runner.resolve import resolve_path


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
