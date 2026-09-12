#!/usr/bin/env python3
"""Measure the spread in time of four channels going high.

This is the N-channel timing question the instrument's own measurement engine
cannot answer directly: its DELAY measurement takes only two sources at a
time. All four channels are digitised in one acquisition on a common time
base, so their relative edge times are directly comparable.

    python examples/02_channel_spread.py 192.168.1.50
    python examples/02_channel_spread.py sim://
"""

import sys

from tek3014b import Tek3014B, plot_waveforms

CHANNELS = [1, 2, 3, 4]


def main(resource: str = "sim://") -> int:
    with Tek3014B.connect(resource) as scope:
        print("Connected to:", scope.identity())

        # Stack the traces so none of them runs off the digitiser, which would
        # corrupt the amplitude estimate the 50% threshold is derived from.
        for channel, position in zip(CHANNELS, (-4.0, -3.0, -2.0, -1.0)):
            scope.configure_channel(channel, volts_per_div=1.0,
                                    position_div=position, coupling="DC")

        scope.set_time_per_div(200e-9)
        scope.configure_edge_trigger(source=1, level=1.65, slope="RISE", mode="NORMAL")

        waveforms, spread = scope.measure_channel_spread(
            CHANNELS,
            direction="RISE",   # "going high"
            percent=50.0,       # each channel crosses its own mid-point
        )

        print("\nRising-edge timing, relative to the trigger")
        print("-" * 46)
        for channel in sorted(spread.times):
            print(
                "  CH%d  t = %9.3f ns   skew = %+8.3f ns"
                % (channel, spread.times[channel] * 1e9, spread.skews[channel] * 1e9)
            )
        print("-" * 46)
        print("  first : CH%d" % spread.earliest_channel)
        print("  last  : CH%d" % spread.latest_channel)
        print("  SPREAD: %.3f ns" % (spread.spread * 1e9))
        print("  stdev : %.3f ns" % (spread.standard_deviation * 1e9))

        # Cross-check two of the channels against the instrument's own engine.
        reference = spread.earliest_channel
        for channel in sorted(spread.times):
            if channel == reference:
                continue
            instrument = scope.measure_delay(reference, channel)
            print(
                "  CH%d-CH%d  host %+8.3f ns   instrument %+8.3f ns"
                % (reference, channel, spread.skews[channel] * 1e9, instrument * 1e9)
            )

        print("\nPlot:", plot_waveforms(waveforms, "spread.png",
                                        title="Channel timing spread", spread=spread))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sim://"))
