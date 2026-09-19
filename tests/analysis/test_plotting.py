"""Host-side plotting.

Traces to: SWE1-FR-070, SWE1-FR-071, SWE4-UT-PLOT.
"""

from __future__ import annotations

import builtins

import pytest

from benchtools.core.errors import OptionalDependencyError
from benchtools.analysis.measure import measure_channel_spread
from benchtools.analysis.plotting import _time_scale, matplotlib_available, plot_waveforms
from benchtools.analysis.waveform import Waveform

pytestmark = pytest.mark.skipif(
    not matplotlib_available(), reason="matplotlib is not installed (it is an optional extra)"
)


def ramp(source: str, delay: float = 0.0) -> Waveform:
    """A single clean rising edge, delayed by *delay* seconds."""
    times = [index * 1.0e-10 for index in range(2000)]
    volts = [0.0 if t < 50.0e-9 + delay else 3.3 for t in times]
    return Waveform(source=source, times=times, volts=volts)


class TestTimeScaling:
    @pytest.mark.parametrize(
        "span,unit",
        [(2.0, "s"), (2.0e-3, "ms"), (2.0e-6, "us"), (2.0e-9, "ns"), (2.0e-12, "ps")],
    )
    def test_engineering_prefix_is_chosen(self, span, unit):
        assert _time_scale(span)[1] == unit

    def test_absurdly_small_span_falls_back_to_picoseconds(self):
        assert _time_scale(1.0e-18)[1] == "ps"


class TestPlotting:
    def test_png_is_written(self, tmp_path):
        path = plot_waveforms({1: ramp("CH1")}, str(tmp_path / "plot.png"))
        assert open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"

    def test_multiple_channels_overlaid(self, tmp_path):
        waveforms = {channel: ramp("CH%d" % channel, delay=channel * 1.0e-9)
                     for channel in (1, 2, 3, 4)}
        path = plot_waveforms(waveforms, str(tmp_path / "multi.png"))
        assert open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"

    def test_separate_axes(self, tmp_path):
        waveforms = {1: ramp("CH1"), 2: ramp("CH2", 2.0e-9)}
        path = plot_waveforms(waveforms, str(tmp_path / "stacked.png"), separate_axes=True)
        assert open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"

    def test_single_channel_on_separate_axes(self, tmp_path):
        """One channel must not trip the axes-list handling."""
        path = plot_waveforms({1: ramp("CH1")}, str(tmp_path / "one.png"), separate_axes=True)
        assert open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"

    def test_spread_annotation(self, tmp_path):
        waveforms = {channel: ramp("CH%d" % channel, delay=channel * 2.0e-9)
                     for channel in (1, 2, 3)}
        spread = measure_channel_spread(waveforms)
        path = plot_waveforms(waveforms, str(tmp_path / "spread.png"), spread=spread)
        assert open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"

    def test_svg_format_follows_the_suffix(self, tmp_path):
        path = plot_waveforms({1: ramp("CH1")}, str(tmp_path / "plot.svg"))
        assert open(path, encoding="utf-8").read(200).lstrip().startswith("<?xml")

    def test_nested_directories_are_created(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "plot.png"
        assert plot_waveforms({1: ramp("CH1")}, str(target)) == str(target)
        assert target.exists()

    def test_empty_input_is_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="no waveforms"):
            plot_waveforms({}, str(tmp_path / "nothing.png"))


class TestMissingDependency:
    def test_clear_error_when_matplotlib_is_absent(self, tmp_path, monkeypatch):
        """Without matplotlib the failure must name the missing extra, not ImportError."""
        real_import = builtins.__import__

        def refuse_matplotlib(name, *args, **kwargs):
            if name.startswith("matplotlib"):
                raise ImportError("no matplotlib for this test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", refuse_matplotlib)
        with pytest.raises(OptionalDependencyError, match="matplotlib"):
            plot_waveforms({1: ramp("CH1")}, str(tmp_path / "plot.png"))
