#!/usr/bin/env python3
"""Flash, verify, inspect and time firmware through a SEGGER J-Link.

    python examples/05_jlink_firmware.py                      # simulator
    python examples/05_jlink_firmware.py jlink://             # local probe
    python examples/05_jlink_firmware.py jlink://192.168.1.9:2331   # probe elsewhere

With a real probe, pass the device and ELF as well::

    python examples/05_jlink_firmware.py jlink:// nRF52840_xxAA build/app.elf
"""

import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.jlink import JLinkProbe, TimingMethod


def main(resource: str = "sim://", device: str = "", elf: str = "") -> int:
    with JLinkProbe.connect(
        resource,
        device=device or None,
        elf=elf or None,
        core_clock_hz=64.0e6,
    ) as probe:
        identity = probe.identify()
        print("Probe    : %s (S/N %s, %s)" % (identity.model, identity.serial_number, identity.firmware))
        print("Target   : attached=%s halted=%s" % (probe.is_attached, probe.is_halted))

        # --- programme and prove what is on the part -------------------
        result = probe.flash(verify=True)
        print("\nFlashed  : %d bytes in %d section(s) in %.2f s"
              % (result.bytes_written, len(result.sections), result.seconds))
        for name, (address, size) in sorted(result.sections.items()):
            print("           %-10s 0x%08x  %6d bytes" % (name, address, size))
        print("Verified : %s" % result.verified)

        # --- RTT, which needs no halting ------------------------------
        probe.rtt_start(log_path="rtt.log")
        try:
            probe.reset(halt=True)
            probe.run_to("sensor.c:75")
            print("\nRTT      :")
            for line in probe.rtt_read_lines():
                print("           %s" % line)
            reply = probe.rtt_command("version", r"(\d+\.\d+\.\d+)")
            print("Version  : %s (asked over RTT)" % reply.group(1))
        finally:
            probe.rtt_stop()

        # --- symbols: variables and the call stack --------------------
        print("\nVariables:")
        for name in ("sensor_mv", "sensor_count", "firmware_version"):
            print("           %-18s = %-8s at 0x%08x (%d bytes)"
                  % (name, probe.read_variable(name),
                     probe.variable_address(name), probe.variable_size(name)))

        print("\nCall stack at sensor.c:75:")
        for frame in probe.call_stack():
            print("           %s" % frame)

        # --- RAM ------------------------------------------------------
        address = probe.variable_address("sensor_count")
        probe.write_word(address, 123)
        print("\nRAM      : wrote 123 to 0x%08x, reads back %d"
              % (address, probe.read_word(address)))

        # --- timing, four ways ----------------------------------------
        print("\nTime from sensor.c:40 to sensor.c:75:")
        attempts = [
            (TimingMethod.CYCLE_COUNTER, {}),
            (TimingMethod.HOST_CLOCK, {}),
            (TimingMethod.SWO_ITM, {"itm_port": 1}),
            (TimingMethod.TARGET_TIMER,
             {"start_variable": "timer_start", "end_variable": "timer_end", "timer_hz": 64.0e6}),
        ]
        for method, options in attempts:
            try:
                timing = probe.measure_time_between(
                    "sensor.c:40", "sensor.c:75", method=method, repeat=3, **options
                )
            except BenchToolsError as exc:
                print("           %-14s unavailable: %s" % (method.value, str(exc)[:60]))
                continue
            note = "" if timing.is_trustworthy else "   <- below this method's resolution"
            print("           %-14s %9.3f us  (%s cycles, halts=%s)%s"
                  % (method.value, timing.microseconds,
                     "%d" % timing.cycles if timing.cycles else "-",
                     timing.halts_target, note))

        print("\nRTT log written to rtt.log")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
