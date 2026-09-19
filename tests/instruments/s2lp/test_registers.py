"""The S2-LP register map.

The map is data, so these tests are about the properties data has to have to be
trustworthy: no duplicate addresses, no overlapping fields, every field inside
its byte, every reset value a byte. A map that is quietly wrong produces dumps
that look authoritative and are not.

Traces to: S2LP-FR-010 .. S2LP-FR-014, SWE4-UT-S2LPREG.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.s2lp import registers as reg
from benchtools.instruments.s2lp.constants import REGISTER_COUNT


class TestTheTableItself:
    def test_it_has_the_documented_number_of_registers(self):
        assert len(reg.REGISTERS) == REGISTER_COUNT

    def test_every_address_appears_once(self):
        addresses = [register.address for register in reg.REGISTERS]
        assert len(set(addresses)) == len(addresses)

    def test_every_name_appears_once(self):
        names = [register.name.upper() for register in reg.REGISTERS]
        assert len(set(names)) == len(names)

    def test_addresses_are_bytes(self):
        assert all(0 <= register.address <= 0xFF for register in reg.REGISTERS)

    def test_reset_values_are_bytes(self):
        assert all(0 <= register.reset <= 0xFF for register in reg.REGISTERS)

    def test_access_is_one_of_two_things(self):
        assert {register.access for register in reg.REGISTERS} == {reg.RW, reg.RO}

    def test_the_table_is_sorted_by_address(self):
        """So a reader can find a register in it, and a diff is readable."""
        addresses = [register.address for register in reg.REGISTERS]
        assert addresses == sorted(addresses)

    def test_the_indexes_agree_with_the_table(self):
        assert len(reg.BY_NAME) == len(reg.REGISTERS)
        assert len(reg.BY_ADDRESS) == len(reg.REGISTERS)

    def test_known_registers_are_where_the_datasheet_puts_them(self):
        """A handful of anchors: if these move, the map is a different chip."""
        assert reg.BY_NAME["GPIO0_CONF"].address == 0x00
        assert reg.BY_NAME["PCKTCTRL3"].address == 0x2E
        assert reg.BY_NAME["RSSI_LEVEL"].address == 0xA2
        assert reg.BY_NAME["MC_STATE0"].address == 0x8E
        assert reg.BY_NAME["DEVICE_INFO1"].address == 0xF0
        assert reg.BY_NAME["IRQ_STATUS0"].address == 0xFD

    def test_status_registers_are_read_only(self):
        for name in ("MC_STATE0", "MC_STATE1", "RSSI_LEVEL", "DEVICE_INFO1"):
            assert reg.BY_NAME[name].access == reg.RO, name


class TestFields:
    def test_no_two_fields_of_a_register_overlap(self):
        for register in reg.REGISTERS:
            used = 0
            for field in register.fields:
                assert not (used & field.mask), "%s.%s overlaps" % (register, field.name)
                used |= field.mask

    def test_every_field_is_inside_its_byte(self):
        for register in reg.REGISTERS:
            for field in register.fields:
                assert 0 <= field.low <= field.high <= 7, "%s.%s" % (register, field.name)

    def test_no_field_is_called_reserved(self):
        """Reserved bits are not fields; naming them would imply they mean
        something."""
        for register in reg.REGISTERS:
            assert all(field.name.upper() != "RESERVED" for field in register.fields)

    def test_a_field_extracts_its_own_bits(self):
        field = reg.BY_NAME["PCKTCTRL3"].field("PCKT_FRMT")
        assert field.bits == "7:6"
        assert field.extract(0xC0) == 3
        assert field.extract(0x3F) == 0

    def test_a_field_replaces_only_its_own_bits(self):
        register = reg.BY_NAME["PCKTCTRL3"]
        assert register.field("PCKT_FRMT").insert(0x2F, 3) == 0xEF

    def test_a_value_too_wide_for_a_field_is_refused(self):
        """Truncating silently would write a different configuration from the
        one asked for, and the read-back would agree with the truncation."""
        field = reg.BY_NAME["PCKTCTRL3"].field("PCKT_FRMT")
        with pytest.raises(ValueError, match="2 bit"):
            field.insert(0x00, 4)

    def test_a_single_bit_field_reads_as_one_number(self):
        field = reg.BY_NAME["PCKTCTRL2"].field("FIX_VAR_LEN")
        assert field.width == 1 and field.bits == "0"

    def test_an_unknown_field_lists_the_ones_that_exist(self):
        with pytest.raises(KeyError, match="PCKT_FRMT"):
            reg.BY_NAME["PCKTCTRL3"].field("PACKET_FORMAT")


class TestLookup:
    def test_by_name_either_case(self):
        assert reg.lookup("pcktctrl3") is reg.lookup("PCKTCTRL3")

    def test_by_address(self):
        assert reg.lookup(0x2E).name == "PCKTCTRL3"

    def test_by_address_as_text(self):
        assert reg.lookup("0x2E").name == "PCKTCTRL3"

    def test_an_unknown_name_is_not_guessed_at(self):
        with pytest.raises(KeyError, match="PCKTCTRL9"):
            reg.lookup("PCKTCTRL9")

    def test_an_unknown_address_names_its_neighbours(self):
        """0x0B is a gap in the map. The likely cause of landing there is an
        off-by-one, and naming the registers either side shows it."""
        with pytest.raises(KeyError) as caught:
            reg.lookup(0x0B)
        message = str(caught.value)
        assert "0x0B" in message
        assert "IF_OFFSET_DIG" in message and "CH_SPACE" in message


class TestReadingABlock:
    def test_runs_cover_every_register(self):
        covered = sum(count for _start, count in reg.contiguous_runs())
        assert covered == len(reg.REGISTERS)

    def test_runs_are_contiguous_within_themselves(self):
        for start, count in reg.contiguous_runs():
            for offset in range(count):
                assert (start + offset) in reg.BY_ADDRESS

    def test_there_are_far_fewer_runs_than_registers(self):
        """The point of runs: a dump is a handful of commands, not 123."""
        assert len(reg.contiguous_runs()) < len(reg.REGISTERS) / 4

    def test_a_chosen_set_of_addresses_groups_too(self):
        assert reg.contiguous_runs([0x00, 0x01, 0x02, 0x10]) == [(0x00, 3), (0x10, 1)]

    def test_duplicates_and_order_do_not_matter(self):
        assert reg.contiguous_runs([0x02, 0x00, 0x01, 0x00]) == [(0x00, 3)]


class TestDescribing:
    def test_a_register_at_its_reset_value_says_so(self):
        line = reg.BY_NAME["PCKTCTRL3"].describe(0x20)
        assert "PCKTCTRL3" in line and "(reset)" in line

    def test_non_zero_fields_are_named(self):
        line = reg.BY_NAME["PCKTCTRL3"].describe(0xC0)
        assert "PCKT_FRMT=3" in line

    def test_zero_fields_are_not_listed(self):
        """A dump that lists every field of every register is a dump nobody
        reads."""
        assert "BYTE_SWAP" not in reg.BY_NAME["PCKTCTRL3"].describe(0xC0)

    def test_a_whole_dump_comes_out_in_address_order(self):
        values = {0x2E: 0x20, 0x00: 0x0A}
        lines = list(reg.describe(values))
        assert lines[0].startswith("0x00") and lines[1].startswith("0x2E")

    def test_an_undocumented_address_is_shown_not_dropped(self):
        lines = list(reg.describe({0x0B: 0x42}))
        assert "undocumented" in lines[0] and "0x42" in lines[0]

    def test_decode_by_address(self):
        assert reg.decode(0x2E, 0xC0)["PCKT_FRMT"] == 3
