"""Each instrument's commands paired with their replies, from the event log (#138).

When a step fails, the question is what each instrument was told and what it
answered. The event log has every line, but interleaved across instruments and
one line at a time. :class:`Traffic` sorts them per instrument into exchanges:
a command and the replies that followed it, with the time each took. Lines an
instrument sends unasked - a BLE scan report, a probe stopping at a
breakpoint, an RTT line - are events of their own, not replies.

The drivers mark their traffic in one of a few ways, all recognised here:

======================  ============  =======================================
Line                    Meaning       Drivers
======================  ============  =======================================
``>> text``             sent          SCPI instruments, supply, S2-LP, J-Link
``<< text``             received      the same
``> text``              sent          BLE dongle, thermometer
``< text``              received      the same; ``< +...`` is an event
``console text``        received      J-Link (GDB console output)
``async text``          event         J-Link (the target ran or stopped)
``rtt: text``           event         J-Link (a line from the target)
anything else           note          opened, closed, resolved, ...
======================  ============  =======================================

Panels (:class:`PsuPanel`, :class:`JlinkPanel`) rebuild a supply's and a
probe's front panel from the same lines. They are ported from the Test Bench
monitor (``tools/test_bench/sources.py``, #82), which is to be frozen once the
viewer replaces it (#142).

Traces to: VIEW-FR-010 .. VIEW-FR-012, VIEW-DD-TRAFFIC.
"""

from __future__ import annotations

import ast
import re
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

__all__ = ["classify", "Traffic", "PsuPanel", "JlinkPanel", "panel_for", "KEEP_EXCHANGES"]

#: Exchanges kept per instrument; older ones are dropped.
KEEP_EXCHANGES = 2000

SENT, RECEIVED, EVENT, NOTE = "sent", "received", "event", "note"


def classify(text: str) -> Tuple[str, str]:
    """``(kind, payload)`` for one line of an instrument's traffic."""
    for prefix, kind in ((">> ", SENT), ("<< ", RECEIVED), ("> ", SENT), ("< ", RECEIVED),
                         ("console ", RECEIVED), ("async ", EVENT), ("rtt: ", EVENT)):
        if text.startswith(prefix):
            payload = text[len(prefix):]
            if kind == RECEIVED and prefix == "< " and payload.startswith("+"):
                return EVENT, payload
            if kind == SENT and prefix == ">> ":
                payload = re.sub(r"^\d+(?=-)", "", payload)   # a GDB/MI token
            return kind, payload
    return NOTE, text


def _milliseconds(start: Optional[float], end: Optional[float]) -> Optional[float]:
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return round((end - start) * 1000.0, 3)
    return None


