"""The simulated 1604 itself: what it displays and how it answers keys.

The driver tests rely on this model being right, so it is checked on its own
against the manual: ranges, resolutions, overload and the key rules.

Traces to: DMM-FR-050, SWE4-UT-DMMSIM.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import TransportTimeoutError
from benchtools.instruments.tti1604 import Function, Key, SimulatedTti1604, decode_frame
from benchtools.instruments.tti1604.constants import READING_INTERVAL


@pytest.fixture
def meter() -> SimulatedTti1604:
    instance = SimulatedTti1604()
    instance.respond(Key.REMOTE.encode())
    return instance


class TestPowerOn:
    def test_starts_on_dc_volts_auto_ranging_in_local(self):
        instance = SimulatedTti1604()
        assert instance.function == Function.DC_VOLTS
        assert instance.auto_range is True
        assert instance.remote is False

    def test_local_mode_sends_nothing(self):
        with pytest.raises(TransportTimeoutError):
            SimulatedTti1604().poll()


class TestKeys:
    def test_keys_are_echoed(self, meter):
        assert meter.respond(b"f") == b"f"

    def test_a_character_that_is_not_a_key_is_ignored(self, meter):
        assert meter.respond(b"z") is None

    def test_dropped_keys_are_neither_echoed_nor_acted_on(self, meter):
        meter.drop_keys = 1
        assert meter.respond(Key.OHMS.encode()) is None
        assert meter.function == Function.DC_VOLTS

    def test_ignored_keys_are_echoed_but_not_acted_on(self, meter):
        meter.ignore_keys = True
        assert meter.respond(Key.OHMS.encode()) == b"i"
        assert meter.function == Function.DC_VOLTS

    def test_units_keep_the_coupling(self, meter):
        meter.respond(b"l")                           # AC
        meter.respond(b"e")                           # mA
        assert meter.function == Function.AC_MILLIAMPS

    def test_ac_dc_on_resistance_is_not_accepted(self, meter):
        meter.respond(b"i")
        meter.respond(b"l")
        assert meter.function == Function.OHMS

    def test_hz_is_refused_on_dc(self, meter):
        """"pressing Hz when an AC range is not selected ... not accepted"."""
        meter.respond(b"j")
        assert meter.hertz is False

    def test_changing_function_sets_autorange(self, meter):
        meter.respond(b"a")
        assert meter.auto_range is False
        meter.respond(b"i")
        assert meter.auto_range is True

    def test_up_and_down_lock_the_range(self, meter):
        meter.respond(b"a")
        assert meter.auto_range is False
        assert meter.range_code == 2

    def test_ranges_stop_at_the_ends(self, meter):
        for _ in range(10):
            meter.respond(b"b")
        assert meter.range_code == 1

    def test_operate_toggles_standby(self, meter):
        meter.respond(b"g")
        with pytest.raises(TransportTimeoutError):
            meter.poll()


class TestDisplay:
    @pytest.mark.parametrize(
        "function_keys,quantity,value,shown,label",
        [
            (b"fm", "dc_volts", 3.3, "3.3000", "4 V"),
            (b"fm", "dc_volts", 33.0, "33.000", "40 V"),
            (b"fm", "dc_volts", 1000.0, "1000.0", "1000 V"),
            (b"fl", "ac_volts", 230.0, "230.0", "400 V"),
            (b"nm", "dc_volts", 0.12345, "123.45", "400 mV"),
            (b"em", "dc_amps", 0.0012345, "1.2345", "4 mA"),
            (b"em", "dc_amps", 0.12345, "123.45", "400 mA"),
            (b"dm", "dc_amps", 2.5, "2.500", "10 A"),
            (b"i", "ohms", 100.0, "100.00", "400 ohm"),
            (b"i", "ohms", 4700.0, "4.700", "40 kohm"),
            (b"i", "ohms", 1.0e6, "1.0000", "4 Mohm"),
        ],
    )
    def test_autoranged_displays(self, meter, function_keys, quantity, value, shown, label):
        """Resolution per range as the manual's specification tables give it."""
        meter.respond(function_keys)
        meter.set_input(quantity, value)
        reading = decode_frame(meter.poll())
        assert reading.display == shown
        assert reading.range_label == label
        assert reading.value == pytest.approx(value, rel=1e-3)

    def test_a_manual_range_overloads(self, meter):
        meter.respond(b"b")                           # lock the 4 V range
        meter.set_input("dc_volts", 5.0)
        assert decode_frame(meter.poll()).overload is True

    def test_the_1000_v_range_reads_to_1024(self, meter):
        meter.set_input("dc_volts", 1020.0)
        assert decode_frame(meter.poll()).overload is False
        meter.set_input("dc_volts", 1030.0)
        assert decode_frame(meter.poll()).overload is True

    def test_open_circuit_resistance_is_ofl(self, meter):
        meter.respond(b"i")
        assert decode_frame(meter.poll()).overload is True

    def test_frequency(self, meter):
        meter.respond(b"flj")
        meter.set_input("frequency", 1234.0)
        reading = decode_frame(meter.poll())
        assert reading.function == Function.FREQUENCY
        assert reading.value == 1234.0

    def test_each_reading_advances_the_clock(self, meter):
        before = meter.clock
        meter.poll()
        assert meter.clock == pytest.approx(before + READING_INTERVAL)

    def test_panel_flags_reach_the_frame(self, meter):
        meter.panel_function_bits = 0x20
        meter.panel_status_bits = 0x40
        reading = decode_frame(meter.poll())
        assert reading.relative and reading.display_hold

    def test_unknown_input_is_refused(self, meter):
        with pytest.raises(KeyError, match="no input"):
            meter.set_input("watts", 1.0)
