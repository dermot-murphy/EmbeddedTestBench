"""Input files named by a relative path, and which driver arguments are files.

Traces to: RUN-FR-007, RUN-FR-017, CORE-DD-PATHS, SWE4-UT-PATHS.
"""

from __future__ import annotations

import os

import pytest

from benchtools.core import paths
from benchtools.core.errors import ConfigurationError
from benchtools.core.paths import (
    input_path_names,
    input_paths,
    resolve_arguments,
    resolve_input_path,
    search_locations,
)
from benchtools.instruments.gpd3303d import Gpd3303D
from benchtools.instruments.jlink import JLinkProbe, JLinkRttReader
from benchtools.instruments.nordic_dongle import NordicDongle
from benchtools.instruments.pico_sht30 import PicoSht30
from benchtools.instruments.s2lp import S2lpDevkit
from benchtools.instruments.tek3014b import Tek3014B
from benchtools.instruments.tti1604 import Tti1604


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """A declaring directory, a working directory and a checkout, all apart."""
    declared = tmp_path / "declared"
    work = tmp_path / "work"
    checkout = tmp_path / "checkout"
    for directory in (declared, work, checkout):
        directory.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(paths, "TESTTOOLS_ROOT", str(checkout))
    return declared, work, checkout


class TestResolveInputPath:
    def test_beside_the_declaring_file_is_searched_first(self, layout):
        declared, work, _ = layout
        (declared / "a.regs").write_text("x")
        (work / "a.regs").write_text("x")
        assert resolve_input_path("a.regs", str(declared)) == str(declared / "a.regs")

    def test_the_working_directory_is_searched_second(self, layout):
        declared, work, checkout = layout
        (work / "a.regs").write_text("x")
        (checkout / "a.regs").write_text("x")
        assert resolve_input_path("a.regs", str(declared)) == str(work / "a.regs")

    def test_the_checkout_is_searched_last(self, layout):
        declared, _, checkout = layout
        (checkout / "configs").mkdir()
        (checkout / "configs" / "a.regs").write_text("x")
        assert (resolve_input_path("configs/a.regs", str(declared))
                == str(checkout / "configs" / "a.regs"))

    def test_a_directory_is_found_as_well_as_a_file(self, layout):
        declared, _, _ = layout
        (declared / "build").mkdir()
        assert resolve_input_path("build", str(declared)) == str(declared / "build")

    def test_no_declaring_file_searches_the_other_two(self, layout):
        _, work, _ = layout
        (work / "a.regs").write_text("x")
        assert resolve_input_path("a.regs", None) == str(work / "a.regs")

    def test_an_absolute_path_is_used_as_given(self, layout, tmp_path):
        missing = str(tmp_path / "nowhere" / "a.regs")
        assert resolve_input_path(missing, str(layout[0])) == missing

    @pytest.mark.parametrize("value", [None, "", 1, b"bytes", object()])
    def test_anything_but_a_path_is_passed_through(self, layout, value):
        assert resolve_input_path(value, str(layout[0])) is value

    def test_a_missing_file_names_every_location_tried(self, layout):
        declared, work, checkout = layout
        with pytest.raises(ConfigurationError) as caught:
            resolve_input_path("a.regs", str(declared), what="s2lp.apply_configuration source")
        message = str(caught.value)
        assert "s2lp.apply_configuration source" in message
        for base in (declared, work, checkout):
            assert str(base / "a.regs") in message

    def test_a_missing_file_can_be_left_to_the_driver(self, layout):
        assert resolve_input_path("a.regs", str(layout[0]), required=False) == "a.regs"

    def test_locations_are_not_repeated(self, layout, monkeypatch):
        declared, _, _ = layout
        monkeypatch.chdir(declared)
        locations = search_locations("a.regs", str(declared))
        assert len(locations) == len(set(locations)) == 2


