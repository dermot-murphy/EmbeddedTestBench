"""A single event log for a bench run, one JSON object per line.

Every instrument driver already reports what it does through :mod:`logging`:
the lines it sends and receives, the steps the runner takes. This module
collects all of that into one file that another program can follow while the
run is in progress - the Test Bench monitor's Events page does exactly that
(#82). Each record says which part of the bench it came from, so a reader can
tell the supply from the radio at a glance.

A record is::

    {"t": 1790600000.123456, "source": "PSU", "level": "DEBUG",
     "logger": "benchtools.instruments.gpd3303d.psu", "text": ">> VSET1:3.300"}

``t`` is host time in seconds since the epoch. ``source`` is the short name of
the instrument the record came from (#126). A specification allocates it to an
instrument role, a bench attaches it to an actual instrument, and the
specification's wins; with neither, it is the driver's default (:data:`SOURCES`).
An instrument carries its name in an :class:`EventSource`, and everything it
owns - its transport, its sessions - logs through a :class:`SourceLogger` bound
to it, so two instruments of one driver are told apart. A record logged by
nothing bound to an instrument falls back to :func:`source_of` its logger name.

A record logged through :func:`log_event` also carries ``kind`` and ``data``:
what happened, as a name, and its details as JSON, so a reader can follow a
run - which test case and step is running, what it returned - without parsing
``text`` (#135). Readers that ignore the two fields are unaffected.

JSON Lines rather than one document, flushed per record, so a reader can
follow the file while it is written and a run that dies leaves a readable log.

Traces to: CORE-FR-060, CORE-FR-063, CORE-FR-064, CORE-DD-EVENTS.
"""

from __future__ import annotations

import contextlib
import dataclasses
import enum
import json
import logging
import math
import os
import re
import threading
from typing import Any, Dict, Iterator, List, MutableMapping, Optional, Tuple

from .errors import ConfigurationError

__all__ = [
    "SOURCES",
    "DEFAULT_SOURCE",
    "EventSource",
    "SourceLogger",
    "connecting_as",
    "pending_source",
    "source_of",
    "validate_source_name",
    "EventLogHandler",
    "start_event_log",
    "EventTail",
    "jsonable",
    "log_event",
]

#: A driver's default name, by the start of its logger's name. First match wins.
_SOURCE_PREFIXES = (
    ("benchtools.instruments.gpd3303d", "PSU"),
    ("benchtools.instruments.nordic_dongle", "BLE"),
    ("benchtools.instruments.jlink", "JLINK"),
    ("benchtools.instruments.s2lp", "RF"),
    ("benchtools.instruments.tek3014b", "SCOPE"),
    ("benchtools.instruments.tti1604", "DMM"),
    ("benchtools.instruments.pico_sht30", "TEMP"),
    ("benchtools.runner", "TEST"),
)

#: What a record belongs to when nothing else says.
DEFAULT_SOURCE = "BENCH"

#: Every default name. A specification or bench may declare others.
SOURCES = tuple(source for _prefix, source in _SOURCE_PREFIXES) + (DEFAULT_SOURCE,)

#: A source name: an upper-case letter, then up to seven of A-Z, 0-9 and _.
_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,7}")


def validate_source_name(name: Any, where: str = "event source name") -> str:
    """Return *name* if it is a valid source name.

    :raises ConfigurationError: naming *where* and the rule, otherwise.
    """
    if not isinstance(name, str) or _NAME.fullmatch(name) is None:
        raise ConfigurationError(
            "%s %r is not valid: 1 to 8 characters, an upper-case letter "
            "followed by A-Z, 0-9 or _, e.g. TEMP or PSU2" % (where, name)
        )
    return name


def source_of(logger_name: str) -> str:
    """The default source for a logger's name; :data:`DEFAULT_SOURCE` for anything else."""
    for prefix, source in _SOURCE_PREFIXES:
        if logger_name == prefix or logger_name.startswith(prefix + "."):
            return source
    return DEFAULT_SOURCE


