"""Software integration and qualification cases that no other test realised (#370).

Each test names the case of ETB-SWE5-001 §6 or ETB-SWE6-001 §5 it realises.
They were written when the cases were traced to tests and a case had none:

- ETB-IT-07, ETB-QT-17: the JSON report states that a run was simulated;
- ETB-IT-10: the runner reaches drivers only through the registry in
  ``bench.py``, the one runner module that imports instrument packages;
- ETB-IT-13: the S2-LP driver and the ETB kit firmware agree on the protocol;
- ETB-IT-15: a specification drives the serial capture instrument through the
  runner;
- ETB-QT-01: every instrument in the simulated bench opens and is identified.

Traces to: RUN-FR-006, RUN-FR-035, RUN-FR-037, RUN-FR-041, SER-FR-006,
S2LP-FR-094, S2LP-FR-098, RUN-DD-RUNNER, RUN-DD-BENCH, SWE4-UT-INTEGRATION.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re

import pytest

from benchtools.instruments.s2lp import kit_firmware
from benchtools.runner.bench import Bench, load_bench
from benchtools.runner.report import write_json
from benchtools.runner.results import Status
from benchtools.runner.runner import BenchRunner
from benchtools.runner.spec import load_spec

# The bench and the specifications are YAML, read when they are loaded.
pytest.importorskip("yaml", reason="pyyaml is not installed (it is an optional extra)")

ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCH = ROOT / "benches" / "simulated_bench.yaml"


def _run(spec_name: str):
    bench = Bench(load_bench(str(BENCH)))
    try:
        return BenchRunner(bench).run(load_spec(str(ROOT / "specs" / spec_name)))
    finally:
        bench.close()


def test_every_simulated_instrument_answers_with_an_identity():
    """ETB-QT-01: the simulated bench opens and identifies every instrument."""
    config = load_bench(str(BENCH))
    bench = Bench(config)
    try:
        for alias in config.instruments:
            bench.get(alias)
        described = bench.describe_instruments()
    finally:
        bench.close()
    assert set(described) == set(config.instruments)
    missing = sorted(alias for alias, entry in described.items()
                     if "identity_error" in entry or not entry.get("model"))
    assert not missing, "instruments with no identity: %s" % ", ".join(missing)


def test_the_serial_capture_specification_passes_through_the_runner():
    """ETB-IT-15: the shipped serial capture specification, through the runner."""
    record = _run("serial_capture.yaml")
    assert record.cases, "the specification ran no case"
    assert all(case.status is Status.PASS for case in record.cases), [
        (case.name, case.status) for case in record.cases]
    assert record.simulated


def test_the_json_report_says_the_run_was_simulated(tmp_path):
    """ETB-IT-07 and ETB-QT-17: the JSON report says the run was simulated."""
    record = _run("serial_capture.yaml")
    path = write_json(record, str(tmp_path / "run.json"))
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    assert data["simulated"] is True


def _imported_modules(path: pathlib.Path) -> set:
    """Every module a file imports, with relative imports resolved against the
    file's package, and the names of a ``from X import a, b`` taken as X.a, X.b
    (a name may be a submodule)."""
    package = ["benchtools"] + list(path.relative_to(ROOT / "benchtools").parent.parts)
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - node.level + 1]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            found.add(module)
            found.update("%s.%s" % (module, alias.name) for alias in node.names)
    return found


def test_the_runner_reaches_drivers_only_through_the_registry_in_bench_py():
    """ETB-IT-10: of the runner's modules, only bench.py, which holds the driver
    registry, imports an instrument package."""
    importers = set()
    for path in sorted((ROOT / "benchtools" / "runner").glob("*.py")):
        if any(name.startswith("benchtools.instruments") for name in _imported_modules(path)):
            importers.add(path.name)
    assert importers == {"bench.py"}, importers


def test_relative_imports_are_resolved():
    """The helper sees what a relative import names (review of #400)."""
    bench = _imported_modules(ROOT / "benchtools" / "runner" / "bench.py")
    assert "benchtools.instruments.jlink" in bench
    assert "benchtools.core.instrument" in bench


def _firmware_defines(path: pathlib.Path) -> dict:
    found = {}
    for name, value in re.findall(r"^#define\s+(\w+)\s+(.+?)\s*$",
                                  path.read_text(encoding="utf-8"), re.M):
        found[name] = value
    return found


class TestTheKitFirmwareProtocolAgrees:
    """ETB-IT-13: host and firmware agree on the ETB S2-LP kit protocol."""

    PROTOCOL_H = ROOT / "firmware" / "s2lp_kit" / "include" / "protocol.h"
    VERSION_H = ROOT / "firmware" / "s2lp_kit" / "include" / "firmware_version.h"

    @staticmethod
    def _number(text: str) -> int:
        return int(re.search(r"\d+", text).group(0))

    def test_the_protocol_version(self):
        """Both sides speak protocol version 1."""
        defines = _firmware_defines(self.PROTOCOL_H)
        assert self._number(defines["PROTO_VERSION"]) == kit_firmware.KIT_PROTOCOL

    def test_the_limits(self):
        """Register, payload and line limits are the same on both sides."""
        defines = _firmware_defines(self.PROTOCOL_H)
        assert self._number(defines["PROTO_MAX_REGISTERS"]) == kit_firmware.MAX_REGISTERS
        assert self._number(defines["PROTO_MAX_PAYLOAD"]) == kit_firmware.MAX_PAYLOAD
        assert self._number(defines["PROTO_LINE_MAX"]) == kit_firmware.LINE_MAX

    def test_the_record_kinds(self):
        """Frame and rejection records use the same kind letters."""
        defines = _firmware_defines(self.PROTOCOL_H)
        kinds = {re.search(r"'(.)'", defines[name]).group(1)
                 for name in ("PROTO_KIND_FRAME", "PROTO_KIND_REJECT")}
        assert kinds == {"f", "r"}
        host = pathlib.Path(kit_firmware.__file__).read_text(encoding="utf-8")
        assert all('words[0] == "%s"' % kind in host for kind in kinds)

    def test_the_firmware_name(self):
        """The name in the `id` reply is the one the host looks for."""
        defines = _firmware_defines(self.VERSION_H)
        assert defines["FIRMWARE_NAME"].strip('"') == kit_firmware.KIT_FIRMWARE_NAME
