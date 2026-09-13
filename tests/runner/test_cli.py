"""The ``benchtools run`` command line.

Traces to: RUN-FR-050 .. RUN-FR-053, SWE4-UT-RUNCLI.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from benchtools.cli import main as top_level_main
from benchtools.runner.cli import main

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = str(ROOT / "specs" / "clock_skew.yaml")
BENCH = str(ROOT / "benches" / "simulated.yaml")

# The shipped specifications are YAML, so this whole module needs the optional
# 'spec' extra. JSON specifications are covered in test_spec.py.
pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")


class TestRunCommand:
    def test_simulated_run_passes(self, capsys):
        assert main([SPEC, "--simulate"]) == 0
        assert "PASS" in capsys.readouterr().out

    def test_named_bench_file(self, capsys):
        assert main([SPEC, "--bench", BENCH]) == 0

    def test_no_bench_and_no_simulate_is_a_usage_error(self, capsys):
        assert main([SPEC]) == 2
        assert "no bench configuration" in capsys.readouterr().err

    def test_missing_spec_is_a_usage_error(self, capsys):
        assert main(["/nonexistent.yaml", "--simulate"]) == 2
        assert "no such specification file" in capsys.readouterr().err

    def test_failure_exits_nonzero(self, capsys, tmp_path):
        tight = tmp_path / "tight.yaml"
        tight.write_text(
            open(SPEC, encoding="utf-8").read().replace("max: 20.0", "max: 1.0")
        )
        assert main([str(tight), "--simulate"]) == 1
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "above the maximum" in out

    def test_reports_are_written(self, capsys, tmp_path):
        status = main([
            SPEC, "--simulate",
            "--json", str(tmp_path / "r.json"),
            "--markdown", str(tmp_path / "r.md"),
            "--junit", str(tmp_path / "r.xml"),
        ])
        assert status == 0
        assert json.loads((tmp_path / "r.json").read_text())["status"] == "PASS"
        assert (tmp_path / "r.md").read_text().startswith("# Bench test report")
        assert (tmp_path / "r.xml").read_text().startswith("<?xml")

    def test_several_specs_get_suffixed_reports(self, capsys, tmp_path):
        status = main([SPEC, SPEC, "--simulate", "--json", str(tmp_path / "r.json")])
        assert status == 0
        assert (tmp_path / "r_1.json").exists()
        assert (tmp_path / "r_2.json").exists()

    def test_verbose_is_accepted(self, capsys):
        assert main([SPEC, "--simulate", "-vv"]) == 0


class TestTopLevelDispatch:
    def test_usage_without_arguments(self, capsys):
        assert top_level_main([]) == 0
        assert "benchtools <command>" in capsys.readouterr().out

    def test_version(self, capsys):
        assert top_level_main(["--version"]) == 0
        assert "benchtools" in capsys.readouterr().out

    def test_unknown_command(self, capsys):
        assert top_level_main(["fly"]) == 2
        assert "unknown command" in capsys.readouterr().err

    def test_drivers_listing(self, capsys):
        assert top_level_main(["drivers"]) == 0
        assert "tek3014b" in capsys.readouterr().out

    def test_backends_listing(self, capsys):
        assert top_level_main(["backends"]) == 0
        assert "vxi11" in capsys.readouterr().out

    def test_scope_is_dispatched(self, capsys):
        assert top_level_main(["scope", "-r", "sim://", "idn"]) == 0
        assert "TDS 3014B" in capsys.readouterr().out

    def test_run_is_dispatched(self, capsys):
        assert top_level_main(["run", SPEC, "--simulate"]) == 0
