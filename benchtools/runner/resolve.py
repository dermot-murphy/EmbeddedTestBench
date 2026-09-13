"""Addressing values inside a step's return value.

A step calls a driver method, and driver methods return whatever suits them: a
float, a dataclass, a dict of channel to waveform, or a tuple of records and a
result object. A declarative specification needs a way to name the number it
wants to test out of that, without the runner knowing any driver's return type.

A path is a dotted sequence of accessors, applied left to right. Each element
is tried as a mapping key, then a sequence index, then an attribute, then a
zero-argument method::

    ""                 the whole result
    "spread"           result.spread
    "1.spread"         result[1].spread        (a tuple-returning method)
    "1.skews.3"        result[1].skews[3]
    "2.peak_to_peak"   result[2].peak_to_peak  (dict keyed by channel number)

Traces to: RUN-FR-013, RUN-DD-RESOLVE.
"""

from __future__ import annotations

from typing import Any

from ..core.errors import SpecError

__all__ = ["resolve_path"]


def _step(value: Any, token: str, path: str) -> Any:
    """Apply one path element to *value*."""
    # Mapping key, by string then by int: a dict keyed by channel number is
    # extremely common, and YAML gives us the key as a string.
    if isinstance(value, dict):
        if token in value:
            return value[token]
        try:
            numeric = int(token)
        except ValueError:
            numeric = None
        if numeric is not None and numeric in value:
            return value[numeric]

    # Sequence index.
    if isinstance(value, (list, tuple)):
        try:
            index = int(token)
        except ValueError:
            index = None
        if index is not None:
            if -len(value) <= index < len(value):
                return value[index]
            raise SpecError(
                "path %r: index %d is out of range for a sequence of %d"
                % (path, index, len(value))
            )

    # Attribute, including a property.
    if hasattr(value, token):
        attribute = getattr(value, token)
        return attribute() if callable(attribute) else attribute

    raise SpecError(
        "path %r: cannot resolve %r on a %s"
        % (path, token, type(value).__name__)
    )


def resolve_path(result: Any, path: str) -> Any:
    """Return the value named by *path* within *result*.

    :param path: Dotted accessor path; empty means the whole result.
    :raises SpecError: if any element cannot be resolved.
    """
    value = result
    if not path:
        return value
    for token in str(path).split("."):
        token = token.strip()
        if not token:
            raise SpecError("path %r has an empty element" % path)
        value = _step(value, token, path)
    return value
