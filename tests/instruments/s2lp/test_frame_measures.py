"""Measures over Kepler frames: filters, intervals, copies, groups, census (#243).

The numbers are taken from a synthetic hour of Kepler traffic
(:mod:`.synthetic_air`), built from the plugin's frame layouts and read back
through a packet log as the driver writes one. The receive path is exercised
on the simulated kit.

Traces to: S2LP-FR-088 .. S2LP-FR-092, SWE4-UT-S2LPMEASURES.
"""

from __future__ import annotations

import json

import pytest

from benchtools.analysis import frames as fr
from benchtools.core import plugins
from benchtools.core.errors import ConfigurationError, MeasurementError
from benchtools.instruments.s2lp.packets import Packet, PacketLog

from ...kepler_plugin import decode_kepler_frame, tables
from . import synthetic_air
from .test_kepler import ALIVE_REPEATS, CONFIG_FRAME, TWF_FRAMES


@pytest.fixture(scope="module")
def hour_log(tmp_path_factory):
    """The synthetic hour as a packet log timed by host_time, as before #243."""
    return synthetic_air.write_log(str(tmp_path_factory.mktemp("air") / "packets.jsonl"))


@pytest.fixture(scope="module")
def hour(hour_log):
    """The synthetic hour, read back from its log through the decoder."""
    return fr.frames_from_log(hour_log, decode_kepler_frame)


# ----------------------------------------------------------------------
# Fields and filters
# ----------------------------------------------------------------------
class TestFieldsAndFilters:
    DECODED = {"type": "ALIVE", "status": {"phase": 2}, "values": [5, 6, 7], "axis": "Z"}

    def test_a_dotted_path_reaches_into_dictionaries_and_lists(self):
        assert fr.field_value(self.DECODED, "status.phase") == 2
        assert fr.field_value(self.DECODED, "values.2") == 7
        assert fr.field_value(self.DECODED, "values.-1") == 7

    def test_a_path_that_is_not_there_is_missing_not_none(self):
        for path in ("status.live", "values.3", "type.name", "nothing"):
            assert fr.field_value(self.DECODED, path) is fr.MISSING

    def test_where_takes_a_value_or_any_of_a_list_and_text_ignores_case(self):
        assert fr.matches(self.DECODED, {"status.phase": 2, "axis": "z"})
        assert fr.matches(self.DECODED, {"status.phase": [1, 2]})
        assert fr.matches(self.DECODED, {"values.0": "5"})
        assert not fr.matches(self.DECODED, {"status.phase": 3})
        assert not fr.matches(self.DECODED, {"status.live": None})

    def test_true_matches_only_true(self):
        assert fr.matches({"on": True}, {"on": True})
        assert not fr.matches({"on": True}, {"on": "yes"})

    def test_where_must_be_a_mapping(self):
        with pytest.raises(ConfigurationError, match="where must map a field"):
            fr.check_where(["mux", 3])

    def test_where_chooses_one_config_multiplex(self, hour):
        chosen = fr.select(hour, "CONFIG", "5C1712", {"mux": 8})
        assert len(chosen) == 6 and {frame.decoded["mux"] for frame in chosen} == {8}

    def test_select_leaves_out_rejected_and_undecoded_receptions(self, hour):
        assert len(hour) == 761
        assert len(fr.select(hour)) == 761 - 1 - 3      # one rejected, three refused


