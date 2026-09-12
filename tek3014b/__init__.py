"""Ethernet driver for the Tektronix TDS3014B digital phosphor oscilloscope.

Capabilities
------------
* Enable and configure up to four input channels: volts/division, screen
  position, offset, coupling and bandwidth limit.
* Configure the time base and an A-event edge trigger; arm single-sequence
  acquisitions and wait for the trigger.
* Capture waveform records from several channels of one acquisition, scaled to
  real seconds and volts, and export them to CSV.
* Capture the instrument's screen as a PNG (or another hardcopy format).
* Take measurements with the instrument's own engine (period, frequency,
  amplitude, rise time, two-source delay) and host-side over the captured
  records (period statistics with jitter, pulse widths, and the timing spread
  of an arbitrary number of channels switching).
* Plot captures host-side with the measured edges annotated.

Does this need VISA?
--------------------
No. The TDS3014B's Ethernet port runs an ONC-RPC VXI-11 server, which is an
open published protocol. :mod:`tek3014b.transport.vxi11` speaks it directly
using only the Python standard library, so the package has **no mandatory
third-party dependencies**. A PyVISA transport is included for sites already
standardised on VISA, and ``matplotlib`` is an optional extra needed only for
host-side plots. See ``docs/VISA_Determination_Report.md`` for the full
analysis and the evidence behind it.

Quick start
-----------
::

    from tek3014b import Tek3014B

    with Tek3014B.connect("192.168.1.50") as scope:
        print(scope.identity())
        scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0)
        scope.configure_channel(2, volts_per_div=1.0, position_div=2.0)
        scope.set_time_per_div(100e-9)
        scope.configure_edge_trigger(source=1, level=1.4)
        waveforms, spread = scope.measure_channel_spread([1, 2])
        print("spread: %.3f ns" % (spread.spread * 1e9))

Traces to: SWE2-ARC-001 (public API surface of the whole item).
"""

from .constants import (
    AcquisitionMode,
    Bandwidth,
    Coupling,
    DataEncoding,
    DelayDirection,
    EdgeDirection,
    HardcopyLayout,
    HardcopyPalette,
    ImageFormat,
    MeasurementType,
    ModelLimits,
    Slope,
    StopAfter,
    TDS3014B_LIMITS,
    TriggerMode,
    TriggerSource,
    TriggerState,
)
from .errors import (
    AcquisitionTimeoutError,
    ConfigurationError,
    ConnectionFailedError,
    InstrumentError,
    MeasurementError,
    OptionalDependencyError,
    ProtocolError,
    Tek3014BError,
    TransportError,
    TransportTimeoutError,
    UnsupportedTransportError,
)
from .measure import (
    EdgeCrossing,
    PeriodResult,
    SignalLevels,
    SpreadResult,
    estimate_levels,
    find_crossings,
    measure_channel_spread,
    measure_period,
    measure_pulse_width,
    measure_rise_time,
)
from .plotting import matplotlib_available, plot_waveforms
from .scope import ChannelSetup, Tek3014B
from .simulator import ChannelSignal, SimulatedTDS3014B
from .transport import (
    MockTransport,
    SocketTransport,
    Transport,
    VisaTransport,
    Vxi11Transport,
    open_transport,
    parse_resource,
    pyvisa_available,
)
from .waveform import Waveform, WaveformPreamble, waveforms_to_csv

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # Driver
    "Tek3014B",
    "ChannelSetup",
    # Transports
    "Transport",
    "Vxi11Transport",
    "SocketTransport",
    "VisaTransport",
    "MockTransport",
    "open_transport",
    "parse_resource",
    "pyvisa_available",
    # Data
    "Waveform",
    "WaveformPreamble",
    "waveforms_to_csv",
    # Measurement
    "EdgeCrossing",
    "SignalLevels",
    "PeriodResult",
    "SpreadResult",
    "estimate_levels",
    "find_crossings",
    "measure_period",
    "measure_pulse_width",
    "measure_rise_time",
    "measure_channel_spread",
    # Plotting
    "plot_waveforms",
    "matplotlib_available",
    # Simulation
    "SimulatedTDS3014B",
    "ChannelSignal",
    # Constants
    "AcquisitionMode",
    "Bandwidth",
    "Coupling",
    "DataEncoding",
    "DelayDirection",
    "EdgeDirection",
    "HardcopyLayout",
    "HardcopyPalette",
    "ImageFormat",
    "MeasurementType",
    "ModelLimits",
    "Slope",
    "StopAfter",
    "TriggerMode",
    "TriggerSource",
    "TriggerState",
    "TDS3014B_LIMITS",
    # Errors
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
