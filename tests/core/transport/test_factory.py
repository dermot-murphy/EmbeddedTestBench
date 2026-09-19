"""Resource-string parsing and backend selection.

Traces to: SWE1-FR-005, SWE4-UT-FACTORY.
"""

from __future__ import annotations

import pytest

from benchtools.core import MockTransport, open_transport, parse_resource
from benchtools.core.errors import UnsupportedTransportError


class TestParseResource:
    @pytest.mark.parametrize(
        "resource,expected",
        [
            ("192.168.1.50", {"backend": "vxi11", "host": "192.168.1.50"}),
            ("scope.lab.local", {"backend": "vxi11", "host": "scope.lab.local"}),
            ("vxi11://10.0.0.5", {"backend": "vxi11", "host": "10.0.0.5"}),
            ("TCPIP::192.168.1.50::INSTR", {"backend": "vxi11", "host": "192.168.1.50"}),
        ],
    )
    def test_vxi11_is_the_default(self, resource, expected):
        """A bare address must not require VISA: it resolves to VXI-11."""
        assert parse_resource(resource) == expected

    def test_visa_style_device_name_is_preserved(self):
        parsed = parse_resource("TCPIP0::192.168.1.50::gpib0,1::INSTR")
        assert parsed == {
            "backend": "vxi11", "host": "192.168.1.50", "device_names": ("gpib0,1",)
        }

    def test_explicit_vxi11_device_name(self):
        parsed = parse_resource("vxi11://10.0.0.5/inst0")
        assert parsed["device_names"] == ("inst0",)

    @pytest.mark.parametrize(
        "resource,port",
        [
            ("socket://10.0.0.5:4000", 4000),
            ("socket://10.0.0.5", 4000),
            ("tcp://10.0.0.5:5025", 5025),
            ("TCPIP::10.0.0.5::4000::SOCKET", 4000),
            ("10.0.0.5:4000", 4000),
        ],
    )
    def test_socket_forms(self, resource, port):
        parsed = parse_resource(resource)
        assert parsed["backend"] == "socket"
        assert parsed["host"] == "10.0.0.5"
        assert parsed["port"] == port

    def test_visa_backend_is_opt_in(self):
        """A VISA-style string only uses PyVISA when explicitly asked."""
        assert parse_resource("TCPIP::10.0.0.5::INSTR")["backend"] == "vxi11"
        assert parse_resource("TCPIP::10.0.0.5::INSTR", backend="visa")["backend"] == "visa"
        assert parse_resource("visa://TCPIP::10.0.0.5::INSTR")["backend"] == "visa"

    @pytest.mark.parametrize("resource", ["sim://", "mock://", "sim", "mock"])
    def test_simulator_forms(self, resource):
        assert parse_resource(resource) == {"backend": "sim"}

    def test_backend_can_override_a_bare_host(self):
        assert parse_resource("10.0.0.5", backend="socket")["backend"] == "socket"

    def test_empty_resource_is_rejected(self):
        with pytest.raises(UnsupportedTransportError, match="must not be empty"):
            parse_resource("")

    def test_unknown_backend_is_rejected(self):
        with pytest.raises(UnsupportedTransportError, match="unknown backend"):
            parse_resource("10.0.0.5", backend="gpib")

    def test_malformed_visa_string_is_rejected(self):
        with pytest.raises(UnsupportedTransportError, match="malformed"):
            parse_resource("TCPIP")

    def test_invalid_port_is_rejected(self):
        with pytest.raises(UnsupportedTransportError, match="invalid port"):
            parse_resource("socket://10.0.0.5:notaport")


class TestOpenTransport:
    def test_simulator_opens(self):
        link = open_transport("sim://")
        try:
            assert isinstance(link, MockTransport)
            assert link.is_open
        finally:
            link.close()

    def test_open_now_can_be_deferred(self):
        link = open_transport("sim://", open_now=False)
        assert not link.is_open
