"""The RF board's identification EEPROM (#80).

Page 0 of the bench kit was read on 2026-09-28; its layout is ST's middleware's
(S2LPManagementIdentificationRFBoard).

Traces to: S2LP-FR-035, SWE4-UT-S2LPEEPROM.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import S2lpDevkit, SimulatedS2lp
from benchtools.instruments.s2lp.eeprom import parse_page0

KIT = SimulatedS2lp.KIT_433_EEPROM


class TestPage0:
    def test_the_bench_kit(self):
        eeprom = parse_page0(KIT)
        assert eeprom.programmed
        assert eeprom.band_hz == 433_000_000
        assert eeprom.band_range_hz == (430_000_000, 440_000_000)
        assert eeprom.xtal_hz == 50_000_000

    @pytest.mark.parametrize("first", [0x00, 0xFF])
    def test_a_blank_eeprom_says_nothing(self, first):
        eeprom = parse_page0(bytes([first]) + KIT[1:])
        assert not eeprom.programmed
        assert eeprom.band_hz is None and eeprom.band_range_hz is None

    @pytest.mark.parametrize("code,hertz", [(3, 868_000_000), (4, 915_000_000),
                                            (0, 169_000_000)])
    def test_the_band_codes(self, code, hertz):
        assert parse_page0(KIT[:3] + bytes([code]) + KIT[4:]).band_hz == hertz

    def test_a_band_with_no_board_here_has_no_range(self):
        assert parse_page0(KIT[:3] + b"\x00" + KIT[4:]).band_range_hz is None


def connect(eeprom=b"", board=""):
    instrument = S2lpDevkit(MockTransport(responder=SimulatedS2lp(eeprom=eeprom)), board=board)
    instrument.initialise()
    return instrument


class TestTheDriver:
    def test_the_band_comes_from_the_eeprom(self):
        radio = connect(KIT)
        assert radio.board == ""
        assert radio.band == (430_000_000, 440_000_000)
        assert radio.eeprom.band_hz == 433_000_000
        radio.close()

    def test_a_frequency_outside_the_eeprom_s_band_is_refused(self):
        radio = connect(KIT)
        with pytest.raises(ConfigurationError, match="outside"):
            radio.set_frequency(868_000_000)
        radio.close()

    def test_a_named_board_that_agrees_is_accepted(self):
        radio = connect(KIT, board="STEVAL-FKI433V2")
        assert radio.band == (430_000_000, 440_000_000)
        radio.close()

    def test_a_named_board_that_disagrees_is_refused(self):
        with pytest.raises(ConfigurationError, match="EEPROM says it was built for 433 MHz"):
            connect(KIT, board="STEVAL-FKI915V1")

    def test_a_blank_eeprom_leaves_the_band_unknown(self):
        radio = connect()
        assert radio.band is None and not radio.eeprom.programmed
        radio.close()

    def test_reading_it_changes_nothing(self):
        kit = SimulatedS2lp(eeprom=KIT)
        radio = S2lpDevkit(MockTransport(responder=kit))
        radio.initialise()
        assert "EepromReadPage 0 0 32" in kit.command_log
        assert not any(line.startswith("EepromWritePage") for line in kit.command_log)
        radio.close()