# ----------------------------------------------------------------------
# Reading a packet log back
# ----------------------------------------------------------------------
class TestPacketLog:
    def test_an_old_log_is_timed_by_its_host_time(self, hour):
        assert hour[0].time_s == synthetic_air.EPOCH.timestamp() + 5.0
        assert hour[-1].time_s - hour[0].time_s == pytest.approx(3570.2)

    def test_a_log_is_timed_by_monotonic_s_when_every_record_has_it(self, tmp_path):
        log = synthetic_air.write_log(str(tmp_path / "packets.jsonl"), monotonic=True)
        assert fr.frames_from_log(log, decode_kepler_frame)[0].time_s == 5005.0

    def test_a_log_with_monotonic_times_is_timed_by_them(self, tmp_path):
        log = tmp_path / "packets.jsonl"
        log.write_text("\n".join(json.dumps(record) for record in [
            {"direction": "rx", "hex": ALIVE_REPEATS[0], "error": 0, "monotonic_s": 10.0,
             "host_time": "2026-10-21T00:00:00+00:00"},
            {"direction": "note", "note": "a note is not a frame"},
            {"direction": "rx", "hex": ALIVE_REPEATS[0], "error": 0, "monotonic_s": 70.5,
             "host_time": "2026-10-21T00:00:01+00:00"},
        ]) + "\n{\"truncated", encoding="utf-8")
        frames = fr.frames_from_log(str(log), decode_kepler_frame)
        assert [frame.time_s for frame in frames] == [10.0, 70.5]

    def test_a_log_mixing_records_with_and_without_monotonic_s_uses_host_time(self, tmp_path):
        log = tmp_path / "packets.jsonl"
        log.write_text("\n".join(json.dumps(record) for record in [
            {"direction": "rx", "hex": ALIVE_REPEATS[0], "error": 0,
             "host_time": "2026-10-21T00:00:00+00:00"},
            {"direction": "rx", "hex": ALIVE_REPEATS[0], "error": 0, "monotonic_s": 99.0,
             "host_time": "2026-10-21T00:00:30+00:00"},
        ]) + "\n", encoding="utf-8")
        frames = fr.frames_from_log(str(log), decode_kepler_frame)
        assert frames[1].time_s - frames[0].time_s == pytest.approx(30.0)

    def test_a_log_appended_to_by_two_runs_has_no_interval_across_them(self, tmp_path):
        path = str(tmp_path / "packets.jsonl")
        for start in (100.0, 900.0):                       # the second run, 13 min later
            with PacketLog(path) as log:
                for index in range(3):
                    log.write(Packet("rx", bytes.fromhex(ALIVE_REPEATS[0]),
                                     monotonic_s=start + 60.0 * index))
        frames = fr.frames_from_log(path, decode_kepler_frame)
        assert [frame.run for frame in frames] == [0, 0, 0, 1, 1, 1]
        result = fr.intervals(frames)
        assert (result["runs"], result["intervals"]) == (2, [60.0, 60.0, 60.0, 60.0])

    def test_two_runs_do_not_join_copies(self):
        frames = [fr.Frame(b"", {"type": "ALIVE", "sensor_id": "A", "frame": {"repeat": r}}, t,
                           run=run) for r, t, run in [(0, 0.0, 0), (1, 0.1, 1)]]
        assert len(fr.transmissions(frames, copy_gap=None)) == 2

    def test_the_board_time_is_read_back_too(self, tmp_path):
        log = tmp_path / "packets.jsonl"
        log.write_text(json.dumps({"direction": "rx", "hex": ALIVE_REPEATS[0], "error": 0,
                                   "board_time_us": 2_500_000}) + "\n", encoding="utf-8")
        assert fr.frames_from_log(str(log), decode_kepler_frame)[0].board_s == 2.5

    def test_without_a_decoder_the_logs_own_decode_is_used(self, tmp_path):
        log = tmp_path / "packets.jsonl"
        log.write_text(json.dumps({"direction": "rx", "hex": "00", "error": 0,
                                   "decoded": {"type": "X"}}) + "\n", encoding="utf-8")
        assert fr.frames_from_log(str(log))[0].frame_type == "X"

    def test_a_payload_the_decoder_refuses_is_kept_with_the_reason(self, hour):
        refused = [frame for frame in hour if not frame.error and not frame.decoded]
        assert len(refused) == 3 and len(refused[0].data) == 20
        assert "this payload is 20" in refused[0].decode_error


