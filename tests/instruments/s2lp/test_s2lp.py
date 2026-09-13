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
from benchtools.instruments.s2lp.s2lp import rssi_dbm_from_register, rssi_register_from_dbm

from .conftest import PAYLOAD


class TestConnection:
    def test_identity(self, radio):
        identity = radio.identify()
        assert identity.manufacturer == "STMicroelectronics"
        assert identity.model == "STEVAL-FKI915V1"
        assert identity.firmware == SimulatedS2lp.BOARD_VERSION

    def test_it_learns_the_board_and_its_band(self, radio):
        assert radio.board == "STEVAL-FKI915V1"
        assert radio.band == (902_000_000, 928_000_000)

    def test_it_reads_the_crystal_the_firmware_detected(self, radio):
        assert radio.xtal_hz == 50_000_000

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
            assert radio.board

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
            "{{SdkEvalSpiReadRegisters} API callback...\r\n"
            "{regs_list: 0x99,0x11}\r\n{timer:00000001}\r\n}\r\n"
        )
        with pytest.raises(ProtocolError, match="0x99"):
            radio.read_register(0x00)

    def test_a_short_reply_is_caught(self, radio, simulator):
        simulator._cmd_sdkevalspireadregisters = lambda arguments: (
            "{{SdkEvalSpiReadRegisters} API callback...\r\n"
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
        assert all(values[r.address] == r.reset for r in reg.REGISTERS)

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

    def test_reset_returns_the_radio_to_its_reset_values(self, radio):
        radio.write_register("PCKTCTRL3", 0xC0)
        radio.reset(settle=0.0)
        assert radio.registers_differing_from_reset() == {}

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
    def test_a_frequency_outside_the_board_s_band_is_refused(self, radio, hertz):
        """The radio would accept it and transmit into a filter and matching
        network that do not pass it."""
        with pytest.raises(ConfigurationError, match="outside the"):
            radio.set_frequency(hertz)

    def test_the_band_comes_from_the_board_not_from_configuration(self, radio):
        with pytest.raises(ConfigurationError, match="STEVAL-FKI915V1"):
            radio.set_frequency(868_000_000)

    def test_modulation_by_name(self, radio):
        assert radio.set_modulation("ook") == "ook"

    def test_an_unknown_modulation_lists_the_real_ones(self, radio):
        with pytest.raises(ConfigurationError, match="2-gfsk-bt1"):
            radio.set_modulation("lora")

    def test_power(self, radio):
        assert radio.set_power_dbm(12) == 12.0

    def test_payload_length_round_trip(self, radio):
        assert radio.set_payload_length(32) == 32
        assert radio.payload_length == 32

    @pytest.mark.parametrize("length", [0, -1, 256])
    def test_an_impossible_payload_length_is_refused(self, radio, length):
        with pytest.raises(ConfigurationError, match="packet handler"):
            radio.set_payload_length(length)

    def test_rssi_is_read_in_dbm(self, radio):
        assert -160.0 < radio.rssi_dbm < 10.0


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
        assert linked.receive() is None

    def test_a_queued_packet_is_delivered_once(self, linked, loopback):
        loopback.queue_packet(PAYLOAD)
        assert linked.receive() is not None
        assert linked.receive() is None


class TestCapture:
    def test_a_continuous_capture_has_no_gaps(self, linked, loopback):
        for index in range(3):
            loopback.queue_packet(bytes([index]) * 3)
        capture = linked.capture(count=3, timeout=5.0)
        assert capture.count == 3
        assert capture.is_continuous
        assert capture.gaps == 0

    def test_a_polled_capture_reports_its_gaps(self, linked, loopback):
        """Each re-arm is an interval in which nothing could have been heard,
        and a capture that does not say so invites a wrong conclusion."""
        loopback.queue_packet(PAYLOAD)
        capture = linked.capture(count=1, timeout=5.0, continuous=False)
        assert capture.count == 1
        assert capture.is_continuous is True or capture.gaps >= 0
        capture = linked.capture(count=2, timeout=2.0, continuous=False)
        assert capture.gaps > 0
        assert not capture.is_continuous
        assert "not a complete record of the air" in capture.describe()

    def test_a_polled_capture_is_bounded_by_attempts(self, linked):
        """An arm that finds nothing returns at once; without a bound the
        capture would spend its timeout re-arming and call that a result."""
        capture = linked.capture(count=2, timeout=5.0, continuous=False, attempts=5)
        assert capture.gaps == 4
        assert capture.stopped_early

    def test_a_capture_that_gets_nothing_says_so_rather_than_failing(self, linked):
        capture = linked.capture(count=2, timeout=0.5)
        assert capture.count == 0
        assert capture.stopped_early

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
        linked.receive()
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
