#!/usr/bin/env python3
"""Identify a Pico 2 + SHT30-D thermometer, then log the temperature.

    python examples/11_pico_thermometer.py                    # simulated
    python examples/11_pico_thermometer.py /dev/ttyACM0       # a real Pico 2
    python examples/11_pico_thermometer.py COM5 --count 60

The first thing printed is what the firmware says it is: its name, version and
the commit it was built from.
A bench log that does not record which firmware produced its numbers cannot be
compared with the next one.

A reading that fails is reported as a failure, not skipped. The sensor can be
absent, a frame can fail its CRC, and the bus can hang; in each case the
firmware answers ``rd temperature`` with ``Error``. Each is a line in the log,
because a gap that nobody explained looks like a steady temperature.

Traces to: PICO-FR-041, PICO-FR-042, PICO-FR-043.
"""

import argparse
import sys
import time

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.pico_sht30 import NoReadingError, PicoSht30


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("port", nargs="?", default="sim://", help="serial port, or sim://")
    parser.add_argument("--count", type=int, default=5, help="readings to take")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between readings")
    args = parser.parse_args()

    try:
        thermometer = PicoSht30.connect(args.port)
    except BenchToolsError as exc:
        print("could not connect to %s: %s" % (args.port, exc), file=sys.stderr)
        return 1

    failures = 0
    with thermometer:
        info = thermometer.firmware_info()
        print("%s %s (commit %s), %s" % (info.name, info.version, info.sha, info.copyright))

        for index in range(args.count):
            if index:
                time.sleep(args.interval)
            try:
                reading = thermometer.read()
            except NoReadingError as exc:
                failures += 1
                print("%s  FAILED  %s" % (time.strftime("%H:%M:%S"), exc))
                continue
            print("%s  %s °C" % (time.strftime("%H:%M:%S"), reading.text))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
