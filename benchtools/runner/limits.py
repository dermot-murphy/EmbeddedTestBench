"""Pass/fail limit checking.

A measured value on its own is not a test result. A limit turns it into one, and
the limit is the part a reviewer reads, so it is declared in the test
specification rather than buried in code.

Four forms are supported, and they compose: ``minimum`` and ``maximum`` give a
one- or two-sided bound, ``equals`` with ``tolerance`` gives a nominal value
with a window, and ``tolerance_percent`` expresses that window relative to the
nominal.

Traces to: RUN-FR-020 .. RUN-FR-023, RUN-DD-LIMITS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ..core.errors import SpecError

__all__ = ["Limit", "LimitOutcome"]


@dataclass(frozen=True)
class LimitOutcome:
    """The result of checking one value against one limit.

    :param passed: Whether the value satisfied the limit.
    :param reason: Empty when passed; otherwise why it failed.
    :param text: Human-readable rendering of the limit itself.
    """

    passed: bool
    reason: str
    text: str


@dataclass(frozen=True)
class Limit:
    """A pass/fail bound on a measured value.

    :param minimum: Inclusive lower bound.
    :param maximum: Inclusive upper bound.
    :param equals: Nominal value; requires *tolerance* or *tolerance_percent*
        unless an exact match is intended.
    :param tolerance: Absolute half-window around *equals*.
    :param tolerance_percent: Half-window around *equals*, as a percentage of
        ``abs(equals)``.
    """

    minimum: Optional[float] = None
    maximum: Optional[float] = None
    equals: Optional[float] = None
    tolerance: Optional[float] = None
    tolerance_percent: Optional[float] = None

    def __post_init__(self) -> None:
        if all(
            bound is None
            for bound in (self.minimum, self.maximum, self.equals)
        ):
            raise SpecError(
                "a limit must set at least one of minimum, maximum or equals"
            )
        if self.equals is None and (self.tolerance is not None or self.tolerance_percent is not None):
            raise SpecError("tolerance is only meaningful alongside equals")
        if self.tolerance is not None and self.tolerance_percent is not None:
            raise SpecError("set tolerance or tolerance_percent, not both")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise SpecError(
                "limit minimum (%g) is above its maximum (%g)" % (self.minimum, self.maximum)
            )

    # ------------------------------------------------------------------
    @classmethod
    def from_mapping(cls, data) -> "Limit":
        """Build a limit from a specification mapping.

        Accepts ``min``/``max`` as aliases for ``minimum``/``maximum``, because
        that is what reads naturally in a YAML test specification.
        """
        if not isinstance(data, dict):
            raise SpecError("a limit must be a mapping, got %r" % (data,))
        aliases = {"min": "minimum", "max": "maximum", "nominal": "equals"}
        fields = {}
        allowed = {"minimum", "maximum", "equals", "tolerance", "tolerance_percent"}
        for key, value in data.items():
            name = aliases.get(key, key)
            if name not in allowed:
                continue
            try:
                fields[name] = float(value)
            except (TypeError, ValueError) as exc:
                raise SpecError("limit %s must be a number, got %r" % (key, value)) from exc
        return cls(**fields)

    @property
    def window(self) -> Optional[float]:
        """Absolute half-window implied by the tolerance settings."""
        if self.tolerance is not None:
            return abs(self.tolerance)
        if self.tolerance_percent is not None and self.equals is not None:
            return abs(self.equals) * (self.tolerance_percent / 100.0)
        return None

    @property
    def text(self) -> str:
        """Human-readable rendering, as it appears in a report."""
        parts = []
        if self.equals is not None:
            window = self.window
            if window is None:
                parts.append("= %g" % self.equals)
            elif self.tolerance_percent is not None:
                parts.append("= %g +/- %g%%" % (self.equals, self.tolerance_percent))
            else:
                parts.append("= %g +/- %g" % (self.equals, window))
        if self.minimum is not None:
            parts.append(">= %g" % self.minimum)
        if self.maximum is not None:
            parts.append("<= %g" % self.maximum)
        return ", ".join(parts)

    # ------------------------------------------------------------------
    def check(self, value: float) -> LimitOutcome:
        """Check *value* against this limit."""
        text = self.text
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return LimitOutcome(False, "value is not a number (%r)" % (value,), text)

        if self.equals is not None:
            window = self.window
            if window is None:
                if value != self.equals:
                    return LimitOutcome(
                        False, "%g != required %g" % (value, self.equals), text
                    )
            elif abs(value - self.equals) > window:
                return LimitOutcome(
                    False,
                    "%g is %g from nominal %g, outside +/- %g"
                    % (value, abs(value - self.equals), self.equals, window),
                    text,
                )
        if self.minimum is not None and value < self.minimum:
            return LimitOutcome(False, "%g is below the minimum %g" % (value, self.minimum), text)
        if self.maximum is not None and value > self.maximum:
            return LimitOutcome(False, "%g is above the maximum %g" % (value, self.maximum), text)
        return LimitOutcome(True, "", text)
