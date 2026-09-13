"""The execution engine.

The distinction these tests pin down hardest is failure versus error: a
measurement out of limit means the thing under test is wrong, while a step that
could not run means the test told you nothing. Conflating them turns a broken
rig into a pile of apparent product defects.

Traces to: RUN-FR-010 .. RUN-FR-033, SWE4-UT-ENGINE.
"""

from __future__ import annotations

import pytest

from benchtools.runner import BenchConfig, BenchRunner, Status, TestSpec


def spec_of(**overrides) -> TestSpec:
    """Build a one-test specification around a single step."""
    base = {
        "name": "Suite",
        "tests": [{"name": "T", "requirement": "R1", "steps": [overrides]}],
    }
    return TestSpec.from_mapping(base)


def run_spec(spec, **kwargs):
    config = BenchConfig.simulated(spec.instruments_used or ["scope"])
    with BenchRunner.from_config(config, **kwargs) as runner:
        return runner.run(spec)


class TestHappyPath:
    def test_passing_suite(self, runner, passing_spec):
        run = runner.run(passing_spec)
        assert run.status is Status.PASS
        assert run.total == 1 and run.passed == 1
        assert run.cases[0].measurements[0].name == "spread"

    def test_measured_value_is_scaled_for_the_limit(self, runner, passing_spec):
        run = runner.run(passing_spec)
        measurement = run.cases[0].measurements[0]
        # The fixture captures channels 1 and 2 only, whose simulated skews are
        # 0 and 4 ns, so the spread is 4 ns. The limit was stated in ns via
        # scale, so the recorded value must be in ns too.
        assert measurement.value == pytest.approx(4.0, abs=0.05)
        assert measurement.raw_value == pytest.approx(4.0e-9, abs=5e-11)
        assert measurement.unit == "ns"

    def test_requirement_roll_up(self, runner, passing_spec):
        assert runner.run(passing_spec).requirements_verified == {"SYS-REQ-001": "PASS"}

    def test_setup_runs_before_the_tests(self, runner, passing_spec):
        runner.run(passing_spec)
        log = runner.bench.get("scope").transport.responder.command_log
        assert any("HORIZONTAL:MAIN:SCALE" in entry for entry in log)

    def test_teardown_runs_even_after_a_failure(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "steps": [
                {"do": "scope.measure_period", "with": {"channel": 1},
                 "expect": [{"max": 1e-12}]},
            ]}],
            "teardown": [{"do": "scope.stop"}],
        })
        config = BenchConfig.simulated(["scope"])
        with BenchRunner.from_config(config) as runner:
            run = runner.run(spec)
            log = runner.bench.get("scope").transport.responder.command_log
        assert run.status is Status.FAIL
        assert "ACQUIRE:STATE STOP" in log

    def test_builtin_sleep_action(self):
        run = run_spec(spec_of(**{"do": "sleep", "with": {"seconds": 0.01}}))
        assert run.status is Status.PASS

    def test_save_keeps_a_result_for_later(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "steps": [
                {"do": "scope.measure_period", "with": {"channel": 1}, "save": "period"},
            ]}],
        })
        config = BenchConfig.simulated(["scope"])
        with BenchRunner.from_config(config) as runner:
            runner.run(spec)
            assert runner._saved["period"] == pytest.approx(1e-6)


class TestFailureVersusError:
    def test_out_of_limit_is_a_failure_not_an_error(self):
        run = run_spec(spec_of(**{
            "do": "scope.measure_period", "with": {"channel": 1},
            "expect": [{"name": "period", "max": 1e-12}],
        }))
        assert run.status is Status.FAIL
        assert run.failed == 1 and run.errored == 0
        assert "above the maximum" in run.cases[0].measurements[0].reason

    def test_unknown_method_is_an_error_not_a_failure(self):
        run = run_spec(spec_of(**{"do": "scope.levitate"}))
        assert run.status is Status.ERROR
        assert run.errored == 1 and run.failed == 0
        assert "has no method 'levitate'" in run.cases[0].error

    def test_error_message_lists_available_methods(self):
        run = run_spec(spec_of(**{"do": "scope.levitate"}))
        assert "measure_period" in run.cases[0].error

    def test_wrong_arguments_are_an_error(self):
        run = run_spec(spec_of(**{"do": "scope.measure_period", "with": {"nonsense": 1}}))
        assert run.status is Status.ERROR
        assert "could not be called as specified" in run.cases[0].error

    def test_driver_exception_is_an_error(self):
        run = run_spec(spec_of(**{
            "do": "scope.configure_channel", "with": {"channel": 99},
        }))
        assert run.status is Status.ERROR
        assert "not available" in run.cases[0].error

    def test_unresolvable_measure_path_is_an_error(self):
        run = run_spec(spec_of(**{
            "do": "scope.measure_period", "with": {"channel": 1},
            "expect": [{"measure": "nope.nope", "max": 1}],
        }))
        assert run.status is Status.ERROR
        assert run.cases[0].measurements[0].status is Status.ERROR

    def test_non_numeric_measurement_is_an_error(self):
        run = run_spec(spec_of(**{"do": "scope.identity", "expect": [{"max": 1}]}))
        assert run.cases[0].measurements[0].status is Status.ERROR
        assert "not a number" in run.cases[0].measurements[0].reason

    def test_action_without_an_instrument_is_rejected(self):
        run = run_spec(spec_of(**{"do": "configure_channel"}))
        assert run.status is Status.ERROR
        assert "must be '<instrument>.<method>'" in run.cases[0].error

    def test_private_methods_are_unreachable(self):
        """A specification is data and must not be able to call internals."""
        run = run_spec(spec_of(**{"do": "scope._write", "with": {"command": "*RST"}}))
        assert run.status is Status.ERROR
        assert "private method" in run.cases[0].error


