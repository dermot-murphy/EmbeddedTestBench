"""rf_monitor's Diagnostics and Sync screens (#155).

Traces to: VIEW-FR-037 .. VIEW-FR-039, SWE4-UT-VIEWDIAG.
"""

from __future__ import annotations

import struct

import pytest

from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.viewer.diagnostics import Diagnostics, SyncTracker


def _alive(repeat, total=3, ticks=400):
    frame = bytearray(35)
    frame[0:8] = bytes.fromhex("5c171203060c0403")
    frame[8] = ((repeat + 1) << 4) | total
    frame[12:14] = struct.pack(">H", ticks)
    return bytes(frame)


def _cmd(param, retry=0):
    frame = bytearray(15)
    frame[0:8] = bytes.fromhex("5c171203060c0408")
    frame[8] = 0x11
    frame[9:12] = bytes.fromhex("5c1712")
    frame[12:14] = struct.pack(">H", param)
    frame[14] = retry
    return bytes(frame)


def _response(param, timer, slot=5):
    frame = bytearray(19)
    frame[0:8] = bytes.fromhex("f000000306000409")
    frame[9:12] = bytes.fromhex("5c1712")
    frame[12:14] = struct.pack(">H", param)
    frame[14:18] = struct.pack(">I", timer)
    frame[18] = slot
    return bytes(frame)


def _fft():
    frame = bytearray(97)
    frame[0:8] = bytes.fromhex("5c171203060c0406")
    return bytes(frame)


def _frame(payload, when):
    decoded = decode_kepler_frame(payload)
    return {"t": when, "sensor_id": decoded["sensor_id"], "decoded": decoded}


def _diagnostics(*frames):
    diagnostics = Diagnostics()
    for payload, when in frames:
        diagnostics.feed(_frame(payload, when))
    return diagnostics


def _row(view, kind):
    return next(row for row in view["types"] if row["type"] == kind)


class TestDiagnostics:
    def test_frames_packets_and_drops(self):
        frames = []
        for minute in range(4):
            for repeat in range(3):
                if minute == 1 and repeat == 2:
                    continue                       # one copy lost
                frames.append((_alive(repeat), minute * 60.0 + repeat * 0.05))
        view = _diagnostics(*frames).view()
        row = _row(view, "ALIVE")
        assert (row["frames"], row["packets"], row["expected"], row["dropped"]) == (4, 11, 12, 1)
        assert row["success_pct"] == pytest.approx(91.7)
        assert view["overall"] == {"expected": 12, "dropped": 1, "received": 11,
                                   "success_pct": 91.7}

    def test_periods_mean_deviation_and_extremes_with_their_frames(self):
        view = _diagnostics((_alive(0), 0.0), (_alive(0), 60.0), (_alive(0), 150.0),
                            (_alive(0), 180.0)).view()
        row = _row(view, "ALIVE")
        assert row["mean_s"] == 60.0
        assert row["std_s"] == pytest.approx(24.495, abs=0.001)
        assert (row["min_s"], row["min_between"]) == (30.0, (150.0, 180.0))
        assert (row["max_s"], row["max_between"]) == (90.0, (60.0, 150.0))

    def test_a_lost_first_copy_still_counts_the_frame(self):
        view = _diagnostics((_alive(1), 0.0), (_alive(2), 0.05), (_alive(1), 60.0),
                            (_alive(0), 120.0)).view()
        row = _row(view, "ALIVE")
        # copy 1 lost from the first burst; copies 1 and 3 from the second
        assert row["frames"] == 3 and row["dropped"] == 3

    def test_a_burst_still_arriving_is_not_yet_counted(self):
        row = _row(_diagnostics((_alive(0), 0.0), (_alive(1), 0.05)).view(), "ALIVE")
        assert (row["expected"], row["dropped"]) == (0, 0)

    def test_a_burst_closes_after_a_gap_without_a_first_copy(self):
        view = _diagnostics((_alive(0), 0.0), (_alive(1), 0.05), (_alive(1), 5.0)).view()
        assert _row(view, "ALIVE")["frames"] == 2

    def test_types_without_a_counter_count_no_drops(self):
        row = _row(_diagnostics((_fft(), 0.0), (_fft(), 10.0)).view(), "FFT")
        assert (row["frames"], row["expected"], row["success_pct"]) == (2, 0, None)

    def test_the_last_ten_frames_newest_first_with_their_deltas(self):
        view = _diagnostics(*[(_alive(0), minute * 60.0) for minute in range(12)]).view()
        recent = _row(view, "ALIVE")["recent"]
        assert len(recent) == 10
        assert recent[0] == {"t": 660.0, "delta_s": 60.0}

    def test_one_sensor_at_a_time_and_reset(self):
        other = bytearray(_alive(0))
        other[0:3] = bytes.fromhex("5c314e")
        diagnostics = _diagnostics((_alive(0), 0.0), (bytes(other), 1.0))
        assert diagnostics.view("5C314E")["sensor"] == "5C314E"
        assert diagnostics.view()["sensors"] == ["5C1712", "5C314E"]
        diagnostics.reset("5C1712")
        assert diagnostics.view()["sensors"] == ["5C314E"]
        diagnostics.reset()
        assert not diagnostics.view()["types"]

    def test_an_unknown_type_is_counted_not_an_error(self):
        diagnostics = Diagnostics()
        assert diagnostics.feed({"t": 1.0, "sensor_id": "5C1712",
                                 "decoded": {"type": None, "sensor_id": "5C1712"}})
        assert diagnostics.view()["types"][0]["type"] == "UNKNOWN"


class TestSync:
    def _track(self, *frames):
        tracker = SyncTracker()
        for payload, when in frames:
            tracker.feed(_frame(payload, when))
        return tracker.view()

    def test_a_lores_then_hires_handshake(self):
        view = self._track((_cmd(0x0001), 0.0), (_response(1, 120000), 0.5),
                           (_cmd(0x8001), 1.0), (_response(2, 4000000), 115.0),
                           (_cmd(0x8002, retry=1), 115.5))
        row = view["sensors"][0]
        assert (row["sensor_id"], row["phase"], row["retry"], row["slot"]) == (
            "5C1712", "ACK_HIRES", 1, 5)
        assert row["lores_remaining_s"] == pytest.approx(120.5 - 115.5)
        assert row["hires_remaining_s"] == pytest.approx(119.0 - 115.5)
        assert row["state"] == "hires"

    def test_countdowns_run_from_the_frame_s_time_and_fire(self):
        row = self._track((_response(2, 1000000), 10.0), (_cmd(0x0003), 12.0))["sensors"][0]
        assert row["hires_remaining_s"] == pytest.approx(-1.0)
        assert row["state"] == "fired" and row["phase"] == "Idle (GENERAL)"

    def test_a_nack_and_a_new_request_starting_afresh(self):
        assert self._track((_cmd(0x7F01), 0.0))["sensors"][0]["state"] == "nack"
        row = self._track((_response(1, 1000), 0.0), (_cmd(0x0001), 5.0))["sensors"][0]
        assert row["lores_remaining_s"] is None and row["phase"] == "REQ_LORES sent"

    def test_an_idle_sensor_leaves_the_table(self):
        other = bytearray(_cmd(0x0001))
        other[0:3] = bytes.fromhex("5c314e")
        view = self._track((_cmd(0x0001), 0.0), (bytes(other), 1300.0))
        assert [row["sensor_id"] for row in view["sensors"]] == ["5C314E"]

    def test_other_frames_are_not_sync(self):
        assert not SyncTracker().feed(_frame(_alive(0), 1.0))
