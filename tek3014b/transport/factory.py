"""Resource-string parsing and transport selection.

One entry point, :func:`open_transport`, turns a human-friendly resource
string into an open :class:`~tek3014b.transport.base.Transport`. Accepted
forms::

    192.168.1.50                        VXI-11 (default for a bare host)
    vxi11://192.168.1.50                VXI-11, explicit
    vxi11://192.168.1.50/gpib0,1        VXI-11 with an explicit device name
    TCPIP::192.168.1.50::INSTR          VISA-style string, served by VXI-11
    TCPIP0::192.168.1.50::inst0::INSTR  VISA-style string with device name
    socket://192.168.1.50:4000          raw SCPI socket (not on a TDS3014B)
    TCPIP::192.168.1.50::4000::SOCKET   VISA-style raw socket
    visa://TCPIP::192.168.1.50::INSTR   force the PyVISA backend
    sim://                              built-in simulator

Note that a VISA-style resource string does **not** imply a VISA library: by
default it is served by the built-in VXI-11 transport. Pass ``backend="visa"``
or the ``visa://`` prefix to route it through PyVISA instead.

Traces to: SWE1-FR-005, SWE2-ARC-003, SWE3-DD-FACTORY.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..constants import DEFAULT_RAW_SOCKET_PORT, DEFAULT_VXI11_DEVICE_NAMES
from ..errors import UnsupportedTransportError
from .base import Transport
from .mock import MockTransport
from .socket_raw import SocketTransport
from .visa_backend import VisaTransport
from .vxi11 import Vxi11Transport

__all__ = ["open_transport", "parse_resource", "BACKENDS"]

_LOG = logging.getLogger(__name__)

#: Backend names accepted by :func:`open_transport`.
BACKENDS = ("auto", "vxi11", "socket", "visa", "sim")


def parse_resource(resource: str, backend: str = "auto") -> dict:
    """Resolve *resource* and *backend* into transport keyword arguments.

    Kept separate from :func:`open_transport` so that resource parsing can be
    unit-tested without opening a connection.

    :returns: A dict with a ``"backend"`` key plus backend-specific arguments.
    :raises UnsupportedTransportError: if the resource cannot be interpreted.
    """
    if backend not in BACKENDS:
        raise UnsupportedTransportError(
            "unknown backend %r; expected one of %s" % (backend, ", ".join(BACKENDS))
        )
    text = (resource or "").strip()
    if not text:
        raise UnsupportedTransportError("resource string must not be empty")

    lowered = text.lower()

    # --- explicit scheme prefixes -------------------------------------
    if lowered.startswith(("sim://", "mock://")) or lowered in ("sim", "mock"):
        return {"backend": "sim"}

    if lowered.startswith("visa://"):
        return {"backend": "visa", "resource": text[len("visa://") :]}

    if lowered.startswith("vxi11://"):
        remainder = text[len("vxi11://") :]
        host, _, device = remainder.partition("/")
        result = {"backend": "vxi11", "host": host}
        if device:
            result["device_names"] = (device,)
        return result

    if lowered.startswith(("socket://", "tcp://")):
        remainder = text.split("://", 1)[1]
        host, port = _split_host_port(remainder, DEFAULT_RAW_SOCKET_PORT)
        return {"backend": "socket", "host": host, "port": port}

    # --- VISA-style resource strings ----------------------------------
    if lowered.startswith("tcpip"):
        fields = [field for field in text.split("::") if field]
        if len(fields) < 2:
            raise UnsupportedTransportError("malformed VISA resource string %r" % resource)
        host = fields[1]
        suffix = fields[-1].upper()
        if backend == "visa":
            return {"backend": "visa", "resource": text}
        if suffix == "SOCKET":
            port = int(fields[2]) if len(fields) > 3 else DEFAULT_RAW_SOCKET_PORT
            return {"backend": "socket", "host": host, "port": port}
        result = {"backend": "vxi11", "host": host}
        if len(fields) > 3 and suffix == "INSTR":
            result["device_names"] = (fields[2],)
        return result

    if backend == "visa":
        return {"backend": "visa", "resource": text}

    # --- bare host, optionally with a port ----------------------------
    if ":" in text and not text.count(":") > 1:
        host, port = _split_host_port(text, DEFAULT_RAW_SOCKET_PORT)
        chosen = "socket" if backend in ("auto", "socket") else backend
        if chosen == "vxi11":
            return {"backend": "vxi11", "host": host}
        return {"backend": "socket", "host": host, "port": port}

    if backend == "socket":
        return {"backend": "socket", "host": text, "port": DEFAULT_RAW_SOCKET_PORT}
    return {"backend": "vxi11", "host": text}


def _split_host_port(text: str, default_port: int):
    host, separator, port_text = text.rpartition(":")
    if not separator:
        return text, default_port
    try:
        return host, int(port_text)
    except ValueError as exc:
        raise UnsupportedTransportError("invalid port in %r" % text) from exc


def open_transport(
    resource: str,
    backend: str = "auto",
    timeout: float = 10.0,
    open_now: bool = True,
    **kwargs,
) -> Transport:
    """Create a transport for *resource* and, by default, open it.

    :param resource: Resource string; see the module docstring for the forms.
    :param backend: ``"auto"`` (default), ``"vxi11"``, ``"socket"``, ``"visa"``
        or ``"sim"``.
    :param timeout: Default I/O timeout in seconds.
    :param open_now: Open the link before returning.
    :param kwargs: Passed through to the transport constructor.
    """
    parsed = parse_resource(resource, backend)
    chosen = parsed.pop("backend")

    if chosen == "sim":
        transport: Transport = MockTransport(timeout=timeout, **kwargs)
    elif chosen == "vxi11":
        parsed.setdefault("device_names", DEFAULT_VXI11_DEVICE_NAMES)
        transport = Vxi11Transport(timeout=timeout, **parsed, **kwargs)
    elif chosen == "socket":
        transport = SocketTransport(timeout=timeout, **parsed, **kwargs)
    elif chosen == "visa":
        transport = VisaTransport(timeout=timeout, **parsed, **kwargs)
    else:  # pragma: no cover - guarded by parse_resource
        raise UnsupportedTransportError("unsupported backend %r" % chosen)

    _LOG.debug("resource %r resolved to %s", resource, transport.description)
    if open_now:
        transport.open()
    return transport
