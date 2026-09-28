"""A single event log for a bench run, one JSON object per line.

Every instrument driver already reports what it does through :mod:`logging`:
the lines it sends and receives, the steps the runner takes. This module
collects all of that into one file that another program can follow while the
run is in progress - the Test Bench monitor's Events page does exactly that
(#82). Each record says which part of the bench it came from, so a reader can
tell the supply from the radio at a glance.

A record is::

    {"t": 1790600000.123456, "source": "psu", "level": "DEBUG",
     "logger": "benchtools.instruments.gpd3303d.psu", "text": ">> VSET1:3.300"}

``t`` is host time in seconds since the epoch. ``source`` is one of
:data:`SOURCES`, decided from the logger's name by :func:`source_of`.

JSON Lines rather than one document, flushed per record, so a reader can
follow the file while it is written and a run that dies leaves a readable log.

Traces to: CORE-FR-060, CORE-DD-EVENTS.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

__all__ = ["SOURCES", "source_of", "EventLogHandler", "start_event_log", "EventTail"]

#: Where an event came from, by the start of its logger's name. First match wins.
_SOURCE_PREFIXES = (
    ("benchtools.instruments.gpd3303d", "psu"),
    ("benchtools.instruments.nordic_dongle", "ble"),
    ("benchtools.instruments.jlink", "jlink"),
    ("benchtools.instruments.s2lp", "rf"),
    ("benchtools.instruments.tek3014b", "scope"),
    ("benchtools.instruments.tti1604", "dmm"),
    ("benchtools.runner", "test"),
)

#: Every source a record can carry.
SOURCES = tuple(source for _prefix, source in _SOURCE_PREFIXES) + ("bench",)


def source_of(logger_name: str) -> str:
    """The bench source a logger belongs to; ``"bench"`` for anything else."""
    for prefix, source in _SOURCE_PREFIXES:
        if logger_name == prefix or logger_name.startswith(prefix + "."):
            return source
    return "bench"


class EventLogHandler(logging.Handler):
    """A logging handler that writes each record as one JSON line, flushed."""

    def __init__(self, path: str, level: int = logging.DEBUG) -> None:
        super().__init__(level=level)
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.path = path
        self._file = open(path, "a", encoding="utf-8")  # pylint: disable=consider-using-with

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = json.dumps({
                "t": round(record.created, 6),
                "source": source_of(record.name),
                "level": record.levelname,
                "logger": record.name,
                "text": record.getMessage(),
            })
            self._file.write(line + "\n")
            self._file.flush()
        except Exception:                           # pylint: disable=broad-except
            self.handleError(record)

    def close(self) -> None:
        try:
            if not self._file.closed:
                self._file.close()
        finally:
            super().close()


def start_event_log(path: str, level: int = logging.DEBUG) -> EventLogHandler:
    """Send every ``benchtools`` log record at *level* or above to *path*.

    :returns: The handler; remove it from the ``benchtools`` logger and close
        it to stop.
    """
    handler = EventLogHandler(path, level)
    root = logging.getLogger()
    # Lowering the package's level would otherwise let DEBUG records through
    # to a console handler that relied on the root level to hold them back.
    for existing in root.handlers:
        if existing.level == logging.NOTSET:
            existing.setLevel(root.level)
    logger = logging.getLogger("benchtools")
    logger.addHandler(handler)
    if logger.getEffectiveLevel() > level:
        logger.setLevel(level)
    return handler


class EventTail:
    """Follow an event log as it grows, returning the records added since the last read.

    A partial last line - the writer mid-record - is left for the next read.
    Lines that are not JSON are returned as ``bench`` records carrying the raw
    text, rather than dropped.
    """

    def __init__(self, path: str, from_start: bool = True) -> None:
        self.path = path
        self._position = 0
        self._partial = ""
        if not from_start and os.path.exists(path):
            self._position = os.path.getsize(path)

    def rewind(self) -> None:
        """Start again from the beginning of the file, e.g. after it was replaced."""
        self._position = 0
        self._partial = ""

    def read(self) -> List[Dict[str, Any]]:
        """Records appended since the previous call."""
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self._position)
            chunk = handle.read()
            self._position = handle.tell()
        text = self._partial + chunk
        lines = text.split("\n")
        self._partial = lines.pop()                # "" when the chunk ended cleanly
        return [record for record in map(self._parse, lines) if record is not None]

    @staticmethod
    def _parse(line: str) -> Optional[Dict[str, Any]]:
        line = line.strip()
        if not line:
            return None
        try:
            record = json.loads(line)
        except ValueError:
            return {"t": None, "source": "bench", "level": "INFO", "logger": "", "text": line}
        return record if isinstance(record, dict) else None
