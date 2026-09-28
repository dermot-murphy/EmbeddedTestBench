"""The S2-LP development kit driver.

Traces to: S2LP-FR-001 .. S2LP-FR-060, SWE4-UT-S2LP.
"""

from __future__ import annotations

import json

import pytest

from benchtools.core.errors import ConfigurationError, ProtocolError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import (
    PacketLog,
    S2lpDevkit,
    SimulatedS2lp,
    registers as reg,
)
from benchtools.instruments.s2lp.constants import AFTER_SHUTDOWN_EXIT
from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.instruments.s2lp.packets import REPORT_ALL_TAGS, BoardClock
from benchtools.instruments.s2lp.packets import rssi_dbm_from_register, rssi_register_from_dbm

from .conftest import PAYLOAD


@pytest.fixture
def radio915(simulator) -> S2lpDevkit:
    """A kit whose board the caller named, so its band is known."""
    instrument = S2lpDevkit(MockTransport(responder=simulator), board="STEVAL-FKI915V1")
    instrument.initialise()
    yield instrument
    instrument.close()


class TestConnection:
    def test_identity(self, radio):
        identity = radio.identify()
        assert identity.manufacturer == "STMicroelectronics"
        assert identity.model == "S2-LP DK"
        assert identity.firmware == "80"
        assert "library 1.3.5" in identity.raw
        assert "S2-LP 0xC1" in identity.raw

    def test_the_board_is_not_invented(self, radio):
        """The firmware never says which board it is on. Reporting a default
        board, and checking frequencies against its band, would present a
        guess as a measurement."""
        assert radio.board == ""
        assert radio.band is None

    def test_a_named_board_brings_its_band(self, radio915):
        assert radio915.board == "STEVAL-FKI915V1"
        assert radio915.band == (902_000_000, 928_000_000)

    def test_an_unknown_board_name_is_refused(self, simulator):
        with pytest.raises(ConfigurationError, match="STEVAL-FKI433V2"):
            S2lpDevkit(MockTransport(responder=simulator), board="STEVAL-FKI999")

    def test_it_reads_the_crystal_the_firmware_uses(self, radio):
        assert radio.xtal_hz == SimulatedS2lp.XTAL_HZ

    def test_it_reads_the_library_and_silicon_versions(self, radio):
        assert radio.library_version == "1.3.5"
        assert radio.silicon_version == 0xC1

    def test_a_radio_that_is_not_an_s2lp_is_refused(self, simulator):
        simulator.PART_NUMBER = 0x02
        instrument = S2lpDevkit(MockTransport(responder=simulator))
        with pytest.raises(Exception, match="part number 0x02"):
            instrument.initialise()

    def test_connecting_configures_nothing(self, simulator):
        """A radio somebody left set up must not be retuned by a driver
        attaching to it."""
        instrument = S2lpDevkit(MockTransport(responder=simulator))
        instrument.initialise()
        written = [line for line in simulator.command_log
                   if line.startswith(("SdkEvalSpiWriteRegisters", "S2LPRadioInit",
                                       "S2LPRadioSetFrequencyBase"))]
        assert written == []
        instrument.close()

    def test_a_bare_port_name_is_a_serial_port(self):
        assert S2lpDevkit._normalise_resource("COM7") == "serial://COM7"
        assert S2lpDevkit._normalise_resource("/dev/ttyACM0") == "serial:///dev/ttyACM0"

    @pytest.mark.parametrize(
        "resource,expected",
        [("sim://", "sim://"), ("", "sim://"), ("sim", "sim"),
         ("serial://COM7", "serial://COM7"),
         ("serial://socket://bench:4003", "serial://socket://bench:4003")],
    )
    def test_resource_forms(self, resource, expected):
        assert S2lpDevkit._normalise_resource(resource) == expected

    def test_connect_through_the_factory(self):
        with S2lpDevkit.connect("sim://") as radio:
            assert radio.silicon_version == 0xC1

    def test_it_is_an_instrument_but_not_scpi(self, radio):
        from benchtools.core.instrument import Instrument
        from benchtools.core.scpi import ScpiInstrument

        assert isinstance(radio, Instrument)
        assert not isinstance(radio, ScpiInstrument)

    def test_closing_is_idempotent(self, radio):
        radio.close()
        radio.close()