# ----------------------------------------------------------------------
# Transmissions and intervals
# ----------------------------------------------------------------------
class TestIntervals:
    def test_copies_are_one_transmission(self, hour):
        alive = fr.select(hour, "ALIVE", "5C1712")
        assert len(alive) == 180 and len(fr.transmissions(alive)) == 60

    def test_each_source_and_type_keeps_its_own_copies(self):
        frames = [fr.Frame(bytes([n]), {"type": kind, "sensor_id": who, "frame": {"repeat": r}}, n)
                  for n, (kind, who, r) in enumerate([
                      ("ALIVE", "A", 0), ("ALIVE", "B", 0), ("ALIVE", "A", 1),
                      ("CONFIG", "A", 0), ("ALIVE", "A", 2), ("ALIVE", "A", 0)])]
        assert [len(group) for group in fr.transmissions(frames)] == [3, 1, 1, 1]

    def test_the_cmd_pacing_of_a_sensor(self, hour):
        # AA0001: a CMD every 50 s, three missed - one 100 s gap, one 150 s.
        result = fr.intervals(fr.select(hour, "CMD", "AA0001"), burst_gap=1.0, above=60)
        assert (result["transmissions"], result["count"]) == (59, 58)
        assert result["minimum"] == pytest.approx(50.0, abs=1e-3)
        assert result["maximum"] == pytest.approx(150.0, abs=1e-3)
        assert result["above"] == 2 and result["largest_burst"] == 1

    def test_cmd_sequences_of_three_attempts(self, hour):
        result = fr.intervals(fr.select(hour, "CMD", "AA0002"), burst_gap=1.0)
        assert (result["transmissions"], result["bursts"], result["largest_burst"]) == (360, 120, 3)
        assert result["minimum"] == pytest.approx(30.0) and result["maximum"] == pytest.approx(30.0)

    def test_config_frames_45_s_apart(self, hour):
        result = fr.intervals(fr.select(hour, "CONFIG", "5C1712"), below=45.5, above=60.5)
        assert result["transmissions"] == 24 and result["count"] == 23
        assert result["minimum"] == pytest.approx(45.0, abs=1e-3)
        assert (result["below"], result["above"]) == (22, 1)

    def test_a_lost_first_copy_does_not_join_two_transmissions(self):
        """Copy 0 of one ALIVE, then only copies 1 and 2 of the next, 60 s on."""
        frames = [fr.Frame(b"", {"type": "ALIVE", "sensor_id": "A", "frame": {"repeat": r}}, t)
                  for r, t in [(0, 0.0), (1, 60.1), (2, 60.2), (0, 120.0), (1, 120.1)]]
        assert [len(group) for group in fr.transmissions(frames)] == [1, 2, 2]
        assert fr.intervals(frames)["intervals"] == [60.1, 59.9]
        assert [len(group) for group in fr.transmissions(frames, copy_gap=None)] == [3, 2]

    def test_a_chain_of_close_transmissions_is_one_burst(self):
        frames = [fr.Frame(b"", {"type": "CMD", "sensor_id": "A", "frame": {"repeat": 0}}, t)
                  for t in (0.0, 0.9, 1.8, 10.0)]
        result = fr.intervals(frames, burst_gap=1.0)
        assert (result["bursts"], result["largest_burst"], result["intervals"]) == (2, 3, [10.0])

    def test_times_that_go_backwards_within_a_run_are_refused(self):
        frames = [fr.Frame(b"", {"type": "CMD", "sensor_id": "A"}, t) for t in (10.0, 20.0, 5.0)]
        with pytest.raises(MeasurementError, match="go backwards.*within one run.*host_time"):
            fr.intervals(frames)

    def test_the_copy_gap_can_be_set(self):
        frames = [fr.Frame(b"", {"type": "ALIVE", "sensor_id": "A", "frame": {"repeat": r}}, t)
                  for r, t in [(0, 0.0), (1, 3.0), (2, 6.0)]]
        assert fr.intervals(frames)["transmissions"] == 3
        assert fr.intervals(frames, copy_gap=5.0)["transmissions"] == 1

    def test_the_board_clock_can_be_chosen(self):
        frames = [fr.Frame(b"", {"type": "CMD", "sensor_id": "A"}, host, board_s=board)
                  for host, board in [(0.0, 100.0), (50.02, 150.0), (99.98, 200.0)]]
        assert fr.intervals(frames, clock="board")["intervals"] == [50.0, 50.0]
        assert fr.intervals(frames)["intervals"] == [50.02, 49.96]
        with pytest.raises(MeasurementError, match="no board time"):
            fr.intervals([fr.Frame(b"", {"type": "CMD"}, 1.0)], clock="board")
        with pytest.raises(ConfigurationError, match="not a clock"):
            fr.intervals(frames, clock="wall")

    def test_a_burst_gap_makes_retries_one_burst(self):
        times = [0.0, 0.1, 0.2, 30.0, 30.1, 60.0, 100.05]
        frames = [fr.Frame(b"", {"type": "CMD", "sensor_id": "A", "frame": {"repeat": 0}}, when)
                  for when in times]
        result = fr.intervals(frames, burst_gap=1.0, above=35)
        assert result["bursts"] == 4 and result["largest_burst"] == 3
        assert result["intervals"] == [30.0, 30.0, 40.05] and result["above"] == 1
        assert fr.intervals(frames)["count"] == 6

    def test_one_transmission_has_no_interval(self):
        result = fr.intervals([fr.Frame(b"", {"type": "A"}, 1.0)])
        assert result["count"] == 0 and result["mean"] is None

    def test_a_frame_with_no_time_is_an_error(self):
        with pytest.raises(MeasurementError, match="no host time"):
            fr.intervals([fr.Frame(b"", {"type": "A"}, None)])


