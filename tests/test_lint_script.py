"""The pylint gate in scripts/lint.py.

The gate fails on any finding: #379 cleared the baseline it used to compare
against, and removed it. pylint reports paths with the host's separator, and
the annotations are written with forward slashes whatever the platform (#81).

Traces to: SWE4-UT-LINT.
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_lint():
    spec = importlib.util.spec_from_file_location("lint_script", ROOT / "scripts" / "lint.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finding(path="tests\\test_x.py", symbol="unused-argument", line=3):
    return {"path": path, "symbol": symbol, "line": line, "message": "Unused argument"}


def test_a_windows_path_is_reported_with_forward_slashes(capsys):
    lint = load_lint()
    assert lint.report([finding(path="benchtools\\instruments\\s2lp\\s2lp.py")]) == 1
    out = capsys.readouterr().out
    assert "file=benchtools/instruments/s2lp/s2lp.py,line=3,title=unused-argument" in out
    assert "\\" not in out


def test_a_posix_path_is_reported_unchanged():
    lint = load_lint()
    assert lint.posix_path("benchtools/core/scpi.py") == "benchtools/core/scpi.py"


def test_no_findings_passes(monkeypatch, capsys):
    lint = load_lint()
    monkeypatch.setattr(lint, "collect", lambda: [])
    monkeypatch.setattr("sys.argv", ["lint.py"])
    assert lint.main() == 0
    assert capsys.readouterr().out == "pylint: 0 finding(s)\n"


def test_a_single_finding_fails(monkeypatch, capsys):
    lint = load_lint()
    monkeypatch.setattr(lint, "collect", lambda: [finding()])
    monkeypatch.setattr("sys.argv", ["lint.py"])
    assert lint.main() == 1
    out = capsys.readouterr().out
    assert "::error file=tests/test_x.py,line=3,title=unused-argument::" in out
    assert "::error::1 pylint finding(s)" in out


def test_there_is_no_baseline_to_hide_findings_in():
    lint = load_lint()
    assert not (ROOT / ".pylint-baseline.json").exists()
    assert not hasattr(lint, "load_baseline")
