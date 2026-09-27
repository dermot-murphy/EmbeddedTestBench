"""Self-checks on the simulated kit.

A simulator that is wrong is worse than none, because every test above it passes
and none of them mean anything. These assert the model's behaviour directly:
that it is a register file with a radio attached, and not a set of canned
replies.

Traces to: S2LP-FR-050, SWE4-UT-S2LPSIM.
"""

from __future__ import annotations


from benchtools.instruments.s2lp import registers as reg
from benchtools.instruments.s2lp.constants import AFTER_SHUTDOWN_EXIT


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
        assert "{value:03}" in ask(simulator, "S2LPGetPktFrmt")


class TestStrobes:
    def test_the_reset_strobe_leaves_the_register_file_alone(self, simulator):
        """ST's command header: SRES is a "reset of all digital part, except
        SPI registers". Modelling it as a register reset let a driver that used
        it to get defaults pass every test and be wrong on the bench."""
        ask(simulator, "SdkEvalSpiWriteRegisters 0x2E {C0}")
        ask(simulator, "SdkEvalSpiCommandStrobes 112")
        assert "0x2E,0xC0" in ask(simulator, "SdkEvalSpiReadRegisters 0x2E 1")

    def test_the_reset_strobe_does_empty_the_fifos(self, simulator):
        simulator.rx_fifo.extend(b"\x01")
        simulator.tx_fifo.extend(b"\x02")
        ask(simulator, "SdkEvalSpiCommandStrobes 112")
        assert simulator.rx_fifo == bytearray() and simulator.tx_fifo == bytearray()

    def test_shutdown_and_back_is_a_power_on_reset(self, simulator):
        """The only thing here that restores register defaults, because on the
        part it is the only thing that does."""
        ask(simulator, "SdkEvalSpiWriteRegisters 0x2E {C0}")
        ask(simulator, "SdkEvalSdn 1")
        ask(simulator, "SdkEvalSdn 0")
        assert "0x2E,0x20" in ask(simulator, "SdkEvalSpiReadRegisters 0x2E 1")

    def test_leaving_shutdown_applies_st_s_settings(self, simulator):
        """Seen on a kit: ST's firmware writes these on the way out."""
        ask(simulator, "SdkEvalSdn 1")
        ask(simulator, "SdkEvalSdn 0")
        address = reg.BY_NAME["VCO_CONFIG"].address
        assert "0x%02X,0x%02X" % (address, AFTER_SHUTDOWN_EXIT["VCO_CONFIG"]) in ask(
            simulator, "SdkEvalSpiReadRegisters 0x%02X 1" % address)

    def test_a_power_cycle_does_not_undo_the_log_of_what_happened(self, routed):
        """What was transmitted, and what is on the air, are not the radio's
        state."""
        ask(routed, "S2LPPktBasicSetPayloadLength 1")
        ask(routed, "S2LPSendNBytes {01}")
        routed.queue_packet(b"\x02")
        ask(routed, "SdkEvalSdn 1")
        ask(routed, "SdkEvalSdn 0")
        assert routed.transmitted == [b"\x01"]
        assert len(routed.inbound) == 1

    def test_flushing_the_rx_fifo_empties_it(self, routed):
        routed.rx_fifo.extend(b"\x01\x02")
        ask(routed, "SdkEvalSpiCommandStrobes 113")
        assert routed.rx_fifo == bytearray()

    def test_an_unknown_strobe_is_still_acknowledged(self, routed):
        """The radio takes any opcode; it is the radio that decides."""
        assert "API call" in ask(routed, "SdkEvalSpiCommandStrobes 0")


