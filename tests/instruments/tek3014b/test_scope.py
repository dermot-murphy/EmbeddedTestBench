"""Driver behaviour against the simulated instrument.

These tests assert both on results and on the exact SCPI sent, because a
command spelling the instrument does not recognise is silently ignored by real
hardware and shows up only as wrong data much later.

Traces to: SWE1-FR-010 .. SWE1-FR-080, SWE4-UT-SCOPE.
"""

from __future__ import annotations

import pytest

from benchtools.core import MockTransport
from benchtools.instruments.tek3014b import Tek3014B, TriggerState
from benchtools.instruments.tek3014b.constants import Coupling, MeasurementType
from benchtools.core.errors import (
    AcquisitionTimeoutError,
    ConfigurationError,
    InstrumentError,
    MeasurementError,
)

from ...conftest import REFERENCE_SKEWS


class TestIdentification:
    def test_identity(self, scope):
        assert scope.identity().startswith("TEKTRONIX,TDS 3014B")

    def test_model(self, scope):
        assert scope.model == "TDS 3014B"

    def test_identity_is_cached(self, scope, simulator):
        scope.identity()
        before = simulator.command_log.count("*IDN?")
        scope.identity()
        assert simulator.command_log.count("*IDN?") == before

    def test_initialise_disables_headers(self, simulator, scope):
        assert simulator.header_enabled is False
        assert simulator.verbose_enabled is False


class TestChannelControl:
    def test_enable_and_disable(self, scope):
        scope.enable_channel(3, True)
        assert scope.is_channel_enabled(3)
        scope.enable_channel(3, False)
        assert not scope.is_channel_enabled(3)

    def test_enabled_channels_lists_only_displayed(self, scope):
        scope.enable_channel(1, True)
        scope.enable_channel(2, True)
        scope.enable_channel(3, False)
        scope.enable_channel(4, False)
        assert scope.enabled_channels() == [1, 2]

    def test_configure_channel_sets_every_field(self, scope, simulator):
        scope.configure_channel(
            2, volts_per_div=0.5, position_div=-2.0, offset_v=0.1,
            coupling="AC", bandwidth="TWENTY",
        )
        assert simulator.displayed[2] is True
        assert simulator.scale[2] == pytest.approx(0.5)
        assert simulator.position[2] == pytest.approx(-2.0)
        assert simulator.offset[2] == pytest.approx(0.1)
        assert simulator.coupling[2] == "AC"
        assert simulator.bandwidth[2] == "TWENTY"

    def test_configure_channel_sends_one_message(self, scope, simulator):
        """Settings are batched so a four-channel setup is four round trips."""
        simulator.command_log.clear()
        scope.configure_channel(1, volts_per_div=1.0, position_div=0.0)
        # One compound write plus the ALLEV? error check.
        assert simulator.command_log.count("ALLEV?") == 1

    def test_unset_fields_are_not_sent(self, scope, simulator):
        simulator.scale[1] = 2.0
        scope.configure_channel(1, position_div=1.0)
        assert simulator.scale[1] == 2.0

    def test_read_back_setup(self, scope):
        scope.configure_channel(4, volts_per_div=0.2, position_div=1.5, coupling="DC")
        setup = scope.get_channel_setup(4)
        assert setup.channel == 4
        assert setup.enabled is True
        assert setup.volts_per_div == pytest.approx(0.2)
        assert setup.position_div == pytest.approx(1.5)
        assert setup.coupling is Coupling.DC

    def test_all_four_channels_are_supported(self, scope):
        for channel in (1, 2, 3, 4):
            scope.configure_channel(channel, volts_per_div=1.0)
        assert scope.enabled_channels() == [1, 2, 3, 4]

    @pytest.mark.parametrize("channel", [0, 5, -1])
    def test_invalid_channel_is_rejected(self, scope, channel):
        with pytest.raises(ConfigurationError, match="not available"):
            scope.configure_channel(channel)

    @pytest.mark.parametrize("volts", [0.0, 0.0005, 20.0])
    def test_out_of_range_sensitivity_is_rejected(self, scope, volts):
        with pytest.raises(ConfigurationError, match="volts/div"):
            scope.configure_channel(1, volts_per_div=volts)

    @pytest.mark.parametrize("position", [-6.0, 6.0])
    def test_out_of_range_position_is_rejected(self, scope, position):
        with pytest.raises(ConfigurationError, match="vertical position"):
            scope.configure_channel(1, position_div=position)

    def test_unsupported_bandwidth_is_rejected(self, scope):
        """The TDS3014B offers 20 MHz and full, not the 150 MHz of wider models."""
        with pytest.raises(ConfigurationError, match="bandwidth limit"):
            scope.configure_channel(1, bandwidth="ONEFIFTY")

    def test_nothing_is_sent_when_validation_fails(self, scope, simulator):
        simulator.command_log.clear()
        with pytest.raises(ConfigurationError):
            scope.configure_channel(1, volts_per_div=1.0, position_div=99.0)
        assert simulator.command_log == []

    def test_apply_setup_configures_a_list(self, scope):
        from benchtools.instruments.tek3014b import ChannelSetup

        scope.apply_setup([
            ChannelSetup(1, volts_per_div=1.0, position_div=-2.0),
            ChannelSetup(2, volts_per_div=2.0, position_div=2.0),
        ])
        assert scope.get_volts_per_div(1) == pytest.approx(1.0)
        assert scope.get_volts_per_div(2) == pytest.approx(2.0)