# ----------------------------------------------------------------------
# Census
# ----------------------------------------------------------------------
class TestCensus:
    EXPECTED = ["VERSION", "ALIVE", "TWF", "CONFIG", "FFT2", "CMD", "RESPONSE"]

    def test_every_type_with_its_lengths_and_fields(self, hour):
        result = fr.census(hour, fields=["rf_capability", "axis"], expected=self.EXPECTED)
        assert result["type_names"] == ["ALIVE", "CMD", "CONFIG", "RESPONSE", "TWF", "VERSION"]
        types = result["types"]
        assert {name: entry["lengths"] for name, entry in types.items()} == {
            "VERSION": [83], "ALIVE": [35], "TWF": [100], "CONFIG": [21], "CMD": [15],
            "RESPONSE": [14]}
        assert types["TWF"]["fields"]["axis"] == ["X"]
        assert types["CMD"]["fields"]["rf_capability"] == [5]
        assert types["CMD"]["fields"]["axis"] == []
        assert (types["ALIVE"]["count"], types["ALIVE"]["transmissions"]) == (180, 60)
        assert (result["rejected"], result["undecoded"]) == (1, 3)

    def test_a_field_named_like_a_count_does_not_collide(self, hour):
        result = fr.census(hour, fields=["count", "lengths"])
        assert result["types"]["ALIVE"]["count"] == 180
        assert result["types"]["ALIVE"]["fields"] == {"count": [], "lengths": []}

    def test_a_type_not_expected_is_counted(self, hour):
        result = fr.census(hour, expected=["VERSION", "ALIVE", "TWF", "CONFIG", "CMD"])
        assert result["unexpected_types"] == ["RESPONSE"] and result["unexpected"] == 59 + 3

    def test_a_frame_the_decoder_refuses_is_unexpected(self, hour):
        result = fr.census(hour, expected=self.EXPECTED)
        assert result["unexpected"] == 3 and len(result["decode_errors"]) == 1

    def test_without_expected_nothing_is_called_unexpected(self, hour):
        assert "unexpected" not in fr.census(hour)


