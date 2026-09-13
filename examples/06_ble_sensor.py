#!/usr/bin/env python3
"""Scan for a BLE sensor, profile its advertising, and time its replies.

    python examples/06_ble_sensor.py                 # simulated dongle and sensors
    python examples/06_ble_sensor.py COM5            # a dongle on Windows
    python examples/06_ble_sensor.py /dev/ttyACM0 SENS-01
    python examples/06_ble_sensor.py serial://socket://bench-pc:4001

Everything printed here comes from the dongle's own microsecond clock except
where it says otherwise.
"""

import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.nordic_dongle import LatencySource, NordicDongle


def main(resource: str = "sim://", wanted: str = "SENS-01", log: str = "ble_session.log") -> int:
    with NordicDongle.connect(resource, log_path=log) as dongle:
        identity = dongle.identify()
        print("Dongle   : %s %s, protocol %s" % (identity.manufacturer, identity.model, identity.firmware))

        # --- scan ------------------------------------------------------
        print("\nScanning 3 s ...")
        sensors = dongle.scan(3.0)
        for sensor in sensors:
            print("           %s" % sensor)
        if not sensors:
            print("           nothing found - is the sensor powered?")
            return 1

        # --- select ----------------------------------------------------
        chosen = dongle.find_sensor(wanted) or sensors[0]
        dongle.select(chosen)
        dongle.log_note("sensor under test: %s" % chosen.qualified_address)
        print("\nSelected : %s (%s)" % (chosen.name or "(no name)", chosen.qualified_address))

        # --- advertising profile --------------------------------------
        print("\nAdvertising profile over 10 s (nominal 100 ms):")
        profile = dongle.measure_advertising_profile(10.0, expected_interval=0.100)
        print("           events        %d  (%d reports before coalescing)"
              % (profile.count, profile.reports))
        print("           interval      %.2f ms  (min %.2f, max %.2f)"
              % (profile.mean_interval_s * 1000.0,
                 profile.minimum_interval_s * 1000.0,
                 profile.maximum_interval_s * 1000.0))
        print("           jitter        %.2f ms  (a conforming sensor shows %.2f from advDelay)"
              % (profile.jitter_s * 1000.0, profile.expected_jitter_s * 1000.0))
        print("           missed        %d of %d expected" % (profile.missed_events, profile.expected_events))
        print("           duty cycle    %.3f" % profile.duty_cycle)
        print("           within spec   %s" % profile.within_specification(0.100))
        if not profile.is_complete:
            print("           WARNING: %d report(s) lost on the way to the host, so a "
                  "missed beacon cannot be blamed on the sensor" % profile.lost_reports)

        # --- command and response over BLE UART -----------------------
        print("\nConnecting ...")
        dongle.open_link()
        print("           connection interval %.1f ms" % (dongle.connection_interval_us / 1000.0))
        try:
            for request in ("version", "id", "temp"):
                try:
                    reply = dongle.command(request)
                except BenchToolsError as exc:
                    print("           %-8s -> %s" % (request, str(exc)[:60]))
                    continue
                print("           %-8s -> %-10s  %6.2f ms (dongle)  %6.2f ms (host)"
                      % (request, reply.text, (reply.dongle_us or 0) / 1000.0, reply.host_s * 1000.0))

            print("\nResponse time over 10 exchanges:")
            for source in (LatencySource.DONGLE, LatencySource.HOST):
                timing = dongle.measure_response_time("measure", repeat=10, source=source)
                note = "" if timing.is_trustworthy else "   <- not resolvable by this clock"
                print("           %-7s %7.2f ms  (min %.2f, max %.2f, sd %.3f)%s"
                      % (source.value, timing.milliseconds,
                         timing.minimum_s * 1000.0, timing.maximum_s * 1000.0,
                         timing.standard_deviation_s * 1000.0, note))
        finally:
            dongle.close_link()

        print("\nSession logged to %s" % dongle.log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
