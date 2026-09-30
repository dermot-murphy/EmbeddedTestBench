"""``benchtools thermo`` against the simulator.

Traces to: PICO-FR-060, SWE4-UT-PICOCLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.pico_sht30.cli import main


def _run(capsys, *argv):
    status = main(list(argv))
    return status, capsys.readouterr()


def test_ver(capsys):
    status, out = _run(capsys, "-r", "sim://", "ver")
    assert status == 0
    payload = json.loads(out.out)
    assert payload["title"] == "Pico2-SHT30-Thermometer"
    assert payload["version"] == "1.0.0"


def test_temp(capsys):
    status, out = _run(capsys, "-r", "sim://", "temp")
    assert status == 0
    assert json.loads(out.out)["temperature_c"] == pytest.approx(22.5, abs=0.003)


def test_temp_series(capsys):
    status, out = _run(capsys, "temp", "--count", "3", "--interval", "0")
    assert status == 0
    assert len(json.loads(out.out)["readings"]) == 3


def test_count_must_be_positive():
    with pytest.raises(SystemExit):
        main(["temp", "--count", "0"])


def test_status(capsys):
    status, out = _run(capsys, "status")
    assert status == 0
    assert json.loads(out.out)["reset_detected"] is True


def test_sreset_and_bootsel(capsys):
    assert _run(capsys, "sreset")[0] == 0
    assert json.loads(_run(capsys, "bootsel")[1].out)["bootloader"] is True


def test_json_file(tmp_path):
    path = tmp_path / "ver.json"
    assert main(["--json", str(path), "ver"]) == 0
    assert json.loads(path.read_text())["title"] == "Pico2-SHT30-Thermometer"


def test_connection_failure_is_reported(capsys):
    status, out = _run(capsys, "-r", "serial:///dev/does-not-exist", "ver")
    assert status == 1
    assert "could not connect" in out.err


def test_reachable_from_the_top_level(capsys):
    assert top_level_main(["thermo", "ver"]) == 0
    assert "Pico2-SHT30-Thermometer" in capsys.readouterr().out