# ----------------------------------------------------------------------
# Copies
# ----------------------------------------------------------------------
class TestCopies:
    def test_distance_copies_differ_only_in_the_count_byte(self, hour):
        chosen = fr.select(hour, "CONFIG", "5C1712", {"permute_method": "distance"})
        assert fr.compare_copies(chosen, ignore_offsets=[9])["not_identical"] == 0
        assert fr.compare_copies(chosen)["identical"] == 0

    def test_polynomial_config_copies_each_carry_a_different_parameter_set(self, hour):
        chosen = fr.select(hour, "CONFIG", "5C1712", {"permute_method": "polynomial"})
        result = fr.compare_copies(chosen, ignore_offsets=[9], positions=tables.frame_positions)
        assert result["transmissions"] == 12 and result["not_identical"] == 12
        assert (result["distinct_blocks"], result["repeated_blocks"]) == (12, 0)
        assert (result["length"], result["covered"], result["missing"]) == (60, 60, 0)
        assert result["conflicts"] == 0

    def test_distance_config_copies_repeat_one_block(self, hour):
        chosen = fr.select(hour, "CONFIG", "5C1712", {"permute_method": "distance"})
        result = fr.compare_copies(chosen, positions=tables.frame_positions)
        assert (result["repeated_blocks"], result["missing"], result["conflicts"]) == (12, 0, 0)

    def test_twf_packet_numbers_ascend(self, hour):
        result = fr.compare_copies(fr.select(hour, "TWF", "5C1712"), ignore_offsets=[9],
                                   ascending="packet_number")
        assert (result["identical"], result["not_ascending"]) == (8, 0)
        assert [row["packet_number"] for row in result["detail"]] == list(range(8))

    def test_an_ascending_field_that_cannot_be_compared_is_counted(self):
        frames = [fr.Frame(bytes([n]), {"type": "TWF", "sensor_id": "A", "packet_number": v}, n)
                  for n, v in enumerate([0, 1, "2", 3])]
        # "2" after 1, and 3 after "2"
        assert fr.compare_copies(frames, ascending="packet_number")["not_ascending"] == 2

    def test_a_restart_value_starts_the_order_afresh(self):
        frames = [fr.Frame(bytes([n]), {"type": "TWF", "sensor_id": "A", "packet_number": v}, n)
                  for n, v in enumerate([0, 1, 2, 0, 1, 1])]
        assert fr.compare_copies(frames, ascending="packet_number")["not_ascending"] == 2
        assert fr.compare_copies(frames, ascending="packet_number",
                                 restart_at=0)["not_ascending"] == 1

    def test_sequences_keep_their_own_positions_and_order(self, hour):
        """Two axes of one capture: the same packet numbers, different samples."""
        x_axis = fr.select(hour, "TWF", "5C1712")
        y_axis = []
        for frame in x_axis:
            data = bytearray(frame.data)
            data[13] = (data[13] & 0x3F) | (1 << 6)        # param bits 15:14, axis Y
            data[30] ^= 0x01                                # a different first sample
            y_axis.append(fr.Frame(bytes(data), decode_kepler_frame(bytes(data)),
                                   frame.time_s + 100.0))
        both = x_axis + y_axis
        mixed = fr.compare_copies(both, positions=tables.frame_positions,
                                  ascending="packet_number")
        assert mixed["conflicts"] > 0 and mixed["not_ascending"] == 1
        apart = fr.compare_copies(both, positions=tables.frame_positions,
                                  ascending="packet_number", sequence=["axis", "param.twfb"])
        assert (apart["sequences"], apart["conflicts"], apart["not_ascending"]) == (2, 0, 0)
        assert apart["length"] == 2 * 256 * 32 and apart["covered"] == 2 * 8 * 32
        assert apart["detail"][-1]["sequence"] == ["Y", 0]

    def test_a_transmission_without_its_sequence_fields_is_left_out(self, hour):
        twf = fr.select(hour, "TWF", "5C1712")
        stray = fr.Frame(twf[0].data, dict(twf[0].decoded, axis=None), 1.0)
        del stray.decoded["axis"]
        result = fr.compare_copies([stray] + twf, positions=tables.frame_positions,
                                   ascending="packet_number", sequence=["axis"])
        assert (result["unsequenced"], result["sequences"], result["not_ascending"]) == (1, 1, 0)
        assert result["covered"] == 8 * 32

    def test_a_packet_number_out_of_order_is_counted(self, hour):
        frames = fr.select(hour, "TWF", "5C1712")
        swapped = frames[3:6] + frames[0:3] + frames[6:]
        assert fr.compare_copies(swapped, ascending="packet_number")["not_ascending"] == 1

    def test_alive_status_is_the_same_in_every_copy(self, hour):
        result = fr.compare_copies(fr.select(hour, "ALIVE", "5C1712"),
                                   ignore_offsets=[8], same_fields=["status"])
        assert (result["fields_differ"], result["not_identical"]) == (0, 0)

    def test_a_status_that_differs_between_copies_is_counted(self):
        """The copies V11.00.0000 sent before Kepler TX-1049 (#252)."""
        first, later = bytearray.fromhex(ALIVE_REPEATS[0]), bytearray.fromhex(ALIVE_REPEATS[1])
        later[34] = first[34] ^ 0x01
        frames = [fr.Frame(bytes(data), decode_kepler_frame(bytes(data)), n)
                  for n, data in enumerate([first, later])]
        result = fr.compare_copies(frames, ignore_offsets=[8], same_fields=["status"])
        assert result["fields_differ"] == 1 and result["detail"][0]["fields_differ"] == ["status"]

    @staticmethod
    def polynomial_twf(packets: int, copies: int = 3):
        """TWF frames under the polynomial, each sample its own position: a
        waveform rebuilt from them is 0, 1, 2, ... wherever it is complete."""
        base = bytearray.fromhex(TWF_FRAMES[0])
        size = packets * 32
        frames = []
        for packet in range(packets):
            for repeat in range(copies):
                data = bytearray(base)
                data[8] = (data[8] & ~0x18) | (2 << 3)          # permute: polynomial
                data[9] = ((repeat + 1) << 4) | copies
                data[17:19] = packet.to_bytes(2, "big")
                data[19:21] = packets.to_bytes(2, "big")
                for slot in range(32):
                    value = tables.twf_sample("polynomial", packet, slot, size, repeat)
                    data[29 + 2 * slot:31 + 2 * slot] = value.to_bytes(2, "big", signed=True)
                frames.append(fr.Frame(bytes(data), decode_kepler_frame(bytes(data)),
                                       float(len(frames))))
        return frames

    def test_a_polynomial_waveform_is_rebuilt_whole_from_its_copies(self):
        frames = self.polynomial_twf(packets=4)
        assert frames[0].decoded["permute_method"] == "polynomial"
        result = fr.compare_copies(frames, ignore_offsets=[9], positions=tables.frame_positions)
        assert (result["transmissions"], result["placed"]) == (4, 12)
        assert (result["length"], result["missing"], result["conflicts"]) == (128, 0, 0)
        assert result["distinct_blocks"] == 4 and result["not_identical"] == 4

    def test_the_copies_of_one_polynomial_packet_share_positions(self):
        """By the firmware's own permutation (Permute_Poly, version = repeat)
        the three copies of one packet are not disjoint: here 100 shared
        positions over 4 packets. The measure reports it; it does not assume."""
        result = fr.compare_copies(self.polynomial_twf(packets=4),
                                   positions=tables.frame_positions)
        assert result["overlapping"] == sum(row["overlapping"] for row in result["detail"]) > 0

    def test_a_missing_packet_leaves_positions_missing(self):
        frames = [frame for frame in self.polynomial_twf(packets=4)
                  if frame.decoded["packet_number"] != 2]
        result = fr.compare_copies(frames, positions=tables.frame_positions)
        assert 0 < result["missing"] < 96 and result["covered"] + result["missing"] == 128

    def test_two_values_for_one_position_are_a_conflict(self):
        frames = self.polynomial_twf(packets=1, copies=1)
        changed = bytearray(frames[0].data)
        changed[29] ^= 0x40                         # slot 0 only
        frames.append(fr.Frame(bytes(changed), decode_kepler_frame(bytes(changed)), 9.0))
        assert fr.compare_copies(frames, positions=tables.frame_positions)["conflicts"] == 1

    def test_a_frame_the_hook_does_not_place_is_left_out(self):
        frames = [fr.Frame(bytes.fromhex(ALIVE_REPEATS[0]),
                           decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0])), 0.0)]
        result = fr.compare_copies(frames, positions=tables.frame_positions)
        assert (result["placed"], result["length"], result["distinct_blocks"]) == (0, 0, 0)


