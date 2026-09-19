"""A firmware build, as the build system described it.

A build writes a manifest beside its image; a driver reads it to learn what it
is about to put on a part, or what it just did. Two facts identify a build and
both are needed: the **version**, which changes when someone deliberately
changes behaviour, and the **build date**, which distinguishes two builds of the
same version - the usual case during development, and precisely when a stale
image is most misleading.

This lives in the core because more than one instrument needs it and none of
them should have to import another: the dongle reads a manifest to decide
whether to refresh itself, and the debug probe reads one to say what version it
has just flashed onto a target.

The error raised when there is no manifest takes a *hint* from the caller, so
the diagnostic can name the build that should have produced it rather than a
generic instruction.

Traces to: CORE-FR-050, BLE-FR-012, JLINK-FR-024, CORE-DD-FIRMWARE.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from .errors import ConfigurationError

__all__ = ["FirmwareBuild", "MANIFEST_NAME", "parse_build_date"]

#: What a build writes, and what a driver looks for.
MANIFEST_NAME = "firmware_manifest.json"

#: Directories searched under a project root when given a directory rather than
#: a manifest. The first is where the Makefiles put their output.
_SEARCH = ("_build", ".", "build")


def parse_build_date(text: str) -> Optional[datetime]:
    """Parse a build date as the firmware reports it.

    ISO 8601 UTC (``2026-09-13T14:22:31Z``) is what an injected date looks like.
    A build that did not inject one reports the compiler's macros, tagged
    ``local:`` - local time, no zone, not sortable - and this returns ``None``
    for those rather than inventing a timezone for them.

    :returns: An aware :class:`~datetime.datetime`, or ``None`` if the text is
        not an unambiguous instant.
    """
    value = (text or "").strip()
    if not value or value.startswith("local:"):
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


@dataclass
class FirmwareBuild:
    """A build of the dongle firmware, as the build system described it.

    :param version: From ``firmware_version.h``.
    :param built: ISO 8601 UTC instant, or a ``local:`` string from a build that
        injected no date.
    :param package: Path to the DFU package, when one was produced.
    :param source: Where this description was read from, for diagnostics.
    """

    version: str = ""
    built: str = ""
    protocol: str = ""
    model: str = ""
    package: Optional[str] = None
    hex_path: Optional[str] = None
    sha256: str = ""
    source: str = ""

    # ------------------------------------------------------------------
    @classmethod
    def load(
        cls,
        where: Union[str, "FirmwareBuild", None],
        hint: str = "",
    ) -> Optional["FirmwareBuild"]:
        """Accept whatever a caller has: a build, a manifest, a directory, None.

        :param hint: How to produce a manifest here, for the diagnostic.
        """
        if where is None or isinstance(where, FirmwareBuild):
            return where
        return cls.from_path(str(where), hint=hint)

    @classmethod
    def from_path(cls, path: str, hint: str = "") -> "FirmwareBuild":
        """Read a manifest, or find one under a directory.

        :param hint: Sentence appended to the diagnostic, saying how to produce
            a manifest for *this* build. Without it the message can only say
            that none was found, which leaves the reader guessing.
        :raises ConfigurationError: if no manifest is there, naming what was
            searched and how to produce one.
        """
        target = pathlib.Path(path)
        candidates = []
        if target.is_dir():
            candidates = [target / name / MANIFEST_NAME for name in _SEARCH]
            candidates += [target / MANIFEST_NAME]
        else:
            candidates = [target]

        for candidate in candidates:
            if candidate.is_file():
                return cls.from_manifest(str(candidate))

        raise ConfigurationError(
            "no firmware manifest found for %r (looked for %s).%s"
            % (
                path,
                ", ".join(str(candidate) for candidate in candidates),
                (" " + hint) if hint else "",
            )
        )

    @classmethod
    def from_manifest(cls, path: str) -> "FirmwareBuild":
        """Read a manifest written by the firmware build."""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as exc:
            raise ConfigurationError("cannot read %s: %s" % (path, exc)) from exc
        except ValueError as exc:
            raise ConfigurationError(
                "%s is not valid JSON: %s. It is written by the firmware build; "
                "rebuild rather than editing it." % (path, exc)
            ) from exc

        directory = os.path.dirname(os.path.abspath(path))
        package = data.get("package")
        hex_name = data.get("hex")
        return cls(
            version=str(data.get("version", "")),
            built=str(data.get("built", "")),
            protocol=str(data.get("protocol", "")),
            model=str(data.get("model", "")),
            package=os.path.join(directory, package) if package else None,
            hex_path=os.path.join(directory, hex_name) if hex_name else None,
            sha256=str(data.get("sha256", "")),
            source=os.path.abspath(path),
        )

    # ------------------------------------------------------------------
    @property
    def built_at(self) -> Optional[datetime]:
        """The build instant, or ``None`` if the build did not record one."""
        return parse_build_date(self.built)

    @property
    def has_package(self) -> bool:
        """True when a DFU package exists to flash."""
        return bool(self.package) and os.path.isfile(self.package)

    def require_package(self, hint: str = "") -> str:
        """The packaged image path, or a diagnostic saying how to produce one."""
        if not self.package:
            raise ConfigurationError(
                "the firmware manifest at %s names no package.%s"
                % (self.source or "?", (" " + hint) if hint else "")
            )
        if not os.path.isfile(self.package):
            raise ConfigurationError(
                "the package %s named by %s does not exist.%s"
                % (self.package, self.source or "?", (" " + hint) if hint else "")
            )
        return self.package

    def as_dict(self) -> Dict[str, object]:
        """Flat mapping for a report."""
        return {
            "version": self.version,
            "built": self.built,
            "protocol": self.protocol,
            "model": self.model,
            "package": self.package,
            "sha256": self.sha256,
            "source": self.source,
        }

    def __str__(self) -> str:
        return "%s (built %s)" % (self.version or "?", self.built or "unknown")
