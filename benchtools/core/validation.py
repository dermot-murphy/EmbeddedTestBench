"""Setting validation shared by every instrument driver.

A setting is checked against the instrument's capability envelope *before* any
byte is sent. A partially applied setup is worse than a rejected one, because
it is silent: the instrument keeps running with a mixture of old and new
settings and the measurement that follows is quietly wrong.

Traces to: CORE-FR-031, CORE-NFR-004, CORE-DD-VALIDATE.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from .errors import ConfigurationError

__all__ = ["validate_range", "validate_channel", "validate_channels", "validate_choice"]


def validate_range(
    name: str,
    value: float,
    bounds: Tuple[float, float],
    unit: str = "",
) -> float:
    """Return *value* as a float, or raise if it falls outside *bounds*.

    :param name: What is being set, used in the message.
    :param bounds: Inclusive ``(low, high)``.
    :param unit: Appended to every number in the message, e.g. ``" V/div"``.
    :raises ConfigurationError: if out of range or not a number.
    """
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("%s must be a number, got %r" % (name, value)) from exc
    low, high = bounds
    if not low <= number <= high:
        raise ConfigurationError(
            "%s of %.6g%s is outside the instrument range %.6g%s to %.6g%s"
            % (name, number, unit, low, unit, high, unit)
        )
    return number


def validate_channel(channel: int, available: Sequence[int], model: str = "instrument") -> int:
    """Return *channel* as an int, or raise if the model does not have it."""
    try:
        number = int(channel)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("channel must be an integer, got %r" % (channel,)) from exc
    if number not in available:
        raise ConfigurationError(
            "channel %d is not available on the %s; valid channels are %s"
            % (number, model, ", ".join(str(c) for c in available))
        )
    return number


def validate_channels(
    channels: Iterable[int],
    available: Sequence[int],
    model: str = "instrument",
) -> List[int]:
    """Validate a collection of channels, rejecting duplicates.

    A duplicate is rejected rather than silently collapsed: it almost always
    means the caller built the list wrongly, and quietly returning fewer
    channels than were asked for would hide that.
    """
    validated = [validate_channel(channel, available, model) for channel in channels]
    if not validated:
        raise ConfigurationError("at least one channel must be given")
    duplicates = sorted({c for c in validated if validated.count(c) > 1})
    if duplicates:
        raise ConfigurationError(
            "channel(s) %s listed more than once" % ", ".join(str(c) for c in duplicates)
        )
    return validated


def validate_choice(name: str, value, allowed: Sequence) -> object:
    """Return *value* if it is in *allowed*, else raise."""
    if value not in allowed:
        raise ConfigurationError(
            "%s of %r is not supported; valid values are %s"
            % (name, value, ", ".join(str(item) for item in allowed))
        )
    return value
