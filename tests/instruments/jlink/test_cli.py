"""The ``benchtools jlink`` command line.

Traces to: JLINK-FR-100, SWE4-UT-JLINKCLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.jlink.cli import main

BASE = ["-r", "sim://", "-e", "firmware.elf"]


def run(capsys, *arguments):
    """Run the CLI and return ``(status, payload, stderr)``.

    stderr is returned rather than left for the caller to fetch: ``readouterr``
    consumes the capture, so a later call in the test would see nothing.
    """
    status = main(BASE + list(arguments))
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else None
    return status, payload, captured.err


class TestSubcommands:
    def test_info(self, capsys):
        status, payload, _ = run(capsys, "info")
        assert status == 0
        assert payload["manufacturer"] == "SEGGER"
        assert payload["attached"] is True

    def test_flash(self, capsys):
        status, payload, _ = run(capsys, "flash")
        assert status == 0
        assert payload["bytes_written"] > 0
        assert payload["verify"]["matched"] is True

    def test_flash_without_verify(self, capsys):
        status, payload, _ = run(capsys, "flash", "--no-verify")
        assert status == 0 and "verify" not in payload

    def test_verify(self, capsys):
        status, payload, _ = run(capsys, "verify")
        assert status == 0 and payload["matched"] is True

    def test_reset(self, capsys):
        status, payload, _ = run(capsys, "reset")
        assert status == 0 and payload["halted"] is True

    def test_run_until(self, capsys):
        status, payload, _ = run(capsys, "run", "--until", "sensor.c:75")
        assert status == 0
        assert payload["function"] == "sensor_done"

    def test_read_memory_dumps(self, capsys):
        status, payload, _ = run(capsys, "read", "0x20000104", "4")
        assert status == 0
        assert payload["hex"] == "d2040000"
        assert payload["dump"][0].startswith("0x20000104")

    def test_write_reports_what_it_wrote(self, capsys):
        """Each invocation is a fresh connection, so a write cannot be read back
        by a second one - the simulated target goes with the process."""
        status, payload, _ = run(capsys, "write", "0x20000900", "deadbeef")
        assert status == 0
        assert payload["written"] == 4 and payload["address"] == "0x20000900"

    def test_variable(self, capsys):
        status, payload, _ = run(capsys, "var", "sensor_mv")
        assert status == 0
        assert payload["value"] == 1234
        assert payload["address"] == "0x20000104"

    def test_variable_set(self, capsys):
        status, payload, _ = run(capsys, "var", "sensor_count", "--set", "55")
        assert status == 0 and payload["value"] == 55

    def test_stack(self, capsys):
        run(capsys, "run", "--until", "sensor.c:75")
        status, payload, _ = run(capsys, "stack")
        assert status == 0
        assert payload["depth"] >= 1
        assert payload["backtrace"][0].startswith("#0")

    def test_timing(self, capsys):
        status, payload, _ = run(capsys, "time", "sensor.c:40", "sensor.c:75")
        assert status == 0
        assert payload["cycles"] == 64_000
        assert payload["microseconds"] == pytest.approx(1000.0)

    def test_timing_warns_when_the_method_cannot_resolve_it(self, capsys):
        status, payload, _ = run(
            capsys, "time", "sensor.c:40", "sensor.c:75", "--method", "HOST_CLOCK"
        )
        assert status == 0
        assert "warning" in payload

    def test_rtt_expect(self, capsys):
        status, payload, _ = run(
            capsys, "rtt", "--send", "version", "--expect", r"\d+\.\d+\.\d+", "--duration", "2"
        )
        assert status == 0
        assert payload["matched"] == "1.4.2"

    def test_rtt_log_file(self, capsys, tmp_path):
        path = tmp_path / "rtt.log"
        status, _, _ = run(
            capsys, "rtt", "--log", str(path), "--send", "status",
            "--expect", "ok", "--duration", "2",
        )
        assert status == 0 and path.exists()


class TestFailuresAndOutput:
    def test_json_is_written_to_a_file(self, capsys, tmp_path):
        target = tmp_path / "out.json"
        status, _, _ = run(capsys, "--json", str(target), "info")
        assert status == 0
        assert json.loads(target.read_text())["manufacturer"] == "SEGGER"

    def test_unknown_variable_exits_nonzero(self, capsys):
        status, _, err = run(capsys, "var", "no_such_symbol")
        assert status == 1
        assert "cannot read" in err

    def test_unreachable_probe_exits_nonzero(self, capsys):
        status = main(["-r", "jlink://127.0.0.1:1", "-t", "0.5", "info"])
        assert status == 1
        assert "could not connect" in capsys.readouterr().err

    def test_verify_failure_exits_nonzero(self, capsys, monkeypatch):
        from benchtools.instruments.jlink import probe as probe_module

        original = probe_module.SimulatedJLink

        def mismatching(*args, **kwargs):
            return original(*args, flash_matches=False, **kwargs)

        monkeypatch.setattr(probe_module, "SimulatedJLink", mismatching)
        status, payload, _ = run(capsys, "verify")
        assert status == 1 and payload["matched"] is False


class TestTopLevelDispatch:
    def test_jlink_is_dispatched(self, capsys):
        assert top_level_main(["jlink", "-r", "sim://", "-e", "firmware.elf", "info"]) == 0
        assert "SEGGER" in capsys.readouterr().out

    def test_jlink_is_listed_in_the_usage(self, capsys):
        top_level_main([])
        assert "jlink" in capsys.readouterr().out

    def test_driver_is_registered(self, capsys):
        top_level_main(["drivers"])
        assert "jlink" in capsys.readouterr().out
