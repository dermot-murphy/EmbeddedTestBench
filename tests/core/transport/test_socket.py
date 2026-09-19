"""Raw-socket transport behaviour.

Traces to: SWE1-FR-003, SWE4-UT-SOCKET.
"""

from __future__ import annotations

import pytest

from benchtools.core import SocketTransport
from benchtools.instruments.tek3014b import Tek3014B
from benchtools.core.errors import ConnectionFailedError, TransportTimeoutError

from .scpi_socket_server import ScpiSocketServer


class TestSocketTransport:
    def test_query(self):
        with ScpiSocketServer() as server:
            with SocketTransport("127.0.0.1", port=server.port) as link:
                assert link.query(b"*IDN?").startswith(b"TEKTRONIX")

    def test_binary_block_is_read_by_length(self):
        """A raw socket has no END bit, so the block header is what bounds it."""
        with ScpiSocketServer() as server:
            with SocketTransport("127.0.0.1", port=server.port) as link:
                link.write(b"SELECT:CH1 ON")
                link.write(b"CURVE?")
                assert link.read_exactly(7) == b"#510000"
                assert len(link.read_exactly(10000)) == 10000

    def test_read_raw_uses_the_idle_gap(self):
        """Hardcopy has no length prefix, so the transfer ends at a quiet period."""
        with ScpiSocketServer() as server:
            with SocketTransport("127.0.0.1", port=server.port, idle_gap=0.2) as link:
                link.write(b"HARDCOPY:PORT GPIB")
                link.write(b"HARDCOPY START")
                image = link.read_raw()
        assert image.startswith(b"\x89PNG\r\n\x1a\n")

    def test_full_driver_over_a_socket(self):
        with ScpiSocketServer() as server:
            transport = SocketTransport("127.0.0.1", port=server.port)
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

    def test_refused_connection_mentions_the_tds3014b_limitation(self):
        """The error must steer the user to VXI-11 rather than just failing."""
        transport = SocketTransport("127.0.0.1", port=1, timeout=0.5)
        with pytest.raises(ConnectionFailedError, match="no raw SCPI socket"):
            transport.open()

    def test_silent_instrument_times_out(self):
        with ScpiSocketServer() as server:
            with SocketTransport("127.0.0.1", port=server.port, timeout=0.3) as link:
                link.write(b"SELECT:CH1 ON")   # a set command produces no reply
                with pytest.raises(TransportTimeoutError):
                    link.read_message()

    @pytest.mark.parametrize("port", [0, 70000, -1])
    def test_invalid_port_is_rejected(self, port):
        with pytest.raises(ValueError, match="port"):
            SocketTransport("127.0.0.1", port=port)

    def test_invalid_idle_gap_is_rejected(self):
        with pytest.raises(ValueError, match="idle_gap"):
            SocketTransport("127.0.0.1", idle_gap=0.0)

    def test_empty_host_is_rejected(self):
        with pytest.raises(ValueError, match="host"):
            SocketTransport("")

    def test_description_names_the_endpoint(self):
        assert SocketTransport("10.0.0.5", port=4000).description == "socket 10.0.0.5:4000"
