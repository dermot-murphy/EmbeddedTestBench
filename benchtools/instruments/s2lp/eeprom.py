"""The RF board's identification EEPROM.

ST's S2-LP boards carry an EEPROM written at manufacture. ST's own firmware
reads its first page to set itself up (``S2LPManagementIdentificationRFBoard``
in ST's S2-LP middleware), and ST's CLI firmware exposes it through a command
its ``help`` hides: ``EepromReadPage <page> <offset> <count>``. It is the only
place the board says which band it was built for - ``SdkEvalRfboardIdentification``
reports nothing (#76, #80).

Page 0, as ST's middleware reads it:

====  ===========================================================
Byte  Meaning
====  ===========================================================
0     0x00 or 0xFF: nothing written; anything else: programmed
1     crystal: 0 24, 1 25, 2 26, 3 48, 4 50, 5 52 MHz
3     band: 0 169, 1 315, 2 433, 3 868, 4 915, 5 450 MHz
====  ===========================================================

Read on the bench kit on 2026-09-28: ``03 04 09 02 ...`` - programmed, a 50 MHz
crystal, the 433 MHz band, which is what its label says (STEVAL-FKI433V2).

Traces to: S2LP-FR-035, S2LP-DD-EEPROM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from .constants import BOARDS

__all__ = ["BoardEeprom", "parse_page0", "BAND_HZ", "XTAL_HZ", "BAND_RANGE_HZ"]

#: Byte 3: the band the board was built for, as ST's middleware maps it.
BAND_HZ: Dict[int, int] = {
    0: 169_000_000, 1: 315_000_000, 2: 433_000_000,
    3: 868_000_000, 4: 915_000_000, 5: 450_000_000,
}

#: Byte 1: the board's crystal.
XTAL_HZ: Dict[int, int] = {
    0: 24_000_000, 1: 25_000_000, 2: 26_000_000,
    3: 48_000_000, 4: 50_000_000, 5: 52_000_000,
}

#: The usable range for the bands this package has a board for.
BAND_RANGE_HZ: Dict[int, Tuple[int, int]] = {
    2: BOARDS["STEVAL-FKI433V2"],
    3: BOARDS["STEVAL-FKI868V2"],
    4: BOARDS["STEVAL-FKI915V1"],
}


@dataclass
class BoardEeprom:
    """What the board's EEPROM says about it.

    :param raw: Page 0 as read.
    """

    raw: bytes

    @property
    def programmed(self) -> bool:
        """False for a blank EEPROM, or none: ST treats 0x00 and 0xFF as absent."""
        return len(self.raw) >= 4 and self.raw[0] not in (0x00, 0xFF)

    @property
    def band_code(self) -> Optional[int]:
        """Byte 3, the band code, or ``None`` for a blank EEPROM."""
        return self.raw[3] if self.programmed else None

    @property
    def band_hz(self) -> Optional[int]:
        """The band's nominal frequency, e.g. 433 000 000."""
        return BAND_HZ.get(self.band_code) if self.band_code is not None else None

    @property
    def band_range_hz(self) -> Optional[Tuple[int, int]]:
        """The usable range, for the bands this package has a board for."""
        return BAND_RANGE_HZ.get(self.band_code) if self.band_code is not None else None

    @property
    def xtal_hz(self) -> Optional[int]:
        """The crystal byte 1 names, in hertz."""
        return XTAL_HZ.get(self.raw[1]) if self.programmed else None

    def matches(self, board: str) -> bool:
        """Whether *board*'s band is the one this EEPROM names."""
        return self.band_range_hz is None or BOARDS.get(board) == self.band_range_hz

    def as_dict(self) -> Dict[str, Any]:
        """The EEPROM as plain data, for JSON."""
        return {
            "programmed": self.programmed,
            "band_code": self.band_code,
            "band_hz": self.band_hz,
            "band_range_hz": list(self.band_range_hz) if self.band_range_hz else None,
            "xtal_hz": self.xtal_hz,
            "page0": self.raw.hex(),
        }


def parse_page0(values: Sequence[int]) -> BoardEeprom:
    """A :class:`BoardEeprom` from page 0's bytes as the firmware reported them."""
    return BoardEeprom(bytes(int(value) & 0xFF for value in values))
