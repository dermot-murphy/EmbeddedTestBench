"""Specifications and bench files run from outside the TestTools checkout.

The runner is normally started from the repository of the firmware under test,
not from this one. Every input file a specification or a bench file names must
be found the same way from there (issue #116).

Traces to: RUN-FR-007, RUN-FR-017, SWE4-UT-PATHS.
"""

from __future__ import annotations

import pathlib
import shutil

import pytest

from benchtools.core.paths import input_paths
from benchtools.runner.bench import Bench, BenchConfig, load_bench, register_driver
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import TestSpec, load_spec

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTER_FILE = ROOT / "configs" / "s2lp_915_38k4_basic.regs"


def _spec(source: str, spec_file: pathlib.Path) -> TestSpec:
    data = {
        "name": "Relative register file",
        "tests": [{
            "name": "The register file is applied",
            "steps": [{"do": "radio.apply_configuration",
                       "with": {"source": source, "reset": "defaults"}}],
        }],
    }
    return TestSpec.from_mapping(data, source=str(spec_file))


def _run(spec: TestSpec):
    config = BenchConfig.simulated(["radio"], driver="s2lp")
    with BenchRunner.from_config(config, simulate=True) as runner:
        return runner.run(spec)


class TestStepArguments:
    def test_a_file_beside_the_specification_is_found_from_elsewhere(
            self, tmp_path, monkeypatch):
        suite = tmp_path / "suite"
        suite.mkdir()
        shutil.copy(REGISTER_FILE, suite / "radio.regs")
        elsewhere = tmp_path / "firmware-under-test"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        record = _run(_spec("radio.regs", suite / "spec.yaml"))
        assert record.status is Status.PASS, record.cases[0].steps[0].error

    def test_a_shipped_configuration_is_found_from_elsewhere(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        record = _run(_spec("configs/s2lp_915_38k4_basic.regs", tmp_path / "spec.yaml"))
        assert record.status is Status.PASS, record.cases[0].steps[0].error

    def test_a_missing_file_is_an_error_naming_where_it_was_looked_for(
            self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        record = _run(_spec("missing.regs", tmp_path / "suite" / "spec.yaml"))
        error = record.cases[0].steps[0].error
        assert record.status is Status.ERROR
        assert "radio.apply_configuration source" in error
        assert str(tmp_path / "suite" / "missing.regs") in error
        assert str(tmp_path / "missing.regs") in error
        assert str(ROOT / "missing.regs") in error


class _RecordingDriver:
    """Stands in for a driver, keeping what the bench handed to ``connect``."""

    received: dict = {}

    @classmethod
    @input_paths("elf", "firmware")
    def connect(cls, resource, timeout=10.0, **options):
        cls.received = dict(options, resource=resource, timeout=timeout)
        return cls()

    def close(self):
        """Nothing to close."""


class TestBenchOptions:
    @pytest.fixture(autouse=True)
    def driver(self):
        register_driver("test-input-paths", _RecordingDriver)
        _RecordingDriver.received = {}

    @staticmethod
    def _bench(tmp_path, options) -> Bench:
        bench_file = tmp_path / "benches" / "bench.json"
        bench_file.parent.mkdir(exist_ok=True)
        config = BenchConfig.from_mapping(
            {"instruments": {"probe": {"driver": "test-input-paths", "options": options}}},
            source=str(bench_file),
        )
        return Bench(config, simulate=True)

    def test_an_option_beside_the_bench_file_is_found_from_elsewhere(
            self, tmp_path, monkeypatch):
        (tmp_path / "benches").mkdir()
        (tmp_path / "benches" / "app.elf").write_text("")
        monkeypatch.chdir(tmp_path)          # not where the bench file is
        self._bench(tmp_path, {"elf": "app.elf", "device": "nRF52840_xxAA"}).get("probe")
        assert _RecordingDriver.received["elf"] == str(tmp_path / "benches" / "app.elf")
        assert _RecordingDriver.received["device"] == "nRF52840_xxAA"

    def test_the_working_directory_still_serves_a_firmware_build(
            self, tmp_path, monkeypatch):
        # benches/lab1.yaml names the firmware repository's own build/,
        # relative to wherever the runner is started.
        work = tmp_path / "firmware-under-test"
        (work / "build").mkdir(parents=True)
        monkeypatch.chdir(work)
        self._bench(tmp_path, {"firmware": "build"}).get("probe")
        assert _RecordingDriver.received["firmware"] == str(work / "build")

    def test_a_missing_option_is_left_to_the_driver_and_logged(
            self, tmp_path, monkeypatch, caplog):
        # A simulated probe never reads its ELF file, so the bench must not
        # refuse it; the driver that does read one says what is missing.
        monkeypatch.chdir(tmp_path)
        with caplog.at_level("WARNING", logger="benchtools.runner.bench"):
            self._bench(tmp_path, {"elf": "firmware.elf"}).get("probe")
        assert _RecordingDriver.received["elf"] == "firmware.elf"
        assert str(tmp_path / "benches" / "firmware.elf") in caplog.text

    def test_an_undeclared_option_is_not_touched(self, tmp_path, monkeypatch):
        (tmp_path / "benches").mkdir()
        (tmp_path / "benches" / "log.txt").write_text("")
        monkeypatch.chdir(tmp_path)
        self._bench(tmp_path, {"log_path": "log.txt"}).get("probe")
        assert _RecordingDriver.received["log_path"] == "log.txt"


SPECS = sorted(ROOT.glob("specs/*.yaml"))
SIMULATED_BENCH = ROOT / "benches" / "simulated_bench.yaml"


def _outcome(spec_path: pathlib.Path):
    """What running *spec_path* on the simulated bench came to, case by case."""
    with BenchRunner.from_config(load_bench(str(SIMULATED_BENCH)), simulate=True) as runner:
        record = runner.run(load_spec(str(spec_path)))
    return record.setup_error, [
        (case.name, case.status, [step.error for step in case.steps]) for case in record.cases
    ]


@pytest.mark.parametrize("spec_path", SPECS, ids=[path.name for path in SPECS])
def test_a_shipped_specification_runs_the_same_from_outside_the_checkout(
        spec_path, tmp_path, monkeypatch):
    """Covers every driver on the simulated bench, against every shipped spec.

    Compared with a run started in the checkout, rather than against PASS:
    some specifications need hardware the simulators do not model, and that
    is not what this test is about. Output files land in the directory each
    run was started from, as they always have.
    """
    # The shipped specifications and bench files are YAML.
    pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")
    monkeypatch.chdir(ROOT)
    inside = _outcome(spec_path)
    monkeypatch.chdir(tmp_path)
    outside = _outcome(spec_path)
    assert outside == inside