class TestHorizontalAndTrigger:
    def test_time_base(self, scope):
        scope.set_time_per_div(200.0e-9)
        assert scope.get_time_per_div() == pytest.approx(200.0e-9)

    @pytest.mark.parametrize("seconds", [1.0e-12, 100.0])
    def test_out_of_range_time_base_is_rejected(self, scope, seconds):
        with pytest.raises(ConfigurationError, match="time/div"):
            scope.set_time_per_div(seconds)

    def test_record_length(self, scope):
        scope.set_record_length(500)
        assert scope.get_record_length() == 500

    def test_unsupported_record_length_is_rejected(self, scope):
        with pytest.raises(ConfigurationError, match="record length"):
            scope.set_record_length(1234)

    def test_edge_trigger_configuration(self, scope, simulator):
        scope.configure_edge_trigger(source=2, level=1.4, slope="FALL",
                                     coupling="DC", mode="NORMAL")
        assert simulator.trigger_type == "EDGE"
        assert simulator.trigger_source == "CH2"
        assert simulator.trigger_slope == "FALL"
        assert simulator.trigger_level == pytest.approx(1.4)
        assert simulator.trigger_mode == "NORMAL"

    def test_trigger_source_accepts_a_name(self, scope, simulator):
        scope.configure_edge_trigger(source="EXT", level=0.5)
        assert simulator.trigger_source == "EXT"

    def test_trigger_level_round_trip(self, scope):
        scope.set_trigger_level(-0.75)
        assert scope.get_trigger_level() == pytest.approx(-0.75)

    def test_trigger_state_is_typed(self, scope):
        scope.configure_edge_trigger(source=1, level=1.0)
        assert isinstance(scope.trigger_state(), TriggerState)

    def test_invalid_trigger_channel_is_rejected(self, scope):
        with pytest.raises(ConfigurationError):
            scope.configure_edge_trigger(source=7, level=1.0)


class TestRemainingVerticalAndHorizontalApi:
    """Individual setters and getters, separate from the batched setup path."""

    def test_volts_per_div_round_trip(self, scope):
        scope.set_volts_per_div(3, 0.05)
        assert scope.get_volts_per_div(3) == pytest.approx(0.05)

    def test_volts_per_div_is_range_checked(self, scope):
        with pytest.raises(ConfigurationError, match="volts/div"):
            scope.set_volts_per_div(1, 50.0)

    def test_position_round_trip(self, scope):
        scope.set_position(2, -3.5)
        assert scope.get_position(2) == pytest.approx(-3.5)

    def test_position_is_range_checked(self, scope):
        with pytest.raises(ConfigurationError, match="vertical position"):
            scope.set_position(1, 7.0)

    def test_individual_setters_validate_the_channel(self, scope):
        with pytest.raises(ConfigurationError, match="not available"):
            scope.set_volts_per_div(9, 1.0)
        with pytest.raises(ConfigurationError, match="not available"):
            scope.get_position(0)

    def test_horizontal_delay_is_applied(self, scope, simulator):
        scope.set_horizontal_delay(1.5e-6)
        assert simulator.horizontal_delay == pytest.approx(1.5e-6)

    def test_horizontal_delay_shifts_the_captured_time_axis(self, configured_scope):
        """The delay must appear in the record's time axis, via XZERO."""
        before = configured_scope.capture_single([1])[1]
        configured_scope.set_horizontal_delay(500.0e-9)
        after = configured_scope.capture_single([1])[1]
        assert after.times[0] == pytest.approx(before.times[0] - 500.0e-9, abs=1e-12)

    def test_force_trigger_completes_a_pending_acquisition(self, simulator):
        """With no trigger present, forcing one must let the acquisition finish."""
        simulator.trigger_occurs = False
        scope = Tek3014B(MockTransport(simulator))
        scope.initialise()
        try:
            scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0)
            scope.configure_edge_trigger(source=1, level=1.0, mode="NORMAL")
            scope.run(continuous=False)
            assert scope.is_busy()
            scope.force_trigger()
            assert not scope.is_busy()
        finally:
            scope.close()

    def test_reset_restores_defaults_and_response_format(self, scope, simulator):
        scope.configure_channel(1, volts_per_div=5.0)
        scope.reset(settle=0.0)
        assert simulator.scale[1] == 1.0
        # Headers must be off again, or every later query would be misparsed.
        assert simulator.header_enabled is False
        assert simulator.verbose_enabled is False

    def test_self_test_flag_reads_the_event_status_register(self, scope):
        assert scope.self_test_passed() is True


