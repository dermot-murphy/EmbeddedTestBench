"""Receive through the benchtools S2-LP driver on the ETB kit firmware (#84).

    python kit_stream.py COM4 registers.json out_dir --seconds 300

1. ``S2lpDevkit.connect(port)`` with the default ``firmware="auto"``: the
   driver asks ``id`` and must choose the kit firmware.
2. ``power_cycle()``, then every register in ``registers.json`` (the writable
   registers dumped from the same kit under ST's firmware with the Kepler
   receive setup) is written with ``write_register`` and read back.
3. An ST-only call (``frequency_hz``) must be refused, naming the firmware.
4. ``stream(decoder=<the Kepler plugin's>, timeout=--seconds)``, with the driver's default
   per-frame registers; then ``stream(count=3)`` to end on a count.
5. Writes ``summary.json``; the driver writes ``session.log`` (every line,
   both directions) and ``packets.jsonl`` (every packet, decoded).

Receive only: nothing is transmitted, and no sensor is commanded.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from benchtools.core import plugins  # noqa: E402
from benchtools.core.errors import InstrumentError  # noqa: E402
from benchtools.instruments.s2lp import S2lpDevkit  # noqa: E402


def summarise(packets):
    """Counts, sequence gaps, PQI range and frame types of *packets*."""
    good = [packet for packet in packets if packet.ok]
    pqi = [packet.extra["pqi"] for packet in good if "pqi" in packet.extra]
    types = collections.Counter(
        (packet.decoded or {}).get("type", "?") for packet in good if packet.decoded)
    return {
        "packets": len(packets),
        "frames": len(good),
        "rejections": len(packets) - len(good),
        "lost_before_total": sum(packet.extra.get("lost_before", 0) for packet in packets),
        "seq_first_last": [packets[0].extra["seq"], packets[-1].extra["seq"]] if packets else [],
        "decode_errors": sum(1 for packet in good if packet.decode_error),
        "pqi_min_max": [min(pqi), max(pqi)] if pqi else [],
        "with_registers": sum(1 for packet in good if len(packet.registers) == 4),
        "frame_types": dict(types),
        "sensors": sorted({(packet.decoded or {}).get("sensor_id", "?")
                           for packet in good if packet.decoded}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("registers")
    parser.add_argument("out")
    parser.add_argument("--seconds", type=float, default=300.0)
    args = parser.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plugins.load_plugin(str(ROOT / "plugins" / "kepler"))
    decoder = plugins.decoder("kepler")
    wanted = json.loads(pathlib.Path(args.registers).read_text())
    summary = {"port": args.port, "seconds": args.seconds}

    with S2lpDevkit.connect(args.port, log_path=str(out / "session.log"),
                            packet_log=str(out / "packets.jsonl")) as radio:
        summary["kit_firmware"] = radio.kit_firmware
        summary["identity"] = radio.identity()
        if not radio.kit_firmware:
            raise SystemExit("the driver did not find the kit firmware")
        radio.power_cycle()
        differ = []
        for name, value in wanted.items():
            radio.write_register(name, value)
            back = radio.read_register(name)
            if back != value:
                differ.append({"register": name, "wanted": value, "read": back})
        summary["registers_written"] = len(wanted)
        summary["registers_differing"] = differ
        try:
            radio.frequency_hz()
            summary["st_call"] = "not refused"
        except InstrumentError as error:
            summary["st_call"] = "refused: %s" % error

        packets = list(radio.stream(decoder=decoder, timeout=args.seconds))
        summary["timed_stream"] = summarise(packets)
        summary["timed_stream"]["kit_counters"] = radio.kit_counters

        counted = list(radio.stream(decoder=decoder, count=3, timeout=120))
        summary["counted_stream"] = summarise(counted)
        summary["counted_stream"]["kit_counters"] = radio.kit_counters
        summary["counted_stream"]["set_aside"] = len(radio._take_set_aside())  # pylint: disable=protected-access
        summary["QI_after"] = radio.read_register("QI")

    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
