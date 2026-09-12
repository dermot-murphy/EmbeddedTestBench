"""Exception hierarchy for the Tektronix TDS3014B driver.

All exceptions raised by this package derive from :class:`Tek3014BError`, so a
caller can guard an entire measurement sequence with a single ``except`` clause
without also swallowing unrelated programming errors.

Traces to: SWE1-NFR-005 (error handling), SWE3-DD-ERR.
"""

from __future__ import annotations

__all__ = [
    "Tek3014BError",
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
]


class Tek3014BError(Exception):
    """Base class for every error raised by this package."""


# --------------------------------------------------------------------------
# Transport layer
# --------------------------------------------------------------------------
class TransportError(Tek3014BError):
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
class InstrumentError(Tek3014BError):
    """The instrument reported one or more entries in its event queue.

    :param message: Human readable summary.
    :param events: Sequence of ``(code, description)`` tuples as reported by
        the ``ALLEv?`` query.
    """

    def __init__(self, message: str, events=()) -> None:
        super().__init__(message)
        self.events = tuple(events)


class ConfigurationError(Tek3014BError, ValueError):
    """A requested setting is outside the capability of the instrument.

    Derives from :class:`ValueError` as well so that argument validation reads
    naturally to callers that already handle ``ValueError``.
    """


class MeasurementError(Tek3014BError):
    """A measurement could not be produced from the available data."""


class AcquisitionTimeoutError(Tek3014BError):
    """The instrument did not complete an acquisition within the timeout.

    Most commonly this means the trigger condition never occurred.
    """


class OptionalDependencyError(Tek3014BError):
    """An optional third-party package is required but is not installed."""
