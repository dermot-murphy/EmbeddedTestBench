"""Summarise a kit_rx.py run (#84): decodes, link quality, copy spacing, repeats.

    python analyse.py rx_run1/frames.jsonl
"""
import collections
import json
import sys

frames = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")
          if line.startswith("{") and "seq" in line or '"direction"' in line]
for frame in frames:          # a packet log from ST's firmware, for comparison
    if "board_time_us" in frame and "board_us" not in frame:
        frame["board_us"] = int(frame["monotonic_s"] * 1e6)
        frame["registers"] = {}
ok = [f for f in frames if "decoded" in f]
print("frames %d, decoded %d, undecoded %d" % (len(frames), len(ok), len(frames) - len(ok)))
pqi = [f["registers"]["LINK_QUALIF2"] for f in ok if "LINK_QUALIF2" in f["registers"]]
sqi = [f["registers"]["LINK_QUALIF1"] & 0x7F for f in ok if "LINK_QUALIF1" in f["registers"]]
if pqi:
    print("PQI min %d max %d; SQI min %d max %d" % (min(pqi), max(pqi), min(sqi), max(sqi)))
by_kind = collections.Counter((f["decoded"]["sensor_id"], f["decoded"]["type"]) for f in ok)
for key, count in sorted(by_kind.items(), key=str):
    print("  %-8s %-9s %d" % (key[0], key[1], count))
# Copies of one transmission: same sensor, type and packet number, each within
# 1 s of the last; other senders' frames may come between them.
groups = []
open_groups = {}
for frame in sorted(ok, key=lambda f: f["board_us"]):
    key = (frame["decoded"]["sensor_id"], frame["decoded"]["type"],
           frame["decoded"].get("packet_number"))
    group = open_groups.get(key)
    if group is not None and frame["board_us"] - group["last"] < 1000000:
        group["frames"].append(frame)
        group["last"] = frame["board_us"]
    else:
        group = {"key": key, "last": frame["board_us"], "frames": [frame]}
        open_groups[key] = group
        groups.append(group)
gaps = []
complete = incomplete = 0
for group in groups:
    times = [f["board_us"] for f in group["frames"]]
    gaps += [b - a for a, b in zip(times, times[1:])]
    counts = {f["decoded"].get("frame", {}).get("frames_per_packet") for f in group["frames"]}
    repeats = sorted(f["decoded"].get("frame", {}).get("repeat") for f in group["frames"])
    wanted = max(c for c in counts if c is not None) if counts - {None} else None
    if wanted is None:
        continue
    if len(set(repeats)) == wanted:
        complete += 1
    else:
        incomplete += 1
        print("  incomplete:", group["key"], "repeats", repeats, "of", wanted)
print("transmissions %d: all copies %d, missing copies %d" % (len(groups), complete, incomplete))
if gaps:
    print("copy spacing ms: min %.1f, max %.1f, n %d" % (min(gaps) / 1000, max(gaps) / 1000, len(gaps)))
