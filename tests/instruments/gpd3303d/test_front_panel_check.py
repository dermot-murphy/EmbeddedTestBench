"""The GPD-3303D front-panel check, ``examples/10_psu_front_panel_check.py``.

Run against the simulator: every step is taken, the log records what the
driver read at each one, and the supply is left as it was found - output off,
original settings back - whether the run completes, is stopped, or fails.

Traces to: PSU-FR-030, PSU-FR-040, PSU-FR-043, SWE4-UT-PSUPANEL.
"""

from __future__ import annotations

import json
import pathlib
import runpy

import pytest

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.gpd3303d import Gpd3303D, SimulatedGpd

SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "examples" / "10_psu_front_panel_check.py"


@pytest.fixture(name="check")
def fixture_check():
    """The script's namespace, loaded without running it."""
    return runpy.run_path(str(SCRIPT), run_name="front_panel_check")


@pytest.fixture(name="supply")
def fixture_supply(monkeypatch):
    """One simulated supply, handed to the script in place of a connection."""
    simulator = SimulatedGpd()
    simulator.channels[1].voltage_setpoint = 5.0
    simulator.channels[1].current_limit = 0.2
    simulator.channels[2].voltage_setpoint = 3.3
    simulator.channels[2].current_limit = 0.1

    def connect(_resource, **_kwargs):
        instrument = Gpd3303D(MockTransport(responder=simulator), command_interval=0.0)
        instrument.initialise()
        return instrument

    monkeypatch.setattr(Gpd3303D, "connect", staticmethod(connect))
    return simulator


def _run(check, tmp_path, *extra):
    log = tmp_path / "log.json"
    status = check["main"](["COM11", "--hold", "0", "--log", str(log), *extra])
    return status, json.loads(log.read_text(encoding="utf-8"))


class TestAFullRun:
    def test_every_step_is_taken_and_logged(self, check, supply, tmp_path):
        status, record = _run(check, tmp_path)
        assert status == 0
        assert [step["step"] for step in record["steps"]] == list(range(1, 11))
        assert all(step["panel"].startswith("(not checked") for step in record["steps"])
        assert record["identity"].startswith("GW INSTEK,GPD-3303D")
        assert supply.command_log

    @pytest.mark.usefixtures("supply")
    def test_the_driver_reading_is_recorded_at_each_step(self, check, tmp_path):
        _, record = _run(check, tmp_path)
        by_step = {step["step"]: step["driver"] for step in record["steps"]}
        assert by_step[5]["output"] is True
        assert by_step[5]["channels"]["CH1"]["out_V"] == pytest.approx(3.3)
        assert by_step[6]["channels"]["CH1"]["mode"] == "parked at 0 V"
        assert by_step[6]["channels"]["CH2"]["out_V"] == pytest.approx(12.0)
        assert by_step[10]["channels"]["CH1"]["set_V"] == 0.0
        assert by_step[10]["channels"]["CH1"]["limit_A"] == pytest.approx(0.5)


class TestTheSupplyIsRestored:
    def test_after_a_completed_run(self, check, supply, tmp_path):
        _, record = _run(check, tmp_path)
        assert supply.output is False
        assert supply.channels[1].voltage_setpoint == pytest.approx(5.0)
        assert supply.channels[1].current_limit == pytest.approx(0.2)
        assert supply.channels[2].voltage_setpoint == pytest.approx(3.3)
        assert supply.channels[2].current_limit == pytest.approx(0.1)
        assert record["restored"]["output"] is False

    def test_a_failure_part_way_still_restores_the_supply(self, check, supply, tmp_path,
                                                         monkeypatch):
        def fail(*_args, **_kwargs):
            raise RuntimeError("the bench lost power")

        monkeypatch.setattr(Gpd3303D, "output_off", fail)
        with pytest.raises(RuntimeError):
            _run(check, tmp_path)
        assert supply.output is False
        assert supply.channels[1].voltage_setpoint == pytest.approx(5.0)
        assert supply.channels[2].current_limit == pytest.approx(0.1)
