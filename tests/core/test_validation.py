"""Shared validation helpers and enumerations.

Traces to: CORE-FR-030, CORE-FR-031, CORE-NFR-004, SWE4-UT-VALIDATE.
"""

from __future__ import annotations

import pytest

from benchtools.core.enums import EdgeDirection, ScpiEnum, Slope
from benchtools.core.errors import ConfigurationError
from benchtools.core.validation import (
    validate_channel,
    validate_channels,
    validate_choice,
    validate_range,
)


class TestScpiEnum:
    def test_member_passes_through(self):
        assert Slope.coerce(Slope.RISE) is Slope.RISE

    @pytest.mark.parametrize("value", ["RISE", "rise", " Rise "])
    def test_case_and_whitespace_insensitive(self, value):
        assert Slope.coerce(value) is Slope.RISE

    def test_value_is_the_scpi_mnemonic(self):
        assert str(EdgeDirection.FALL) == "FALL"

    def test_unknown_value_lists_the_alternatives(self):
        with pytest.raises(ValueError, match="RISE, FALL"):
            Slope.coerce("sideways")

    def test_non_string_is_rejected(self):
        with pytest.raises(ValueError):
            Slope.coerce(7)

    def test_subclassing_works_for_instrument_enums(self):
        class Range(ScpiEnum):
            LOW = "LOW"
            HIGH = "HIGH"

        assert Range.coerce("high") is Range.HIGH


class TestValidateRange:
    def test_value_inside_bounds_is_returned_as_float(self):
        assert validate_range("v", 1, (0.0, 10.0)) == 1.0

    @pytest.mark.parametrize("value", [0.0, 10.0])
    def test_bounds_are_inclusive(self, value):
        assert validate_range("v", value, (0.0, 10.0)) == value

    @pytest.mark.parametrize("value", [-0.1, 10.1])
    def test_outside_bounds_is_rejected(self, value):
        with pytest.raises(ConfigurationError, match="outside the instrument range"):
            validate_range("volts/div", value, (0.0, 10.0), " V/div")

    def test_message_carries_the_unit(self):
        with pytest.raises(ConfigurationError, match="V/div"):
            validate_range("volts/div", 99.0, (0.0, 10.0), " V/div")

    def test_non_numeric_is_rejected(self):
        with pytest.raises(ConfigurationError, match="must be a number"):
            validate_range("v", "loud", (0.0, 10.0))


class TestValidateChannels:
    def test_valid_channel(self):
        assert validate_channel(2, (1, 2, 3, 4)) == 2

    def test_unavailable_channel_names_the_model(self):
        with pytest.raises(ConfigurationError, match="TDS3012B"):
            validate_channel(4, (1, 2), "TDS3012B")

    def test_non_integer_is_rejected(self):
        with pytest.raises(ConfigurationError, match="must be an integer"):
            validate_channel("two", (1, 2))

    def test_list_is_validated(self):
        assert validate_channels([3, 1], (1, 2, 3, 4)) == [3, 1]

    def test_empty_list_is_rejected(self):
        with pytest.raises(ConfigurationError, match="at least one channel"):
            validate_channels([], (1, 2, 3, 4))

    def test_duplicates_are_rejected(self):
        """Silently collapsing a duplicate would hide a caller's mistake."""
        with pytest.raises(ConfigurationError, match="more than once"):
            validate_channels([1, 2, 1], (1, 2, 3, 4))


class TestValidateChoice:
    def test_allowed_value(self):
        assert validate_choice("width", 2, (1, 2)) == 2

    def test_disallowed_value_lists_the_options(self):
        with pytest.raises(ConfigurationError, match="1, 2"):
            validate_choice("width", 4, (1, 2))
