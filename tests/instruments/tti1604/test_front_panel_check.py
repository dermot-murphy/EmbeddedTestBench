"""The TTi 1604 front-panel check, ``examples/12_dmm_front_panel_check.py``.

Run against the simulator: every step is taken, the log records what the
driver read at each one, the operator's answers are recorded as given, and the
meter is left on DC volts, auto-ranging, in local mode - whether the run
completes, is stopped, or fails.

Traces to: DMM-FR-029, DMM-FR-030, DMM-FR-033, DMM-FR-081, SWE4-UT-DMMPANEL.
"""

from __future__ import annotations

import json
import math
import pathlib
import runpy

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.tti1604 import SimulatedTti1604, Tti1604

SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "examples" / "12_dmm_front_panel_check.py"


@pytest.fixture(name="check")
def fixture_check():
    """The script's namespace, loaded without running it."""
    return runpy.run_path(str(SCRIPT), run_name="front_panel_check")


@pytest.fixture(name="meter")
def fixture_meter(monkeypatch):
    """One simulated meter, open-circuit, handed to the script in place of a port."""
    simulator = SimulatedTti1604(value=0.0)
    simulator.measurement_type = 3                  # found on DC milliamps

    def connect(_resource, **_kwargs):
        instrument = Tti1604(MockTransport(responder=simulator))
        instrument.initialise()
        return instrument

    monkeypatch.setattr(Tti1604, "connect", staticmethod(connect))
    return simulator


def _run(check, tmp_path, *extra):
    log = tmp_path / "log.json"
    status = check["main"](["COM6", "--hold", "0", "--log", str(log), *extra])
    return status, json.loads(log.read_text(encoding="utf-8"))


class TestAFullRun:
    def test_every_step_is_taken_and_logged(self, check, meter, tmp_path):
        status, record = _run(check, tmp_path)
        assert status == 0
        assert [step["step"] for step in record["steps"]] == list(range(1, 13))
        assert all(step["panel"].startswith("(not checked") for step in record["steps"])
        assert record["identity"].startswith("Thurlby Thandar Instruments,1604")
        assert record["original"]["function"] == "dc_milliamps"
        assert meter.received

    @pytest.mark.usefixtures("meter")
    def test_the_driver_reading_is_recorded_at_each_step(self, check, tmp_path):
        _, record = _run(check, tmp_path)
        by_step = {step["step"]: step["driver"] for step in record["steps"]}
        assert by_step[2]["function"] == "dc_volts" and by_step[2]["auto"] is True
        assert by_step[3]["function"] == "ac_volts"
        assert by_step[4]["function"] == "dc_millivolts"
        assert by_step[5]["range"] == "40 V" and by_step[5]["auto"] is False
        assert by_step[5]["display"] == "0.000"
        assert by_step[6]["range"] == "1000 V"
        assert by_step[7]["auto"] is True
        assert by_step[9]["function"] == "frequency" and by_step[9]["gate_10s"] is False
        assert by_step[10]["gate_10s"] is True
        assert by_step[11]["function"] == "dc_volts"

    def test_open_circuit_resistance_reads_ofl(self, check, meter, tmp_path):
        meter.set_value(math.inf)
        _, record = _run(check, tmp_path)
        assert record["steps"][7]["driver"]["overrange"] is True


class TestTheOperatorsAnswers:
    def test_answers_are_recorded_and_a_mismatch_fails_the_run(self, check, meter,
                                                               tmp_path, monkeypatch):
        # pylint: disable=unused-argument
        answers = iter(["y"] + [""] * 3 + ["only mV lit, no DC"] + [""] * 20)
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        log = tmp_path / "log.json"
        status = check["main"](["COM6", "--log", str(log)])
        record = json.loads(log.read_text(encoding="utf-8"))
        assert status == 1
        assert record["steps"][3]["panel"] == "only mV lit, no DC"
        assert record["steps"][0]["panel"] == "match"

    def test_q_stops_early_and_still_restores_the_meter(self, check, meter, tmp_path,
                                                        monkeypatch):
        answers = iter(["y", "", "q"])
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        log = tmp_path / "log.json"
        status = check["main"](["COM6", "--log", str(log)])
        record = json.loads(log.read_text(encoding="utf-8"))
        assert status == 0
        assert len(record["steps"]) == 2
        assert record["restored"]["function"] == "dc_volts"
        assert meter.remote is False


class TestTheMeterIsRestored:
    def test_after_a_completed_run(self, check, meter, tmp_path):
        _, record = _run(check, tmp_path)
        assert record["restored"]["function"] == "dc_volts"
        assert record["restored"]["auto"] is True
        assert meter.remote is False                  # handed back to the panel

    def test_a_failure_part_way_still_restores_the_meter(self, check, meter, tmp_path,
                                                         monkeypatch):
        def fail(*_args, **_kwargs):
            raise RuntimeError("the bench lost power")

        monkeypatch.setattr(Tti1604, "select_hertz", fail)
        with pytest.raises(RuntimeError):
            _run(check, tmp_path)
        assert meter.measurement_type == 2 and meter.ac is False
        assert meter.remote is False
