#!/usr/bin/env python3
"""Find a sensor by part of its name, read its version over BLE UART, disconnect.

    python examples/09_sensor_version.py                       # simulated: finds SENS-...
    python examples/09_sensor_version.py COM10                 # any sensor named *kappa*
    python examples/09_sensor_version.py COM10 kappa "rd version"
    python examples/09_sensor_version.py /dev/ttyACM0 SENS version

The name is matched on the host and ignores case, so "kappa" finds
KAPPA_5C1712_V11.00.00; the dongle's own name filter would not. The strongest
match is used. The command goes over the Nordic UART Service, and the reply is
printed as the sensor sent it.
"""

import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.nordic_dongle import NordicDongle

#: Long enough to hear a sensor that advertises every 9 s at least once.
SCAN_SECONDS = 10.0

#: A sensor that advertises rarely can fall outside a connect window; a few
#: attempts are normal, and each one reports why it failed.
CONNECT_ATTEMPTS = 3


def main(resource: str = "sim://", fragment: str = "", request: str = "rd version",
         log: str = "ble_session.log") -> int:
    if not fragment:
        fragment = "sens" if resource.startswith("sim://") else "kappa"

    with NordicDongle.connect(resource, log_path=log) as dongle:
        print("Scanning %.0f s for a sensor named *%s* (any case) ..." % (SCAN_SECONDS, fragment))
        dongle.scan(SCAN_SECONDS, active=True)
        try:
            sensor = dongle.select_by_name(fragment)
        except BenchToolsError as exc:
            print("           %s" % exc)
            return 1
        print("Selected : %s (%s, %d dBm)" % (sensor.name, sensor.qualified_address, sensor.rssi))

        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            try:
                dongle.open_link()
                break
            except BenchToolsError as exc:
                print("Attempt %d: %s" % (attempt, str(exc).split(". ")[0]))
        else:
            print("No link after %d attempts." % CONNECT_ATTEMPTS)
            return 1

        try:
            reply = dongle.command(request)
        except BenchToolsError as exc:
            print("Request  : %s\nNo reply : %s" % (request, exc))
            return 1
        finally:
            dongle.close_link()

        print("Request  : %s" % request)
        print("Reply    : %s" % reply.text.strip())
        print("Round trip %.1f ms on the dongle clock, %.1f ms on the host"
              % ((reply.dongle_us or 0) / 1000.0, reply.host_s * 1000.0))
        print("Disconnected. Session logged to %s" % dongle.log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
