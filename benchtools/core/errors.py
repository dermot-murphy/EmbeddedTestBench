"""Exception hierarchy for every tool in this repository.

All exceptions derive from :class:`BenchToolsError`, so a caller can guard an
entire measurement sequence - across any number of instruments and the test
runner - with a single ``except`` clause, without also swallowing unrelated
programming errors.

Traces to: CORE-NFR-005 (error handling), CORE-DD-ERR.
"""

from __future__ import annotations

__all__ = [
    "BenchToolsError",
    "TransportError",
    "ConnectionFailedError",
    "TransportTimeoutError",
    "ProtocolError",
    "UnsupportedTransportError",
    "InstrumentError",
    "ConfigurationError",
    "MeasurementError",
    "AcquisitionTimeoutError",
    "OptionalDependencyError",
    "BenchError",
    "SpecError",
    "BenchConfigError",
    "StepError",
]


class BenchToolsError(Exception):
    """Base class for every error raised by any tool in this repository."""


# --------------------------------------------------------------------------
# Transport layer
# --------------------------------------------------------------------------
class TransportError(BenchToolsError):
    """Base class for faults in the instrument link."""


class ConnectionFailedError(TransportError):
    """The link to the instrument could not be established."""


class TransportTimeoutError(TransportError):
    """An I/O operation on the instrument link did not complete in time."""


class ProtocolError(TransportError):
    """A malformed or unexpected response was received from the instrument."""


class UnsupportedTransportError(TransportError):
    """The requested transport backend is unknown or unavailable."""


# --------------------------------------------------------------------------
# Instrument / application layer
# --------------------------------------------------------------------------
class InstrumentError(BenchToolsError):
    """The instrument reported one or more entries in its event queue.

    :param message: Human readable summary.
    :param events: Sequence of ``(code, description)`` tuples as reported by the
        instrument's error queue (``SYSTem:ERRor?``, or a vendor equivalent).
    """

    def __init__(self, message: str, events=()) -> None:
        super().__init__(message)
        self.events = tuple(events)


class ConfigurationError(BenchToolsError, ValueError):
    """A requested setting is outside the capability of the instrument.

    Derives from :class:`ValueError` as well so that argument validation reads
    naturally to callers that already handle ``ValueError``.
    """


class MeasurementError(BenchToolsError):
    """A measurement could not be produced from the available data."""


class AcquisitionTimeoutError(BenchToolsError):
    """The instrument did not complete an acquisition within the timeout.

    Most commonly this means the trigger condition never occurred.
    """


class OptionalDependencyError(BenchToolsError):
    """An optional third-party package is required but is not installed."""


# --------------------------------------------------------------------------
# Test runner
# --------------------------------------------------------------------------
class BenchError(BenchToolsError):
    """Base class for faults in the bench test runner."""


class SpecError(BenchError):
    """A test specification is malformed or refers to something unknown."""


class BenchConfigError(BenchError):
    """The bench configuration is malformed or names an unknown instrument."""


class StepError(BenchError):
    """A test step failed to execute (as distinct from failing its limits)."""
