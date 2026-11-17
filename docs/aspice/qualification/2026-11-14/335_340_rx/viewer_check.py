"""#340 on real frames: feed the 2026-11-14 packet log to the viewer as
rf_packet records and count how often the Kepler decoder runs.

    python viewer_check.py packets.jsonl
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from benchtools.core import plugins  # noqa: E402
from benchtools.viewer.radio import RfFrames  # noqa: E402

plugin = plugins.load_plugin(str(ROOT / "plugins" / "kepler"))
real = plugin.decoders["kepler"]
calls = []


def counting(payload):
    calls.append(payload)
    return real(payload)


plugin.decoders["kepler"] = counting
packets = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")
           if line.startswith("{")]
for label, strip in (("as logged (decoder named)", False), ("older log (no decoder field)", True)):
    calls.clear()
    frames = RfFrames()
    for packet in packets:
        data = dict(packet)
        if strip:
            data.pop("decoder", None)
        frames.feed({"kind": "rf_packet", "t": 0.0, "source": "s2lp", "data": data})
    view = frames.view(limit=1000)
    described = sum(1 for frame in view["frames"] if frame["summary"])
    print("%-30s records %d, received %d, described %d, decoder calls %d"
          % (label, len(packets), view["received"], described, len(calls)))
