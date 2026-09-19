#!/usr/bin/env python3
"""Configure an S2-LP, dump its registers, transmit, and capture to a log.

    python examples/08_s2lp_radio.py                   # simulated kit
    python examples/08_s2lp_radio.py /dev/ttyACM0      # a real kit
    python examples/08_s2lp_radio.py COM7

The kit runs ST's own CLI firmware - the firmware the S2-LP DK GUI drives - so
there is nothing to flash before running this.

Two things here are worth reading rather than skimming. The register dump is
filtered to what differs from reset, which is the answer to "what has this radio
been configured to do?". And the capture reports whether it was continuous:
a capture with re-arm gaps cannot be quoted as evidence that nothing was
transmitted, only that nothing was heard while listening.
"""

import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.s2lp import S2lpDevkit, lookup


def main(resource: str = "sim://", session_log: str = "s2lp_session.log",
         packet_log: str = "s2lp_packets.jsonl") -> int:
    with S2lpDevkit.connect(resource, log_path=session_log, packet_log=packet_log) as radio:
        identity = radio.identify()
        print("Kit      : %s (%s), crystal %.1f MHz"
              % (identity.model, identity.manufacturer, radio.xtal_hz / 1e6))
        low, high = radio.band
        print("Band     : %.1f to %.1f MHz" % (low / 1e6, high / 1e6))

        # --- configure -------------------------------------------------
        # The band check refuses a frequency this board cannot radiate: the
        # radio itself would accept it and report it back perfectly happily.
        centre = (low + high) // 2
        info = radio.configure_radio(frequency_hz=centre, data_rate_bps=38_400,
                                     modulation="2-gfsk-bt1")
        print("\nRadio    : %.3f MHz  %s  %d bps  dev %d Hz  bw %d Hz"
              % (info["frequency_hz"] / 1e6, info["modulation_name"],
                 info["data_rate_bps"], info["deviation_hz"], info["bandwidth_hz"]))
        radio.set_payload_length(16)
        radio.log_note("configured for the example at %.3f MHz" % (centre / 1e6))

        # --- registers -------------------------------------------------
        values = radio.read_all_registers()
        print("\nRegisters: %d read" % len(values))
        changed = radio.registers_differing_from_reset(values)
        if changed:
            print("Changed from reset:")
            for name, (reset, value) in changed.items():
                print("  %-22s 0x%02X -> 0x%02X" % (name, reset, value))
        else:
            print("  every register is at its reset value")

        print("\nA few, decoded:")
        for name in ("PCKTCTRL3", "PCKTCTRL2", "MOD2", "PA_POWER0"):
            print("  " + lookup(name).describe(radio.read_register(name)))

        # --- transmit --------------------------------------------------
        print("\nTransmitting:")
        for index in range(3):
            packet = radio.transmit(bytes([index]) + b"payload")
            print("  %s" % packet)

        # --- capture ---------------------------------------------------
        # continuous=True keeps the board in its own loop, so the radio is armed
        # for the whole capture. That is what makes the result quotable.
        print("\nCapturing up to 5 packets for 10 s:")
        capture = radio.capture(count=5, timeout=10.0)
        for packet in capture.packets:
            print("  %s" % packet)
        print("  %s" % capture.describe())
        if not capture.is_continuous:
            print("  note: this capture had gaps, so it says nothing about what"
                  "\n        was transmitted while the radio was not listening.")

        print("\nSession log : %s" % radio.log_path)
        print("Packet log  : %s" % radio.packet_log_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv[1:4]))
    except BenchToolsError as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
