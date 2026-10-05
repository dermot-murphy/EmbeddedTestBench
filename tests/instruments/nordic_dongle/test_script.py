"""Command and response tests read from the document that specifies them.

Two halves, and the second is the one that matters. Reading the document is
mechanical: these tests pin the shape it accepts and every shape it refuses,
because a row read wrongly is a command silently untested. Running it is a
claim about a sensor: a step that passes must have been checked, a step that
was skipped must not look like one that passed, and a run that says PASS must
mean no step failed.

Traces to: BLE-FR-100 .. BLE-FR-108, SWE4-UT-BLESCRIPT.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError, TransportTimeoutError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import (
    NordicDongle,
    SimulatedDongle,
    load_script,
    parse_script,
)
from benchtools.instruments.nordic_dongle.script import (
    ERROR,
    FAIL,
    PASS,
    RESOLUTION_S,
    SKIP,
)
from benchtools.instruments.nordic_dongle.script_run import CONNECT_ATTEMPTS, run_script

DOCUMENT = """# Sensor commands

Prose between the tables is ignored.

## Identity

| Step | Command    | Expected response |
|------|------------|-------------------|
| 1    | rd version | 1.4.2             |
| 2    | rd id      | /^SENS-[0-9A-F]{6}$/ |

## Readings

| Step | Command   | Expected response |
|------|-----------|-------------------|
| 1    | temp      | 23.5              |
| 2    | delay 250 |                   |
| 3    | log start |                   |
"""


def document(body: str) -> str:
    """A minimal document wrapping *body* as one test's table."""
    return "## A test\n\n| Step | Command | Expected response |\n|---|---|---|\n" + body


class TestReadingTheDocument:
    def test_a_heading_becomes_a_test(self):
        script = parse_script(DOCUMENT)
        assert [test.name for test in script.tests] == ["Identity", "Readings"]

    def test_the_document_title_is_not_a_test(self):
        """A single # is the document's own title; ## and below name tests."""
        assert "Sensor commands" not in [test.name for test in parse_script(DOCUMENT).tests]

    def test_steps_keep_their_number_and_their_test(self):
        step = parse_script(DOCUMENT).tests[0].steps[1]
        assert (step.test, step.number, step.command) == ("Identity", "2", "rd id")

    def test_a_delay_is_read_as_a_duration_not_a_command(self):
        step = parse_script(DOCUMENT).tests[1].steps[1]
        assert step.is_delay and step.delay_s == pytest.approx(0.25)
        assert step.command == ""

    @pytest.mark.parametrize("written", ["delay 250", "DELAY 250", "delay 250 ms", "delay 250ms"])
    def test_the_ways_a_delay_is_written(self, written):
        step = parse_script(document("| 1 | %s | |\n" % written)).steps[0]
        assert step.delay_s == pytest.approx(0.25)

    def test_a_command_with_no_expected_response_expects_nothing(self):
        step = parse_script(DOCUMENT).tests[1].steps[2]
        assert step.command == "log start"
        assert not step.expects_response and not step.is_delay

    def test_extra_columns_are_left_alone(self):
        """A document carries notes and requirement references; the reader
        takes the three columns it needs and ignores the rest."""
        script = parse_script(
            "## A test\n"
            "| Step | Command | Expected response | Notes |\n"
            "|---|---|---|---|\n"
            "| 1 | temp | 23.5 | degrees |\n"
        )
        assert script.steps[0].expected == "23.5"

    def test_the_columns_may_be_in_any_order(self):
        script = parse_script(
            "## A test\n"
            "| Expected response | Step | Command |\n"
            "|---|---|---|\n"
            "| 23.5 | 1 | temp |\n"
        )
        step = script.steps[0]
        assert (step.number, step.command, step.expected) == ("1", "temp", "23.5")

    def test_how_many_steps_actually_check_something(self):
        """A document of delays and fire-and-forget commands cannot fail, and a
        report saying PASS without saying that would mislead."""
        script = parse_script(DOCUMENT)
        assert len(script) == 5 and script.checks == 3

    def test_a_file_is_read_from_disk(self, tmp_path):
        path = tmp_path / "commands.md"
        path.write_text(DOCUMENT)
        assert load_script(str(path)).source == str(path)

    def test_a_file_that_is_not_there_says_so(self, tmp_path):
        with pytest.raises(ConfigurationError, match="cannot read the command document"):
            load_script(str(tmp_path / "absent.md"))


