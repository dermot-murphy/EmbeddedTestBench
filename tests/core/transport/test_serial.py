"""The serial transport.

pyserial's ``loop://`` URL provides a real serial object with no hardware, so
the framing and lifecycle are exercised rather than mocked. Tests needing it
skip when the optional extra is absent, which is the correct behaviour for an
optional extra; the resource parsing and registration are checked either way.

Traces to: CORE-FR-017, SWE4-UT-SERIAL.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConnectionFailedError, TransportError
from benchtools.core.transport.factory import parse_resource, registered_backends
from benchtools.core.transport.serial_port import DEFAULT_BAUDRATE, SerialTransport


class TestResourceParsing:
    """No pyserial needed: parsing is separate from opening."""

    @pytest.mark.parametrize(
        "resource,port,baud",
        [
            ("COM5", "COM5", DEFAULT_BAUDRATE),
            ("COM5:9600", "COM5", 9600),
            ("/dev/ttyACM0", "/dev/ttyACM0", DEFAULT_BAUDRATE),
            ("/dev/ttyUSB0:115200", "/dev/ttyUSB0", 115200),
            ("loop://", "loop://", DEFAULT_BAUDRATE),
        ],
    )
    def test_port_and_rate(self, resource, port, baud):
        transport = SerialTransport(resource)
        assert transport.port == port
        assert transport.baudrate == baud

    def test_a_tcp_port_is_not_mistaken_for_a_line_rate(self):
        """serial://socket://host:4001 is how a container reaches a dongle on
        another machine; 4001 is a TCP port, not 4001 baud."""
        transport = SerialTransport("socket://bench-pc:4001")
        assert transport.port == "socket://bench-pc:4001"
        assert transport.baudrate == DEFAULT_BAUDRATE

    def test_an_explicit_rate_wins_over_the_default(self):
        assert SerialTransport("COM5", baudrate=9600).baudrate == 9600

    def test_a_rate_in_the_resource_wins_over_the_argument(self):
        """The resource string is the more specific statement of intent."""
        assert SerialTransport("COM5:4800", baudrate=9600).baudrate == 4800

    def test_no_port_is_rejected(self):
        with pytest.raises(ValueError, match="serial port is required"):
            SerialTransport()

    def test_the_description_names_the_port(self):
        assert "COM5" in SerialTransport("COM5").description

    def test_the_backend_is_registered(self):
        assert "serial" in registered_backends()

    @pytest.mark.parametrize("scheme", ["serial", "com", "rs232"])
    def test_schemes_resolve(self, scheme):
        parsed = parse_resource("%s://COM5" % scheme)
        assert parsed["backend"] == "serial"
        assert parsed["resource"] == "COM5"

    def test_a_posix_device_survives_the_scheme(self):
        assert parse_resource("serial:///dev/ttyACM0")["resource"] == "/dev/ttyACM0"


class TestLifecycle:
    def test_io_before_open_is_rejected(self):
        transport = SerialTransport("loop://")
        with pytest.raises(TransportError, match="not open"):
            transport.write(b"x")

    def test_an_unopenable_port_says_what_to_check(self):
        pytest.importorskip("serial")
        transport = SerialTransport("/dev/definitely-not-a-port")
        with pytest.raises(ConnectionFailedError) as caught:
            transport.open()
        message = str(caught.value)
        assert "cannot open" in message
        assert "COM5 on Windows" in message

    def test_closing_before_opening_is_harmless(self):
        SerialTransport("loop://").close()


class TestLoopback:
    """Against pyserial's own loopback handler."""

    @pytest.fixture
    def transport(self):
        pytest.importorskip("serial")
        instance = SerialTransport("loop://", timeout=2.0)
        instance.open()
        yield instance
        instance.close()

    def test_a_line_round_trips(self, transport):
        transport.write(b"ver")
        assert transport.read_message() == b"ver"

    def test_the_terminator_is_added_and_stripped(self, transport):
        transport.write(b"scan start 1000")
        assert transport.read_message() == b"scan start 1000"

    def test_several_lines_are_framed_separately(self, transport):
        transport.write(b"one")
        transport.write(b"two")
        assert transport.read_message() == b"one"
        assert transport.read_message() == b"two"

    def test_a_long_line_survives(self, transport):
        """Longer than one chunk, within the loopback's buffer."""
        payload = b"x" * 512
        transport.write(payload)
        assert transport.read_message() == payload

    def test_a_write_the_far_end_will_not_take_is_a_timeout(self, transport):
        """Not a connection failure: the port is fine, the far end is not
        reading. pyserial's loopback buffer fills at about 1 kB."""
        from benchtools.core.errors import TransportTimeoutError

        transport.timeout = 0.2
        with pytest.raises(TransportTimeoutError, match="not reading"):
            transport.write(b"x" * 8192)

    def test_a_silent_port_times_out(self, transport):
        from benchtools.core.errors import TransportTimeoutError

        transport.timeout = 0.1
        with pytest.raises(TransportTimeoutError, match="no data"):
            transport.read_message()

    def test_closing_then_reading_is_rejected(self, transport):
        transport.close()
        with pytest.raises(TransportError):
            transport.read_message()


class TestHandshakeLines:
    """DTR and RTS are interface power on some instruments, not flow control.

    The TTi 1604's opto-isolated interface draws its power from them: with DTR
    unasserted the meter is mute, which presents as a dead port rather than as
    a configuration mistake.
    """

    def test_the_lines_are_left_alone_by_default(self):
        transport = SerialTransport(port="loop://")
        assert transport._dtr is None
        assert transport._rts is None

    def test_requested_states_are_applied_after_opening(self):
        transport = SerialTransport(port="loop://", dtr=True, rts=False)
        transport.open()
        try:
            assert transport._serial.dtr is True
            assert transport._serial.rts is False
        finally:
            transport.close()