class TestRegisters:
    def test_read_one_by_name(self, radio):
        assert radio.read_register("PCKTCTRL3") == reg.BY_NAME["PCKTCTRL3"].reset

    def test_read_one_by_address(self, radio):
        assert radio.read_register(0x2E) == radio.read_register("PCKTCTRL3")

    def test_read_a_block(self, radio):
        values = radio.read_registers("GPIO0_CONF", 4)
        assert values == [reg.BY_ADDRESS[address].reset for address in range(4)]

    def test_write_and_read_back(self, radio):
        radio.write_register("PCKTCTRL3", 0xC0)
        assert radio.read_register("PCKTCTRL3") == 0xC0

    def test_write_a_block(self, radio):
        radio.write_registers(0x00, [0x11, 0x22, 0x33])
        assert radio.read_registers(0x00, 3) == [0x11, 0x22, 0x33]

    def test_a_read_only_register_is_refused_rather_than_ignored(self, radio):
        """The radio would accept the write, discard it, and read back the old
        value - which looks like the driver losing a setting."""
        with pytest.raises(ConfigurationError, match="read-only"):
            radio.write_register("MC_STATE0", 0x01)

    def test_reading_past_the_end_of_the_map_is_refused(self, radio):
        with pytest.raises(ConfigurationError, match="0xFF"):
            radio.read_registers(0xF0, 32)

    def test_a_mis_framed_reply_is_caught_not_believed(self, radio, simulator):
        """The firmware interleaves address and value; if the addresses do not
        match what was asked for, the values are not what was asked for
        either."""
        simulator._cmd_sdkevalspireadregisters = lambda arguments: (
            "{{(SdkEvalSpiReadRegisters)} API callback...\r\n"
            "{regs_list: 0x99,0x11}\r\n{timer:00000001}\r\n}\r\n"
        )
        with pytest.raises(ProtocolError, match="0x99"):
            radio.read_register(0x00)

    def test_a_short_reply_is_caught(self, radio, simulator):
        simulator._cmd_sdkevalspireadregisters = lambda arguments: (
            "{{(SdkEvalSpiReadRegisters)} API callback...\r\n"
            "{regs_list: 0x00,0x11}\r\n{timer:00000001}\r\n}\r\n"
        )
        with pytest.raises(ProtocolError, match="asked for 4"):
            radio.read_registers(0x00, 4)

    def test_read_all_registers_covers_the_map(self, radio):
        values = radio.read_all_registers()
        assert len(values) == len(reg.REGISTERS)
        assert set(values) == set(reg.BY_ADDRESS)

    def test_read_all_registers_is_not_123_round_trips(self, radio, simulator):
        """Contiguous runs, or a dump on a 115200 baud link would crawl."""
        before = len(simulator.command_log)
        radio.read_all_registers()
        assert len(simulator.command_log) - before == len(reg.contiguous_runs())

    def test_a_fresh_radio_reads_back_its_reset_values(self, radio):
        values = radio.read_all_registers()
        assert all(values[r.address] == r.reset for r in reg.REGISTERS if r.writable)

    def test_status_registers_do_not_count_as_changes(self, radio, simulator):
        """RSSI, interrupt flags and the silicon version are never at a
        "reset value" on a live radio. Counting them made every reset check
        fail on a kit."""
        simulator.registers[0xA2] = 0x55
        assert radio.registers_differing_from_reset() == {}

    def test_what_has_been_changed_is_the_short_answer(self, radio):
        radio.write_register("PCKTCTRL3", 0xC0)
        changed = radio.registers_differing_from_reset()
        assert changed == {"PCKTCTRL3": (0x20, 0xC0)}

    def test_the_dump_names_registers_and_decodes_fields(self, radio):
        radio.write_register("PCKTCTRL3", 0xC0)
        dump = radio.dump_registers()
        assert "PCKTCTRL3" in dump
        assert "PCKT_FRMT=3" in dump
        assert len(dump.splitlines()) == len(reg.REGISTERS)


