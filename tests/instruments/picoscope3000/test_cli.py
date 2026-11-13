"""``benchtools pscope`` against the simulator.

Traces to: PSCOPE-FR-030, SWE4-UT-PSCOPECLI.
"""

from __future__ import annotations

import json

from benchtools.cli import main as top_level_main
from benchtools.instruments.picoscope3000.cli import main


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def test_info(capsys):
    assert main(["info"]) == 0
    assert _json(capsys)["unit"]["variant"] == "3405DMSO"


def test_capture_analog_and_digital(capsys, tmp_path):
    csv_path = tmp_path / "block.csv"
    status = main(["capture", "-c", "A", "B", "--range", "5", "--digital", "0",
                   "--interval", "1e-6", "--samples", "2000", "--trigger", "A",
                   "--csv", str(csv_path)])
    result = _json(capsys)
    assert status == 0
    assert sorted(result["channels"]) == ["A", "B"]
    assert result["channels"]["A"]["peak_to_peak_v"] > 1.9
    assert result["digital"]["D0"]["edges"] >= 3
    assert csv_path.exists()


def test_digital_trigger(capsys):
    assert main(["capture", "--digital", "0", "--digital-trigger", "D1:RISE",
                 "--samples", "500"]) == 0
    assert "D1" in _json(capsys)["digital"]


def test_siggen_on_and_off(capsys):
    assert main(["siggen", "--wave", "SQUARE", "--frequency", "500", "--vpp", "1"]) == 0
    assert _json(capsys)["signal_generator"]["wave"] == "SQUARE"
    assert main(["siggen", "--off"]) == 0


def test_errors_are_reported_not_raised(capsys):
    assert main(["siggen", "--vpp", "5"]) == 1
    assert "generator" in capsys.readouterr().err
    assert main(["-r", "10.0.0.1", "info"]) == 1
    assert main(["capture", "--digital-trigger", "x:RISE", "--digital", "0"]) == 2


def test_top_level_command(capsys):
    assert top_level_main(["pscope", "info"]) == 0
    assert "3405DMSO" in capsys.readouterr().out
