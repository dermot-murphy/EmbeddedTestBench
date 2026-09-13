"""What is on the dongle, what the build produced, and how to reconcile them.

A bench dongle drifts out of date silently. Its firmware is part of the
measuring instrument, so a stale one produces results that look perfectly
plausible and answer a different question - and nothing about the numbers says
so. This module makes that condition detectable, reportable and, where the
tooling can, self-correcting.

Two facts identify a build, and both are needed:

* the **version**, which changes when someone deliberately changes behaviour;
* the **build date**, which distinguishes two builds of the *same* version -
  the usual case during development, and precisely when a stale dongle is most
  misleading.

The firmware reports both over its link; the build writes both into a manifest
beside the DFU package. Comparing the two is the whole of :class:`FirmwareStatus`.

Traces to: BLE-FR-012 .. BLE-FR-014, BLE-DD-FIRMWARE.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from ...core.errors import ConfigurationError, InstrumentError

__all__ = [
    "FirmwareBuild",
    "FirmwareStatus",
    "FirmwareUpdateError",
    "MANIFEST_NAME",
    "parse_build_date",
]

#: What the build writes, and what the driver looks for.
MANIFEST_NAME = "firmware_manifest.json"

#: Directories searched under a project root when given a directory rather than
#: a manifest. The first is where the Makefile puts its output.
_SEARCH = ("_build", ".", "build")


class FirmwareUpdateError(InstrumentError):
    """A firmware update could not be carried out."""


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
    def load(cls, where: Union[str, "FirmwareBuild", None]) -> Optional["FirmwareBuild"]:
        """Accept whatever a caller has: a build, a manifest, a directory, None."""
        if where is None or isinstance(where, FirmwareBuild):
            return where
        return cls.from_path(str(where))

    @classmethod
    def from_path(cls, path: str) -> "FirmwareBuild":
        """Read a manifest, or find one under a directory.

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
            "no firmware manifest found for %r (looked for %s). Build the "
            "firmware and run 'make manifest' - or 'make dfu', which writes one "
            "- in firmware/nordic_dongle."
            % (path, ", ".join(str(candidate) for candidate in candidates))
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

    def require_package(self) -> str:
        """The DFU package path, or a diagnostic saying how to produce one."""
        if not self.package:
            raise ConfigurationError(
                "the firmware manifest at %s names no DFU package. Run "
                "'make dfu' in firmware/nordic_dongle." % (self.source or "?")
            )
        if not os.path.isfile(self.package):
            raise ConfigurationError(
                "the DFU package %s named by %s does not exist. Run 'make dfu' "
                "in firmware/nordic_dongle." % (self.package, self.source or "?")
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


@dataclass
class FirmwareStatus:
    """What is on the dongle, against what was expected of it.

    Every field is a plain type so a declarative test can assert on it:
    ``measure: matches`` with ``equals: 1`` is the check worth putting in a
    specification, because a dongle running the wrong firmware invalidates every
    measurement taken with it.
    """

    installed_version: str = ""
    installed_built: str = ""
    expected_version: str = ""
    expected_built: str = ""
    compared: bool = False
    reason: str = ""
    package: Optional[str] = None
    updated: bool = False

    # ------------------------------------------------------------------
    @property
    def version_matches(self) -> bool:
        """True when the versions agree."""
        return bool(self.expected_version) and (self.installed_version == self.expected_version)

    @property
    def date_matches(self) -> bool:
        """True when the build dates agree.

        Two builds of one version are different firmware, and during development
        that is the common case.
        """
        return bool(self.expected_built) and (self.installed_built == self.expected_built)

    @property
    def matches(self) -> bool:
        """True when the dongle is running exactly the expected build."""
        return self.compared and self.version_matches and self.date_matches

    @property
    def installed_at(self) -> Optional[datetime]:
        return parse_build_date(self.installed_built)

    @property
    def expected_at(self) -> Optional[datetime]:
        return parse_build_date(self.expected_built)

    @property
    def is_older(self) -> Optional[bool]:
        """Whether the dongle predates the build, when both dates are instants.

        ``None`` when either side reported no unambiguous date, which is a
        different answer from "no": an unknown cannot be ordered.
        """
        installed = self.installed_at
        expected = self.expected_at
        if installed is None or expected is None:
            return None
        return installed < expected

    def describe(self) -> str:
        """One line, for a log or a diagnostic."""
        if not self.compared:
            return "dongle runs %s (built %s); nothing to compare against" % (
                self.installed_version or "?", self.installed_built or "unknown"
            )
        if self.matches:
            return "dongle runs the expected build: %s (built %s)" % (
                self.installed_version, self.installed_built
            )
        return (
            "dongle runs %s (built %s); the build is %s (built %s)"
            % (
                self.installed_version or "?",
                self.installed_built or "unknown",
                self.expected_version or "?",
                self.expected_built or "unknown",
            )
        )

    def as_dict(self) -> Dict[str, object]:
        """Flat mapping for a report or a limit check."""
        return {
            "installed_version": self.installed_version,
            "installed_built": self.installed_built,
            "expected_version": self.expected_version,
            "expected_built": self.expected_built,
            "compared": self.compared,
            "matches": self.matches,
            "version_matches": self.version_matches,
            "date_matches": self.date_matches,
            "is_older": self.is_older,
            "updated": self.updated,
            "package": self.package,
            "reason": self.reason or self.describe(),
        }

    def __str__(self) -> str:
        return self.describe()


def run_nrfutil(package: str, port: str, timeout: float = 180.0) -> str:
    """Flash *package* to a dongle in bootloader mode on *port*.

    Separated from the driver so a test can supply its own flasher, and so the
    one place that shells out is small enough to read.

    :returns: The tool's output, which is worth keeping in a log.
    :raises FirmwareUpdateError: if the tool is missing, fails, or hangs.
    """
    command = ["nrfutil", "dfu", "usb-serial", "-pkg", package, "-p", port]
    try:
        finished = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FirmwareUpdateError(
            "nrfutil is not installed, so the dongle cannot be updated from "
            "here. Install it with: pip install nrfutil"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FirmwareUpdateError(
            "nrfutil did not finish within %.0f s updating %s on %s"
            % (timeout, package, port)
        ) from exc

    output = (finished.stdout or "") + (finished.stderr or "")
    if finished.returncode != 0:
        raise FirmwareUpdateError(
            "nrfutil failed with status %d updating %s on %s:\n%s"
            % (finished.returncode, package, port, output.strip())
        )
    return output
