"""ST S2-LP sub-1 GHz development kit, over USB.

Driven through ST's own CLI firmware - the firmware the S2-LP DK GUI talks to -
or through the ETB kit firmware (``firmware/s2lp_kit``, #84), whichever the
board answers as.

Traces to: S2LP-FR-001 .. S2LP-FR-060, S2LP-FR-098 .. S2LP-FR-100, S2LP-ARC-001.
"""

from .configuration import (
    ConfigurationCheck,
    RegisterConfiguration,
    RegisterSetting,
    format_register_file,
    load_register_file,
    parse_register_file,
)
from .kit_firmware import KitSession, SimulatedKitFirmware
from .constants import BOARDS, CRC_MODES, DEFAULT_BOARD, MODEL, Modulation, PacketFormat, Strobe
from .packets import Capture, Packet, PacketLog, rssi_dbm_from_register, rssi_register_from_dbm
from .protocol import Reply, format_command, parse_reply
from .registers import BY_ADDRESS, BY_NAME, REGISTERS, Field, Register, lookup
from .s2lp import S2lpDevkit
from .session import S2lpSession
from .simulator import SimulatedS2lp

__all__ = [
    "S2lpDevkit",
    "SimulatedS2lp",
    "SimulatedKitFirmware",
    "KitSession",
    "S2lpSession",
    "RegisterConfiguration",
    "RegisterSetting",
    "ConfigurationCheck",
    "load_register_file",
    "parse_register_file",
    "format_register_file",
    "Packet",
    "Capture",
    "PacketLog",
    "Reply",
    "format_command",
    "parse_reply",
    "REGISTERS",
    "BY_NAME",
    "BY_ADDRESS",
    "Register",
    "Field",
    "lookup",
    "Modulation",
    "PacketFormat",
    "CRC_MODES",
    "Strobe",
    "BOARDS",
    "DEFAULT_BOARD",
    "MODEL",
    "rssi_dbm_from_register",
    "rssi_register_from_dbm",
]
