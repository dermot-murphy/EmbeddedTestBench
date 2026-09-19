"""Bench configuration and live instrument resolution.

Traces to: RUN-FR-001 .. RUN-FR-005, SWE4-UT-BENCH.
"""

from __future__ import annotations

import json

import pytest

from benchtools.core.errors import BenchConfigError, InstrumentError
from benchtools.core.scpi import ScpiInstrument
from benchtools.core.simulator import SimulatedInstrument
from benchtools.runner.bench import (
    Bench,
    BenchConfig,
    InstrumentConfig,
    load_bench,
    register_driver,
    registered_drivers,
)


class TestInstrumentConfig:
    def test_mapping_form(self):
        config = InstrumentConfig.from_mapping(
            "scope", {"driver": "tek3014b", "resource": "1.2.3.4", "timeout": 15}
        )
        assert (config.driver, config.resource, config.timeout) == ("tek3014b", "1.2.3.4", 15.0)

    def test_shorthand_form(self):
        config = InstrumentConfig.from_mapping("psu", "generic@sim://")
        assert (config.driver, config.resource) == ("generic", "sim://")

    def test_resource_defaults_to_the_simulator(self):
        assert InstrumentConfig.from_mapping("s", {"driver": "generic"}).resource == "sim://"

    def test_driver_names_are_case_insensitive(self):
        assert InstrumentConfig.from_mapping("s", {"driver": "TEK3014B"}).driver == "tek3014b"

    def test_unknown_driver_lists_the_registered_ones(self):
        with pytest.raises(BenchConfigError, match="registered drivers are"):
            InstrumentConfig.from_mapping("s", {"driver": "flux-capacitor"})

    def test_missing_driver_is_reported(self):
        with pytest.raises(BenchConfigError, match="has no driver"):
            InstrumentConfig.from_mapping("s", {"resource": "sim://"})

    def test_bad_shorthand_is_reported(self):
        with pytest.raises(BenchConfigError, match="shorthand"):
            InstrumentConfig.from_mapping("s", "just-a-driver")

    def test_non_numeric_timeout_is_reported(self):
        with pytest.raises(BenchConfigError, match="non-numeric timeout"):
            InstrumentConfig.from_mapping("s", {"driver": "generic", "timeout": "soon"})


class TestBenchConfig:
    def test_from_mapping(self):
        config = BenchConfig.from_mapping({
            "name": "B", "instruments": {"scope": {"driver": "tek3014b"}},
        })
        assert config.name == "B" and "scope" in config.instruments

    def test_no_instruments_is_rejected(self):
        with pytest.raises(BenchConfigError, match="lists no instruments"):
            BenchConfig.from_mapping({"name": "B"})

    def test_instruments_must_be_a_mapping(self):
        with pytest.raises(BenchConfigError, match="mapping of alias"):
            BenchConfig.from_mapping({"name": "B", "instruments": ["scope"]})

    def test_simulated_factory(self):
        config = BenchConfig.simulated(["scope", "psu"])
        assert sorted(config.instruments) == ["psu", "scope"]
        assert all(item.resource == "sim://" for item in config.instruments.values())

    def test_simulated_from_a_mapping_uses_the_right_driver(self):
        """A suite spanning a scope and a probe cannot be simulated with one
        driver for every alias."""
        config = BenchConfig.simulated({"scope": "tek3014b", "probe": "jlink"})
        assert config.instruments["probe"].driver == "jlink"
        assert config.instruments["scope"].driver == "tek3014b"

    def test_simulated_falls_back_for_an_undeclared_alias(self):
        config = BenchConfig.simulated({"scope": ""}, driver="tek3014b")
        assert config.instruments["scope"].driver == "tek3014b"

    def test_simulated_rejects_an_unknown_driver(self):
        with pytest.raises(BenchConfigError, match="cannot simulate unknown driver"):
            BenchConfig.simulated({"x": "flux-capacitor"})

    def test_load_from_json(self, tmp_path):
        path = tmp_path / "bench.json"
        path.write_text(json.dumps({"name": "B", "instruments": {"scope": "tek3014b@sim://"}}))
        assert load_bench(str(path)).name == "B"

    def test_shipped_bench_files_are_valid(self):
        import pathlib

        pytest.importorskip("yaml")
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("simulated.yaml", "lab1.yaml"):
            config = load_bench(str(root / "benches" / name))
            assert config.instruments


