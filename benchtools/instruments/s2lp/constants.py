"""What the S2-LP development kit is, and the vocabulary its firmware speaks.

The command table here is the interface contract with **ST's own CLI firmware**
(the firmware the S2-LP DK GUI drives). It is written down so that a driver
mistake - a command that does not exist, or the wrong number of arguments -
fails as a named error in a test rather than as a timeout on the bench.

Nothing in this package is vendored from ST. The command names and argument
shapes are the interface; the register map is in :mod:`registers`; the values
below are the device's own constants, published in its datasheet.

Traces to: S2LP-FR-001 .. S2LP-FR-005, S2LP-DD-CONST.
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "MANUFACTURER",
    "MODEL",
    "BOARDS",
    "DEFAULT_BOARD",
    "Band",
    "DEFAULT_BAUDRATE",
    "DEFAULT_TIMEOUT",
    "STOP_CHARACTER",
    "Strobe",
    "Modulation",
    "PacketFormat",
    "COMMANDS",
    "FIFO_SIZE",
    "MAX_PAYLOAD",
    "REGISTER_COUNT",
    "DEFAULT_XTAL_HZ",
]

MANUFACTURER = "STMicroelectronics"
MODEL = "S2-LP DK"

#: Kit boards this driver is written for, and the band each one is built for.
#: The firmware is the same on all of them; the band decides what a frequency
#: setting means and which settings the hardware can actually reach.
BOARDS: Dict[str, Tuple[int, int]] = {
    "STEVAL-FKI915V1": (902_000_000, 928_000_000),
    "STEVAL-FKI868V2": (860_000_000, 870_000_000),
    "STEVAL-FKI433V2": (430_000_000, 440_000_000),
    "X-NUCLEO-S2915A1": (902_000_000, 928_000_000),
    "X-NUCLEO-S2868A1": (860_000_000, 870_000_000),
    "X-NUCLEO-S2868A2": (860_000_000, 870_000_000),
}

#: The kit this driver was written against.
DEFAULT_BOARD = "STEVAL-FKI915V1"


class Band:
    """The two sub-1 GHz bands these kits are built for."""

    ISM_868 = "868"
    ISM_915 = "915"
    ISM_433 = "433"


#: The CLI firmware's line rate, fixed in ST's firmware.
DEFAULT_BAUDRATE = 115200

#: Seconds to wait for a reply. ST's blocking receive holds the board for a
#: second at a time, so the default allows for that plus the link.
DEFAULT_TIMEOUT = 5.0

#: Sent on its own to stop a batch command early. ST's firmware polls the port
#: for this one character inside its capture loops (``checkStop()``), and it is
#: the only way to end a long capture without resetting the board.
STOP_CHARACTER = b"S"

#: The radio's FIFO, in bytes. A packet longer than this is sent in parts.
FIFO_SIZE = 128

#: Longest payload the CLI's byte-string argument carries in one command.
MAX_PAYLOAD = 255

#: Documented registers. Cross-checked against :mod:`registers`.
REGISTER_COUNT = 123

#: 0 asks the firmware to detect the crystal rather than be told it, which is
#: what the kit boards support and what the GUI does.
DEFAULT_XTAL_HZ = 0


class Strobe:
    """S2-LP command strobes, by their opcode."""

    TX = 0x60
    RX = 0x61
    READY = 0x62
    STANDBY = 0x63
    SLEEP = 0x64
    LOCK_RX = 0x65
    LOCK_TX = 0x66
    ABORT = 0x67
    LDC_RELOAD = 0x68
    RCO_CALIBRATION = 0x69
    RESET = 0x70
    FLUSH_RX_FIFO = 0x71
    FLUSH_TX_FIFO = 0x72
    SEQUENCE_UPDATE = 0x73

    #: Name to opcode, for a command line and for error messages.
    BY_NAME: Dict[str, int] = {
        "tx": TX, "rx": RX, "ready": READY, "standby": STANDBY, "sleep": SLEEP,
        "lock_rx": LOCK_RX, "lock_tx": LOCK_TX, "abort": ABORT,
        "ldc_reload": LDC_RELOAD, "rco_calibration": RCO_CALIBRATION,
        "reset": RESET, "flush_rx": FLUSH_RX_FIFO, "flush_tx": FLUSH_TX_FIFO,
        "sequence_update": SEQUENCE_UPDATE,
    }


class Modulation:
    """Modulation codes, as the MOD2 register encodes them."""

    FSK_2 = 0x00
    FSK_4 = 0x10
    GFSK_2_BT1 = 0x20
    GFSK_4_BT1 = 0x30
    ASK_OOK = 0x50
    POLAR = 0x60
    UNMODULATED = 0x70
    GFSK_2_BT05 = 0xA0
    GFSK_4_BT05 = 0xB0

    BY_NAME: Dict[str, int] = {
        "2-fsk": FSK_2, "4-fsk": FSK_4,
        "2-gfsk-bt1": GFSK_2_BT1, "4-gfsk-bt1": GFSK_4_BT1,
        "2-gfsk-bt0.5": GFSK_2_BT05, "4-gfsk-bt0.5": GFSK_4_BT05,
        "ook": ASK_OOK, "ask": ASK_OOK, "polar": POLAR,
        "cw": UNMODULATED, "unmodulated": UNMODULATED,
    }

    @classmethod
    def name_of(cls, code: int) -> str:
        """The name for a code, or its hex value when it is not one of these."""
        for name, value in cls.BY_NAME.items():
            if value == code and name not in ("ask", "unmodulated"):
                return name
        return "0x%02X" % code


class PacketFormat:
    """Packet handler formats, as PCKTCTRL3.PCKT_FRMT encodes them."""

    BASIC = 0
    MBUS = 2
    STACK = 3

    BY_NAME: Dict[str, int] = {"basic": BASIC, "mbus": MBUS, "stack": STACK}


#: ST CLI commands this driver uses, and the argument types ST's firmware
#: declares for each. The letters are ST's: u one-byte, v two-byte, w four-byte
#: unsigned, b byte string. Checked against every command the driver sends, so a
#: driver that drifts from the firmware fails in a test and not on the bench.
COMMANDS: Dict[str, str] = {
    # The motherboard's own SPI access: this is "all registers".
    "SdkEvalSpiReadRegisters": "uu",
    "SdkEvalSpiWriteRegisters": "ub",
    "SdkEvalSpiCommandStrobes": "u",
    "SdkEvalSpiReadFifo": "u",
    "SdkEvalSpiWriteFifo": "b",
    "SdkEvalRfboardIdentification": "w",
    "SdkEvalGetVersion": "",
    "SdkEvalSdn": "u",
    "SdkEvalLedHandler": "uu",
    # The radio.
    "S2LPRadioInit": "wuwwww",
    "S2LPRadioGetInfo": "",
    "S2LPRadioSetFrequencyBase": "w",
    "S2LPRadioGetFrequencyBase": "",
    "S2LPRadioSetModulation": "u",
    "S2LPRadioGetModulation": "",
    "S2LPRadioSetPALeveldBm": "wu",
    "S2LPRadioGetPALeveldBm": "u",
    "S2LPRadioGetXtalFrequency": "",
    "S2LPQiGetRssidBm": "",
    "S2LPGetVersion": "",
    "S2LPGetLibVersion": "",
    # The packet handler.
    "S2LPPktBasicInit": "vuwuuuuuu",
    "S2LPPktBasicGetInfo": "",
    "S2LPPktBasicSetPayloadLength": "v",
    "S2LPPktBasicGetPayloadLength": "",
    "S2LPGetPktFrmt": "",
    # Traffic.
    "S2LPSendNBytes": "b",
    "S2LPSendNBytesBatch": "wwb",
    "S2LPGetNBytes": "v",
    "S2LPGetNBytesBatch": "ww",
    "S2LPGetNBytesReportAll": "u",
    "S2LPTimerSetRxTimeoutUs": "w",
    "S2LPTimerGetRxTimeout": "",
    "S2LPIrq": "wu",
    "S2LPIrqGetStatus": "",
}
