"""The Pico 2 + SHT30-D thermometer driver.

Organised around the driver's two promises: it reports what the firmware *is*
(name, copyright, version, commit), and it never reports a temperature that is
not true - ``Error`` raises, and a value that is not degrees to two places is
refused.

Traces to: PICO-FR-040 .. PICO-FR-047, SWE4-UT-PICO.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import InstrumentError, ProtocolError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.pico_sht30 import (
    COPYRIGHT,
    NAME,
    NoReadingError,
    PicoSht30,
    RdRefusedError,
    SensorError,
    SimulatedPicoSht30,
)
from benchtools.instruments.pico_sht30.thermometer import parse_fields

_IDENTITY = {
    "rd name": "ACK rd name = %s" % NAME,
    "rd copyright": "ACK rd copyright = %s" % COPYRIGHT,
    "rd version": "ACK rd version = V1.00.0000",
    "rd sha": "ACK rd sha = 0c0ffee",
}


class _Scripted:  # pylint: disable=too-few-public-methods
    """Answers the identity reads normally and every other command with *reply*."""

    def __init__(self, reply: str, identity=None) -> None:
        self.reply = reply
        self.identity = dict(_IDENTITY, **(identity or {}))

    def respond(self, message: bytes):
        text = message.decode().strip()
        return (self.identity.get(text, self.reply) + "\n").encode()


def _scripted(reply: str, **identity) -> PicoSht30:
    instrument = PicoSht30(MockTransport(responder=_Scripted(reply, identity)))
    instrument.initialise()
    return instrument


class TestIdentity:
    def test_name_version_and_sha(self, thermometer):
        assert thermometer.name == NAME
        assert thermometer.version == "V1.00.0000"
        assert thermometer.sha == SimulatedPicoSht30.DEFAULT_SHA

    def test_firmware_info(self, thermometer):
        assert thermometer.firmware_info().as_dict() == {
            "name": NAME, "copyright": COPYRIGHT, "version": "V1.00.0000",
            "sha": SimulatedPicoSht30.DEFAULT_SHA,
        }

    def test_identity(self, thermometer):
        identity = thermometer.identify()
        assert identity.manufacturer == "Raspberry Pi"
        assert identity.model == "Pico 2/SHT30"
        assert identity.firmware == "V1.00.0000 (0c0ffee)"

    def test_a_different_version_is_reported_as_it_is(self):
        simulator = SimulatedPicoSht30(version="V1.01.0000")
        with PicoSht30(MockTransport(responder=simulator)) as device:
            assert device.version == "V1.01.0000"

    def test_another_device_is_refused(self):
        with pytest.raises(ProtocolError, match="name 'Something else'"):
            _scripted("ok", **{"rd name": "ACK rd name = Something else"})

    def test_a_reply_for_another_option_is_refused(self):
        with pytest.raises(ProtocolError, match="is for 'version'"):
            _scripted("ok", **{"rd sha": "ACK rd version = V1.00.0000"})

    def test_connecting_sends_only_rd(self, simulator, thermometer):  # pylint: disable=unused-argument
        """*CLS would be answered with err 1 by this firmware."""
        assert simulator.command_log == ["rd name", "rd copyright", "rd version", "rd sha"]

    def test_no_error_queue(self, thermometer):
        assert thermometer.read_event_queue() == []


class TestRd:
    def test_other_options(self, thermometer):
        assert thermometer.rd("copyright") == COPYRIGHT
        assert thermometer.rd("temperature") == "22.50"

    def test_nak(self, thermometer):
        with pytest.raises(RdRefusedError, match="NAK rd colour = Error"):
            thermometer.rd("colour")

    def test_err_reply(self):
        thermometer = _scripted("err 2 wrong number of arguments")
        with pytest.raises(SensorError) as caught:
            thermometer.rd("temperature")
        assert caught.value.code == 2

    def test_a_reply_that_is_neither_ack_nor_nak(self):
        thermometer = _scripted("hello")
        with pytest.raises(ProtocolError, match="unexpected"):
            thermometer.rd("temperature")


class TestReading:
    def test_temperature(self, simulator, thermometer):
        simulator.temperature = 23.45
        assert thermometer.temperature() == pytest.approx(23.45, abs=0.006)

    def test_below_zero(self, simulator, thermometer):
        simulator.temperature = -10.25
        assert thermometer.temperature() == pytest.approx(-10.25, abs=0.006)

    def test_two_decimal_places(self, thermometer):
        reading = thermometer.read()
        assert reading.text == "22.50"
        assert set(reading.as_dict()) == {"temperature_c", "text", "timestamp"}

    def test_every_reading_is_a_new_measurement(self, simulator, thermometer):
        thermometer.read()
        thermometer.read()
        assert simulator.measurements == 2

    @pytest.mark.parametrize("value", ["22.5", "22.500", "warm", "1e3", "-"])
    def test_a_value_not_to_two_places_is_refused(self, value):
        thermometer = _scripted("ACK rd temperature = %s" % value)
        with pytest.raises(ProtocolError, match="two places"):
            thermometer.read()


class TestFailedReadings:
    """A failed reading raises; it never returns the previous value."""

    @pytest.mark.parametrize(
        "fault,value",
        [("sensor_present", False), ("corrupt_next", True), ("bus_timeout", True)],
    )
    def test_error(self, simulator, thermometer, fault, value):
        setattr(simulator, fault, value)
        with pytest.raises(NoReadingError):
            thermometer.read()

    def test_a_crc_failure_affects_one_reading(self, simulator, thermometer):
        simulator.corrupt_next = True
        with pytest.raises(NoReadingError):
            thermometer.read()
        assert thermometer.temperature() == pytest.approx(22.5, abs=0.006)

    def test_no_reading_is_an_instrument_error(self, simulator, thermometer):
        simulator.sensor_present = False
        with pytest.raises(InstrumentError):
            thermometer.temperature()

    def test_identity_survives_a_missing_sensor(self):
        simulator = SimulatedPicoSht30()
        simulator.sensor_present = False
        with PicoSht30(MockTransport(responder=simulator)) as device:
            assert device.name == NAME


class TestStatusAndControl:
    def test_status_after_power_up(self, thermometer):
        status = thermometer.status()
        assert status.raw == 0x0010
        assert status.flag("reset_detected")
        assert not status.flag("alert_pending")
        assert status.as_dict()["raw"] == "0x0010"

    def test_status_with_no_sensor(self, simulator, thermometer):
        simulator.sensor_present = False
        with pytest.raises(SensorError) as caught:
            thermometer.status()
        assert caught.value.symbol == "PROTO_ERR_NO_SENSOR"

    def test_soft_reset(self, simulator, thermometer):
        thermometer.soft_reset_sensor()
        assert simulator.command_log[-1] == "sreset"

    def test_reboot_is_ecureset(self, simulator, thermometer):
        thermometer.reset()
        assert simulator.command_log[-1] == "ecureset"
        assert simulator.reboots == 1

    def test_bootloader(self, simulator, thermometer):
        thermometer.enter_bootloader()
        assert simulator.bootloader_requests == 1

    def test_help_lines_are_skipped(self, thermometer):
        assert thermometer.execute("help") == {}
        assert thermometer.rd("name") == NAME

    def test_a_reply_that_is_neither_ok_nor_err(self):
        with pytest.raises(ProtocolError, match="unexpected"):
            _scripted("hello").status()

    def test_a_malformed_err_reply(self):
        with pytest.raises(ProtocolError, match="malformed error"):
            _scripted("err x broken").status()

    def test_a_status_reply_without_its_field(self):
        with pytest.raises(ProtocolError, match="no 'status' field"):
            _scripted("ok").status()


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
            assert thermometer.name == NAME


def test_parse_fields():
    assert parse_fields("ok a=1 b=0x2 c=") == {"a": "1", "b": "0x2", "c": ""}
    assert not parse_fields("ok")
