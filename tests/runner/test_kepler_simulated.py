"""The Kepler specifications' BLE and RTT steps, on the simulated bench (#121).

The four ``specs/kepler_*.yaml`` select sensor 5C1712, talk to it over the
dongle, read its RTT log through the probe and set its supply, then check what
its radio transmits with the S2-LP kit. The first three now have a simulated
sensor behind them; the radio does not yet (#122), so the S2-LP steps are
stood in for here by ones that fail at once, rather than wait out their 60 to
180 s receive timeouts on a silent simulated air.

As with the bring-up specification, passing is half of it. Each fact the
specifications check over BLE or RTT is then broken in the simulated sensor, to
confirm the specification would notice.

Traces to: BLE-FR-120, SWE4-UT-KEPLERSIM.
"""

from __future__ import annotations

import pathlib

import pytest

from benchtools.core.errors import MeasurementError
from benchtools.instruments.s2lp.s2lp import S2lpDevkit
from benchtools.runner.bench import Bench, load_bench
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import load_spec
from benchtools.simulated import kepler_sensor, reset_world

# The specifications and the bench are YAML, an optional extra.
yaml = pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCH = ROOT / "benches" / "simulated_bench.yaml"

#: The instruments the simulated sensor stands behind; every step on them must
#: pass. ``s2lp`` steps wait for #122.
SIMULATED = ("dongle.", "rtt.", "psu.", "sleep")

#: Waits that are about the sensor's real timing, shortened so a run takes
#: seconds. Nothing checked depends on them.
FAST = {"settle_s": 0.0, "interval_s": 0.05}


@pytest.fixture(autouse=True)
def silent_radio(monkeypatch):
    """The S2-LP steps fail at once: the simulated sensor does not transmit yet (#122)."""
    def not_simulated(self, *args, **kwargs):
        raise MeasurementError("the simulated sensor does not transmit yet (#122)")

    for name in ("kepler_frame", "kepler_samples", "check_preamble"):
        monkeypatch.setattr(S2lpDevkit, name, not_simulated)
    reset_world()
    yield
    reset_world()


def run(spec_name: str, tmp_path: pathlib.Path, only=()):
    """Run *spec_name* on the simulated bench, with its waits shortened."""
    data = yaml.safe_load((ROOT / "specs" / spec_name).read_text())
    for name, value in FAST.items():
        if name in data.get("parameters", {}):
            data["parameters"][name] = value
    path = tmp_path / spec_name
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    bench = Bench(load_bench(str(BENCH)))
    try:
        return BenchRunner(bench).run(load_spec(str(path)), selection=only)
    finally:
        bench.close()


def steps(record):
    for case in record.cases:
        for step in case.steps:
            yield case, step


def measurement(record, name: str, action: str = ""):
    """The first measurement called *name*, from a step doing *action* if given."""
    for _, step in steps(record):
        if action and step.action != action:
            continue
        for measured in step.measurements:
            if measured.name == name:
                return measured
    raise AssertionError("no measurement called %r" % name)


@pytest.mark.parametrize("spec_name", ["kepler_version.yaml", "kepler_battery.yaml",
                                       "kepler_preamble.yaml", "kepler_temperature.yaml"])
def test_every_ble_rtt_and_supply_step_passes(spec_name, tmp_path):
    """Done when, #121: the BLE-side steps of all four specifications pass."""
    record = run(spec_name, tmp_path)
    assert not record.setup_error, record.setup_error
    simulated = [(case.name, step) for case, step in steps(record)
                 if step.action.startswith(SIMULATED)]
    assert simulated, "no simulated step ran"
    failed = ["%s: %s %s %s" % (name, step.action, step.status, step.error)
              for name, step in simulated if step.status is not Status.PASS]
    assert not failed, "\n".join(failed)


class TestBrokenFactsAreNoticed:
    """Each fact checked over BLE or RTT, made false in the simulated sensor."""

    def test_a_battery_that_does_not_follow_the_supply(self, tmp_path):
        model = kepler_sensor()
        model.supply = None
        model.battery_mv = 3000                # 0.3 V below the 3.3 V setting
        record = run("kepler_battery.yaml", tmp_path)
        assert measurement(record, "ble_lowest").status is Status.FAIL

    def test_an_alive_period_the_sensor_does_not_acknowledge(self, tmp_path):
        model = kepler_sensor()
        model.ALIVE_PERIOD_RANGE = (60, 900)   # 10 s is now out of range
        record = run("kepler_battery.yaml", tmp_path)
        # In setup, so nothing after it runs: no supply step is trusted to a
        # sensor that did not take the setting.
        assert "dongle.command" in record.setup_error
        assert "expectation was not met" in record.setup_error

    def test_a_machine_temperature_that_wanders(self, tmp_path, monkeypatch):
        model = kepler_sensor()
        readings = iter(range(20000, 40000, 1500))      # 1.5 C a reading
        original = model.respond

        def wandering(request):
            if request.strip().upper() == "RD TEMPERATURE":
                model.temperature_mc = next(readings)
            return original(request)

        monkeypatch.setattr(model, "respond", wandering)
        record = run("kepler_temperature.yaml", tmp_path,
                     only=("The machine temperature read over BLE is steady",))
        assert measurement(record, "machine_spread").status is Status.FAIL

    def test_an_mcu_far_from_the_machine_temperature(self, tmp_path):
        kepler_sensor().mcu_above_machine_mc = 6000      # the limit is 5 C
        record = run("kepler_temperature.yaml", tmp_path)
        assert measurement(record, "mcu_highest_from_machine").status is Status.FAIL

    def test_a_reset_the_sensor_does_not_acknowledge(self, tmp_path, monkeypatch):
        model = kepler_sensor()
        original = model.respond
        monkeypatch.setattr(model, "respond", lambda request: (
            "NACK Invalid Command" if "ECURESET" in request.upper() else original(request)))
        record = run("kepler_version.yaml", tmp_path)
        assert measurement(record, "reset_acknowledged").status is Status.FAIL

    def test_a_loaded_battery_reading_in_another_format(self, tmp_path, monkeypatch):
        model = kepler_sensor()
        original = model.respond
        monkeypatch.setattr(model, "respond", lambda request: (
            original(request).replace("mV", " volts")
            if request.strip().upper() == "RD BATTERY-LOADED" else original(request)))
        record = run("kepler_version.yaml", tmp_path)
        sampled = [step for _, step in steps(record) if step.action == "dongle.sample_command"]
        assert sampled[0].status is Status.ERROR
        assert "finds no number" in sampled[0].error

    def test_a_silent_rtt_log_is_not_an_mcu_reading(self, tmp_path, monkeypatch):
        """A probe wired to nothing reads no MCU temperature, and says so."""
        monkeypatch.setattr("benchtools.instruments.jlink.probe.rtt_source",
                            lambda target: (lambda: "something else"))
        data = yaml.safe_load((ROOT / "specs" / "kepler_temperature.yaml").read_text())
        data["parameters"].update(FAST)
        for step in data["tests"][1]["steps"]:
            if step.get("do") == "rtt.rtt_samples":
                step["with"]["timeout"] = 2.0
        (tmp_path / "quiet.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
        bench = Bench(load_bench(str(BENCH)))
        try:
            record = BenchRunner(bench).run(load_spec(str(tmp_path / "quiet.yaml")))
        finally:
            bench.close()
        assert measurement(record, "readings", action="rtt.rtt_samples").status is Status.FAIL
