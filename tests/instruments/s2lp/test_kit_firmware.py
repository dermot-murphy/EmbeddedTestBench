"""The S2-LP driver on the ETB kit firmware (#84).

Traces to: SWE4-UT-S2LPKITHOST, S2LP-FR-098 .. S2LP-FR-100.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError, ProtocolError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import (
    KitSession,
    S2lpDevkit,
    SimulatedKitFirmware,
    SimulatedS2lp,
)
from benchtools.core.errors import TransportTimeoutError
from benchtools.instruments.s2lp import kit_firmware
from benchtools.instruments.s2lp.kit_firmware import parse_identity, parse_record

RSSI, PQI, SQI, AFC = 0xA2, 0x9F, 0xA0, 0x9E


def _kit(simulated, **kwargs) -> S2lpDevkit:
    instrument = S2lpDevkit(MockTransport(responder=simulated), **kwargs)
    instrument.initialise()
    return instrument


@pytest.fixture
def board() -> SimulatedKitFirmware:
    return SimulatedKitFirmware()


@pytest.fixture
def kit(board):
    instrument = _kit(board)
    yield instrument
    instrument.close()


class TestLines:
    def test_a_frame_record_with_registers(self):
        record = parse_record("f 7 123456 3 a218 0a0b0c")
        assert (record.kind, record.seq, record.time_us, record.length) == ("f", 7, 123456, 3)
        assert record.registers == b"\xa2\x18" and record.payload == b"\x0a\x0b\x0c"

    def test_a_frame_record_without_registers(self):
        record = parse_record("f 0 5 2 - beef")
        assert record.registers == b"" and record.payload == b"\xbe\xef"

    def test_a_rejection_record(self):
        record = parse_record("r 3 99 00000002")
        assert (record.kind, record.seq, record.irq) == ("r", 3, 2)

    @pytest.mark.parametrize("line", ["ok", "f 1 2", "f x 2 3 - 00", "r 1 2 zz", "frames=3"])
    def test_anything_else_is_not_a_record(self, line):
        assert parse_record(line) is None

    def test_the_identity(self):
        identity = parse_identity("ok etb-s2lp-kit V1.00.0001 proto=1 silicon=c1")
        assert (identity.version, identity.protocol, identity.silicon) == ("V1.00.0001", 1, 0xC1)
        assert parse_identity("no such command") is None


class TestChoosingTheFirmware:
    def test_the_kit_firmware_is_found_by_asking(self, kit, board):
        assert kit.kit_firmware
        assert isinstance(kit.session, KitSession)
        assert board.command_log[0] == "id"
        assert kit.identify().firmware == "etb-s2lp-kit V1.00.0001"
        assert kit.silicon_version == 0xC1

    def test_st_firmware_answers_id_with_an_error_and_is_kept(self):
        simulator = SimulatedS2lp()
        radio = _kit(simulator)
        try:
            assert not radio.kit_firmware
            assert simulator.command_log[0] == "id"
            assert simulator.command_log[1].startswith("SdkEvalRfboardIdentification")
        finally:
            radio.close()

    def test_firmware_st_does_not_ask(self):
        simulator = SimulatedS2lp()
        radio = _kit(simulator, firmware="st")
        try:
            assert "id" not in simulator.command_log
        finally:
            radio.close()

    def test_firmware_kit_on_st_firmware_is_refused(self):
        radio = S2lpDevkit(MockTransport(responder=SimulatedS2lp()), firmware="kit")
        with pytest.raises(InstrumentError, match="ETB kit firmware"):
            radio.initialise()

    def test_an_unknown_firmware_choice_is_refused(self):
        with pytest.raises(ConfigurationError):
            S2lpDevkit(MockTransport(responder=SimulatedKitFirmware()), firmware="other")

    def test_another_protocol_version_is_refused(self):
        board = SimulatedKitFirmware()
        board._do_id = lambda _words: "ok etb-s2lp-kit V9.00.0000 proto=9 silicon=c1"
        radio = S2lpDevkit(MockTransport(responder=board))
        with pytest.raises(InstrumentError, match="protocol 9"):
            radio.initialise()

    def test_a_board_left_receiving_is_stopped(self, board):
        board.running = True
        radio = _kit(board)
        try:
            assert not board.running
            assert "rx stop" in board.command_log
        finally:
            radio.close()

    def test_the_session_log_carries_on(self, board, tmp_path):
        path = tmp_path / "kit.log"
        radio = S2lpDevkit(MockTransport(responder=board))
        radio.session.log_to(str(path))
        radio.initialise()
        radio.read_register("PCKTLEN0")
        radio.close()
        text = path.read_text(encoding="utf-8")
        assert "> id" in text and "< ok etb-s2lp-kit" in text and "> rd 32 1" in text


class TestRegistersAndCommands:
    def test_registers_read_and_write(self, kit, board):
        kit.write_registers("SYNC3", [0x12, 0x34])
        assert kit.read_registers("SYNC3", 2) == [0x12, 0x34]
        assert board.command_log[-2:] == ["wr 33 1234", "rd 33 2"]

    def test_a_long_read_is_split_to_the_firmware_limit(self, kit, board):
        assert len(kit.read_registers(0x00, 200)) == 200
        assert board.command_log[-2:] == ["rd 00 128", "rd 80 72"]

    def test_a_strobe_and_a_power_cycle(self, kit, board):
        kit.strobe("ready")
        kit.power_cycle(settle=0)
        assert board.command_log[-3:] == ["cmd 62", "sdn 1", "sdn 0"]

    def test_an_err_answer_is_a_protocol_error(self, kit, board):
        board.running = True
        with pytest.raises(ProtocolError, match="receiving"):
            kit.read_register("QI")

    def test_st_commands_are_refused_naming_the_firmware(self, kit):
        with pytest.raises(InstrumentError, match="needs ST's CLI firmware.*etb-s2lp-kit"):
            kit.frequency_hz()
        with pytest.raises(InstrumentError, match="etb-s2lp-kit"):
            kit.transmit(b"ping")


class TestStream:
    def test_frames_with_their_registers_and_decode(self, kit, board):
        board.queue_frame(b"\x01\x02", {RSSI: 0x60, PQI: 40, SQI: 0x9F, AFC: 0xFE})
        board.queue_frame(b"\x03")
        packets = list(kit.stream(decoder=lambda data: {"n": len(data)}, count=2, timeout=2))
        assert [packet.data for packet in packets] == [b"\x01\x02", b"\x03"]
        first = packets[0]
        assert first.registers == {"AFC_CORR": 0xFE, "LINK_QUALIF2": 40,
                                   "LINK_QUALIF1": 0x9F, "RSSI_LEVEL": 0x60}
        assert (first.extra["pqi"], first.extra["sqi"], first.extra["afc_corr"]) == (40, 31, -2)
        assert first.extra["carrier_sense"] == 1
        assert first.rssi_dbm is not None and first.decoded == {"n": 2}
        assert [packet.extra["seq"] for packet in packets] == [0, 1]
        assert packets[1].board_time_us > first.board_time_us
        assert board.command_log[-3].startswith("rx start 9e,9f,a0,a2")
        assert not board.running
        assert kit.kit_counters["frames"] == 2

    def test_registers_may_be_named_in_batch_mode(self, kit, board):
        board.queue_frame(b"\x01", {RSSI: 0x55})
        packet = next(iter(kit.stream(count=1, timeout=2, registers=["RSSI_LEVEL"])))
        assert packet.registers == {"RSSI_LEVEL": 0x55}

    def test_more_than_eight_registers_are_refused(self, kit):
        with pytest.raises(ConfigurationError, match="at most 8"):
            kit.stream(registers=["RSSI_LEVEL"] * 9)

    def test_the_pqi_check_is_on_while_receiving_and_restored(self, kit, board):
        board.queue_frame(b"\x01")
        list(kit.stream(count=1, timeout=2))
        assert "wr 37 03" in board.command_log
        assert board.registers[0x37] == 0x01

    def test_a_lost_record_is_counted_on_the_next(self, kit, board):
        board.queue_frame(b"\x01")
        board.queue_frame(b"\x02", dropped=True)
        board.queue_frame(b"\x03")
        packets = list(kit.stream(count=2, timeout=2))
        assert [packet.extra["seq"] for packet in packets] == [0, 2]
        assert packets[1].extra["lost_before"] == 1
        assert kit.kit_counters["overflows"] == 1

    def test_a_rejection_is_yielded_undecoded(self, kit, board):
        board.queue_reject(0x02)
        packet = next(iter(kit.stream(decoder=lambda data: {}, count=1, timeout=2)))
        assert not packet.ok and packet.error == 2 and packet.decoded is None
        assert packet.extra["irq_status"] == 2

    def test_the_rest_are_set_aside_when_the_count_is_reached(self, kit, board):
        for payload in (b"\x01", b"\x02", b"\x03"):
            board.queue_frame(payload)
        assert [p.data for p in kit.stream(count=1, timeout=2)] == [b"\x01"]
        assert [p.data for p in kit._take_set_aside()] == [b"\x02", b"\x03"]

    def test_a_caller_that_stops_iterating_stops_the_board(self, kit, board):
        board.queue_frame(b"\x01")
        board.queue_frame(b"\x02")
        stream = kit.stream(timeout=2)
        next(stream)
        stream.close()
        assert not board.running and board.command_log[-1] != "rx start"

    def test_until_ends_it_and_what_the_board_still_held_is_yielded(self, kit, board):
        for payload in (b"", b"", b""):
            board.queue_frame(payload)
        taken = []
        for packet in kit.stream(timeout=2, until=lambda: len(taken) >= 1):
            taken.append(packet)
        assert [packet.data for packet in taken] == [b"", b"", b""]
        assert [packet.extra["seq"] for packet in taken] == [0, 1, 2]
        assert not board.running and kit.kit_counters["frames"] == 3

    def test_a_failed_start_still_stops_the_board_and_restores_qi(self, kit, board):
        def refuse(words):
            if words[0] == "start":
                raise ValueError(words)
            return SimulatedKitFirmware._do_rx(board, words)
        board._do_rx = refuse
        with pytest.raises(ProtocolError, match="bad argument"):
            list(kit.stream(timeout=1))
        assert board.command_log[-2:] == ["rx stop", "wr 37 01"]
        assert board.registers[0x37] == 0x01

    def test_a_stop_that_times_out_is_raised_and_tried_again(self, kit, board, monkeypatch):
        monkeypatch.setattr(kit_firmware, "STOP_TIMEOUT", 0.2)
        kit.session.timeout = 0.2
        answer = board.respond
        silent = {"on": True}
        board.respond = lambda message: (
            None if silent["on"] and message.strip() == b"rx stop" else answer(message))
        with pytest.raises(TransportTimeoutError):
            list(kit.stream(timeout=0.2))
        assert board.running and kit.session.receiving    # QI cannot be written now
        assert "wr 37 01" not in board.command_log
        silent["on"] = False
        kit.stop()
        assert not board.running and not kit.session.receiving

    def test_a_record_lost_after_the_last_sent_is_noted(self, board, tmp_path):
        path = tmp_path / "kit.log"
        radio = S2lpDevkit(MockTransport(responder=board))
        radio.session.log_to(str(path))
        radio.initialise()
        board.queue_frame(b"")
        board.queue_frame(b"", dropped=True)
        list(radio.stream(count=1, timeout=1))
        radio.close()
        assert "1 record(s) lost after the last one sent" in path.read_text(encoding="utf-8")

    def test_a_timeout_with_nothing_heard_ends_cleanly(self, kit, board):
        assert not list(kit.stream(timeout=0.2))
        assert not board.running
        assert kit.kit_counters == {"frames": 0, "rejects": 0, "overflows": 0, "deaf_max_us": 0}
