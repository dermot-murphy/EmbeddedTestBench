"""rf_monitor's TWF screen: reassembly and spectrum (#154).

Traces to: VIEW-FR-034 .. VIEW-FR-036, SWE4-UT-VIEWTWF.
"""

from __future__ import annotations

import builtins
import math
import struct

import pytest

from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.instruments.s2lp.kepler_tables import twf_sample
from benchtools.viewer import twf as twf_module
from benchtools.viewer.twf import TwfAssembler, fill_gaps, spectrum

_PERMUTE = {"distance": 0x00, "none": 0x08, "polynomial": 0x10}
_PARAM_PERMUTE = {"distance": 0, "none": 1, "polynomial": 2}


def _param(method, layout):
    """The TWF param word: axis, TWF scale, TWFB and permutation."""
    return (layout.get("axis", 0) << 14) | (layout.get("twf_scale", 0) << 12) | \
        ((1 if layout.get("twfb") else 0) << 8) | (_PARAM_PERMUTE[method] << 2)


def _frame(samples, method, where, layout):
    """One TWF frame: *where* is (packet, repeat, repeats)."""
    packet, repeat, repeats = where
    frame = bytearray(100)
    frame[0:8] = bytes.fromhex("5c171203060c0404")
    frame[8] = _PERMUTE[method]
    frame[9] = ((repeat + 1) << 4) | repeats
    frame[13:15] = struct.pack(">H", _param(method, layout))
    frame[15:17] = struct.pack(">H", layout.get("odr_code", 1600))
    frame[17:19] = struct.pack(">H", packet)
    frame[19:21] = struct.pack(">H", len(samples) // 32)
    for slot in range(32):
        value = samples[twf_sample(method, packet, slot, len(samples), repeat)]
        frame[29 + 2 * slot:31 + 2 * slot] = struct.pack(">h", value)
    return bytes(frame)


def _frames(samples, method="none", repeats=1, **layout):
    """Frames carrying *samples*, laid out as the firmware lays them out.

    *layout*: ``dropped`` packets, ``twfb``, ``axis``, ``twf_scale``, ``odr_code``.
    """
    return [_frame(samples, method, (packet, repeat, repeats), layout)
            for packet in range(len(samples) // 32) for repeat in range(repeats)
            if packet not in layout.get("dropped", ())]


def _assemble(frames):
    assembler = TwfAssembler()
    for index, payload in enumerate(frames):
        decoded = decode_kepler_frame(payload)
        assembler.feed({"t": float(index), "sensor_id": decoded["sensor_id"], "decoded": decoded})
    return assembler


SAMPLES = [((n * 37) % 2001) - 1000 for n in range(256)]
MG = 8 * 1000.0 / 32767.0               # twf_scale 0


class TestReassembly:
    @pytest.mark.parametrize("method, repeats", [("none", 1), ("distance", 1),
                                                 ("polynomial", 1), ("polynomial", 3)])
    def test_sample_for_sample_under_each_method(self, method, repeats):
        view = _assemble(_frames(SAMPLES, method, repeats)).view()
        assert view["capture"]["complete"]
        assert [v for _t, v in view["waveform"]] == pytest.approx(
            [s * MG for s in SAMPLES], abs=1e-3)

    def test_a_missing_packet_is_a_gap(self):
        view = _assemble(_frames(SAMPLES, "none", dropped={2})).view()
        values = [v for _t, v in view["waveform"]]
        assert values[64:96] == [None] * 32 and values[63] is not None
        capture = view["capture"]
        assert (capture["complete"], capture["packets"], capture["missed"]) == (False, 7, 1)
        assert capture["signal"] == "Fair"            # 7 of 8, 87.5%

    def test_distance_spreads_a_lost_packet_across_the_waveform(self):
        values = [v for _t, v in _assemble(_frames(SAMPLES, "distance", dropped={0})).view()[
            "waveform"]]
        assert [index for index, value in enumerate(values) if value is None] == \
            list(range(0, 256, 8))

    def test_the_twf_scale_sets_mg_and_the_odr_code_the_time(self):
        view = _assemble(_frames(SAMPLES, twf_scale=2, odr_code=0x8000 | 2560)).view()
        capture = view["capture"]
        assert capture["full_scale_mg"] == 32000 and capture["odr_hz"] == 25600
        assert view["waveform"][1][0] == pytest.approx(1000.0 / 25600, abs=1e-6)
        assert view["waveform"][5][1] == pytest.approx(SAMPLES[5] * 32000 / 32767, abs=1e-3)

    def test_buffer_and_axis_from_the_frame(self):
        assembler = _assemble(_frames(SAMPLES, twfb=True, axis=2))
        assert assembler.view(buffer="B", axis="Z")["capture"]["complete"]
        fallback = assembler.view(buffer="A", axis="Z")
        assert fallback["buffer"] == "B"         # nothing in A: shows B
        assert assembler.view(buffer="A", axis="X")["capture"] is None

    def test_packet_zero_after_a_complete_capture_starts_the_next(self):
        frames = _frames(SAMPLES) + _frames([0] * 256)[:1]
        view = _assemble(frames).view()
        assert view["capture"]["packets"] == 1 and not view["capture"]["complete"]

    def test_frames_that_are_not_twf_are_ignored(self):
        assert not TwfAssembler().feed({"t": 1.0, "sensor_id": "5C1712",
                                        "decoded": {"type": "ALIVE"}})


class TestSpectrum:
    def test_a_sine_peaks_at_its_frequency(self):
        odr, size = 1024.0, 1024
        values = [500.0 * math.sin(2 * math.pi * 64 * n / odr) for n in range(size)]
        bins = spectrum(values, odr)
        peak = max(bins, key=lambda b: b[1])
        assert peak[0] == 64.0
        assert peak[1] == pytest.approx(250.0, rel=0.01)   # Hann window halves it
        assert bins[1][0] == pytest.approx(odr / size)

    def test_gaps_are_filled_before_the_transform(self):
        assert fill_gaps([None, 1.0, None, None, 4.0, None]) == [1.0, 1.0, 2.0, 3.0, 4.0, 4.0]
        assert fill_gaps([None, None]) == [0.0, 0.0]

    def test_without_numpy_the_numbers_are_the_same(self, monkeypatch):
        values = [math.sin(n / 3.0) + (n % 5) for n in range(64)]
        with_numpy = spectrum(values, 100.0)
        real_import = builtins.__import__

        def no_numpy(name, *args, **kwargs):
            if name == "numpy":
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_numpy)
        plain = spectrum(values, 100.0)
        assert [b[0] for b in plain] == [b[0] for b in with_numpy]
        assert [b[1] for b in plain] == pytest.approx([b[1] for b in with_numpy], abs=1e-5)

    def test_a_length_that_is_not_a_power_of_two(self, monkeypatch):
        monkeypatch.setattr(twf_module, "_fft", lambda values: pytest.fail("radix-2 used"))
        real_import = builtins.__import__

        def no_numpy(name, *args, **kwargs):
            if name == "numpy":
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_numpy)
        assert len(spectrum([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 6.0)) == 4

    def test_nothing_to_transform(self):
        assert spectrum([1.0], 100.0) == [] and spectrum([1.0, 2.0], 0) == []