class TestResolveArguments:
    def test_only_declared_names_are_resolved(self, layout):
        declared, _, _ = layout
        (declared / "log.txt").write_text("x")
        resolved = resolve_arguments({"source": "log.txt", "path": "log.txt"},
                                     ("source",), str(declared))
        assert resolved == {"source": str(declared / "log.txt"), "path": "log.txt"}

    def test_the_arguments_given_are_not_changed(self, layout):
        declared, _, _ = layout
        (declared / "a.regs").write_text("x")
        given = {"source": "a.regs"}
        resolve_arguments(given, ("source",), str(declared))
        assert given == {"source": "a.regs"}

    def test_a_declared_name_that_is_not_given_is_ignored(self, layout):
        assert not resolve_arguments({}, ("source",), str(layout[0]))


class TestDeclaration:
    def test_a_function_carries_its_mark(self):
        @input_paths("source")
        def load(source):
            return source
        assert input_path_names(load) == ("source",)
        assert load("x") == "x"

    def test_an_unmarked_function_declares_nothing(self):
        assert not input_path_names(len)

    def test_a_mark_survives_classmethod_and_staticmethod(self):
        class Driver:
            @classmethod
            @input_paths("firmware")
            def connect(cls, firmware=None):
                return firmware

            @staticmethod
            @input_paths("source")
            def load(source):
                return source

            @input_paths("path")
            def verify(self, path=None):
                return path

        assert input_path_names(Driver.connect) == ("firmware",)
        assert input_path_names(Driver.load) == ("source",)
        assert input_path_names(Driver().load) == ("source",)
        assert input_path_names(Driver().verify) == ("path",)


class TestEveryDriverDeclaresItsInputFiles:
    """The inventory in issue #116, held where it cannot drift from the code.

    An output path - a log, a report, a screenshot - is deliberately absent:
    it is written relative to the working directory, as it always was.
    """

    @pytest.mark.parametrize("member, names", [
        (JLinkProbe.connect, ("elf", "firmware")),
        (JLinkRttReader.connect, ("elf", "firmware")),
        (JLinkProbe.load_symbols, ("elf",)),
        (JLinkProbe.flash, ("path",)),
        (JLinkProbe.image_build, ("path",)),
        (JLinkProbe.verify, ("path",)),
        (NordicDongle.connect, ("firmware",)),
        (NordicDongle.expect_firmware, ("firmware",)),
        (NordicDongle.check_firmware, ("firmware",)),
        (NordicDongle.update_firmware, ("firmware",)),
        (NordicDongle.ensure_firmware, ("firmware",)),
        (NordicDongle.run_script, ("source",)),
        (S2lpDevkit.load_configuration, ("source",)),
        (S2lpDevkit.apply_configuration, ("source",)),
        (S2lpDevkit.verify_configuration, ("source",)),
    ], ids=lambda value: getattr(value, "__qualname__", None) or "-".join(value))
    def test_declared(self, member, names):
        assert input_path_names(member) == names

    @pytest.mark.parametrize("member", [
        S2lpDevkit.start_log, S2lpDevkit.save_configuration, S2lpDevkit.measure_preamble,
        NordicDongle.start_log, NordicDongle.measure_response_time,
        JLinkProbe.rtt_start, Tek3014B.save_csv, Tek3014B.screenshot,
        Tek3014B.configure_edge_trigger,
    ], ids=lambda member: member.__qualname__)
    def test_an_output_or_a_channel_is_not_a_file_to_find(self, member):
        assert not input_path_names(member)

    @pytest.mark.parametrize("driver", [Gpd3303D, Tti1604, Tek3014B, PicoSht30],
                             ids=lambda driver: driver.__name__)
    def test_a_driver_that_reads_no_file_declares_none(self, driver):
        declared = [
            name for name in dir(driver)
            if not name.startswith("_") and input_path_names(getattr(driver, name, None))
        ]
        assert declared == []


def test_the_checkout_is_where_the_shipped_configurations_are():
    assert os.path.isdir(os.path.join(paths.TESTTOOLS_ROOT, "configs"))