class TestTheDocumentIsRefused:
    """Every one of these is a row that would otherwise be a command nobody
    tested and nobody missed."""

    def test_a_table_before_any_heading(self):
        with pytest.raises(ConfigurationError, match="before any test heading"):
            parse_script("| Step | Command | Expected response |\n|---|---|---|\n| 1 | temp | 1 |\n")

    def test_a_missing_column(self):
        with pytest.raises(ConfigurationError, match="expected"):
            parse_script("## A test\n| Step | Command |\n|---|---|\n| 1 | temp |\n")

    def test_a_row_with_the_wrong_number_of_cells(self):
        with pytest.raises(ConfigurationError, match="cell"):
            parse_script(document("| 1 | temp |\n"))

    def test_a_row_with_no_step_number(self):
        with pytest.raises(ConfigurationError, match="no step number"):
            parse_script(document("|  | temp | 23.5 |\n"))

    def test_the_same_step_number_twice_in_one_test(self):
        with pytest.raises(ConfigurationError, match="already used on line"):
            parse_script(document("| 1 | temp | 23.5 |\n| 1 | battery | 97 |\n"))

    def test_the_same_step_number_in_different_tests_is_fine(self):
        script = parse_script(
            "## One\n| Step | Command | Expected response |\n|---|---|---|\n| 1 | temp | 1 |\n"
            "\n## Two\n| Step | Command | Expected response |\n|---|---|---|\n| 1 | temp | 1 |\n"
        )
        assert len(script) == 2

    def test_a_row_with_no_command(self):
        with pytest.raises(ConfigurationError, match="no command"):
            parse_script(document("| 1 |  | 23.5 |\n"))

    def test_a_delay_that_expects_a_response(self):
        with pytest.raises(ConfigurationError, match="delay cannot have an expected"):
            parse_script(document("| 1 | delay 100 | 23.5 |\n"))

    @pytest.mark.parametrize("amount", ["0", "0.0"])
    def test_a_delay_of_nothing(self, amount):
        with pytest.raises(ConfigurationError, match="is not a wait"):
            parse_script(document("| 1 | delay %s | |\n" % amount))

    def test_a_document_with_no_tests(self):
        with pytest.raises(ConfigurationError, match="names no tests"):
            parse_script("# Just a title\n\nSome prose.\n")

    def test_the_diagnostic_names_the_document_and_the_line(self):
        with pytest.raises(ConfigurationError, match=r"commands\.md line 5"):
            parse_script(document("| 1 |  | 23.5 |\n"), source="commands.md")


class TestMatching:
    def make(self, expected: str):
        return parse_script(document("| 1 | temp | %s |\n" % expected)).steps[0]

    def test_exact(self):
        assert self.make("23.5").matches("23.5")

    def test_surrounding_space_does_not_decide_a_test(self):
        assert self.make("23.5").matches("  23.5 ")

    def test_a_different_reply_does_not_match(self):
        assert not self.make("23.5").matches("24.5")

    def test_a_longer_reply_does_not_match(self):
        """Exact means exact: 23.50 is not 23.5, and a rule that let it pass
        would let a truncated or padded reply pass too."""
        assert not self.make("23.5").matches("23.50")

    def test_a_pattern_when_it_is_marked_as_one(self):
        step = self.make(r"/^-?[0-9]+\.[0-9]$/")
        assert step.pattern is not None
        assert step.matches("23.5") and step.matches("-4.0")
        assert not step.matches("23.55")

    def test_a_slash_in_an_ordinary_response_is_not_a_pattern(self):
        step = self.make("OK 1/2")
        assert step.pattern is None and step.matches("OK 1/2")


