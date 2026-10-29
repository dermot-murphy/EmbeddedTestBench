"""The serial capture instrument's own error.

In a module of its own so that the command set (:mod:`.console`) can catch it
without importing the driver, which imports the command set.

Traces to: SER-FR-005, SER-DD-DRIVER.
"""

from __future__ import annotations

from ...core.errors import InstrumentError

__all__ = ["CaptureBusyError"]


class CaptureBusyError(InstrumentError):
    """A capture is running, and the request needs it stopped first."""
