"""Resource-string parsing and transport selection.

One entry point, :func:`open_transport`, turns a human-friendly resource string
into an open :class:`~benchtools.core.transport.base.Transport`. Accepted forms::

    192.168.1.50                        VXI-11 (default for a bare host)
    vxi11://192.168.1.50                VXI-11, explicit
    vxi11://192.168.1.50/gpib0,1        VXI-11 with an explicit device name
    TCPIP::192.168.1.50::INSTR          VISA-style string, served by VXI-11
    TCPIP0::192.168.1.50::inst0::INSTR  VISA-style string with device name
    socket://192.168.1.50:4000          raw SCPI socket
    TCPIP::192.168.1.50::4000::SOCKET   VISA-style raw socket
    process://arm-none-eabi-gdb --interp=mi2   a child process over its pipes
    visa://TCPIP::192.168.1.50::INSTR   force the PyVISA backend
    sim://                              in-process simulator

A VISA-style resource string does **not** imply a VISA library: by default it is
served by the built-in VXI-11 transport. Pass ``backend="visa"`` or the
``visa://`` prefix to route it through PyVISA instead.

Backends and URL schemes are held in registries rather than an if-chain, so a
new link type - a serial BLE dongle, USBTMC, an HTTP-controlled RF box - is
added with :func:`register_backend` from its own module, without editing this
one.

Traces to: CORE-FR-002, CORE-FR-010, CORE-ARC-003, CORE-DD-FACTORY.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Tuple, Type

from ..errors import UnsupportedTransportError
from .base import Transport
from .constants import DEFAULT_RAW_SOCKET_PORT, DEFAULT_VXI11_DEVICE_NAMES
from .mock import MockTransport
from .process import ProcessTransport
from .socket_raw import SocketTransport
from .visa_backend import VisaTransport
from .vxi11 import Vxi11Transport

__all__ = [
    "open_transport",
    "parse_resource",
    "register_backend",
    "registered_backends",
    "BACKENDS",
]

_LOG = logging.getLogger(__name__)

#: Backend name to transport class.
_BACKENDS: Dict[str, Type[Transport]] = {}

#: URL scheme (without ``://``) to the backend that serves it.
_SCHEMES: Dict[str, str] = {}


def register_backend(
    name: str,
    transport_class: Type[Transport],
    schemes: Tuple[str, ...] = (),
) -> None:
    """Register a transport backend and the URL schemes that select it.

    :param name: Backend name, as accepted by ``backend=``.
    :param transport_class: Class constructed with the parsed keyword arguments.
    :param schemes: URL scheme prefixes routed to this backend.
    """
    _BACKENDS[name] = transport_class
    for scheme in schemes:
        _SCHEMES[scheme.lower()] = name


def registered_backends() -> Tuple[str, ...]:
    """Return the registered backend names, plus ``"auto"``."""
    return ("auto",) + tuple(sorted(_BACKENDS))


register_backend("vxi11", Vxi11Transport, ("vxi11",))
register_backend("socket", SocketTransport, ("socket", "tcp"))
register_backend("visa", VisaTransport, ("visa",))
register_backend("sim", MockTransport, ("sim", "mock"))
register_backend("process", ProcessTransport, ("process", "stdio"))


def _split_host_port(text: str, default_port: int) -> Tuple[str, int]:
    host, separator, port_text = text.rpartition(":")
    if not separator:
        return text, default_port
    try:
        return host, int(port_text)
    except ValueError as exc:
        raise UnsupportedTransportError("invalid port in %r" % text) from exc


def parse_resource(resource: str, backend: str = "auto") -> dict:
    """Resolve *resource* and *backend* into transport keyword arguments.

    Kept separate from :func:`open_transport` so that resource parsing can be
    unit-tested without opening a connection.

    :returns: A dict with a ``"backend"`` key plus backend-specific arguments.
    :raises UnsupportedTransportError: if the resource cannot be interpreted.
    """
    if backend != "auto" and backend not in _BACKENDS:
        raise UnsupportedTransportError(
            "unknown backend %r; expected one of %s"
            % (backend, ", ".join(registered_backends()))
        )
    text = (resource or "").strip()
    if not text:
        raise UnsupportedTransportError("resource string must not be empty")

    lowered = text.lower()

    # --- explicit scheme prefixes -------------------------------------
    scheme, separator, remainder = text.partition("://")
    if separator:
        chosen = _SCHEMES.get(scheme.lower())
        if chosen is None:
            raise UnsupportedTransportError(
                "unknown resource scheme %r; registered schemes are %s"
                % (scheme, ", ".join(sorted(_SCHEMES)))
            )
        return _parse_for_backend(chosen, remainder, original=text)

    if lowered in _SCHEMES:          # bare "sim" / "mock"
        return _parse_for_backend(_SCHEMES[lowered], "", original=text)

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
    if text.count(":") == 1:
        host, port = _split_host_port(text, DEFAULT_RAW_SOCKET_PORT)
        if backend == "vxi11":
            return {"backend": "vxi11", "host": host}
        return {"backend": "socket", "host": host, "port": port}

    if backend not in ("auto", "vxi11"):
        return _parse_for_backend(backend, text, original=text)
    return {"backend": "vxi11", "host": text}


def _parse_for_backend(backend: str, remainder: str, original: str) -> dict:
    """Build keyword arguments for *backend* from the part after the scheme."""
    if backend == "sim":
        return {"backend": "sim"}
    if backend == "visa":
        return {"backend": "visa", "resource": remainder or original}
    if backend == "vxi11":
        host, _, device = remainder.partition("/")
        if not host:
            raise UnsupportedTransportError("no host in resource %r" % original)
        result = {"backend": "vxi11", "host": host}
        if device:
            result["device_names"] = (device,)
        return result
    if backend == "socket":
        host, port = _split_host_port(remainder, DEFAULT_RAW_SOCKET_PORT)
        if not host:
            raise UnsupportedTransportError("no host in resource %r" % original)
        return {"backend": "socket", "host": host, "port": port}
    # A backend registered by another module: hand it the remainder verbatim.
    return {"backend": backend, "resource": remainder or original}


def open_transport(
    resource: str,
    backend: str = "auto",
    timeout: float = 10.0,
    open_now: bool = True,
    responder_factory: Optional[Callable[[], object]] = None,
    **kwargs,
) -> Transport:
    """Create a transport for *resource* and, by default, open it.

    :param resource: Resource string; see the module docstring for the forms.
    :param backend: Backend name, or ``"auto"`` to infer from the resource.
    :param timeout: Default I/O timeout in seconds.
    :param open_now: Open the link before returning.
    :param responder_factory: Called to build the instrument model when the
        resource selects the simulator and no ``responder`` was passed. This is
        how an instrument driver supplies *its own* simulator without this
        module knowing about any instrument.
    :param kwargs: Passed through to the transport constructor.
    """
    parsed = parse_resource(resource, backend)
    chosen = parsed.pop("backend")
    transport_class = _BACKENDS.get(chosen)
    if transport_class is None:  # pragma: no cover - guarded by parse_resource
        raise UnsupportedTransportError("unsupported backend %r" % chosen)

    if chosen == "sim" and responder_factory is not None and "responder" not in kwargs:
        kwargs = dict(kwargs, responder=responder_factory())

    transport = transport_class(timeout=timeout, **parsed, **kwargs)
    _LOG.debug("resource %r resolved to %s", resource, transport.description)
    if open_now:
        transport.open()
    return transport


#: Backwards-compatible view of the accepted backend names.
BACKENDS = registered_backends()
