"""The simulated S2-LP kit hearing the simulated Kepler sensor (#122).

Unit-level: the transmitter settings the kit must match, the air clock, the
receive path that takes a frame from the air, and the bench option that wires
the two. The Kepler specifications run end to end in
``tests/runner/test_kepler_simulated.py``.

Traces to: S2LP-FR-087, SWE4-UT-KEPLERSIM.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.instruments.s2lp.registers import lookup
from benchtools.instruments.s2lp.s2lp import S2lpDevkit
from benchtools.instruments.s2lp.simulator import SimulatedS2lp
from benchtools.simulated import (
    KEPLER_5C1712_ID,
    Air,
    air,
    air_time,
    kepler_sensor,
    reset_world,
)
from benchtools.simulated.kepler import COPIES, COPY_GAP_S, KEPLER_433_TRANSMITTER

ROOT = pathlib.Path(__file__).resolve().parents[3]
KEPLER_REGS = ROOT / "plugins" / "kepler" / "configs" / "s2lp_kepler_433_rx.regs"


@pytest.fixture(autouse=True)
def clean_world():
    reset_world()
    yield
    reset_world()


def kepler_registers():
    """The register file the Kepler specifications apply, by address."""
    values = {}
    for line in KEPLER_REGS.read_text().splitlines():
        words = line.split("#", 1)[0].split()
        if len(words) == 2:
            values[lookup(words[0]).address] = int(words[1], 0)
    return values


def kit(set_up: bool = True) -> SimulatedS2lp:
    """A simulated kit on 5C1712's air, its interrupt routed."""
    simulator = SimulatedS2lp()
    simulator.air = air(["kepler-5C1712"])
    simulator.route_interrupt()
    if set_up:
        simulator.registers.update(kepler_registers())
    return simulator


def receive(simulator: SimulatedS2lp) -> bytes:
    """Arm one receive and return what the board reports, or b"" for nothing."""
    simulator.respond(b"S2LPGetNBytes 0")
    return simulator.poll() or b""


def frame_bytes(report: bytes) -> bytes:
    found = re.search(rb"\{bytes: ([^}]*)\}", report)
    assert found, report
    return bytes(int(value, 16) for value in found.group(1).split(b","))


class TestHearing:
    """A frame reaches the FIFO only if the kit is set up for the transmitter."""

    def test_the_kepler_register_file_hears_the_sensor(self):
        simulator = kit()
        payload = frame_bytes(receive(simulator))
        assert payload[:3] == bytes.fromhex("5C1712")
        assert simulator.unheard == 0

    def test_a_kit_at_its_reset_values_hears_nothing(self):
        simulator = kit(set_up=False)
        assert receive(simulator) == b""
        assert simulator.unheard == 1

    @pytest.mark.parametrize("name, mask",
                             [entry[:2] for entry in KEPLER_433_TRANSMITTER.registers],
                             ids=[entry[0] for entry in KEPLER_433_TRANSMITTER.registers])
    def test_each_compared_register_matters(self, name, mask):
        """Every register compared matters: flip the lowest bit under its mask."""
        simulator = kit()
        address = lookup(name).address
        lowest = mask & -mask
        simulator.registers[address] ^= lowest
        assert not simulator._hears(KEPLER_433_TRANSMITTER)  # pylint: disable=protected-access

    @pytest.mark.parametrize("field, bit", [("WHIT_EN", 0x10), ("FEC_EN", 0x01)])
    def test_whitening_or_fec_is_not_heard(self, field, bit):
        simulator = kit()
        simulator.registers[lookup("PCKTCTRL1").address] |= bit
        assert not simulator._hears(KEPLER_433_TRANSMITTER), field  # pylint: disable=protected-access

    def test_the_secondary_sync_word_needs_second_sync_sel(self):
        simulator = kit()
        simulator.registers[lookup("PCKTCTRL1").address] &= ~0x02
        assert not simulator._hears(KEPLER_433_TRANSMITTER)  # pylint: disable=protected-access

    def test_the_sensor_sync_word_as_the_primary_is_heard(self):
        simulator = kit()
        simulator.registers[lookup("PCKTCTRL1").address] &= ~0x02
        for index, byte in enumerate((0xA7, 0x0C, 0x9C, 0xB1)):       # LSB first
            simulator.registers[lookup("SYNC3").address + index] = byte
        assert simulator._hears(KEPLER_433_TRANSMITTER)  # pylint: disable=protected-access

    def test_pqi_is_the_whole_preamble(self):
        simulator = kit()
        simulator.registers[lookup("QI").address] |= 0x02          # PQI check on
        receive(simulator)
        assert simulator.registers[lookup("LINK_QUALIF2").address] == 2 * 32 - 1

    def test_a_kit_on_no_air_hears_nothing(self):
        simulator = SimulatedS2lp()
        simulator.route_interrupt()
        simulator.registers.update(kepler_registers())
        assert receive(simulator) == b""
        assert simulator.unheard == 0

    def test_the_board_timer_follows_the_air(self):
        simulator = kit()
        kepler_sensor().reset()                       # VERSION 8 s on, copies 0.1 s apart
        timers = []
        for _ in range(2):
            report = receive(simulator)
            timers.append(int(re.search(rb"\{timer:([0-9A-F]+)\}", report).group(1), 16))
        gap_us = timers[1] - timers[0]
        assert COPY_GAP_S * 1e6 <= gap_us < COPY_GAP_S * 1e6 + 10_000


