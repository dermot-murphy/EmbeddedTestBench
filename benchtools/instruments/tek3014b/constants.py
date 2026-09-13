"""TDS3014B constants, SCPI mnemonics and capability limits.

Every SCPI mnemonic used by the driver is defined here exactly once so that the
command vocabulary can be reviewed against the *TDS3000, TDS3000B and TDS3000C
Series Programmer Manual* (Tektronix 071-0381-03) in a single place.

Enumeration values are the **short-form** SCPI mnemonics accepted by the
instrument; the long forms are accepted by the scope too but the short forms
keep the command strings compact on a 10 Mbit/s link.

Only TDS3000-family specifics live here. Enumerations that mean the same
thing on every instrument (:class:`~benchtools.core.enums.ScpiEnum`,
:class:`~benchtools.core.enums.EdgeDirection`) come from the shared core.

Traces to: SCOPE-FR-010, SCOPE-FR-020, SCOPE-FR-030, SCOPE-DD-CONST.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from ...core.enums import EdgeDirection, ScpiEnum

__all__ = [
    "ScpiEnum",
    "EdgeDirection",
    "Coupling",
    "Bandwidth",
    "Slope",
    "TriggerMode",
    "TriggerSource",
    "TriggerState",
    "AcquisitionMode",
    "StopAfter",
    "DataEncoding",
    "MeasurementType",
    "EdgeDirection",
    "DelayDirection",
    "ImageFormat",
    "HardcopyPalette",
    "HardcopyLayout",
    "ModelLimits",
    "TDS3014B_LIMITS",
    "INVALID_MEASUREMENT",
]


class Coupling(ScpiEnum):
    """Vertical input coupling (``CH<x>:COUPling``)."""

    AC = "AC"
    DC = "DC"
    GND = "GND"


class Bandwidth(ScpiEnum):
    """Vertical bandwidth limit (``CH<x>:BANdwidth``)."""

    TWENTY_MHZ = "TWENTY"
    ONE_FIFTY_MHZ = "ONEFIFTY"
    FULL = "FULL"


class Slope(ScpiEnum):
    """Edge trigger slope (``TRIGger:A:EDGE:SLOpe``)."""

    RISE = "RISE"
    FALL = "FALL"


class TriggerMode(ScpiEnum):
    """A-event trigger mode (``TRIGger:A:MODe``)."""

    AUTO = "AUTO"
    NORMAL = "NORMAL"


class TriggerSource(ScpiEnum):
    """Edge trigger source (``TRIGger:A:EDGE:SOUrce``)."""

    CH1 = "CH1"
    CH2 = "CH2"
    CH3 = "CH3"
    CH4 = "CH4"
    EXT = "EXT"
    EXT10 = "EXT10"
    LINE = "LINE"

    @classmethod
    def from_channel(cls, channel: int) -> "TriggerSource":
        """Return the trigger source for analogue input *channel* (1..4)."""
        return cls.coerce("CH%d" % int(channel))


class TriggerState(ScpiEnum):
    """Values returned by ``TRIGger:STATE?``."""

    ARMED = "ARMED"
    AUTO = "AUTO"
    READY = "READY"
    SAVE = "SAVE"
    TRIGGER = "TRIGGER"


class AcquisitionMode(ScpiEnum):
    """Acquisition mode (``ACQuire:MODe``)."""

    SAMPLE = "SAMPLE"
    PEAK_DETECT = "PEAKDETECT"
    AVERAGE = "AVERAGE"
    ENVELOPE = "ENVELOPE"


class StopAfter(ScpiEnum):
    """Acquisition stop condition (``ACQuire:STOPAfter``)."""

    RUN_STOP = "RUNSTOP"
    SEQUENCE = "SEQUENCE"


class DataEncoding(ScpiEnum):
    """Waveform transfer encoding (``DATa:ENCdg``).

    ``RIBINARY`` (signed, big-endian) is the driver default: it is roughly five
    times more compact than ``ASCII`` on the wire and needs no text parsing.
    """

    ASCII = "ASCII"
    RIBINARY = "RIBINARY"
    RPBINARY = "RPBINARY"
    SRIBINARY = "SRIBINARY"
    SRPBINARY = "SRPBINARY"


class MeasurementType(ScpiEnum):
    """Immediate measurement type (``MEASUrement:IMMed:TYPe``)."""

    AMPLITUDE = "AMPLITUDE"
    AREA = "AREA"
    BURST = "BURST"
    CYCLE_AREA = "CAREA"
    CYCLE_MEAN = "CMEAN"
    CYCLE_RMS = "CRMS"
    DELAY = "DELAY"
    FALL = "FALL"
    FREQUENCY = "FREQUENCY"
    HIGH = "HIGH"
    LOW = "LOW"
    MAXIMUM = "MAXIMUM"
    MEAN = "MEAN"
    MINIMUM = "MINIMUM"
    NEGATIVE_DUTY = "NDUTY"
    NEGATIVE_OVERSHOOT = "NOVERSHOOT"
    NEGATIVE_WIDTH = "NWIDTH"
    NONE = "NONE"
    PERIOD = "PERIOD"
    PHASE = "PHASE"
    PEAK_TO_PEAK = "PK2PK"
    POSITIVE_DUTY = "PDUTY"
    POSITIVE_OVERSHOOT = "POVERSHOOT"
    POSITIVE_WIDTH = "PWIDTH"
    RISE = "RISE"
    RMS = "RMS"


class DelayDirection(ScpiEnum):
    """Search direction for ``MEASUrement:IMMed:DELay:DIRection``."""

    FORWARDS = "FORWARDS"
    BACKWARDS = "BACKWARDS"


class ImageFormat(ScpiEnum):
    """Hardcopy image format (``HARDCopy:FORMat``)."""

    PNG = "PNG"
    TIFF = "TIFF"
    BMP = "BMP"
    BMP_COLOR = "BMPCOLOR"
    JPEG = "JPEG"
    PCX = "PCX"
    PCX_COLOR = "PCXCOLOR"
    RLE = "RLE"
    EPSIMAGE = "EPSIMAGE"

    @property
    def suffix(self) -> str:
        """Return the conventional file-name suffix for this format."""
        return {
            ImageFormat.PNG: ".png",
            ImageFormat.TIFF: ".tif",
            ImageFormat.BMP: ".bmp",
            ImageFormat.BMP_COLOR: ".bmp",
            ImageFormat.JPEG: ".jpg",
            ImageFormat.PCX: ".pcx",
            ImageFormat.PCX_COLOR: ".pcx",
            ImageFormat.RLE: ".rle",
            ImageFormat.EPSIMAGE: ".eps",
        }[self]


class HardcopyPalette(ScpiEnum):
    """Hardcopy colour palette (``HARDCopy:PALEtte``)."""

    COLOR = "COLOR"
    INKSAVER = "INKSAVER"
    BLACK_AND_WHITE = "BLACKANDWHITE"


class HardcopyLayout(ScpiEnum):
    """Hardcopy page orientation (``HARDCopy:LAYout``)."""

    LANDSCAPE = "LANDSCAPE"
    PORTRAIT = "PORTRAIT"


#: Value returned by the instrument when a measurement cannot be computed.
#: The programmer manual specifies 9.9E37 as the "invalid data" sentinel.
INVALID_MEASUREMENT = 9.9e37

@dataclass(frozen=True)
class ModelLimits:
    """Capability envelope used to validate settings before they are sent.

    Defaults describe the TDS3014B. Instantiate a different object and pass it
    to :class:`~tek3014b.scope.Tek3014B` to drive another member of the family
    or to deliberately relax a limit.

    All ranges are inclusive.
    """

    model: str = "TDS3014B"
    channel_count: int = 4
    analogue_bandwidth_hz: float = 100.0e6
    max_sample_rate_hz: float = 1.25e9
    volts_per_div_range: Tuple[float, float] = (1.0e-3, 10.0)
    position_div_range: Tuple[float, float] = (-5.0, 5.0)
    offset_volts_range: Tuple[float, float] = (-100.0, 100.0)
    seconds_per_div_range: Tuple[float, float] = (4.0e-9, 10.0)
    trigger_level_range: Tuple[float, float] = (-100.0, 100.0)
    record_lengths: Tuple[int, ...] = (500, 10000)
    average_counts: Tuple[int, ...] = (2, 4, 8, 16, 32, 64, 128, 256, 512)
    #: Vertical graticule height in divisions, used to sanity-check captures.
    vertical_divisions: float = 10.0
    #: Horizontal graticule width in divisions.
    horizontal_divisions: float = 10.0
    #: Bandwidth-limit settings this model actually implements.
    bandwidth_options: Tuple[Bandwidth, ...] = field(
        default_factory=lambda: (Bandwidth.TWENTY_MHZ, Bandwidth.FULL)
    )

    @property
    def channels(self) -> Tuple[int, ...]:
        """Return the valid channel numbers, e.g. ``(1, 2, 3, 4)``."""
        return tuple(range(1, self.channel_count + 1))


#: Capability envelope for the TDS3014B (4 channels, 100 MHz, 1.25 GS/s).
TDS3014B_LIMITS = ModelLimits()
