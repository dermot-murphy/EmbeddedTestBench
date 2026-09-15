"""The sensor bring-up specification, run end to end on the simulated bench.

This is the shipped first test of a bench session: it powers the board, checks
the dongle that will measure it, programs the firmware, reads the board's own
identifier off the part, starts it, finds it over the air *by that identifier*
and confirms it reports the version that was flashed onto it.

Two things are being verified here and they are worth separating. The first is
that the specification runs: every step resolves, every limit is met. The
second, and the reason the tests below go to the trouble of breaking things, is
that it would **fail** if any of those facts stopped being true - a
specification that passes whatever the bench does is worse than none, because
it reads as evidence.

Traces to: RUN-FR-016, RUN-FR-024, SWE4-UT-BRINGUP.
"""

from __future__ import annotations

import json
import pathlib

import pytest

# The specification and the bench it runs on are YAML, so this whole group needs
# the optional extra. The fixture checks below do not, but splitting them out
# would separate the assertions about the fixtures from the run that depends on
# them, which is worth more than three tests in the extras-blocked run.
pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

from benchtools.instruments.jlink.simulator import (
    DEVICE_ID_ADDRESS,
    DEVICE_ID_VALID,
    SIMULATED_DEVICE_ID,
)
from benchtools.instruments.nordic_dongle import DEFAULT_SENSORS, SimulatedDongle
from benchtools.runner.bench import Bench, load_bench
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import load_spec

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "specs" / "sensor_bringup.yaml"
BENCH = ROOT / "benches" / "simulated_bench.yaml"
FIXTURES = ROOT / "benches" / "simulated"


def manifest(name: str) -> dict:
    return json.loads((FIXTURES / name / "firmware_manifest.json").read_text())


def run(**overrides):
    """Run the shipped specification on the simulated bench."""
    config = load_bench(str(BENCH))
    for alias, options in overrides.items():
        config.instruments[alias].options.update(options)
    bench = Bench(config)
    try:
        return BenchRunner(bench).run(load_spec(str(SPEC)))
    finally:
        bench.close()


def case(record, fragment: str):
    """The one case whose name contains *fragment*."""
    matching = [item for item in record.cases if fragment in item.name]
    assert len(matching) == 1, "no single case matching %r" % fragment
    return matching[0]


def measurement(record, name: str):
    for item in record.cases:
        for step in item.steps:
            for measured in step.measurements:
                if measured.name == name:
                    return measured
    raise AssertionError("no measurement called %r" % name)


class TestTheBenchFixturesAreHonest:
    """The manifests under benches/simulated are fixtures, not build output.
    They are only worth having if they say what the simulators say: otherwise a
    simulated run fails for reasons that are about the fixture."""

    def test_the_dongle_manifest_matches_the_simulated_dongle(self):
        data = manifest("dongle")
        assert data["version"] == SimulatedDongle.DEFAULT_FIRMWARE_VERSION
        assert data["built"] == SimulatedDongle.DEFAULT_FIRMWARE_BUILT

    def test_the_sensor_manifest_matches_what_the_simulated_sensor_reports(self):
        sensor = next(item for item in DEFAULT_SENSORS if item.name == "SENS-0A1B2C")
        assert manifest("sensor")["version"] == sensor.responses["rd version"]

    def test_the_simulated_board_is_the_one_the_dongle_advertises(self):
        """The identifier in the part, rendered as the six hex digits the
        specification scans for, must appear in the name of a board the
        simulated dongle actually advertises."""
        digits = "{:06X}".format(SIMULATED_DEVICE_ID)
        assert any(digits in item.name for item in DEFAULT_SENSORS)

    def test_exactly_one_simulated_board_carries_that_identifier(self):
        """The specification requires exactly one, so a population with two
        would fail it for a reason that is about the fixture."""
        digits = "{:06X}".format(SIMULATED_DEVICE_ID)
        assert sum(digits in item.name for item in DEFAULT_SENSORS) == 1