class TestRunningIt:
    @pytest.fixture
    def dongle(self):
        instrument = NordicDongle(MockTransport(responder=SimulatedDongle()))
        instrument.initialise()
        instrument.scan(duration=0.2, name="0A1B2C")
        instrument.select("SENS-0A1B2C")
        instrument.open_link()
        yield instrument
        instrument.close()

    def run(self, dongle, body: str, **arguments):
        waited = []
        return run_script(
            dongle,
            parse_script(document(body)),
            sleep=waited.append,
            **arguments,
        ), waited

    def test_a_matching_reply_passes(self, dongle):
        run, _ = self.run(dongle, "| 1 | rd version | 1.4.2 |\n")
        assert run.results[0].result is PASS
        assert run.result == PASS and run.passed == 1

    def test_a_reply_that_does_not_match_fails_and_shows_both(self, dongle):
        run, _ = self.run(dongle, "| 1 | rd version | 9.9.9 |\n")
        step = run.results[0]
        assert step.result == FAIL
        assert step.response == "1.4.2" and step.expected == "9.9.9"
        assert run.result == FAIL

    def test_a_delay_waits_and_is_skipped(self, dongle):
        run, waited = self.run(dongle, "| 1 | delay 250 | |\n")
        assert waited == [pytest.approx(0.25)]
        assert run.results[0].result == SKIP
        assert run.results[0].elapsed_s == pytest.approx(0.25)

    def test_a_command_with_nothing_promised_is_skipped_but_recorded(self, dongle):
        """Knowing what the board said is useful even when nothing was
        promised: the next revision of the document can make a claim about it."""
        run, _ = self.run(dongle, "| 1 | temp | |\n")
        step = run.results[0]
        assert step.result == SKIP and step.response == "23.5"

    def test_a_skipped_step_does_not_make_a_run_pass_on_its_own(self, dongle):
        run, _ = self.run(dongle, "| 1 | delay 10 | |\n")
        assert run.result == PASS and run.passed == 0 and run.skipped == 1

    def test_one_failure_fails_the_run(self, dongle):
        run, _ = self.run(
            dongle,
            "| 1 | rd version | 1.4.2 |\n| 2 | temp | 0.0 |\n| 3 | battery | 97 |\n",
        )
        assert run.passed == 2 and run.failed == 1
        assert run.result == FAIL
        assert [item.number for item in run.failures] == ["2"]

    def test_the_steps_are_reported_in_document_order(self, dongle):
        run, _ = self.run(
            dongle, "| 1 | temp | 23.5 |\n| 2 | battery | 97 |\n| 3 | id | SENS-0A1B2C |\n"
        )
        assert [item.number for item in run.results] == ["1", "2", "3"]

    def test_the_time_is_the_dongle_clock_at_ten_millisecond_resolution(self, dongle):
        """`measure` takes 95 ms on this sensor. The dongle measures it in
        microseconds; the report quotes 10 ms, and keeps what was measured."""
        run, _ = self.run(dongle, "| 1 | measure | OK 1024 |\n")
        step = run.results[0]
        assert step.clock == "dongle"
        assert step.elapsed_s == pytest.approx(0.095)
        assert step.reported_s == pytest.approx(0.10)
        assert step.as_dict()["resolution_s"] == RESOLUTION_S

    def test_the_measured_time_is_kept_beside_the_quoted_one(self, dongle):
        run, _ = self.run(dongle, "| 1 | measure | OK 1024 |\n")
        record = run.results[0].as_dict()
        assert record["seconds"] == pytest.approx(0.10)
        assert record["measured_seconds"] == pytest.approx(0.095)

    def test_the_run_records_which_sensor_answered(self, dongle):
        run, _ = self.run(dongle, "| 1 | temp | 23.5 |\n")
        assert "SENS-0A1B2C" in run.sensor

    def test_the_session_log_carries_the_exchange_and_names_the_test(self, dongle, tmp_path):
        """Whatever the report says, the log has what was sent and what came
        back - and a note per test, so the two read together."""
        path = tmp_path / "ble.log"
        dongle.start_log(str(path))
        self.run(dongle, "| 1 | temp | 23.5 |\n")
        dongle.stop_log()
        log = path.read_text()
        assert "# script: A test" in log
        assert "cmd %s" % b"temp".hex() in log
        assert b"23.5".hex() in log


class TestASensorThatDoesNotAnswer:
    """The simulated sensor always replies - it answers an unknown command
    with an error - so silence is modelled here instead, with a dongle whose
    command call raises as a real one does on timeout."""

    class Silent:
        """A dongle that never gets a reply."""

        selected = None

        def command(self, request, timeout=0.0):
            raise TransportTimeoutError("the sensor did not reply within %.2f s" % timeout)

    def run(self, body: str, **arguments):
        return run_script(
            self.Silent(), parse_script(document(body)), sleep=lambda seconds: None,
            **arguments
        )

    def test_a_step_that_expected_a_reply_is_an_error(self):
        run = self.run("| 1 | temp | 23.5 |\n", timeout=0.05)
        step = run.results[0]
        assert step.result == ERROR and run.result == ERROR
        assert "no reply within 0.05 s" in step.reason

    def test_a_step_that_expected_none_is_still_only_skipped(self):
        """The document promised nothing, so silence keeps that promise."""
        run = self.run("| 1 | log start | |\n", listen=0.05)
        step = run.results[0]
        assert step.result == SKIP and run.result == PASS
        assert "expected none" in step.reason

    def test_the_listening_window_is_the_one_given_not_the_timeout(self):
        """A document full of fire-and-forget commands would otherwise wait the
        full reply timeout on every one of them."""
        run = self.run("| 1 | log start | |\n", timeout=30.0, listen=0.05)
        assert "0.05 s" in run.results[0].reason

    def test_nothing_is_recorded_as_a_response(self):
        run = self.run("| 1 | temp | 23.5 |\n", timeout=0.05)
        assert run.results[0].response == ""
        assert run.results[0].elapsed_s is None


class TestTheReport:
    @pytest.fixture
    def run(self):
        instrument = NordicDongle(MockTransport(responder=SimulatedDongle()))
        instrument.initialise()
        instrument.scan(duration=0.2, name="0A1B2C")
        instrument.select("SENS-0A1B2C")
        instrument.open_link()
        script = parse_script(
            document(
                "| 1 | rd version | 1.4.2 |\n"
                "| 2 | delay 100 | |\n"
                "| 3 | temp | 0.0 |\n"
            ),
            source="commands.md",
        )
        try:
            yield run_script(instrument, script, sleep=lambda seconds: None)
        finally:
            instrument.close()

    def test_it_leads_with_the_verdict(self, run):
        assert "| Result | **FAIL** |" in run.markdown()

    def test_it_has_a_row_per_step_with_the_columns_asked_for(self, run):
        lines = [line for line in run.markdown().splitlines() if line.startswith("| A test |")]
        assert len(lines) == 3
        assert "| A test | 3 | temp | 0.0 | 0.0 |" not in lines[2], "response and expected differ"
        assert "23.5" in lines[2] and "0.0" in lines[2]

    def test_failures_are_listed_separately_with_both_values(self, run):
        text = run.markdown()
        assert "## Errors and failures" in text
        assert "expected `0.0`, got `23.5`" in text

    def test_the_document_and_the_sensor_are_named(self, run):
        text = run.markdown()
        assert "commands.md" in text and "SENS-0A1B2C" in text

    def test_it_says_what_a_skip_means(self, run):
        assert "SKIP when nothing was expected" in run.markdown()

    def test_it_is_written_where_asked(self, run, tmp_path):
        path = run.write(str(tmp_path / "results.md"))
        assert "| Result | **FAIL** |" in open(path, encoding="utf-8").read()

    def test_the_record_carries_every_column(self, run):
        record = run.as_dict()
        assert record["result"] == "FAIL"
        assert set(record["steps"][0]) >= {
            "test", "step", "command", "response", "expected",
            "seconds", "resolution_s", "clock", "result",
        }


