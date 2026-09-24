"""The bench self-check, run end to end on the simulated bench.

It asks whether every instrument can be reached and driven, with nothing
connected to any of them. The interesting test is the last one: a supply that
has something still wired to it must be *caught*, because that is the
condition the specification's warning asks the operator to remove, and the
whole point of the check is that it notices.

Traces to: RUN-FR-016, RUN-FR-054 .. RUN-FR-057, TB-QT-05.
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
SPEC = ROOT / "specs" / "bench_self_check.yaml"
BENCH = ROOT / "benches" / "simulated_bench.yaml"


def run(load_ohms=None):
    """Run the self-check, optionally with something still wired to the rail."""
    bench = Bench(load_bench(str(BENCH)))
    try:
        if load_ohms is not None:
            # Reach the simulated supply and hang a load on channel 1, which
            # is what "a sensor was left connected" looks like from here.
            bench.get("psu").transport.responder.set_load(1, load_ohms)
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


class TestTheCheckPasses:
    def test_a_healthy_bench_passes(self):
        record = run()
        assert record.status is Status.PASS, [
            (item.name, item.status) for item in record.cases if item.status is not Status.PASS
        ]

    def test_every_instrument_is_reached(self):
        # Five instruments, five tests. A check that quietly skipped one would
        # still be green, and would be worse than no check at all.
        record = run()
        assert len(record.cases) == 5
        for fragment in ("supply", "multimeter", "oscilloscope", "debug probe", "BLE dongle"):
            assert case(record, fragment).status is Status.PASS

    def test_every_instrument_identity_is_recorded(self):
        # The identities are what makes the check evidence rather than a
        # green light: they say which instruments answered.
        record = run()
        assert set(record.instruments) == {"psu", "dmm", "scope", "probe", "dongle"}

    def test_the_supply_draws_nothing_into_an_open_circuit(self):
        assert measurement(run(), "supply_current_into_open_circuit").value == pytest.approx(0.0)

    def test_the_scope_readback_matches_what_was_set(self):
        record = run()
        assert measurement(record, "scope_volts_per_div").value == pytest.approx(0.5)
        assert measurement(record, "scope_time_per_div").value == pytest.approx(0.001)


class TestTheCheckWouldFail:
    def test_something_still_connected_to_the_supply_is_caught(self):
        # 10 ohms at 1 V draws 100 mA, which is the configured limit, so the
        # supply leaves constant voltage. That is the check noticing that the
        # warning was not acted on - the one failure this specification exists
        # to produce.
        record = run(load_ohms=10.0)
        assert record.status is not Status.PASS
        assert case(record, "supply").status is Status.FAIL

    def test_the_other_instruments_still_pass_when_the_supply_fails(self):
        # A loaded rail says nothing about the scope or the dongle, and a
        # check that failed everything would hide where the problem is.
        record = run(load_ohms=10.0)
        assert case(record, "oscilloscope").status is Status.PASS
        assert case(record, "BLE dongle").status is Status.PASS
