"""Host-side rendering of captured waveforms.

``matplotlib`` is imported lazily and only here, so the driver, the capture
path and every measurement work without it. Ask for a plot without it
installed and you get a clear :class:`~tek3014b.errors.OptionalDependencyError`
rather than an ``ImportError`` from deep inside the call stack.

This complements - it does not replace - the instrument's own hardcopy: the
hardcopy is the authoritative record of what the operator saw, while a
host-side plot can be re-scaled, annotated with measured edges, and regenerated
from stored CSV long after the bench has been packed up.

Traces to: ANA-FR-020, ANA-FR-021, ANA-DD-PLOT.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

from ..core.errors import OptionalDependencyError
from .measure import SpreadResult
from .waveform import Waveform

__all__ = ["matplotlib_available", "plot_waveforms", "ENGINEERING_PREFIXES"]

#: Engineering prefixes used when auto-scaling the time axis.
ENGINEERING_PREFIXES = (
    (1.0, "s"),
    (1.0e-3, "ms"),
    (1.0e-6, "us"),
    (1.0e-9, "ns"),
    (1.0e-12, "ps"),
)

#: Trace colours matching the TDS3014B front panel, so a host-side plot reads
#: the same way as the instrument screen.
CHANNEL_COLOURS = {1: "#f6c700", 2: "#00c0f0", 3: "#f000c0", 4: "#00d060"}


def matplotlib_available() -> bool:
    """Return ``True`` when ``matplotlib`` can be imported."""
    try:
        import matplotlib  # noqa: F401  # pylint: disable=unused-import
    except ImportError:
        return False
    return True


def _time_scale(span: float):
    """Choose an engineering prefix for a time span.

    :returns: ``(divisor, unit_label)``.
    """
    for divisor, label in ENGINEERING_PREFIXES:
        if span >= divisor:
            return divisor, label
    return ENGINEERING_PREFIXES[-1]


def _pyplot():
    """Import ``matplotlib.pyplot`` on the non-interactive Agg backend.

    :raises OptionalDependencyError: if ``matplotlib`` is not installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # never require a display on a test rig
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise OptionalDependencyError(
            "plotting needs matplotlib (pip install matplotlib, or "
            "pip install benchtools[plot]). Waveform capture and CSV export do not."
        ) from exc
    return plt


def _new_figure(plt, count: int, separate_axes: bool, figure_size):
    """Create the figure and one axes per channel, shared or stacked.

    :returns: ``(figure, axes_list)`` with *count* entries in *axes_list*.
    """
    if separate_axes:
        # No explicit hspace here: tight_layout() below computes the spacing,
        # and setting both makes matplotlib warn and pick one.
        figure, axes_list = plt.subplots(
            count, 1, sharex=True, figsize=figure_size,
        )
        if count == 1:
            axes_list = [axes_list]
    else:
        figure, single = plt.subplots(figsize=figure_size)
        axes_list = [single] * count
    return figure, axes_list


def _plot_channels(axes_list, waveforms, divisor: float, separate_axes: bool,
                   show_trigger: bool) -> None:
    """Draw each channel's trace on its axes, in channel order."""
    for axes, channel in zip(axes_list, sorted(waveforms)):
        waveform = waveforms[channel]
        axes.plot(
            [t / divisor for t in waveform.times],
            waveform.volts,
            linewidth=1.0,
            color=CHANNEL_COLOURS.get(channel, None),
            label="CH%d" % channel,
        )
        axes.grid(True, which="major", alpha=0.25, linestyle=":")
        axes.set_ylabel("CH%d (V)" % channel if separate_axes else "Volts")
        if show_trigger:
            axes.axvline(0.0, color="#b00020", linewidth=0.8, alpha=0.6)


def _mark_spread(axes_list, channels, spread: SpreadResult, divisor: float,
                 unit: str) -> None:
    """Mark each channel's measured crossing and title the plot with the spread."""
    for axes, channel in zip(axes_list, channels):
        crossing = spread.crossings.get(channel)
        if crossing is None:
            continue
        axes.plot(
            [crossing.time / divisor],
            [crossing.threshold],
            marker="o",
            markersize=5,
            color=CHANNEL_COLOURS.get(channel, "#ffffff"),
            markeredgecolor="#202020",
            zorder=5,
        )
        axes.axvline(
            crossing.time / divisor,
            color=CHANNEL_COLOURS.get(channel, "#808080"),
            linewidth=0.7,
            linestyle="--",
            alpha=0.7,
        )
    annotation = "%s spread: %.4g %s (CH%d first, CH%d last)" % (
        "rising" if spread.direction.value == "RISE" else "falling",
        spread.spread / divisor,
        unit,
        spread.earliest_channel,
        spread.latest_channel,
    )
    axes_list[0].set_title(annotation, fontsize=10, loc="left")


def plot_waveforms(  # pylint: disable=too-many-arguments,too-many-positional-arguments  # public API; each option is documented
    waveforms: Mapping[int, Waveform],
    path: str,
    title: str = "Tektronix TDS3014B capture",
    spread: Optional[SpreadResult] = None,
    show_trigger: bool = True,
    separate_axes: bool = False,
    dpi: int = 120,
    figure_size=(11.0, 6.0),
) -> str:
    """Render *waveforms* to an image file.

    :param waveforms: Channel number to :class:`~tek3014b.waveform.Waveform`.
    :param path: Destination image path; the suffix selects the format.
    :param title: Figure title.
    :param spread: When given, each channel's measured crossing is marked and
        the overall spread is annotated, which is what makes a skew result
        reviewable rather than just a number in a log.
    :param show_trigger: Draw a vertical line at t = 0, the trigger point.
    :param separate_axes: Stack the channels on their own axes instead of
        overlaying them on shared axes.
    :returns: The path written.
    :raises OptionalDependencyError: if ``matplotlib`` is not installed.
    """
    if not waveforms:
        raise ValueError("no waveforms to plot")
    plt = _pyplot()

    channels = sorted(waveforms)
    divisor, unit = _time_scale(waveforms[channels[0]].duration or 1.0)
    figure, axes_list = _new_figure(plt, len(channels), separate_axes, figure_size)
    _plot_channels(axes_list, waveforms, divisor, separate_axes, show_trigger)
    if spread is not None:
        _mark_spread(axes_list, channels, spread, divisor, unit)

    axes_list[-1].set_xlabel("Time (%s), relative to trigger" % unit)
    if not separate_axes:
        axes_list[0].legend(loc="upper right", fontsize=9, framealpha=0.85)

    figure.suptitle(title, fontsize=12)
    figure.tight_layout()

    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    figure.savefig(path, dpi=dpi)
    plt.close(figure)
    return path
