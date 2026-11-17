"""``benchtools ppk2`` against the simulator, and the example specification.

Traces to: PPK-FR-011, PPK-FR-012, SWE4-UT-PPKCLI.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.ppk2 import cli
from benchtools.instruments.ppk2.cli import main

ROOT = pathlib.Path(__file__).resolve().parents[3]


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def test_info(capsys):
    assert main(["info"]) == 0
    result = _json(capsys)
    assert result["info"]["mode"] == "source"
    assert result["metadata"]["vdd"] == 3300


def test_measure_with_pulses_and_a_csv(capsys, tmp_path):
    path = tmp_path / "run.csv"
    assert main(["measure", "--duration", "0.01", "--threshold", "0.001", "--csv",
                 str(path)]) == 0
    result = _json(capsys)
    assert result["samples"] == 1000
    assert "pulses" not in result["pulses"]
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "time_s,current_a,logic" and len(lines) == 1001


def test_measure_lists_the_pulses_when_asked(capsys):
    assert main(["measure", "--duration", "0.01", "--line", "0", "--pulses"]) == 0
    assert _json(capsys)["pulses"]["pulses"] == []


@pytest.mark.parametrize("argv, key, value", [
    (["mode", "ammeter"], "mode", "ammeter"),
    (["--voltage-limit", "3.3", "voltage", "3.0"], "volts", 3.0),
    (["--voltage-limit", "3.3", "power", "on"], "powered", True),
    (["power", "off"], "powered", False),
])
def test_settings(capsys, argv, key, value):
    assert main(argv) == 0
    assert _json(capsys)[key] == value


def test_errors_exit_1(capsys):
    assert main(["--voltage-limit", "3.3", "voltage", "4.0"]) == 1
    assert "voltage limit" in capsys.readouterr().err
    assert main(["-r", "nowhere://x", "info"]) == 1


@pytest.mark.parametrize("argv", [["voltage", "3.0"], ["power", "on"]])
def test_supplying_needs_a_voltage_limit(capsys, argv):
    # The command line reads no bench file, and the kit may be left at 4 V.
    assert main(argv) == 2
    assert "--voltage-limit" in capsys.readouterr().err


def test_list(capsys, monkeypatch):
    monkeypatch.setattr(cli, "find_ppk2_ports", lambda: [{"port": "COM5"}])
    assert main(["list"]) == 0
    assert _json(capsys) == [{"port": "COM5"}]


def test_dispatch_from_the_top_level_command(capsys):
    assert top_level_main(["ppk2", "info"]) == 0
    assert _json(capsys)["info"]["model"] == "Power Profiler Kit II"


def test_the_example_specification_passes_on_the_simulated_bench():
    pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")
    # pylint: disable=import-outside-toplevel
    from benchtools.runner.bench import Bench, load_bench
    from benchtools.runner.results import Status
    from benchtools.runner.runner import BenchRunner
    from benchtools.runner.spec import load_spec

    bench = Bench(load_bench(str(ROOT / "benches" / "simulated_bench.yaml")))
    try:
        record = BenchRunner(bench).run(load_spec(str(ROOT / "specs" / "ppk2.yaml")))
        kit = bench.get("ppk")
        assert kit.powered is False
    finally:
        bench.close()
    assert [case.status for case in record.cases] == [Status.PASS] * 3
