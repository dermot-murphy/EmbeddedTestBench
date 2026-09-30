"""Optional PyVISA transport.

Provided for sites whose test infrastructure is standardised on VISA (NI-VISA,
Keysight IO Libraries or TekVISA) - for instance where an instrument inventory,
licence server or existing LabVIEW rig already resolves VISA resource strings.
It is **not required** to drive a TDS3014B; see the VISA determination report.

``pyvisa`` is imported lazily so that the package as a whole keeps a zero
mandatory dependency footprint.

Traces to: SWE1-FR-004, SWE2-ARC-003, SWE3-DD-VISA.
"""

from __future__ import annotations

import logging
from typing import Tuple

from ..errors import ConnectionFailedError, OptionalDependencyError, TransportError, TransportTimeoutError
from .base import Transport

__all__ = ["VisaTransport", "pyvisa_available"]

_LOG = logging.getLogger(__name__)


def pyvisa_available() -> bool:
    """Return ``True`` when ``pyvisa`` can be imported."""
    try:
        import pyvisa  # noqa: F401  # pylint: disable=unused-import
    except ImportError:
        return False
    return True


class VisaTransport(Transport):
    """Instrument link delegated to PyVISA.

    :param resource: VISA resource string, e.g.
        ``TCPIP0::192.168.1.50::inst0::INSTR``.
    :param timeout: Default I/O timeout in seconds.
    :param visa_library: Backend selector passed to ``pyvisa.ResourceManager``.
        Use ``"@py"`` for the dependency-light pure-Python pyvisa-py backend,
        or ``""`` for the system VISA installation.
    """

    def __init__(
        self,
        resource: str,
        timeout: float = 10.0,
        visa_library: str = "",
    ) -> None:
        super().__init__(timeout=timeout)
        if not resource:
            raise ValueError("resource must be a non-empty VISA resource string")
        self._resource = str(resource)
        self._visa_library = visa_library
        self._rm = None
        self._instrument = None

    @property
    def description(self) -> str:
        return "VISA %s" % self._resource

    def _open_link(self) -> None:
        try:
            import pyvisa
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise OptionalDependencyError(
                "the VISA transport needs the 'pyvisa' package "
                "(pip install pyvisa, or pip install pyvisa-py for a pure-Python backend). "
                "The built-in VXI-11 transport needs no third-party package at all."
            ) from exc

        try:
            self._rm = pyvisa.ResourceManager(self._visa_library)
            self._instrument = self._rm.open_resource(self._resource)
        except Exception as exc:
            self._close_link()
            raise ConnectionFailedError(
                "PyVISA could not open %r: %s" % (self._resource, exc)
            ) from exc

        # PyVISA expresses timeouts in milliseconds.
        self._instrument.timeout = self._timeout * 1000.0
        self._instrument.read_termination = None
        self._instrument.write_termination = None

    def _close_link(self) -> None:
        if self._instrument is not None:
            try:
                self._instrument.close()
            finally:
                self._instrument = None
        if self._rm is not None:
            try:
                self._rm.close()
            finally:
                self._rm = None

    def _send(self, data: bytes) -> None:
        if self._instrument is None:
            raise TransportError("VISA session is not open")
        try:
            self._instrument.write_raw(data)
        except Exception as exc:
            raise TransportError("VISA write failed: %s" % exc) from exc

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if self._instrument is None:
            raise TransportError("VISA session is not open")
        try:
            import pyvisa
        except ImportError as exc:  # pragma: no cover
            raise OptionalDependencyError("pyvisa is not installed") from exc

        try:
            data, status = self._instrument.visalib.read(
                self._instrument.session, max(int(max_bytes), 1)
            )
        except Exception as exc:
            message = str(exc)
            if "timeout" in message.lower():
                raise TransportTimeoutError("VISA read timed out: %s" % message) from exc
            raise TransportError("VISA read failed: %s" % message) from exc

        end = status != pyvisa.constants.StatusCode.success_max_count_read
        return bytes(data), bool(end)

    def clear(self) -> None:
        """Issue a VISA device clear."""
        if self._instrument is not None:
            self._instrument.clear()
        self._reset_buffer()

    def read_stb(self) -> int:
        """Read the status byte through the VISA serial-poll service."""
        if self._instrument is None:
            raise TransportError("VISA session is not open")
        return int(self._instrument.read_stb()) & 0xFF
