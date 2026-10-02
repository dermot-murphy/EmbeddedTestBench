"""Input files named by a relative path, found wherever the tools are started.

A specification and a bench file name the files a driver reads - a register
file, a command document, a firmware build - by a path relative to something.
Opened as given, that something is the current directory, so the same file is
found when the runner is started in the TestTools checkout and is not found
when it is started in the repository of the firmware under test, which is the
normal case. The test then errors for a reason that has nothing to do with the
thing under test (issue #116).

Two halves keep the knowledge where it belongs:

* A **driver** says which of its arguments are input files, with
  :func:`input_paths`. Only the driver knows that ``source`` on the S2-LP is a
  register file while ``source`` on the oscilloscope is a channel, so guessing
  from the name or the value would be wrong somewhere.
* The **runner** resolves those arguments with :func:`resolve_input_path`,
  because only the runner knows which file declared them.

A relative path is looked for, in order, beside the file that names it, in the
current directory, and in the TestTools checkout. The declaring file comes
first so a specification means the same thing wherever it is run from; the
current directory comes before the checkout so a bench file that names the
firmware repository's own ``build/`` keeps finding it there. Output paths are
not declared and are left alone: they are written relative to the current
directory, as they always were.

Traces to: RUN-FR-007, RUN-FR-017, CORE-DD-PATHS.
"""

from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Sequence, Tuple, TypeVar

from .errors import ConfigurationError

__all__ = [
    "TESTTOOLS_ROOT",
    "input_path_names",
    "input_paths",
    "resolve_arguments",
    "resolve_input_path",
    "search_locations",
]

#: The checkout this package was imported from: where the shipped ``configs/``,
#: ``specs/`` and ``benches/`` live. Installed as a package rather than run from
#: a checkout, nothing is found here, and the search moves on.
TESTTOOLS_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: Attribute :func:`input_paths` sets on the function it marks.
_ATTRIBUTE = "__benchtools_input_paths__"

_Function = TypeVar("_Function", bound=Callable[..., Any])


def input_paths(*names: str) -> Callable[[_Function], _Function]:
    """Mark the arguments of a driver method that name a file to be read.

    Apply it beneath ``@classmethod`` or ``@staticmethod``, to the function
    itself. The function is returned unchanged apart from the mark.

    :param names: Argument names that take an input path.
    """
    def mark(function: _Function) -> _Function:
        setattr(function, _ATTRIBUTE, tuple(names))
        return function
    return mark


def input_path_names(member: Any) -> Tuple[str, ...]:
    """Return the input-path argument names *member* declares, if any.

    Works on a plain function, a bound method, and a class or static method
    reached through its class, since each forwards attribute reads to the
    function :func:`input_paths` marked.
    """
    return tuple(getattr(member, _ATTRIBUTE, ()))


def search_locations(path: str, declared_in: Optional[str] = None) -> List[str]:
    """Return where a relative *path* is looked for, in order, without duplicates.

    :param declared_in: Directory of the file that names *path*; ``None`` when
        it came from no file, such as a bench built by ``--simulate``.
    """
    bases = [declared_in, os.getcwd(), TESTTOOLS_ROOT]
    found: List[str] = []
    for base in bases:
        if not base:
            continue
        candidate = os.path.normpath(os.path.join(os.path.abspath(base), path))
        if candidate not in found:
            found.append(candidate)
    return found


def resolve_input_path(
    value: Any,
    declared_in: Optional[str] = None,
    required: bool = True,
    what: str = "input file",
) -> Any:
    """Return *value* with a relative path replaced by the file it names.

    Anything that is not a string - a configuration already loaded, a parsed
    script, ``None`` - is returned unchanged, so a Python caller can still hand
    a driver an object instead of a path. An absolute path is returned as
    given: it means one thing already, and whether it exists is the driver's
    to report.

    :param declared_in: Directory of the file that names *value*.
    :param required: If no location holds the file, raise. Otherwise return
        *value* unchanged, so the driver decides - a simulated probe, for one,
        does not read its ELF file at all.
    :param what: What the path is, for the error message.
    :raises ConfigurationError: if *required* and the file is in none of the
        locations searched. The message lists every one of them.
    """
    if not isinstance(value, str) or not value or os.path.isabs(value):
        return value
    locations = search_locations(value, declared_in)
    for candidate in locations:
        if os.path.exists(candidate):
            return candidate
    if required:
        raise ConfigurationError(
            "cannot find %s %r; looked in: %s" % (what, value, ", ".join(locations))
        )
    return value


def resolve_arguments(
    arguments: dict,
    names: Sequence[str],
    declared_in: Optional[str] = None,
    required: bool = True,
    what: str = "argument",
) -> dict:
    """Return a copy of *arguments* with each of *names* resolved.

    :param what: Prefix for the error message, e.g. ``"s2lp.apply_configuration"``.
    """
    resolved = dict(arguments)
    for name in names:
        if name in resolved:
            resolved[name] = resolve_input_path(
                resolved[name],
                declared_in,
                required=required,
                what="%s %s" % (what, name),
            )
    return resolved
