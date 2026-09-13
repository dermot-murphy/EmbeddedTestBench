"""Instrument-agnostic foundations shared by every tool in this repository.

Nothing in this package knows about any particular instrument. That is the
point: the transport layer, the SCPI plumbing, the validation helpers and the
simulator harness are the same for an oscilloscope, a power supply, a DMM, a
signal generator, a spectrum analyser or a BLE tester.

Traces to: CORE-ARC-001 .. CORE-ARC-004.
"""

from .enums import EdgeDirection, ScpiEnum, Slope
from .errors import (
    AcquisitionTimeoutError,
    BenchToolsError,
    ConfigurationError,
    ConnectionFailedError,
    InstrumentError,
    MeasurementError,
    OptionalDependencyError,
    ProtocolError,
    TransportError,
    TransportTimeoutError,
    UnsupportedTransportError,
)
from .scpi import (
    InstrumentIdentity,
    ScpiInstrument,
    format_ieee_block,
    parse_ieee_block,
)
from .simulator import Responder, SimulatedInstrument, format_number, scpi_slug
from .transport import (
    MockTransport,
    SocketTransport,
    Transport,
    VisaTransport,
    Vxi11Transport,
    open_transport,
    parse_resource,
    pyvisa_available,
    register_backend,
)
from .validation import validate_channel, validate_channels, validate_choice, validate_range

__all__ = [
    "ScpiInstrument",
    "InstrumentIdentity",
    "parse_ieee_block",
    "format_ieee_block",
    "SimulatedInstrument",
    "Responder",
    "scpi_slug",
    "format_number",
    "ScpiEnum",
    "EdgeDirection",
    "Slope",
    "validate_range",
    "validate_channel",
    "validate_channels",
    "validate_choice",
    "Transport",
    "Vxi11Transport",
    "SocketTransport",
    "VisaTransport",
    "MockTransport",
    "open_transport",
    "parse_resource",
    "register_backend",
    "pyvisa_available",
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
]