class TestBench:
    @pytest.fixture
    def bench(self):
        config = BenchConfig.from_mapping({
            "name": "B",
            "instruments": {"scope": "tek3014b@sim://", "psu": "generic@sim://"},
        })
        with Bench(config) as instance:
            yield instance

    def test_instruments_connect_on_first_use(self, bench):
        assert bench.connected == {}
        bench.get("scope")
        assert list(bench.connected) == ["scope"]

    def test_the_same_instance_is_reused(self, bench):
        assert bench.get("scope") is bench.get("scope")

    def test_correct_driver_per_alias(self, bench):
        assert bench.get("scope").model == "TDS 3014B"
        assert "SIMULATED" in bench.get("psu").model

    def test_unknown_alias_lists_what_exists(self, bench):
        with pytest.raises(BenchConfigError, match="it provides psu, scope"):
            bench.get("thermometer")

    def test_require_passes_for_present_instruments(self, bench):
        bench.require(["scope", "psu"])

    def test_require_reports_everything_missing(self, bench):
        with pytest.raises(BenchConfigError, match="'dmm'.*'scope2'|'scope2'.*'dmm'"):
            bench.require(["dmm", "scope2"])

    def test_close_releases_everything(self, bench):
        scope = bench.get("scope")
        bench.close()
        assert bench.connected == {}
        assert not scope.transport.is_open

    def test_simulate_overrides_the_configured_resource(self):
        config = BenchConfig.from_mapping({
            "name": "B", "instruments": {"scope": "tek3014b@192.0.2.1"},
        })
        with Bench(config, simulate=True) as bench:
            assert bench.get("scope").model == "TDS 3014B"

    def test_declared_drivers_are_checked(self, bench):
        bench.check_drivers({"scope": "tek3014b", "psu": "generic"})

    def test_a_driver_alias_is_accepted(self, bench):
        """Several names map to one driver, so classes are compared, not names."""
        bench.check_drivers({"scope": "tds3014b"})

    def test_the_wrong_kind_of_instrument_is_reported(self, bench):
        """Better here than four steps later on a missing method."""
        with pytest.raises(BenchConfigError, match="wants instrument 'scope' to be a JLinkProbe"):
            bench.check_drivers({"scope": "jlink"})

    def test_an_unregistered_declared_driver_is_reported(self, bench):
        with pytest.raises(BenchConfigError, match="not registered"):
            bench.check_drivers({"scope": "nonexistent"})

    def test_an_absent_alias_is_left_to_require(self, bench):
        bench.check_drivers({"thermometer": "generic"})

    def test_iteration_yields_aliases(self, bench):
        assert list(bench) == ["psu", "scope"]

    def test_all_sim_resources_count_as_simulated(self, bench):
        """A report must disclose simulation even without --simulate."""
        assert bench.is_simulated is True

    def test_a_real_resource_is_not_simulated(self):
        config = BenchConfig.from_mapping({
            "name": "B", "instruments": {"scope": "tek3014b@192.0.2.1"},
        })
        assert Bench(config).is_simulated is False

    def test_simulate_flag_forces_it(self):
        config = BenchConfig.from_mapping({
            "name": "B", "instruments": {"scope": "tek3014b@192.0.2.1"},
        })
        assert Bench(config, simulate=True).is_simulated is True

    def test_a_mixed_bench_is_not_simulated(self):
        """One real instrument makes the run a hardware run."""
        config = BenchConfig.from_mapping({
            "name": "B",
            "instruments": {"scope": "tek3014b@sim://", "psu": "generic@192.0.2.2"},
        })
        assert Bench(config).is_simulated is False


class TestDriverRegistry:
    def test_defaults_are_registered(self):
        assert "tek3014b" in registered_drivers()
        assert "generic" in registered_drivers()

    def test_a_new_driver_can_be_registered(self):
        class Widget(ScpiInstrument):
            SIMULATOR_CLASS = SimulatedInstrument
            MODEL_NAME = "Widget"

        register_driver("widget-test", Widget)
        try:
            assert "widget-test" in registered_drivers()
            config = BenchConfig.from_mapping({
                "name": "B", "instruments": {"w": "widget-test@sim://"},
            })
            with Bench(config) as bench:
                assert isinstance(bench.get("w"), Widget)
        finally:
            from benchtools.runner import bench as bench_module

            bench_module._DRIVERS.pop("widget-test", None)


class TestDescribingInstruments:
    """What made the measurement is part of the measurement.

    A result without the instrument - and, for anything programmable, the
    firmware it was running - is not evidence. These tests cover what a run
    record carries about the bench.

    Traces to: RUN-FR-037, RUN-DD-BENCH.
    """

    @pytest.fixture
    def bench(self):
        config = BenchConfig.from_mapping({
            "name": "B",
            "instruments": {"scope": "tek3014b@sim://", "dongle": "ble-dongle@sim://"},
        })
        with Bench(config) as instance:
            yield instance

    def test_only_instruments_that_were_used(self, bench):
        """Opening an instrument to describe it would change what the run did."""
        bench.get("scope")
        assert list(bench.describe_instruments()) == ["scope"]

    def test_what_is_recorded(self, bench):
        bench.get("scope")
        described = bench.describe_instruments()["scope"]
        assert described["driver"] == "Tek3014B"
        assert described["resource"] == "sim://"
        assert described["model"]
        assert "identity" in described

    def test_firmware_is_recorded_where_the_instrument_reports_it(self, bench):
        """The dongle's firmware build decides what its timings mean."""
        dongle = bench.get("dongle")
        described = bench.describe_instruments()["dongle"]
        assert described["firmware"] == dongle.identify().firmware
        assert dongle.firmware_version in described["firmware"]

    def test_an_instrument_that_will_not_identify_is_still_recorded(self, bench):
        """Silence about the bench is worse than a recorded failure."""
        instrument = bench.get("scope")

        def refuse():
            raise InstrumentError("no answer to *IDN?")

        instrument.identify = refuse
        described = bench.describe_instruments()["scope"]
        assert described["identity_error"] == "no answer to *IDN?"
        assert described["driver"] == "Tek3014B"
