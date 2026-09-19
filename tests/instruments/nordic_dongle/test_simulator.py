"""Self-checks on the simulated dongle.

A test double that is too permissive is worse than none, because the suite
reports success. These tests hold the simulator to the behaviour the driver
relies on: exact advertising intervals, refusals where the firmware refuses,
and drop counters that reconcile.

Traces to: BLE-FR-080, SWE4-UT-BLESIM.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.nordic_dongle.constants import DongleError
from benchtools.instruments.nordic_dongle.protocol import parse_line
from benchtools.instruments.nordic_dongle.simulator import (
    DEFAULT_SENSORS,
    SimulatedDongle,
    SimulatedSensor,
)


def send(simulator, line):
    """Send one command and return the parsed lines it produced."""
    raw = simulator.respond((line + "\n").encode())
    return [parse_line(text) for text in raw.decode().splitlines() if text]


def reply_of(lines):
    return [item for item in lines if item is not None and hasattr(item, "ok")][-1]


class TestProtocol:
    def test_identity(self, simulator):
        reply = reply_of(send(simulator, "ver"))
        assert reply.ok and "proto" in reply.fields

    def test_an_unknown_command_is_refused(self, simulator):
        reply = reply_of(send(simulator, "fly"))
        assert reply.ok is False and reply.error is DongleError.UNKNOWN

    def test_the_command_log_records_what_arrived(self, simulator):
        send(simulator, "ver")
        send(simulator, "time")
        assert simulator.command_log == ["ver", "time"]

    def test_a_blank_line_is_not_a_command(self, simulator):
        assert simulator.respond(b"\n") is None

    def test_the_clock_advances_monotonically(self, simulator):
        first = reply_of(send(simulator, "time")).fields["t"]
        send(simulator, "scan start 5000")
        simulator.poll()
        second = reply_of(send(simulator, "time")).fields["t"]
        assert int(second) > int(first)


class TestAdvertising:
    def test_events_arrive_on_the_nominal_interval(self, simulator):
        send(simulator, "scan start 5000")
        send(simulator, "adv start E4:1C:7B:02:9A:11")

        timestamps = []
        while len(timestamps) < 5:
            for line in simulator.poll().decode().splitlines():
                event = parse_line(line)
                if event is not None and getattr(event, "name", "") == "adv":
                    timestamps.append(event.timestamp_us)

        intervals = [
            timestamps[index + 1] - timestamps[index] for index in range(len(timestamps) - 1)
        ]
        # 100 ms nominal plus the rotating advertising delay.
        assert min(intervals) == 100_000
        assert max(intervals) == 110_000

    def test_a_sensor_that_misses_beacons(self, simulator):
        """SENS-0B2C3D skips one in five, which must show as a gap not a silence."""
        send(simulator, "scan start 20000")
        send(simulator, "adv start C9:3A:51:0F:22:04")

        timestamps = []
        for _ in range(200):
            for line in simulator.poll().decode().splitlines():
                event = parse_line(line)
                if event is not None and getattr(event, "name", "") == "adv":
                    timestamps.append(event.timestamp_us)
            if len(timestamps) >= 8:
                break

        intervals = [
            timestamps[index + 1] - timestamps[index] for index in range(len(timestamps) - 1)
        ]
        assert max(intervals) > 400_000        # a skipped beacon leaves a double gap

    def test_the_advertising_payload_carries_the_name(self, simulator):
        send(simulator, "scan start 5000")
        send(simulator, "adv start E4:1C:7B:02:9A:11")
        event = None
        while event is None:
            for line in simulator.poll().decode().splitlines():
                parsed = parse_line(line)
                if parsed is not None and getattr(parsed, "name", "") == "adv":
                    event = parsed
        payload = bytes.fromhex(event.get("data"))
        assert b"SENS-0A1B2C" in payload
        assert event.get("name") == "SENS-0A1B2C"

    def test_nothing_is_produced_when_not_scanning(self, simulator):
        assert simulator.poll() == b""

    def test_channels_rotate(self, simulator):
        send(simulator, "scan start 5000")
        send(simulator, "adv start E4:1C:7B:02:9A:11")
        channels = set()
        for _ in range(20):
            for line in simulator.poll().decode().splitlines():
                event = parse_line(line)
                if event is not None and getattr(event, "name", "") == "adv":
                    channels.add(event.integer("ch"))
        assert channels == {37, 38, 39}

    def test_the_stats_reconcile(self, simulator):
        send(simulator, "scan start 5000")
        send(simulator, "adv start E4:1C:7B:02:9A:11")
        for _ in range(10):
            simulator.poll()
        reply = reply_of(send(simulator, "adv stats"))
        assert reply.fields["received"] == reply.fields["reported"]

    def test_a_dropping_dongle_says_so(self):
        """The drop counter is the only way the host can know its stream was
        lossy rather than the sensor quiet."""
        simulator = SimulatedDongle(drop_every=2)
        send(simulator, "scan start 5000")
        send(simulator, "adv start E4:1C:7B:02:9A:11")
        for _ in range(10):
            simulator.poll()
        reply = reply_of(send(simulator, "adv stats"))
        assert int(reply.fields["dropped"]) > 0
        assert int(reply.fields["reported"]) < int(reply.fields["received"])


class TestScanAndSelect:
    def test_scanning_finds_sensors(self, simulator):
        """Long enough for the 1 s beacon to appear as well."""
        send(simulator, "scan start 5000")
        for _ in range(20):
            simulator.poll()
        lines = send(simulator, "list")
        assert reply_of(lines).fields["sensors"] == "3"

    def test_a_name_filter_is_applied(self, simulator):
        send(simulator, "scan start 5000 name=SENS-0B2C3D")
        for _ in range(20):
            simulator.poll()
        assert reply_of(send(simulator, "list")).fields["sensors"] == "1"

    def test_selecting_an_unknown_address_is_refused(self, simulator):
        reply = reply_of(send(simulator, "select AA:BB:CC:DD:EE:FF"))
        assert reply.ok is False and reply.error is DongleError.VALUE

    def test_selected_before_selecting(self, simulator):
        assert reply_of(send(simulator, "selected")).error is DongleError.NO_SENSOR


class TestLinkAndUart:
    def connect(self, simulator):
        send(simulator, "scan start 5000")
        for _ in range(10):
            simulator.poll()
        send(simulator, "select E4:1C:7B:02:9A:11")
        return send(simulator, "connect")

    def test_connecting_emits_the_ready_event(self, simulator):
        self.connect(simulator)
        events = [item for item in send(simulator, "time") if getattr(item, "name", "") == "conn"]
        assert any(event.get("state") == "ready" for event in events)

    def test_connecting_twice_is_refused(self, simulator):
        self.connect(simulator)
        assert reply_of(send(simulator, "connect")).error is DongleError.STATE

    def test_a_command_reports_both_timestamps(self, simulator):
        self.connect(simulator)
        reply = reply_of(send(simulator, "cmd " + b"version".hex()))
        assert int(reply.fields["dt_us"]) == 12_500
        assert int(reply.fields["t_rx"]) - int(reply.fields["t_tx"]) == 12_500
        assert bytes.fromhex(reply.fields["data"]) == b"1.4.2"

    def test_a_slow_command_takes_longer(self, simulator):
        """A sensor that measures something before answering."""
        self.connect(simulator)
        reply = reply_of(send(simulator, "cmd " + b"measure".hex()))
        assert int(reply.fields["dt_us"]) == 95_000

    def test_an_unknown_sensor_command_still_answers(self, simulator):
        self.connect(simulator)
        reply = reply_of(send(simulator, "cmd " + b"nonsense".hex()))
        assert b"unknown" in bytes.fromhex(reply.fields["data"])

    def test_uart_without_a_connection_is_refused(self, simulator):
        assert reply_of(send(simulator, "uart 0102")).error is DongleError.NOT_CONNECTED

    def test_malformed_hex_is_refused(self, simulator):
        self.connect(simulator)
        assert reply_of(send(simulator, "uart zzzz")).error is DongleError.VALUE

    def test_disconnect_emits_the_event(self, simulator):
        self.connect(simulator)
        send(simulator, "disconnect")
        events = [item for item in send(simulator, "time") if getattr(item, "name", "") == "disc"]
        assert events

    def test_the_radio_stops_advertising_reports_while_connected(self, simulator):
        """One radio: a connection means no scanning, as on the real part."""
        self.connect(simulator)
        simulator.poll()                        # drains the queued +conn events
        assert simulator.poll() == b""


class TestCustomPopulation:
    def test_a_bespoke_sensor(self):
        sensor = SimulatedSensor(
            address="11:22:33:44:55:66", name="FAST", interval_us=20_000,
            delay_pattern_us=(0,), responses={"ping": "pong"},
        )
        simulator = SimulatedDongle(sensors=(sensor,))
        send(simulator, "scan start 5000")
        send(simulator, "adv start 11:22:33:44:55:66")
        timestamps = []
        while len(timestamps) < 3:
            for line in simulator.poll().decode().splitlines():
                event = parse_line(line)
                if event is not None and getattr(event, "name", "") == "adv":
                    timestamps.append(event.timestamp_us)
        assert timestamps[1] - timestamps[0] == 20_000

    def test_the_default_population_is_stable(self):
        """The tests assert on these figures, so they are part of the contract."""
        assert [sensor.name for sensor in DEFAULT_SENSORS] == ["SENS-0A1B2C", "SENS-0B2C3D", ""]
        assert DEFAULT_SENSORS[0].interval_us == 100_000
        assert DEFAULT_SENSORS[1].miss_every == 5
        assert DEFAULT_SENSORS[2].connectable is False


class TestTheDefaultPopulationIsNotShared:
    """`DEFAULT_SENSORS` is a module-level tuple of dataclasses holding mutable
    dicts. Handing those objects to every simulator made one test's change to a
    sensor's replies visible to every simulator built afterwards - and the
    tests it broke were in other files, describing the sensor rather than the
    test that had altered it (D-40).

    Traces to: BLE-FR-080.
    """

    def test_the_default_population_is_not_shared_between_simulators(self):
        first, second = SimulatedDongle(), SimulatedDongle()
        first.sensors[0].responses["temp"] = "changed"
        assert second.sensors[0].responses["temp"] != "changed"

    def test_the_module_level_default_is_left_alone(self):
        simulator = SimulatedDongle()
        simulator.sensors[0].responses.clear()
        simulator.sensors.pop()
        assert DEFAULT_SENSORS[0].responses, "the shipped population still has replies"
        assert len(DEFAULT_SENSORS) == 3

    def test_a_population_given_explicitly_is_copied_too(self):
        given = SimulatedSensor(address="AA:BB:CC:DD:EE:FF", name="SENS-000001",
                                responses={"temp": "1.0"})
        simulator = SimulatedDongle(sensors=(given,))
        simulator.sensors[0].responses["temp"] = "2.0"
        assert given.responses["temp"] == "1.0"
