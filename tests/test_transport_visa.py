"""PyVISA transport tests.

Skipped when ``pyvisa`` is not installed, which is the normal case: the driver
does not need it. When it is present these tests run the VISA transport
against the same loopback VXI-11 server the built-in transport is tested
against, so the two paths are proved equivalent on identical traffic.

Traces to: SWE1-FR-004, SWE4-UT-VISA.
"""

from __future__ import annotations

import pytest

from tek3014b import Tek3014B, VisaTransport, pyvisa_available
from tek3014b.errors import ConnectionFailedError

from .vxi11_server import FakeVxi11Server

pytestmark = pytest.mark.skipif(
    not pyvisa_available(), reason="pyvisa is not installed (it is an optional extra)"
)


def resource_for(port: int) -> str:
    """Build a pyvisa-py resource string aimed at the loopback server."""
    return "TCPIP::127.0.0.1::inst0::INSTR"


class TestVisaTransport:
    def test_availability_probe(self):
        assert pyvisa_available() is True

    def test_query_through_pyvisa_py(self, monkeypatch):
        """pyvisa-py's own VXI-11 client must reach the same simulated scope."""
        with FakeVxi11Server() as server:
            _point_pyvisa_py_at(monkeypatch, server.port)
            transport = VisaTransport(resource_for(server.port), visa_library="@py", timeout=5.0)
            with transport as link:
                assert link.query(b"*IDN?").startswith(b"TEKTRONIX,TDS 3014B")

    def test_driver_over_visa(self, monkeypatch):
        with FakeVxi11Server() as server:
            _point_pyvisa_py_at(monkeypatch, server.port)
            transport = VisaTransport(resource_for(server.port), visa_library="@py", timeout=5.0)
            scope = Tek3014B(transport)
            scope.initialise()
            try:
                assert "TDS 3014B" in scope.identity()
                scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0)
                scope.set_time_per_div(200.0e-9)
                scope.configure_edge_trigger(source=1, level=1.65)
                waveforms = scope.capture_single([1])
                assert len(waveforms[1]) == 10000
            finally:
                scope.close()

    def test_bad_resource_is_reported(self):
        transport = VisaTransport("TCPIP::0.0.0.0::inst0::INSTR", visa_library="@py", timeout=0.5)
        with pytest.raises(ConnectionFailedError, match="could not open"):
            transport.open()

    def test_empty_resource_is_rejected(self):
        with pytest.raises(ValueError, match="resource"):
            VisaTransport("")

    def test_description_names_the_resource(self):
        assert "TCPIP" in VisaTransport("TCPIP::1.2.3.4::INSTR").description


def _point_pyvisa_py_at(monkeypatch, port: int) -> None:
    """Make pyvisa-py's VXI-11 client talk to the loopback server's port.

    pyvisa-py resolves the core channel through the portmapper on port 111,
    which needs a privileged bind and a real instrument. Replacing only its
    portmapper client leaves the rest of its stack - RPC record framing,
    create_link, device_write and device_read - genuinely under test.
    """
    from pyvisa_py.protocols import rpc

    class _FixedPortMapper:
        def __init__(self, host, open_timeout=5000):
            self.host = host

        def get_port(self, mapping):
            return port

        def close(self):
            pass

    monkeypatch.setattr(rpc, "TCPPortMapperClient", _FixedPortMapper)
