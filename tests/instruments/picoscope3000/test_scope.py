"""The driver against the simulated 3405D MSO.

Traces to: PSCOPE-FR-001 .. PSCOPE-FR-020, SWE4-UT-PSCOPE.
"""

from __future__ import annotations

import csv

import pytest

from benchtools.analysis.measure import measure_period
from benchtools.core.errors import (
    AcquisitionTimeoutError,
    ConfigurationError,
    InstrumentError,
)
from benchtools.instruments.picoscope3000 import ChannelSignal, PicoScope3000
from benchtools.instruments.picoscope3000.sdk import Ps3000aSdk


@pytest.fixture
def scope():
    with PicoScope3000.connect("sim://") as instrument:
        yield instrument


def test_identity(scope):
    identity = scope.identify()
    assert identity.manufacturer == "Pico Technology"
    assert identity.model == "PicoScope 3405DMSO"
    assert scope.unit_info()["variant"] == "3405DMSO"
    assert scope.event_source == "PSCOPE"


def test_open_leaves_a_known_state(scope):
    assert scope.enabled_channels() == [1]
    assert scope.enabled_ports() == []
    assert ("set_simple_trigger", (False, 0, 0, 2, 0, 0)) in scope.sdk.calls


def test_resource_forms():
    assert isinstance(PicoScope3000.connect("pico://HT415/0202", initialise=False).sdk,
                      Ps3000aSdk)
    assert PicoScope3000.connect("pico://", initialise=False).sdk._serial is None
    with pytest.raises(ConfigurationError, match="pico://"):
        PicoScope3000.connect("192.168.1.50", initialise=False)


def test_range_rounds_up_and_offset_is_checked(scope):
    setup = scope.configure_channel("B", range_volts=1.2, coupling="AC", offset=-0.5)
    assert setup.range_volts == 2.0 and setup.coupling.value == "AC"
    with pytest.raises(ConfigurationError, match="offset"):
        scope.configure_channel("B", range_volts=0.2, offset=1.0)
    with pytest.raises(ConfigurationError):
        scope.configure_channel("A", range_volts=50)
    with pytest.raises(ConfigurationError):
        scope.configure_channel(5)
    # A refused setting changes nothing.
    assert scope.get_channel_setup("B").range_volts == 2.0


def test_capture_in_si_units(scope):
    scope.configure_channel("A", range_volts=2.0)
    scope.set_sample_interval(1e-6)
    scope.set_record_length(5000, pre_trigger=0.2)
    scope.configure_edge_trigger("A", level=0.0, slope="RISE")
    block = scope.capture()
    record = block.analog[1]
    assert len(record) == 5000
    assert record.source == "A"
    assert record.sample_interval == pytest.approx(1e-6)
    assert record.peak_to_peak == pytest.approx(2.0, abs=0.05)
    # The trigger is at t = 0, 20 % into the record, on a rising zero crossing.
    assert record.times[1000] == pytest.approx(0.0, abs=1e-12)
    assert record.value_at(0.0) == pytest.approx(0.0, abs=0.05)
    assert record.value_at(2e-6) > record.value_at(-2e-6)
    period = measure_period(record)
    assert period.mean == pytest.approx(1e-3, rel=1e-3)


def test_offset_moves_the_window_not_the_reading(scope):
    scope.configure_channel("D", range_volts=0.2, offset=-0.25 + 0.05)  # reads 0.0..0.4 V
    scope.configure_channel("D", range_volts=1.0, offset=-1.0)
    scope.enable_channel("A", False)
    block = scope.capture()
    assert block.analog[4].mean == pytest.approx(1.2, abs=0.01)


def test_four_channels_and_digital_in_one_block(scope):
    for channel in "ABCD":
        scope.configure_channel(channel, range_volts=5.0)
    scope.configure_digital_port(0, threshold=1.5)
    scope.configure_digital_port(1, threshold=1.5)
    scope.set_sample_interval(8e-9)
    with pytest.raises(InstrumentError, match="timebase"):   # as the bench unit refused
        scope.set_sample_interval(1e-9)
        scope.capture()
    scope.set_sample_interval(10e-6)
    scope.set_record_length(1000)
    block = scope.capture()
    assert sorted(block.analog) == [1, 2, 3, 4]
    assert sorted(block.digital) == list(range(16))
    assert block.digital[0].preamble.y_unit == "bit"
    assert set(block.bits(0)) == {0, 1}
    assert block.analog[2].maximum == pytest.approx(3.3, abs=0.05)
    # One time base for all.
    assert block.digital[5].times == block.analog[1].times


