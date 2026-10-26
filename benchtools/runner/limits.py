"""Pass/fail limit checking.

A measured value on its own is not a test result. A limit turns it into one, and
the limit is the part a reviewer reads, so it is declared in the test
specification rather than buried in code.

Four forms are supported, and they compose: ``minimum`` and ``maximum`` give a
one- or two-sided bound, ``equals`` with ``tolerance`` gives a nominal value
with a window, and ``tolerance_percent`` expresses that window relative to the
nominal. Text has its own limit, :class:`TextLimit`: exact, one of a list, or a
regular expression with a reason, each optionally ignoring case (#242).

Traces to: RUN-FR-020 .. RUN-FR-024, RUN-FR-067, RUN-FR-068, RUN-DD-LIMITS.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from ..core.errors import SpecError

__all__ = ["Limit", "LimitOutcome", "TextLimit"]

#: A number as a reply writes one, for comparing with a number in ``one_of``.
_PLAIN_NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)")


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


@dataclass(frozen=True)
class TextLimit:
    """A bound on a value that is text, not a number.

    Not every pass criterion is numeric. "The firmware reports the version that
    was flashed onto it" is a bench test like any other, and before this there
    was no way to state it: every limit went through ``float()`` and a version
    string failed as "not a number" - an error, not a verdict.

    Exactly one of three forms (#242):

    * ``equals`` - the stripped text, exactly. The default, and the strictest:
      a limit that matched loosely would pass for a version that merely began
      with the right digits, which is the failure this exists to catch.
    * ``one_of`` - any of a list; an item that is a number is compared as a
      number, so ``one_of: [1, 2]`` passes ``2.0``.
    * ``matches`` - a regular expression the whole stripped text must match
      (``re.fullmatch``). Looser by design, so it needs a ``reason`` saying
      why the exact text cannot be known, which the report carries.

    ``ignore_case`` makes any form compare without regard to case, for text
    two sources spell differently: a VERSION frame and ``RD VERSION``.

    Traces to: RUN-FR-024, RUN-FR-067, RUN-FR-068.
    """

    equals: Optional[str] = None
    matches: Optional[str] = None
    one_of: Tuple[Any, ...] = ()
    ignore_case: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        for item in self.one_of:
            if item is None or isinstance(item, (bool, list, tuple, dict, set)):
                raise SpecError(
                    "one_of item %r is not a text or a number%s" % (
                        item, "; quote ON, OFF, YES and NO, which YAML reads as true and "
                        "false" if isinstance(item, bool) else ""))
            if isinstance(item, float) and not math.isfinite(item):
                raise SpecError("one_of item %r is not a finite number" % item)
        forms = [self.equals is not None, self.matches is not None, bool(self.one_of)]
        if sum(forms) != 1:
            raise SpecError("a text limit takes exactly one of equals, matches or one_of")
        if self.matches is not None:
            if not self.reason.strip():
                raise SpecError("a matches limit needs a reason: why the exact text "
                                "cannot be stated")
            try:
                re.compile(self.matches, re.IGNORECASE if self.ignore_case else 0)
            except re.error as exc:
                raise SpecError("matches %r is not a regular expression: %s"
                                % (self.matches, exc)) from exc

    @property
    def window(self) -> Optional[float]:
        """No numeric window applies to text; present for a common interface."""
        return None

    @property
    def text(self) -> str:
        """Human-readable rendering, as it appears in a report."""
        if self.matches is not None:
            text = "matches /%s/ (%s)" % (self.matches, self.reason.strip())
        elif self.one_of:
            text = "one of %s" % ", ".join('"%s"' % item for item in self.one_of)
        else:
            text = '= "%s"' % self.equals
        return text + (", ignoring case" if self.ignore_case else "")

    def _same(self, actual: str, wanted: Any) -> bool:
        if isinstance(wanted, (int, float)) and not isinstance(wanted, bool):
            # Only a plainly written number: float() also reads "1_0" and
            # "1e0", which no instrument reply means as 10 or 1.
            if _PLAIN_NUMBER.fullmatch(actual) is None:
                return False
            return float(actual) == float(wanted)
        if isinstance(wanted, (bytes, bytearray)):
            wanted = wanted.decode("utf-8", errors="replace")
        wanted = str(wanted).strip()
        if self.ignore_case:
            return actual.casefold() == wanted.casefold()
        return actual == wanted

    def check(self, value) -> LimitOutcome:
        """Check *value* against this limit, comparing as text."""
        text = self.text
        if value is None:
            return LimitOutcome(False, "no value was measured", text)
        actual = str(value).strip()
        if self.matches is not None:
            flags = re.IGNORECASE if self.ignore_case else 0
            if re.fullmatch(self.matches, actual, flags) is None:
                return LimitOutcome(
                    False, '"%s" does not match /%s/' % (actual, self.matches), text)
        elif self.one_of:
            if not any(self._same(actual, item) for item in self.one_of):
                return LimitOutcome(False, '"%s" is not %s' % (actual, text), text)
        elif not self._same(actual, self.equals):
            return LimitOutcome(
                False, '"%s" != required "%s"%s'
                % (actual, self.equals, " (ignoring case)" if self.ignore_case else ""), text)
        return LimitOutcome(True, "", text)
