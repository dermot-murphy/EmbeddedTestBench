"""The pylint baseline gate in scripts/lint.py.

A finding is keyed by file and rule. pylint reports paths with the host's
separator and the baseline records forward slashes, so on Windows every
baselined finding used to count as new (#81).
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


def test_a_windows_path_keys_the_same_as_the_baseline():
    lint = load_lint()
    windows = {"path": "benchtools\\instruments\\s2lp\\s2lp.py", "symbol": "too-many-lines"}
    posix = {"path": "benchtools/instruments/s2lp/s2lp.py", "symbol": "too-many-lines"}
    assert lint.key_of(windows) == lint.key_of(posix)


def test_a_baselined_finding_reported_with_backslashes_is_not_new(capsys):
    lint = load_lint()
    message = {"path": "tests\\test_x.py", "symbol": "unused-argument", "line": 3,
               "message": "Unused argument"}
    counts = lint.tally([message])
    baseline = {("tests/test_x.py", "unused-argument"): 1}
    assert lint.report_new(counts, baseline, [message]) == 0
    assert capsys.readouterr().out == ""


def test_the_recorded_baseline_uses_forward_slashes():
    lint = load_lint()
    assert all("\\" not in path for path, _symbol in lint.load_baseline())