class TestFramePositionsHook:
    def test_config_under_distance(self):
        size, values = tables.frame_positions(decode_kepler_frame(bytes.fromhex(CONFIG_FRAME)))
        decoded = decode_kepler_frame(bytes.fromhex(CONFIG_FRAME))
        assert size == 60
        assert values == {entry["parameter"]: entry["value"] for entry in decoded["parameters"]}

    def test_twf_without_a_packet_count_is_not_placed(self):
        decoded = dict(decode_kepler_frame(bytes.fromhex(TWF_FRAMES[0])), packet_count=0)
        assert tables.frame_positions(decoded) is None

    def test_the_plugin_provides_it(self):
        assert plugins.hook("frame_positions") is tables.frame_positions


# ----------------------------------------------------------------------
# Distinct values per group
# ----------------------------------------------------------------------
def twf(group: int, axis: int, sync: int, packet: int = 0, twfb: int = 0) -> fr.Frame:
    """A TWF frame's decode, as much of it as the group measure reads."""
    return fr.Frame(b"", {"type": "TWF", "sensor_id": "5C1712", "group_id": group,
                          "axis": "XYZ"[axis], "param": {"twfb": twfb},
                          "packet_number": packet, "sync_attribute": sync,
                          "frame": {"repeat": 0}}, float(packet))