class TestSetupAndSkips:
    def test_setup_failure_aborts_the_suite(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "setup": [{"do": "scope.configure_channel", "with": {"channel": 42}}],
            "tests": [{"name": "T", "steps": [{"do": "scope.identity"}]}],
        })
        run = run_spec(spec)
        assert run.status is Status.ERROR
        assert run.cases == []
        assert "setup step" in run.setup_error

    def test_missing_instrument_is_reported_before_anything_runs(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "steps": [{"do": "dmm.identity"}]}],
        })
        config = BenchConfig.simulated(["scope"])
        with BenchRunner.from_config(config) as runner:
            run = runner.run(spec)
        assert run.status is Status.ERROR
        assert "does not define" in run.setup_error
        assert run.cases == []

    def test_skipped_test_is_not_executed(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "skip": True, "skip_reason": "no fixture",
                       "steps": [{"do": "scope.levitate"}]}],
        })
        run = run_spec(spec)
        assert run.skipped == 1
        assert run.cases[0].status is Status.SKIP
        assert run.cases[0].skip_reason == "no fixture"
        assert run.status is Status.SKIP

    def test_a_failure_does_not_stop_later_tests(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [
                {"name": "bad", "steps": [
                    {"do": "scope.measure_period", "with": {"channel": 1},
                     "expect": [{"max": 1e-12}]}]},
                {"name": "good", "steps": [
                    {"do": "scope.measure_period", "with": {"channel": 1},
                     "expect": [{"max": 1.0}]}]},
            ],
        })
        run = run_spec(spec)
        assert run.total == 2 and run.failed == 1 and run.passed == 1

    def test_stop_on_error_abandons_the_rest(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [
                {"name": "boom", "steps": [{"do": "scope.levitate"}]},
                {"name": "never", "steps": [{"do": "scope.identity"}]},
            ],
        })
        run = run_spec(spec, stop_on_error=True)
        assert run.total == 1 and run.errored == 1

    def test_a_step_that_errors_stops_its_own_case(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [{"name": "T", "steps": [
                {"do": "scope.levitate"},
                {"do": "scope.identity"},
            ]}],
        })
        run = run_spec(spec)
        assert len(run.cases[0].steps) == 1


class TestStatusAggregation:
    def test_worst_of_several(self):
        assert Status.worst([Status.PASS, Status.FAIL]) is Status.FAIL
        assert Status.worst([Status.FAIL, Status.ERROR]) is Status.ERROR
        assert Status.worst([Status.PASS, Status.SKIP]) is Status.SKIP
        assert Status.worst([]) is Status.PASS

    def test_requirement_takes_the_worst_of_its_tests(self):
        spec = TestSpec.from_mapping({
            "name": "S",
            "tests": [
                {"name": "a", "requirement": "R1", "steps": [
                    {"do": "scope.measure_period", "with": {"channel": 1},
                     "expect": [{"max": 1.0}]}]},
                {"name": "b", "requirement": "R1", "steps": [
                    {"do": "scope.measure_period", "with": {"channel": 1},
                     "expect": [{"max": 1e-12}]}]},
            ],
        })
        assert run_spec(spec).requirements_verified == {"R1": "FAIL"}

    def test_simulated_flag_is_recorded(self, passing_spec):
        config = BenchConfig.simulated(["scope"])
        with BenchRunner.from_config(config, simulate=True) as runner:
            assert runner.run(passing_spec).simulated is True
