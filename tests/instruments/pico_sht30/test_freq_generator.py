"""The frequency generator: its driver, simulator and command line.

Traces to: PICO-FR-085, PICO-FR-086, PICO-FR-087, SWE4-UT-PICOFGEN.
"""

from __future__ import annotations

import json

import pytest

from benchtools.instruments.pico_sht30 import (
    CommandRefusedError,
    PicoSht30,
    RdRefusedError,
    SimulatedPicoSht30,
)
from benchtools.instruments.pico_sht30.cli import main
from benchtools.instruments.pico_sht30.simulator import dac_actual_mhz, parse_milli, pwm_actual_mhz


class FakeClock:
    """A clock a test moves by hand."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture(name="sim")
def fixture_sim():
    simulator = SimulatedPicoSht30()
    simulator.clock = FakeClock()
    return simulator


def ask(sim, command):
    return sim.respond(command.encode("ascii")).decode("ascii").splitlines()


@pytest.fixture(name="generator")
def fixture_generator():
    with PicoSht30.connect("sim://") as instrument:
        yield instrument


# --- the simulator's command set -----------------------------------------
@pytest.mark.parametrize("command,reply", [
    ("rd freq", "ACK rd freq 1 = 1000.00"),
    ("rd duty", "ACK rd duty 1 = 50.00"),
    ("rd wave 2", "ACK rd wave 2 = square"),
    ("rd freq 9", "NAK rd freq 9 = Error"),
    ("rd name 1", "err 2 wrong number of arguments"),
    ("wr freq 5k", "ACK wr freq 1 = 5000.00"),
    ("wr freq 2 1.5k", "ACK wr freq 2 = 1500.00"),
    ("wr freq 20k", "NAK wr freq 1 = Error"),
    ("wr freq 9.999", "NAK wr freq 1 = Error"),
    ("wr freq 1k5", "NAK wr freq 1 = Error"),
    ("wr freq 1.2345", "NAK wr freq 1 = Error"),
    ("wr duty 5k", "NAK wr duty 1 = Error"),
    ("wr duty 25", "ACK wr duty 1 = 25.00"),
    ("wr duty 0.5", "NAK wr duty 1 = Error"),
    ("wr amp 100.001", "NAK wr amp 1 = Error"),
    ("wr ratio 0.2", "ACK wr ratio 1 = 0.20"),
    ("wr cycles 1.5", "NAK wr cycles 1 = Error"),
    ("wr wave sine", "ACK wr wave 1 = sine"),
    ("wr wave pulse", "NAK wr wave 1 = Error"),
    ("wr wave 3 sine", "NAK wr wave 3 = Error"),
    ("wr amp 3 50", "NAK wr amp 3 = Error"),
    ("wr freq 9 1000", "NAK wr freq 9 = Error"),
    ("wr bogus 1", "NAK wr bogus = Error"),
    ("wr freq", "err 2 wrong number of arguments"),
    ("routine freq", "err 2 wrong number of arguments"),
    ("routine freq results 1", "ACK routine freq results 1 = Not Started"),
    ("routine freq start 9", "NAK routine freq start 9 = Error"),
    ("routine freq stop", "NAK routine freq stop = Error"),
    ("routine temp start", "NAK routine temp start = Error"),
    ("routine all start", "NAK routine all start = Error"),
    ("routine all abort", "ACK routine all abort = Aborted"),
])
def test_commands(sim, command, reply):
    assert ask(sim, command) == [reply]


def test_start_with_no_channel_means_channel_1(sim):
    assert ask(sim, "routine freq start") == ["ACK routine freq start 1 = Running"]
    assert ask(sim, "routine freq results 1") == [
        "ACK routine freq results 1 = Running, square, 1000.00 Hz"]


def test_a_continuous_run_cannot_be_restarted(sim):
    ask(sim, "routine freq start 1")
    assert ask(sim, "routine freq start 1") == ["NAK routine freq start 1 = Error"]
    ask(sim, "routine freq abort 1")
    assert ask(sim, "routine freq start 1") == ["ACK routine freq start 1 = Running"]


def test_a_finite_run_restarts_with_new_settings(sim):
    ask(sim, "wr cycles 1 1000")
    ask(sim, "routine freq start 1")
    ask(sim, "wr freq 1 2000")
    assert ask(sim, "routine freq start 1") == ["ACK routine freq start 1 = Running"]
    assert ask(sim, "routine freq results 1")[0].endswith("2000.00 Hz")


def test_wr_does_not_change_a_running_channel(sim):
    ask(sim, "routine freq start 1")
    ask(sim, "wr freq 1 2000")
    assert ask(sim, "routine freq results 1")[0].endswith("1000.00 Hz")
    assert ask(sim, "rd freq 1") == ["ACK rd freq 1 = 2000.00"]


def test_a_finite_run_completes_on_time(sim):
    ask(sim, "wr wave 1 sine")
    ask(sim, "wr cycles 1 10")
    ask(sim, "routine freq start 1")
    sim.clock.now += 0.009
    assert "Running" in ask(sim, "routine freq results 1")[0]
    sim.clock.now += 0.002
    assert ask(sim, "routine freq results 1") == [
        "ACK routine freq results 1 = Complete, sine, 1000.00 Hz"]


def test_abort_leaves_complete_alone(sim):
    ask(sim, "wr cycles 1 1")
    ask(sim, "routine freq start 1")
    sim.clock.now += 1.0
    ask(sim, "routine all abort")
    assert "Complete" in ask(sim, "routine freq results 1")[0]


def test_abort_does_not_touch_a_channel_that_never_ran(sim):
    ask(sim, "routine freq abort 2")
    assert ask(sim, "routine freq results 2") == ["ACK routine freq results 2 = Not Started"]


def test_results_for_every_channel(sim):
    ask(sim, "routine freq start 2")
    assert ask(sim, "routine freq results") == [
        "ACK routine freq results 1 = Not Started",
        "ACK routine freq results 2 = Running, square, 1000.00 Hz",
        "ACK routine freq results 3 = Not Started",
    ]


def test_the_arithmetic_matches_the_firmware_vectors():
    assert parse_milli("20k", True) == 20000000
    assert parse_milli("1.5k", True) == 1500000
    assert parse_milli("20k", False) is None
    assert parse_milli(".", False) is None
    assert parse_milli("999.98", False) == 999980
    assert dac_actual_mhz(1000000) == 1000000
    assert pwm_actual_mhz(12000000) == 12000000
    assert abs(pwm_actual_mhz(10000) - 10000) <= 10


# --- the driver ----------------------------------------------------------
def test_wr_returns_the_stored_value(generator):
    assert generator.wr("freq", 1500) == "1500.00"
    assert generator.wr("freq", "2.5k", channel=2) == "2500.00"
    assert generator.rd("freq", 2) == "2500.00"


def test_wr_a_fraction_keeps_its_places(generator):
    assert generator.wr("freq", 999.98) == "999.98"


def test_rd_a_setting_with_no_channel_means_channel_1(generator):
    generator.wr("duty", 30)
    assert generator.rd("duty") == "30.00"


def test_a_refused_wr_raises(generator):
    with pytest.raises(CommandRefusedError):
        generator.wr("freq", "20k")


def test_a_refused_rd_is_still_the_rd_error(generator):
    with pytest.raises(RdRefusedError):
        generator.rd("freq", 9)


def test_start_freq_writes_then_starts(generator):
    generator.start_freq(1, 2000, wave="sine", amp=50)
    status = generator.freq_status(1)
    assert (status.status, status.wave, status.frequency) == ("Running", "sine", 2000.0)
    assert generator.rd("amp", 1) == "50.00"
    assert generator.rd("cycles", 1) == "0"


def test_start_freq_sine2(generator):
    generator.start_freq(2, 50, wave="sine2", freq2=1000, ratio=0.2)
    assert generator.freq_status(2).wave == "sine2"
    assert generator.rd("freq2", 2) == "1000.00"


def test_start_freq_refused_on_a_continuous_run(generator):
    generator.start_freq(1, 1000)
    with pytest.raises(CommandRefusedError):
        generator.start_freq(1, 2000)


def test_status_of_a_channel_that_never_ran(generator):
    status = generator.freq_status(3)
    assert (status.status, status.wave, status.frequency) == ("Not Started", None, None)


def test_status_of_every_channel(generator):
    generator.start_freq(1, 1000)
    statuses = generator.freq_status()
    assert [item.channel for item in statuses] == [1, 2, 3]
    assert [item.status for item in statuses] == ["Running", "Not Started", "Not Started"]


def test_abort_one_channel(generator):
    generator.start_freq(1, 1000)
    generator.abort_freq(1)
    assert generator.freq_status(1).status == "Aborted"


def test_abort_every_channel(generator):
    generator.start_freq(1, 1000)
    generator.start_freq(3, 1000)
    generator.abort_freq()
    assert [item.status for item in generator.freq_status()] == [
        "Aborted", "Not Started", "Aborted"]


def test_abort_all(generator):
    generator.start_freq(2, 1000)
    generator.abort_all()
    assert generator.freq_status(2).status == "Aborted"


def test_status_as_dict(generator):
    generator.start_freq(1, 1000, wave="triangle")
    assert generator.freq_status(1).as_dict() == {
        "channel": 1, "status": "Running", "wave": "triangle", "frequency_hz": 1000.0}


# --- the command line ----------------------------------------------------
def run(capsys, *argv):
    code = main(["-r", "sim://", *argv])
    return code, capsys.readouterr()


def test_cli_wr_with_no_channel(capsys):
    code, out = run(capsys, "wr", "freq", "5k")
    assert code == 0
    assert json.loads(out.out) == {"setting": "freq", "channel": 1, "value": "5000.00"}


def test_cli_wr_with_a_channel(capsys):
    code, out = run(capsys, "wr", "duty", "2", "25")
    assert code == 0
    assert json.loads(out.out) == {"setting": "duty", "channel": 2, "value": "25.00"}


def test_cli_wr_refused(capsys):
    code, out = run(capsys, "wr", "freq", "20k")
    assert code == 1
    assert "refused" in out.err


def test_cli_wr_takes_at_most_a_channel_and_a_value(capsys):
    code, out = run(capsys, "wr", "freq", "1", "2", "3")
    assert code == 1
    assert "[channel] value" in out.err


def test_cli_rd_a_setting(capsys):
    code, out = run(capsys, "rd", "duty")
    assert code == 0
    assert json.loads(out.out) == {"option": "duty", "value": "50.00"}


def test_cli_rd_a_setting_on_a_channel(capsys):
    code, out = run(capsys, "rd", "freq", "2")
    assert code == 0
    assert json.loads(out.out) == {"option": "freq", "channel": 2, "value": "1000.00"}


def test_cli_routine_start(capsys):
    code, out = run(capsys, "routine", "freq", "start")
    assert code == 0
    assert json.loads(out.out) == {"channel": 1, "status": "Running"}


def test_cli_routine_results_every_channel(capsys):
    code, out = run(capsys, "routine", "freq", "results")
    assert code == 0
    assert len(json.loads(out.out)["channels"]) == 3


def test_cli_routine_results_one_channel(capsys):
    code, out = run(capsys, "routine", "freq", "results", "3")
    assert code == 0
    assert json.loads(out.out)["status"] == "Not Started"


def test_cli_routine_abort(capsys):
    code, out = run(capsys, "routine", "freq", "abort", "1")
    assert code == 0
    assert json.loads(out.out) == {"channel": 1, "status": "Aborted"}


def test_cli_routine_all_abort(capsys):
    code, out = run(capsys, "routine", "all", "abort")
    assert code == 0
    assert json.loads(out.out) == {"status": "Aborted"}


def test_cli_routine_all_start_is_refused(capsys):
    code, out = run(capsys, "routine", "all", "start")
    assert code == 1
    assert "routine all abort" in out.err