class TestThroughTheDriver:
    def test_it_runs_a_document_and_writes_the_report(self, tmp_path):
        instrument = NordicDongle(MockTransport(responder=SimulatedDongle()))
        instrument.initialise()
        instrument.scan(duration=0.2, name="0A1B2C")
        instrument.select("SENS-0A1B2C")
        instrument.open_link()
        source = tmp_path / "commands.md"
        source.write_text(document("| 1 | rd version | 1.4.2 |\n"))
        report = tmp_path / "results.md"
        try:
            run = instrument.run_script(str(source), report=str(report))
        finally:
            instrument.close()
        assert run.result == PASS and report.is_file()

    def test_it_refuses_to_run_with_no_link_open(self, tmp_path):
        """Every step would fail for the same reason, and none of the failures
        would be about the sensor."""
        instrument = NordicDongle(MockTransport(responder=SimulatedDongle()))
        instrument.initialise()
        source = tmp_path / "commands.md"
        source.write_text(document("| 1 | temp | 23.5 |\n"))
        try:
            with pytest.raises(InstrumentError, match="no link is open"):
                instrument.run_script(str(source))
        finally:
            instrument.close()


class TestTheShippedDocument:
    """`specs/sensor_commands.md` is shipped as the worked example, and is run
    by `specs/sensor_commands.yaml`. If it stopped parsing, or stopped passing
    against the simulated sensor, the example would be teaching the wrong
    thing."""

    import pathlib

    SOURCE = pathlib.Path(__file__).resolve().parents[3] / "specs" / "sensor_commands.md"

    def test_it_reads(self):
        script = load_script(str(self.SOURCE))
        assert len(script.tests) >= 4 and script.checks >= 6

    def test_it_passes_against_the_simulated_sensor(self):
        instrument = NordicDongle(MockTransport(responder=SimulatedDongle()))
        instrument.initialise()
        instrument.scan(duration=0.2, name="0A1B2C")
        instrument.select("SENS-0A1B2C")
        instrument.open_link()
        try:
            run = run_script(
                instrument, load_script(str(self.SOURCE)), sleep=lambda seconds: None
            )
        finally:
            instrument.close()
        assert run.result == PASS, [item.as_dict() for item in run.failures]
        assert run.skipped == 3, "the delay and the two commands promising nothing"



# ----------------------------------------------------------------------
# Variables, connect and disconnect (#46)
# ----------------------------------------------------------------------
VARIABLES = """# Parameterised

| Variable  | Default | Notes |
|-----------|---------|-------|
| SENSOR_ID |         | required |
| SETTLE_MS | 100     |       |
| VERSION   | 1.4     |       |

## Identity

| Step | Command              | Expected response  |
|------|----------------------|--------------------|
| 1    | connect ${SENSOR_ID} |                    |
| 2    | delay ${SETTLE_MS}   |                    |
| 3    | rd version           | /^${VERSION}/      |
| 4    | disconnect           |                    |
"""


def no_wait(seconds):
    """Stand-in for time.sleep: the tests must not wait in real time."""
    del seconds