class TestItPasses:
    def test_every_case_passes(self):
        record = run()
        assert record.status is Status.PASS, [
            (item.name, item.status.value) for item in record.cases
        ]

    def test_the_run_is_disclosed_as_simulated(self):
        """Simulated numbers that read as hardware measurements are the one
        thing this repository will not produce."""
        assert run().simulated is True

    def test_the_rail_is_the_one_that_was_asked_for(self):
        assert measurement(run(), "rail_voltage").value == pytest.approx(3.2)

    def test_the_identity_record_is_checked_before_it_is_used(self):
        """Zero is valid. A part that was never programmed reads 0xFF here, so
        "never programmed" fails the same check as "corrupted"."""
        assert measurement(run(), "identity_is_valid").value == DEVICE_ID_VALID

    def test_the_identifier_comes_from_the_part(self):
        """Three bytes, most significant first - the order they are printed in
        and the order they appear in the name."""
        assert measurement(run(), "sensor_id").value == SIMULATED_DEVICE_ID

    def test_the_device_was_chosen_by_that_identifier(self):
        record = run()
        assert measurement(record, "boards_with_that_identifier").value == 1
        assert measurement(record, "linked_board").value == "SENS-0A1B2C"

    def test_the_reported_version_is_recorded_as_text(self):
        """A version is not a number, and a report that rendered it as one
        would lose the only thing about it that mattered."""
        assert measurement(run(), "reported_version").value == "1.4.2"


class TestItWouldFail:
    """Each of these breaks one fact the specification claims to establish."""

    def test_a_firmware_that_reports_another_version(self, tmp_path):
        """The heart of it: the build says one thing, the board says another.
        A failure, with both versions in the record - not an error."""
        (tmp_path / "firmware_manifest.json").write_text(
            json.dumps({"version": "9.9.9", "built": "2026-01-01T00:00:00Z"})
        )
        record = run(probe={"firmware": str(tmp_path)})
        reported = measurement(record, "reported_version")
        assert reported.status is Status.FAIL
        assert reported.value == "1.4.2" and "9.9.9" in reported.limit

    @pytest.mark.parametrize(
        "record,why",
        [
            (b"\xff\xff\xff\xff", "never programmed"),
            (b"\x01\x0a\x1b\x2c", "validity byte not zero"),
        ],
    )
    def test_a_part_whose_identity_record_is_not_valid(self, record, why):
        """Caught where it is read, rather than three steps later as "no sensor
        found" - which would point at the radio rather than at the part."""
        assert case(run(), "identifies itself").status is Status.PASS, why
        bench = Bench(load_bench(str(BENCH)))
        try:
            probe = bench.get("probe")
            probe.write_memory(DEVICE_ID_ADDRESS, record)
            assert probe.read_u8(DEVICE_ID_ADDRESS) != DEVICE_ID_VALID
            spec = load_spec(str(SPEC))
            identity = next(
                item for item in spec.tests if "identifies itself" in item.name
            )
            assert BenchRunner(bench).run_case(identity).status is Status.FAIL
        finally:
            bench.close()

    def test_an_identifier_of_zero_is_refused(self):
        """A valid record whose identifier is nothing. The scan would go
        looking for board 000000."""
        bench = Bench(load_bench(str(BENCH)))
        try:
            probe = bench.get("probe")
            probe.write_memory(DEVICE_ID_ADDRESS, b"\x00\x00\x00\x00")
            spec = load_spec(str(SPEC))
            identity = next(
                item for item in spec.tests if "identifies itself" in item.name
            )
            assert BenchRunner(bench).run_case(identity).status is Status.FAIL
        finally:
            bench.close()

    def test_a_board_that_says_nothing_on_rtt(self):
        """A silent board is a failed test, not a broken bench: the step counts
        lines rather than waiting for one, so the verdict is a limit."""
        bench = Bench(load_bench(str(BENCH)))
        try:
            probe = bench.get("probe")
            probe.rtt_start()
            # Never started: halted at reset, so nothing is emitted.
            assert probe.rtt_lines_within(0.2) == 0
        finally:
            bench.close()
