"""Register values read from a file, applied and verified.

The file ends up written to a radio, so the parser's job is to be forgiving
about punctuation and unforgiving about content. These tests are mostly about
the second half: every way a file can be wrong should name the file and the
line rather than produce a radio configured almost right.

Traces to: S2LP-FR-017 .. S2LP-FR-019, SWE4-UT-S2LPCONFIG.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError
from benchtools.instruments.s2lp import registers as reg
from benchtools.instruments.s2lp.configuration import (
    RegisterConfiguration,
    format_register_file,
    load_register_file,
    parse_register_file,
)

BASIC = """\
# 915 MHz, basic packets
PCKTCTRL3   0xC0
PCKTCTRL2 = 0x01
MOD2: 27
"""


def write(tmp_path, text, name="config.regs"):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


class TestParsingWhatPeopleWrite:
    def test_a_plain_file(self):
        configuration = parse_register_file(BASIC, source="c.regs")
        assert configuration.names == ["PCKTCTRL3", "PCKTCTRL2", "MOD2"]
        assert configuration.as_map() == {0x2E: 0xC0, 0x2F: 0x01, 0x10: 0x27}

    @pytest.mark.parametrize(
        "line",
        ["PCKTCTRL3 0xC0", "PCKTCTRL3=0xC0", "PCKTCTRL3 = 0xC0",
         "PCKTCTRL3:0xC0", "PCKTCTRL3, 0xC0", "  PCKTCTRL3\t0xC0  "],
    )
    def test_the_separator_can_be_any_of_the_usual_ones(self, line):
        assert parse_register_file(line).as_map() == {0x2E: 0xC0}

    def test_a_value_is_hexadecimal_with_or_without_the_prefix(self):
        """A register file carries hex. Reading 10 as ten in one file and
        sixteen in the next is the ambiguity this avoids."""
        assert parse_register_file("PCKTCTRL3 C0").as_map() == {0x2E: 0xC0}
        assert parse_register_file("PCKTCTRL3 10").as_map() == {0x2E: 0x10}

    def test_a_register_can_be_named_by_address(self):
        assert parse_register_file("0x2E 0xC0").as_map() == {0x2E: 0xC0}
        assert parse_register_file("46 0xC0").as_map() == {0x2E: 0xC0}

    def test_names_are_case_insensitive(self):
        assert parse_register_file("pcktctrl3 c0").names == ["PCKTCTRL3"]

    @pytest.mark.parametrize("marker", ["#", ";", "//"])
    def test_comments_on_their_own_line_and_after_a_value(self, marker):
        text = "%s a heading\nPCKTCTRL3 0xC0 %s why\n" % (marker, marker)
        assert parse_register_file(text).as_map() == {0x2E: 0xC0}

    def test_blank_lines_are_ignored(self):
        assert len(parse_register_file("\n\nPCKTCTRL3 0xC0\n\n")) == 1

    def test_the_file_s_order_is_kept(self):
        """Some settings only take effect written after another, so a file that
        works should be applied the way it was written."""
        text = "MOD2 27\nPCKTCTRL3 C0\nPCKTCTRL2 01\n"
        assert parse_register_file(text).names == ["MOD2", "PCKTCTRL3", "PCKTCTRL2"]


class TestRefusingWhatIsWrong:
    def test_an_unknown_register_names_the_line(self):
        with pytest.raises(ConfigurationError, match="line 2.*NOTAREG"):
            parse_register_file("PCKTCTRL3 C0\nNOTAREG 01\n", source="c.regs")

    def test_a_line_that_is_not_a_setting_says_what_was_expected(self):
        with pytest.raises(ConfigurationError, match="PCKTCTRL3 0x20"):
            parse_register_file("PCKTCTRL3\n")

    def test_a_value_too_big_for_a_register(self):
        with pytest.raises(ConfigurationError, match="one byte"):
            parse_register_file("PCKTCTRL3 0x1FF")

    def test_a_value_that_is_not_a_number_is_refused_with_the_line(self):
        """It cannot be read as a value at all, so it is reported as a line
        that is not a setting - which is what it is."""
        with pytest.raises(ConfigurationError, match="PCKTCTRL3 = zz"):
            parse_register_file("PCKTCTRL3 = zz")

    def test_a_value_that_looks_hexadecimal_but_is_too_wide(self):
        """'dead' is a perfectly good hex number and not a register value."""
        with pytest.raises(ConfigurationError, match="one byte"):
            parse_register_file("PCKTCTRL3 dead")

    def test_a_read_only_register_cannot_be_set_by_a_file(self):
        """The radio would ignore the write and read back its own value, which
        looks like the file not having been applied."""
        with pytest.raises(ConfigurationError, match="read-only"):
            parse_register_file("MC_STATE0 0x01")

    def test_a_register_set_twice_is_ambiguous_not_last_wins(self):
        with pytest.raises(ConfigurationError, match="already set on line 1"):
            parse_register_file("PCKTCTRL3 C0\nPCKTCTRL3 20\n")

    def test_the_error_names_the_file(self):
        with pytest.raises(ConfigurationError, match="radio.regs line 1"):
            parse_register_file("NOTAREG 01", source="radio.regs")


class TestLoadingFromDisk:
    def test_a_file(self, tmp_path):
        configuration = load_register_file(write(tmp_path, BASIC))
        assert len(configuration) == 3
        assert configuration.source.endswith("config.regs")

    def test_a_missing_file(self, tmp_path):
        with pytest.raises(ConfigurationError, match="cannot read"):
            load_register_file(str(tmp_path / "absent.regs"))

    def test_an_empty_file_is_refused(self, tmp_path):
        """It would be applied and verified without doing anything, and without
        saying so."""
        with pytest.raises(ConfigurationError, match="names no registers"):
            load_register_file(write(tmp_path, "# nothing but a comment\n"))


class TestTheConfigurationObject:
    def test_it_describes_itself_with_fields_decoded(self):
        text = parse_register_file(BASIC).describe()
        assert "PCKTCTRL3" in text and "PCKT_FRMT=3" in text

    def test_a_value_can_be_looked_up_by_name_or_address(self):
        configuration = parse_register_file(BASIC)
        assert configuration.get("PCKTCTRL3") == 0xC0
        assert configuration.get(0x2E) == 0xC0
        assert configuration.get("GPIO0_CONF") is None

    def test_it_serialises_for_a_report(self):
        summary = parse_register_file(BASIC, source="c.regs").as_dict()
        assert summary["count"] == 3
        assert summary["settings"][0]["name"] == "PCKTCTRL3"
        assert summary["settings"][0]["fields"]["PCKT_FRMT"] == 3

    def test_an_empty_configuration_is_falsey(self):
        assert not RegisterConfiguration()


class TestWritingAFileBack:
    def test_it_round_trips(self):
        values = {0x2E: 0xC0, 0x2F: 0x01, 0x10: 0x27}
        text = format_register_file(values, title="captured")
        assert parse_register_file(text).as_map() == values

    def test_read_only_registers_are_left_out(self):
        """A file naming one cannot be applied, and a captured configuration
        that cannot be applied is a trap rather than a record."""
        text = format_register_file({0x8E: 0x01, 0x2E: 0xC0})
        assert "MC_STATE0" not in text
        assert "PCKTCTRL3" in text

    def test_only_changed_leaves_out_what_is_at_reset(self):
        values = {register.address: register.reset for register in reg.REGISTERS}
        values[0x2E] = 0xC0
        text = format_register_file(values, only_changed=True)
        assert "PCKTCTRL3" in text
        assert "GPIO0_CONF" not in text

    def test_the_title_becomes_a_comment(self):
        assert format_register_file({0x2E: 0xC0}, title="from the GUI").startswith("# from the GUI")


class TestApplyingToARadio:
    def test_apply_writes_every_setting(self, radio, tmp_path):
        radio.apply_configuration(write(tmp_path, BASIC))
        assert radio.read_register("PCKTCTRL3") == 0xC0
        assert radio.read_register("MOD2") == 0x27

    def test_apply_verifies_by_default(self, radio, tmp_path, simulator):
        """A write is acknowledged by the firmware, not by the radio: "the
        command was accepted" and "the register holds the value" differ."""
        path = write(tmp_path, BASIC)
        original = simulator._cmd_sdkevalspiwriteregisters
        simulator._cmd_sdkevalspiwriteregisters = lambda arguments: original(["0x00", "{00}"])
        with pytest.raises(InstrumentError, match="did not take the configuration"):
            radio.apply_configuration(path)

    def test_apply_can_skip_verifying(self, radio, tmp_path):
        check = radio.apply_configuration(write(tmp_path, BASIC), verify=False)
        assert check.checked == 3

    def test_consecutive_registers_are_written_together(self, radio, tmp_path, simulator):
        """PCKTCTRL3 and PCKTCTRL2 are adjacent, so they go in one command."""
        before = len(simulator.command_log)
        radio.apply_configuration(write(tmp_path, "PCKTCTRL3 C0\nPCKTCTRL2 01\n"), verify=False)
        writes = [line for line in simulator.command_log[before:]
                  if line.startswith("SdkEvalSpiWriteRegisters")]
        assert len(writes) == 1

    def test_a_configuration_object_can_be_applied_directly(self, radio):
        radio.apply_configuration(parse_register_file(BASIC, source="<memory>"))
        assert radio.read_register("PCKTCTRL3") == 0xC0


