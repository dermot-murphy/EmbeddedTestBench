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
beside the DFU package. Reading that manifest is the core's job
(:class:`benchtools.core.firmware.FirmwareBuild`, which the debug probe uses
too); comparing the two is the whole of :class:`FirmwareStatus`.

Traces to: BLE-FR-012 .. BLE-FR-014, BLE-DD-FIRMWARE.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Union

from ...core.errors import InstrumentError
from ...core.firmware import MANIFEST_NAME, FirmwareBuild, parse_build_date

__all__ = [
    "BUILD_HINT",
    "FirmwareBuild",
    "FirmwareStatus",
    "FirmwareUpdateError",
    "MANIFEST_NAME",
    "load_build",
    "parse_build_date",
]

#: How to produce a manifest for *this* firmware, for the diagnostic when there
#: is none. The reader of that message is usually someone who has just cloned
#: the repository and has no build yet.
BUILD_HINT = (
    "Build the firmware and run 'make manifest' - or 'make dfu', which writes "
    "one - in firmware/nordic_dongle."
)

#: How to produce the DFU package, which only flashing needs.
PACKAGE_HINT = "Run 'make dfu' in firmware/nordic_dongle."


class FirmwareUpdateError(InstrumentError):
    """A firmware update could not be carried out."""


def load_build(
    where: Union[str, FirmwareBuild, None],
) -> Optional[FirmwareBuild]:
    """Read a dongle build description, with this firmware's build hint.

    The manifest format is the core's (:mod:`benchtools.core.firmware`); what
    is local to the dongle is only how to produce one.
    """
    return FirmwareBuild.load(where, hint=BUILD_HINT)


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
