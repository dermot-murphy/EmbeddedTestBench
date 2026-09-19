"""End-to-end tests of the command-line interface against the simulator.

Traces to: SWE1-FR-100, SWE4-UT-CLI.
"""

from __future__ import annotations

import json

import pytest

from benchtools.instruments.tek3014b.cli import main


def run(capsys, *argv):
    """Run the CLI and return ``(exit_status, parsed_json)``."""
    status = main(list(argv))
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else None
    return status, payload


#: Positions that keep a 3.3 V trace at 1 V/div inside the digitiser range.
_POSITIONS = (-4.0, -3.0, -2.0, -1.0)


def setup_for(channel_count: int):
    """Return CLI setup arguments sized for *channel_count* channels."""
    positions = ",".join("%g" % value for value in _POSITIONS[:channel_count])
    return (
        "--vdiv", "1.0",
        "--position=" + positions,
        "--tdiv", "200e-9",
        "--trigger-source", "1",
        "--trigger-level", "1.65",
    )


SETUP = setup_for(4)


class TestIdentify:
    def test_idn_reports_the_instrument(self, capsys):
        status, payload = run(capsys, "-r", "sim://", "idn")
        assert status == 0
        assert "TDS 3014B" in payload["identity"]
        # The description comes from the instrument's own *IDN? model field, so it
        # works for any simulated instrument rather than being hardcoded.
        assert payload["transport"] == "simulated TDS 3014B"

    def test_json_is_also_written_to_a_file(self, capsys, tmp_path):
        target = tmp_path / "idn.json"
        status, _ = run(capsys, "-r", "sim://", "--json", str(target), "idn")
        assert status == 0
        assert "TDS 3014B" in json.loads(target.read_text())["identity"]


class TestSpread:
    def test_spread_reports_the_simulated_skews(self, capsys):
        status, payload = run(capsys, "-r", "sim://", "spread", "-c", "1,2,3,4", *SETUP)
        assert status == 0
        # Simulator defaults: 0, 4, 9 and 1 ns.
        assert payload["spread_ns"] == pytest.approx(9.0, abs=0.05)
        assert payload["earliest_channel"] == 1
        assert payload["latest_channel"] == 3

    def test_spread_writes_csv_and_plot(self, capsys, tmp_path):
        # --plot needs the optional 'plot' extra; CSV export does not.
        pytest.importorskip("matplotlib", reason="matplotlib is an optional extra")
        csv_path = tmp_path / "spread.csv"
        plot_path = tmp_path / "spread.png"
        status, payload = run(
            capsys, "-r", "sim://", "spread", "-c", "1,2,3,4", *SETUP,
            "--csv", str(csv_path), "--plot", str(plot_path),
        )
        assert status == 0
        assert csv_path.exists() and plot_path.exists()
        assert plot_path.read_bytes().startswith(b"\x89PNG")
        assert payload["csv"] == str(csv_path)

    def test_absolute_threshold_is_accepted(self, capsys):
        status, payload = run(
            capsys, "-r", "sim://", "spread", "-c", "1,2", *setup_for(2), "--threshold", "1.0"
        )
        assert status == 0
        assert payload["spread_s"] > 0

    def test_falling_edge_direction(self, capsys):
        status, payload = run(
            capsys, "-r", "sim://", "spread", "-c", "1,2,3,4", *SETUP, "--direction", "FALL"
        )
        assert status == 0
        assert payload["direction"] == "FALL"

    def test_reference_channel_is_honoured(self, capsys):
        status, payload = run(
            capsys, "-r", "sim://", "spread", "-c", "1,2,3,4", *SETUP, "--reference", "3"
        )
        assert status == 0
        assert payload["reference_channel"] == 3
        assert payload["skews_s"]["3"] == 0.0

    def test_one_channel_is_rejected(self, capsys):
        status, _ = run(capsys, "-r", "sim://", "spread", "-c", "1", *setup_for(1))
        assert status == 2


class TestCaptureAndMeasure:
    def test_capture_summarises_each_channel(self, capsys, tmp_path):
        status, payload = run(
            capsys, "-r", "sim://", "capture", "-c", "1,2", *setup_for(2),
            "--csv", str(tmp_path / "c.csv"),
        )
        assert status == 0
        assert payload["points"] == 10000
        assert payload["channels"]["1"]["clipped_samples"] == 0
        assert payload["channels"]["1"]["peak_to_peak_v"] == pytest.approx(2.0, abs=0.1)

    def test_capture_reports_clipping(self, capsys):
        """A position that drives the trace off screen must be flagged."""
        status, payload = run(
            capsys, "-r", "sim://", "capture", "-c", "1",
            "--vdiv", "0.1", "--position", "4.0", "--tdiv", "200e-9",
            "--trigger-source", "1", "--trigger-level", "1.0",
        )
        assert status == 0
        assert payload["channels"]["1"]["clipped_samples"] > 0

    def test_period_reports_statistics(self, capsys):
        status, payload = run(capsys, "-r", "sim://", "period", "-c", "1",
                              "--vdiv", "1.0", "--position=-2", "--tdiv", "1e-6",
                              "--trigger-source", "1", "--trigger-level", "1.0")
        assert status == 0
        assert payload["mean_ns"] == pytest.approx(1000.0, rel=1e-3)
        assert payload["instrument_period_s"] == pytest.approx(1.0e-6)

    def test_measure_summary(self, capsys):
        status, payload = run(capsys, "-r", "sim://", "measure", "-c", "1", "--vdiv", "1.0")
        assert status == 0
        assert payload["measurements"]["frequency"] == pytest.approx(1.0e6)

    def test_measure_single_type(self, capsys):
        status, payload = run(capsys, "-r", "sim://", "measure", "-c", "1",
                              "--vdiv", "1.0", "--type", "PERIOD")
        assert status == 0
        assert payload["value"] == pytest.approx(1.0e-6)
        assert payload["units"] == "s"

    def test_screenshot(self, capsys, tmp_path):
        target = tmp_path / "screen.png"
        status, payload = run(capsys, "-r", "sim://", "screenshot", str(target))
        assert status == 0
        assert target.read_bytes().startswith(b"\x89PNG")


class TestArgumentHandling:
    def test_per_channel_values_are_expanded(self, capsys):
        status, _ = run(capsys, "-r", "sim://", "capture", "-c", "1,2,3,4",
                        "--vdiv", "1.0,2.0,0.5,0.2", "--position=-4,-3,-2,-1",
                        "--tdiv", "200e-9", "--trigger-source", "1", "--trigger-level", "1.0")
        assert status == 0

    def test_wrong_number_of_values_is_rejected(self, capsys):
        status, _ = run(capsys, "-r", "sim://", "capture", "-c", "1,2,3",
                        "--vdiv", "1.0,2.0")
        assert status == 2

    def test_non_numeric_value_is_rejected(self, capsys):
        status, _ = run(capsys, "-r", "sim://", "capture", "-c", "1", "--vdiv", "loud")
        assert status == 2

    def test_out_of_range_setting_is_reported(self, capsys):
        status, _ = run(capsys, "-r", "sim://", "capture", "-c", "1", "--vdiv", "500")
        assert status == 1

    def test_unreachable_instrument_is_reported(self, capsys):
        status, _ = run(capsys, "-r", "vxi11://127.0.0.1", "-t", "0.5", "idn")
        assert status == 1

    def test_bad_channel_list_is_rejected(self):
        with pytest.raises(SystemExit):
            main(["-r", "sim://", "capture", "-c", "one"])