class TestStartingFromAKnownState:
    """A partial file applied onto whatever was there before is not
    deterministic. These cover the reset that makes it so.

    Traces to: S2LP-FR-021.
    """

    def test_by_default_nothing_is_reset(self, radio, tmp_path):
        """Applying a configuration writes what the file names. Wiping 123
        registers is a bigger action than applying three, and is asked for."""
        radio.write_register("GPIO0_CONF", 0x55)
        radio.apply_configuration(write(tmp_path, BASIC))
        assert radio.read_register("GPIO0_CONF") == 0x55

    def test_reset_defaults_clears_what_a_previous_test_left(self, radio, tmp_path):
        radio.write_register("GPIO0_CONF", 0x55)
        radio.apply_configuration(write(tmp_path, BASIC), reset="defaults")
        assert radio.read_register("GPIO0_CONF") == reg.BY_NAME["GPIO0_CONF"].reset

    def test_and_the_file_is_still_applied_on_top(self, radio, tmp_path):
        radio.write_register("GPIO0_CONF", 0x55)
        radio.apply_configuration(write(tmp_path, BASIC), reset="defaults")
        assert radio.read_register("PCKTCTRL3") == 0xC0

    def test_so_a_strict_check_afterwards_means_something(self, radio, tmp_path):
        """This is the pairing a test wants: reset, apply, then assert that the
        radio holds the file and nothing else."""
        path = write(tmp_path, BASIC)
        radio.write_register("GPIO0_CONF", 0x55)
        radio.apply_configuration(path, reset="defaults")
        assert radio.verify_configuration(path, strict=True).matches

    def test_true_means_defaults(self, radio, tmp_path):
        radio.write_register("GPIO0_CONF", 0x55)
        radio.apply_configuration(write(tmp_path, BASIC), reset=True)
        assert radio.read_register("GPIO0_CONF") == reg.BY_NAME["GPIO0_CONF"].reset

    def test_reset_power_takes_the_radio_through_shutdown(self, radio, tmp_path, simulator):
        radio.write_register("GPIO0_CONF", 0x55)
        radio.apply_configuration(write(tmp_path, BASIC), reset="power")
        assert "SdkEvalSdn 1" in simulator.command_log
        assert radio.read_register("GPIO0_CONF") == reg.BY_NAME["GPIO0_CONF"].reset
        assert radio.read_register("PCKTCTRL3") == 0xC0

    @pytest.mark.parametrize("mode", ["sres", "yes", "hard", 2])
    def test_an_unknown_reset_mode_lists_the_real_ones(self, radio, tmp_path, mode):
        with pytest.raises(ConfigurationError, match="none, defaults, power"):
            radio.apply_configuration(write(tmp_path, BASIC), reset=mode)

    def test_a_reset_that_did_not_take_stops_before_writing(self, radio, tmp_path, simulator):
        """"The reset was commanded" and "the radio is at defaults" are
        different facts, and the file is written on top of the second one."""
        original = simulator._cmd_sdkevalsdn
        simulator._cmd_sdkevalsdn = lambda arguments: original(["0"])   # never shuts down
        radio.write_register("GPIO0_CONF", 0x55)
        with pytest.raises(InstrumentError, match="not in the state a power reset leaves"):
            radio.apply_configuration(write(tmp_path, BASIC), reset="power")
        assert radio.read_register("PCKTCTRL3") == reg.BY_NAME["PCKTCTRL3"].reset

    def test_the_failure_names_what_is_not_at_its_default(self, radio, tmp_path, simulator):
        original = simulator._cmd_sdkevalsdn
        simulator._cmd_sdkevalsdn = lambda arguments: original(["0"])
        radio.write_register("GPIO0_CONF", 0x55)
        with pytest.raises(InstrumentError, match=r"GPIO0_CONF = 0x55 \(expected 0x0A\)"):
            radio.apply_configuration(write(tmp_path, BASIC), reset="power")


