"""The PPK2 driver against the simulated kit.

Traces to: PPK-FR-001, PPK-FR-002, PPK-FR-005 .. PPK-FR-010, SWE4-UT-PPK.
"""

from __future__ import annotations

import logging
import types

import pytest

from benchtools.core.errors import ConfigurationError, ConnectionFailedError, InstrumentError
from benchtools.instruments.ppk2 import Ppk2, SimulatedPpk2
from benchtools.instruments.ppk2 import ppk2 as module


@pytest.fixture(name="kit")
def fixture_kit():
    kit = Ppk2.connect("sim://", voltage_limit=3.3)
    yield kit
    kit.close()


def sim(kit) -> SimulatedPpk2:
    """The simulated kit behind *kit*."""
    return kit._transport.simulator  # pylint: disable=protected-access


class TestConnect:
    def test_identity_and_event_name(self, kit):
        identity = kit.identify()
        assert identity.manufacturer == "Nordic Semiconductor"
        assert identity.model == "Power Profiler Kit II"
        assert identity.firmware == "HW 1"
        assert kit.event_source == "PPK"

    def test_connecting_reads_the_kit_and_changes_nothing(self, kit):
        assert [command[0] for command in sim(kit).received] == [0x07, 0x19]
        assert kit.mode == "source" and kit.volts == 3.3
        assert kit.powered is None
        assert kit.metadata["hw"] == 1

    def test_info(self, kit):
        info = kit.info()
        assert info["mode"] == "source" and info["voltage_limit"] == 3.3
        assert info["sample_rate"] == 100000

    def test_a_voltage_limit_outside_the_kit_s_range_is_refused(self):
        with pytest.raises(ConfigurationError, match="voltage_limit"):
            Ppk2.connect("sim://", voltage_limit=6)

    def test_a_port_still_off_usb_is_retried(self, monkeypatch):
        kit = Ppk2.connect("sim://", initialise=False)
        real_open, tries = kit._transport.open, []  # pylint: disable=protected-access

        def flaky_open():
            tries.append(1)
            if len(tries) < 3:
                raise ConnectionFailedError("cannot open COM5")
            return real_open()
        monkeypatch.setattr(kit._transport, "open", flaky_open)  # pylint: disable=protected-access
        kit.initialise()
        assert kit.is_open and len(tries) == 3
        kit.close()

    def test_a_port_that_never_comes_back_is_an_error(self, monkeypatch):
        monkeypatch.setattr(module, "REENUMERATE_WAIT", 0.2)
        kit = Ppk2.connect("sim://", initialise=False)

        def dead_open():
            raise ConnectionFailedError("cannot open COM5")
        monkeypatch.setattr(kit._transport, "open", dead_open)  # pylint: disable=protected-access
        with pytest.raises(ConnectionFailedError):
            kit.initialise()

    def test_metadata_is_asked_for_once(self, kit):
        assert [command for command in sim(kit).received if command == b""] == [b""]
        kit.set_voltage(3.0)
        assert kit.metadata["vdd"] == 3300 and kit.volts == 3.0

    def test_metadata_that_never_ends_is_an_error(self, monkeypatch):
        monkeypatch.setattr(module, "METADATA_TIMEOUT", 0.3)
        monkeypatch.setattr(SimulatedPpk2, "metadata", lambda self: "VDD: 3300\n")
        with pytest.raises(InstrumentError, match="did not finish its metadata"):
            Ppk2.connect("sim://")


class TestResources:
    KITS = [types.SimpleNamespace(device="COM5", vid=0x1915, pid=0xC00A,
                                  serial_number="D527E1DA8DBA", description="PPK2"),
            types.SimpleNamespace(device="COM10", vid=0x1915, pid=0x521A,
                                  serial_number="D7FA0F34C85A", description="dongle")]

    @pytest.fixture(autouse=True)
    def _ports(self, monkeypatch):
        pytest.importorskip("serial")
        from serial.tools import list_ports  # pylint: disable=import-outside-toplevel
        self.kits = list(self.KITS)
        monkeypatch.setattr(list_ports, "comports", lambda: self.kits)

    def test_only_ppk2s_are_listed(self):
        assert module.find_ppk2_ports() == [
            {"port": "COM5", "serial_number": "D527E1DA8DBA", "description": "PPK2"}]

    @pytest.mark.parametrize("resource", ["ppk2://", "ppk2://D527E1DA8DBA",
                                          "ppk2://d527e1da8dba"])
    def test_a_kit_is_found_by_serial_number(self, resource):
        assert module._resolve_port(resource) == "COM5"  # pylint: disable=protected-access

    def test_a_missing_kit(self):
        with pytest.raises(ConnectionFailedError, match="serial number 0000"):
            module._resolve_port("ppk2://0000", wait=0)  # pylint: disable=protected-access

    def test_a_kit_back_on_usb_within_the_wait_is_found(self, monkeypatch):
        present = list(self.kits)
        self.kits.clear()
        calls = []

        def comports():
            calls.append(1)
            return present if len(calls) > 2 else []
        from serial.tools import list_ports  # pylint: disable=import-outside-toplevel
        monkeypatch.setattr(list_ports, "comports", comports)
        assert module._resolve_port("ppk2://", wait=2.0) == "COM5"  # pylint: disable=protected-access
        assert len(calls) == 3

    def test_two_kits_need_a_serial_number(self):
        self.kits.append(types.SimpleNamespace(device="COM7", vid=0x1915, pid=0xC00A,
                                               serial_number="AB", description="PPK2"))
        with pytest.raises(ConfigurationError, match="2 PPK2s"):
            module._resolve_port("ppk2://")  # pylint: disable=protected-access