class TestFields:
    def test_read_a_field(self, radio):
        assert radio.read_field("PCKTCTRL3", "RX_MODE") == 2

    def test_writing_a_field_leaves_the_rest_of_the_register_alone(self, radio):
        """The mistake this exists to prevent: writing the field's value to the
        whole register and zeroing everything else."""
        before = radio.read_register("PCKTCTRL3")
        radio.write_field("PCKTCTRL3", "PCKT_FRMT", 3)
        after = radio.read_register("PCKTCTRL3")
        assert after == 0xC0 | (before & 0x3F)
        assert radio.read_field("PCKTCTRL3", "RX_MODE") == 2

    def test_a_value_too_wide_for_the_field_is_refused(self, radio):
        with pytest.raises(ConfigurationError, match="2 bit"):
            radio.write_field("PCKTCTRL3", "PCKT_FRMT", 4)

    def test_an_unknown_field_is_refused(self, radio):
        with pytest.raises(KeyError, match="PCKT_FRMT"):
            radio.write_field("PCKTCTRL3", "NOT_A_FIELD", 1)


class TestStrobes:
    def test_by_name(self, radio, simulator):
        radio.strobe("flush_rx")
        assert "SdkEvalSpiCommandStrobes 113" in simulator.command_log

    def test_by_opcode(self, radio, simulator):
        radio.strobe(0x60)
        assert "SdkEvalSpiCommandStrobes 96" in simulator.command_log

    def test_an_unknown_name_lists_the_strobes(self, radio):
        with pytest.raises(ConfigurationError, match="flush_rx"):
            radio.strobe("transmit")

    def test_the_reset_strobe_does_not_restore_register_defaults(self, radio):
        """ST's command header calls SRES a "reset of all digital part, except
        SPI registers". A radio reset this way comes back configured exactly as
        it was, and code that used it to get defaults would be wrong in a way
        no amount of testing against a forgiving simulator would reveal."""
        radio.write_register("PCKTCTRL3", 0xC0)
        radio.reset(settle=0.0)
        assert radio.read_register("PCKTCTRL3") == 0xC0

    def test_a_power_cycle_clears_what_was_written(self, radio):
        radio.write_register("PCKTCTRL3", 0xC0)
        radio.power_cycle(settle=0.0)
        assert "PCKTCTRL3" not in radio.registers_differing_from_reset()

    def test_a_power_cycle_lands_where_st_s_firmware_leaves_it(self, radio):
        """ST's firmware writes ten registers on the way out of shutdown, so a
        power reset through it is not the datasheet's reset."""
        radio.power_cycle(settle=0.0)
        assert radio.registers_differing_from_reset(expected=AFTER_SHUTDOWN_EXIT) == {}
        assert set(radio.registers_differing_from_reset()) == set(AFTER_SHUTDOWN_EXIT)

    def test_a_power_cycle_goes_through_shutdown(self, radio, simulator):
        radio.power_cycle(settle=0.0)
        assert simulator.command_log[-2:] == ["SdkEvalSdn 1", "SdkEvalSdn 0"]

    def test_restore_defaults_writes_the_map_back(self, radio):
        radio.write_register("PCKTCTRL3", 0xC0)
        radio.write_register("GPIO0_CONF", 0xFF)
        radio.restore_defaults()
        assert radio.registers_differing_from_reset() == {}


