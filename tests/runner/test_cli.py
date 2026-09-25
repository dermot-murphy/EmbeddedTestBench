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


class TestSafetyWarning:
    """A specification's warning, and the gate that stops it being skipped.

    The point of the gate is that the consequence of ignoring the warning is
    silent and physical: something still wired to the bench is damaged, and
    nothing in the report says so. A warning a script can step over by not
    reading it would not be a control at all.

    Traces to: RUN-FR-054 .. RUN-FR-057, SWE4-UT-RUNCLI.
    """

    SELF_CHECK = str(ROOT / "specs" / "bench_self_check.yaml")
    SIMULATED = str(ROOT / "benches" / "simulated_bench.yaml")

    @staticmethod
    def hardware_bench(tmp_path):
        """A bench that is not simulated, so the gate applies."""
        path = tmp_path / "hardware_bench.yaml"
        path.write_text(
            "name: Pretend hardware\n"
            "instruments:\n"
            "  psu:\n"
            "    driver: gpd3303d\n"
            "    resource: serial:///dev/ttyUSB99\n"
            "    timeout: 1.0\n"
        )
        return str(path)

    def test_the_warning_is_printed_before_anything_runs(self, capsys):
        main([self.SELF_CHECK, "--bench", self.SIMULATED])
        err = capsys.readouterr().err
        assert "DISCONNECT EVERYTHING" in err
        # On stderr, so a run whose stdout is piped to a file still puts the
        # warning in front of whoever is standing at the bench.
        assert "SAFETY WARNING" in err

    def test_a_simulated_run_is_not_gated(self, capsys):
        # Nothing is energised and CI has nobody to answer the question.
        assert main([self.SELF_CHECK, "--bench", self.SIMULATED]) == 0
        assert "PASS" in capsys.readouterr().out

    def test_hardware_without_a_terminal_refuses_to_start(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        status = main([self.SELF_CHECK, "--bench", self.hardware_bench(tmp_path)])
        err = capsys.readouterr().err
        assert status == 3
        assert "--acknowledge" in err
        # Nothing ran: no result line was printed for the specification.
        assert "Bench self-check:" not in capsys.readouterr().out

    def test_acknowledge_lets_an_unattended_hardware_run_proceed(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        status = main([self.SELF_CHECK, "--bench", self.hardware_bench(tmp_path), "--acknowledge"])
        # It gets past the gate and fails on the absent port, which is the
        # point: the gate is no longer what stopped it.
        assert status != 3
        assert "--acknowledge" not in capsys.readouterr().err

    def test_a_terminal_is_asked_and_yes_proceeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("sys.stderr.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
        assert main([self.SELF_CHECK, "--bench", self.hardware_bench(tmp_path)]) != 3

    @pytest.mark.parametrize("answer", ["no", "", "y", "YES please"])
    def test_anything_but_yes_stops_the_run(self, tmp_path, capsys, monkeypatch, answer):
        # Deliberately strict: "y" is not confirmation of a warning about
        # damaging hardware.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("sys.stderr.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt: answer)
        assert main([self.SELF_CHECK, "--bench", self.hardware_bench(tmp_path)]) == 3
        assert "nothing was energised" in capsys.readouterr().err

    def test_a_specification_with_no_warning_is_never_gated(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        # clock_skew.yaml carries no warning, so the hardware bench must not
        # stop it at the gate - it should fail on the instrument instead.
        assert main([SPEC, "--bench", self.hardware_bench(tmp_path)]) != 3


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
