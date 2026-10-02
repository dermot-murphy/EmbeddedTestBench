"""Where the Test Bench monitor's data comes from, kept apart from the GUI.

* :class:`LiveRadio` owns the S2-LP kit through the benchtools driver and
  receives with the firmware's own loop (``stream(mode="batch")``, as ST's GUI
  receives) on a background thread, handing each packet to the GUI through a
  queue.
* :func:`spirit_line` renders a packet as the line ST's GUI writes to its log,
  which is what the monitor's frame parser (inherited from rf_monitor) reads -
  so every existing page decodes a live packet exactly as it decoded a logged
  one.
* :func:`st_gui_row` is a packet as ST's GUI displays it: time, byte count,
  RSSI, data in hex.
* :func:`event_row` formats a record from a bench event log
  (:mod:`benchtools.core.events`) or from the radio, and :func:`style_of`
  gives each source its label and colour: the defaults from
  :data:`SOURCE_STYLES`, and any other name a specification or bench declared
  (#126) a colour of its own. Names are upper case; a log written before #126
  carries them in lower case, and reads the same.

Traces to: SWE4-UT-TESTBENCH.
"""

from __future__ import annotations

import datetime
import queue
import re
import threading
import time
import zlib
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

#: Each default event source's label and colour on the Events page.
SOURCE_STYLES: Dict[str, Tuple[str, str]] = {
    "RF":    ("ST RF",  "#26c6da"),
    "PSU":   ("PSU",    "#ffb74d"),
    "BLE":   ("BLE",    "#64b5f6"),
    "JLINK": ("J-Link", "#81c784"),
    "TEST":  ("TEST",   "#fff176"),
    "SCOPE": ("SCOPE",  "#ce93d8"),
    "DMM":   ("DMM",    "#f48fb1"),
    "TEMP":  ("TEMP",   "#ff8a65"),
    "BENCH": ("BENCH",  "#7a8a9e"),
}

#: The order the default sources are offered in, on the Events page. Any other
#: name is added after them as it first appears.
SOURCE_ORDER = ("RF", "PSU", "BLE", "JLINK", "TEST", "SCOPE", "DMM", "TEMP", "BENCH")

#: Colours for a declared name that is not a default, chosen by the name so
#: one name keeps its colour from run to run.
_EXTRA_COLOURS = ("#4db6ac", "#aed581", "#ffd54f", "#9575cd", "#4fc3f7", "#e57373",
                  "#a1887f", "#90a4ae")


def source_key(source: Any) -> str:
    """The upper-case name a record's source is filed under; ``BENCH`` if it has none."""
    text = str(source or "").strip().upper()
    return text or "BENCH"


def style_of(source: str) -> Tuple[str, str]:
    """(label, colour) for a source key: a default's own, otherwise the name
    itself in a colour derived from it."""
    if source in SOURCE_STYLES:
        return SOURCE_STYLES[source]
    index = zlib.crc32(source.encode("ascii", "replace")) % len(_EXTRA_COLOURS)
    return source, _EXTRA_COLOURS[index]


def _local_time(packet) -> datetime.datetime:
    """The packet's host time, in local time."""
    try:
        moment = datetime.datetime.fromisoformat(packet.host_time)
    except (TypeError, ValueError):
        return datetime.datetime.now()
    return moment.astimezone() if moment.tzinfo else moment