class TestVerifyingAgainstARadio:
    def test_a_radio_that_matches(self, radio, tmp_path):
        path = write(tmp_path, BASIC)
        radio.apply_configuration(path)
        check = radio.verify_configuration(path)
        assert check.matches
        assert check.checked == 3
        assert "3 register(s) match" in check.describe()

    def test_a_radio_that_does_not(self, radio, tmp_path):
        check = radio.verify_configuration(write(tmp_path, BASIC))
        assert not check.matches
        assert set(check.mismatches) == {"PCKTCTRL3", "PCKTCTRL2", "MOD2"}
        assert check.mismatches["PCKTCTRL3"] == (0xC0, 0x20)
        assert "expected 0xC0, read 0x20" in check.describe()

    def test_a_loose_check_ignores_what_the_file_does_not_name(self, radio, tmp_path):
        """The file states what the test requires; the rest is not its
        business."""
        path = write(tmp_path, BASIC)
        radio.apply_configuration(path)
        radio.write_register("GPIO0_CONF", 0x55)
        assert radio.verify_configuration(path).matches

    def test_a_strict_check_does_not(self, radio, tmp_path):
        """Which is what catches a setting left behind by whatever ran
        before."""
        path = write(tmp_path, BASIC)
        radio.apply_configuration(path)
        radio.write_register("GPIO0_CONF", 0x55)
        check = radio.verify_configuration(path, strict=True)
        assert not check.matches
        assert check.unexpected["GPIO0_CONF"] == (0x0A, 0x55)
        assert "not named by the file" in check.describe()

    def test_a_strict_check_on_a_clean_radio_passes(self, radio, tmp_path):
        path = write(tmp_path, BASIC)
        radio.apply_configuration(path)
        check = radio.verify_configuration(path, strict=True)
        assert check.matches
        assert "nothing else is set" in check.describe()

    def test_a_loose_check_reads_only_what_it_needs(self, radio, tmp_path, simulator):
        """Rather than the whole map, which on a 115200 baud link is the
        difference between a quick check and a slow one."""
        path = write(tmp_path, BASIC)
        before = len(simulator.command_log)
        radio.verify_configuration(path)
        loose = len(simulator.command_log) - before
        before = len(simulator.command_log)
        radio.verify_configuration(path, strict=True)
        assert loose < len(simulator.command_log) - before

    def test_the_result_serialises_for_a_report(self, radio, tmp_path):
        check = radio.verify_configuration(write(tmp_path, BASIC))
        summary = check.as_dict()
        assert summary["matches"] is False
        assert summary["mismatches"]["PCKTCTRL3"] == {"expected": "0xC0", "actual": "0x20"}
        assert summary["summary"]

    def test_matches_is_the_one_line_a_specification_asserts_on(self, radio, tmp_path):
        path = write(tmp_path, BASIC)
        radio.apply_configuration(path)
        assert radio.verify_configuration(path).matches is True