def test_digital_trigger_finds_the_edge(scope):
    scope.configure_digital_port(0)
    scope.set_sample_interval(1e-6)
    scope.set_record_length(2000, pre_trigger=0.5)
    scope.configure_digital_trigger({1: "RISE"})
    block = scope.capture()
    bits = block.bits(1)
    assert bits[999] == 0 and bits[1000] == 1


def test_digital_trigger_needs_its_port(scope):
    with pytest.raises(ConfigurationError, match="port 1 is off"):
        scope.configure_digital_trigger({9: "HIGH"})
    with pytest.raises(ConfigurationError):
        scope.configure_digital_trigger({})


def test_no_trigger_times_out_and_auto_captures():
    with PicoScope3000.connect("sim://", timeout=0.2,
                               simulated_signals={1: ChannelSignal("DC", offset=0.1)}) as scope:
        scope.configure_channel("A", range_volts=1.0)
        scope.configure_edge_trigger("A", level=0.5)
        with pytest.raises(AcquisitionTimeoutError):
            scope.capture()
        assert scope.sdk.calls[-1][0] == "stop"
        scope.configure_edge_trigger("A", level=0.5, auto_ms=10)
        assert scope.capture().analog[1].mean == pytest.approx(0.1, abs=0.01)


def test_trigger_level_must_be_on_screen(scope):
    scope.configure_channel("A", range_volts=1.0)
    with pytest.raises(ConfigurationError, match="range"):
        scope.configure_edge_trigger("A", level=1.5)


def test_overrange_is_reported(scope):
    scope.configure_channel("B", range_volts=1.0)       # B is 0..3.3 V
    scope.enable_channel("A", False)
    block = scope.capture()
    assert block.overrange == (2,)
    assert block.analog[2].is_clipped


def test_signal_generator_drives_channel_a(scope):
    scope.set_signal_generator("SQUARE", 2e3, amplitude_pp=1.0, offset=0.5)
    scope.configure_channel("A", range_volts=2.0)
    scope.set_sample_interval(1e-6)
    scope.configure_edge_trigger("A", level=0.5)
    record = scope.capture().analog[1]
    assert record.minimum == pytest.approx(0.0, abs=0.02)
    assert record.maximum == pytest.approx(1.0, abs=0.02)
    assert measure_period(record).mean == pytest.approx(0.5e-3, rel=1e-3)
    scope.signal_generator_off()
    scope.disable_trigger()
    assert scope.capture().analog[1].peak_to_peak == pytest.approx(0.0, abs=0.02)


def test_signal_generator_limits(scope):
    with pytest.raises(ConfigurationError):
        scope.set_signal_generator("SINE", 1e3, amplitude_pp=3.0, offset=1.0)
    with pytest.raises(ConfigurationError):
        scope.set_signal_generator("SINE", 2e6)
    with pytest.raises(ValueError):
        scope.set_signal_generator("NOISE")


def test_channel_spread_matches_the_tds3014b_step(scope):
    for channel in "ABC":
        scope.configure_channel(channel, range_volts=5.0)
    scope.set_sample_interval(1e-6)
    scope.configure_edge_trigger("B", level=1.65)
    records, spread = scope.measure_channel_spread(["A", "B"], absolute_threshold=0.5)
    assert sorted(records) == [1, 2]
    assert spread.spread >= 0
    with pytest.raises(ConfigurationError):
        scope.capture_single(["D"])


def test_csv_holds_analog_and_digital(scope, tmp_path):
    scope.configure_digital_port(0)
    scope.set_record_length(100)
    path = scope.capture().to_csv(str(tmp_path / "block.csv"))
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:3] == ["time_s", "A_volts", "D0"]
    assert len(rows) == 101
    assert rows[1][2] in ("0", "1")


def test_nothing_enabled_is_refused(scope):
    scope.enable_channel("A", False)
    with pytest.raises(ConfigurationError, match="no channel"):
        scope.capture()


def test_record_length_and_threshold_checks(scope):
    with pytest.raises(ConfigurationError):
        scope.set_record_length(1)
    with pytest.raises(ConfigurationError):
        scope.set_record_length(100, pre_trigger=1.5)
    with pytest.raises(ConfigurationError):
        scope.configure_digital_port(0, threshold=6.0)
    with pytest.raises(ConfigurationError):
        scope.configure_digital_port(2)
