"""#299 review: stops that land with a reception pending (the #99 case).

Many short batch receives, each stopped by the host after a random short time,
while other sensors and noise are on air. After each stop, read IRQ_STATUS
(which clears it) and then the nIRQ line, as the driver did before #299, and
record every IRQ_STATUS value seen with how often the line then read high or
low. Listens only; no command goes to any sensor.

    python probe_299_e3.py <out_dir> <cycles>
"""

import json
import pathlib
import random
import sys
import time

from benchtools.instruments.s2lp import S2lpDevkit

OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
CYCLES = int(sys.argv[2])


def main():
    seen = {}          # IRQ_STATUS value -> {"high": n, "low": n, "with_reports": n}
    started = time.monotonic()
    with S2lpDevkit.connect("COM4", board="STEVAL-FKI433V2",
                            log_path=str(OUT / "s2lp_session.log")) as radio:
        radio.apply_configuration("plugins/kepler/configs/s2lp_kepler_433_rx.regs",
                                  reset="defaults")
        session = radio._session  # pylint: disable=protected-access
        radio.prepare_receive()
        session.execute("S2LPIrqGetStatus")
        session.execute("S2LPGetNBytesReportAll", 1)
        rng = random.Random(299)
        for _ in range(CYCLES):
            session.send("S2LPGetNBytesBatch", 0, 4294967295)
            time.sleep(rng.uniform(0.005, 0.120))
            replies = session.stop()
            value = session.execute("S2LPIrqGetStatus").raw
            value = value.split("value:")[-1][:8] if "value:" in value else "?"
            level = session.execute("S2MGpioGetValue", 3).hex_number("value")
            entry = seen.setdefault(value, {"high": 0, "low": 0, "with_reports": 0,
                                            "acknowledged": 0})
            entry["high" if level == 1 else "low"] += 1
            entry["acknowledged"] += 1 if session.last_stop_acknowledged else 0
            if any(r.command != "S2LPGetNBytesBatch" or "error" in r.raw for r in replies):
                entry["with_reports"] += 1
    result = {"cycles": CYCLES, "seconds": round(time.monotonic() - started, 1),
              "irq_status": seen}
    (OUT / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