class TestRadioConfiguration:
    def test_configure_returns_what_the_radio_says_afterwards(self, radio):
        """Not what it was asked for: the two differ whenever a setting is not
        reachable, and the read-back is the one worth recording."""
        info = radio.configure_radio(frequency_hz=915_000_000, data_rate_bps=38_400)
        assert info["frequency_hz"] == 915_000_000
        assert info["data_rate_bps"] == 38_400
        assert info["modulation_name"] == "2-gfsk-bt1"

    def test_frequency_round_trip(self, radio):
        assert radio.set_frequency(902_500_000) == 902_500_000
        assert radio.frequency_hz == 902_500_000

    @pytest.mark.parametrize("hertz", [868_000_000, 433_000_000, 1_000_000_000])
    def test_a_frequency_outside_the_board_s_band_is_refused(self, radio915, hertz):
        """The radio would accept it and transmit into a filter and matching
        network that do not pass it."""
        with pytest.raises(ConfigurationError, match="outside the"):
            radio915.set_frequency(hertz)

    def test_the_band_comes_from_the_named_board(self, radio915):
        with pytest.raises(ConfigurationError, match="STEVAL-FKI915V1"):
            radio915.set_frequency(868_000_000)

    @pytest.mark.parametrize("hertz", [433_425_000, 868_000_000, 915_000_000])
    def test_an_unknown_board_is_checked_against_the_synthesiser(self, radio, hertz):
        assert radio.set_frequency(hertz) == hertz

    @pytest.mark.parametrize("hertz", [300_000_000, 600_000_000, 1_000_000_000])
    def test_a_frequency_no_s2lp_can_tune_is_refused(self, radio, hertz):
        with pytest.raises(ConfigurationError, match="synthesiser"):
            radio.set_frequency(hertz)

    def test_a_radio_init_the_radio_refuses_is_an_error(self, radio, simulator):
        simulator._cmd_s2lpradioinit = lambda arguments: simulator._call(
            "S2LPRadioInit", "{error:01}")
        with pytest.raises(ConfigurationError, match="error 0x01"):
            radio.configure_radio(frequency_hz=915_000_000)

    def test_modulation_by_name(self, radio):
        assert radio.set_modulation("ook") == "ook"

    def test_an_unknown_modulation_lists_the_real_ones(self, radio):
        with pytest.raises(ConfigurationError, match="2-gfsk-bt1"):
            radio.set_modulation("lora")

    def test_power(self, radio):
        assert radio.set_power_dbm(12) == 12.0

    def test_power_is_read_in_tenths(self, radio, simulator):
        simulator.power_tenths[3] = -105
        assert radio.power_level_dbm(3) == -10.5

    def test_a_negative_power_is_sent_signed(self, radio, simulator):
        """ST's table says ``w`` but the handler reads a signed number."""
        radio.set_power_dbm(-10, index=2)
        assert "S2LPRadioSetPALeveldBm -10 2" in simulator.command_log

    def test_payload_length_round_trip(self, radio):
        assert radio.set_payload_length(32) == 32
        assert radio.payload_length == 32

    @pytest.mark.parametrize("length", [0, -1, 256])
    def test_an_impossible_payload_length_is_refused(self, radio, length):
        with pytest.raises(ConfigurationError, match="packet handler"):
            radio.set_payload_length(length)

    def test_rssi_is_read_in_dbm(self, radio):
        assert radio.rssi_dbm == -146.0

    def test_rssi_keeps_its_sign_and_fraction(self, radio, simulator):
        simulator.queue_packet(PAYLOAD, rssi_dbm=-72.5)
        assert radio.rssi_dbm == -72.5


class TestRssiConversion:
    def test_the_datasheet_conversion(self):
        """dBm = value / 2 - 146."""
        assert rssi_dbm_from_register(0) == -146.0
        assert rssi_dbm_from_register(212) == -40.0

    def test_it_round_trips_across_the_representable_range(self):
        for dbm in (-146.0, -120.0, -100.5, -70.0, -40.0, -18.5):
            assert rssi_dbm_from_register(rssi_register_from_dbm(dbm)) == dbm

    def test_it_stays_inside_a_byte(self):
        """The register is one byte, so the scale stops at -18.5 dBm. Clamping
        is right; pretending 0 dBm is representable would not be."""
        assert rssi_register_from_dbm(500.0) == 255
        assert rssi_dbm_from_register(255) == -18.5
        assert rssi_register_from_dbm(-500.0) == 0


class TestTransmit:
    def test_one_packet(self, linked, loopback):
        packet = linked.transmit(PAYLOAD)
        assert packet.direction == "tx"
        assert packet.data == PAYLOAD
        assert loopback.transmitted == [PAYLOAD]

    def test_text_is_sent_as_its_bytes(self, linked, loopback):
        linked.transmit("ping")
        assert loopback.transmitted == [b"ping"]

    def test_an_empty_transmission_is_refused(self, linked):
        with pytest.raises(ConfigurationError, match="empty transmission"):
            linked.transmit(b"")

    def test_a_payload_longer_than_the_command_carries(self, linked):
        with pytest.raises(ConfigurationError, match="in parts"):
            linked.transmit(b"x" * 256)

    def test_a_batch_runs_on_the_board(self, linked, loopback):
        """The interval is the firmware's, so it is not at the mercy of USB."""
        packets = linked.transmit_batch(PAYLOAD, count=4, interval_ms=1)
        assert len(packets) == 4
        assert loopback.transmitted == [PAYLOAD] * 4