class TestSettings:
    def test_mode_switches_the_dut_power_off_first(self, kit):
        sim(kit).received.clear()
        assert kit.set_mode("ammeter") == "ammeter"
        assert sim(kit).received == [b"\x0c\x00", b"\x11\x01"]
        assert kit.mode == "ammeter" and kit.powered is False
        assert sim(kit).mode == 1

    def test_an_unknown_mode_is_refused(self, kit):
        with pytest.raises(ConfigurationError, match="ammeter or source"):
            kit.set_mode("smu")

    def test_voltage(self, kit):
        assert kit.set_voltage(3.0) == 3.0
        assert sim(kit).vdd_mv == 3000

    @pytest.mark.parametrize("volts, message", [(3.4, "voltage limit"), (0.5, "0.8 V")])
    def test_a_voltage_above_the_limit_or_outside_the_range_is_refused(
            self, kit, volts, message):
        sim(kit).received.clear()
        with pytest.raises(ConfigurationError, match=message):
            kit.set_voltage(volts)
        assert not sim(kit).received

    def test_power(self, kit):
        assert kit.power_on() is True and sim(kit).running
        assert kit.power_off() is False and not sim(kit).running

    def test_a_source_kit_above_the_limit_is_not_switched_on(self):
        with Ppk2.connect("sim://", voltage_limit=3.0) as kit:
            # The simulated kit starts at 3.3 V, as a kit left at 4 V would.
            with pytest.raises(ConfigurationError, match="set_voltage first"):
                kit.power_on()
            assert not sim(kit).running
            kit.set_mode("ammeter")
            assert kit.power_on() is True

    def test_settings_are_logged(self, kit, caplog):
        with caplog.at_level(logging.INFO):
            kit.set_voltage(3.0)
            kit.power_on()
        kinds = [getattr(record, "event_kind", None) for record in caplog.records]
        assert "ppk_voltage" in kinds and "ppk_power" in kinds


class TestMeasure:
    def test_nothing_drawn_with_the_power_off(self, kit):
        result = kit.measure(0.1)
        assert result.samples == 10000
        assert result.average == pytest.approx(0.0, abs=1e-7)

    def test_the_simulated_device_s_profile(self, kit):
        kit.set_voltage(3.0)
        kit.power_on()
        result = kit.measure(1.0, threshold=1e-3)
        assert result.samples == 100000 and result.lost == 0
        assert result.duration == pytest.approx(1.0)
        assert result.average == pytest.approx(5e-3 * 0.05 + 20e-6 * 0.95, rel=0.02)
        assert result.peak == pytest.approx(5e-3, rel=0.01)
        assert result.pulses.count in (9, 10)
        assert result.pulses.mean_width == pytest.approx(5e-3, abs=50e-6)
        assert result.pulses.mean_charge == pytest.approx(25e-6, rel=0.02)
        assert result.pulses.mean_interval == pytest.approx(0.1, rel=1e-3)
        assert result.mode == "source" and result.volts == 3.0

    def test_pulses_by_logic_input(self, kit):
        kit.power_on()
        result = kit.measure(0.5, line=0)
        assert result.pulses.source == "D0"
        assert result.pulses.count in (4, 5)

    def test_sampling_stops_after(self, kit):
        kit.measure(0.05)
        assert not sim(kit).sampling
        assert [command[0] for command in sim(kit).received[-2:]] == [0x06, 0x07]

    def test_lost_samples_are_reported(self, kit):
        sim(kit).lose_samples = 7
        assert kit.measure(0.05).lost == 7

    def test_average_current(self, kit):
        kit.power_on()
        assert kit.average_current(0.2) == pytest.approx(269e-6, rel=0.03)

    @pytest.mark.parametrize("duration", [0, -1, 121])
    def test_a_duration_out_of_range_is_refused(self, kit, duration):
        with pytest.raises(ConfigurationError, match="duration"):
            kit.measure(duration)

    def test_threshold_and_line_together_are_refused(self, kit):
        with pytest.raises(ConfigurationError, match="not both"):
            kit.measure(0.1, threshold=1e-3, line=0)

    def test_a_kit_that_stops_sending(self, kit, monkeypatch):
        monkeypatch.setattr(SimulatedPpk2, "_command",
                            lambda self, command: None)
        with pytest.raises(InstrumentError, match="stopped sending after 0 of"):
            kit.measure(0.1)

    def test_a_measurement_is_logged(self, kit, caplog):
        with caplog.at_level(logging.DEBUG):
            kit.measure(0.05)
        kinds = [getattr(record, "event_kind", None) for record in caplog.records]
        assert "ppk_measurement" in kinds and "reading" in kinds

    def test_closing_stops_sampling(self):
        kit = Ppk2.connect("sim://")
        simulated = sim(kit)
        simulated.sampling = True
        kit.close()
        assert not simulated.sampling and not kit.is_open
