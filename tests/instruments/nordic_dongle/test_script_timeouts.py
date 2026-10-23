"""Timeouts by command prefix in a command document (#60).

A document can declare a timeout for every command that starts with a prefix,
so a family of slow commands does not need the same value in every row. These
tests pin how a prefix matches, what wins over what, what is refused, and that
each result says which timeout applied and why.

Split from ``test_script.py``, which is at its 1000-line limit; the helpers are
shared.

Traces to: BLE-FR-119, SWE4-UT-BLESCRIPT.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.instruments.nordic_dongle import parse_script
from benchtools.instruments.nordic_dongle.script import PASS, SKIP
from benchtools.instruments.nordic_dongle.script_run import run_script

from . import test_script
from .test_script import document, linked, no_wait, timed

#: A dongle that never gets a reply. Taken from its class rather than imported
#: by name, so pytest does not collect that class's tests a second time here.
Silent = test_script.TestASensorThatDoesNotAnswer.Silent

PREFIXES = (
    "| Command prefix | Timeout (ms) |\n|---|---|\n"
    "| WR | 45000 |\n| ROUTINE | 45000 |\n| RD | 500 |\n| RD EOL | 5000 |\n\n"
)


def prefixed(body: str, table: str = PREFIXES, **arguments):
    """A document with a timeouts-by-prefix table, then one Timed test."""
    return parse_script(table + timed(body), **arguments)


def table_of(*rows: str) -> str:
    """A | Command prefix | Timeout (ms) | table of *rows*."""
    return "| Command prefix | Timeout (ms) |\n|---|---|\n" + "".join(rows) + "\n"


class TestReadingTheTable:
    """The | Command prefix | Timeout (ms) | table, and values given for the run."""

    def test_a_command_takes_its_prefix_timeout(self):
        step = prefixed("| 1 | wr ignore-duration 300 | /^ACK/ | | |\n").steps[0]
        assert step.timeout_s == pytest.approx(45.0)
        assert step.timeout_from == "prefix WR (document)"

    def test_the_prefix_ignores_case(self):
        step = prefixed("| 1 | Routine config start | | | |\n").steps[0]
        assert step.timeout_s == pytest.approx(45.0)

    def test_the_longest_matching_prefix_wins(self):
        steps = prefixed("| 1 | rd eol | /x/ | | |\n| 2 | rd version | 1.4.2 | | |\n").steps
        assert [step.timeout_s for step in steps] == [pytest.approx(5.0), pytest.approx(0.5)]
        assert steps[0].timeout_from == "prefix RD EOL (document)"

    def test_the_order_of_the_rows_does_not_decide(self):
        table = table_of("| RD EOL | 5000 |\n", "| RD | 500 |\n")
        assert prefixed("| 1 | rd eol | /x/ | | |\n", table).steps[0].timeout_s == \
            pytest.approx(5.0)

    def test_a_prefix_matches_only_the_start_of_the_command(self):
        step = prefixed("| 1 | log wr | | | |\n").steps[0]
        assert step.timeout_s is None and step.timeout_from == ""

    def test_the_steps_own_timeout_cell_still_wins(self):
        step = prefixed("| 1 | wr mode normal | /^ACK/ | 2000 | |\n").steps[0]
        assert step.timeout_s == pytest.approx(2.0)
        assert step.timeout_from == "Timeout cell"

    def test_it_applies_without_a_timeout_column(self):
        step = parse_script(PREFIXES + document("| 1 | rd version | 1.4.2 |\n")).steps[0]
        assert step.timeout_s == pytest.approx(0.5)

    def test_it_does_not_apply_to_connect_delay_or_disconnect(self):
        table = table_of("| connect | 5000 |\n", "| delay | 5000 |\n", "| disconnect | 5000 |\n")
        steps = parse_script(table + document(
            "| 1 | connect SENS | |\n| 2 | delay 10 | |\n| 3 | disconnect | |\n")).steps
        assert [step.timeout_s for step in steps] == [None, None, None]

    def test_a_timeout_can_be_a_variable_given_for_the_run(self):
        text = ("| Variable | Default |\n|---|---|\n| WR_TIMEOUT_MS | 45000 |\n\n"
                + table_of("| WR | ${WR_TIMEOUT_MS} |\n"))
        assert parse_script(text + timed("| 1 | wr x | | | |\n")).steps[0].timeout_s == \
            pytest.approx(45.0)
        script = parse_script(text + timed("| 1 | wr x | | | |\n"),
                              variables={"WR_TIMEOUT_MS": "30000"})
        assert script.steps[0].timeout_s == pytest.approx(30.0)

    def test_the_run_overrides_and_adds_to_the_table(self):
        script = prefixed("| 1 | wr x | | | |\n| 2 | measure | | | |\n",
                          timeouts={"wr": "20000", "MEASURE": 1500})
        assert [step.timeout_s for step in script.steps] == [pytest.approx(20.0),
                                                              pytest.approx(1.5)]
        assert script.steps[0].timeout_from == "prefix wr (--timeout)"
        assert [(item.prefix, item.origin) for item in script.timeouts] == [
            ("wr", "--timeout"), ("ROUTINE", "document"), ("RD", "document"),
            ("RD EOL", "document"), ("MEASURE", "--timeout")]

    def test_the_run_cannot_override_a_steps_own_cell(self):
        script = prefixed("| 1 | wr x | | 2000 | |\n", timeouts={"WR": "20000"})
        assert script.steps[0].timeout_s == pytest.approx(2.0)

    @pytest.mark.parametrize("table, message", [
        (table_of("| WR | 45000 |\n", "| wr | 500 |\n"), "given a timeout twice"),
        (table_of("|  | 45000 |\n"), "no command prefix"),
        (table_of("| WR | 61000 |\n"), "milliseconds from 100 to 60000"),
        (table_of("| WR | soon |\n"), "milliseconds from 100 to 60000"),
        (table_of("| WR | ${NOPE} |\n"), "not declared"),
        (table_of("| WR |\n"), "has 1 cell"),
        ("| Command prefix | Notes |\n|---|---|\n| WR | slow |\n\n", "needs a 'Timeout \\(ms\\)'"),
    ])
    def test_a_bad_table_is_refused_naming_the_line(self, table, message):
        with pytest.raises(ConfigurationError, match=message) as caught:
            prefixed("| 1 | wr x | | | |\n", table)
        assert "line" in str(caught.value)

    def test_a_table_after_the_first_step_is_refused(self):
        with pytest.raises(ConfigurationError, match="after the first step"):
            parse_script(timed("| 1 | wr x | | | |\n") + "\n" + PREFIXES)

    @pytest.mark.parametrize("timeouts, message", [
        ({"WR": "0"}, "--timeout WR=0: a timeout for a command prefix"),
        ({" ": "500"}, "command prefix is empty"),
    ])
    def test_a_bad_run_timeout_is_refused(self, timeouts, message):
        with pytest.raises(ConfigurationError, match=message):
            prefixed("| 1 | wr x | | | |\n", timeouts=timeouts)

class TestRunningWithIt:
    """The timeout reaches the dongle, and each result says which applied and why."""

    def test_the_prefix_timeout_reaches_the_dongle(self):
        instrument, simulator = linked()
        try:
            run_script(instrument, prefixed("| 1 | rd version | 1.4.2 | | |\n"), sleep=no_wait)
            assert simulator.last_command_timeout_ms == 500
        finally:
            instrument.close()

    def test_it_is_the_listening_window_for_a_command_expecting_nothing(self):
        run = run_script(Silent(),
                         prefixed("| 1 | wr x | | | |\n"), sleep=no_wait, listen=0.05)
        assert run.results[0].result == SKIP
        assert "no reply within 45.00 s" in run.results[0].reason
        assert run.results[0].timeout == "45000 ms, prefix WR (document)"

    def test_a_slow_command_passes_with_its_prefix_timeout(self):
        """The Kepler case (#60): a command slower than the run's default."""
        instrument, _ = linked(latency_overrides={"rd version": 4_000_000})
        try:
            run = run_script(instrument, prefixed("| 1 | rd version | 1.4.2 | | |\n",
                                                  table_of("| RD VERSION | 6000 |\n")),
                             timeout=2.0, sleep=no_wait)
            assert run.results[0].result == PASS
        finally:
            instrument.close()

    def test_each_result_says_which_timeout_applied_and_why(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, prefixed(
                "| 1 | rd version | 1.4.2 | | |\n| 2 | rd version | 1.4.2 | 1500 | |\n"
                "| 3 | temp | 23.5 | | |\n| 4 | delay 10 | | | |\n"), timeout=2.0, sleep=no_wait)
        finally:
            instrument.close()
        assert [item.timeout for item in run.results] == [
            "500 ms, prefix RD (document)", "1500 ms, Timeout cell",
            "2000 ms, run default (--timeout-s)", ""]
        assert run.results[0].as_dict()["timeout_ms"] == pytest.approx(500.0)
        assert run.results[0].as_dict()["timeout_from"] == "prefix RD (document)"
        assert run.as_dict()["timeouts"][0] == {"prefix": "WR", "timeout_ms": 45000.0,
                                                "from": "document"}
        text = run.markdown()
        assert ("| Timeouts by prefix | WR 45000 ms (document), ROUTINE 45000 ms (document), "
                "RD 500 ms (document), RD EOL 5000 ms (document) |") in text
        assert "| 500 ms, prefix RD (document) | PASS |" in text
        assert "\tTX\t" in run.events[1] and "prefix RD (document)" in run.events[1]

    def test_a_document_without_a_table_reports_none(self):
        run = run_script(Silent(),
                         parse_script(document("| 1 | log start | |\n")),
                         sleep=no_wait, listen=0.05)
        assert "| Timeouts by prefix | none |" in run.markdown()
        assert run.results[0].timeout == "50 ms, listening window (--listen)"

    def test_a_disconnect_waits_its_prefix_timeout(self):
        instrument, simulator = linked()
        simulator.sensors[0].disconnect_on = {"wr mode normal": 100_000}
        try:
            run = run_script(instrument, prefixed("| 1 | wr mode normal | <disconnect> | | |\n"),
                             sleep=no_wait)
        finally:
            instrument.close()
        assert run.results[0].result == PASS
        assert run.results[0].timeout == "45000 ms, prefix WR (document)"

    def test_the_driver_passes_run_timeouts_to_the_document(self, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(PREFIXES + timed("| 1 | rd version | 1.4.2 | | |\n"))
        instrument, simulator = linked()
        try:
            run = instrument.run_script(str(source), timeouts={"RD": "800"})
            assert simulator.last_command_timeout_ms == 800
        finally:
            instrument.close()
        assert run.results[0].timeout == "800 ms, prefix RD (--timeout)"

    def test_timeouts_cannot_be_given_for_a_parsed_document(self):
        instrument, _ = linked()
        try:
            with pytest.raises(ConfigurationError, match="already parsed"):
                instrument.run_script(prefixed("| 1 | rd version | 1.4.2 | | |\n"),
                                      timeouts={"RD": "800"})
        finally:
            instrument.close()
