#!/usr/bin/env python3
"""Listen for the Kepler sensor's radio frames and print them decoded.

    python examples/11_kepler_rf_stream.py                 # simulated kit
    python examples/11_kepler_rf_stream.py COM4 900        # a real kit, 15 minutes

The kit (the 433 MHz S2-LP board) is put into the sensor's receive settings
from ``configs/s2lp_kepler_433_rx.regs``. Frames are received by ST's own
receive loop - the way ST's GUI receives, which misses the fewest - and each
payload is decoded. The packet log gets one record per frame with the raw
bytes, the firmware's fields and the decode together. For PQI and SQI per
frame, pass ``mode="polled"`` to ``stream()``; it misses frames that come close
together.

A sensor sends each packet three times; the ``repeat`` in the decode tells them
apart. An ALIVE packet comes every 10 minutes, so a short run may see nothing.
"""

import pathlib
import sys

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.s2lp import S2lpDevkit
from benchtools.instruments.s2lp.kepler import decode_kepler_frame

SETUP = pathlib.Path(__file__).resolve().parents[1] / "configs" / "s2lp_kepler_433_rx.regs"


def main(resource: str = "sim://", seconds: str = "30",
         packet_log: str = "kepler_frames.jsonl") -> int:
    with S2lpDevkit.connect(resource, board="STEVAL-FKI433V2",
                            packet_log=packet_log) as radio:
        radio.apply_configuration(str(SETUP), reset="defaults")
        print("Listening at %.3f MHz for %s s. Ctrl-C to stop."
              % (radio.frequency_hz / 1e6, seconds))
        frames = 0
        try:
            for frame in radio.stream(decoder=decode_kepler_frame, timeout=float(seconds)):
                frames += 1
                print(frame)
                if frame.decoded:
                    decoded = frame.decoded
                    print("    %s from %s, repeat %s: %s"
                          % (decoded["type"], decoded["sensor_id"],
                             decoded.get("frame", {}).get("repeat", "-"),
                             {key: decoded[key] for key in ("temperature_c", "battery_mv")
                              if key in decoded}))
        except KeyboardInterrupt:
            radio.stop()
        print("%d frame(s). Packet log: %s" % (frames, radio.packet_log_path))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv[1:4]))
    except BenchToolsError as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
