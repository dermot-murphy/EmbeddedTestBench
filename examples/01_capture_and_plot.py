#!/usr/bin/env python3
"""Configure two channels, trigger once, then save a CSV, a plot and a screenshot.

Run against a real instrument::

    python examples/01_capture_and_plot.py 192.168.1.50

or against the built-in simulator, which needs no hardware::

    python examples/01_capture_and_plot.py sim://
"""

import sys

from benchtools.analysis import plot_waveforms
from benchtools.instruments.tek3014b import Tek3014B

DESTINATION = "capture"


def main(resource: str = "sim://") -> int:
    with Tek3014B.connect(resource) as scope:
        print("Connected to:", scope.identity())

        # Vertical: 1 V/div, traces separated so they do not overlap on screen.
        scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0, coupling="DC")
        scope.configure_channel(2, volts_per_div=1.0, position_div=1.0, coupling="DC")

        # Horizontal and trigger.
        scope.set_time_per_div(200e-9)
        scope.set_record_length(10000)
        scope.configure_edge_trigger(source=1, level=1.65, slope="RISE", mode="NORMAL")

        # One acquisition, both channels: their timing is directly comparable.
        waveforms = scope.capture_single([1, 2], timeout=10.0)

        for channel, waveform in sorted(waveforms.items()):
            print(
                "CH%d: %d points, %.3f Vpp, %.1f ns/sample%s"
                % (
                    channel,
                    len(waveform),
                    waveform.peak_to_peak,
                    waveform.sample_interval * 1e9,
                    "  [CLIPPED]" if waveform.is_clipped else "",
                )
            )

        print("CSV       :", scope.save_csv(waveforms, DESTINATION + ".csv"))
        print("Plot      :", plot_waveforms(waveforms, DESTINATION + ".png"))
        print("Screenshot:", scope.screenshot(DESTINATION + "_screen.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sim://"))
