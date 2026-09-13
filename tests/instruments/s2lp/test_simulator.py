"""Self-checks on the simulated kit.

A simulator that is wrong is worse than none, because every test above it passes
and none of them mean anything. These assert the model's behaviour directly:
that it is a register file with a radio attached, and not a set of canned
replies.

Traces to: S2LP-FR-050, SWE4-UT-S2LPSIM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.s2lp import SimulatedS2lp, registers as reg
from benchtools.instruments.s2lp.simulator import RX_TIMEOUT


def ask(simulator, command):
    reply = simulator.respond(command.encode("ascii"))
    return None if reply is None else reply.decode("ascii")


class TestRegisterFile:
    def test_it_starts_at_the_documented_reset_values(self, simulator):
        reply = ask(simulator, "SdkEvalSpiReadRegisters 0x2E 1")
        assert "0x2E,0x%02X" % reg.BY_NAME["PCKTCTRL3"].reset in reply

    def test_a_write_is_remembered(self, simulator):
        ask(simulator, "SdkEvalSpiWriteRegisters 0x2E {C0}")
        assert "0x2E,0xC0" in ask(simulator, "SdkEvalSpiReadRegisters 0x2E 1")

    def test_a_block_write_lands_on_consecutive_addresses(self, simulator):
        ask(simulator, "SdkEvalSpiWriteRegisters 0x00 {11 22 33}")
        reply = ask(simulator, "SdkEvalSpiReadRegisters 0x00 3")
        assert "0x00,0x11,0x01,0x22,0x02,0x33" in reply

    def test_a_read_interleaves_address_and_value(self, simulator):
        """As the firmware does - and it is what the driver checks against."""
        reply = ask(simulator, "SdkEvalSpiReadRegisters 0x00 2")
        assert "{regs_list: 0x00,0x0A,0x01,0xA2}" in reply

    def test_a_write_to_a_read_only_register_is_ignored(self, simulator):
        """As the hardware ignores it. The driver refuses such a write; this is
        what would happen if it did not."""
        expected = "0x8E,0x%02X" % reg.BY_NAME["MC_STATE0"].reset
        assert expected in ask(simulator, "SdkEvalSpiReadRegisters 0x8E 1")
        ask(simulator, "SdkEvalSpiWriteRegisters 0x8E {FF}")
        assert expected in ask(simulator, "SdkEvalSpiReadRegisters 0x8E 1")

    def test_the_packet_format_follows_the_register(self, simulator):
        """Not a stored variable: writing PCKTCTRL3 changes what the packet
        format query answers, because that is where the radio keeps it."""
        ask(simulator, "SdkEvalSpiWriteRegisters 0x2E {C0}")
        assert "{format: 3}" in ask(simulator, "S2LPGetPktFrmt")


class TestStrobes:
    def test_reset_restores_the_register_file(self, simulator):
        ask(simulator, "SdkEvalSpiWriteRegisters 0x2E {C0}")
        ask(simulator, "SdkEvalSpiCommandStrobes 112")
        assert "0x2E,0x20" in ask(simulator, "SdkEvalSpiReadRegisters 0x2E 1")

    def test_flushing_the_rx_fifo_empties_it(self, simulator):
        simulator.rx_fifo.extend(b"\x01\x02")
        ask(simulator, "SdkEvalSpiCommandStrobes 113")
        assert simulator.rx_fifo == bytearray()

    def test_an_unknown_strobe_is_still_acknowledged(self, simulator):
        """The radio takes any opcode; it is the radio that decides."""
        assert "API call" in ask(simulator, "SdkEvalSpiCommandStrobes 0")


class TestTheAir:
    def test_a_transmitted_packet_is_recorded(self, simulator):
        ask(simulator, "S2LPSendNBytes {01 02 03}")
        assert simulator.transmitted == [b"\x01\x02\x03"]

    def test_loopback_hears_what_it_sent(self, loopback):
        ask(loopback, "S2LPSendNBytes {01 02}")
        assert "{bytes: 0x01,0x02}" in ask(loopback, "S2LPGetNBytes 2")

    def test_a_queued_packet_is_delivered_once(self, simulator):
        simulator.queue_packet(b"\x09")
        assert "{error:00}" in ask(simulator, "S2LPGetNBytes 1")
        assert "{error:%02X}" % RX_TIMEOUT in ask(simulator, "S2LPGetNBytes 1")

    def test_an_empty_air_answers_with_an_error_not_an_empty_packet(self, simulator):
        reply = ask(simulator, "S2LPGetNBytes 4")
        assert "{error:%02X}" % RX_TIMEOUT in reply
        assert "bytes" not in reply

    def test_the_rssi_is_encoded_as_the_register_encodes_it(self, simulator):
        """dBm = value / 2 - 146, so -40 dBm is 212 = 0xD4."""
        simulator.queue_packet(b"\x01", rssi_dbm=-40.0)
        assert "{rssi:D4}" in ask(simulator, "S2LPGetNBytes 1")

    def test_a_batch_answers_once_per_packet(self, simulator):
        for index in range(3):
            simulator.queue_packet(bytes([index]))
        reply = ask(simulator, "S2LPGetNBytesBatch 0 3")
        assert reply.count("S2LPGetNBytes") == 3

    def test_the_stop_character_ends_a_batch(self, simulator):
        """It is a character, not a command: the firmware polls for it inside
        its capture loop."""
        simulator.stopped = True
        assert ask(simulator, "S2LPGetNBytesBatch 0 5") == ""

    def test_the_stop_character_is_not_a_command(self, simulator):
        assert simulator.respond(b"S") is None
        assert simulator.stopped is True
        assert "S" not in simulator.command_log

    def test_a_packet_arriving_while_deaf_is_counted_and_lost(self, simulator):
        """Which is what the hardware does, and what a capture cannot see."""
        simulator.arrive_while_deaf(b"\x01")
        assert simulator.missed == 1
        assert "{error:%02X}" % RX_TIMEOUT in ask(simulator, "S2LPGetNBytes 1")


class TestIdentityAndRadio:
    def test_board_identification(self, simulator):
        reply = ask(simulator, "SdkEvalRfboardIdentification 0")
        assert "{board: STEVAL-FKI915V1}" in reply
        assert "{xtal: 50000000}" in reply

    def test_radio_settings_are_remembered(self, simulator):
        ask(simulator, "S2LPRadioInit 915000000 32 38400 20000 100000 0")
        reply = ask(simulator, "S2LPRadioGetInfo")
        assert "{frequency: 915000000}" in reply
        assert "{datarate: 38400}" in reply

    def test_the_timer_advances(self, simulator):
        first = ask(simulator, "SdkEvalGetVersion")
        second = ask(simulator, "SdkEvalGetVersion")
        assert first != second

    def test_an_unknown_command_is_an_error_not_silence(self, simulator):
        assert "Command error" in ask(simulator, "NotACommand 1")

    def test_an_empty_line_is_ignored(self, simulator):
        assert ask(simulator, "") is None

    def test_every_command_is_logged(self, simulator):
        ask(simulator, "SdkEvalGetVersion")
        assert simulator.command_log == ["SdkEvalGetVersion"]

    def test_replies_end_the_way_the_firmware_ends_them(self, simulator):
        assert simulator.respond(b"SdkEvalGetVersion").endswith(b"\r\n")