def _clock(moment: datetime.datetime) -> str:
    """``HH:MM:SS.cc``, as ST's GUI writes time."""
    return moment.strftime("%H:%M:%S.") + "%02d" % (moment.microsecond // 10000)


def spirit_line(packet) -> str:
    """A received packet as ST's GUI logs it: the monitor's parser input."""
    rssi = int(round(packet.rssi_dbm)) if packet.rssi_dbm is not None else 0
    return "%s\tPacket received (%d bytes)\t%d\t%s" % (
        _clock(_local_time(packet)), packet.length, rssi,
        " ".join("%02X" % byte for byte in packet.data))


def st_gui_row(packet) -> Tuple[str, str, str, str]:
    """A packet as ST's GUI displays it: time, bytes, RSSI, data in hex.

    A reception the firmware rejected shows as ST's GUI shows it, with its
    reason in place of the data.
    """
    rssi = "%.1f" % packet.rssi_dbm if packet.rssi_dbm is not None else ""
    if not packet.ok:
        reason = {2: "Packet lost. CRC error"}.get(packet.error, "Packet lost. Error %d"
                                                  % packet.error)
        return _clock(_local_time(packet)), "", rssi, reason
    return (_clock(_local_time(packet)), str(packet.length), rssi,
            " ".join("%02X" % byte for byte in packet.data))


def rf_event(packet, decoded: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """An Events-page record for a packet the radio received."""
    moment = _local_time(packet)
    if not packet.ok:
        text = "rejected (error %d)" % packet.error
    elif decoded:
        text = "%s %s" % (decoded.get("sensor_id", "?"), decoded.get("type", "?"))
        if decoded.get("frame_of"):
            text += " frame %d of %d" % tuple(decoded["frame_of"])
        elif decoded.get("frame"):
            text += " frame %d of %d" % (decoded["frame"]["repeat"] + 1,
                                         decoded["frame"]["frames_per_packet"])
        text += ", %d bytes" % packet.length
    else:
        text = "%d bytes %s" % (packet.length, packet.hex[:24])
    if packet.rssi_dbm is not None:
        text += ", %.1f dBm" % packet.rssi_dbm
    return {"t": moment.timestamp(), "source": "RF", "level": "INFO", "text": text}


def event_row(record: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """(time, source key, source label, text) for one event record."""
    source = source_key(record.get("source"))
    stamp = record.get("t")
    when = (_clock(datetime.datetime.fromtimestamp(stamp))
            if isinstance(stamp, (int, float)) else "")
    return when, source, style_of(source)[0], str(record.get("text", ""))


class LiveRadio:
    """The S2-LP kit, receiving on a background thread.

    :param resource: The kit's port (``COM4``) or ``sim://``.
    :param board: Optional board name; the driver also reads the board's band
        from its EEPROM.
    :param setup: A register file to apply (with a reset to defaults) before
        receiving, e.g. ``configs/s2lp_kepler_433_rx.regs``.
    :param packet_log: Where the driver writes every packet, raw and decoded.
    """

    def __init__(self, resource: str, board: str = "", setup: Optional[str] = None,
                 packet_log: Optional[str] = None, decoder=None) -> None:
        from benchtools.instruments.s2lp import S2lpDevkit

        self.packets: "queue.Queue" = queue.Queue()
        self.error: Optional[str] = None
        self._stop = threading.Event()
        self._snapshot_lock = threading.Lock()
        self._decoder = decoder
        self.radio = S2lpDevkit.connect(resource, board=board, packet_log=packet_log)
        if setup:
            self.radio.apply_configuration(setup, reset="defaults")
        self.description = "%s on %s" % (self.radio.identify().model, resource)
        self._thread = threading.Thread(target=self._run, name="s2lp-receive", daemon=True)

    def start(self) -> "LiveRadio":
        self._thread.start()
        return self

    def _run(self) -> None:
        try:
            for packet in self.radio.stream(decoder=self._decoder, until=self._stop.is_set):
                self.packets.put(packet)
        except Exception as exc:                        # pylint: disable=broad-except
            self.error = "%s: %s" % (type(exc).__name__, exc)

    def snapshot(self) -> Dict[str, Any]:
        """Read the RF setup and every register, pausing reception to do it.

        The receive loop holds the kit's port, so it is stopped - the driver
        stops the board - the settings are read, and it is started again. The
        radio hears nothing for that second or so; the snapshot says how long.
        """
        with self._snapshot_lock:
            was_running = self._thread.is_alive()
            if was_running:
                self._stop.set()
                self._thread.join(timeout=10.0)
            started = time.monotonic()
            try:
                max_index = self.radio.read_field("PA_POWER0", "PA_LEVEL_MAX_IDX")
                snapshot = {
                    "radio": self.radio.radio_info(),
                    "registers": self.radio.read_all_registers(),
                    "power_dbm": self.radio.power_level_dbm(max_index),
                    "eeprom": self.radio.eeprom.as_dict() if self.radio.eeprom else None,
                }
            finally:
                snapshot_paused = time.monotonic() - started
                if was_running:
                    self._stop = threading.Event()
                    self._thread = threading.Thread(target=self._run, name="s2lp-receive",
                                                    daemon=True)
                    self._thread.start()
            snapshot["paused_s"] = snapshot_paused
            return snapshot

    def drain(self, limit: int = 500):
        """Packets received since the last call, oldest first."""
        out = []
        while len(out) < limit:
            try:
                out.append(self.packets.get_nowait())
            except queue.Empty:
                break
        return out

    def close(self) -> None:
        """Stop receiving - the driver stops the board - and close the kit."""
        self._stop.set()
        self._thread.join(timeout=5.0)
        self.radio.close()


class SimulatedAir(threading.Thread):
    """Puts Kepler frames on a simulated kit's air, for running without hardware.

    Sends one ALIVE packet - three repeats - every *interval* seconds, as the
    bench sensors do every ten minutes.
    """

    ALIVE = bytes.fromhex(
        "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005")

    def __init__(self, radio, interval: float = 5.0) -> None:
        super().__init__(name="simulated-air", daemon=True)
        self._kit = radio.transport.responder
        self._interval = interval
        self._stop = threading.Event()

    def run(self) -> None:
        count = 0
        while not self._stop.wait(self._interval):
            count += 1
            for repeat in range(3):
                frame = bytearray(self.ALIVE)
                frame[8] = ((repeat + 1) << 4) | 3
                frame[12:14] = (400 + count).to_bytes(2, "big")    # ticks move on
                self._kit.queue_packet(bytes(frame), rssi_dbm=-90.0 - repeat)

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------
# The ST GUI page's RF setup and register panels
# ---------------------------------------------------------------------------

_PACKET_FORMATS = {0: "Basic", 1: "802.15.4g", 2: "wM-Bus", 3: "STack"}
_CRC_MODES = {0: "none", 1: "8 bit (0x07)", 2: "16 bit (0x8005)", 3: "16 bit (0x1021)",
              4: "24 bit", 5: "32 bit"}
_TX_SOURCES = {0: "FIFO", 1: "direct via FIFO", 2: "direct via GPIO", 3: "PN9"}


def _field(values: Dict[int, int], name: str, field: str) -> int:
    from benchtools.instruments.s2lp import registers as reg

    register = reg.BY_NAME[name]
    return register.field(field).extract(values.get(register.address, register.reset))


def _bytes_msb(values: Dict[int, int], names) -> str:
    """A sync word stored least significant byte first, as 0x... ."""
    from benchtools.instruments.s2lp import registers as reg

    octets = [values.get(reg.BY_NAME[name].address, 0) for name in names]
    return "0x" + "".join("%02X" % octet for octet in reversed(octets))


def rf_setup_rows(snapshot: Dict[str, Any]):
    """(section, label, value) rows for the RF setup panel, from a snapshot.

    A snapshot is what :meth:`LiveRadio.snapshot` reads: ``radio`` (the
    driver's ``radio_info()``), ``registers`` (address to value), ``power_dbm``
    and ``eeprom``. Packet settings are decoded from the registers themselves.
    """
    radio = snapshot.get("radio") or {}
    values = snapshot.get("registers") or {}
    eeprom = snapshot.get("eeprom") or {}
    rows = []

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
    if snapshot.get("power_dbm") is not None:
        add("Radio", "Output power", "%.1f dBm" % snapshot["power_dbm"])
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
        add("Packet", "Address field", "yes" if _field(values, "PCKTCTRL4", "ADDRESS_LEN")
            else "no")
        add("Packet", "CRC", _CRC_MODES.get(_field(values, "PCKTCTRL1", "CRC_MODE"), "?"))
        add("Packet", "Whitening", "on" if _field(values, "PCKTCTRL1", "WHIT_EN") else "off")
        add("Packet", "FEC", "on" if _field(values, "PCKTCTRL1", "FEC_EN") else "off")
        add("Packet", "TX source", _TX_SOURCES.get(_field(values, "PCKTCTRL1", "TXSOURCE"), "?"))
        rx_timer = _field(values, "TIMERS5", "RX_TIMER_CNTR")
        add("Packet", "RX timeout", "infinite" if rx_timer == 0 else "counter %d" % rx_timer)
    return rows


def register_rows(values: Dict[int, int]):
    """(address, name, value, default, fields, changed) for every register read,
    as ST's GUI lists them: fields is ``[(field, value), ...]`` for expanding the
    row, and changed is a writable register no longer at its reset value."""
    from benchtools.instruments.s2lp import registers as reg

    rows = []
    for register in reg.REGISTERS:
        value = values.get(register.address)
        if value is None:
            continue
        rows.append(("0x%02X" % register.address, register.name, "0x%02X" % value,
                     "0x%02X" % register.reset, list(register.decode(value).items()),
                     register.writable and value != register.reset))
    return rows


def regs_text(values: Dict[int, int]) -> str:
    """The registers read, as a register file the driver's ``--setup`` applies:
    every writable register not at its reset value, applied over the defaults."""
    from benchtools.instruments.s2lp import registers as reg

    lines = ["# Exported by the Test Bench monitor. Apply with reset=defaults "
             "(the CLI's --setup does)."]
    for register in reg.REGISTERS:
        value = values.get(register.address)
        if value is None or not register.writable or value == register.reset:
            continue
        fields = " ".join("%s=%d" % item for item in register.decode(value).items())
        lines.append("%-22s 0x%02X   # %s" % (register.name, value, fields))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Instrument panels, rebuilt from the event log
#
# The monitor does not own the supply's or the probe's port - the test run
# does - so it rebuilds what their front panels would show from the traffic the
# run logs. A value is only what the log has said: None until it has said it.

_PSU_SET = re.compile(r"^(VSET|ISET)([12]):\s*([-+0-9.]+)$", re.IGNORECASE)
_PSU_QUERY = re.compile(r"^(VOUT|IOUT|VSET|ISET)([12])\?$", re.IGNORECASE)
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


class PsuPanel:
    """The GPD-3303D's front panel as the event log describes it.

    Feed it every ``psu`` record in order. ``channels`` holds, per channel, the
    set voltage and current limit (``vset``, ``iset``), the last readings
    (``vout``, ``iout``) and CV or CC (``mode``); ``output``, ``tracking`` and
    ``beep`` come from ``STATUS?`` and the ``OUT``/``BEEP`` commands. ``recent``
    is the last ten commands, each ``[time, command, reply]``.
    """

    RECENT = 10

    def __init__(self) -> None:
        self.identity: Optional[str] = None
        self.channels = {channel: {"vset": None, "iset": None, "vout": None, "iout": None,
                                   "mode": None} for channel in (1, 2)}
        self.output: Optional[bool] = None
        self.tracking: Optional[str] = None
        self.beep: Optional[bool] = None
        self.status_raw: Optional[str] = None
        self.problem: Optional[str] = None
        self.updated: Optional[float] = None
        self.recent: "deque" = deque(maxlen=self.RECENT)
        self._pending: Optional[str] = None

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; True if it was the supply's."""
        if record.get("source") != "psu":
            return False
        text = str(record.get("text", ""))
        when = record.get("t")
        self.updated = when if isinstance(when, (int, float)) else self.updated
        if record.get("level") in ("WARNING", "ERROR", "CRITICAL"):
            self.problem = text
        if text.startswith(">> "):
            self._command(text[3:].strip(), when)
        elif text.startswith("<< "):
            self._reply(text[3:].strip())
        return True

    def _command(self, command: str, when) -> None:
        self.recent.append([when, command, ""])
        self._pending = command if command.endswith("?") else None
        upper = command.upper()
        match = _PSU_SET.match(command)
        if match:
            key = "vset" if match.group(1).upper() == "VSET" else "iset"
            self.channels[int(match.group(2))][key] = float(match.group(3))
        elif upper in ("OUT0", "OUT1"):
            self.output = upper == "OUT1"
        elif upper in ("BEEP0", "BEEP1"):
            self.beep = upper == "BEEP1"
        elif upper.startswith("TRACK") and upper[5:].isdigit():
            from benchtools.instruments.gpd3303d.constants import TRACKING_MODES

            self.tracking = TRACKING_MODES.get(int(upper[5:]), upper)

    def _reply(self, reply: str) -> None:
        if self.recent and not self.recent[-1][2]:
            self.recent[-1][2] = reply
        query, self._pending = self._pending, None
        if query is None:
            return
        upper = query.upper()
        match = _PSU_QUERY.match(query)
        if match:
            number = _NUMBER.search(reply)
            if number:
                self.channels[int(match.group(2))][match.group(1).lower()] = float(
                    number.group(0))
        elif upper == "*IDN?":
            self.identity = reply
        elif upper == "STATUS?":
            self._status(reply)

    def _status(self, reply: str) -> None:
        from benchtools.instruments.gpd3303d.constants import (
            STATUS_BIT_BEEP, STATUS_BIT_OUTPUT, TRACKING_MODES)

        fields = reply.split() if " " in reply else list(reply)
        if len(fields) != 8:
            return
        flags = [field == "1" for field in fields]
        self.status_raw = reply
        for channel in (1, 2):
            self.channels[channel]["mode"] = "CV" if flags[channel - 1] else "CC"
        self.tracking = TRACKING_MODES.get((flags[2] << 1) | flags[3], "unknown")
        self.beep = flags[STATUS_BIT_BEEP]
        self.output = flags[STATUS_BIT_OUTPUT]


class JlinkPanel:
    """The J-Link's state as the event log describes it.

    Feed it every ``jlink`` record in order: the GDB/MI commands the driver
    sends, the probe's console and async records, RTT lines and the probe's
    own reports. ``rows()`` is the state for display; ``recent`` the last
    lines, each ``(time, kind, text)`` with kind one of ``command``,
    ``console``, ``async``, ``rtt``, ``info``, ``problem``.
    """

    RECENT = 500

    def __init__(self) -> None:
        self.server: Optional[str] = None
        self.probe: Optional[str] = None
        self.target: Optional[str] = None
        self.elf: Optional[str] = None
        self.core: Optional[str] = None
        self.stopped_at: Optional[str] = None
        self.flash: Optional[str] = None
        self.verify: Optional[str] = None
        self.rtt: Optional[str] = None
        self.rtt_lines = 0
        self.rtt_last: Optional[str] = None
        self.breakpoints = 0
        self.commands = 0
        self.last_command: Optional[str] = None
        self.problem: Optional[str] = None
        self.updated: Optional[float] = None
        self.recent: "deque" = deque(maxlen=self.RECENT)

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; True if it was the probe's."""
        if record.get("source") != "jlink":
            return False
        text = str(record.get("text", ""))
        when = record.get("t")
        self.updated = when if isinstance(when, (int, float)) else self.updated
        logger = str(record.get("logger", ""))
        level = record.get("level")
        if level in ("WARNING", "ERROR", "CRITICAL"):
            self.problem = text
            kind = "problem"
        elif text.startswith(">> "):
            self._command(re.sub(r"^\d+", "", text[3:].strip()))
            kind = "command"
        elif text.startswith("console "):
            self._console(text[8:].strip())
            kind = "console"
        elif text.startswith("async "):
            self._async(text[6:].strip())
            kind = "async"
        elif text.startswith("rtt: "):
            self.rtt_lines += 1
            self.rtt_last = text[5:]
            self.rtt = self.rtt or "started"
            kind = "rtt"
        else:
            self._info(logger, text)
            kind = "info"
        self.recent.append((when, kind, text))
        return True

    def _command(self, command: str) -> None:
        self.commands += 1
        self.last_command = command
        console = re.match(r'^-interpreter-exec console "(.*)"$', command)
        action = console.group(1) if console else command
        if action.startswith("-target-select"):
            self.target = action.split(None, 1)[1] if " " in action else action
        elif action.startswith("-file-exec-and-symbols"):
            self.elf = action.split(None, 1)[1].strip('"') if " " in action else None
        elif action in ("monitor reset", "monitor reset 0"):
            self.core = "reset"
            self.stopped_at = None
        elif action == "monitor halt":
            self.core = "halted"
        elif action in ("-target-detach", "-gdb-exit"):
            # The driver sends "monitor go" first unless told to leave it halted.
            self.core = "detached, core %s" % ("running" if self.core == "running" else
                                                self.core or "unknown")
        elif action in ("monitor go", "-exec-continue", "-exec-run", "continue"):
            self.core = "running"
            self.stopped_at = None
        elif action == "monitor rtt start":
            self.rtt = "starting"
        elif action == "monitor rtt stop":
            self.rtt = "stopped"
        elif action == "load":
            self.flash = "flashing..."
        elif action == "compare-sections":
            self.verify = "checking..."
        elif action.startswith("-break-insert"):
            self.breakpoints += 1
        elif action.startswith("-break-delete"):
            self.breakpoints = max(0, self.breakpoints - max(1, len(action.split()) - 1))

    def _console(self, text: str) -> None:
        lower = text.lower()
        if lower.startswith("segger"):
            self.probe = text
        elif lower.startswith("s/n:") and self.probe and "S/N" not in self.probe:
            self.probe += ", S/N %s" % text[4:].strip()
        elif lower.startswith("target halted"):
            self.core = "halted"
        elif lower.startswith("resetting target"):
            self.core = "reset"
        elif lower.startswith("rtt started"):
            self.rtt = "started"
        elif lower.startswith("section ") and self.verify is not None:
            if "mis-matched" in lower or "mismatch" in lower:
                self.verify = "MISMATCH: " + text
            elif self.verify == "checking...":
                self.verify = "match"

    def _async(self, text: str) -> None:
        if text.startswith("running"):
            self.core = "running"
            self.stopped_at = None
            return
        if not text.startswith("stopped"):
            return
        self.core = "halted"
        import ast

        try:
            results = ast.literal_eval(text[len("stopped"):].strip() or "{}")
        except (ValueError, SyntaxError):
            results = {}
        if not isinstance(results, dict):
            results = {}
        frame = results.get("frame") or {}
        where = frame.get("func") or frame.get("addr") or ""
        if frame.get("file") and frame.get("line"):
            where += " (%s:%s)" % (frame["file"], frame["line"])
        reason = results.get("reason", "")
        if reason == "breakpoint-hit" and results.get("bkptno"):
            reason += " %s" % results["bkptno"]
        self.stopped_at = ", ".join(part for part in (reason, where) if part) or None
        if results.get("disp") == "del":
            self.breakpoints = max(0, self.breakpoints - 1)

    def _info(self, logger: str, text: str) -> None:
        if logger.endswith(".server"):
            listening = re.search(r"listening on (\S+)", text)
            if listening:
                self.server = "listening on %s" % listening.group(1)
            elif text.startswith("starting"):
                self.server = "starting"
        elif text.startswith("flashed "):
            self.flash = text[len("flashed "):]
        elif "RTT line" in text:
            self.rtt = self.rtt or "started"

    def rows(self) -> List[Tuple[str, str]]:
        """(label, value) pairs for the state panel; unknown shows as a dash."""
        def show(value):
            return "-" if value in (None, "") else str(value)

        core = self.core
        if core == "halted" and self.stopped_at:
            core = "halted: %s" % self.stopped_at
        rtt = self.rtt
        if rtt or self.rtt_lines:
            rtt = "%s, %d line(s)" % (rtt or "started", self.rtt_lines)
        return [
            ("Probe", show(self.probe)),
            ("GDB server", show(self.server)),
            ("Target", show(self.target)),
            ("Firmware (ELF)", show(self.elf)),
            ("Core", show(core)),
            ("Last flash", show(self.flash)),
            ("Verify", show(self.verify)),
            ("Breakpoints", str(self.breakpoints)),
            ("RTT", show(rtt)),
            ("Last RTT line", show(self.rtt_last)),
            ("Commands sent", str(self.commands)),
            ("Last command", show(self.last_command)),
            ("Last problem", show(self.problem)),
        ]