class TestVariables:
    """``${NAME}`` is Robot Framework's syntax, so a row converts as written."""

    def test_defaults_and_values_are_substituted(self):
        script = parse_script(VARIABLES, variables={"SENSOR_ID": "sens"})
        steps = script.steps
        assert steps[0].target == "sens"
        assert steps[1].delay_s == pytest.approx(0.100)
        assert steps[2].expected == "/^1.4/"
        assert script.variables == {"SENSOR_ID": "sens", "SETTLE_MS": "100", "VERSION": "1.4"}

    def test_a_value_overrides_a_default(self):
        script = parse_script(VARIABLES, variables={"SENSOR_ID": "s", "SETTLE_MS": "250"})
        assert script.steps[1].delay_s == pytest.approx(0.250)

    def test_a_variable_with_no_default_must_be_given(self):
        with pytest.raises(ConfigurationError, match="--var SENSOR_ID="):
            parse_script(VARIABLES)

    def test_an_undeclared_variable_is_refused(self):
        with pytest.raises(ConfigurationError, match=r"\$\{NOPE\} is not declared"):
            parse_script(document("| 1 | rd ${NOPE} | 1 |\n"))

    def test_a_value_for_an_undeclared_variable_is_refused(self):
        """A misspelt --var would otherwise leave the default silently in force."""
        with pytest.raises(ConfigurationError, match="SENSOR_IDD"):
            parse_script(VARIABLES, variables={"SENSOR_ID": "s", "SENSOR_IDD": "x"})

    def test_a_variable_declared_twice_is_refused(self):
        text = "| Variable | Default |\n|---|---|\n| A | 1 |\n| A | 2 |\n\n"
        with pytest.raises(ConfigurationError, match="declared twice"):
            parse_script(text + document("| 1 | x | 1 |\n"))

    def test_a_bad_variable_name_is_refused(self):
        text = "| Variable | Default |\n|---|---|\n| 2FAST | 1 |\n\n"
        with pytest.raises(ConfigurationError, match="not a variable name"):
            parse_script(text + document("| 1 | x | 1 |\n"))

    def test_variables_are_declared_before_the_first_step(self):
        text = document("| 1 | x | 1 |\n") + "\n| Variable | Default |\n|---|---|\n| A | 1 |\n"
        with pytest.raises(ConfigurationError, match="after the first step"):
            parse_script(text)

    def test_a_table_that_is_not_steps_is_prose(self):
        """A legend or a conversion table sits beside the steps unread."""
        legend = "## Legend\n\n| Row | Robot Framework |\n|---|---|\n| a | b |\n\n"
        script = parse_script(legend + document("| 1 | temp | 23.5 |\n"))
        assert [test.name for test in script.tests] == ["A test"]


def unlinked():
    """A dongle over the simulator, with no sensor selected and no link."""
    instrument = NordicDongle(MockTransport(responder=SimulatedDongle()))
    instrument.initialise()
    return instrument