class Traffic:
    """Every instrument's exchanges, in order, per event-log source."""

    def __init__(self) -> None:
        self.sources: Dict[str, Deque[Dict[str, Any]]] = {}
        self.drivers: Dict[str, str] = {}
        self.counts: Dict[str, int] = {}
        #: Per source, the exchange whose replies are still arriving.
        self._open: Dict[str, Dict[str, Any]] = {}

    def clear(self) -> None:
        """Forget everything, for a new run."""
        self.sources.clear()
        self.drivers.clear()
        self.counts.clear()
        self._open.clear()

    def feed(self, record: Dict[str, Any]) -> bool:
        """Take one record; ``True`` if it was an instrument's traffic."""
        source = record.get("source")
        if not source or source == "TEST" or record.get("kind"):
            return False
        logger = str(record.get("logger", ""))
        if logger.startswith("benchtools.instruments."):
            self.drivers.setdefault(source, logger.split(".")[2])
        kind, payload = classify(str(record.get("text", "")))
        when = record.get("t")
        exchanges = self.sources.setdefault(source, deque(maxlen=KEEP_EXCHANGES))
        current = self._open.get(source)
        if kind == RECEIVED and current is not None:
            # Events in between - a scan report - do not end the command: its
            # reply may come after them.
            current["replies"].append(payload)
            if current["reply_t"] is None:
                current["reply_t"] = when
                current["ms"] = _milliseconds(current["t"], when)
            current["end_t"] = when
            return True
        entry = {"t": when, "end_t": when, "kind": kind, "text": payload,
                 "level": record.get("level")}
        if kind == SENT:
            entry.update(kind="exchange", replies=[], reply_t=None, ms=None)
            self._open[source] = entry
        elif kind == RECEIVED:
            entry["kind"] = "unasked"              # a reply with no command before it
        exchanges.append(entry)
        self.counts[source] = self.counts.get(source, 0) + 1
        return True

    def view(self, t0: Optional[float] = None, t1: Optional[float] = None,
             limit: int = 300) -> Dict[str, Any]:
        """Per source, the latest *limit* entries, or those between *t0* and *t1*.

        An exchange belongs to a window if its command was sent inside it.
        """
        listed: Dict[str, Any] = {}
        for source, entries in self.sources.items():
            chosen = [dict(entry, replies=list(entry["replies"])) if "replies" in entry
                      else dict(entry) for entry in entries
                      if (t0 is None or (entry["t"] or 0) >= t0)
                      and (t1 is None or (entry["t"] or 0) <= t1)]
            if t0 is None and t1 is None:
                chosen = chosen[-limit:]
            listed[source] = {"driver": self.drivers.get(source, ""),
                              "count": self.counts.get(source, 0), "entries": chosen}
        return listed


# ---------------------------------------------------------------------------
# Front panels, rebuilt from the traffic
#
# A value is only what the log has said: None until it has said it.

_PSU_SET = re.compile(r"^(VSET|ISET)([12]):\s*([-+0-9.]+)$", re.IGNORECASE)
_PSU_QUERY = re.compile(r"^(VOUT|IOUT|VSET|ISET)([12])\?$", re.IGNORECASE)
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _show(value: Any) -> str:
    return "-" if value in (None, "") else str(value)


class PsuPanel:
    """The GPD-3303D's front panel as its traffic describes it."""

    kind = "psu"

    def __init__(self) -> None:
        self.identity: Optional[str] = None
        self.channels = {channel: {"vset": None, "iset": None, "vout": None, "iout": None,
                                   "mode": None} for channel in (1, 2)}
        self.output: Optional[bool] = None
        self.tracking: Optional[str] = None
        self.beep: Optional[bool] = None
        self.problem: Optional[str] = None
        self._pending: Optional[str] = None

    def feed(self, record: Dict[str, Any]) -> None:
        """Take one of the supply's records."""
        text = str(record.get("text", ""))
        if record.get("level") in ("WARNING", "ERROR", "CRITICAL"):
            self.problem = text
        kind, payload = classify(text)
        if kind == SENT:
            self._command(payload.strip())
        elif kind == RECEIVED:
            self._reply(payload.strip())

    def _command(self, command: str) -> None:
        from ..instruments.gpd3303d.constants import TRACKING_MODES

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
            self.tracking = TRACKING_MODES.get(int(upper[5:]), upper)

    def _reply(self, reply: str) -> None:
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
        from ..instruments.gpd3303d.constants import (
            STATUS_BIT_BEEP, STATUS_BIT_OUTPUT, TRACKING_MODES)

        fields = reply.split() if " " in reply else list(reply)
        if len(fields) != 8:
            return
        flags = [field == "1" for field in fields]
        for channel in (1, 2):
            self.channels[channel]["mode"] = "CV" if flags[channel - 1] else "CC"
        self.tracking = TRACKING_MODES.get((flags[2] << 1) | flags[3], "unknown")
        self.beep = flags[STATUS_BIT_BEEP]
        self.output = flags[STATUS_BIT_OUTPUT]

    def rows(self) -> List[Tuple[str, str]]:
        """(label, value) pairs for display; unknown shows as a dash."""
        def channel(number: int) -> str:
            values = self.channels[number]
            unit = {"vset": "V", "iset": "A", "vout": "V", "iout": "A"}
            parts = ["%s %s %s" % (name, values[name], unit[name])
                     for name in ("vout", "iout", "vset", "iset") if values[name] is not None]
            if values["mode"]:
                parts.append(values["mode"])
            return ", ".join(parts) or "-"

        output = None if self.output is None else ("on" if self.output else "off")
        return [("Identity", _show(self.identity)), ("Channel 1", channel(1)),
                ("Channel 2", channel(2)), ("Output", _show(output)),
                ("Tracking", _show(self.tracking)), ("Last problem", _show(self.problem))]


