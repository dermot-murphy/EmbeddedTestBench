"""The shared simulator harness.

Traces to: CORE-FR-040, CORE-FR-041, SWE4-UT-SIMBASE.
"""

from __future__ import annotations

import pytest

from benchtools.core.simulator import (
    COMMAND_ERROR,
    UNDEFINED_HEADER,
    Responder,
    SimulatedInstrument,
    format_number,
    scpi_slug,
)


class TestSlugAndFormat:
    @pytest.mark.parametrize(
        "header,slug",
        [
            ("*IDN?", "IDN_Q"),
            ("*RST", "RST"),
            ("CH1:SCALE?", "CH1_SCALE_Q"),
            ("MEASUREMENT:IMMED:VALUE?", "MEASUREMENT_IMMED_VALUE_Q"),
            ("select:ch2", "SELECT_CH2"),
        ],
    )
    def test_slug(self, header, slug):
        assert scpi_slug(header) == slug

    def test_number_format_is_nr3(self):
        assert format_number(1e-6) == "1.000000E-06"
        assert format_number(-0.5) == "-5.000000E-01"


class TestBaseSimulator:
    @pytest.fixture
    def simulator(self):
        return SimulatedInstrument()

    def test_satisfies_the_responder_protocol(self, simulator):
        assert isinstance(simulator, Responder)

    def test_mandated_queries(self, simulator):
        assert simulator.respond(b"*IDN?") == b"BENCHTOOLS,SIMULATED INSTRUMENT,0,1.0\n"
        assert simulator.respond(b"*OPC?") == b"1\n"
        assert simulator.respond(b"*ESR?") == b"0\n"
        assert simulator.respond(b"*CLS") is None

    def test_custom_idn(self):
        assert SimulatedInstrument(idn="ACME,PSU,1,2").respond(b"*IDN?") == b"ACME,PSU,1,2\n"

    def test_commands_are_logged(self, simulator):
        simulator.respond(b"*CLS")
        simulator.respond(b"*IDN?")
        assert simulator.command_log == ["*CLS", "*IDN?"]

    def test_compound_message_is_split(self, simulator):
        assert simulator.respond(b"*CLS;:*IDN?") == b"BENCHTOOLS,SIMULATED INSTRUMENT,0,1.0\n"
        assert simulator.command_log == ["*CLS", "*IDN?"]

    def test_compound_queries_are_joined(self, simulator):
        assert simulator.respond(b"*OPC?;:*ESR?") == b"1;0\n"

    def test_unknown_header_is_recorded_not_ignored(self, simulator):
        """A driver that misspells a command must fail a test, not pass quietly."""
        simulator.respond(b"NOT:A:COMMAND 1")
        assert simulator.events[0][0] == UNDEFINED_HEADER
        assert simulator.esr & 0x20

    def test_unknown_query_still_answers(self, simulator):
        """An unanswered query would hang the driver instead of failing it."""
        assert simulator.respond(b"NOT:A:QUERY?") == b"\n"

    def test_error_queue_pops_one_at_a_time(self, simulator):
        simulator.push_event(-100, "first")
        simulator.push_event(-200, "second")
        assert simulator.respond(b"SYSTEM:ERROR?") == b'-100,"first"\n'
        assert simulator.respond(b"SYSTEM:ERROR?") == b'-200,"second"\n'
        assert simulator.respond(b"SYSTEM:ERROR?") == b'0,"No error"\n'

    def test_error_count(self, simulator):
        simulator.push_event(-1, "x")
        assert simulator.respond(b"SYSTEM:ERROR:COUNT?") == b"1\n"

    def test_quotes_in_a_message_do_not_break_the_response(self, simulator):
        simulator.push_event(-113, 'Undefined header; command "FOO"')
        assert simulator.respond(b"SYSTEM:ERROR?").count(b'"') == 2

    def test_reset_clears_the_queue(self, simulator):
        simulator.push_event(-1, "x")
        simulator.respond(b"*RST")
        assert simulator.events == []

    def test_binary_reply(self, simulator):
        class WithImage(SimulatedInstrument):
            def _cmd_IMAGE_Q(self, _argument):
                self.set_binary_reply(b"\x89PNG\r\n\x1a\n")
                return None

        assert WithImage().respond(b"IMAGE?") == b"\x89PNG\r\n\x1a\n"


class TestSubclassing:
    def test_subclass_adds_commands_and_keeps_the_base(self):
        class Psu(SimulatedInstrument):
            DEFAULT_IDN = "ACME,PSU-1,0,1.0"

            def reset(self):
                super().reset()
                self.voltage = 0.0

            def _cmd_VOLTAGE(self, argument):
                self.voltage = float(argument)
                return None

            def _cmd_VOLTAGE_Q(self, _argument):
                return format_number(self.voltage)

        psu = Psu()
        assert psu.respond(b"*IDN?") == b"ACME,PSU-1,0,1.0\n"
        psu.respond(b"VOLTAGE 3.3")
        assert psu.respond(b"VOLTAGE?") == b"3.300000E+00\n"
        psu.respond(b"*RST")
        assert psu.respond(b"VOLTAGE?") == b"0.000000E+00\n"

    def test_unknown_command_hook_can_match_a_family(self):
        class Multi(SimulatedInstrument):
            def _unknown_command(self, element):
                head = element.partition(" ")[0].upper()
                if head.startswith("OUT") and head.endswith("?"):
                    return "1"
                return super()._unknown_command(element)

        multi = Multi()
        assert multi.respond(b"OUTPUT3?") == b"1\n"
        multi.respond(b"NONSENSE")
        assert multi.events[0][0] == UNDEFINED_HEADER

    def test_command_error_code_is_available(self):
        simulator = SimulatedInstrument()
        simulator.push_event(COMMAND_ERROR, "query only")
        assert simulator.events == [(COMMAND_ERROR, "query only")]
