"""The Kepler specifications, end to end on the simulated bench (#121, #122).

The four ``specs/kepler_*.yaml`` select sensor 5C1712, talk to it over the
dongle, read its RTT log through the probe and set its supply, then check what
its radio transmits with the S2-LP kit. On the simulated bench one simulated
sensor stands behind all of them, and the simulated kit hears its frames.

As with the bring-up specification, passing is half of it. Each fact the
specifications check is then broken in the simulated sensor, to confirm the
specification would notice.

Traces to: BLE-FR-120, S2LP-FR-087, SWE4-UT-KEPLERSIM.
"""

from __future__ import annotations

import pathlib

import pytest

from benchtools.runner.bench import Bench, load_bench
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import load_spec
from benchtools.simulated import kepler_sensor, reset_world

# The specifications and the bench are YAML, an optional extra.
yaml = pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCH = ROOT / "benches" / "simulated_bench.yaml"
SPECS = ["kepler_version.yaml", "kepler_battery.yaml", "kepler_preamble.yaml",
         "kepler_temperature.yaml"]

#: Waits that are about the sensor's real timing, shortened so a run takes
#: seconds. Nothing checked depends on them.
FAST = {"settle_s": 0.0, "interval_s": 0.05}

#: A receive that will hear nothing waits out its timeout in real time; a
#: test that expects that shortens it to this.
QUIET_S = 1.0

#: The Kepler plugin the specifications name (#238).
KEPLER_PLUGIN = ROOT / "plugins" / "kepler"


@pytest.fixture(autouse=True)
def clean_world():
    """Every test starts with a sensor fresh from the factory, and the air at 0."""
    reset_world()
    yield
    reset_world()


def run(spec_name: str, tmp_path: pathlib.Path, only=(), quiet: bool = False,
        regs: str = ""):
    """Run *spec_name* on the simulated bench, with its waits shortened.

    :param quiet: Shorten the S2-LP receive timeouts, for a test in which the
        frames will not come.
    :param regs: Apply this register file instead of the specification's.
    """
    data = yaml.safe_load((ROOT / "specs" / spec_name).read_text())
    data["plugins"] = [str(KEPLER_PLUGIN)]      # the copy is not beside plugins/
    for name, value in FAST.items():
        if name in data.get("parameters", {}):
            data["parameters"][name] = value
    for step in _all_steps(data):
        if quiet and step.get("do", "").startswith("s2lp.") and "timeout" in step.get("with", {}):
            step["with"]["timeout"] = QUIET_S
        if regs and step.get("do") == "s2lp.apply_configuration":
            step["with"]["source"] = regs
    if quiet and "frame_timeout_s" in data.get("parameters", {}):
        data["parameters"]["frame_timeout_s"] = QUIET_S
    path = tmp_path / spec_name
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    bench = Bench(load_bench(str(BENCH)))
    try:
        return BenchRunner(bench).run(load_spec(str(path)), selection=only)
    finally:
        bench.close()


def _all_steps(data):
    for section in ("setup", "teardown"):
        yield from data.get(section) or []
    for case in data.get("tests") or []:
        yield from case.get("steps") or []


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


def step_doing(record, action: str):
    """The first step doing *action*."""
    for _, step in steps(record):
        if step.action == action:
            return step
    raise AssertionError("no step did %s" % action)


def corrupt(monkeypatch, frame: str, offset: int, value: int) -> None:
    """Make every *frame* (``version_frame`` or ``alive_frame``) the sensor
    sends carry *value* at byte *offset*, and nothing else change."""
    model = kepler_sensor()
    original = getattr(model, frame)

    def changed(repeat: int = 0) -> bytes:
        payload = bytearray(original(repeat))
        payload[offset] = value
        return bytes(payload)

    monkeypatch.setattr(model, frame, changed)


@pytest.mark.parametrize("spec_name", SPECS)
def test_every_step_passes(spec_name, tmp_path):
    """Done when, #122: all four specifications pass on the simulated bench."""
    record = run(spec_name, tmp_path)
    assert not record.setup_error, record.setup_error
    ran = list(steps(record))
    assert any(step.action.startswith("s2lp.dut_") or step.action == "s2lp.check_preamble"
               for _, step in ran), "no radio step ran"
    failed = ["%s: %s %s %s" % (case.name, step.action, step.status, step.error)
              for case, step in ran if step.status is not Status.PASS]
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
        data["plugins"] = [str(KEPLER_PLUGIN)]
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