class TestTheAir:
    def test_a_transmitted_packet_is_recorded(self, routed):
        ask(routed, "S2LPPktBasicSetPayloadLength 3")
        ask(routed, "S2LPSendNBytes {01 02 03}")
        assert routed.transmitted == [b"\x01\x02\x03"]

    def test_loopback_hears_what_it_sent(self, routed):
        routed.loopback = True
        ask(routed, "S2LPPktBasicSetPayloadLength 2")
        ask(routed, "S2LPSendNBytes {01 02}")
        assert "{bytes: 0x01,0x02}" in ask(routed, "S2LPGetNBytes 2")

    def test_a_queued_packet_is_delivered_once(self, routed):
        routed.queue_packet(b"\x09")
        assert "{error:00}" in ask(routed, "S2LPGetNBytes 1")
        assert "{{" not in ask(routed, "S2LPGetNBytes 1")

    def test_an_empty_air_answers_nothing_until_stopped(self, routed):
        """ST's receive has no time limit of its own: the echo, then silence."""
        assert ask(routed, "S2LPGetNBytes 4") == "S2LPGetNBytes 4\r\n"
        assert "(StopCmd)" in ask(routed, "S")

    def test_a_packet_arriving_during_a_wait_is_reported(self, routed):
        ask(routed, "S2LPGetNBytes 1")
        routed.queue_packet(b"\x07")
        assert "{bytes: 0x07}" in routed.poll().decode("ascii")

    def test_a_rejected_packet_has_an_error_and_no_bytes(self, routed):
        routed.queue_packet(b"\x07", error=2)
        reply = ask(routed, "S2LPGetNBytes 1")
        assert "{error:02}" in reply and "bytes" not in reply

    def test_a_reception_sets_the_link_quality_registers(self, routed):
        routed.queue_packet(b"\x07", rssi_dbm=-40.0, pqi=33, sqi=17)
        ask(routed, "S2LPGetNBytes 1")
        assert "0x9F,0x21,0xA0,0x11,0xA1,0x00,0xA2,0xD4" in ask(
            routed, "SdkEvalSpiReadRegisters 0x9F 4")

    def test_the_rssi_is_encoded_as_the_register_encodes_it(self, routed):
        """dBm = value / 2 - 146, so -40 dBm is 212 = 0xD4."""
        routed.queue_packet(b"\x01", rssi_dbm=-40.0)
        assert "{rssi:D4}" in ask(routed, "S2LPGetNBytes 1")

    def test_a_batch_answers_once_per_packet(self, routed):
        for index in range(3):
            routed.queue_packet(bytes([index]))
        reply = ask(routed, "S2LPGetNBytesBatch 0 3")
        assert reply.count("(S2LPGetNBytes)") == 3
        assert reply.endswith("{{(S2LPGetNBytesBatch)} API call...}\r\n>")

    def test_report_all_adds_the_firmware_s_extra_fields(self, routed):
        ask(routed, "S2LPGetNBytesReportAll 1")
        routed.queue_packet(b"\x01\x02")
        assert "{packet_len:03}" in ask(routed, "S2LPGetNBytesBatch 0 1")

    def test_the_stop_character_ends_a_batch(self, routed):
        """It is a character, not a command: the firmware polls for it inside
        its capture loop."""
        routed.queue_packet(b"\x01")
        assert ask(routed, "S2LPGetNBytesBatch 0 5").count("(S2LPGetNBytes)") == 1
        assert "(StopCmd)" in ask(routed, "S")
        assert routed.stopped is True

    def test_the_stop_character_is_not_a_command(self, routed):
        ask(routed, "S2LPGetNBytes 1")
        ask(routed, "S")
        assert "S" not in routed.command_log

    def test_a_stop_sent_to_an_idle_board_spoils_the_next_command(self, routed):
        """Seen on a kit: the character waits in the command buffer."""
        assert ask(routed, "S") == "S"
        assert "no such command" in ask(routed, "S2LPGetVersion")
        assert "{value:03C1}" in ask(routed, "S2LPGetVersion")

    def test_a_packet_arriving_while_deaf_is_counted_and_lost(self, routed):
        """Which is what the hardware does, and what a capture cannot see."""
        routed.arrive_while_deaf(b"\x01")
        assert routed.missed == 1
        assert "{{" not in ask(routed, "S2LPGetNBytes 1")




