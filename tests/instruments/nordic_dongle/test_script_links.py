"""Command documents against a link that drops, and replies that come more than once.

Split from ``test_script.py`` when it passed 1000 lines; the helpers are shared.

Traces to: BLE-FR-109, BLE-FR-115, SWE4-UT-BLESCRIPT.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import NordicDongle, SimulatedDongle, parse_script
from benchtools.instruments.nordic_dongle.script import ERROR, FAIL, PASS, SKIP
from benchtools.instruments.nordic_dongle.script_run import run_script

from .test_script import document, linked, no_wait


class TestALinkThatDrops:
    """A sensor that crashes mid-run is one event, not one error per step (#51)."""

    DOCUMENT = document(
        "| 1 | connect SENS-0A1B2C | |\n"
        "| 2 | rd eol start | |\n"
        "| 3 | delay 10 | |\n"
        "| 4 | rd version | 1.4.2 |\n"
        "| 5 | temp | 23.5 |\n"
        "| 6 | connect SENS-0A1B2C | |\n"
        "| 7 | rd version | 1.4.2 |\n")

    @staticmethod
    def crashing():
        simulator = SimulatedDongle()
        simulator.sensors[0].responses["rd eol start"] = "ACK RD EOL = RF Testing Started"
        simulator.sensors[0].crash_on = {"rd eol start": 34_000_000}
        instrument = NordicDongle(MockTransport(responder=simulator))
        instrument.initialise()
        return instrument

    def test_the_drop_is_logged_once_where_it_happened(self):
        instrument = self.crashing()
        try:
            run = run_script(instrument, parse_script(self.DOCUMENT), sleep=no_wait, scan_s=0.2)
        finally:
            instrument.close()
        drops = [line.split("\t") for line in run.events if "\tDISCONNECT\t" in line]
        assert len(drops) == 1
        # The simulator's clock does not move during a delay, so the crash is
        # found straight after the command that caused it.
        assert drops[0][2] == "A test/2" and drops[0][4] == "ERROR"
        assert "reason 0x08" in drops[0][3] and "supervision timeout" in drops[0][3]
        assert "dongle time" in drops[0][3]

    def test_the_steps_after_it_are_not_sent_and_say_why(self):
        instrument = self.crashing()
        try:
            run = run_script(instrument, parse_script(self.DOCUMENT), sleep=no_wait, scan_s=0.2)
        finally:
            instrument.close()
        results = [item.result for item in run.results]
        assert results == [SKIP, SKIP, SKIP, ERROR, ERROR, SKIP, PASS]
        assert run.results[3].reason.startswith("not sent: link lost during or after A test/2")
        tx = [line.split("\t")[2] for line in run.events if "\tTX\t" in line]
        assert "A test/4" not in tx and "A test/5" not in tx

    def test_a_connect_recovers_and_the_run_goes_on(self):
        instrument = self.crashing()
        try:
            run = run_script(instrument, parse_script(self.DOCUMENT), sleep=no_wait, scan_s=0.2)
        finally:
            instrument.close()
        assert run.results[-1].result == PASS
        assert run.result == ERROR and run.errors == 2


def framed(body: str) -> str:
    """One test whose table has a Frames column."""
    return ("## Framed\n\n| Step | Command | Expected response | Frames |\n|---|---|---|---|\n"
            + body)


class TestCountingReplyFrames:
    """A sensor that answers twice leaves every later command a reply behind (#53)."""

    def test_one_frame_passes(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(framed("| 1 | rd version | 1.4.2 | 1 |\n")),
                             sleep=no_wait)
        finally:
            instrument.close()
        assert run.results[0].result == PASS

    def test_a_second_frame_fails_and_says_what_it_was(self):
        instrument, _ = linked(extra_frames={"rd version": ("1.4.2",)})
        try:
            run = run_script(instrument, parse_script(framed("| 1 | rd version | 1.4.2 | 1 |\n")),
                             sleep=no_wait)
        finally:
            instrument.close()
        result = run.results[0]
        assert result.result == FAIL
        assert "2 reply frame(s), expected 1: then 1.4.2" in result.reason
        rx = [line.split("\t") for line in run.events if "\tRX\t" in line]
        assert [row[3] for row in rx][1] == "frame 2: 1.4.2"

    def test_a_frame_count_is_a_claim_even_with_no_expected_response(self):
        script = parse_script(framed("| 1 | rd version | | 1 |\n"))
        assert script.checks == 1
        instrument, _ = linked()
        try:
            run = run_script(instrument, script, sleep=no_wait)
        finally:
            instrument.close()
        assert run.results[0].result == PASS

    def test_a_right_count_with_a_wrong_reply_still_fails(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(framed("| 1 | rd version | 9.9.9 | 1 |\n")),
                             sleep=no_wait)
        finally:
            instrument.close()
        assert run.results[0].result == FAIL
        assert "does not match" in run.results[0].reason

    def test_a_frame_count_must_be_a_whole_number_from_one(self):
        with pytest.raises(ConfigurationError, match="whole number from 1"):
            parse_script(framed("| 1 | rd version | 1.4.2 | 0 |\n"))
        with pytest.raises(ConfigurationError, match="whole number from 1"):
            parse_script(framed("| 1 | rd version | 1.4.2 | one |\n"))

    def test_only_a_command_has_frames_to_count(self):
        with pytest.raises(ConfigurationError, match="only a command's reply frames"):
            parse_script(framed("| 1 | delay 10 | | 1 |\n"))