class TestAcquisition:
    def test_single_completes(self, configured_scope, simulator):
        configured_scope.single(timeout=2.0)
        assert simulator.acquire_state == 0

    def test_busy_is_polled_until_clear(self, configured_scope, simulator):
        simulator.command_log.clear()
        configured_scope.single(timeout=2.0)
        assert simulator.command_log.count("BUSY?") >= 1

    def test_no_trigger_times_out_with_a_useful_message(self, simulator):
        simulator.trigger_occurs = False
        scope = Tek3014B(MockTransport(simulator))
        scope.initialise()
        try:
            scope.configure_edge_trigger(source=1, level=1.0, mode="NORMAL")
            with pytest.raises(AcquisitionTimeoutError, match="trigger condition never occurred"):
                scope.single(timeout=0.2, poll_interval=0.01)
        finally:
            scope.close()

    def test_run_and_stop(self, scope, simulator):
        scope.run()
        assert simulator.acquire_state == 1
        scope.stop()
        assert simulator.acquire_state == 0

    def test_acquisition_mode_with_averaging(self, scope, simulator):
        scope.set_acquisition_mode("AVERAGE", average_count=64)
        assert simulator.acquire_mode == "AVERAGE"
        assert simulator.num_avg == 64

    def test_invalid_average_count_is_rejected(self, scope):
        with pytest.raises(ConfigurationError, match="average count"):
            scope.set_acquisition_mode("AVERAGE", average_count=7)

    def test_zero_timeout_is_rejected(self, configured_scope):
        with pytest.raises(ValueError):
            configured_scope.wait_for_acquisition(timeout=0.0)