class TestAir:
    """The air clock, moved on only by a receiver taking a frame."""

    def test_the_clock_moves_to_the_frame_taken(self):
        kepler_sensor().reset()
        sent = air(["kepler-5C1712"]).next_transmission()
        assert sent.at_s == pytest.approx(8.0)
        assert air_time() == pytest.approx(8.0)

    def test_the_earliest_sensor_goes_first(self):
        early, late = kepler_sensor(0x111111), kepler_sensor(0x222222)
        early.alive_period_s, late.alive_period_s = 20, 10
        sent = Air([0x111111, 0x222222]).next_transmission()
        assert sent.source == "222222"

    def test_nothing_when_nobody_transmits(self):
        kepler_sensor().transmitting = False
        assert air(["kepler-5C1712"]).next_transmission() is None

    def test_an_unknown_target_is_refused(self):
        with pytest.raises(ValueError, match="no simulated target"):
            air(["kepler-000000"])


class TestSensorRadio:
    """What the sensor model puts on the air."""

    def test_every_copy_carries_the_same_ticks_and_a_reset_starts_them_at_1(self):
        model = kepler_sensor()
        model.reset()
        copies = [model.transmit() for _ in range(COPIES)]
        assert {copy.payload[81:83] for copy in copies} == {b"\x00\x01"}
        assert model.transmit().payload[12:14] == b"\x00\x02"      # the next, an ALIVE

    def test_a_preamble_written_without_a_reset_is_not_sent(self):
        model = kepler_sensor(KEPLER_5C1712_ID)
        assert model.respond("WR PREAMBLE-LENGTH 48") == "ACK WR PREAMBLE-LENGTH 48 Pairs"
        assert model.transmit().preamble_pairs == 32
        model.reset()
        assert model.transmit().preamble_pairs == 48


class TestBenchOption:
    """``simulated_targets`` wires a simulated kit to the air."""

    def test_the_option_wires_the_kit(self):
        devkit = S2lpDevkit.connect("sim://", simulated_targets=["kepler-5C1712"])
        try:
            assert devkit._transport.responder.air is not None  # pylint: disable=protected-access
        finally:
            devkit.close()

    def test_one_name_as_text_is_accepted(self):
        devkit = S2lpDevkit.connect("sim://", simulated_targets="kepler-5C1712")
        try:
            assert devkit._transport.responder.air.sensor_ids == [KEPLER_5C1712_ID]  # pylint: disable=protected-access
        finally:
            devkit.close()

    def test_without_it_the_kit_hears_no_sensor(self):
        devkit = S2lpDevkit.connect("sim://")
        try:
            assert devkit._transport.responder.air is None  # pylint: disable=protected-access
        finally:
            devkit.close()

    def test_an_unknown_target_is_a_configuration_error(self):
        with pytest.raises(ConfigurationError, match="no simulated target"):
            S2lpDevkit.connect("sim://", simulated_targets=["kepler-000000"])
