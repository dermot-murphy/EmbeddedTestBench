"""The Embedded Test Bench monitor's ST GUI page: the S2-LP kit's RF setup and registers (#157).

ST's S2-LP DK GUI shows, on one screen, the kit's RF setup, its register table
and the frames it receives. The Embedded Test Bench monitor (#82) copied that layout,
reading the kit itself. The viewer cannot: the run owns the kit's port. So the
S2-LP driver logs what it reads as an ``rf_setup`` record (S2LP-FR-084), and
:class:`StGui` keeps the latest one per source. A refresh is a request to the
runner (``read_setup``, RUN-FR-066), which reads between steps.

The rows are ported from the monitor's ``sources.py`` (``rf_setup_rows``,
``register_rows``, ``regs_text``); the frames list is ST's: timestamp, bytes,
RSSI, data, a CRC failure as "Packet lost".

Traces to: VIEW-FR-043 .. VIEW-FR-045, VIEW-DD-STGUI.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..instruments.s2lp import registers as reg

__all__ = ["StGui", "rf_setup_rows", "register_rows", "regs_text", "st_row"]

_PACKET_FORMATS = {0: "Basic", 1: "802.15.4g", 2: "wM-Bus", 3: "STack"}
_CRC_MODES = {0: "none", 1: "8 bit (0x07)", 2: "16 bit (0x8005)", 3: "16 bit (0x1021)",
              4: "24 bit", 5: "32 bit"}
_TX_SOURCES = {0: "FIFO", 1: "direct via FIFO", 2: "direct via GPIO", 3: "PN9"}


def _field(values: Dict[int, int], name: str, field: str) -> int:
    register = reg.BY_NAME[name]
    return register.field(field).extract(values.get(register.address, register.reset))


def _bytes_msb(values: Dict[int, int], names) -> str:
    """A sync word stored least significant byte first, as ``0x...``."""
    octets = [values.get(reg.BY_NAME[name].address, 0) for name in names]
    return "0x" + "".join("%02X" % octet for octet in reversed(octets))


def rf_setup_rows(setup: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(section, label, value) rows for the RF setup panel, from a setup record."""
    radio = setup.get("radio") or {}
    values = setup.get("registers") or {}
    eeprom = setup.get("eeprom") or {}
    rows: List[Tuple[str, str, str]] = []

    def add(section, label, value):
        rows.append((section, label, value))

    band = eeprom.get("band_hz")
    add("Board", "Band (EEPROM)", "%.0f MHz" % (band / 1e6) if band else "unknown")
    add("Board", "Crystal", "%.6f MHz" % (radio["xtal_hz"] / 1e6) if radio.get("xtal_hz") else "")
    if radio:
        add("Radio", "Frequency base", "%.6f MHz" % (radio["frequency_hz"] / 1e6))
        add("Radio", "Modulation", str(radio.get("modulation_name", "")).upper())
        add("Radio", "Data rate", "%d bps" % radio["data_rate_bps"])
        add("Radio", "Frequency deviation", "%.3f kHz" % (radio["deviation_hz"] / 1e3))
        add("Radio", "Channel filter", "%.3f kHz" % (radio["bandwidth_hz"] / 1e3))
    if setup.get("power_dbm") is not None:
        add("Radio", "Output power", "%.1f dBm" % setup["power_dbm"])
    if values:
        add("Packet", "Format", _PACKET_FORMATS.get(_field(values, "PCKTCTRL3", "PCKT_FRMT"), "?"))
        preamble = ((_field(values, "PCKTCTRL6", "PREAMBLE_LEN_9_8") << 8)
                    | _field(values, "PCKTCTRL5", "PREAMBLE_LEN"))
        add("Packet", "Preamble", "%d pairs (%d bits)" % (preamble, 2 * preamble))
        add("Packet", "Sync length", "%d bits" % _field(values, "PCKTCTRL6", "SYNC_LEN"))
        add("Packet", "Sync word", _bytes_msb(values, ("SYNC3", "SYNC2", "SYNC1", "SYNC0")))
        dual = _field(values, "PCKTCTRL1", "SECOND_SYNC_SEL")
        add("Packet", "Second sync word",
            _bytes_msb(values, ("PCKT_FLT_GOALS3", "PCKT_FLT_GOALS2", "PCKT_FLT_GOALS1",
                                "PCKT_FLT_GOALS0")) + (" (on)" if dual else " (off)"))
        variable = _field(values, "PCKTCTRL2", "FIX_VAR_LEN")
        length = (_field(values, "PCKTLEN1", "PCKTLEN1") << 8) | _field(values, "PCKTLEN0",
                                                                       "PCKTLEN0")
        add("Packet", "Length", "variable" if variable else "fixed, %d bytes" % length)
        add("Packet", "Address field",
            "yes" if _field(values, "PCKTCTRL4", "ADDRESS_LEN") else "no")
        add("Packet", "CRC", _CRC_MODES.get(_field(values, "PCKTCTRL1", "CRC_MODE"), "?"))
        add("Packet", "Whitening", "on" if _field(values, "PCKTCTRL1", "WHIT_EN") else "off")
        add("Packet", "FEC", "on" if _field(values, "PCKTCTRL1", "FEC_EN") else "off")
        add("Packet", "TX source", _TX_SOURCES.get(_field(values, "PCKTCTRL1", "TXSOURCE"), "?"))
        rx_timer = _field(values, "TIMERS5", "RX_TIMER_CNTR")
        add("Packet", "RX timeout", "infinite" if rx_timer == 0 else "counter %d" % rx_timer)
    return rows


