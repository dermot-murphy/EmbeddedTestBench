"""Enumerations shared across instruments and analysis.

:class:`ScpiEnum` is the base every instrument's own enumerations derive from:
its value is the literal SCPI argument, and :meth:`ScpiEnum.coerce` accepts a
member, a member name or a mnemonic, case-insensitively. That is what lets
every public API in the repository take ``"rise"``, ``"RISE"`` or
``Slope.RISE`` interchangeably, and reject anything else with a message that
lists the valid values.

Only genuinely cross-instrument enumerations belong here. Anything specific to
one model belongs in that instrument's own ``constants`` module.

Traces to: CORE-FR-030, CORE-DD-ENUMS.
"""

from __future__ import annotations

import enum

__all__ = ["ScpiEnum", "EdgeDirection", "Slope"]


class ScpiEnum(str, enum.Enum):
    """Base for enumerations whose value is the literal SCPI argument."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    @classmethod
    def coerce(cls, value):
        """Return *value* as a member of this enumeration.

        Accepts an existing member, or a case-insensitive string matching
        either the member name or the SCPI mnemonic.

        :raises ValueError: if *value* cannot be resolved.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            token = value.strip().upper()
            for member in cls:
                if token in (member.name.upper(), str(member.value).upper()):
                    return member
        raise ValueError(
            "%r is not a valid %s; expected one of %s"
            % (value, cls.__name__, ", ".join(m.value for m in cls))
        )


class EdgeDirection(ScpiEnum):
    """Polarity of a signal transition.

    Used by host-side edge finding and by any instrument measurement that
    needs to name an edge.
    """

    RISE = "RISE"
    FALL = "FALL"


class Slope(ScpiEnum):
    """Trigger slope. Distinct from :class:`EdgeDirection` only in intent."""

    RISE = "RISE"
    FALL = "FALL"