class TestCapture:
    def test_record_length_and_scaling(self, configured_scope):
        waveforms = configured_scope.capture_single([1])
        record = waveforms[1]
        assert len(record) == 10000
        assert record.sample_interval == pytest.approx(200.0e-9 * 10 / 10000)
        assert record.peak_to_peak == pytest.approx(3.3, abs=0.15)

    def test_time_axis_is_centred_on_the_trigger(self, configured_scope):
        record = configured_scope.capture_single([1])[1]
        assert record.times[0] == pytest.approx(-1.0e-6, abs=1e-9)
        assert record.times[-1] == pytest.approx(1.0e-6, abs=1e-9)

    def test_all_four_channels_from_one_acquisition(self, configured_scope):
        waveforms = configured_scope.capture_single([1, 2, 3, 4])
        assert sorted(waveforms) == [1, 2, 3, 4]
        assert all(len(w) == 10000 for w in waveforms.values())

    def test_capture_defaults_to_displayed_channels(self, configured_scope):
        assert sorted(configured_scope.capture_single()) == [1, 2, 3, 4]

    def test_two_byte_transfer(self, configured_scope):
        record = configured_scope.capture_single([1], width=2)[1]
        assert len(record) == 10000
        assert record.peak_to_peak == pytest.approx(3.3, abs=0.15)

    def test_partial_record_keeps_absolute_times(self, configured_scope):
        full = configured_scope.capture_single([1])[1]
        part = configured_scope.capture([1], start=5001, stop=6000)[1]
        assert len(part) == 1000
        assert part.times[0] == pytest.approx(full.times[5000], abs=1e-12)

    def test_no_displayed_channel_is_reported(self, scope):
        for channel in (1, 2, 3, 4):
            scope.enable_channel(channel, False)
        with pytest.raises(ConfigurationError, match="no channel is displayed"):
            scope.capture()

    def test_invalid_width_is_rejected(self, configured_scope):
        with pytest.raises(ConfigurationError, match="width"):
            configured_scope.capture([1], width=3)

    def test_duplicate_channels_are_rejected(self, configured_scope):
        with pytest.raises(ConfigurationError, match="more than once"):
            configured_scope.capture([1, 1])

    def test_stop_before_start_is_rejected(self, configured_scope):
        with pytest.raises(ConfigurationError, match="must not be less than"):
            configured_scope.capture([1], start=100, stop=50)

    def test_payload_containing_a_hash_byte_is_not_re_parsed(self, configured_scope):
        """Regression: 0x23 in the sample data must not be read as a block header.

        The driver consumes the IEEE 488.2 header while reading the declared
        length, so the payload must never be passed through the block parser a
        second time.

        The edge is slowed so that the ramp steps through every digitiser code
        between the two levels, which guarantees code 35 ('#') appears in the
        payload rather than leaving it to chance.
        """
        simulator = configured_scope.transport.simulator
        simulator.signals[2].rise_time = 40.0e-9      # ~200 samples across the edge
        configured_scope.configure_channel(2, volts_per_div=1.0, position_div=1.0)
        waveforms = configured_scope.capture_single([2])
        assert len(waveforms[2]) == 10000
        assert 35 in waveforms[2].raw          # the byte that triggered the bug

    def test_every_position_transfers_intact(self, configured_scope):
        """Sweep the vertical position so many code values appear in the payload."""
        for position in (-4.0, -2.0, 0.0, 1.0, 2.0):
            configured_scope.configure_channel(1, volts_per_div=1.0, position_div=position)
            record = configured_scope.capture_single([1])[1]
            assert len(record) == 10000

    def test_ascii_encoding_matches_binary(self, configured_scope):
        """The ASCII transfer path must decode to identical digitiser codes."""
        configured_scope.transport.simulator.signals[2].rise_time = 40.0e-9
        configured_scope.configure_channel(2, volts_per_div=1.0, position_div=1.0)
        binary = configured_scope.capture_single([2])[2]
        ascii_record = configured_scope.capture([2], encoding="ASCII")[2]
        assert ascii_record.raw == binary.raw
        assert ascii_record.volts == pytest.approx(binary.volts)

    def test_csv_export(self, configured_scope, tmp_path):
        waveforms = configured_scope.capture_single([1, 2])
        path = configured_scope.save_csv(waveforms, str(tmp_path / "cap.csv"))
        lines = open(path, encoding="utf-8").read().splitlines()
        assert lines[0] == "time_s,ch1_volts,ch2_volts"
        assert len(lines) == 10001


class TestInstrumentMeasurements:
    def test_period(self, configured_scope):
        assert configured_scope.measure_period(1) == pytest.approx(1.0e-6)

    def test_frequency(self, configured_scope):
        assert configured_scope.measure_frequency(1) == pytest.approx(1.0e6)

    def test_amplitude(self, configured_scope):
        assert configured_scope.measure_amplitude(1) == pytest.approx(3.3)

    def test_delay_between_two_channels(self, configured_scope):
        measured = configured_scope.measure_delay(1, 3)
        assert measured == pytest.approx(REFERENCE_SKEWS[3] - REFERENCE_SKEWS[1])

    def test_delay_requires_a_second_source(self, configured_scope):
        with pytest.raises(ConfigurationError, match="needs source2"):
            configured_scope.measure(MeasurementType.DELAY, source1=1)

    def test_units_are_reported(self, configured_scope):
        configured_scope.measure_period(1)
        assert configured_scope.measure_units() == "s"

    def test_undisplayed_channel_raises(self, configured_scope):
        configured_scope.enable_channel(2, False)
        with pytest.raises(MeasurementError, match="could not compute"):
            configured_scope.measure_period(2)

    def test_summary_skips_what_cannot_be_measured(self, configured_scope):
        summary = configured_scope.measure_summary(1)
        assert summary["period"] == pytest.approx(1.0e-6)
        assert summary["frequency"] == pytest.approx(1.0e6)


