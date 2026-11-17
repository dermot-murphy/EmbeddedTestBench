"""The PICO2 Test Board's test sequence, run end to end on the simulated bench.

``specs/pico2_test_board.yaml`` drives the LEDs, reads the temperature and runs
the generator as bench-runner steps (#330). This runs it against the simulated
bench and checks that it passes, and that the board is left dark and idle.

Traces to: PICO-FR-008, PICO-FR-009, PICO-FR-040, SWE4-UT-PICOSPEC.
"""

from __future__ import annotations

import pathlib

import pytest

# pylint: disable=wrong-import-position
pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

from benchtools.runner.bench import Bench, load_bench
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import load_spec

ROOT = pathlib.Path(__file__).resolve().parents[3]
SPEC = ROOT / "specs" / "pico2_test_board.yaml"
BENCH = ROOT / "benches" / "simulated_bench.yaml"


@pytest.fixture(name="ran")
def fixture_ran():
    bench = Bench(load_bench(str(BENCH)))
    try:
        record = BenchRunner(bench).run(load_spec(str(SPEC)))
        board = bench.get("pico2")
        after = {
            "leds": [board.led(colour) for colour in ("red", "yellow", "green")],
            "status": [item.status for item in board.freq_status()],
        }
        yield record, after
    finally:
        bench.close()


def test_the_sequence_passes(ran):
    record, _ = ran
    failed = [(item.name, item.status) for item in record.cases if item.status != Status.PASS]
    assert not failed
    assert len(record.cases) == 5


def test_the_board_is_left_dark_and_idle(ran):
    _, after = ran
    assert after["leds"] == [False, False, False]
    assert "Running" not in after["status"]
