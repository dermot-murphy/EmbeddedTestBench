#!/usr/bin/env python3
"""Measure a board's supply current with a TTi 1604, and log it.

    python examples/09_dmm_current.py                  # simulated meter
    python examples/09_dmm_current.py /dev/ttyUSB1     # a real 1604
    python examples/09_dmm_current.py COM6

The meter goes in series with the supply, on its mA socket (to 400 mA). This
selects DC milliamps - which puts the meter's shunt across its input, so the
leads must already be in the mA and COM sockets and in series, not across a
rail - takes one measurement, locks the range so the log does not jump between
ranges, and logs ten readings (four seconds).

Every number printed is a live reading: the driver refuses overload, a held or
recalled display, and a Null reading nobody asked for.
"""

import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.tti1604 import Function, Tti1604


def main(resource: str = "sim://") -> int:
    with Tti1604.connect(resource) as dmm:
        if resource.startswith("sim"):
            # Something for the simulated meter to measure.
            dmm.transport.simulator.set_input("dc_amps", 0.01234)

        print("Meter    : %s %s" % (dmm.manufacturer, dmm.model))
        print("Showing  : %s on the %s range"
              % (dmm.last_reading.function, dmm.last_reading.range_label))

        amps = dmm.measure(Function.DC_MILLIAMPS)
        reading = dmm.last_reading
        print("Current  : %.4f mA (%s range, %s)"
              % (amps * 1e3, reading.range_label,
                 "auto" if reading.auto_range else "manual"))

        # Lock the range the meter chose, so the log is at one resolution.
        dmm.set_range(reading.full_scale)
        print("\nLogging ten readings on the locked %s range:" % reading.range_label)
        for index, sample in enumerate(dmm.read_many(10)):
            flag = "" if sample.is_live else "   <-- not live"
            print("  %2d  %9.4f mA%s" % (index, sample.value * 1e3, flag))

        dmm.set_auto_range()
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv[1:]))
    except BenchToolsError as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
