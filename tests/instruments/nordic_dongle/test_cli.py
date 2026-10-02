"""The ``benchtools ble`` command line.

Traces to: BLE-FR-070, BLE-FR-071, SWE4-UT-BLECLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.cli import main as top_level_main
from benchtools.instruments.nordic_dongle import SimulatedDongle
from benchtools.instruments.nordic_dongle.cli import build_parser, main


def run(capsys, *argv):
    """Run the CLI and return ``(status, payload, stderr)``."""
    status = main(list(argv))
    captured = capsys.readouterr()
    payload = None
    text = captured.out.strip()
    # ``monitor`` prints event lines before its JSON summary, so the payload is
    # whatever follows the first brace rather than the whole of stdout.
    if "{" in text:
        payload = json.loads(text[text.index("{"):])
    return status, payload, captured.err


SIM = ("--resource", "sim://")


class TestSubcommands:
    def test_info(self, capsys):
        status, payload, _ = run(capsys, *SIM, "info")
        assert status == 0
        assert payload["manufacturer"] == "Nordic"
        assert payload["protocol"] == "1.4"
        assert payload["firmware"] == SimulatedDongle.DEFAULT_FIRMWARE_VERSION
        assert payload["built"] == SimulatedDongle.DEFAULT_FIRMWARE_BUILT

    def test_scan(self, capsys):
        status, payload, _ = run(capsys, *SIM, "scan", "--duration", "1")
        assert status == 0
        assert payload["count"] == 3
        assert payload["sensors"][0]["name"] == "SENS-0A1B2C"

    def test_scan_with_a_filter(self, capsys):
        _, payload, _ = run(capsys, *SIM, "scan", "--duration", "1", "--name", "SENS-0B2C3D")
        assert payload["count"] == 1

    def test_select(self, capsys):
        status, payload, _ = run(capsys, *SIM, "select", "SENS-0A1B2C", "--scan-seconds", "1")
        assert status == 0
        assert payload["address"] == "E4:1C:7B:02:9A:11"

    def test_profile(self, capsys):
        status, payload, _ = run(
            capsys, *SIM, "profile", "--select", "SENS-0A1B2C",
            "--duration", "2", "--interval", "0.1", "--scan-seconds", "1",
        )
        assert status == 0
        assert payload["count"] >= 19
        assert payload["mean_interval_ms"] == pytest.approx(105.0, abs=0.5)
        assert payload["missed_events"] == 0
        assert payload["is_complete"] is True
        assert "warning" not in payload

    def test_profile_can_include_every_event(self, capsys):
        _, payload, _ = run(
            capsys, *SIM, "profile", "--select", "SENS-0A1B2C",
            "--duration", "1", "--interval", "0.1", "--scan-seconds", "1", "--events",
        )
        assert len(payload["events"]) == payload["count"]
        assert payload["events"][0]["address"] == "E4:1C:7B:02:9A:11"

    def test_cmd_reports_the_reply_and_the_timing(self, capsys):
        status, payload, _ = run(
            capsys, *SIM, "cmd", "measure", "--select", "SENS-0A1B2C",
            "--repeat", "3", "--scan-seconds", "1",
        )
        assert status == 0
        assert payload["count"] == 3
        assert payload["milliseconds"] == pytest.approx(95.0)
        assert payload["responses"] == ["OK 1024"] * 3
        assert "warning" not in payload

    def test_cmd_warns_when_the_figure_is_not_resolvable(self, capsys):
        """12.5 ms on a 30 ms link is the link's floor, not the sensor's."""
        _, payload, _ = run(
            capsys, *SIM, "cmd", "version", "--select", "SENS-0A1B2C", "--scan-seconds", "1"
        )
        assert payload["trustworthy"] is False
        assert "connection interval" in payload["warning"]

    def test_monitor_streams_events(self, capsys):
        status, payload, _ = run(
            capsys, *SIM, "monitor", "--duration", "1", "--addr", "E4:1C:7B:02:9A:11"
        )
        assert status == 0
        assert payload["events"] >= 1

    def test_the_session_can_be_logged(self, capsys, tmp_path):
        path = tmp_path / "ble.log"
        run(capsys, *SIM, "--log", str(path), "scan", "--duration", "1")
        text = path.read_text()
        assert "> scan start" in text
        assert "session opened" in text

    def test_json_can_be_written_to_a_file(self, capsys, tmp_path):
        path = tmp_path / "result.json"
        run(capsys, *SIM, "--json", str(path), "info")
        assert json.loads(path.read_text())["model"] == "PCA10059"



class TestChoosingASensor:
    """``--select`` takes what an operator types; ``--addr`` is honoured (#124).

    The simulated dongle hears SENS-0A1B2C at -62 dBm and SENS-0B2C3D at -78.
    """

    A1B2C = "E4:1C:7B:02:9A:11"

    @pytest.mark.parametrize("target", [
        "E4:1C:7B:02:9A:11",        # an address
        "SENS-0A1B2C",              # the whole name
        "0A1B2C",                   # part of it
        "sens-0a1b2c",              # in another case
        "0a1b",                     # part of it, in another case
    ])
    def test_select_takes_an_address_a_name_or_part_of_one(self, capsys, target):
        status, payload, stderr = run(capsys, *SIM, "select", target, "--scan-seconds", "1")
        assert status == 0, stderr
        assert payload["address"] == self.A1B2C

    def test_the_strongest_of_several_matches_is_chosen(self, capsys):
        status, payload, _ = run(capsys, *SIM, "select", "SENS-", "--scan-seconds", "1")
        assert status == 0
        assert payload["address"] == self.A1B2C

    def test_a_name_in_the_right_case_needs_one_scan(self, capsys, tmp_path):
        log = tmp_path / "ble.log"
        run(capsys, *SIM, "--log", str(log), "select", "0A1B2C", "--scan-seconds", "1")
        assert log.read_text().count("> scan start") == 1

    def test_a_name_in_another_case_is_found_by_an_unfiltered_scan(self, capsys, tmp_path):
        # The firmware's name filter is case-sensitive, so the first scan hears
        # nothing; the second has no filter and the host matches ignoring case.
        log = tmp_path / "ble.log"
        status, _, _ = run(capsys, *SIM, "--log", str(log), "select", "0a1b2c",
                           "--scan-seconds", "1")
        assert status == 0
        assert log.read_text().count("> scan start") == 2

    def test_no_match_names_the_sensors_heard(self, capsys):
        status, _, stderr = run(capsys, *SIM, "select", "KAPPA", "--scan-seconds", "1")
        assert status == 1
        assert "SENS-0A1B2C" in stderr and "SENS-0B2C3D" in stderr

    @pytest.mark.parametrize("sub", [
        ("cmd", "measure"),
        ("profile", "--duration", "1"),
        ("monitor", "--duration", "1"),
    ], ids=lambda sub: sub[0])
    def test_every_subcommand_takes_part_of_a_name(self, capsys, sub):
        status, _, stderr = run(capsys, *SIM, *sub, "--select", "0a1b", "--scan-seconds", "1")
        assert status == 0, stderr

    def test_cmd_connects_to_the_address_it_is_given(self, capsys):
        status, payload, stderr = run(capsys, *SIM, "cmd", "measure", "--addr", self.A1B2C)
        assert status == 0, stderr
        assert payload["responses"] == ["OK 1024"]

    @pytest.mark.parametrize("sub", ["cmd", "profile", "monitor"])
    def test_addr_and_select_together_are_a_usage_error(self, capsys, sub):
        argv = [*SIM, sub] + (["measure"] if sub == "cmd" else [])
        with pytest.raises(SystemExit) as caught:
            main(argv + ["--addr", self.A1B2C, "--select", "0A1B2C"])
        assert caught.value.code == 2
        assert "not allowed with" in capsys.readouterr().err


class TestFailures:
    def test_an_unreachable_dongle_is_reported(self, capsys):
        status, _, stderr = run(capsys, "--resource", "serial://nonexistent-port-xyz", "info")
        assert status == 1
        assert "could not connect" in stderr

    def test_an_unknown_sensor_is_reported(self, capsys):
        status, _, stderr = run(capsys, *SIM, "select", "NOT-A-SENSOR", "--scan-seconds", "1")
        assert status == 1
        assert stderr.startswith("error:")

    def test_an_unknown_subcommand_is_a_usage_error(self):
        with pytest.raises(SystemExit) as caught:
            main(["--resource", "sim://", "fly"])
        assert caught.value.code == 2

    def test_no_subcommand_is_a_usage_error(self):
        with pytest.raises(SystemExit) as caught:
            main(["--resource", "sim://"])
        assert caught.value.code == 2


class TestFirmwareCommand:
    """``ble firmware``: is this dongle running the build under test?

    Traces to: BLE-FR-012 .. BLE-FR-014, BLE-FR-070.
    """

    def manifest(self, directory, version, built):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "firmware_manifest.json").write_text(json.dumps({
            "version": version, "built": built, "protocol": "1.4",
            "model": "PCA10059", "hex": "f.hex", "package": "f.zip",
        }))
        (directory / "f.zip").write_bytes(b"not really a zip")
        return str(directory)

    def test_a_matching_build_exits_clean(self, capsys, tmp_path):
        build = self.manifest(tmp_path / "b", SimulatedDongle.DEFAULT_FIRMWARE_VERSION,
                              SimulatedDongle.DEFAULT_FIRMWARE_BUILT)
        status, payload, _ = run(capsys, *SIM, "firmware", build)
        assert status == 0
        assert payload["matches"] is True
        assert payload["installed_version"] == SimulatedDongle.DEFAULT_FIRMWARE_VERSION

    def test_a_stale_dongle_fails_and_says_why(self, capsys, tmp_path):
        """Exit 1 so a build step stops rather than publishing the numbers."""
        build = self.manifest(tmp_path / "b", "2.0.0", "2026-11-01T00:00:00Z")
        status, payload, _ = run(capsys, *SIM, "firmware", build)
        assert status == 1
        assert payload["matches"] is False
        assert payload["is_older"] is True
        assert "--update" in payload["warning"]

    def test_with_no_build_it_just_reports_what_is_installed(self, capsys):
        status, payload, _ = run(capsys, *SIM, "firmware")
        assert status == 0
        assert payload["compared"] is False
        assert payload["installed_version"] == SimulatedDongle.DEFAULT_FIRMWARE_VERSION
        assert payload["protocol_compatible"] is True

    def test_the_build_can_come_from_the_global_option(self, capsys, tmp_path):
        build = self.manifest(tmp_path / "b", SimulatedDongle.DEFAULT_FIRMWARE_VERSION,
                              SimulatedDongle.DEFAULT_FIRMWARE_BUILT)
        status, payload, _ = run(capsys, *SIM, "--firmware", build, "firmware")
        assert status == 0 and payload["matches"] is True

    def test_updating_is_attempted_only_when_asked(self, capsys, tmp_path, monkeypatch):
        """--update is a write to the instrument; it must be explicit."""
        import benchtools.instruments.nordic_dongle.dongle as module

        attempts = []
        monkeypatch.setattr(module.NordicDongle, "update_firmware",
                            lambda self, *a, **k: attempts.append(a) or self.check_firmware())
        build = self.manifest(tmp_path / "b", "2.0.0", "2026-11-01T00:00:00Z")
        run(capsys, *SIM, "firmware", build)
        assert attempts == []
        run(capsys, *SIM, "firmware", build, "--update")
        assert len(attempts) == 1


class TestDispatch:
    @pytest.mark.parametrize("name", ["ble", "dongle", "nordic"])
    def test_the_top_level_command_dispatches(self, name, capsys):
        assert top_level_main([name, "--resource", "sim://", "info"]) == 0
        assert "Nordic" in capsys.readouterr().out

    def test_the_usage_lists_the_dongle(self, capsys):
        top_level_main([])
        assert "ble " in capsys.readouterr().out

    def test_the_parser_documents_every_subcommand(self):
        text = build_parser().format_help()
        for name in ("info", "scan", "select", "profile", "cmd", "monitor", "firmware"):
            assert name in text


class TestScript:
    """``benchtools ble script``: a document run on its own, for its exit status."""

    DOCUMENT = (
        "| Variable | Default |\n|---|---|\n| SENSOR_ID | |\n\n"
        "## Identity\n\n| Step | Command | Expected response |\n|---|---|---|\n"
        "| 1 | connect ${SENSOR_ID} | |\n| 2 | rd version | %s |\n"
    )

    def test_a_passing_document_exits_zero(self, capsys, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(self.DOCUMENT % "1.4.2")
        report = tmp_path / "report.md"
        status, payload, _ = run(capsys, *SIM, "script", str(source),
                                 "--var", "SENSOR_ID=sens-0a1b", "--report", str(report))
        assert status == 0
        assert payload["result"] == "PASS"
        assert payload["variables"] == {"SENSOR_ID": "sens-0a1b"}
        assert report.is_file()

    def test_a_failing_document_exits_one(self, capsys, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(self.DOCUMENT % "9.9.9")
        status, payload, _ = run(capsys, *SIM, "script", str(source),
                                 "--var", "SENSOR_ID=sens-0a1b")
        assert status == 1
        assert payload["result"] == "FAIL"

    def test_a_missing_sensor_is_an_error(self, capsys, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(self.DOCUMENT % "1.4.2")
        status, _, err = run(capsys, *SIM, "script", str(source))
        assert status == 1
        assert "--var SENSOR_ID=" in err

    def test_a_var_without_a_value_is_an_error(self, capsys, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(self.DOCUMENT % "1.4.2")
        status, _, err = run(capsys, *SIM, "script", str(source), "--var", "SENSOR_ID")
        assert status == 1
        assert "NAME=VALUE" in err


    def test_the_event_log_is_written_where_asked(self, capsys, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(TestScript.DOCUMENT % "1.4.2")
        events = tmp_path / "events.log"
        status, payload, _ = run(capsys, *SIM, "script", str(source),
                                 "--var", "SENSOR_ID=sens-0a1b", "--events", str(events))
        assert status == 0
        assert payload["events"] == str(events)
        kinds = [line.split("\t")[1] for line in events.read_text().splitlines()[1:]]
        assert kinds == ["CONNECT", "TX", "RX"]
