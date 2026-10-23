"""#234 hardware check: open_link after ECURESET HARD, repeated, on 5C1712.

Each cycle: open_link() with the default 3 attempts, RD VERSION, then
ECURESET HARD and wait for the drop. The next cycle links within seconds of
the reset, which is when #180's 0x3E failures were seen.
"""
import json
import logging
import sys
import time

from benchtools.instruments.nordic_dongle.dongle import NordicDongle

OUT = sys.argv[1]
CYCLES = int(sys.argv[2]) if len(sys.argv) > 2 else 10
ADDRESS = "D1:8D:3B:4C:19:96"

logging.basicConfig(filename=OUT + "/python.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

results = []
dongle = NordicDongle.connect("COM10", timeout=10.0, log_path=OUT + "/dongle_session.log")
print("dongle:", dongle.identity if hasattr(dongle, "identity") else "", flush=True)
dongle.scan(12.0)
dongle.select(ADDRESS)
for cycle in range(1, CYCLES + 1):
    row = {"cycle": cycle}
    t0 = time.monotonic()
    try:
        dongle.open_link(connect_timeout=30.0)
        row["link_s"] = round(time.monotonic() - t0, 2)
        reply = dongle.command("RD VERSION", timeout=45.0)
        row["version"] = str(getattr(reply, "text", reply))
        drop = dongle.command_expecting_disconnect("ECURESET HARD", timeout=15.0)
        row["dropped"] = bool(getattr(drop, "disconnected", drop))
    except Exception as exc:  # record and go on: each cycle is one sample
        row["error"] = "%s: %s" % (type(exc).__name__, exc)
        try:
            dongle.close_link()
        except Exception:
            pass
    print(json.dumps(row), flush=True)
    results.append(row)
    time.sleep(2.0)
dongle.close()
with open(OUT + "/results.json", "w") as fh:
    json.dump(results, fh, indent=1)
