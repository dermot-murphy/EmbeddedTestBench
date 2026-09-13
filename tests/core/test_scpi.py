"""The shared SCPI instrument base.

Traces to: CORE-FR-020 .. CORE-FR-028, SWE4-UT-SCPI.
"""

from __future__ import annotations

import pytest

from benchtools.core import MockTransport, SimulatedInstrument
from benchtools.core.errors import InstrumentError, ProtocolError
from benchtools.core.scpi import (
    InstrumentIdentity,
    ScpiInstrument,
    format_ieee_block,
    parse_ieee_block,
)
from benchtools.instruments.generic import GenericScpiInstrument


class TestIeee488Blocks:
    def test_definite_length_round_trip(self):
        assert parse_ieee_block(format_ieee_block(b"x" * 1000)) == b"x" * 1000

    def test_header_length_field_grows_with_the_payload(self):
        assert format_ieee_block(b"ab").startswith(b"#12")
        assert format_ieee_block(b"x" * 1000).startswith(b"#41000")

    def test_indefinite_length(self):
        assert parse_ieee_block(b"#0abcd\n") == b"abcd"

    def test_payload_may_contain_the_terminator(self):
        assert parse_ieee_block(b"#13a\nb") == b"a\nb"

    def test_response_without_a_header_passes_through(self):
        assert parse_ieee_block(b"1,2,3") == b"1,2,3"

    def test_truncated_payload_is_detected(self):
        with pytest.raises(ProtocolError, match="truncated"):
            parse_ieee_block(b"#41000ab")

    def test_empty_response_is_rejected(self):
        with pytest.raises(ProtocolError, match="empty response"):
            parse_ieee_block(b"")


class TestInstrumentIdentity:
    def test_four_fields_are_parsed(self):
        identity = InstrumentIdentity("TEKTRONIX,TDS 3014B,0,CF:91.1CT FV:v3.41")
        assert identity.manufacturer == "TEKTRONIX"
        assert identity.model == "TDS 3014B"
        assert identity.serial_number == "0"
        assert identity.firmware == "CF:91.1CT FV:v3.41"

    def test_short_response_does_not_raise(self):
        """A sparse *IDN? must degrade, not crash: some instruments send fewer fields."""
        identity = InstrumentIdentity("ACME,PSU-1")
        assert identity.model == "PSU-1"
        assert identity.serial_number == ""
        assert identity.firmware == ""

    def test_raw_is_retained(self):
        assert str(InstrumentIdentity("A,B,C,D")) == "A,B,C,D"


class TestGenericInstrument:
    """The generic driver adds nothing, so it tests the base class directly."""

    @pytest.fixture
    def instrument(self):
        device = GenericScpiInstrument.connect("sim://")
        yield device
        device.close()

    def test_identification(self, instrument):
        assert instrument.manufacturer == "BENCHTOOLS"
        assert "SIMULATED" in instrument.model

    def test_identity_is_cached_then_refreshable(self, instrument):
        simulator = instrument.transport.responder
        instrument.identity()
        before = simulator.command_log.count("*IDN?")
        instrument.identity()
        assert simulator.command_log.count("*IDN?") == before
        instrument.identity(refresh=True)
        assert simulator.command_log.count("*IDN?") == before + 1

    def test_scpi_standard_error_queue_is_drained(self, instrument):
        simulator = instrument.transport.responder
        simulator.push_event(-113, "Undefined header")
        simulator.push_event(-222, "Data out of range")
        events = instrument.read_event_queue()
        assert [code for code, _ in events] == [-113, -222]
        assert instrument.read_event_queue() == []

    def test_check_errors_raises_with_detail(self, instrument):
        instrument.transport.responder.push_event(-113, "Undefined header")
        with pytest.raises(InstrumentError, match="-113") as info:
            instrument.check_errors()
        assert info.value.events[0][0] == -113

    def test_check_errors_is_quiet_when_clean(self, instrument):
        instrument.check_errors()

    def test_error_queue_poll_is_bounded(self, instrument):
        """A stuck error queue must not hang the caller."""
        simulator = instrument.transport.responder
        for index in range(200):
            simulator.push_event(-100, "error %d" % index)
        assert len(instrument.read_event_queue()) <= 64

    def test_mandated_queries(self, instrument):
        assert instrument.operation_complete() is True
        assert instrument.event_status() == 0
        assert instrument.self_test_passed() is True

    def test_raw_access(self, instrument):
        instrument.write_raw("*CLS")
        assert instrument.query_raw("*IDN?").startswith("BENCHTOOLS")

    def test_reset_reinitialises(self, instrument):
        instrument.reset(settle=0.0)
        assert instrument.query_raw("*IDN?").startswith("BENCHTOOLS")

    def test_context_manager_closes(self):
        with GenericScpiInstrument.connect("sim://") as device:
            assert device.identity()
        assert not device.transport.is_open

    def test_unparsable_number_is_reported(self, instrument):
        with pytest.raises(ProtocolError, match="expected a number"):
            instrument._query_float("*IDN?")

    def test_compound_query_field_count_is_checked(self, instrument):
        with pytest.raises(ProtocolError, match="expected 3 fields"):
            instrument._query_fields("*IDN?", 3)


class TestSimulatorInjection:
    """A driver supplies its own simulator; the transport layer supplies none."""

    def test_bare_sim_resource_uses_the_driver_simulator(self):
        from benchtools.instruments.tek3014b import SimulatedTDS3014B, Tek3014B

        scope = Tek3014B.connect("sim://")
        try:
            assert isinstance(scope.transport.responder, SimulatedTDS3014B)
        finally:
            scope.close()

    def test_transport_alone_falls_back_to_the_plain_simulator(self):
        from benchtools.core.transport import open_transport

        link = open_transport("sim://")
        try:
            assert isinstance(link.responder, SimulatedInstrument)
            assert link.query(b"*IDN?").startswith(b"BENCHTOOLS")
        finally:
            link.close()

    def test_an_explicit_responder_wins(self):
        class Fake:
            idn = "ACME,FAKE,0,1"

            def respond(self, message):
                return b"ACME,FAKE,0,1\n"

        instrument = GenericScpiInstrument(MockTransport(responder=Fake()))
        instrument.initialise()
        try:
            assert instrument.model == "FAKE"
        finally:
            instrument.close()


class TestSubclassHooks:
    def test_model_name_appears_in_error_messages(self):
        class Widget(ScpiInstrument):
            SIMULATOR_CLASS = SimulatedInstrument
            MODEL_NAME = "Widget 9000"

        device = Widget.connect("sim://")
        try:
            device.transport.responder.push_event(-1, "boom")
            with pytest.raises(InstrumentError, match="Widget 9000"):
                device.check_errors()
        finally:
            device.close()

    def test_auto_check_errors_can_be_disabled(self):
        device = GenericScpiInstrument.connect("sim://", auto_check_errors=False)
        try:
            simulator = device.transport.responder
            simulator.command_log.clear()
            device._after_configuration()
            assert "SYSTEM:ERROR?" not in simulator.command_log
        finally:
            device.close()
