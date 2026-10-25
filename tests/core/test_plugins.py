"""Device plugins: loading by path, what a plugin provides, and the lookups (#238).

Tested with the synthetic plugin in ``tests/plugins/synthetic``, whose frames
are made up, so the interface is tested without any product code.

Traces to: CORE-FR-066 .. CORE-FR-070, VIEW-FR-047, SWE4-UT-PLUGINS.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import pathlib
import subprocess
import sys
import threading

import pytest

from benchtools.core import MockTransport, plugins
from benchtools.core.errors import ConfigurationError
from benchtools.core.events import start_event_log
from benchtools.core.paths import resolve_input_path
from benchtools.instruments.s2lp import S2lpDevkit
from benchtools.instruments.s2lp.cli import main as s2lp_main
from benchtools.instruments.s2lp.simulator import SimulatedS2lp
from benchtools.runner import BenchRunner
from benchtools.runner.bench import BenchConfig
from benchtools.runner.cli import main as run_main
from benchtools.runner.report import format_markdown, plugin_text, write_junit
from benchtools.runner.spec import TestSpec
from benchtools.viewer import twf as twf_module
from benchtools.viewer.plugin_panels import run_plugins
from benchtools.viewer.server import Catalogue, Hub, Launcher, ViewerServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
SYNTHETIC = ROOT / "tests" / "plugins" / "synthetic"
KEPLER = ROOT / "plugins" / "kepler"
BENCHTOOLS = ROOT / "benchtools"


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    """A registry of its own, so each test sees only the plugins it loads."""
    fresh = plugins.Registry()
    monkeypatch.setattr(plugins, "REGISTRY", fresh)
    return fresh


def write_plugin(folder: pathlib.Path, body: str) -> pathlib.Path:
    folder.mkdir(parents=True)
    (folder / "__init__.py").write_text(body, encoding="utf-8")
    return folder


class TestLoading:
    def test_the_synthetic_plugin_provides_everything(self, registry):
        plugin = plugins.load_plugin(str(SYNTHETIC))
        assert plugin.name == "synthetic"
        assert plugin.path == os.path.normpath(str(SYNTHETIC))
        assert set(plugin.decoders) == {"synthetic"}
        assert set(plugin.register_files) == {"synthetic_rx.regs"}
        assert set(plugin.panels) == {"synthetic"}
        assert plugin.fields == {"reading": "value"}
        assert set(plugin.hooks) == {"twf_sample"}
        assert registry.plugins == {"synthetic": plugin}

    def test_a_plugin_in_a_git_checkout_records_its_commit(self):
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              stdout=subprocess.PIPE, check=True).stdout.decode().strip()
        described = plugins.load_plugin(str(SYNTHETIC)).describe()
        assert described["ref"] == head
        assert set(described) == {"name", "path", "ref", "dirty"}
        assert isinstance(described["dirty"], bool)

    def test_a_plugin_outside_git_has_no_ref(self, tmp_path):
        folder = write_plugin(tmp_path / "plain", "def register(plugin):\n    pass\n")
        assert plugins.load_plugin(str(folder)).describe()["ref"] is None

    def test_loading_a_folder_twice_gives_the_same_plugin(self):
        assert plugins.load_plugin(str(SYNTHETIC)) is plugins.load_plugin(str(SYNTHETIC) + os.sep)

    def test_the_plugin_name_defaults_to_the_folder(self, tmp_path):
        folder = write_plugin(tmp_path / "my-device", "def register(plugin):\n    pass\n")
        assert plugins.load_plugin(str(folder)).name == "my-device"

    @pytest.mark.parametrize("body, reason", [
        (None, "no __init__.py"),
        ("x = 1\n", "has no register"),
        ("raise RuntimeError('broken')\n", "failed to import: broken"),
        ("def register(plugin):\n    raise RuntimeError('nope')\n", "failed to register: nope"),
    ])
    def test_a_folder_that_is_not_a_working_plugin_is_refused(self, registry, tmp_path,
                                                                body, reason):
        folder = tmp_path / "bad"
        if body is None:
            folder.mkdir()
        else:
            write_plugin(folder, body)
        with pytest.raises(ConfigurationError, match=reason):
            plugins.load_plugin(str(folder))
        assert not registry.plugins

    def test_two_plugins_with_one_name_are_refused(self, tmp_path):
        plugins.load_plugin(str(SYNTHETIC))
        other = write_plugin(tmp_path / "other",
                             "NAME = 'synthetic'\ndef register(plugin):\n    pass\n")
        with pytest.raises(ConfigurationError, match="two plugins are named 'synthetic'"):
            plugins.load_plugin(str(other))

    def test_a_plugin_imports_its_own_modules(self, tmp_path):
        folder = write_plugin(tmp_path / "pkg", "from .helper import VALUE\n"
                              "def register(plugin):\n    plugin.add_field('x', VALUE)\n")
        (folder / "helper.py").write_text("VALUE = 'from helper'\n", encoding="utf-8")
        assert plugins.load_plugin(str(folder)).fields == {"x": "from helper"}


class TestLookups:
    def test_a_decoder_by_name_or_the_only_one(self):
        plugins.load_plugin(str(SYNTHETIC))
        named = plugins.decoder("synthetic")
        assert plugins.decoder() is named
        assert named(bytes([0xA5, 1, 0x12, 0x34, 0, 0, 7]))["sensor_id"] == "1234"

    def test_an_unknown_decoder_names_those_loaded(self):
        plugins.load_plugin(str(SYNTHETIC))
        with pytest.raises(ConfigurationError, match="no decoder 'kepler'.*synthetic"):
            plugins.decoder("kepler")

    def test_no_decoder_to_choose_says_how_to_load_one(self):
        with pytest.raises(ConfigurationError, match="--plugin"):
            plugins.decoder()

    def test_two_decoders_must_be_named(self):
        plugins.load_plugin(str(SYNTHETIC))
        plugins.load_plugin(str(KEPLER))
        with pytest.raises(ConfigurationError, match="kepler, synthetic"):
            plugins.decoder()

    def test_decode_tries_each_decoder_in_load_order(self):
        plugins.load_plugin(str(KEPLER))
        plugins.load_plugin(str(SYNTHETIC))
        assert plugins.decode(bytes([0xA5, 2, 0, 1, 0, 0, 0]))["type"] == "HELLO"
        with pytest.raises(ValueError, match="kepler: .*; synthetic: not a synthetic frame"):
            plugins.decode(b"\x00")

    def test_decode_with_nothing_loaded_is_a_value_error(self):
        with pytest.raises(ValueError, match="no decoder is loaded"):
            plugins.decode(b"\x00")

    def test_a_field_name_and_a_hook(self, registry):
        assert registry.field("reading") == "reading"
        assert plugins.hook("twf_sample", len) is len
        plugins.load_plugin(str(SYNTHETIC))
        assert registry.field("reading") == "value"
        assert plugins.hook("twf_sample")("none", 0, 0, 64) == 63

    def test_panels_with_their_plugin(self, registry):
        plugin = plugins.load_plugin(str(SYNTHETIC))
        [(owner, panel)] = registry.panels()
        assert owner is plugin and panel.scripts == ("synthetic.js",)
        assert panel.static == os.path.normpath(str(SYNTHETIC / "static"))


class TestPluginPaths:
    def test_a_register_file_by_name_or_a_path_in_the_folder(self):
        plugins.load_plugin(str(SYNTHETIC))
        regs = os.path.normpath(str(SYNTHETIC / "configs" / "synthetic_rx.regs"))
        assert plugins.resolve_plugin_path("plugin:synthetic/synthetic_rx.regs") == regs
        assert plugins.resolve_plugin_path("plugin:synthetic/configs/synthetic_rx.regs") == regs
        assert resolve_input_path("plugin:synthetic/synthetic_rx.regs") == regs

    @pytest.mark.parametrize("value, reason", [
        ("plugin:kepler/x.regs", "plugin 'kepler', which is not loaded"),
        ("plugin:synthetic/missing.regs", "has no file 'missing.regs'"),
        ("plugin:synthetic/../frames.py", "outside plugin synthetic"),
    ])
    def test_a_plugin_path_that_names_nothing_is_refused(self, value, reason):
        plugins.load_plugin(str(SYNTHETIC))
        with pytest.raises(ConfigurationError, match=reason):
            resolve_input_path(value)

    def test_plugin_folders_are_taken_from_the_declaring_file(self, tmp_path):
        assert not plugins.plugin_folders(None, str(tmp_path), "x")
        assert plugins.plugin_folders("p", str(tmp_path), "x") == (str(tmp_path / "p"),)
        absolute = str(tmp_path / "abs" / "q")
        assert plugins.plugin_folders(["../p", absolute], str(tmp_path / "d"), "x") == (
            os.path.normpath(str(tmp_path / "p")), os.path.normpath(absolute))
        with pytest.raises(ConfigurationError, match="must be a list of plugin folders"):
            plugins.plugin_folders([1], None, "bench.yaml")

    def test_a_bench_file_and_a_specification_name_plugins(self, tmp_path):
        source = str(tmp_path / "benches" / "lab.yaml")
        bench = BenchConfig.from_mapping(
            {"instruments": {"s2lp": "s2lp@sim://"}, "plugins": ["../plugins/synthetic"]},
            source=source)
        assert bench.plugins == (os.path.normpath(str(tmp_path / "plugins" / "synthetic")),)
        spec = TestSpec.from_mapping(
            {"name": "x", "plugins": ["../plugins/synthetic"],
             "tests": [{"name": "t", "steps": [{"do": "sleep", "with": {"seconds": 0}}]}]},
            source=str(tmp_path / "specs" / "x.yaml"))
        assert list(spec.plugins) == [os.path.normpath(str(tmp_path / "plugins" / "synthetic"))]


def test_no_benchtools_module_imports_a_plugin_or_a_kepler_module():
    """The bench carries no product code (#238). The simulated Kepler sensor in
    benchtools/simulated/, and the simulators' imports of it, stay until #119
    and #240."""
    offenders = []
    for path in BENCHTOOLS.rglob("*.py"):
        if "simulated" in path.relative_to(BENCHTOOLS).parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            words = line.split()
            if len(words) < 2 or words[0] not in ("import", "from"):
                continue
            module = words[1].lower()               # what is imported from, not its names
            if "simulated" in module:
                continue
            if "kepler" in module or "etb_plugins" in module:
                text = line.strip()
                offenders.append("%s:%d: %s" % (path.relative_to(ROOT).as_posix(), number, text))
    assert not offenders, "\n".join(offenders)


def synthetic_frame(frame_type, sender, repeat, value):
    return bytes([0xA5, frame_type, sender >> 8, sender & 0xFF, repeat, value >> 8, value & 0xFF])


@pytest.fixture
def kit():
    simulator = SimulatedS2lp()
    radio = S2lpDevkit(MockTransport(responder=simulator))
    radio.initialise()
    yield radio, simulator
    radio.close()


class TestActions:
    def test_dut_samples_decodes_with_the_named_decoder_and_skips_copies(self, kit):
        plugins.load_plugin(str(SYNTHETIC))
        radio, simulator = kit
        for value in (10, 20):
            for repeat in range(3):
                simulator.queue_packet(synthetic_frame(1, 0x1234, repeat, value))
        samples = radio.dut_samples("reading", source="1234", frame_type="READING",
                                    count=2, timeout=10.0, decoder="synthetic")
        assert samples.values == [10.0, 20.0]

    def test_dut_frame_with_the_only_decoder_loaded(self, kit):
        plugins.load_plugin(str(SYNTHETIC))
        radio, simulator = kit
        simulator.queue_packet(synthetic_frame(2, 0x0001, 0, 7))
        frame = radio.dut_frame("HELLO", timeout=10.0)
        assert frame["sensor_id"] == "0001" and frame["raw"] == "A5 02 00 01 00 00 07"

    def test_an_action_with_no_decoder_loaded_says_so(self, kit):
        radio, _simulator = kit
        with pytest.raises(ConfigurationError, match="--plugin"):
            radio.dut_frame("HELLO", timeout=0.1)

    def test_the_kepler_names_are_the_dut_actions_with_the_kepler_decoder(self, kit):
        plugins.load_plugin(str(KEPLER))
        radio, simulator = kit
        simulator.queue_packet(bytes.fromhex(
            "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005"))
        assert radio.kepler_frame("ALIVE", source="5C1712", timeout=10.0)["type"] == "ALIVE"
        plugins.load_plugin(str(SYNTHETIC))      # two decoders: the alias still names one
        simulator.queue_packet(bytes.fromhex(
            "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005"))
        assert radio.kepler_samples("temperature_c", count=1, timeout=10.0).count == 1


class TestRunRecords:
    SPEC = {"name": "plugged", "plugins": [str(SYNTHETIC)],
            "tests": [{"name": "t", "steps": [{"do": "sleep", "with": {"seconds": 0}}]}]}

    def run(self, tmp_path):
        log = tmp_path / "events.jsonl"
        handler = start_event_log(str(log))
        try:
            with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
                record = runner.run(TestSpec.from_mapping(self.SPEC))
        finally:
            logging.getLogger("benchtools").removeHandler(handler)
            handler.close()
        return record, [json.loads(line) for line in log.read_text().splitlines()]

    def test_the_record_and_run_start_name_each_plugin_and_its_ref(self, tmp_path):
        record, events = self.run(tmp_path)
        [plugin] = record.plugins
        assert plugin["name"] == "synthetic" and plugin["ref"]
        assert record.as_dict()["plugins"] == [plugin]
        [start] = [event for event in events if event.get("kind") == "run_start"]
        assert start["data"]["plugins"] == [plugin]

    def test_the_reports_name_the_plugin(self, tmp_path):
        record, _events = self.run(tmp_path)
        line = plugin_text(record.plugins[0])
        assert line.startswith("synthetic at ") and str(SYNTHETIC) in line
        assert "| Plugin | %s |" % line in format_markdown(record)
        junit = tmp_path / "junit.xml"
        write_junit(record, str(junit))
        assert 'name="plugin"' in junit.read_text(encoding="utf-8")

    def test_a_plugin_that_will_not_load_stops_the_run_before_it_starts(self,
                                                                       tmp_path):
        spec = dict(self.SPEC, plugins=[str(tmp_path / "nowhere")])
        with BenchRunner.from_config(BenchConfig.simulated([]), simulate=True) as runner:
            with pytest.raises(ConfigurationError, match="no plugin in"):
                runner.run(TestSpec.from_mapping(spec))

    def test_the_run_command_takes_plugin(self, tmp_path, capsys):
        spec = tmp_path / "spec.json"
        spec.write_text(json.dumps(dict(self.SPEC, plugins=[])))
        result = tmp_path / "run.json"
        assert run_main([str(spec), "--simulate", "--plugin", str(SYNTHETIC),
                         "--json", str(result)]) == 0
        assert json.loads(result.read_text())["plugins"][0]["name"] == "synthetic"
        capsys.readouterr()

    def test_the_run_command_refuses_a_plugin_that_will_not_load(self, tmp_path,
                                                                 capsys):
        spec = tmp_path / "spec.json"
        spec.write_text(json.dumps(dict(self.SPEC, plugins=[])))
        assert run_main([str(spec), "--simulate", "--plugin", str(tmp_path / "x")]) == 2
        assert "no plugin in" in capsys.readouterr().err


class TestViewer:
    def test_a_panel_is_fed_each_frame_and_viewed_by_name(self):
        plugins.load_plugin(str(SYNTHETIC))
        hub = Hub()
        hub._apply({"kind": "rf_packet", "t": 1.0, "source": "s2lp", "data": {
            "direction": "rx", "hex": synthetic_frame(1, 0x00AB, 0, 42).hex(), "length": 7}})
        assert hub.panel_view("synthetic", "00AB") == {"sensor": "00AB", "value": 42}
        assert hub.panel_view("missing") == {}

    def test_the_twf_hook_places_the_samples(self):
        plugins.load_plugin(str(SYNTHETIC))
        assert plugins.hook("twf_sample")("none", 0, 1, 4) == 2

    def test_the_api_lists_the_plugins_and_serves_their_scripts(self, tmp_path):
        plugins.load_plugin(str(SYNTHETIC))
        hub = Hub(interval=0.05).start()
        catalogue = Catalogue([], [])
        server = ViewerServer(hub, catalogue, Launcher(catalogue, str(tmp_path / "runs")))
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            def get(path):
                connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
                connection.request("GET", path, headers={"Host": "127.0.0.1:%d" % server.port})
                response = connection.getresponse()
                body = response.read()
                connection.close()
                return response.status, body
            status, body = get("/api/plugins")
            reply = json.loads(body)
            assert reply["missing"] == []
            [listed] = reply["plugins"]
            assert status == 200 and listed["name"] == "synthetic"
            assert listed["panels"] == [{"name": "synthetic",
                                         "scripts": ["/plugin/synthetic/synthetic.js"]}]
            status, body = get("/plugin/synthetic/synthetic.js")
            assert status == 200 and b"syntheticPanelLoaded" in body
            assert get("/plugin/synthetic/../frames.py")[0] == 404
            assert get("/plugin/nobody/synthetic.js")[0] == 404
            status, body = get("/api/panel?name=synthetic")
            assert status == 200 and json.loads(body) == {"latest": {}}
        finally:
            server.shutdown()
            server.server_close()
            hub.stop()

    def test_the_page_loads_the_plugin_scripts(self):
        page = (BENCHTOOLS / "viewer" / "static" / "index.html").read_text(encoding="utf-8")
        assert '<script src="/static/plugins.js"></script>' in page
        assert "kepler.js" not in page

    def test_a_run_started_from_the_page_names_its_plugins(self, tmp_path):
        bench = tmp_path / "bench.yaml"
        bench.write_text("instruments: {s2lp: s2lp@sim://}\nplugins: [p]\n")
        spec = tmp_path / "spec.json"
        spec.write_text(json.dumps(dict(TestRunRecords.SPEC, plugins=["q"])))
        assert run_plugins(str(spec), str(bench)) == [str(tmp_path / "q"), str(tmp_path / "p")]
        assert run_plugins(str(spec), None) == [str(tmp_path / "q")]


class TestS2lpCommand:
    def test_stream_takes_a_plugin_decoder(self, capsys):
        """The simulated kit hears nothing, so the stream ends with no frames."""
        s2lp_main(["-r", "sim://", "--plugin", str(SYNTHETIC), "stream",
                   "--timeout", "0.2", "--decode", "synthetic"])
        err = capsys.readouterr().err
        assert '"frames": 0' in err and "error" not in err

    def test_an_unknown_decoder_is_an_error(self, capsys):
        assert s2lp_main(["-r", "sim://", "--plugin", str(SYNTHETIC), "stream", "--timeout", "0.2",
                          "--decode", "nothing"]) == 1
        assert "no decoder 'nothing'" in capsys.readouterr().err

    def test_setup_takes_a_plugin_register_file(self, capsys):
        assert s2lp_main(["-r", "sim://", "--plugin", str(SYNTHETIC),
                          "--setup", "plugin:synthetic/synthetic_rx.regs", "info"]) == 0
        capsys.readouterr()


class TestRoundOneOfReview:
    """Findings of the first review of #304."""

    def test_two_folders_with_one_name_are_two_plugins(self, registry, tmp_path):
        one = write_plugin(tmp_path / "a" / "dev", "NAME = 'one'\nfrom .m import V\n"
                           "def register(plugin):\n    plugin.add_field('v', V)\n")
        (one / "m.py").write_text("V = 'one'\n", encoding="utf-8")
        two = write_plugin(tmp_path / "b" / "dev", "NAME = 'two'\nfrom .m import V\n"
                           "def register(plugin):\n    plugin.add_field('v', V)\n")
        (two / "m.py").write_text("V = 'two'\n", encoding="utf-8")
        assert plugins.load_plugin(str(one)).fields == {"v": "one"}
        assert plugins.load_plugin(str(two)).fields == {"v": "two"}
        assert registry.plugins["one"].module != registry.plugins["two"].module

    def test_a_plugin_that_fails_leaves_no_modules_behind(self, tmp_path):
        folder = write_plugin(tmp_path / "broken", "from .m import V\nraise RuntimeError('x')\n")
        (folder / "m.py").write_text("V = 1\n", encoding="utf-8")
        before = set(sys.modules)
        with pytest.raises(ConfigurationError):
            plugins.load_plugin(str(folder))
        assert {name for name in set(sys.modules) - before if "broken" in name} == set()

    def test_a_decoder_that_raises_anything_is_a_frame_it_cannot_read(self, tmp_path):
        folder = write_plugin(tmp_path / "rough", "def bad(payload):\n    raise KeyError(1)\n"
                              "def register(plugin):\n    plugin.add_decoder('rough', bad)\n")
        plugins.load_plugin(str(folder))
        with pytest.raises(ValueError, match="rough: 1"):
            plugins.decode(b"\x00")

    @pytest.mark.parametrize("name", ["..notes.regs", "configs/../configs/synthetic_rx.regs"])
    def test_a_name_that_only_looks_like_a_parent_stays_inside(self, name):
        plugin = plugins.load_plugin(str(SYNTHETIC))
        target = SYNTHETIC / name
        target_existed = target.exists()
        if not target_existed:
            target.write_text("# made for the test\n", encoding="utf-8")
        try:
            resolved = plugins.resolve_plugin_path("plugin:synthetic/" + name)
            assert os.path.normpath(resolved).startswith(plugin.path)
        finally:
            if not target_existed:
                target.unlink()

    def test_a_path_on_another_drive_is_outside(self):
        assert not plugins._inside("Z:\\elsewhere\\x.regs" if os.name == "nt" else "/x.regs",
                                   str(SYNTHETIC))


class TestDeprecatedKeplerNames:
    """A specification written before #238 still runs for one release."""

    def test_kepler_frame_with_no_plugin_loads_the_checkouts(self, registry, kit, caplog):
        radio, simulator = kit
        simulator.queue_packet(bytes.fromhex(
            "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005"))
        with caplog.at_level(logging.WARNING, logger="benchtools.core.plugins"):
            assert radio.kepler_frame("ALIVE", timeout=10.0)["sensor_id"] == "5C1712"
        assert registry.plugins["kepler"].path == os.path.normpath(plugins.LEGACY_KEPLER)
        assert "s2lp.kepler_frame is deprecated" in caplog.text

    def test_the_old_register_file_path_still_resolves(self, caplog, tmp_path,
                                                       monkeypatch):
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.WARNING, logger="benchtools.core.plugins"):
            found = resolve_input_path("configs/s2lp_kepler_433_rx.regs",
                                       declared_in=str(tmp_path))
        assert found == os.path.join(plugins.LEGACY_KEPLER, "configs", "s2lp_kepler_433_rx.regs")
        assert "configs/s2lp_kepler_433_rx.regs is deprecated" in caplog.text

    def test_a_loaded_kepler_plugin_is_used_as_it_is(self, registry, tmp_path):
        own = write_plugin(tmp_path / "theirs", "NAME = 'kepler'\n"
                           "def register(plugin):\n    plugin.add_decoder('kepler', len)\n")
        plugins.load_plugin(str(own))
        assert plugins.ensure_legacy_kepler("x")
        assert registry.plugins["kepler"].path == os.path.normpath(str(own))


