"""Reading what a build said about itself.

The manifest reader is in the core because two instruments need it and neither
should have to import the other: the dongle reads a manifest to decide whether
to refresh itself, and the debug probe reads one to say what it just flashed
onto a target. What is *not* in the core is how to produce a manifest - that is
different for each build, so the caller supplies it as a hint.

Traces to: CORE-FR-050, SWE4-UT-COREFW.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.core.firmware import MANIFEST_NAME, FirmwareBuild, parse_build_date


def write(directory: pathlib.Path, **fields) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    data = {"version": "1.4.2", "built": "2026-09-13T12:00:00Z"}
    data.update(fields)
    path = directory / MANIFEST_NAME
    path.write_text(json.dumps(data))
    return path


class TestReading:
    def test_a_manifest_by_name(self, tmp_path):
        assert FirmwareBuild.from_path(str(write(tmp_path))).version == "1.4.2"

    def test_a_directory_holding_one(self, tmp_path):
        write(tmp_path)
        assert FirmwareBuild.from_path(str(tmp_path)).version == "1.4.2"

    def test_a_build_subdirectory(self, tmp_path):
        write(tmp_path / "_build")
        assert FirmwareBuild.from_path(str(tmp_path)).version == "1.4.2"

    def test_load_passes_a_build_through_untouched(self):
        build = FirmwareBuild(version="9.9.9")
        assert FirmwareBuild.load(build) is build

    def test_load_of_nothing_is_nothing(self):
        assert FirmwareBuild.load(None) is None

    def test_the_build_date_is_parsed(self, tmp_path):
        write(tmp_path)
        built = FirmwareBuild.from_path(str(tmp_path)).built_at
        assert built is not None and built.year == 2026


class TestDiagnostics:
    def test_a_missing_manifest_names_everywhere_it_looked(self, tmp_path):
        with pytest.raises(ConfigurationError, match=MANIFEST_NAME):
            FirmwareBuild.from_path(str(tmp_path))

    def test_the_caller_supplies_how_to_produce_one(self, tmp_path):
        """The core cannot know: 'make dfu' is the dongle's answer and means
        nothing to a sensor build."""
        with pytest.raises(ConfigurationError, match="run the sensor build"):
            FirmwareBuild.from_path(str(tmp_path), hint="Then run the sensor build.")

    def test_without_a_hint_the_message_still_ends_cleanly(self, tmp_path):
        with pytest.raises(ConfigurationError) as raised:
            FirmwareBuild.from_path(str(tmp_path))
        assert not str(raised.value).endswith(" ")

    def test_a_corrupt_manifest_says_so_and_says_not_to_edit_it(self, tmp_path):
        (tmp_path / MANIFEST_NAME).write_text("{not json")
        with pytest.raises(ConfigurationError, match="rebuild rather than editing"):
            FirmwareBuild.from_path(str(tmp_path))


class TestBuildDates:
    def test_an_injected_utc_date(self):
        assert parse_build_date("2026-09-13T12:00:00Z").hour == 12

    def test_a_build_that_injected_none_is_not_a_date(self):
        """`local:` is the compiler's macros: local time, no zone. Comparing
        two of those would be comparing two timezones."""
        assert parse_build_date("local: Sep 13 2026 12:00:00") is None

    def test_nothing_is_not_a_date(self):
        assert parse_build_date("") is None
