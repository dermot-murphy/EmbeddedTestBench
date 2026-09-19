"""The instrument lifecycle, independent of any wire protocol.

Not every instrument on a bench speaks SCPI. A debug probe is driven over
GDB/MI, a BLE dongle over its own command set, a legacy meter over an RS-232
dialect of its own. What they all share is a *lifecycle*: open a link, find out
what you are talking to, check whether it complained, close cleanly, and behave
correctly as a context manager when something raises.

:class:`Instrument` owns exactly that, and nothing else.
:class:`~benchtools.core.scpi.ScpiInstrument` adds SCPI on top; a driver for
something that is not SCPI subclasses :class:`Instrument` directly and is still
usable by the bench runner, because the runner only relies on this contract.

Traces to: CORE-FR-012 .. CORE-FR-016, CORE-ARC-006, CORE-DD-INSTRUMENT.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Type

from .simulator import Responder

__all__ = ["Instrument", "InstrumentIdentity"]

_LOG = logging.getLogger(__name__)


class InstrumentIdentity:
    """What an instrument says it is.

    Populated from ``*IDN?`` for a SCPI instrument, and from whatever the
    equivalent is elsewhere - a probe's serial number and firmware string, a
    dongle's version banner.

    :param raw: The unparsed identification text, retained for logs and reports.
    """

    __slots__ = ("raw", "manufacturer", "model", "serial_number", "firmware")

    def __init__(
        self,
        raw: str,
        manufacturer: str = "",
        model: str = "",
        serial_number: str = "",
        firmware: str = "",
    ) -> None:
        self.raw = raw
        self.manufacturer = manufacturer
        self.model = model
        self.serial_number = serial_number
        self.firmware = firmware

    @classmethod
    def from_idn(cls, raw: str) -> "InstrumentIdentity":
        """Parse the four comma-separated fields of an IEEE 488.2 ``*IDN?``.

        Degrades rather than failing on a response with fewer fields: some
        instruments send three, and a missing serial number is not a reason to
        abandon a test run.
        """
        fields = [field.strip() for field in raw.split(",")]
        fields += [""] * (4 - len(fields))
        return cls(
            raw=raw,
            manufacturer=fields[0],
            model=fields[1],
            serial_number=fields[2],
            firmware=fields[3],
        )

    def __str__(self) -> str:
        return self.raw

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<InstrumentIdentity %s %s>" % (self.manufacturer, self.model)


class Instrument:
    """Base class for every instrument driver, whatever protocol it speaks.

    Subclasses must provide :meth:`identify` and :meth:`_open` / :meth:`_close`,
    and may override :meth:`read_event_queue` if the instrument has one.

    :param auto_check_errors: Query the instrument's error state after each
        configuration operation and raise if it reported anything.
    """

    #: Simulator class used for a ``sim://`` resource. Subclasses set this so
    #: that simulation needs no knowledge of instruments anywhere else.
    SIMULATOR_CLASS: Optional[Type[Responder]] = None

    #: Human-readable name used in messages before the model is known.
    MODEL_NAME = "instrument"

    def __init__(self, auto_check_errors: bool = True) -> None:
        self.auto_check_errors = bool(auto_check_errors)
        self._identity: Optional[InstrumentIdentity] = None
        self._initialised = False

    # ------------------------------------------------------------------
    # Lifecycle, which subclasses implement
    # ------------------------------------------------------------------
    def _open(self) -> None:
        """Open whatever links this instrument needs. Idempotent."""
        raise NotImplementedError

    def _close(self) -> None:
        """Release every link. Must not raise."""
        raise NotImplementedError

    @property
    def is_open(self) -> bool:
        """``True`` while the instrument is reachable."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    def initialise(self) -> None:
        """Put the instrument into a known *communication* state.

        Called once by :meth:`connect`. Deliberately does not reset the
        instrument's settings: silently discarding an operator's setup would be
        a surprising side effect of connecting.
        """
        self._open()
        self._post_open()
        self._initialised = True

    def _post_open(self) -> None:
        """Hook run once the links are open, before the instrument is used.

        Subclasses put the instrument's *communication* state in order here -
        response formatting, status clearing - and chain to ``super()``.
        """

    def close(self) -> None:
        """Release the instrument. Idempotent, and never raises."""
        try:
            self._close()
        except Exception:  # pragma: no cover - defensive
            _LOG.warning("error while closing %s", self.MODEL_NAME, exc_info=True)
        finally:
            self._initialised = False

    def __enter__(self) -> "Instrument":
        if not self._initialised:
            self.initialise()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def identify(self, refresh: bool = False) -> InstrumentIdentity:
        """Return the parsed identification, cached after the first call."""
        if self._identity is None or refresh:
            self._identity = self._read_identity()
        return self._identity

    def identity(self, refresh: bool = False) -> str:
        """Return the raw identification string."""
        return self.identify(refresh=refresh).raw

    def _read_identity(self) -> InstrumentIdentity:
        """Ask the instrument what it is. Subclasses implement this."""
        raise NotImplementedError

    @property
    def manufacturer(self) -> str:
        """Manufacturer field of the identification."""
        return self.identify().manufacturer

    @property
    def model(self) -> str:
        """Model field of the identification."""
        return self.identify().model or "unknown"

    @property
    def serial_number(self) -> str:
        """Serial number field of the identification."""
        return self.identify().serial_number

    @property
    def firmware(self) -> str:
        """Firmware field of the identification."""
        return self.identify().firmware

    # ------------------------------------------------------------------
    # Error reporting
    # ------------------------------------------------------------------
    def read_event_queue(self) -> List[Tuple[int, str]]:
        """Return and clear whatever errors the instrument is holding.

        The default is an instrument with no error queue, which is the honest
        answer for most non-SCPI hardware.
        """
        return []

    def check_errors(self) -> None:
        """Raise if the instrument reported anything.

        Called after configuration operations when ``auto_check_errors`` is set,
        so a rejected setting is caught where it happened rather than
        discovered as odd data later.
        """
        from .errors import InstrumentError

        events = self.read_event_queue()
        if events:
            summary = "; ".join("%d: %s" % item for item in events)
            raise InstrumentError(
                "%s reported %d event(s): %s" % (self.MODEL_NAME, len(events), summary),
                events,
            )

    def _after_configuration(self) -> None:
        """Hook run after a configuration change; checks errors if enabled."""
        if self.auto_check_errors:
            self.check_errors()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<%s>" % type(self).__name__
