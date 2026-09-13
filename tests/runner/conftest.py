"""Fixtures for the bench runner tests.

Traces to: SWE4-UT-ENGINE.
"""

from __future__ import annotations

import pytest

from benchtools.runner import BenchConfig, BenchRunner, TestSpec

#: A minimal specification that passes against the default simulator, whose
#: channel skews are 0, 4, 9 and 1 ns.
PASSING_SPEC = {
    "name": "Skew suite",
    "requirements": ["SYS-REQ-001"],
    "setup": [
        {"do": "scope.configure_channel",
         "with": {"channel": 1, "volts_per_div": 1.0, "position_div": -4.0}},
        {"do": "scope.configure_channel",
         "with": {"channel": 2, "volts_per_div": 1.0, "position_div": -3.0}},
        {"do": "scope.set_time_per_div", "with": {"seconds_per_div": 200e-9}},
        {"do": "scope.configure_edge_trigger", "with": {"source": 1, "level": 1.65}},
    ],
    "tests": [
        {
            "name": "Spread within 20 ns",
            "requirement": "SYS-REQ-001",
            "steps": [
                {
                    "do": "scope.measure_channel_spread",
                    "with": {"channels": [1, 2], "direction": "RISE"},
                    "expect": [
                        {"name": "spread", "measure": "1.spread",
                         "scale": 1e9, "display_unit": "ns", "max": 20.0},
                    ],
                },
            ],
        },
    ],
}


@pytest.fixture
def passing_spec() -> TestSpec:
    return TestSpec.from_mapping(PASSING_SPEC, source="<fixture>")


@pytest.fixture
def simulated_config(passing_spec) -> BenchConfig:
    return BenchConfig.simulated(passing_spec.instruments_used)


@pytest.fixture
def runner(simulated_config) -> BenchRunner:
    instance = BenchRunner.from_config(simulated_config)
    yield instance
    instance.close()
