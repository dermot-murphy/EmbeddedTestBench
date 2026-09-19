#!/usr/bin/env python3
"""Measure period two ways and compare them.

The instrument returns a single period value. Measuring host-side over the
whole captured record additionally gives the minimum, maximum, standard
deviation and peak-to-peak jitter across every cycle on screen.

    python examples/03_period_and_jitter.py 192.168.1.50
    python examples/03_period_and_jitter.py sim://
"""

import sys

from benchtools.core.errors import MeasurementError
from benchtools.instruments.tek3014b import Tek3014B


def main(resource: str = "sim://") -> int:
    with Tek3014B.connect(resource) as scope:
        print("Connected to:", scope.identity())

        scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0, coupling="DC")
        scope.set_time_per_div(1e-6)      # several cycles of a 1 MHz signal on screen
        scope.configure_edge_trigger(source=1, level=1.65, mode="NORMAL")

        waveforms, period = scope.measure_period_host(1)

        print("\nHost-side, over %d cycles of the captured record:" % period.count)
        print("  mean      : %.6f us" % (period.mean * 1e6))
        print("  minimum   : %.6f us" % (period.minimum * 1e6))
        print("  maximum   : %.6f us" % (period.maximum * 1e6))
        print("  stdev     : %.6f ns" % (period.standard_deviation * 1e9))
        print("  pk-pk jit : %.6f ns" % (period.peak_to_peak_jitter * 1e9))
        print("  frequency : %.6f MHz" % (period.frequency / 1e6))

        try:
            print("\nInstrument engine:")
            print("  period    : %.6f us" % (scope.measure_period(1) * 1e6))
            print("  frequency : %.6f MHz" % (scope.measure_frequency(1) / 1e6))
        except MeasurementError as exc:
            print("  unavailable:", exc)

        print("\nOther instrument measurements on CH1:")
        for name, value in sorted(scope.measure_summary(1).items()):
            print("  %-12s %.6g" % (name, value))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sim://"))
