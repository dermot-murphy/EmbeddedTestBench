"""SCPI plumbing shared by every instrument driver.

:class:`ScpiInstrument` owns everything that is the same for a power supply, a
DMM, a signal generator, a spectrum analyser and an oscilloscope: opening the
link, sending commands, parsing scalar responses, identification, reset, the
error queue, and the connect/close lifecycle. An instrument driver subclasses
it and adds only its own command vocabulary.

Two things are deliberately pluggable, because instrument families genuinely
differ:

**The error queue.** SCPI-1999 specifies ``SYSTem:ERRor?``, polled until it
returns 0. Tektronix instruments use ``ALLEv?``, which returns every pending
event in one response. Override :meth:`read_event_queue` rather than
reimplementing error handling.

**Post-connect setup.** Some instruments need their response format put into a
known state before queries parse predictably. Override :meth:`initialise`,
calling ``super().initialise()`` first.

Traces to: CORE-FR-020 .. CORE-FR-027, CORE-ARC-001, CORE-DD-SCPI.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from .errors import ProtocolError
from .instrument import Instrument, InstrumentIdentity
from .transport.base import Transport
from .transport.factory import open_transport

__all__ = ["ScpiInstrument", "InstrumentIdentity", "parse_ieee_block", "format_ieee_block"]



# ---------------------------------------------------------------------------
# IEEE 488.2 arbitrary block data
# ---------------------------------------------------------------------------
def parse_ieee_block(data: bytes) -> bytes:
    """Extract the payload from an IEEE 488.2 arbitrary block response.

    Handles the definite-length form (``#<n><length><payload>``) and the
    indefinite-length form (``#0<payload>``). A response with no block header
    is returned unchanged, which keeps ASCII encodings working through the same
    path.

    Used for oscilloscope waveform records, spectrum analyser traces, and
    arbitrary waveform uploads - hence its place in the shared layer.

    :raises ProtocolError: if the header is malformed or the payload is short.
    """
    if not data:
        raise ProtocolError("empty response where an IEEE 488.2 block was expected")
    start = data.find(b"#")
    if start < 0:
        return data
    if len(data) < start + 2:
        raise ProtocolError("truncated IEEE 488.2 block header")

    digit_count = data[start + 1 : start + 2]
    if not digit_count.isdigit():
        raise ProtocolError("malformed IEEE 488.2 block header %r" % data[start : start + 4])
    digits = int(digit_count)

    if digits == 0:
        return data[start + 2 :].rstrip(b"\r\n")

    length_start = start + 2
    length_field = data[length_start : length_start + digits]
    if len(length_field) < digits or not length_field.isdigit():
        raise ProtocolError("malformed IEEE 488.2 block length %r" % length_field)
    length = int(length_field)

    payload_start = length_start + digits
    payload = data[payload_start : payload_start + length]
    if len(payload) < length:
        raise ProtocolError(
            "IEEE 488.2 block truncated: header declared %d bytes, received %d"
            % (length, len(payload))
        )
    return payload


def format_ieee_block(payload: bytes) -> bytes:
    """Wrap *payload* in a definite-length IEEE 488.2 block header.

    Needed when sending bulk data *to* an instrument, such as an arbitrary
    waveform upload.
    """
    count = str(len(payload)).encode("ascii")
    return b"#" + str(len(count)).encode("ascii") + count + payload


class ScpiInstrument(Instrument):
    """Base class for a SCPI instrument driver.

    :param transport: An open or unopened link.
    :param auto_check_errors: Query the instrument's error queue after each
        configuration operation and raise if it reported anything. Costs one
        round trip per operation; turn it off for throughput once a sequence is
        known-good.
    :param owns_transport: Close the transport when :meth:`close` is called.
    """

    MODEL_NAME = "SCPI instrument"

    def __init__(
        self,
        transport: Transport,
        auto_check_errors: bool = True,
        owns_transport: bool = True,
    ) -> None:
        super().__init__(auto_check_errors=auto_check_errors)
        self._transport = transport
        self._owns_transport = bool(owns_transport)
        self._adopt(transport)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def connect(
        cls,
        resource: str,
        backend: str = "auto",
        timeout: float = 10.0,
        auto_check_errors: bool = True,
        initialise: bool = True,
        transport_kwargs: Optional[dict] = None,
        **instrument_kwargs,
    ) -> "ScpiInstrument":
        """Open a link to the instrument and return a ready driver.

        :param resource: Host name, IP address, resource string, or ``sim://``
            for this instrument's own simulator.
        :param backend: ``"auto"``, ``"vxi11"``, ``"socket"``, ``"visa"`` or
            ``"sim"``.
        :param initialise: Put the instrument's response format into a known
            state and clear its status. Does not reset the front-panel setup.
        :param transport_kwargs: Extra keyword arguments for the transport.
        :param instrument_kwargs: Extra keyword arguments for this driver's
            constructor, such as a non-default capability envelope.
        """
        link_kwargs = dict(transport_kwargs or {})
        if cls.SIMULATOR_CLASS is not None and "responder" not in link_kwargs:
            link_kwargs.setdefault("responder_factory", cls.SIMULATOR_CLASS)
        transport = open_transport(resource, backend=backend, timeout=timeout, **link_kwargs)
        instrument = cls(
            transport,
            auto_check_errors=auto_check_errors,
            owns_transport=True,
            **instrument_kwargs,
        )
        try:
            if initialise:
                instrument.initialise()
        except Exception:
            instrument.close()
            raise
        return instrument

    def _open(self) -> None:
        self._transport.open()

    def _close(self) -> None:
        if self._owns_transport:
            self._transport.close()

    @property
    def is_open(self) -> bool:
        """``True`` while the instrument link is open."""
        return self._transport.is_open

    def _post_open(self) -> None:
        """Clear the status and event queues.

        Deliberately does **not** reset the front-panel setup: silently
        discarding an operator's setup would be a surprising side effect of
        connecting. Call :meth:`reset` for that.
        """
        self._write("*CLS")

    @property
    def transport(self) -> Transport:
        """The underlying instrument link."""
        return self._transport

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<%s via %s>" % (type(self).__name__, self._transport.description)

    # ------------------------------------------------------------------
    # Primitive I/O
    # ------------------------------------------------------------------
    @property
    def _io_log(self) -> logging.LoggerAdapter:
        """The logger this instrument's I/O is recorded under: its own module's.

        So a line sent to a supply is logged as the supply's, not as the shared
        SCPI layer's, and carries the instrument's event-log name (#126).
        """
        return self._logger

    def _write(self, command: str) -> None:
        """Send *command*, expecting no response."""
        self._io_log.debug(">> %s", command)
        self._transport.write(command.encode("ascii"))

    def _query(self, command: str) -> str:
        """Send *command* and return the response with whitespace stripped."""
        self._io_log.debug(">> %s", command)
        self._transport.write(command.encode("ascii"))
        response = self._transport.read_message().decode("ascii", errors="replace").strip()
        self._io_log.debug("<< %s", response)
        return response

    def _query_float(self, command: str) -> float:
        response = self._query(command)
        try:
            return float(response)
        except ValueError as exc:
            raise ProtocolError(
                "expected a number from %r, got %r" % (command, response)
            ) from exc

    def _query_int(self, command: str) -> int:
        return int(round(self._query_float(command)))

    def _query_bool(self, command: str) -> bool:
        return self._query(command).strip().upper() in ("1", "ON", "TRUE")

    def _query_fields(self, command: str, expected: int) -> List[str]:
        """Send a compound query and split its ``;``-separated response.

        Batching related queries into one message turns *n* round trips into
        one, which matters on a 10 Mbit/s instrument link.

        :raises ProtocolError: if the field count does not match *expected*.
        """
        response = self._query(command)
        fields = [field.strip() for field in response.split(";")]
        if len(fields) != expected:
            raise ProtocolError(
                "expected %d fields from %r, got %d: %r"
                % (expected, command, len(fields), response)
            )
        return fields

    # ------------------------------------------------------------------
    # Identification and status
    # ------------------------------------------------------------------
    def _read_identity(self) -> InstrumentIdentity:
        """Identify the instrument with the IEEE 488.2 ``*IDN?`` query."""
        return InstrumentIdentity.from_idn(self._query("*IDN?"))

    def reset(self, settle: float = 0.5) -> None:
        """Issue ``*RST``, then restore the driver's communication state.

        :param settle: Seconds to wait for the instrument to finish resetting.
        """
        import time

        self._write("*RST")
        if settle > 0.0:
            time.sleep(settle)
        self._post_open()

    def clear_status(self) -> None:
        """Clear the status byte and event queue (``*CLS``)."""
        self._write("*CLS")

    def operation_complete(self) -> bool:
        """Return the result of ``*OPC?``.

        Note that on many instruments this reports that the *command* has been
        parsed, not that a long operation such as an acquisition has finished.
        Check the instrument's own busy indication for that.
        """
        return self._query("*OPC?").strip() == "1"

    def event_status(self) -> int:
        """Read and clear the Standard Event Status Register (``*ESR?``)."""
        return self._query_int("*ESR?")

    def self_test_passed(self) -> bool:
        """Return ``True`` if no error bits are set in the ESR."""
        return (self.event_status() & 0x3C) == 0

    # ------------------------------------------------------------------
    # Error queue
    # ------------------------------------------------------------------
    def read_event_queue(self) -> List[Tuple[int, str]]:
        """Drain and return the instrument's error queue.

        The default implementation polls ``SYSTem:ERRor?`` until it reports 0,
        which is the SCPI-1999 behaviour. Instrument families that report
        errors differently override this.

        :returns: ``(code, description)`` pairs; empty when nothing was reported.
        """
        events: List[Tuple[int, str]] = []
        for _ in range(64):   # bounded, so a stuck queue cannot hang the caller
            response = self._query("SYSTEM:ERROR?")
            code, _, description = response.partition(",")
            try:
                number = int(code)
            except ValueError:
                break
            if number == 0:
                break
            events.append((number, description.strip().strip('"')))
        return events

    # ------------------------------------------------------------------
    # Raw access, for commands a driver does not wrap
    # ------------------------------------------------------------------
    def write_raw(self, command: str) -> None:
        """Send an arbitrary SCPI command.

        An escape hatch for instrument features the driver does not wrap. Use
        sparingly: a command sent this way is not validated and not traced to a
        requirement.
        """
        self._write(command)

    def query_raw(self, command: str) -> str:
        """Send an arbitrary SCPI query and return the raw response."""
        return self._query(command)