class TestViewerWithoutThePlugins:
    def test_a_run_that_used_plugins_not_loaded_is_reported(self, caplog):
        hub = Hub()
        with caplog.at_level(logging.WARNING):
            hub._apply({"kind": "run_start", "t": 0, "data": {"plugins": [
                {"name": "kepler", "path": "/somewhere/kepler", "ref": "abc", "dirty": False}]}})
        assert [plugin["name"] for plugin in hub.plugins()["missing"]] == ["kepler"]
        assert "benchtools view --plugin /somewhere/kepler" in caplog.text

    def test_a_permuted_waveform_with_no_plugin_is_not_guessed(self):
        buffer = twf_module._Capture(2, "polynomial", 0, 0, 0.0)
        buffer.frames[(0, 0)] = [1] * 32
        assert buffer.waveform() == [None] * 64
        buffer.method = "none"
        assert buffer.waveform()[:32] != [None] * 32


class TestRoundTwoOfReview:
    """Findings of the second review of #304."""

    LEGACY_SPEC = {"name": "old", "tests": [{"name": "t", "steps": [
        {"do": "s2lp.apply_configuration",
         "with": {"source": "configs/s2lp_kepler_433_rx.regs", "reset": "defaults"}}]}]}

    def test_a_legacy_kepler_run_records_the_plugin_it_falls_back_to(self, registry, tmp_path):
        log = tmp_path / "events.jsonl"
        handler = start_event_log(str(log))
        try:
            with BenchRunner.from_config(BenchConfig.simulated({"s2lp": "s2lp"}),
                                         simulate=True) as runner:
                record = runner.run(TestSpec.from_mapping(self.LEGACY_SPEC))
        finally:
            logging.getLogger("benchtools").removeHandler(handler)
            handler.close()
        assert [plugin["name"] for plugin in record.plugins] == ["kepler"]
        [start] = [json.loads(line) for line in log.read_text().splitlines()
                   if json.loads(line).get("kind") == "run_start"]
        assert [plugin["name"] for plugin in start["data"]["plugins"]] == ["kepler"]
        assert "kepler" in registry.plugins

    def test_a_deprecated_action_is_found_in_a_specification(self):
        assert plugins.uses_legacy_kepler(["s2lp.kepler_frame"], []) == "s2lp.kepler_frame"
        assert plugins.uses_legacy_kepler(["s2lp.dut_frame"], ["x", 3]) is None

    def test_the_moved_path_comes_from_the_kepler_plugin_loaded(self, tmp_path,
                                                                monkeypatch):
        own = write_plugin(tmp_path / "theirs", "NAME = 'kepler'\ndef register(plugin):\n"
                           "    plugin.add_register_file('s2lp_kepler_433_rx.regs', 'r.regs')\n")
        (own / "r.regs").write_text("# theirs\n", encoding="utf-8")
        plugins.load_plugin(str(own))
        monkeypatch.chdir(tmp_path)
        assert resolve_input_path("configs/s2lp_kepler_433_rx.regs", str(tmp_path)) == \
            os.path.normpath(str(own / "r.regs"))

    def test_a_folder_named_in_another_case_is_the_same_plugin(self):
        if os.name != "nt":
            pytest.skip("case-insensitive paths are Windows'")
        assert plugins.load_plugin(str(SYNTHETIC).upper()) is plugins.load_plugin(str(SYNTHETIC))

    def test_a_decoder_raising_an_empty_exception_is_named_by_its_type(self, tmp_path):
        folder = write_plugin(tmp_path / "quiet", "def bad(payload):\n    raise KeyError()\n"
                              "def register(plugin):\n    plugin.add_decoder('quiet', bad)\n")
        plugins.load_plugin(str(folder))
        with pytest.raises(ValueError, match="quiet: KeyError"):
            plugins.decode(b"\x00")