class TestDistinctPerGroup:
    def test_one_value_per_waveform(self, hour):
        result = fr.distinct_per_group(fr.select(hour, "TWF", "5C1712"), "sync_attribute",
                                       "group_id", item=["axis", "param.twfb"])
        assert (result["groups"], result["items"], result["inconsistent"]) == (1, 1, 0)
        per_frame = fr.distinct_per_group(fr.select(hour, "TWF", "5C1712"),
                                          "sync_attribute", "group_id")
        assert per_frame["not_distinct"] == 1          # eight packets, one waveform

    def test_six_waveforms_with_unique_attributes_then_a_new_set(self):
        frames = [twf(1, axis, 100 + 10 * axis + twfb, packet, twfb)
                  for twfb in (0, 1) for axis in range(3) for packet in range(2)]
        frames += [twf(2, axis, 200 + axis, 0) for axis in range(3)]
        result = fr.distinct_per_group(frames, "sync_attribute", "group_id",
                                       item=["axis", "param.twfb"])
        assert result["group_values"] == [1, 2] and result["items"] == 9
        assert (result["all_distinct"], result["repeated_sets"]) == (2, 0)
        assert result["not_incrementing"] == 0

    def test_a_repeated_attribute_and_a_repeated_set_are_counted(self):
        frames = [twf(1, 0, 5), twf(1, 1, 5), twf(2, 0, 5), twf(2, 1, 5)]
        result = fr.distinct_per_group(frames, "sync_attribute", "group_id", item=["axis"])
        assert (result["not_distinct"], result["repeated_sets"]) == (2, 1)

    def test_a_waveform_whose_packets_disagree_is_inconsistent(self):
        frames = [twf(1, 0, 5, 0), twf(1, 0, 6, 1)]
        result = fr.distinct_per_group(frames, "sync_attribute", "group_id", item=["axis"])
        assert result["inconsistent"] == 1 and result["items"] == 1

    def test_a_group_counter_that_wraps(self):
        frames = [twf(group, 0, group) for group in (254, 255, 1, 2, 4)]
        assert fr.distinct_per_group(frames, "sync_attribute", "group_id")[
            "not_incrementing"] == 2                    # 255 -> 1 and 2 -> 4
        wrapped = fr.distinct_per_group(frames, "sync_attribute", "group_id",
                                        wrap_after=255, wrap_to=1)
        assert wrapped["not_incrementing"] == 1


# ----------------------------------------------------------------------
# The driver's actions, on the simulated kit
# ----------------------------------------------------------------------
def config_frame(mux: int, repeat: int = 0) -> bytes:
    data = bytearray.fromhex(CONFIG_FRAME)
    data[9] = ((repeat + 1) << 4) | 3
    data[10] = mux
    return bytes(data)


class TestActions:
    def test_dut_frame_takes_the_multiplex_asked_for(self, radio, simulator):
        for mux in (0, 1, 2):
            simulator.queue_packet(config_frame(mux))
        frame = radio.dut_frame("CONFIG", source="5C1712", where={"mux": 2}, timeout=10.0,
                                decoder="kepler")
        assert frame["mux"] == 2 and isinstance(frame["monotonic_s"], float)

    def test_dut_frame_names_the_filter_when_nothing_matches(self, radio, simulator):
        simulator.queue_packet(config_frame(0))
        with pytest.raises(MeasurementError, match="no CONFIG frame from 5C1712 with mux 7"):
            radio.dut_frame("CONFIG", source="5C1712", where={"mux": 7}, timeout=1.5,
                            decoder="kepler")

    def test_dut_samples_takes_a_dotted_field_with_a_filter(self, radio, simulator):
        for mux in (0, 1, 0):
            for repeat in range(3):
                simulator.queue_packet(config_frame(mux, repeat))
        samples = radio.dut_samples("values.0", source="5C1712", frame_type="CONFIG",
                                    where={"mux": 0}, count=2, timeout=10.0, decoder="kepler")
        assert samples.count == 2 and len(samples.instants) == 2
        assert samples.instants[0] <= samples.instants[1]

    def test_dut_transmissions_stops_after_count_with_every_copy(self, radio, simulator):
        for mux in (0, 1, 2):
            for repeat in range(3):
                simulator.queue_packet(config_frame(mux, repeat))
        result = radio.dut_transmissions("CONFIG", source="5C1712", count=2, window=10.0,
                                         ignore_offsets=[9], positions=True, decoder="kepler")
        assert (result["transmissions"], result["copies"], result["requested"]) == (2, 6, 2)
        assert result["not_identical"] == 0 and result["repeated_blocks"] == 2

    def test_positions_need_a_hook(self, radio, monkeypatch):
        monkeypatch.setattr(plugins, "hook", lambda name, default=None: None)
        with pytest.raises(ConfigurationError, match="frame_positions hook"):
            radio.dut_transmissions("TWF", positions=True, window=0.5, decoder="kepler")

    def test_dut_intervals_on_the_board_clock(self, radio, simulator):
        for _ in range(3):
            for repeat in range(3):
                simulator.queue_packet(config_frame(0, repeat))
        result = radio.dut_intervals("CONFIG", "5C1712", window=1.5, clock="board",
                                     copy_gap=None, decoder="kepler")
        assert result["transmissions"] == 3 and result["count"] == 2
        assert result["first_s"] is not None and result["minimum"] >= 0

    def test_dut_census_of_a_window(self, radio, simulator):
        simulator.queue_packet(config_frame(0))
        simulator.queue_packet(bytes.fromhex(ALIVE_REPEATS[0]))
        simulator.queue_packet(b"\x00" * 4)                 # too short for a header
        result = radio.dut_census(window=1.5, expected=["ALIVE", "CONFIG"], decoder="kepler")
        assert result["type_names"] == ["ALIVE", "CONFIG"] and result["unexpected"] == 1

    def test_the_actions_read_a_packet_log_without_the_board(self, radio, simulator, hour_log):
        sent = len(simulator.command_log)
        assert radio.dut_intervals("CMD", "AA0001", log=hour_log, burst_gap=1.0)["count"] == 58
        assert radio.dut_census(log=hour_log)["undecoded"] == 3
        assert radio.dut_transmissions("CONFIG", "5C1712", where={"permute_method": "polynomial"},
                                       positions=True, log=hour_log)["missing"] == 0
        assert radio.dut_distinct("sync_attribute", "group_id", "TWF", "5C1712",
                                  item=["axis", "param.twfb"], log=hour_log)["groups"] == 1
        assert len(simulator.command_log) == sent

    def test_the_deprecated_kepler_names_take_where(self, radio, simulator):
        simulator.queue_packet(config_frame(0))
        simulator.queue_packet(config_frame(5))
        assert radio.kepler_frame("CONFIG", where={"mux": 5}, timeout=10.0)["mux"] == 5

    def test_every_packet_carries_its_host_time(self, radio, simulator):
        simulator.queue_packet(bytes.fromhex(ALIVE_REPEATS[0]))
        packets = list(radio.stream(timeout=1.0))
        assert packets and isinstance(packets[0].monotonic_s, float)
        assert "monotonic_s" in packets[0].as_dict()


