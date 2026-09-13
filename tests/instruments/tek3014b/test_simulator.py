"""Self-checks on the instrument simulator.

The simulator is test equipment in its own right: if it misrepresents the
instrument, every test above it is worthless. These tests pin down the
behaviour the driver relies on.

Traces to: SWE4-UT-ENV.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.tek3014b.constants import INVALID_MEASUREMENT
from benchtools.instruments.tek3014b.simulator import ChannelSignal, SimulatedTDS3014B, make_png


class TestSignalModel:
    def test_square_wave_levels(self):
        signal = ChannelSignal(frequency=1.0e6, amplitude=3.3, baseline=0.0, rise_time=1.0e-12)
        assert signal.value_at(0.25e-6) == pytest.approx(3.3)   # inside the high time
        assert signal.value_at(0.75e-6) == pytest.approx(0.0)   # inside the low time

    def test_delay_shifts_the_waveform(self):
        signal = ChannelSignal(frequency=1.0e6, delay=100.0e-9, rise_time=1.0e-12)
        assert signal.value_at(50.0e-9) == pytest.approx(0.0)
        assert signal.value_at(150.0e-9) == pytest.approx(signal.high)

    def test_absent_signal_is_flat(self):
        signal = ChannelSignal(present=False, baseline=0.5)
        assert signal.value_at(1.0e-6) == 0.5

    def test_rise_time_is_a_linear_ramp(self):
        signal = ChannelSignal(frequency=1.0e6, amplitude=2.0, rise_time=4.0e-9)
        assert signal.value_at(2.0e-9) == pytest.approx(1.0)


class TestCommandHandling:
    def test_unknown_command_lands_in_the_event_queue(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("NOT:A:COMMAND 1")
        assert simulator.events and simulator.events[0][0] == 113

    def test_compound_commands_are_split(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("SELECT:CH2 ON;:CH2:SCALE 0.5")
        assert simulator.displayed[2] is True
        assert simulator.scale[2] == pytest.approx(0.5)

    def test_compound_queries_return_joined_values(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("CH1:SCALE 2.0;:CH1:POSITION -1.0")
        assert simulator.handle("CH1:SCALE?;:CH1:POSITION?").split(";") == [
            "2.000000E+00", "-1.000000E+00"
        ]

    def test_reset_restores_defaults(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("CH1:SCALE 5.0")
        simulator.handle("*RST")
        assert simulator.scale[1] == 1.0

    def test_query_only_command_is_rejected(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("CH1:PROBE 10")
        assert simulator.events and "query only" in simulator.events[0][1]


class TestWaveformGeneration:
    def test_curve_length_follows_the_transfer_range(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("DATA:START 1;:DATA:STOP 500")
        assert len(simulator.curve(1)) == 500

    def test_two_byte_transfer_doubles_the_payload(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("DATA:WIDTH 2")
        assert len(simulator.curve(1)) == 20000

    def test_curve_block_header_is_well_formed(self):
        simulator = SimulatedTDS3014B()
        reply = simulator.respond(b"CURVE?")
        assert reply.startswith(b"#510000")
        assert len(reply) == 7 + 10000 + 1

    def test_samples_clip_at_the_digitiser_rail(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("CH1:POSITION 4.0;:CH1:SCALE 0.1")
        assert max(simulator.curve(1)) == 127


class TestMeasurementModel:
    def test_measurements_come_from_the_model_not_the_samples(self):
        simulator = SimulatedTDS3014B(
            signals={1: ChannelSignal(frequency=2.5e6, amplitude=1.8)}
        )
        simulator.handle("SELECT:CH1 ON;:MEASUREMENT:IMMED:TYPE PERIOD"
                         ";:MEASUREMENT:IMMED:SOURCE1 CH1")
        assert float(simulator.handle("MEASUREMENT:IMMED:VALUE?")) == pytest.approx(1 / 2.5e6)

    def test_undisplayed_channel_returns_the_invalid_sentinel(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("SELECT:CH2 OFF;:MEASUREMENT:IMMED:TYPE PERIOD"
                         ";:MEASUREMENT:IMMED:SOURCE1 CH2")
        assert float(simulator.handle("MEASUREMENT:IMMED:VALUE?")) == pytest.approx(INVALID_MEASUREMENT)

    def test_delay_reflects_the_configured_skew(self):
        simulator = SimulatedTDS3014B(signals={
            1: ChannelSignal(delay=0.0), 2: ChannelSignal(delay=7.0e-9),
        })
        simulator.handle("SELECT:CH1 ON;:SELECT:CH2 ON;:MEASUREMENT:IMMED:TYPE DELAY"
                         ";:MEASUREMENT:IMMED:SOURCE1 CH1;:MEASUREMENT:IMMED:SOURCE2 CH2")
        assert float(simulator.handle("MEASUREMENT:IMMED:VALUE?")) == pytest.approx(7.0e-9)


class TestHardcopy:
    def test_png_signature_and_dimensions(self):
        image = make_png(64, 32)
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        assert image[16:24] == (64).to_bytes(4, "big") + (32).to_bytes(4, "big")
        assert image.endswith(b"IEND\xae\x42\x60\x82")

    def test_hardcopy_needs_the_command_port(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("HARDCOPY:PORT CENTRONICS")
        assert simulator.respond(b"HARDCOPY START") is None
        assert simulator.events

    def test_unsupported_format_is_refused(self):
        simulator = SimulatedTDS3014B()
        simulator.handle("HARDCOPY:FORMAT SVG")
        assert simulator.hardcopy_format == "PNG"
        assert simulator.events