class EventSource:
    """The name one instrument's records carry, shared by everything it owns.

    Mutable, so a name given after construction reaches every logger already
    bound to it.
    """

    def __init__(self, name: str) -> None:
        self._name = validate_source_name(name)

    @property
    def name(self) -> str:
        """The current name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = validate_source_name(value)

    def __repr__(self) -> str:
        return "EventSource(%r)" % self._name


class SourceLogger(logging.LoggerAdapter):
    """A logger whose records carry the name of the instrument it is bound to.

    Unbound (``source`` is ``None``), a record falls back to :func:`source_of`
    its logger's name, as before #126.
    """

    def __init__(self, logger: logging.Logger, source: Optional[EventSource] = None) -> None:
        super().__init__(logger, {})
        if source is None and pending_source() is not None:
            # Built while the bench connects an instrument: its name already.
            source = EventSource(pending_source())
        self.source = source

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> Tuple[Any, MutableMapping[str, Any]]:
        if self.source is not None:
            extra = dict(kwargs.get("extra") or {})
            extra["event_source"] = self.source.name
            kwargs["extra"] = extra
        return msg, kwargs


_PENDING = threading.local()


@contextlib.contextmanager
def connecting_as(name: Optional[str]) -> Iterator[None]:
    """While an instrument is built in this thread, give it *name* from the start.

    Without this an instrument's first records - opening the link, identifying -
    would carry its driver's default before the bench could rename it.
    """
    previous = getattr(_PENDING, "name", None)
    _PENDING.name = None if name is None else validate_source_name(name)
    try:
        yield
    finally:
        _PENDING.name = previous


def pending_source() -> Optional[str]:
    """The name :func:`connecting_as` set for this thread, if any."""
    return getattr(_PENDING, "name", None)


#: Longest sequence :func:`jsonable` copies; a waveform is summarised, not logged.
MAX_ITEMS = 256


def jsonable(value: Any, depth: int = 0) -> Any:  # pylint: disable=too-many-return-statements
    """*value* as something :func:`json.dumps` writes as standard JSON.

    Numbers, text, booleans and None pass through; mappings, sequences and
    dataclasses are converted item by item; bytes become hex; an enum its value.
    A float that is not finite becomes text, because ``NaN`` is not JSON and a
    browser refuses the whole line for it. A sequence longer than
    :data:`MAX_ITEMS` is cut short and says so. Anything else is its ``repr``.
    """
    if depth > 8:
        return repr(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, enum.Enum):
        return jsonable(value.value, depth + 1)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: jsonable(getattr(value, field.name), depth + 1)
                for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key): jsonable(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        converted = [jsonable(item, depth + 1) for item in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            converted.append("... %d more" % (len(items) - MAX_ITEMS))
        return converted
    return repr(value)


def log_event(logger: Any, kind: str, text: str, data: Dict[str, Any],
              level: int = logging.INFO) -> None:
    """Log *text* as usual, carrying a structured *kind* and *data* for the event log.

    A console handler shows the text; :class:`EventLogHandler` also writes
    ``kind`` and ``data``, so a reader can follow a run without parsing text.
    """
    logger.log(level, "%s", text, extra={"event_kind": kind, "event_data": data})


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
            fields = {
                "t": round(record.created, 6),
                "source": (getattr(record, "event_source", None) or pending_source()
                           or source_of(record.name)),
                "level": record.levelname,
                "logger": record.name,
                "text": record.getMessage(),
            }
            kind = getattr(record, "event_kind", None)
            if kind:
                fields["kind"] = kind
                fields["data"] = jsonable(getattr(record, "event_data", None) or {})
            line = json.dumps(fields)
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
    Lines that are not JSON are returned as ``BENCH`` records carrying the raw
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
            return {"t": None, "source": DEFAULT_SOURCE, "level": "INFO", "logger": "",
                    "text": line}
        return record if isinstance(record, dict) else None