class TestConnectAndDisconnect:
    def test_connect_and_disconnect_are_steps_for_the_dongle(self):
        script = parse_script(document("| 1 | connect SENS | |\n| 2 | disconnect | |\n"))
        assert [step.action for step in script.steps] == ["connect", "disconnect"]
        assert script.connects is True
        assert script.checks == 0           # neither has an expected response

    def test_connect_names_a_sensor(self):
        with pytest.raises(ConfigurationError, match="names no sensor"):
            parse_script(document("| 1 | connect | |\n"))

    def test_connect_has_no_expected_response(self):
        with pytest.raises(ConfigurationError, match="cannot have an expected response"):
            parse_script(document("| 1 | connect SENS | ok |\n"))

    def test_a_document_that_connects_needs_no_link_opened_for_it(self):
        instrument = unlinked()
        try:
            script = parse_script(VARIABLES, variables={"SENSOR_ID": "sens-0a1b"})
            run = run_script(instrument, script, sleep=no_wait, scan_s=0.2)
            assert [item.result for item in run.results] == [SKIP, SKIP, PASS, SKIP]
            assert "SENS-0A1B2C" in run.sensor
            assert run.variables["SENSOR_ID"] == "sens-0a1b"
            assert instrument.is_linked is False
        finally:
            instrument.close()

    def test_a_link_the_document_opened_is_closed_when_it_ends(self):
        instrument = unlinked()
        try:
            script = parse_script(document("| 1 | connect SENS-0A1B2C | |\n"))
            run_script(instrument, script, sleep=no_wait, scan_s=0.2)
            assert instrument.is_linked is False
        finally:
            instrument.close()

    def test_a_sensor_that_cannot_be_found_fails_the_connect_and_what_follows(self):
        instrument = unlinked()
        try:
            script = parse_script(document("| 1 | connect kappa | |\n| 2 | rd version | 1.4.2 |\n"))
            run = run_script(instrument, script, sleep=no_wait, scan_s=0.2, connect_attempts=1)
            assert [item.result for item in run.results] == [ERROR, ERROR]
            assert "kappa" in run.results[0].reason
        finally:
            instrument.close()

    def test_connect_takes_an_address(self):
        instrument = unlinked()
        try:
            script = parse_script(document("| 1 | connect E4:1C:7B:02:9A:11 | |\n"))
            run = run_script(instrument, script, sleep=no_wait, scan_s=0.2)
            assert run.results[0].result == SKIP
        finally:
            instrument.close()

    def test_the_driver_runs_a_document_that_connects_with_no_link_open(self, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(VARIABLES)
        instrument = unlinked()
        try:
            run = instrument.run_script(str(source), variables={"SENSOR_ID": "SENS-0A1B2C"})
        finally:
            instrument.close()
        assert run.result == PASS


class TestTheTemplate:
    """`specs/templates/ble_sensor_test.md` is what people copy. It must parse,
    must demand a sensor, and must start by connecting to it."""

    import pathlib

    SOURCE = (pathlib.Path(__file__).resolve().parents[3]
              / "specs" / "templates" / "ble_sensor_test.md")

    def test_it_parses_with_a_sensor_given(self):
        script = load_script(str(self.SOURCE), variables={"SENSOR_ID": "kappa"})
        assert script.steps[0].action == "connect"
        assert script.steps[0].target == "kappa"
        assert script.connects is True
        assert any(step.is_delay for step in script.steps)
        assert script.checks >= 2

    def test_it_will_not_run_without_a_sensor(self):
        with pytest.raises(ConfigurationError, match="SENSOR_ID"):
            load_script(str(self.SOURCE))


# ----------------------------------------------------------------------
# Results in priority order, Timeout and Note columns, <disconnect>, and the
# event log (#46)
# ----------------------------------------------------------------------
def timed(body: str) -> str:
    """One test whose table has Timeout and Note columns."""
    return ("## Timed\n\n| Step | Command | Expected response | Timeout (ms) | Note |\n"
            "|---|---|---|---|---|\n" + body)


def linked(**sensor_fields):
    """A dongle linked to the simulated sensor, with fields of it changed."""
    simulator = SimulatedDongle()
    for name, value in sensor_fields.items():
        setattr(simulator.sensors[0], name, value)
    instrument = NordicDongle(MockTransport(responder=simulator))
    instrument.initialise()
    instrument.scan(duration=0.2)
    instrument.select("SENS-0A1B2C")
    instrument.open_link()
    return instrument, simulator


class TestTheTimeoutColumn:
    def test_a_timeout_is_read_in_milliseconds(self):
        script = parse_script(timed("| 1 | rd version | 1.4.2 | 5000 | |\n"))
        assert script.steps[0].timeout_s == pytest.approx(5.0)

    def test_an_empty_timeout_leaves_the_default(self):
        script = parse_script(timed("| 1 | rd version | 1.4.2 | | |\n"))
        assert script.steps[0].timeout_s is None

    def test_a_timeout_can_be_a_variable(self):
        text = "| Variable | Default |\n|---|---|\n| SLOW | 12000 |\n\n"
        script = parse_script(text + timed("| 1 | routine x | /^ACK/ | ${SLOW} | |\n"))
        assert script.steps[0].timeout_s == pytest.approx(12.0)

    def test_a_delay_cannot_have_a_timeout(self):
        with pytest.raises(ConfigurationError, match="cannot have a timeout"):
            parse_script(timed("| 1 | delay 100 | | 500 | |\n"))

    def test_a_timeout_out_of_range_is_refused(self):
        with pytest.raises(ConfigurationError, match="milliseconds from 100 to 60000"):
            parse_script(timed("| 1 | rd version | 1.4.2 | 99 | |\n"))
        with pytest.raises(ConfigurationError, match="milliseconds from 1000 to 60000"):
            parse_script(timed("| 1 | connect SENS | | 500 | |\n"))

    def test_the_step_timeout_reaches_the_dongle(self):
        instrument, simulator = linked()
        try:
            run_script(instrument, parse_script(timed("| 1 | rd version | 1.4.2 | 7000 | |\n")),
                       sleep=no_wait)
            assert simulator.last_command_timeout_ms == 7000
        finally:
            instrument.close()

    def test_a_slow_command_errors_by_default_and_passes_with_its_own_timeout(self):
        """Some commands take longer than others."""
        instrument, _ = linked(latency_overrides={"rd version": 4_000_000})
        try:
            run = run_script(instrument, parse_script(timed(
                "| 1 | rd version | 1.4.2 | | |\n| 2 | rd version | 1.4.2 | 6000 | |\n")),
                timeout=2.0, sleep=no_wait)
            assert [item.result for item in run.results] == [ERROR, PASS]
        finally:
            instrument.close()


class TestResultsInPriorityOrder:
    """ERROR, then SKIP, then FAIL, then PASS: the first that applies wins."""

    def test_a_refused_command_is_an_error_even_with_nothing_expected(self):
        instrument = unlinked()                  # no link: the dongle refuses
        try:
            script = parse_script(document("| 1 | connect nobody | |\n| 2 | log start | |\n"))
            run = run_script(instrument, script, sleep=no_wait, scan_s=0.2, connect_attempts=1)
            assert [item.result for item in run.results] == [ERROR, ERROR]
        finally:
            instrument.close()

    def test_a_wrong_reply_fails_and_a_right_one_passes(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(document(
                "| 1 | rd version | 9.9.9 |\n| 2 | rd version | 1.4.2 |\n")), sleep=no_wait)
            assert [item.result for item in run.results] == [FAIL, PASS]
            assert run.result == FAIL
        finally:
            instrument.close()

    def test_an_error_outranks_a_failure_in_the_verdict(self):
        run = run_script(TestASensorThatDoesNotAnswer.Silent(),
                         parse_script(document("| 1 | temp | 23.5 |\n")),
                         sleep=no_wait, timeout=0.05)
        assert run.result == ERROR and run.errors == 1

    def test_the_note_column_is_carried_to_the_result(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(timed(
                "| 1 | rd version | 9.9.9 | | the build decides |\n")), sleep=no_wait)
            assert run.results[0].note == "the build decides"
            assert "the build decides" in run.results[0].notes
            assert "the reply does not match" in run.results[0].notes
        finally:
            instrument.close()

    def test_the_report_has_response_time_result_and_note_columns(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(document("| 1 | rd version | 1.4.2 |\n")),
                             sleep=no_wait)
        finally:
            instrument.close()
        text = run.markdown()
        assert "| Expected | Actual | Response time (ms) | Result | Note |" in text
        assert "| A test | 1 | rd version | 1.4.2 | 1.4.2 | 10 | PASS |" in text


class TestExpectingADisconnect:
    """`<disconnect>`: the sensor drops the link after the command - a reset."""

    def test_it_is_a_claim_that_can_pass_or_fail(self):
        script = parse_script(document("| 1 | wr mode normal | <disconnect> |\n"))
        step = script.steps[0]
        assert step.expects_disconnect and not step.expects_response
        assert script.checks == 1

    def test_the_drop_passes_and_is_timed_on_the_dongle_clock(self):
        instrument, _ = linked(disconnect_on={"wr mode normal": 350_000})
        try:
            run = run_script(instrument, parse_script(document(
                "| 1 | wr mode normal | <disconnect> |\n")), sleep=no_wait)
            result = run.results[0]
            assert result.result == PASS
            assert result.clock == "dongle"
            assert result.elapsed_s == pytest.approx(0.350)
            assert instrument.is_linked is False
        finally:
            instrument.close()

    def test_a_sensor_that_stays_connected_fails(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(timed(
                "| 1 | wr mode normal | <disconnect> | 200 | |\n")), sleep=no_wait)
            assert run.results[0].result == FAIL
            assert "still connected" in run.results[0].reason
        finally:
            instrument.close()


class TestTheEventLog:
    def test_every_kind_of_event_is_logged_with_its_step_and_result(self, tmp_path):
        source = tmp_path / "test.md"
        source.write_text(
            "## Events\n\n| Step | Command | Expected response |\n|---|---|---|\n"
            "| 1 | connect SENS-0A1B2C | |\n| 2 | delay 10 | |\n| 3 | rd version | 1.4.2 |\n"
            "| 4 | wr mode normal | <disconnect> |\n| 5 | rd version | 1.4.2 |\n"
            "| 6 | disconnect | |\n")
        path = tmp_path / "events.log"
        simulator = SimulatedDongle()
        simulator.sensors[0].disconnect_on = {"wr mode normal": 100_000}
        instrument = NordicDongle(MockTransport(responder=simulator))
        instrument.initialise()
        try:
            run = instrument.run_script(str(source), events=str(path))
        finally:
            instrument.close()

        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "time\tevent\tstep\tdata\tresult"
        rows = [line.split("\t") for line in lines[1:]]
        assert all(len(row) == 5 for row in rows)
        assert [row[1] for row in rows] == [
            "CONNECT", "DELAY", "TX", "RX", "TX", "DISCONNECT", "TX", "ERROR", "DISCONNECT"]
        assert rows[3][2] == "Events/3" and rows[3][4] == "PASS"
        assert "1.4.2" in rows[3][3] and "dongle clock" in rows[3][3]
        assert rows[5][4] == "PASS"                       # the sensor dropped the link
        assert rows[7][4] == "ERROR"                      # no link for step 5
        assert run.events == lines

    def test_with_no_file_the_lines_are_still_kept_on_the_run(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(document("| 1 | rd version | 1.4.2 |\n")),
                             sleep=no_wait)
        finally:
            instrument.close()
        assert [line.split("\t")[1] for line in run.events[1:]] == ["TX", "RX"]


    def test_each_failed_connect_attempt_is_logged(self):
        """A flaky link stays visible though the step goes on to link (#180)."""
        simulator = SimulatedDongle()
        simulator.sensors[0].not_established = 2
        instrument = NordicDongle(MockTransport(responder=simulator))
        instrument.initialise()
        try:
            run = run_script(instrument, parse_script(document("| 1 | connect SENS-0A1B2C | |\n")),
                             sleep=no_wait, scan_s=0.2)
        finally:
            instrument.close()
        assert run.results[0].result == SKIP
        rows = [line.split("\t") for line in run.events[1:]]
        assert [row[1] for row in rows] == ["CONNECT", "CONNECT", "CONNECT"]
        assert "attempt 1 of 3 failed" in rows[0][3] and "0x3e" in rows[0][3]
        assert "attempt 2 of 3 failed" in rows[1][3]
        assert rows[0][4] == "-" and rows[1][4] == "-"
        assert "linked to" in rows[2][3] and rows[2][4] == SKIP

    def test_a_connect_step_makes_no_more_attempts_than_it_is_allowed(self):
        """The driver's own retry on 0x3E must not multiply the step's."""
        simulator = SimulatedDongle()
        simulator.sensors[0].not_established = 9
        instrument = NordicDongle(MockTransport(responder=simulator))
        instrument.initialise()
        try:
            run = run_script(instrument, parse_script(document("| 1 | connect SENS-0A1B2C | |\n")),
                             sleep=no_wait, scan_s=0.2)
        finally:
            instrument.close()
        assert run.results[0].result == ERROR
        assert simulator.sensors[0].not_established == 9 - CONNECT_ATTEMPTS
        assert len([line for line in simulator.command_log
                    if line.startswith("connect")]) == CONNECT_ATTEMPTS

def saving(body: str) -> str:
    """One test whose table has a Save column."""
    return ("## Saving\n\n| Step | Command | Expected response | Save |\n|---|---|---|---|\n"
            + body)


class TestSavingAReply:
    """A reply saved in one step is compared in a later one (#54)."""

    def test_a_saved_reply_is_compared_later(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(saving(
                "| 1 | rd version | | BEFORE |\n"
                "| 2 | temp | 23.5 | |\n"
                "| 3 | rd version | ${BEFORE} | |\n")), sleep=no_wait)
        finally:
            instrument.close()
        assert [item.result for item in run.results] == [SKIP, PASS, PASS]
        assert run.saved == {"BEFORE": "1.4.2"}
        assert "saved BEFORE = 1.4.2" in run.results[0].reason

    def test_a_named_group_saves_just_that_part(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(saving(
                "| 1 | rd id | /^SENS-(?P<code>[0-9A-F]+)$/ | CODE |\n"
                "| 2 | rd id | SENS-${CODE} | |\n")), sleep=no_wait)
        finally:
            instrument.close()
        assert run.saved == {"CODE": "0A1B2C"}
        assert run.results[1].result == PASS

    def test_a_saved_value_is_escaped_inside_a_pattern(self):
        """A saved 1.4.2 must not match 1x4x2."""
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(saving(
                "| 1 | rd version | | V |\n| 2 | rd version | /^${V}$/ | |\n")),
                sleep=no_wait)
        finally:
            instrument.close()
        assert run.results[1].expected == "/^1\\.4\\.2$/"
        assert run.results[1].result == PASS

    def test_a_reply_that_failed_its_check_is_not_saved(self):
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(saving(
                "| 1 | rd version | 9.9.9 | V |\n| 2 | rd version | ${V} | |\n")),
                sleep=no_wait)
        finally:
            instrument.close()
        assert [item.result for item in run.results] == [FAIL, ERROR]
        assert "was not saved" in run.results[1].reason

    def test_a_saved_name_is_usable_only_after_the_row_that_saves_it(self):
        with pytest.raises(ConfigurationError, match=r"\$\{V\} is not declared"):
            parse_script(saving("| 1 | rd version | ${V} | |\n| 2 | rd version | | V |\n"))

    def test_a_saved_name_cannot_shadow_a_declared_variable(self):
        text = "| Variable | Default |\n|---|---|\n| V | 1 |\n\n"
        with pytest.raises(ConfigurationError, match="needs a name of its own"):
            parse_script(text + saving("| 1 | rd version | | V |\n"))

    def test_only_a_command_reply_can_be_saved(self):
        with pytest.raises(ConfigurationError, match="only a command's reply"):
            parse_script(saving("| 1 | delay 10 | | V |\n"))
        with pytest.raises(ConfigurationError, match="only a command's reply"):
            parse_script(saving("| 1 | wr reset | <disconnect> | V |\n"))