def register_rows(values: Dict[int, int]) -> List[Dict[str, Any]]:
    """Every register read, as ST's GUI lists them, with its fields, and whether a
    writable register is no longer at its reset value."""
    rows = []
    for register in reg.REGISTERS:
        value = values.get(register.address)
        if value is None:
            continue
        rows.append({"address": "0x%02X" % register.address, "name": register.name,
                     "value": "0x%02X" % value, "default": "0x%02X" % register.reset,
                     "fields": [list(item) for item in register.decode(value).items()],
                     "changed": bool(register.writable and value != register.reset)})
    return rows


def regs_text(values: Dict[int, int]) -> str:
    """The registers read, as a register file the driver's ``--setup`` applies:
    every writable register not at its reset value, applied over the defaults."""
    lines = ["# Exported by the benchtools test run viewer. Apply with reset=defaults "
             "(the CLI's --setup does)."]
    for register in reg.REGISTERS:
        value = values.get(register.address)
        if value is None or not register.writable or value == register.reset:
            continue
        fields = " ".join("%s=%d" % item for item in register.decode(value).items())
        lines.append("%-22s 0x%02X   # %s" % (register.name, value, fields))
    return "\n".join(lines) + "\n"


def st_row(frame: Dict[str, Any]) -> Dict[str, Any]:
    """A received frame as ST's GUI lists it."""
    when = frame.get("t")
    stamp = (datetime.datetime.fromtimestamp(when).strftime("%H:%M:%S.%f")[:11]
             if isinstance(when, (int, float)) else "")
    error = frame.get("error") or 0
    if error:
        data = "Packet lost. CRC error" if error == 2 else "Packet lost. Error %d" % error
        return {"t": when, "time": stamp, "bytes": "", "rssi": frame.get("rssi_dbm"),
                "data": data, "lost": True}
    hex_text = frame.get("hex", "")
    return {"t": when, "time": stamp, "bytes": len(hex_text) // 2, "rssi": frame.get("rssi_dbm"),
            "data": " ".join(hex_text[i:i + 2].upper() for i in range(0, len(hex_text), 2)),
            "lost": False}


class StGui:
    """The latest RF setup each S2-LP kit logged."""

    def __init__(self) -> None:
        self.setups: Dict[str, Dict[str, Any]] = {}

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; ``True`` if it was an ``rf_setup``."""
        data = record.get("data")
        if record.get("kind") != "rf_setup" or not isinstance(data, dict):
            return False
        registers = {}
        for address, value in (data.get("registers") or {}).items():
            try:
                registers[int(address)] = int(value)
            except (TypeError, ValueError):
                continue
        self.setups[str(record.get("source", ""))] = dict(data, registers=registers,
                                                          t=record.get("t"))
        return True

    def setup(self, source: str = "") -> Optional[Dict[str, Any]]:
        """The latest setup of *source*, or of the kit read most recently."""
        if source in self.setups:
            return self.setups[source]
        if not self.setups:
            return None
        return max(self.setups.values(), key=lambda item: item.get("t") or 0)

    def view(self, frames: List[Dict[str, Any]], source: str = "") -> Dict[str, Any]:
        """The page: RF setup rows, register rows, and ST's frames list."""
        setup = self.setup(source)
        rows = [st_row(frame) for frame in frames]
        if setup is None:
            return {"read": None, "setup": [], "registers": [], "frames": rows}
        return {"read": setup.get("t"), "setup": [list(row) for row in rf_setup_rows(setup)],
                "registers": register_rows(setup["registers"]), "frames": rows}