class JlinkPanel:  # pylint: disable=too-many-instance-attributes
    """The J-Link's state as its traffic describes it."""

    kind = "jlink"

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
        self.problem: Optional[str] = None

    def feed(self, record: Dict[str, Any]) -> None:
        """Take one of the probe's records."""
        text = str(record.get("text", ""))
        logger = str(record.get("logger", ""))
        if record.get("level") in ("WARNING", "ERROR", "CRITICAL"):
            self.problem = text
            return
        kind, payload = classify(text)
        if text.startswith(">> "):
            self._command(payload.strip())
        elif text.startswith("console "):
            self._console(payload.strip())
        elif text.startswith("async "):
            self._async(payload.strip())
        elif text.startswith("rtt: "):
            self.rtt_lines += 1
            self.rtt_last = payload
            self.rtt = self.rtt or "started"
        elif kind == NOTE:
            self._info(logger, text)

    def _command(self, command: str) -> None:  # pylint: disable=too-many-branches
        self.commands += 1
        console = re.match(r'^-interpreter-exec console "(.*)"$', command)
        action = console.group(1) if console else command
        if action.startswith("-target-select"):
            self.target = action.split(None, 1)[1] if " " in action else action
        elif action.startswith("-file-exec-and-symbols"):
            self.elf = action.split(None, 1)[1].strip('"') if " " in action else None
        elif action in ("monitor reset", "monitor reset 0"):
            self.core, self.stopped_at = "reset", None
        elif action == "monitor halt":
            self.core = "halted"
        elif action in ("-target-detach", "-gdb-exit"):
            self.core = "detached, core %s" % ("running" if self.core == "running" else
                                                self.core or "unknown")
        elif action in ("monitor go", "-exec-continue", "-exec-run", "continue"):
            self.core, self.stopped_at = "running", None
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
            self.core, self.stopped_at = "running", None
            return
        if not text.startswith("stopped"):
            return
        self.core = "halted"
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

    def rows(self) -> List[Tuple[str, str]]:
        """(label, value) pairs for display; unknown shows as a dash."""
        core = self.core
        if core == "halted" and self.stopped_at:
            core = "halted: %s" % self.stopped_at
        rtt = self.rtt
        if rtt or self.rtt_lines:
            rtt = "%s, %d line(s)" % (rtt or "started", self.rtt_lines)
        return [("Probe", _show(self.probe)), ("GDB server", _show(self.server)),
                ("Target", _show(self.target)), ("Firmware (ELF)", _show(self.elf)),
                ("Core", _show(core)), ("Last flash", _show(self.flash)),
                ("Verify", _show(self.verify)), ("Breakpoints", str(self.breakpoints)),
                ("RTT", _show(rtt)), ("Last RTT line", _show(self.rtt_last)),
                ("Commands sent", str(self.commands)), ("Last problem", _show(self.problem))]


_PANELS = (("benchtools.instruments.gpd3303d", PsuPanel),
           ("benchtools.instruments.jlink", JlinkPanel))


def panel_for(logger: str):
    """A new panel for the driver *logger* belongs to, or ``None``."""
    for prefix, panel in _PANELS:
        if logger == prefix or logger.startswith(prefix + "."):
            return panel()
    return None