# ----------------------------------------------------------------------
# In a specification
# ----------------------------------------------------------------------
def test_a_specification_judges_a_packet_log_with_the_measures(  # pylint: disable=too-many-locals
        tmp_path, monkeypatch, hour_log):
    """Paths beside the specification, ``where`` and limits on the results."""
    from benchtools.runner.bench import BenchConfig  # pylint: disable=import-outside-toplevel
    from benchtools.runner.results import Status  # pylint: disable=import-outside-toplevel
    from benchtools.runner.runner import BenchRunner  # pylint: disable=import-outside-toplevel
    from benchtools.runner.spec import TestSpec  # pylint: disable=import-outside-toplevel

    from ...kepler_plugin import FOLDER  # pylint: disable=import-outside-toplevel

    suite = tmp_path / "suite"
    suite.mkdir()
    with open(hour_log, "rb") as source:
        (suite / "capture.jsonl").write_bytes(source.read())
    monkeypatch.chdir(tmp_path)

    def step(action, arguments, *limits):
        return {"do": "s2lp." + action, "with": dict(arguments, log="capture.jsonl"),
                "expect": [dict(limit) for limit in limits]}

    spec = TestSpec.from_mapping({
        "name": "Measures over a packet log",
        "plugins": [str(FOLDER)],
        "tests": [{"name": "An hour of traffic", "steps": [
            step("dut_census", {"expected": TestCensus.EXPECTED},
                 {"name": "only_the_short_frames", "measure": "unexpected", "nominal": 3},
                 {"name": "alive_length", "measure": "types.ALIVE.lengths.0", "nominal": 35}),
            step("dut_intervals", {"frame_type": "CMD", "source": "AA0001", "burst_gap": 1.0},
                 {"name": "cmd_pacing", "measure": "minimum", "min": 49.0, "max": 51.0}),
            step("dut_transmissions", {"frame_type": "CONFIG", "source": "5C1712",
                                       "where": {"permute_method": "polynomial"},
                                       "positions": True},
                 {"name": "parameters_missing", "measure": "missing", "nominal": 0},
                 {"name": "repeated_blocks", "measure": "repeated_blocks", "nominal": 0}),
            step("dut_distinct", {"value": "sync_attribute", "group": "group_id",
                                  "frame_type": "TWF", "item": ["axis", "param.twfb"]},
                 {"name": "sync_unique", "measure": "not_distinct", "nominal": 0}),
        ]}],
    }, source=str(suite / "spec.yaml"))
    config = BenchConfig.simulated(["s2lp"], driver="s2lp")
    with BenchRunner.from_config(config, simulate=True) as runner:
        record = runner.run(spec)
    steps = record.cases[0].steps
    assert record.status is Status.PASS, [(s.action, s.error) for s in steps]
    assert [m.name for s in steps for m in s.measurements] == [
        "only_the_short_frames", "alive_length", "cmd_pacing", "parameters_missing",
        "repeated_blocks", "sync_unique"]