class TestTheInterrupt:
    def test_the_first_send_routes_the_interrupt(self, linked, loopback):
        """ST's firmware waits for an interrupt nothing routes by default."""
        linked.transmit(PAYLOAD)
        assert loopback.irq_reaches_board(0x04)
        assert "S2MGpioIrqConfiguration 3 1" in loopback.command_log

    def test_it_is_routed_once_per_session(self, linked, loopback):
        linked.transmit(PAYLOAD)
        linked.transmit(PAYLOAD)
        assert loopback.command_log.count("S2MGpioIrqConfiguration 3 1") == 1

    def test_connecting_does_not_route_it(self, radio, simulator):
        assert radio.is_open
        assert not simulator.irq_reaches_board(0x04)

    def test_the_packet_length_follows_the_payload(self, linked, loopback):
        """The radio sends exactly PCKTLEN bytes, and waits in TX for more if
        given fewer."""
        linked.transmit(b"abc")
        assert loopback.transmitted == [b"abc"]
        assert linked.payload_length == 3

    def test_routing_is_confirmed_at_the_board(self, linked, loopback):
        """The board's pin must read high: nIRQ idles high."""
        loopback._cmd_s2mgpiogetvalue = lambda arguments: loopback._value(
            "S2MGpioGetValue", "00")
        with pytest.raises(Exception, match="reads 0 at the board"):
            linked.transmit(PAYLOAD)

    def test_the_gpio_is_made_an_output_not_an_input(self, linked, loopback):
        linked.prepare_traffic()
        assert "S2LPGpioInit 3 2 0" in loopback.command_log

    def test_a_send_is_refused_while_the_tx_source_is_pn9(self, radio, simulator):
        """The radio's power-on TX source: it would send PN9 forever."""
        with pytest.raises(ConfigurationError, match="PN9"):
            radio.transmit(PAYLOAD)
        assert simulator.transmitted == []

    def test_configure_packets_reads_back_what_it_set(self, radio):
        info = radio.configure_packets(preamble=64, sync_bits=32, sync_word=0xB19C0CA7,
                                       crc="16-8005")
        assert info["preamble_length"] == 16          # the simulator reports a fixed setup
        assert radio.read_field("PCKTCTRL1", "TXSOURCE") == 0
        assert radio.read_field("PCKTCTRL1", "CRC_MODE") == 2

    def test_an_unknown_crc_mode_lists_the_real_ones(self, radio):
        with pytest.raises(ConfigurationError, match="16-8005"):
            radio.configure_packets(crc="16")

    def test_a_send_that_never_completes_is_stopped_and_aborted(self, linked, loopback):
        linked.prepare_traffic()
        loopback.board_irq_lines.clear()            # the interrupt is lost
        with pytest.raises(Exception, match="did not report the packet sent"):
            linked.transmit(PAYLOAD, timeout=0.2)
        assert loopback.stopped
        assert "SdkEvalSpiCommandStrobes 103" in loopback.command_log
        assert linked.payload_length == len(PAYLOAD)


