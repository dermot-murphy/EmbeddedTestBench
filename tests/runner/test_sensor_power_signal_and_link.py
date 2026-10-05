"""The five-instrument specification, run end to end on the simulated bench.

It powers a board, programs it, measures what it draws through the meter,
checks the LED line is being driven, then finds the board over the air by
signal strength and asks it what it is running.

As with the bring-up specification, two things are verified and they are worth
separating. The first is that it runs: every step resolves and every limit is
met. The second, and the reason these tests go to the trouble of breaking
things, is that it would **fail** if those facts stopped being true. A
specification that passes whatever the bench does is worse than none, because
it reads as evidence.

Traces to: RUN-FR-016, RUN-FR-024, DMM-FR-045, BLE-FR-025, ETB-QT-02a.
"""

from __future__ import annotations

import pathlib

import pytest

# The whole group needs the optional YAML extra, so the skip has to run
# before the imports below rather than after them.
# pylint: disable=wrong-import-position
pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

from benchtools.runner.bench import Bench, load_bench
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import load_spec

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "specs" / "sensor_power_signal_and_link.yaml"
BENCH = ROOT / "benches" / "simulated_bench.yaml"


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
    matching = [item for item in record.cases if fragment in item.name]
    assert len(matching) == 1, "no single case matching %r" % fragment
    return matching[0]


def measurement(record, name: str):
    for item in record.cases:
        for step in item.steps:
            for measured in step.measurements:
                if measured.name == name:
                    return measured
    raise AssertionError("no measurement named %r" % name)


class TestItPasses:
    def test_the_specification_passes_on_the_simulated_bench(self):
        record = run()
        assert record.status is Status.PASS, [
            (item.name, item.status) for item in record.cases if item.status is not Status.PASS
        ]

    def test_every_instrument_is_exercised(self):
        # Five instruments in one pass is the point of this specification; a
        # run that quietly skipped one would still be green.
        record = run()
        assert len(record.cases) == 5

    def test_the_current_is_measured_through_the_meter(self):
        # Not taken from the supply's own reading: the supply measures what it
        # delivers to the whole rail, the meter what this board takes.
        measured = measurement(record=run(), name="sensor_current")
        assert measured.value == pytest.approx(0.0214)
        assert measured.unit == "A"

    def test_the_strongest_board_is_the_one_connected_to(self):
        record = run()
        assert measurement(record, "target_signal_dbm").value == -62
        assert case(record, "found over the air").status is Status.PASS

    def test_the_reported_version_is_compared_with_the_flashed_build(self):
        assert measurement(run(), "reported_version").value == "1.4.2"


class TestItWouldFail:
    """The tests that make the ones above worth having."""

    def test_a_board_drawing_too_much_fails_the_current_test_only(self):
        # A short across the rail, a wrongly wired meter, or a board with a
        # fault all look like this. It must fail here and not contaminate the
        # other four tests.
        # 200 mA: above the board's band, inside the meter's 400 mA range. The
        # simulated meter shows OFL above that range, as a real 1604 does, so
        # 1 A here would be an overrange rather than a reading (#115).
        record = run(dmm={"simulated_value": 0.2})
        assert record.status is Status.FAIL
        assert case(record, "draws the current").status is Status.FAIL
        assert case(record, "powered at 3.2 V").status is Status.PASS
        assert case(record, "found over the air").status is Status.PASS

    def test_a_board_drawing_nothing_fails_too(self):
        # The other end of the band: a board that is not running draws almost
        # nothing, and "almost nothing" must not read as a pass.
        record = run(dmm={"simulated_value": 0.0001})
        assert record.status is Status.FAIL
        assert case(record, "draws the current").status is Status.FAIL

    def test_a_board_running_a_different_build_fails_the_version_check(self):
        # The last test compares what the build manifest says with what the
        # board reports over the air. Flashing a different build must break
        # that comparison - otherwise the two ends were never really compared.
        record = run(probe={"firmware": "benches/simulated/dongle"})
        assert record.status is not Status.PASS
        assert case(record, "found over the air").status is Status.FAIL
        assert case(record, "draws the current").status is Status.PASS
