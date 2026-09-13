#!/usr/bin/env python3
"""Bring up two supply rails, and catch one that is not delivering.

    python examples/07_supply_rails.py                  # simulated supply
    python examples/07_supply_rails.py /dev/ttyUSB0     # a real GPD-2303S
    python examples/07_supply_rails.py COM4

The second half of this example is the point. A channel in current limit reads a
perfectly plausible voltage that is not the one it was set to, and every
measurement taken downstream of it - firmware timing, radio behaviour, anything
- is then describing a board that is browning out. It takes one line to detect
and is otherwise invisible.

Nothing here is energised without an explicit call, and the example switches the
supply off before it exits, including after a failure.
"""

import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.gpd2303s import Gpd2303S

RAILS = (
    # channel, volts, current limit, what it is
    (1, 3.3, 0.5, "sensor board 3V3"),
    (2, 5.0, 1.0, "sensor board 5V"),
)


def show(psu: Gpd2303S, channel: int, label: str) -> bool:
    """Print one channel's state and say whether it is doing its job."""
    reading = psu.read_channel(channel)
    print(
        "  CH%d %-18s %6.3f V  %6.3f A  %5.2f W  %s%s"
        % (
            reading.channel, label, reading.voltage, reading.current,
            reading.power, reading.mode,
            "" if reading.regulated else "   <-- NOT REGULATED",
        )
    )
    return reading.regulated


def main(resource: str = "sim://") -> int:
    with Gpd2303S.connect(resource) as psu:
        identity = psu.identify()
        print("Supply   : %s %s, serial %s"
              % (identity.manufacturer, identity.model, identity.serial_number or "(none)"))

        status = psu.status()
        print("Status   : tracking %s, %d baud, output %s"
              % (status.tracking, status.baudrate, "on" if status.output else "off"))
        if status.tracking != "independent":
            print("           the channels are wired together; readings below are not"
                  " per-channel in the usual sense")

        try:
            # --- program, then energise. Two separate decisions. --------
            print("\nProgramming:")
            for channel, volts, limit, label in RAILS:
                psu.configure_channel(channel, volts=volts, current_limit=limit)
                print("  CH%d %-18s %.3f V, limit %.3f A" % (channel, label, volts, limit))

            print("\nSwitching on:")
            psu.all_outputs_on()

            healthy = True
            for channel, _volts, _limit, label in RAILS:
                healthy &= show(psu, channel, label)

            if not healthy:
                print("\nA rail is in current limit: it is holding its current limit"
                      "\nrather than its voltage, so the board is below its setpoint."
                      "\nRaise the limit if the demand is legitimate, or find the short."
                      "\nDo not trust any measurement taken while this is true.")
                return 1

            print("\nBoth rails regulated.")
            return 0
        finally:
            # Not output_off(channel): that parks a channel at 0 V. This opens
            # the supply's own switch, which is the only thing here that really
            # disconnects both rails.
            psu.all_outputs_off()
            print("\nOutputs off.")


if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv[1:]))
    except BenchToolsError as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
