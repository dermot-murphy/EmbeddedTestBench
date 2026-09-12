"""Wire-level tests for the VXI-11 transport.

These run the real client against an independently implemented RPC server on a
loopback socket, which is what substantiates the claim that no VISA library is
needed to drive this instrument.

Traces to: SWE1-FR-001, SWE1-FR-002, SWE4-UT-VXI11.
"""

from __future__ import annotations

import pytest

from tek3014b import SimulatedTDS3014B, Tek3014B, Vxi11Transport
from tek3014b.errors import ConnectionFailedError
from tek3014b.transport import vxi11 as vxi11_module
from tek3014b.transport.vxi11 import _Packer, _Unpacker, query_portmapper

from .vxi11_server import FakePortmapper, FakeVxi11Server


class TestXdrCodec:
    """SWE4-UT-VXI11-001: the XDR codec round-trips every type it uses."""

    def test_scalars_round_trip(self):
        packed = _Packer().int(-7).uint(4294967295).bool(True).bool(False).bytes()
        reader = _Unpacker(packed)
        assert reader.int() == -7
        assert reader.uint() == 4294967295
        assert reader.uint() == 1
        assert reader.uint() == 0

    @pytest.mark.parametrize("payload", [b"", b"a", b"ab", b"abc", b"abcd", b"abcde"])
    def test_opaque_is_padded_to_four_bytes(self, payload):
        packed = _Packer().opaque(payload).bytes()
        assert len(packed) % 4 == 0
        assert _Unpacker(packed).opaque() == payload

    def test_string_round_trips(self):
        packed = _Packer().string("gpib0,1").bytes()
        assert _Unpacker(packed).opaque() == b"gpib0,1"

    def test_truncated_stream_is_rejected(self):
        from tek3014b.errors import ProtocolError

        with pytest.raises(ProtocolError):
            _Unpacker(b"\x00\x00").uint()


class TestVxi11OverASocket:
    """SWE4-UT-VXI11-002: the client drives a real RPC server over TCP."""

    def test_identity_query(self):
        with FakeVxi11Server() as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                assert link.query(b"*IDN?").startswith(b"TEKTRONIX,TDS 3014B")

    def test_link_reports_the_accepted_device_name(self):
        with FakeVxi11Server(device_names=("inst0",)) as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                assert link.device_name == "inst0"

    def test_device_names_are_probed_in_order(self):
        """A VXI-11.2-style instrument that only answers to gpib0,1 still works."""
        with FakeVxi11Server(device_names=("gpib0,1",)) as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                assert link.device_name == "gpib0,1"
                assert server.create_link_attempts[0] == "inst0"

    def test_unknown_device_name_raises(self):
        with FakeVxi11Server(device_names=("something-else",)) as server:
            transport = Vxi11Transport("127.0.0.1", core_port=server.port)
            with pytest.raises(ConnectionFailedError, match="refused every logical device name"):
                transport.open()

    def test_large_transfer_is_reassembled(self):
        """A 10 000-point record arrives intact despite a 1 kB receive size."""
        with FakeVxi11Server(max_recv_size=1024) as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                link.write(b"SELECT:CH1 ON")
                link.write(b"CURVE?")
                block = link.read_raw()
        assert block.startswith(b"#510000")
        assert len(block) == 7 + 10000 + 1

    def test_write_is_chunked_to_max_recv_size(self):
        """A command longer than maxRecvSize is split and reassembled server-side."""
        with FakeVxi11Server(max_recv_size=512) as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                padding = ";:".join(["SELECT:CH1 ON"] * 80)
                link.write(padding.encode("ascii"))
                assert link.query(b"SELECT:CH1?") == b"1"

    def test_device_clear_and_status_byte(self):
        with FakeVxi11Server() as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                link.clear()
                assert link.read_stb() == 16

    def test_remote_local_and_trigger_services(self):
        """The optional VXI-11 services must complete without error."""
        with FakeVxi11Server() as server:
            with Vxi11Transport("127.0.0.1", core_port=server.port) as link:
                link.remote()
                link.trigger()
                link.local()
                assert link.query(b"*IDN?").startswith(b"TEKTRONIX")

    def test_services_before_open_are_rejected(self):
        from tek3014b.errors import TransportError

        transport = Vxi11Transport("127.0.0.1", core_port=1)
        with pytest.raises(TransportError):
            transport.clear()

    def test_empty_host_and_device_list_are_rejected(self):
        with pytest.raises(ValueError, match="host"):
            Vxi11Transport("")
        with pytest.raises(ValueError, match="device_names"):
            Vxi11Transport("127.0.0.1", device_names=())

    def test_full_driver_over_the_socket(self):
        """SWE4-UT-VXI11-003: the whole driver works over a real VXI-11 link."""
        with FakeVxi11Server(simulator=SimulatedTDS3014B()) as server:
            transport = Vxi11Transport("127.0.0.1", core_port=server.port)
            scope = Tek3014B(transport)
            scope.initialise()
            try:
                assert "TDS 3014B" in scope.identity()
                scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0)
                waveforms = scope.capture_single([1])
                assert len(waveforms[1]) == 10000
            finally:
                scope.close()


class TestPortmapper:
    """SWE4-UT-VXI11-004: the portmapper lookup speaks RPC correctly."""

    def test_getport_returns_the_mapped_port(self, monkeypatch):
        with FakePortmapper(mapped_port=4242) as mapper:
            monkeypatch.setattr(vxi11_module, "_PMAP_PORT", mapper.port)
            assert query_portmapper("127.0.0.1", timeout=2.0) == 4242

    def test_unreachable_portmapper_is_reported_clearly(self, monkeypatch):
        # Port 1 is reserved and nothing listens on it, so both TCP and UDP fail.
        monkeypatch.setattr(vxi11_module, "_PMAP_PORT", 1)
        with pytest.raises(ConnectionFailedError, match="portmapper"):
            query_portmapper("127.0.0.1", timeout=0.5)