class TestBrokenRadioFactsAreNoticed:
    """Each fact checked over the air, made false in the simulated sensor (#122)."""

    # -- kepler_version.yaml ---------------------------------------------
    def test_a_version_frame_with_the_sha_appended(self, tmp_path):
        """What the captured V11.00.0000-95 build sends, against the V11 rule."""
        kepler_sensor().frame_version_with_sha = True
        record = run("kepler_version.yaml", tmp_path)
        assert measurement(record, "version_as_rd_version").status is Status.FAIL
        assert measurement(record, "sha_as_start_of_rd_sha").status is Status.PASS

    def test_a_version_frame_with_another_sha(self, tmp_path, monkeypatch):
        corrupt(monkeypatch, "version_frame", 9, ord("d"))      # c051f36 -> d051f36
        record = run("kepler_version.yaml", tmp_path)
        assert measurement(record, "sha_as_start_of_rd_sha").status is Status.FAIL

    def test_a_version_frame_after_a_reset_that_is_not_a_soft_reset(self, tmp_path,
                                                                     monkeypatch):
        model = kepler_sensor()
        original = model.reset

        def power_on_reset():
            original()
            model.reset_reason = 1

        monkeypatch.setattr(model, "reset", power_on_reset)
        record = run("kepler_version.yaml", tmp_path)
        assert measurement(record, "reset_reason").status is Status.FAIL

    def test_a_version_frame_from_another_pcb(self, tmp_path):
        kepler_sensor().pcb_code = 4
        record = run("kepler_version.yaml", tmp_path)
        assert measurement(record, "pcb_version").status is Status.FAIL

    def test_a_version_frame_whose_loaded_battery_is_not_the_ble_reading(self, tmp_path,
                                                                         monkeypatch):
        corrupt(monkeypatch, "version_frame", 77, 150)          # 3000 mV, not 3280
        record = run("kepler_version.yaml", tmp_path)
        assert (measurement(record, "battery_loaded_as_rd_battery_loaded").status
                is Status.FAIL)

    def test_no_version_frame_after_the_reset(self, tmp_path, monkeypatch):
        model = kepler_sensor()
        original = model.reset

        def reset_without_version():
            original()
            model._next_version_at = None       # pylint: disable=protected-access

        monkeypatch.setattr(model, "reset", reset_without_version)
        record = run("kepler_version.yaml", tmp_path, quiet=True)
        frame = step_doing(record, "s2lp.dut_frame")
        assert frame.status is Status.ERROR
        assert "no VERSION frame from 5C1712" in frame.error

    def test_frames_from_another_sensor(self, tmp_path, monkeypatch):
        """The receiver hears a sensor, but not the one the specification names."""
        corrupt(monkeypatch, "version_frame", 0, 0x5D)          # 5C1712 -> 5D1712
        record = run("kepler_version.yaml", tmp_path, quiet=True)
        assert step_doing(record, "s2lp.dut_frame").status is Status.ERROR

    # -- the receiver's configuration ------------------------------------
    @pytest.mark.parametrize("register, value", [
        ("SYNT0", "0xF4"),                  # another frequency
        ("MOD3", "0x26"),                   # another data rate
        ("PCKT_FLT_GOALS0", "0xB0"),        # the sensor's sync word, one bit off
    ])
    def test_a_receiver_not_set_up_for_the_sensor_hears_nothing(self, tmp_path, register,
                                                                 value):
        """The configuration step proves nothing if a wrong one also hears."""
        source = KEPLER_PLUGIN / "configs" / "s2lp_kepler_433_rx.regs"
        lines = []
        for line in source.read_text().splitlines():
            if line.split() and line.split()[0] == register:
                line = "%-22s %s" % (register, value)
            lines.append(line)
        regs = tmp_path / "wrong.regs"
        regs.write_text("\n".join(lines) + "\n")
        record = run("kepler_temperature.yaml", tmp_path, quiet=True, regs=str(regs),
                     only=("The ALIVE frame carries the temperature read over BLE",))
        assert measurement(record, "frames").status is Status.FAIL

    # -- kepler_battery.yaml ---------------------------------------------
    def test_an_alive_battery_that_does_not_follow_the_supply(self, tmp_path, monkeypatch):
        corrupt(monkeypatch, "alive_frame", 11, 165)            # 3.3 V whatever is set
        record = run("kepler_battery.yaml", tmp_path)
        first = [case for case in record.cases if case.name.startswith("At 3.3 V")][0]
        later = [case for case in record.cases if case.name.startswith("At 3.0 V")][0]
        assert all(step.status is Status.PASS for step in first.steps)
        assert any(measured.name == "alive_lowest_from_ble" and measured.status is Status.FAIL
                   for step in later.steps for measured in step.measurements)

    def test_a_sensor_that_sends_nothing(self, tmp_path):
        kepler_sensor().transmitting = False
        record = run("kepler_battery.yaml", tmp_path, quiet=True,
                     only=("At 3.3 V the sensor reads the supply, and the ALIVE frame carries it",))
        assert measurement(record, "alive_frames").status is Status.FAIL

    # -- kepler_temperature.yaml -----------------------------------------
    def test_an_alive_temperature_far_from_the_ble_reading(self, tmp_path, monkeypatch):
        corrupt(monkeypatch, "alive_frame", 10, 0xDF)           # 22.3 C, not 21.2 C
        record = run("kepler_temperature.yaml", tmp_path,
                     only=("The machine temperature read over BLE is steady",
                           "The ALIVE frame carries the temperature read over BLE"))
        assert measurement(record, "alive_highest_from_ble").status is Status.FAIL

    # -- kepler_preamble.yaml --------------------------------------------
    def test_a_preamble_setting_the_radio_does_not_take(self, tmp_path, monkeypatch):
        """The setting is stored, but the radio keeps sending 32 pairs."""
        model = kepler_sensor()
        original = model.reset

        def reset_keeping_the_preamble():
            kept = model.radio_preamble_length
            original()
            model.radio_preamble_length = kept

        monkeypatch.setattr(model, "reset", reset_keeping_the_preamble)
        record = run("kepler_preamble.yaml", tmp_path,
                     only=("A 48-pair preamble is heard as 48 pairs",))
        assert measurement(record, "preamble_as_set").status is Status.FAIL
        assert measurement(record, "best_pqi").status is Status.FAIL

    def test_a_preamble_longer_than_set(self, tmp_path, monkeypatch):
        model = kepler_sensor()
        original = model.reset

        def reset_with_a_longer_preamble():
            original()
            model.radio_preamble_length += 4

        monkeypatch.setattr(model, "reset", reset_with_a_longer_preamble)
        record = run("kepler_preamble.yaml", tmp_path,
                     only=("The default 32-pair preamble is restored and heard as 32 pairs",))
        assert measurement(record, "preamble_as_set").status is Status.FAIL