class TestHostSideMeasurements:
    def test_spread_matches_the_injected_skews(self, configured_scope):
        _, spread = configured_scope.measure_channel_spread([1, 2, 3, 4])
        expected = max(REFERENCE_SKEWS.values()) - min(REFERENCE_SKEWS.values())
        assert spread.spread == pytest.approx(expected, abs=2.0e-11)

    def test_spread_skews_match_the_instrument_delay_measurement(self, configured_scope):
        """Host-side analysis and the scope's own engine must agree."""
        _, spread = configured_scope.measure_channel_spread([1, 2, 3, 4])
        for channel in (2, 3, 4):
            instrument = configured_scope.measure_delay(1, channel)
            assert spread.skews[channel] == pytest.approx(instrument, abs=2.0e-11)

    def test_spread_identifies_first_and_last(self, configured_scope):
        _, spread = configured_scope.measure_channel_spread([1, 2, 3, 4])
        assert spread.earliest_channel == 1
        assert spread.latest_channel == 3

    def test_spread_needs_two_channels(self, configured_scope):
        with pytest.raises(ConfigurationError, match="at least two channels"):
            configured_scope.measure_channel_spread([1])

    def test_spread_can_reuse_an_existing_capture(self, configured_scope):
        waveforms = configured_scope.capture_single([1, 2, 3, 4])
        records, spread = configured_scope.measure_channel_spread(
            [1, 2, 3, 4], waveforms=waveforms
        )
        assert records is not waveforms          # a copy, not the caller's dict
        assert spread.spread == pytest.approx(25.0e-9, abs=2.0e-11)

    def test_host_period_agrees_with_the_instrument(self, configured_scope):
        _, result = configured_scope.measure_period_host(1)
        assert result.mean == pytest.approx(configured_scope.measure_period(1), rel=1e-3)


class TestScreenshot:
    def test_png_is_written(self, configured_scope, tmp_path):
        path = configured_scope.screenshot(str(tmp_path / "screen.png"))
        data = open(path, "rb").read()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")

    def test_suffix_is_added_when_missing(self, configured_scope, tmp_path):
        path = configured_scope.screenshot(str(tmp_path / "screen"))
        assert path.endswith(".png")

    def test_hardcopy_port_is_switched_to_the_command_interface(
        self, configured_scope, simulator, tmp_path
    ):
        """Without this the image goes to a printer and the read would hang."""
        configured_scope.screenshot(str(tmp_path / "shot.png"))
        assert simulator.hardcopy_port == "GPIB"

    def test_unsupported_format_falls_back(self, configured_scope, simulator, tmp_path, caplog):
        """Older firmware without PNG must still yield an image, not an error."""
        original = simulator._cmd_HARDCOPY_FORMAT

        def reject_png(argument):
            if argument.upper() == "PNG":
                return None          # silently ignored, as old firmware does
            return original(argument)

        simulator._cmd_HARDCOPY_FORMAT = reject_png
        simulator.hardcopy_format = "BMP"
        path = configured_scope.screenshot(str(tmp_path / "shot.png"), image_format="PNG")
        assert simulator.hardcopy_format == "BMPCOLOR"
        assert open(path, "rb").read()

    def test_timeout_is_restored_after_the_transfer(self, configured_scope, tmp_path):
        before = configured_scope.transport.timeout
        configured_scope.screenshot(str(tmp_path / "s.png"), timeout=30.0)
        assert configured_scope.transport.timeout == before


class TestErrorHandling:
    def test_event_queue_is_reported(self, scope, simulator):
        simulator.events.append((113, "Undefined header"))
        with pytest.raises(InstrumentError, match="113"):
            scope.check_errors()

    def test_empty_event_queue_is_not_an_error(self, scope):
        scope.check_errors()

    def test_events_carry_structured_detail(self, scope, simulator):
        simulator.events.append((222, "Data out of range"))
        with pytest.raises(InstrumentError) as info:
            scope.check_errors()
        assert info.value.events[0][0] == 222

    def test_auto_check_can_be_disabled(self, simulator):
        scope = Tek3014B(MockTransport(simulator), auto_check_errors=False)
        scope.initialise()
        try:
            simulator.command_log.clear()
            scope.set_time_per_div(1.0e-6)
            assert "ALLEV?" not in simulator.command_log
        finally:
            scope.close()

    def test_context_manager_closes_the_link(self, simulator):
        with Tek3014B(MockTransport(simulator)) as scope:
            assert scope.identity()
        assert not scope.transport.is_open