class TestEscapedPipes:
    """``\\|`` is a pipe inside a cell, as the row-width error has always said (#50)."""

    def test_a_pattern_can_use_alternation(self):
        script = parse_script(document(
            "| 1 | rd fast | /^ACK = (ENABLED\\|DISABLED)$/ |\n"))
        step = script.steps[0]
        assert step.expected == "/^ACK = (ENABLED|DISABLED)$/"
        assert step.matches("ACK = ENABLED") and step.matches("ACK = DISABLED")
        assert not step.matches("ACK = ABLED")

    def test_a_command_can_contain_a_pipe(self):
        script = parse_script(document("| 1 | wr sep a\\|b | ok |\n"))
        assert script.steps[0].command == "wr sep a|b"

    def test_a_backslash_before_anything_else_is_kept(self):
        script = parse_script(document("| 1 | rd v | /^V[0-9]+\\.[0-9]+\\b/ |\n"))
        assert script.steps[0].expected == "/^V[0-9]+\\.[0-9]+\\b/"

    def test_an_escaped_pipe_at_the_end_of_a_row_is_not_its_closing_pipe(self):
        script = parse_script(
            "## A test\n\n| Step | Command | Expected response |\n|---|---|---|\n"
            "| 1 | rd v | /a\\|b\\|/\n")
        assert script.steps[0].expected == "/a|b|/"

    def test_an_unescaped_pipe_still_splits_and_is_still_refused(self):
        with pytest.raises(ConfigurationError, match="needs escaping"):
            parse_script(document("| 1 | rd v | /a|b/ |\n"))

    def test_the_report_escapes_what_the_reader_unescapes(self):
        """A reply with a pipe in it survives into the report's table intact."""
        instrument, _ = linked()
        try:
            run = run_script(instrument, parse_script(document(
                "| 1 | rd version | /^1\\.4\\.2$\\|^x$/ |\n")), sleep=no_wait)
        finally:
            instrument.close()
        assert run.results[0].result == PASS
        row = [line for line in run.markdown().splitlines() if line.startswith("| A test |")][0]
        assert "/^1\\.4\\.2$\\|^x$/" in row