class TestReceive:
    def test_a_packet_that_was_transmitted_comes_back(self, linked):
        linked.transmit(PAYLOAD)
        packet = linked.receive()
        assert packet is not None
        assert packet.data == PAYLOAD
        assert packet.direction == "rx"

    def test_the_rssi_is_the_one_the_board_reported(self, linked, loopback):
        loopback.queue_packet(PAYLOAD, rssi_dbm=-72.0)
        assert linked.receive().rssi_dbm == -72.0

    def test_nothing_on_the_air_returns_none_not_an_empty_packet(self, linked):
        """An empty packet and no packet are different facts."""
        assert linked.receive(timeout=0.2) is None

    def test_a_receive_that_times_out_is_stopped_on_the_board(self, linked, loopback):
        """ST's receive waits with no limit of its own. Leaving it running would
        lose every later command to a board still listening."""
        linked.receive(timeout=0.2)
        assert loopback.stopped
        assert linked.payload_length == len(PAYLOAD)

    def test_a_rejected_reception_is_logged_but_not_returned(self, linked, loopback, tmp_path):
        path = str(tmp_path / "packets.jsonl")
        linked.start_packet_log(path)
        loopback.queue_packet(PAYLOAD, error=2)
        assert linked.receive(timeout=0.2) is None
        record = PacketLog.read(path)[0]
        assert record["error"] == 2 and record["hex"] == ""

    def test_board_time_is_in_microseconds(self, linked, loopback):
        loopback.timer_us = 1_000_000
        loopback.queue_packet(PAYLOAD)
        assert linked.receive().board_time_us == 1_000_000 + 2_000

    def test_a_queued_packet_is_delivered_once(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        assert linked.receive() is not None
        assert linked.receive(timeout=0.2) is None


#: An ALIVE frame sensor 5C1712 sent on 2026-09-27.
KEPLER_ALIVE = bytes.fromhex(
    "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005")


class TestStream:
    def test_each_frame_carries_the_registers_read_after_it(self, linked, loopback):
        loopback.queue_packet(PAYLOAD, rssi_dbm=-80.0, pqi=33, sqi=17)
        packet = next(linked.stream(count=1, mode="polled"))
        assert packet.registers["LINK_QUALIF2"] == 33
        assert packet.extra["pqi"] == 33 and packet.extra["sqi"] == 17
        assert packet.rssi_dbm == -80.0

    def test_frames_of_any_length(self, linked, loopback):
        """ST's receive ends on data-ready when asked for 0xFFFF bytes."""
        loopback.queue_packet(b"\x01" * 35)
        loopback.queue_packet(b"\x02" * 83)
        lengths = [packet.length for packet in linked.stream(count=2, mode="polled")]
        assert lengths == [35, 83]
        assert "S2LPGetNBytes 65535" in loopback.command_log

    def test_frames_are_decoded(self, linked, loopback):
        loopback.queue_packet(KEPLER_ALIVE)
        packet = next(linked.stream(count=1, decoder=decode_kepler_frame))
        assert packet.decoded["type"] == "ALIVE"
        assert packet.decoded["sensor_id"] == "5C1712"

    def test_a_frame_that_will_not_decode_keeps_its_bytes(self, linked, loopback):
        loopback.queue_packet(b"\x00\x01")
        packet = next(linked.stream(count=1, decoder=decode_kepler_frame))
        assert packet.decoded is None
        assert "8-byte header" in packet.decode_error
        assert packet.data == b"\x00\x01"

    def test_a_rejected_reception_is_yielded_with_its_error(self, linked, loopback):
        loopback.queue_packet(PAYLOAD, error=2)
        packet = next(linked.stream(count=1, decoder=decode_kepler_frame))
        assert packet.error == 2 and packet.decoded is None and packet.decode_error == ""

    def test_raw_and_decoded_are_one_record(self, linked, loopback, tmp_path):
        path = str(tmp_path / "frames.jsonl")
        linked.start_packet_log(path)
        loopback.queue_packet(KEPLER_ALIVE, pqi=40)
        list(linked.stream(count=1, decoder=decode_kepler_frame, mode="polled"))
        record = PacketLog.read(path)[0]
        assert record["hex"] == KEPLER_ALIVE.hex()
        assert record["decoded"]["type"] == "ALIVE"
        assert record["registers"]["LINK_QUALIF2"] == 40
        assert record["extra"]["pqi"] == 40

    def test_a_timeout_ends_the_stream_and_stops_the_board(self, linked, loopback):
        assert not list(linked.stream(timeout=0.3))
        assert loopback.stopped
        assert linked.payload_length == len(PAYLOAD)

    def test_until_ends_a_stream_that_is_waiting(self, linked, loopback):
        calls = []

        def until():
            calls.append(1)
            return len(calls) > 3

        assert not list(linked.stream(until=until))
        assert loopback.stopped

    def test_the_registers_to_read_can_be_chosen(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        packet = next(linked.stream(registers=("RSSI_LEVEL",), count=1, mode="polled"))
        assert list(packet.registers) == ["RSSI_LEVEL"]
        assert "pqi" not in packet.extra


class TestBatchStream:
    """The default: ST's receive loop, as ST's GUI starts it (#87)."""

    def test_it_is_the_default_and_starts_the_loop_once(self, linked, loopback):
        for index in range(3):
            loopback.queue_packet(bytes([index]) * 3)
        packets = list(linked.stream(count=3))
        assert [packet.data[0] for packet in packets] == [0, 1, 2]
        assert loopback.command_log.count("S2LPGetNBytesBatch 0 3") == 1
        assert "S2LPGetNBytes 65535" not in loopback.command_log

    def test_receiving_is_set_up_as_st_s_gui_does(self, linked, loopback):
        """Read from the kit while the GUI received: infinite RX timeout,
        low-power receive off. Once per session."""
        loopback.queue_packet(PAYLOAD)
        loopback.queue_packet(PAYLOAD)
        list(linked.stream(count=1))
        list(linked.stream(count=1))
        assert loopback.command_log.count("S2LPTimerSetRxTimeoutUs 0") == 1
        assert loopback.command_log.count("S2LPGetBatchLP 0") == 1
        assert linked.read_register("TIMERS5") == 0

    def test_the_board_re_arms_before_printing(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        list(linked.stream(count=1))
        assert "S2LPGetNBytesReportAll 1" in loopback.command_log

    def test_without_a_count_it_runs_until_stopped(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        assert len(list(linked.stream(timeout=0.3))) == 1
        assert "S2LPGetNBytesBatch 0 4294967295" in loopback.command_log
        assert loopback.stopped
        assert linked.payload_length == len(PAYLOAD)

    def test_frames_carry_the_firmware_s_fields_and_no_registers(self, linked, loopback):
        loopback.queue_packet(KEPLER_ALIVE, rssi_dbm=-90.0)
        packet = next(linked.stream(count=1, decoder=decode_kepler_frame))
        assert packet.rssi_dbm == -90.0
        assert packet.extra["packet_len"] == len(KEPLER_ALIVE) + 1
        assert packet.registers == {}
        assert packet.decoded["type"] == "ALIVE"

    def test_registers_are_refused_in_batch_mode(self, linked):
        with pytest.raises(ConfigurationError, match="polled"):
            linked.stream(registers=("RSSI_LEVEL",))

    def test_an_unknown_mode_is_refused(self, linked):
        with pytest.raises(ConfigurationError, match="batch, polled"):
            linked.stream(mode="interrupt")

    def test_a_caller_that_stops_iterating_stops_the_board(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        loopback.queue_packet(PAYLOAD)
        frames = linked.stream()
        next(frames)
        frames.close()
        assert loopback.stopped
        assert linked.payload_length == len(PAYLOAD)

    def test_until_ends_it(self, linked, loopback):
        calls = []

        def until():
            calls.append(1)
            return len(calls) > 3

        assert not list(linked.stream(until=until))
        assert loopback.stopped

    def test_rejections_are_yielded(self, linked, loopback):
        loopback.queue_packet(PAYLOAD, error=2)
        assert next(linked.stream(count=1)).error == 2


class TestBoardClock:
    def test_it_passes_readings_through_until_a_wrap(self):
        clock = BoardClock()
        assert clock.unwrap(10) == 10
        assert clock.unwrap(20) == 20

    def test_a_smaller_reading_is_one_wrap(self):
        """The 32-bit microsecond counter wraps every 71.6 minutes."""
        clock = BoardClock()
        clock.unwrap(0xFFFFFF00)
        assert clock.unwrap(0x10) == (1 << 32) + 0x10


class TestCapture:
    def test_a_batch_capture_is_not_gap_free(self, linked, loopback):
        """ST's batch loop re-arms the radio after each packet. Calling that
        continuous, as this driver once did, claimed a complete record of the
        air that the firmware does not give."""
        for index in range(3):
            loopback.queue_packet(bytes([index]) * 3)
        capture = linked.capture(count=3, timeout=5.0)
        assert capture.count == 3
        assert capture.gaps == 2
        assert capture.rearm == "firmware"
        assert not capture.is_continuous

    def test_a_batch_capture_asks_for_the_early_re_arm(self, linked, loopback):
        """With ReportAll on, ST's loop re-arms before printing the report."""
        loopback.queue_packet(PAYLOAD)
        linked.capture(count=1, timeout=5.0)
        assert "S2LPGetNBytesReportAll 1" in loopback.command_log

    def test_a_batch_capture_carries_the_firmware_s_extra_fields(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        packet = linked.capture(count=1, timeout=5.0).packets[0]
        assert packet.extra["packet_len"] == len(PAYLOAD) + 1
        assert set(packet.extra) == set(REPORT_ALL_TAGS)

    def test_a_single_reception_is_continuous(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        assert linked.capture(count=1, timeout=5.0).is_continuous

    def test_rejected_receptions_are_kept_apart(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        loopback.queue_packet(PAYLOAD, error=2)
        loopback.queue_packet(PAYLOAD)
        capture = linked.capture(count=3, timeout=5.0)
        assert capture.count == 2
        assert [packet.error for packet in capture.rejected] == [2]
        assert "1 rejected" in capture.describe()

    def test_a_polled_capture_reports_its_gaps(self, linked, loopback):
        """Each re-arm is an interval in which nothing could have been heard,
        and a capture that does not say so invites a wrong conclusion."""
        loopback.queue_packet(PAYLOAD)
        loopback.queue_packet(PAYLOAD)
        capture = linked.capture(count=2, timeout=5.0, continuous=False)
        assert capture.count == 2
        assert capture.gaps == 1
        assert capture.rearm == "host"
        assert "host re-arm" in capture.describe()
        assert "not a complete record of the air" in capture.describe()

    def test_a_polled_capture_with_nothing_on_the_air_stops_the_board(self, linked, loopback):
        capture = linked.capture(count=2, timeout=0.3, continuous=False)
        assert capture.count == 0
        assert capture.stopped_early
        assert loopback.stopped
        assert linked.payload_length == len(PAYLOAD)

    def test_a_capture_that_gets_nothing_says_so_rather_than_failing(self, linked, loopback):
        capture = linked.capture(count=2, timeout=0.5)
        assert capture.count == 0
        assert capture.stopped_early
        assert loopback.stopped
        assert linked.payload_length == len(PAYLOAD)

    def test_the_summary_carries_the_signal_level(self, linked, loopback):
        loopback.queue_packet(PAYLOAD, rssi_dbm=-60.0)
        loopback.queue_packet(PAYLOAD, rssi_dbm=-80.0)
        capture = linked.capture(count=2, timeout=5.0)
        assert capture.mean_rssi_dbm == -70.0
        assert "-70.0 dBm" in capture.describe()


class TestLogs:
    def test_the_session_log_carries_both_directions(self, linked, tmp_path):
        path = linked.start_log(str(tmp_path / "session.log"))
        linked.transmit(PAYLOAD)
        linked.receive(timeout=0.5)
        text = open(path, encoding="utf-8").read()
        assert " > S2LPSendNBytes" in text
        assert " < {" in text

    def test_the_session_log_is_flushed_per_line(self, linked, tmp_path):
        """The log of a session that then hung is the log worth having."""
        path = linked.start_log(str(tmp_path / "session.log"))
        linked.transmit(PAYLOAD)
        assert "S2LPSendNBytes" in open(path, encoding="utf-8").read()

    def test_the_packet_log_is_one_json_object_per_packet(self, linked, tmp_path):
        path = str(tmp_path / "packets.jsonl")
        linked.start_packet_log(path)
        linked.transmit(PAYLOAD)
        linked.receive()
        records = PacketLog.read(path)
        assert [record["direction"] for record in records] == ["tx", "rx"]
        assert records[1]["hex"] == PAYLOAD.hex()
        assert records[1]["rssi_dbm"] is not None

    def test_a_note_goes_into_both_logs(self, linked, tmp_path):
        session = linked.start_log(str(tmp_path / "session.log"))
        packets = str(tmp_path / "packets.jsonl")
        linked.start_packet_log(packets)
        linked.log_note("sensor under test: A3")
        assert "sensor under test: A3" in open(session, encoding="utf-8").read()
        assert PacketLog.read(packets)[0]["note"] == "sensor under test: A3"

    def test_a_truncated_packet_log_still_reads(self, tmp_path):
        """A capture killed mid-write should be readable up to its last
        complete record."""
        path = tmp_path / "packets.jsonl"
        path.write_text(json.dumps({"direction": "rx"}) + "\n{\"direction\": \"r")
        assert len(PacketLog.read(str(path))) == 1

    def test_both_logs_can_be_opened_at_connect(self, tmp_path):
        with S2lpDevkit.connect(
            "sim://",
            log_path=str(tmp_path / "s.log"),
            packet_log=str(tmp_path / "p.jsonl"),
        ) as radio:
            assert radio.log_path and radio.packet_log_path
