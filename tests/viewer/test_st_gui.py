"""The ST GUI page: the kit's setup logged, read on request between steps, shown (#157).

Traces to: S2LP-FR-084, RUN-FR-066, VIEW-FR-043 .. VIEW-FR-045, SWE4-UT-VIEWSTGUI.
"""

from __future__ import annotations

import logging

import pytest

from benchtools.core.events import EventTail, start_event_log
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.s2lp import S2lpDevkit
from benchtools.instruments.s2lp import registers as reg
from benchtools.instruments.s2lp.configuration import parse_register_file
from benchtools.instruments.s2lp.simulator import SimulatedS2lp
from benchtools.runner import BenchConfig, BenchRunner
from benchtools.runner.control import READ_SETUP, RunControl
from benchtools.runner.spec import TestSpec
from benchtools.viewer.server import Hub
from benchtools.viewer.st_gui import StGui, register_rows, regs_text, rf_setup_rows, st_row


def _logged(tmp_path, action):
    path = str(tmp_path / "events.jsonl")
    handler = start_event_log(path)
    try:
        action()
    finally:
        logging.getLogger("benchtools").removeHandler(handler)
        handler.close()
    return path, EventTail(path).read()


def _kit_setup(tmp_path):
    def act():
        kit = S2lpDevkit(MockTransport(responder=SimulatedS2lp()))
        kit.initialise()
        kit.write_register("PCKTLEN0", 0x20)
        kit.read_setup()
        kit.close()
    return _logged(tmp_path, act)


class TestDriver:
    def test_read_setup_returns_what_it_logs(self, tmp_path):
        result = {}

        def act():
            kit = S2lpDevkit(MockTransport(responder=SimulatedS2lp()))
            kit.initialise()
            result["setup"] = kit.read_setup()
            kit.close()
        _path, records = _logged(tmp_path, act)
        logged = next(r for r in records if r.get("kind") == "rf_setup")["data"]
        assert logged["radio"] == result["setup"]["radio"]
        assert {int(k): v for k, v in logged["registers"].items()} == result["setup"]["registers"]

    def test_read_setup_is_logged_as_one_record(self, tmp_path):
        _path, records = _kit_setup(tmp_path)
        setups = [r for r in records if r.get("kind") == "rf_setup"]
        assert len(setups) == 1
        data = setups[0]["data"]
        assert setups[0]["source"] == "RF"
        assert len(data["registers"]) == len(reg.REGISTERS)
        assert data["registers"][str(reg.BY_NAME["PCKTLEN0"].address)] == 0x20
        assert {"frequency_hz", "data_rate_bps"} <= set(data["radio"])
        assert data["power_dbm"] is not None


class _Asker(RunControl):
    """Asks for the setup when the run reaches test case 0, step 1."""

    def checkpoint(self, phase, case, step, interruptible=True):
        if (phase, case, step) == ("test", 0, 1) and not getattr(self, "asked", False):
            self.asked = True                     # pylint: disable=attribute-defined-outside-init
            with self._condition:
                self._position = {"phase": phase, "case": case, "step": step}
            self.reply = self.request({"cmd": READ_SETUP})  # pylint: disable=W0201
        return super().checkpoint(phase, case, step, interruptible)


class TestRunner:
    def test_read_setup_between_steps_without_interrupting_the_run(self, tmp_path):
        control = _Asker()
        spec = TestSpec.from_mapping({"name": "st", "instruments": {"s2lp": "s2lp"}, "tests": [
            {"name": "t", "steps": [{"do": "s2lp.frequency_hz"},
                                    {"do": "sleep", "with": {"seconds": 0}},
                                    {"do": "sleep", "with": {"seconds": 0}}]}]})
        result = {}

        def act():
            with BenchRunner.from_config(BenchConfig.simulated({"s2lp": "s2lp"}), simulate=True,
                                         control=control) as runner:
                result["run"] = runner.run(spec)
        _path, records = _logged(tmp_path, act)
        assert control.reply["ok"]
        assert result["run"].status.value == "PASS"
        assert len(result["run"].cases[0].steps) == 3
        kinds = [r.get("kind") for r in records if r.get("kind")]
        assert kinds.count("rf_setup") == 1
        assert kinds.index("rf_setup") < max(i for i, k in enumerate(kinds) if k == "step_end")

    def test_refused_in_teardown_and_with_no_run(self):
        control = RunControl()
        assert control.request({"cmd": READ_SETUP})["ok"] is False
        control.begin("x", lambda case, step: None)
        control.checkpoint("teardown", None, 0, interruptible=False)
        assert "teardown" in control.request({"cmd": READ_SETUP})["error"]

    def test_a_failing_reader_does_not_fail_the_run(self, monkeypatch):
        monkeypatch.setattr(S2lpDevkit, "read_setup", lambda self: 1 / 0)
        control = _Asker()
        spec = TestSpec.from_mapping({"name": "st", "instruments": {"s2lp": "s2lp"}, "tests": [
            {"name": "t", "steps": [{"do": "s2lp.frequency_hz"},
                                    {"do": "sleep", "with": {"seconds": 0}}]}]})
        with BenchRunner.from_config(BenchConfig.simulated({"s2lp": "s2lp"}), simulate=True,
                                     control=control) as runner:
            assert runner.run(spec).status.value == "PASS"


class TestPage:
    @pytest.fixture
    def setup(self, tmp_path):
        _path, records = _kit_setup(tmp_path)
        gui = StGui()
        for record in records:
            gui.feed(record)
        return gui.setup()

    def test_rf_setup_rows(self, setup):
        rows = {label: value for _section, label, value in rf_setup_rows(setup)}
        assert rows["Format"] == "Basic"
        assert rows["Length"] == "fixed, 32 bytes"        # PCKTLEN0 written as 0x20
        assert rows["Preamble"] == "16 pairs (32 bits)"
        assert rows["Output power"].endswith("dBm")

    def test_register_rows_mark_a_changed_register(self, setup):
        rows = {row["name"]: row for row in register_rows(setup["registers"])}
        assert rows["PCKTLEN0"]["value"] == "0x20" and rows["PCKTLEN0"]["changed"]
        assert rows["PCKTLEN0"]["fields"]

    def test_the_register_file_round_trips(self, setup):
        parsed = parse_register_file(regs_text(setup["registers"]))
        assert "PCKTLEN0" in parsed.names
        changed = [row["name"] for row in register_rows(setup["registers"]) if row["changed"]]
        assert sorted(parsed.names) == sorted(changed)

    def test_frames_as_st_s_gui_lists_them(self):
        good = st_row({"t": 1.0, "hex": "5c1712", "rssi_dbm": -70.5, "error": 0})
        assert (good["bytes"], good["data"], good["lost"]) == (3, "5C 17 12", False)
        crc = st_row({"t": 1.0, "hex": "", "rssi_dbm": -80.0, "error": 2})
        assert (crc["data"], crc["lost"]) == ("Packet lost. CRC error", True)
        assert st_row({"t": 1.0, "hex": "", "error": 4})["data"] == "Packet lost. Error 4"

    def test_the_hub_serves_the_page_and_the_file(self, tmp_path):
        path, _records = _kit_setup(tmp_path)
        hub = Hub()
        hub.follow(path)
        hub.poll()
        screen = hub.st_gui_screen()
        assert screen["read"] and len(screen["registers"]) == len(reg.REGISTERS)
        assert hub.registers_file().startswith("# Exported by the benchtools test run viewer")

    def test_nothing_read_yet(self):
        assert not StGui().view([])["registers"] and Hub().registers_file() is None
