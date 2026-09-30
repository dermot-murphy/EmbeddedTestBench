"""The bench configurations shipped in this repository.

A bench file is a statement about a physical rig, and the ways it can be wrong
are quiet ones: two instruments pointed at the same cable, an alias whose
driver does not exist. Neither shows up until someone is standing at the bench
with the hardware in front of them.

Traces to: RUN-FR-001 .. RUN-FR-005, SWE4-UT-BENCH.
"""

from __future__ import annotations

import pathlib

import pytest

# The shipped bench files are YAML, so this group needs the optional extra.
# pylint: disable=wrong-import-position
pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

from benchtools.runner.bench import load_bench, registered_drivers

ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCHES = sorted(ROOT.glob("benches/*.yaml"))


def bench_ids():
    return [path.name for path in BENCHES]


@pytest.mark.parametrize("path", BENCHES, ids=bench_ids())
class TestEveryShippedBench:
    def test_it_loads(self, path):
        assert load_bench(str(path)).instruments

    def test_every_driver_is_registered(self, path):
        known = set(registered_drivers())
        for alias, instrument in load_bench(str(path)).instruments.items():
            assert instrument.driver.lower() in known, (
                "%s: alias %r names driver %r, which no driver is registered under"
                % (path.name, alias, instrument.driver)
            )

    def test_no_two_instruments_share_a_port(self, path):
        # One cable, one instrument. Two aliases on the same port cannot both
        # be opened, and the failure arrives at the bench rather than here -
        # as "could not open port", pointing at the cable rather than at the
        # configuration that asked for it twice.
        #
        # sim:// is exempt: every simulator is its own in-process object, so
        # any number of aliases may name it.
        seen = {}
        for alias, instrument in load_bench(str(path)).instruments.items():
            resource = instrument.resource.strip().lower()
            if not resource or resource.startswith(("sim", "mock")):
                continue
            assert resource not in seen, (
                "%s: %r and %r are both on %s"
                % (path.name, seen[resource], alias, instrument.resource)
            )
            seen[resource] = alias
