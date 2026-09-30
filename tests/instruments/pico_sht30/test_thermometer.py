"""The Pico 2 + SHT30-D thermometer driver.

Organised around the driver's two promises: it reports what the firmware *is*
(title, version, protocol), and it never reports a temperature that is not
true - a failed reading raises, and a reading whose value disagrees with its
raw word is refused.

Traces to: PICO-FR-040 .. PICO-FR-046, SWE4-UT-PICO.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import InstrumentError, ProtocolError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.pico_sht30 import (
    DEFAULT_ADDRESS,
    PROTOCOL_VERSION,
    TITLE,
    PicoSht30,
    SensorError,
    SimulatedPicoSht30,
    raw_to_celsius,
    raw_to_percent,
)
from benchtools.instruments.pico_sht30.thermometer import parse_fields


class _Scripted:  # pylint: disable=too-few-public-methods
    """A responder that answers every command with the same fixed line."""

    def __init__(self, ver: str, reply: str) -> None:
        self.ver = ver
        self.reply = reply

    def respond(self, message: bytes):
        text = message.decode().strip()
        return ((self.ver if text == "ver" else self.reply) + "\n").encode()


_VER = ("ok title=%s fw=1.0.0 built=2026-09-30T00:00:00Z proto=1.0 board=pico2 "
        "serial=E6614C311B7F2A21 sensor=SHT30-DIS addr=0x44 uptime_s=5" % TITLE)


def _scripted(reply: str, ver: str = _VER) -> PicoSht30:
    instrument = PicoSht30(MockTransport(responder=_Scripted(ver, reply)))
    instrument.initialise()
    return instrument


class TestIdentity:
    def test_title_and_version(self, thermometer):
        assert thermometer.title == TITLE
        assert thermometer.version == "1.0.0"

    def test_firmware_info(self, thermometer):
        info = thermometer.firmware_info()
        assert info.protocol == PROTOCOL_VERSION
        assert info.board == "pico2"
        assert info.sensor == "SHT30-DIS"
        assert info.address == DEFAULT_ADDRESS
        assert info.serial == SimulatedPicoSht30.DEFAULT_SERIAL
        assert info.build_date_is_utc

    def test_identity(self, thermometer):
        identity = thermometer.identify()
        assert identity.manufacturer == "Raspberry Pi"
        assert identity.model == "Pico 2/SHT30-DIS"
        assert identity.serial_number == SimulatedPicoSht30.DEFAULT_SERIAL
        assert identity.firmware.startswith("1.0.0 (built ")

    def test_a_different_version_is_reported_as_it_is(self):
        with PicoSht30(MockTransport(responder=SimulatedPicoSht30(version="1.2.3"))) as device:
            assert device.version == "1.2.3"

    def test_a_local_build_date_is_flagged(self):
        simulator = SimulatedPicoSht30()
        simulator.built = "local:Sep_30_2026T12:00:00"
        with PicoSht30(MockTransport(responder=simulator)) as device:
            assert not device.firmware_info().build_date_is_utc

    def test_an_incompatible_protocol_is_refused(self):
        ver = _VER.replace("proto=1.0", "proto=2.0")
        with pytest.raises(ProtocolError, match="protocol 2.0"):
            _scripted("ok", ver=ver)

    def test_a_ver_reply_without_a_title_is_refused(self):
        with pytest.raises(ProtocolError, match="title"):
            _scripted("ok", ver="ok fw=1.0.0 proto=1.0")

    def test_connecting_sends_no_scpi(self, simulator, thermometer):  # pylint: disable=unused-argument
        """*CLS would be answered with err 1 by this firmware."""
        assert all(not command.startswith("*") for command in simulator.command_log)

    def test_no_error_queue(self, thermometer):
        assert thermometer.read_event_queue() == []


class TestReading:
    def test_temperature(self, simulator, thermometer):
        simulator.temperature = 23.45
        assert thermometer.temperature() == pytest.approx(23.45, abs=0.003)

    def test_humidity(self, simulator, thermometer):
        simulator.humidity = 61.0
        assert thermometer.humidity() == pytest.approx(61.0, abs=0.002)

    def test_below_zero(self, simulator, thermometer):
        simulator.temperature = -10.25
        assert thermometer.temperature() == pytest.approx(-10.25, abs=0.003)

    def test_raw_words_travel_with_the_values(self, thermometer):
        reading = thermometer.read()
        assert reading.temperature == raw_to_celsius(reading.raw_temperature)
        assert reading.humidity == raw_to_percent(reading.raw_humidity)

    def test_as_dict(self, thermometer):
        payload = thermometer.read().as_dict()
        assert set(payload) == {"temperature_c", "humidity_pct", "raw_temperature",
                                "raw_humidity", "timestamp"}
        assert payload["raw_temperature"].startswith("0x")

    def test_every_reading_is_a_new_measurement(self, simulator, thermometer):
        thermometer.read()
        thermometer.read()
        assert simulator.measurements == 2


class TestFailedReadings:
    """A failed reading raises; it never returns the previous value."""

    def test_no_sensor(self, simulator, thermometer):
        simulator.sensor_present = False
        with pytest.raises(SensorError) as caught:
            thermometer.read()
        assert caught.value.code == 4
        assert caught.value.symbol == "PROTO_ERR_NO_SENSOR"

    def test_crc_failure(self, simulator, thermometer):
        thermometer.read()
        simulator.corrupt_next = True
        with pytest.raises(SensorError) as caught:
            thermometer.read()
        assert caught.value.code == 5

    def test_bus_timeout(self, simulator, thermometer):
        simulator.bus_timeout = True
        with pytest.raises(SensorError) as caught:
            thermometer.temperature()
        assert caught.value.code == 6

    def test_a_sensor_error_is_an_instrument_error(self, simulator, thermometer):
        simulator.sensor_present = False
        with pytest.raises(InstrumentError):
            thermometer.read()

    def test_identity_survives_a_missing_sensor(self):
        simulator = SimulatedPicoSht30()
        simulator.sensor_present = False
        with PicoSht30(MockTransport(responder=simulator)) as device:
            assert device.title == TITLE

    def test_a_value_that_disagrees_with_its_raw_word_is_refused(self):
        thermometer = _scripted("ok t=25.500 rh=40.000 raw_t=0x6666 raw_rh=0x6666")
        with pytest.raises(ProtocolError, match="temperature 25.500"):
            thermometer.read()

    def test_a_humidity_that_disagrees_is_refused(self):
        thermometer = _scripted("ok t=25.000 rh=41.000 raw_t=0x6666 raw_rh=0x6666")
        with pytest.raises(ProtocolError, match="humidity"):
            thermometer.read()

    def test_a_missing_field_is_refused(self):
        thermometer = _scripted("ok t=25.000 rh=40.000 raw_t=0x6666")
        with pytest.raises(ProtocolError, match="raw_rh"):
            thermometer.read()

    def test_a_malformed_number_is_refused(self):
        thermometer = _scripted("ok t=warm rh=40.000 raw_t=0x6666 raw_rh=0x6666")
        with pytest.raises(ProtocolError, match="malformed"):
            thermometer.read()

    def test_a_reply_that_is_neither_ok_nor_err(self):
        thermometer = _scripted("hello")
        with pytest.raises(ProtocolError, match="unexpected"):
            thermometer.read()

    def test_a_malformed_err_reply(self):
        thermometer = _scripted("err x broken")
        with pytest.raises(ProtocolError, match="malformed error"):
            thermometer.read()


class TestStatusAndControl:
    def test_status_after_power_up(self, thermometer):
        status = thermometer.status()
        assert status.raw == 0x0010
        assert status.flag("reset_detected")
        assert not status.flag("alert_pending")
        assert status.as_dict()["raw"] == "0x0010"

    def test_status_with_no_sensor(self, simulator, thermometer):
        simulator.sensor_present = False
        with pytest.raises(SensorError):
            thermometer.status()

    def test_soft_reset(self, simulator, thermometer):
        thermometer.soft_reset_sensor()
        assert simulator.command_log[-1] == "sreset"

    def test_reboot(self, simulator, thermometer):
        thermometer.reset()
        assert simulator.reboots == 1

    def test_bootloader(self, simulator, thermometer):
        thermometer.enter_bootloader()
        assert simulator.bootloader_requests == 1

    def test_help_lines_are_skipped(self, thermometer):
        assert thermometer.execute("help") == {}
        assert thermometer.title == TITLE


class TestResources:
    @pytest.mark.parametrize(
        "resource,expected",
        [("COM5", "serial://COM5"), ("/dev/ttyACM0", "serial:///dev/ttyACM0"),
         ("sim://", "sim://"), ("", "sim://"), ("sim", "sim"),
         ("serial://COM5", "serial://COM5")],
    )
    def test_resource_forms(self, resource, expected):
        assert PicoSht30._normalise_resource(resource) == expected

    def test_connect_through_the_factory(self):
        with PicoSht30.connect("sim://") as thermometer:
            assert thermometer.title == TITLE


def test_parse_fields():
    assert parse_fields("ok a=1 b=0x2 c=") == {"a": "1", "b": "0x2", "c": ""}
    assert not parse_fields("ok")