class TestCapturingFromARadio:
    def test_it_writes_a_file_that_reads_back(self, radio, tmp_path):
        radio.write_register("PCKTCTRL3", 0xC0)
        path = radio.save_configuration(str(tmp_path / "captured.regs"))
        assert load_register_file(path).as_map() == {0x2E: 0xC0}

    def test_a_captured_file_reapplies(self, radio, tmp_path):
        radio.write_register("PCKTCTRL3", 0xC0)
        path = radio.save_configuration(str(tmp_path / "captured.regs"))
        radio.restore_defaults()
        radio.apply_configuration(path)
        assert radio.read_register("PCKTCTRL3") == 0xC0

    def test_it_records_where_it_came_from(self, radio, tmp_path):
        radio.write_register("PCKTCTRL3", 0xC0)
        path = radio.save_configuration(str(tmp_path / "captured.regs"))
        assert "captured from S2-LP DK on simulated" in open(path, encoding="utf-8").read()


class TestTheShippedConfiguration:
    def test_it_loads(self):
        """The example in configs/ must stay loadable as the map changes."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3]
        configuration = load_register_file(str(root / "configs" / "s2lp_915_38k4_basic.regs"))
        assert len(configuration) >= 5
        assert "PCKTCTRL3" in configuration.names

    def test_the_kepler_receive_file_holds_the_sensor_s_settings(self, radio):
        """Captured from the kit; checked here against the sensor firmware's
        values and the S2-LP DK GUI setup rf_monitor uses: primary sync
        0x4E63F358 and secondary 0xB19C0CA7, each least significant byte first,
        with SECOND_SYNC_SEL on; variable length, one address byte, CRC-16
        0x8005, TX source the FIFO."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3]
        path = str(root / "configs" / "s2lp_kepler_433_rx.regs")
        values = load_register_file(path).as_map()
        by_name = {reg.BY_ADDRESS[address].name: value for address, value in values.items()}
        assert [by_name[name] for name in ("SYNC3", "SYNC2", "SYNC1", "SYNC0")] == [
            0x58, 0xF3, 0x63, 0x4E]
        assert [by_name["PCKT_FLT_GOALS%d" % index] for index in (3, 2, 1, 0)] == [
            0xA7, 0x0C, 0x9C, 0xB1]
        assert by_name["PCKTCTRL2"] & 0x01 == 1          # variable length
        assert by_name["PCKTCTRL4"] == 0x08              # one address byte
        assert by_name["PCKTCTRL1"] == 0x42              # CRC-16 0x8005, dual sync, TXSOURCE 0
        radio.apply_configuration(path, reset="defaults")
        assert radio.read_field("PCKTCTRL1", "TXSOURCE") == 0