class TestTheInterruptLine:
    """Seen on a kit: send and receive wait for an interrupt that nothing
    routes to the board by default."""

    def test_an_unrouted_send_never_finishes(self, simulator):
        ask(simulator, "S2LPPktBasicSetPayloadLength 1")
        assert ask(simulator, "S2LPSendNBytes {01}") == "S2LPSendNBytes {01}\r\n"

    def test_a_stopped_send_acknowledges_after_the_stop(self, simulator):
        ask(simulator, "S2LPPktBasicSetPayloadLength 1")
        ask(simulator, "S2LPSendNBytes {01}")
        assert ask(simulator, "S") == (
            "{{(StopCmd)} API call...}\r\n{{(S2LPSendNBytes)} API call...}\r\n>")

    def test_an_unrouted_receive_hears_nothing(self, simulator):
        simulator.queue_packet(b"\x01")
        ask(simulator, "S2LPGetNBytes 1")
        assert simulator.poll() is None

    def test_a_payload_shorter_than_the_packet_length_never_goes(self, routed):
        ask(routed, "S2LPPktBasicSetPayloadLength 8")
        assert "{{" not in ask(routed, "S2LPSendNBytes {01 02}")
        assert routed.transmitted == []

    def test_routing_takes_all_three_steps(self, simulator):
        ask(simulator, "S2LPGpioInit 3 2 0")
        ask(simulator, "S2LPIrq 4 1")
        assert not simulator.irq_reaches_board(4)
        ask(simulator, "S2MGpioIrqConfiguration 3 1")
        assert simulator.irq_reaches_board(4)

    def test_mode_1_makes_the_pin_an_input(self, simulator):
        """The CLI's help numbers the modes one lower than the register does;
        following it made GPIO3 an input on the kit."""
        ask(simulator, "S2LPGpioInit 3 1 0")
        ask(simulator, "S2MGpioIrqConfiguration 3 1")
        ask(simulator, "S2LPIrq 4 1")
        assert not simulator.irq_reaches_board(4)
        assert "{value:00}" in ask(simulator, "S2MGpioGetValue 3")

    def test_a_routed_line_idles_high_at_the_board(self, routed):
        assert "{value:01}" in ask(routed, "S2MGpioGetValue 3")

    def test_the_power_on_tx_source_is_pn9_and_a_send_never_ends(self, simulator):
        simulator.route_interrupt()
        ask(simulator, "S2LPPktBasicSetPayloadLength 1")
        assert "{{" not in ask(simulator, "S2LPSendNBytes {01}")
        assert simulator.transmitted == []

    def test_the_packet_handler_setup_selects_the_fifo(self, simulator):
        ask(simulator, "S2LPPktBasicInit 64 32 2290649224 0 0 64 0 0 0")
        assert "0x30,0x40" in ask(simulator, "SdkEvalSpiReadRegisters 0x30 1")


class TestIdentityAndRadio:
    def test_board_identification_names_no_board(self, simulator):
        """As on the kit: the command answers with no tags at all."""
        reply = ask(simulator, "SdkEvalRfboardIdentification 0")
        assert "{{(SdkEvalRfboardIdentification)} API call...}" in reply

    def test_radio_settings_are_remembered(self, simulator):
        ask(simulator, "S2LPRadioInit 915000000 32 38400 20000 100000 0")
        reply = ask(simulator, "S2LPRadioGetInfo")
        assert "{Frequency_base:3689CAC0}" in reply
        assert "{Data_rate:00009600}" in reply

    def test_getters_answer_the_way_the_kit_did(self, simulator):
        """Recorded from a kit on 2026-09-27."""
        assert ask(simulator, "S2LPGetVersion") == (
            "S2LPGetVersion\r\n{{(S2LPGetVersion)} API call...{value:03C1}}\r\n>")
        assert "{value:00010305}" in ask(simulator, "S2LPGetLibVersion")
        assert "{value:120}" in ask(simulator, "S2LPRadioGetPALeveldBm 0")
        assert "{value:-146.0}" in ask(simulator, "S2LPQiGetRssidBm")

    def test_the_timer_advances(self, simulator):
        first = ask(simulator, "CliGetTimer")
        second = ask(simulator, "CliGetTimer")
        assert first != second

    def test_an_unknown_command_is_an_error_not_silence(self, simulator):
        assert "no such command" in ask(simulator, "NotACommand 1")

    def test_an_empty_line_is_ignored(self, simulator):
        assert ask(simulator, "") is None

    def test_every_command_is_logged(self, simulator):
        ask(simulator, "SdkEvalGetVersion")
        assert simulator.command_log == ["SdkEvalGetVersion"]

    def test_replies_end_the_way_the_firmware_ends_them(self, simulator):
        """With a prompt and no line end after it."""
        assert simulator.respond(b"SdkEvalGetVersion").endswith(b"}\r\n>")
