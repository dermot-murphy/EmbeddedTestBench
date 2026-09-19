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
    "length"           how many, for a step that returns a list
    "2.peak_to_peak"   result[2].peak_to_peak  (dict keyed by channel number)

Traces to: RUN-FR-013, RUN-FR-016, RUN-DD-RESOLVE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..core.errors import SpecError

__all__ = [
    "Reference",
    "parse_references",
    "resolve_path",
    "resolve_references",
]


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

    # How many, for a step that returns a collection. After the mapping and
    # index branches, so a dict with that key still wins, and before attributes
    # because a list already has a `count` method that means something else.
    # Without it "the scan found one device" could only be expressed by
    # addressing element 0, which errors when the list is empty instead of
    # failing a limit - and "nothing was found" is a test result, not a broken
    # bench.
    if token == "length" and isinstance(value, (list, tuple, dict, set, str)):
        return len(value)

    # Attribute, including a property.
    if hasattr(value, token):
        attribute = getattr(value, token)
        if not callable(attribute):
            return attribute
        try:
            return attribute()
        except TypeError as exc:
            # A method that needs arguments: `count` on a list, say. Saying so
            # is better than letting the call's own TypeError out, which reads
            # as a fault in the driver rather than in the path.
            raise SpecError(
                "path %r: %r on a %s takes arguments, so it cannot be read as "
                "a value (%s)" % (path, token, type(value).__name__, exc)
            ) from exc

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


@dataclass(frozen=True)
class Reference:
    """A value taken from an earlier step's saved result.

    A bench test is rarely a list of independent actions. The identifier read
    off a part decides which radio to connect to; the version a build produced
    decides what the firmware should report. Writing those values into the
    specification instead would make the test assert its own input - it would
    pass on the wrong board, and go stale the day the build changes.

    In a specification a reference is a mapping, and it is accepted anywhere an
    argument or a limit is::

        - do: probe.read_word
          with: {address: 0x10001080}
          save: sensor_id

        - do: dongle.scan
          with:
            name: {from: sensor_id, format: "SENS-{:02X}"}

    :param path: ``save`` name, optionally followed by a dotted path into that
        result - ``build.version`` is the ``version`` of whatever was saved as
        ``build``.
    :param format: Optional :meth:`str.format` template applied to the value,
        for the common case where the thing on the wire is a rendering of the
        number rather than the number. Empty means use the value itself.
    """

    path: str
    format: str = ""

    #: Key that marks a mapping in a specification as a reference.
    KEY = "from"

    @classmethod
    def is_reference(cls, data: Any) -> bool:
        """Whether *data* is a reference mapping rather than an ordinary value."""
        return isinstance(data, dict) and cls.KEY in data

    @classmethod
    def from_mapping(cls, data: Any) -> "Reference":
        data = dict(data)
        path = str(data.pop(cls.KEY, "")).strip()
        if not path:
            raise SpecError("a reference must name a saved value: {from: <name>}")
        template = str(data.pop("format", ""))
        if data:
            raise SpecError(
                "a reference takes only 'from' and 'format'; got %s"
                % ", ".join(sorted(data))
            )
        return cls(path=path, format=template)

    # ------------------------------------------------------------------
    def resolve(self, saved: Mapping[str, Any]) -> Any:
        """The referenced value, formatted if a template was given.

        :raises SpecError: if nothing was saved under that name, naming what
            has been. A reference to a step that has not run yet is the most
            likely mistake, and it is invisible in the specification itself.
        """
        head, _, rest = self.path.partition(".")
        if head not in saved:
            raise SpecError(
                "no step has saved %r; saved so far: %s"
                % (head, ", ".join(sorted(saved)) or "nothing")
            )
        value = resolve_path(saved[head], rest)
        if not self.format:
            return value
        try:
            return self.format.format(value)
        except (ValueError, TypeError, IndexError, KeyError) as exc:
            raise SpecError(
                "format %r cannot be applied to %r (from %s): %s"
                % (self.format, value, self.path, exc)
            ) from exc

    def __str__(self) -> str:
        return "<%s>" % self.path if not self.format else "<%s as %s>" % (self.path, self.format)


def parse_references(value: Any) -> Any:
    """Replace every reference mapping inside *value* with a :class:`Reference`.

    Applied when a specification is loaded, so a malformed reference is a load
    error rather than a surprise half way through a bench run.
    """
    if Reference.is_reference(value):
        return Reference.from_mapping(value)
    if isinstance(value, dict):
        return {key: parse_references(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(parse_references(item) for item in value)
    return value


def resolve_references(value: Any, saved: Mapping[str, Any]) -> Any:
    """Replace every :class:`Reference` inside *value* with what it refers to."""
    if isinstance(value, Reference):
        return value.resolve(saved)
    if isinstance(value, dict):
        return {key: resolve_references(item, saved) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(resolve_references(item, saved) for item in value)
    return value
