"""The dongle driver, against the simulated dongle and its sensors.

Traces to: BLE-FR-002 .. BLE-FR-062, SWE4-UT-BLE.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import (
    ConfigurationError,
    InstrumentError,
    MeasurementError,
)
from benchtools.core.instrument import Instrument
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import (
    AddressType,
    DongleCommandError,
    LatencySource,
    NordicDongle,
    Sensor,
    SimulatedDongle,
    SimulatedSensor,
)

from .conftest import (
    CONNECTION_INTERVAL_US,
    FAST_LATENCY_US,
    FLAKY_ADDRESS,
    FLAKY_INTERVAL_S,
    FLAKY_NAME,
    MEAN_INTERVAL_S,
    NOMINAL_INTERVAL_S,
    SENSOR_ADDRESS,
    SENSOR_NAME,
    SLOW_LATENCY_US,
)


class TestConnection:
    def test_identity(self, dongle):
        identity = dongle.identify()
        assert identity.manufacturer == "Nordic"
        assert identity.model == "PCA10059"
        # The firmware field carries the build on the dongle, not the protocol
        # it speaks: the build is what decides what a measurement means.
        assert identity.firmware.startswith(SimulatedDongle.DEFAULT_FIRMWARE_VERSION)
        assert SimulatedDongle.DEFAULT_FIRMWARE_BUILT in identity.firmware
        assert dongle.protocol_version == "1.1"

    def test_it_is_an_instrument_but_not_scpi(self, dongle):
        """The runner drives it through the same contract as every other
        instrument, without it pretending to speak SCPI."""
        from benchtools.core.scpi import ScpiInstrument

        assert isinstance(dongle, Instrument)
        assert not isinstance(dongle, ScpiInstrument)

    def test_a_bare_port_name_is_a_serial_port(self):
        """COM5 must not be parsed as a network host, which is the sensible
        default everywhere else in this package and wrong here."""
        assert NordicDongle._normalise_resource("COM5") == "serial://COM5"
        assert NordicDongle._normalise_resource("/dev/ttyACM0") == "serial:///dev/ttyACM0"

    @pytest.mark.parametrize(
        "resource,expected",
        [("sim://", "sim://"), ("sim", "sim"), ("", "sim://"),
         ("serial://COM5", "serial://COM5"),
         ("serial://socket://bench:4001", "serial://socket://bench:4001")],
    )
    def test_resource_forms(self, resource, expected):
        assert NordicDongle._normalise_resource(resource) == expected

    def test_connect_through_the_factory(self):
        with NordicDongle.connect("sim://") as instrument:
            assert instrument.identify().model == "PCA10059"

    def test_a_firmware_speaking_another_protocol_is_reported(self, simulator):
        """Better here than as a confusing failure three commands later.

        Only the major version is fatal: a minor difference means one side has
        commands the other lacks, which fails per command and is recoverable.
        """
        simulator.protocol = "9.9"
        instrument = NordicDongle(MockTransport(responder=simulator))
        with pytest.raises(InstrumentError, match="9.9"):
            instrument.initialise()

    def test_closing_is_idempotent(self, dongle):
        dongle.close()
        dongle.close()

    def test_the_dongle_clock_can_be_read(self, dongle):
        assert dongle.dongle_time_us() > 0


class TestScanning:
    def test_scan_finds_the_sensors(self, dongle):
        sensors = dongle.scan(1.0)
        assert [sensor.name for sensor in sensors[:2]] == [SENSOR_NAME, FLAKY_NAME]
        assert sensors[0].address == SENSOR_ADDRESS
        assert sensors[0].rssi == -62
        assert sensors[0].address_type is AddressType.RANDOM_STATIC

    def test_a_sensor_with_no_name_is_still_listed(self, dongle):
        """"No name" is a fact about the device, not a reason to hide it."""
        sensors = dongle.scan(1.0)
        assert any(sensor.name == "" for sensor in sensors)

    def test_filtering_by_name(self, dongle):
        sensors = dongle.scan(1.0, name=FLAKY_NAME)
        assert [sensor.name for sensor in sensors] == [FLAKY_NAME]

    def test_filtering_by_signal_strength(self, dongle):
        sensors = dongle.scan(1.0, min_rssi=-80)
        assert all(sensor.rssi >= -80 for sensor in sensors)
        assert len(sensors) == 2

    def test_filtering_by_address(self, dongle):
        sensors = dongle.scan(1.0, address=FLAKY_ADDRESS)
        assert [sensor.address for sensor in sensors] == [FLAKY_ADDRESS]

    def test_a_name_filter_with_a_space_is_refused(self, dongle):
        """The link is space separated, so this could not be sent correctly."""
        with pytest.raises(ValueError, match="cannot contain a space"):
            dongle.scan(1.0, name="SENS 01")

    def test_a_malformed_address_filter_is_refused(self, dongle):
        with pytest.raises(InstrumentError, match="six colon-separated octets"):
            dongle.scan(1.0, address="not-an-address")

    def test_scan_duration_must_be_positive(self, dongle):
        with pytest.raises(ConfigurationError, match="must be positive"):
            dongle.scan(0.0)

    def test_sensors_are_remembered(self, dongle):
        dongle.scan(1.0)
        assert len(dongle.sensors) == 3

    def test_find_by_name_or_address(self, scanned):
        assert scanned.find_sensor(SENSOR_NAME).address == SENSOR_ADDRESS
        assert scanned.find_sensor(SENSOR_ADDRESS.lower()).name == SENSOR_NAME
        assert scanned.find_sensor("nothing here") is None


class TestStrongest:
    """Choosing by signal strength rather than by name.

    Worth its own class because "strongest" is a statement about a link at a
    moment, not about which board is nearest, and because the empty case has
    to fail here rather than three steps later at the point of connecting.
    """

    def test_the_highest_rssi_wins(self, dongle):
        dongle.scan(1.0)
        found = dongle.sensors
        assert len(found) > 1, "the fixture needs more than one sensor to choose between"
        assert dongle.strongest().rssi == max(sensor.rssi for sensor in found)

    def test_a_supplied_list_is_used_instead_of_the_last_scan(self, dongle):
        near = Sensor(address="AA:BB:CC:DD:EE:01", name="NEAR", rssi=-40, index=1)
        far = Sensor(address="AA:BB:CC:DD:EE:02", name="FAR", rssi=-90, index=0)
        assert dongle.strongest([far, near]).name == "NEAR"

    def test_a_tie_is_broken_by_scan_order(self, dongle):
        # Repeating a scan over two boards at equal strength must select the
        # same one, not alternate between them.
        first = Sensor(address="AA:BB:CC:DD:EE:01", name="FIRST", rssi=-55, index=0)
        second = Sensor(address="AA:BB:CC:DD:EE:02", name="SECOND", rssi=-55, index=1)
        assert dongle.strongest([first, second]).name == "FIRST"
        assert dongle.strongest([second, first]).name == "FIRST"

    def test_an_empty_scan_is_refused_where_it_happened(self, dongle):
        # Selecting from nothing would otherwise surface at connect time and
        # read as a link problem rather than as an empty room.
        with pytest.raises(InstrumentError) as excinfo:
            dongle.strongest([])
        message = str(excinfo.value)
        assert "found nothing" in message
        assert "advertising" in message


class TestSelection:
    def test_select_by_name(self, dongle):
        dongle.scan(1.0)
        sensor = dongle.select(SENSOR_NAME)
        assert sensor.address == SENSOR_ADDRESS
        assert dongle.selected.name == SENSOR_NAME

    def test_select_by_index(self, dongle):
        dongle.scan(1.0)
        assert dongle.select(0).address == SENSOR_ADDRESS

    def test_select_by_address(self, dongle):
        dongle.scan(1.0)
        assert dongle.select(FLAKY_ADDRESS).name == FLAKY_NAME

    def test_select_a_sensor_object(self, dongle):
        sensors = dongle.scan(1.0)
        assert dongle.select(sensors[1]).address == FLAKY_ADDRESS

    def test_the_address_type_travels_with_the_address(self, scanned):
        """Connecting with the wrong type simply never finds the device."""
        assert scanned.selected.qualified_address.endswith("/1")

    def test_selecting_an_unknown_address_is_allowed(self, dongle):
        """The host may know an address from an earlier run; requiring a scan
        first would make every suite start with one."""
        dongle.scan(1.0)
        assert dongle.select(SENSOR_ADDRESS).address == SENSOR_ADDRESS

    def test_selecting_an_unknown_name_is_refused(self, dongle):
        dongle.scan(1.0)
        with pytest.raises(InstrumentError):
            dongle.select("NOT-A-SENSOR")

    def test_commands_need_a_selection(self, dongle):
        with pytest.raises(ConfigurationError, match="no sensor is selected"):
            dongle.open_link()


class TestLink:
    def test_connect_and_disconnect(self, scanned):
        scanned.open_link()
        assert scanned.is_linked is True
        scanned.close_link()
        assert scanned.is_linked is False

    def test_the_connection_interval_is_recorded(self, linked):
        """It is the floor under every latency measured on this link."""
        assert linked.connection_interval_us == CONNECTION_INTERVAL_US

    def test_disconnecting_twice_is_harmless(self, linked):
        linked.close_link()
        linked.close_link()

    def test_an_unconnectable_sensor_is_reported(self, dongle):
        dongle.scan(1.0)
        dongle.select(2)                        # the beacon-only device
        with pytest.raises(DongleCommandError, match="refused"):
            dongle.open_link()

    def test_writing_without_a_link_is_reported(self, scanned):
        with pytest.raises(DongleCommandError, match="not connected"):
            scanned.write("version")


class TestUart:
    def test_a_command_and_its_reply(self, linked):
        sample = linked.command("version")
        assert sample.text == "1.4.2"
        assert sample.dongle_us == FAST_LATENCY_US

    def test_both_clocks_are_recorded(self, linked):
        """The dongle's figure is the measurement; the host's is the check."""
        sample = linked.command("temp")
        assert sample.dongle_us == FAST_LATENCY_US
        assert sample.host_s > 0.0
        assert sample.transmitted_us < sample.received_us

    def test_an_unknown_command_still_answers(self, linked):
        assert "unknown" in linked.command("nonsense").text

    def test_a_write_reports_what_it_sent(self, linked):
        assert linked.write("ping") == 4

    def test_binary_payloads(self, linked):
        assert linked.write(b"\x00\x01\x02") == 3

    def test_an_over_long_payload_is_refused_before_sending(self, linked):
        with pytest.raises(ConfigurationError, match="the firmware accepts at most"):
            linked.write("x" * 200)


class TestResponseTiming:
    def test_a_measurable_latency(self, linked):
        timing = linked.measure_response_time("measure", repeat=5)
        assert timing.count == 5
        assert timing.microseconds == pytest.approx(SLOW_LATENCY_US)
        assert timing.is_trustworthy is True

    def test_a_latency_inside_the_connection_interval_is_flagged(self, linked):
        """12.5 ms on a 30 ms link is where the write landed, not firmware."""
        timing = linked.measure_response_time("version", repeat=3)
        assert timing.microseconds == pytest.approx(FAST_LATENCY_US)
        assert timing.is_trustworthy is False

    def test_the_host_clock_can_be_asked_for(self, linked):
        timing = linked.measure_response_time("measure", repeat=2, source="HOST")
        assert timing.source is LatencySource.HOST
        assert timing.resolution_s == pytest.approx(1e-3)

    def test_repeat_must_be_positive(self, linked):
        with pytest.raises(ConfigurationError, match="repeat must be at least 1"):
            linked.measure_response_time("version", repeat=0)

    def test_the_replies_are_kept(self, linked):
        assert linked.measure_response_time("id", repeat=2).responses == ["SENS-0A1B2C", "SENS-0A1B2C"]


class TestAdvertisingProfile:
    def test_the_nominal_interval_is_recovered(self, scanned):
        """The bounds are exact; the mean depends on where in the simulated
        delay rotation the capture happened to start, as it would on a sensor
        whose advDelay is genuinely random."""
        profile = scanned.measure_advertising_profile(2.0, expected_interval=NOMINAL_INTERVAL_S)
        assert profile.minimum_interval_s == NOMINAL_INTERVAL_S
        assert profile.maximum_interval_s == pytest.approx(NOMINAL_INTERVAL_S + 0.010)
        assert profile.spread_s == pytest.approx(0.010)
        assert profile.mean_interval_s == pytest.approx(MEAN_INTERVAL_S, abs=0.002)
        assert profile.count >= 19

    def test_the_capture_covers_the_window_asked_for(self, scanned):
        profile = scanned.measure_advertising_profile(2.0, expected_interval=0.1)
        assert profile.duration_s >= 2.0

    def test_a_healthy_sensor_misses_nothing(self, scanned):
        profile = scanned.measure_advertising_profile(2.0, expected_interval=0.1)
        assert profile.missed_events == 0
        assert profile.duty_cycle == pytest.approx(1.0)
        assert profile.is_complete is True

    def test_a_sensor_that_skips_beacons_is_caught(self, dongle):
        dongle.scan(1.0)
        dongle.select(FLAKY_NAME)
        profile = dongle.measure_advertising_profile(3.0, expected_interval=FLAKY_INTERVAL_S)
        assert profile.missed_events >= 1
        assert profile.duty_cycle < 1.0

    def test_the_events_carry_what_was_advertised(self, scanned):
        profile = scanned.measure_advertising_profile(1.0, expected_interval=0.1)
        event = profile.advertising_events[0]
        assert event.address == SENSOR_ADDRESS
        assert event.rssi == -62
        assert event.channel in (37, 38, 39)
        assert event.payload.startswith(b"\x02\x01\x06")
        assert event.host_time is not None

    def test_profiling_a_named_address(self, scanned):
        profile = scanned.measure_advertising_profile(
            1.0, address=FLAKY_ADDRESS, expected_interval=FLAKY_INTERVAL_S
        )
        assert profile.address == FLAKY_ADDRESS

    def test_a_lossy_link_is_declared_rather_than_averaged(self, dongle):
        """A dongle that dropped lines must not look like a sensor that
        skipped beacons."""
        dongle.session.transport.responder.drop_every = 3
        dongle.scan(1.0)
        dongle.select(SENSOR_NAME)
        profile = dongle.measure_advertising_profile(2.0, expected_interval=0.1)
        assert profile.is_complete is False
        assert profile.dongle_dropped > 0

    def test_duration_must_be_positive(self, scanned):
        with pytest.raises(ConfigurationError, match="must be positive"):
            scanned.measure_advertising_profile(0.0)

    def test_profiling_needs_a_sensor(self, dongle):
        with pytest.raises(ConfigurationError, match="no sensor is selected"):
            dongle.measure_advertising_profile(1.0)

    def test_a_silent_sensor_gives_no_statistics_rather_than_zero(self, dongle):
        """Nothing heard is the absence of a measurement, not a rate of zero."""
        quiet = SimulatedSensor(address="AA:BB:CC:DD:EE:FF", name="QUIET",
                                interval_us=10_000_000)
        instrument = NordicDongle(MockTransport(responder=SimulatedDongle(sensors=(quiet,))))
        instrument.initialise()
        instrument.scan(11.0)                   # long enough to hear it once
        instrument.select("QUIET")
        profile = instrument.measure_advertising_profile(0.2, expected_interval=0.1)
        if profile.count < 2:
            with pytest.raises(MeasurementError):
                _ = profile.mean_interval_s
        instrument.close()


class TestLogging:
    def test_the_session_can_be_logged_to_a_file(self, scanned, tmp_path):
        path = tmp_path / "ble.log"
        scanned.start_log(str(path))
        scanned.measure_advertising_profile(1.0, expected_interval=0.1)
        scanned.stop_log()

        text = path.read_text()
        assert "> adv start" in text
        assert "+adv t=" in text
        assert text.count("\n") > 10

    def test_a_note_lands_in_the_log(self, dongle, tmp_path):
        path = tmp_path / "ble.log"
        dongle.start_log(str(path))
        dongle.log_note("FW-REQ-030 advertising profile")
        assert "FW-REQ-030" in path.read_text()

    def test_the_log_path_is_reported(self, dongle, tmp_path):
        path = str(tmp_path / "ble.log")
        dongle.start_log(path)
        assert dongle.log_path == path

    def test_connect_can_start_the_log(self, tmp_path):
        """So that the connection dialogue is in the log as well."""
        path = str(tmp_path / "ble.log")
        with NordicDongle.connect("sim://", log_path=path) as instrument:
            instrument.identify()
        assert "> ver" in open(path).read()


class TestMiscellany:
    def test_reset_clears_local_state(self, scanned):
        scanned.reset()
        assert scanned.selected is None
        assert scanned.sensors == []

    def test_the_event_backlog_can_be_read(self, scanned):
        scanned.session.execute("scan", "start", 500)
        scanned.session.collect(0.1)
        scanned.read_event_queue()              # must not raise

    def test_there_is_no_error_queue_to_poll(self, dongle):
        """Every failure arrives in the reply to the command that caused it."""
        assert dongle.read_event_queue() == []

    def test_a_sensor_renders_readably(self):
        sensor = Sensor(address=SENSOR_ADDRESS, name=SENSOR_NAME, rssi=-62, index=0)
        assert "SENS-0A1B2C" in str(sensor)
        assert sensor.as_dict()["rssi"] == -62
