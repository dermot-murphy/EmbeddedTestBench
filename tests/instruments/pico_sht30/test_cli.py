"""``benchtools thermo`` against the simulator.

Traces to: PICO-FR-060, PICO-FR-061, SWE4-UT-PICOCLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.pico_sht30.cli import main


def _run(capsys, *argv):
    status = main(list(argv))
    return status, capsys.readouterr()


def test_info(capsys):
    status, out = _run(capsys, "-r", "sim://", "info")
    assert status == 0
    payload = json.loads(out.out)
    assert payload["name"] == "Pico 2 SHT30 Temperature Sensor"
    assert payload["version"] == "V1.00.0000"
    assert payload["copyright"] == "(c) 2026 Dermot Murphy"
    assert len(payload["sha"]) == 7


@pytest.mark.parametrize("option", ["name", "copyright", "version", "sha", "temperature"])
def test_rd(capsys, option):
    status, out = _run(capsys, "rd", option)
    assert status == 0
    assert json.loads(out.out)["option"] == option


def test_rd_rejects_an_unknown_option():
    with pytest.raises(SystemExit):
        main(["rd", "colour"])


def test_ecureset(capsys):
    status, out = _run(capsys, "ecureset")
    assert status == 0
    assert json.loads(out.out) == {"rebooted": True}


def test_temp(capsys):
    status, out = _run(capsys, "-r", "sim://", "temp")
    assert status == 0
    assert json.loads(out.out)["text"] == "22.50"


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
    path = tmp_path / "info.json"
    assert main(["--json", str(path), "info"]) == 0
    assert json.loads(path.read_text())["name"] == "Pico 2 SHT30 Temperature Sensor"


def test_connection_failure_is_reported(capsys):
    status, out = _run(capsys, "-r", "serial:///dev/does-not-exist", "info")
    assert status == 1
    assert "could not connect" in out.err


def test_reachable_from_the_top_level(capsys):
    assert top_level_main(["thermo", "info"]) == 0
    assert "Pico 2 SHT30 Temperature Sensor" in capsys.readouterr().out
