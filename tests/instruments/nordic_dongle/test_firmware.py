"""Firmware identity: what is on the dongle against what was built.

A stale dongle produces measurements that look perfectly plausible and answer a
different question. These tests are about making that condition detectable, and
about the one subtlety that matters: two builds of the *same version* are
different firmware, which is the usual case during development.

Traces to: BLE-FR-012 .. BLE-FR-014, SWE4-UT-BLEFIRMWARE.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import (
    FirmwareBuild,
    FirmwareStatus,
    FirmwareUpdateError,
    NordicDongle,
    SimulatedDongle,
    parse_build_date,
)
from benchtools.instruments.nordic_dongle.firmware import MANIFEST_NAME, run_nrfutil

INSTALLED_VERSION = SimulatedDongle.DEFAULT_FIRMWARE_VERSION
INSTALLED_BUILT = SimulatedDongle.DEFAULT_FIRMWARE_BUILT


def write_manifest(directory, version=INSTALLED_VERSION, built=INSTALLED_BUILT,
                   package="nordic_dongle_dfu.zip", make_package=True):
    """Write a manifest of the shape the firmware build produces."""
    directory = pathlib.Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MANIFEST_NAME).write_text(json.dumps({
        "version": version,
        "built": built,
        "protocol": "1.1",
        "model": "PCA10059",
        "hex": "nordic_dongle_pca10059.hex",
        "package": package,
        "sha256": "0" * 64,
    }))
    if make_package and package:
        (directory / package).write_bytes(b"PK\x03\x04 not really a zip")
    return directory


class TestBuildDates:
    def test_an_iso_instant(self):
        parsed = parse_build_date("2026-09-13T12:00:00Z")
        assert parsed is not None
        assert parsed.year == 2026 and parsed.hour == 12

    def test_an_offset_is_normalised_to_utc(self):
        assert parse_build_date("2026-09-13T14:00:00+02:00").hour == 12

    def test_a_compiler_date_is_not_an_instant(self):
        """__DATE__ is local time in an awkward format; claiming otherwise
        would let two dongles in different timezones compare equal."""
        assert parse_build_date("local:Sep 13 2026 14:22:31") is None

    @pytest.mark.parametrize("text", ["", "   ", "yesterday", "2026-09-13T12:00:00"])
    def test_anything_else_is_unknown(self, text):
        assert parse_build_date(text) is None


class TestLoadingABuild:
    def test_from_a_manifest(self, tmp_path):
        write_manifest(tmp_path)
        build = FirmwareBuild.from_path(str(tmp_path / MANIFEST_NAME))
        assert build.version == INSTALLED_VERSION
        assert build.built == INSTALLED_BUILT
        assert build.has_package

    def test_from_a_directory(self, tmp_path):
        write_manifest(tmp_path)
        assert FirmwareBuild.from_path(str(tmp_path)).version == INSTALLED_VERSION

    def test_from_a_project_directory_with_a_build_subdirectory(self, tmp_path):
        """What a bench configuration usually names: the firmware directory."""
        write_manifest(tmp_path / "_build")
        assert FirmwareBuild.from_path(str(tmp_path)).version == INSTALLED_VERSION

    def test_the_package_path_is_resolved_beside_the_manifest(self, tmp_path):
        write_manifest(tmp_path)
        build = FirmwareBuild.from_path(str(tmp_path))
        assert pathlib.Path(build.package).parent == tmp_path

    def test_a_missing_manifest_says_how_to_produce_one(self, tmp_path):
        with pytest.raises(ConfigurationError, match="make manifest"):
            FirmwareBuild.from_path(str(tmp_path))

    def test_a_corrupt_manifest_is_reported(self, tmp_path):
        (tmp_path / MANIFEST_NAME).write_text("{not json")
        with pytest.raises(ConfigurationError, match="not valid JSON"):
            FirmwareBuild.from_path(str(tmp_path))

    def test_a_missing_package_is_reported_only_when_needed(self, tmp_path):
        """Checking the firmware does not need the package; flashing does."""
        write_manifest(tmp_path, make_package=False)
        build = FirmwareBuild.from_path(str(tmp_path))
        assert build.has_package is False
        with pytest.raises(ConfigurationError, match="make dfu"):
            build.require_package()

    def test_load_passes_through_a_build_and_none(self, tmp_path):
        write_manifest(tmp_path)
        build = FirmwareBuild.from_path(str(tmp_path))
        assert FirmwareBuild.load(build) is build
        assert FirmwareBuild.load(None) is None

    def test_it_renders_readably(self, tmp_path):
        write_manifest(tmp_path)
        assert INSTALLED_VERSION in str(FirmwareBuild.from_path(str(tmp_path)))


class TestStatus:
    def status(self, installed=INSTALLED_VERSION, installed_built=INSTALLED_BUILT,
               expected=INSTALLED_VERSION, expected_built=INSTALLED_BUILT, compared=True):
        return FirmwareStatus(
            installed_version=installed, installed_built=installed_built,
            expected_version=expected, expected_built=expected_built, compared=compared,
        )

    def test_a_matching_build(self):
        status = self.status()
        assert status.matches and status.version_matches and status.date_matches
        assert status.is_older is False

    def test_a_different_version(self):
        status = self.status(installed="1.0.0")
        assert status.matches is False and status.version_matches is False

    def test_the_same_version_rebuilt_is_a_mismatch(self):
        """The case that matters: comparing versions alone would call this
        dongle up to date."""
        status = self.status(installed_built="2026-09-01T08:00:00Z")
        assert status.version_matches is True
        assert status.date_matches is False
        assert status.matches is False
        assert status.is_older is True

    def test_a_dongle_newer_than_the_build(self):
        """Someone flashed from another checkout: not older, still wrong."""
        status = self.status(installed_built="2026-12-01T08:00:00Z")
        assert status.matches is False
        assert status.is_older is False

    def test_an_unknown_date_cannot_be_ordered(self):
        """None, not False: an unknown is not the same answer as "no"."""
        status = self.status(installed_built="local:Sep 1 2026 08:00:00")
        assert status.is_older is None
        assert status.matches is False

    def test_nothing_to_compare_against(self):
        status = self.status(compared=False, expected="", expected_built="")
        assert status.matches is False
        assert "nothing to compare" in status.describe()

    def test_the_description_names_both_builds(self):
        text = self.status(installed="1.0.0").describe()
        assert "1.0.0" in text and INSTALLED_VERSION in text

    def test_as_dict_is_assertable_by_a_specification(self):
        summary = self.status().as_dict()
        assert summary["matches"] is True
        assert summary["version_matches"] is True
        assert summary["date_matches"] is True
        assert summary["compared"] is True


class TestTheDongleReportsItsBuild:
    def test_version_and_date(self, dongle):
        assert dongle.firmware_version == INSTALLED_VERSION
        assert dongle.firmware_built == INSTALLED_BUILT
        assert dongle.firmware_built_at is not None

    def test_the_identity_carries_the_build_not_the_protocol(self, dongle):
        """A report reader needs to know which firmware produced the numbers."""
        identity = dongle.identify()
        assert INSTALLED_VERSION in identity.firmware
        assert INSTALLED_BUILT in identity.firmware
        assert "fw=" in identity.raw

    def test_the_protocol_is_reported_separately(self, dongle):
        assert dongle.protocol_version == "1.1"
        assert dongle.protocol_is_compatible is True


class TestProtocolCompatibility:
    def test_a_different_minor_version_is_survivable(self, simulator, caplog):
        """One side lacks commands the other has; those fail individually."""
        simulator.protocol = "1.9"
        instrument = NordicDongle(MockTransport(responder=simulator))
        instrument.initialise()
        assert instrument.protocol_is_compatible is True
        instrument.close()

    def test_a_different_major_version_is_refused(self, simulator):
        simulator.protocol = "2.0"
        instrument = NordicDongle(MockTransport(responder=simulator))
        with pytest.raises(InstrumentError, match="not compatible"):
            instrument.initialise()

    def test_an_incompatible_dongle_can_still_be_reached_to_update_it(self, tmp_path):
        """Refusing to talk to it would mean refusing to fix it."""
        write_manifest(tmp_path)
        simulator = SimulatedDongle()
        simulator.protocol = "0.9"
        instrument = NordicDongle(MockTransport(responder=simulator))
        instrument._allow_incompatible_protocol = True
        instrument.initialise()
        assert instrument.protocol_is_compatible is False
        instrument.close()


class TestChecking:
    def test_against_a_matching_build(self, dongle, tmp_path):
        write_manifest(tmp_path)
        status = dongle.check_firmware(str(tmp_path))
        assert status.matches is True
        assert status.compared is True

    def test_against_a_newer_build(self, dongle, tmp_path):
        write_manifest(tmp_path, version="1.2.0", built="2026-10-01T09:00:00Z")
        status = dongle.check_firmware(str(tmp_path))
        assert status.matches is False
        assert status.is_older is True
        assert status.package is not None

    def test_with_nothing_configured(self, dongle):
        status = dongle.check_firmware()
        assert status.compared is False
        assert status.installed_version == INSTALLED_VERSION
        assert "no expected build" in status.reason

    def test_the_build_can_be_set_after_connecting(self, dongle, tmp_path):
        write_manifest(tmp_path)
        dongle.expect_firmware(str(tmp_path))
        assert dongle.expected_firmware.version == INSTALLED_VERSION
        assert dongle.check_firmware().matches is True

    def test_connect_can_take_the_build(self, tmp_path):
        write_manifest(tmp_path)
        with NordicDongle.connect("sim://", firmware=str(tmp_path)) as instrument:
            assert instrument.check_firmware().matches is True

    def test_connect_can_require_it(self, tmp_path):
        write_manifest(tmp_path, version="9.9.9")
        with pytest.raises(InstrumentError, match="not running the expected firmware"):
            NordicDongle.connect("sim://", firmware=str(tmp_path), require_firmware=True)

    def test_requiring_it_passes_when_it_matches(self, tmp_path):
        write_manifest(tmp_path)
        with NordicDongle.connect("sim://", firmware=str(tmp_path),
                                  require_firmware=True) as instrument:
            assert instrument.firmware_version == INSTALLED_VERSION


class TestUpdating:
    def flasher_for(self, simulator, build):
        """A flasher that does what nrfutil would: the dongle comes back new."""
        calls = []

        def flash(package, port):
            calls.append((package, port))
            simulator.apply_update(build.version, build.built)
            return "Device programmed."

        flash.calls = calls
        return flash

    def test_an_out_of_date_dongle_is_refreshed(self, dongle, simulator, tmp_path):
        write_manifest(tmp_path, version="1.2.0", built="2026-10-01T09:00:00Z")
        build = FirmwareBuild.from_path(str(tmp_path))
        flash = self.flasher_for(simulator, build)

        status = dongle.ensure_firmware(build, settle=0.0, flasher=flash)

        assert status.matches is True
        assert status.updated is True
        assert dongle.firmware_version == "1.2.0"
        assert len(flash.calls) == 1
        assert flash.calls[0][0].endswith("nordic_dongle_dfu.zip")

    def test_the_dongle_is_asked_into_its_bootloader_first(self, dongle, simulator, tmp_path):
        write_manifest(tmp_path, version="1.2.0", built="2026-10-01T09:00:00Z")
        build = FirmwareBuild.from_path(str(tmp_path))
        dongle.update_firmware(build, settle=0.0, flasher=self.flasher_for(simulator, build))
        assert simulator.dfu_requests == 1

    def test_a_dongle_already_up_to_date_is_left_alone(self, dongle, simulator, tmp_path):
        write_manifest(tmp_path)
        build = FirmwareBuild.from_path(str(tmp_path))
        flash = self.flasher_for(simulator, build)
        status = dongle.ensure_firmware(build, settle=0.0, flasher=flash)
        assert status.matches is True
        assert status.updated is False
        assert flash.calls == []
        assert simulator.dfu_requests == 0

    def test_a_flash_that_does_not_take_is_reported(self, dongle, simulator, tmp_path):
        """"The tool said success" is not the same fact as "the dongle runs it"."""
        write_manifest(tmp_path, version="1.2.0", built="2026-10-01T09:00:00Z")
        build = FirmwareBuild.from_path(str(tmp_path))

        def useless(package, port):
            # The dongle comes back out of its bootloader, as it would after a
            # real flash - but running what it ran before.
            simulator.apply_update(INSTALLED_VERSION, INSTALLED_BUILT)
            return "Device programmed."

        with pytest.raises(FirmwareUpdateError, match="was flashed but is running"):
            dongle.update_firmware(build, settle=0.0, flasher=useless)

    def test_updating_without_a_package(self, dongle, tmp_path):
        write_manifest(tmp_path, version="1.2.0", make_package=False)
        with pytest.raises(ConfigurationError, match="make dfu"):
            dongle.update_firmware(str(tmp_path), settle=0.0, flasher=lambda p, q: "")

    def test_updating_without_a_build(self, dongle):
        with pytest.raises(ConfigurationError, match="nothing to flash"):
            dongle.update_firmware(settle=0.0, flasher=lambda p, q: "")

    def test_ensure_can_refuse_to_update(self, dongle, tmp_path):
        write_manifest(tmp_path, version="1.2.0", built="2026-10-01T09:00:00Z")
        with pytest.raises(InstrumentError, match="updating was not permitted"):
            dongle.ensure_firmware(str(tmp_path), update=False)

    def test_ensure_with_nothing_to_compare_does_nothing(self, dongle):
        status = dongle.ensure_firmware()
        assert status.compared is False
        assert status.updated is False

    def test_the_update_is_noted_in_the_session_log(self, dongle, simulator, tmp_path):
        write_manifest(tmp_path, version="1.2.0", built="2026-10-01T09:00:00Z")
        build = FirmwareBuild.from_path(str(tmp_path))
        log = tmp_path / "session.log"
        dongle.start_log(str(log))
        dongle.update_firmware(build, settle=0.0, flasher=self.flasher_for(simulator, build))
        text = log.read_text()
        assert "updating firmware to 1.2.0" in text
        assert "firmware updated" in text


class TestFlashingTool:
    def test_a_missing_nrfutil_says_how_to_get_it(self, monkeypatch, tmp_path):
        import benchtools.instruments.nordic_dongle.firmware as module

        def missing(*args, **kwargs):
            raise FileNotFoundError("nrfutil")

        monkeypatch.setattr(module.subprocess, "run", missing)
        with pytest.raises(FirmwareUpdateError, match="pip install nrfutil"):
            run_nrfutil(str(tmp_path / "p.zip"), "COM5")

    def test_a_failing_nrfutil_carries_its_output(self, monkeypatch, tmp_path):
        import benchtools.instruments.nordic_dongle.firmware as module

        class Finished:
            returncode = 1
            stdout = "Opening serial port.\n"
            stderr = "Timed out waiting for acknowledgement.\n"

        monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: Finished())
        with pytest.raises(FirmwareUpdateError, match="Timed out waiting"):
            run_nrfutil(str(tmp_path / "p.zip"), "COM5")

    def test_a_successful_run_returns_its_output(self, monkeypatch, tmp_path):
        import benchtools.instruments.nordic_dongle.firmware as module

        class Finished:
            returncode = 0
            stdout = "Device programmed.\n"
            stderr = ""

        monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: Finished())
        assert "programmed" in run_nrfutil(str(tmp_path / "p.zip"), "COM5")
