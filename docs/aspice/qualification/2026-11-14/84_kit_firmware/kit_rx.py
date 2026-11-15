"""Receive on the S2-LP kit running the ETB kit firmware (#84), for a bench check.

    python kit_rx.py COM4 registers.json out_dir --seconds 600

1. ``id``; power-cycles the radio (``sdn 1``, ``sdn 0``).
2. Writes every writable register from ``registers.json``, a dump taken from
   the same kit under ST's firmware with the Kepler receive setup applied, and
   reads each back; then sets QI.PQI_TH to 1, so that PQI is computed.
3. ``rx start`` with RSSI_LEVEL, LINK_QUALIF2 (PQI), LINK_QUALIF1 (SQI) and
   AFC_CORR read after each frame; receives for ``--seconds``; ``rx stop``.
4. Writes ``raw.txt`` (every line, with the host time), ``frames.jsonl``
   (each record decoded with the Kepler plugin) and ``summary.json``.

Receive only: nothing is transmitted, and no sensor is commanded.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import serial

ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from benchtools.core import plugins  # noqa: E402
from benchtools.instruments.s2lp.registers import BY_ADDRESS  # noqa: E402

AFTER_FRAME = ("RSSI_LEVEL", "LINK_QUALIF2", "LINK_QUALIF1", "AFC_CORR")


def ask(port, command, log, timeout=2.0):
    port.write((command + "\n").encode())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = port.readline().decode(errors="replace").strip()
        if line:
            log.write("%.6f < %s\n" % (time.time(), line))
            if line.startswith(("ok", "err")):
                return line
    raise RuntimeError("no answer to %r" % command)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("registers")
    parser.add_argument("out")
    parser.add_argument("--seconds", type=float, default=600.0)
    args = parser.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plugins.load_plugin(str(ROOT / "plugins" / "kepler"))
    decode = plugins.decoder("kepler")
    by_name = {register.name: register for register in BY_ADDRESS.values()}
    wanted = json.loads(pathlib.Path(args.registers).read_text())

    summary = {"port": args.port, "seconds": args.seconds}
    with serial.Serial(args.port, 115200, timeout=0.2) as port, \
            open(out / "raw.txt", "w", encoding="utf-8") as log:
        port.reset_input_buffer()
        summary["id"] = ask(port, "id", log)
        ask(port, "rx stop", log)
        ask(port, "sdn 1", log)
        time.sleep(0.05)
        ask(port, "sdn 0", log)
        time.sleep(0.05)
        written, differ = 0, []
        for name, value in sorted(wanted.items(), key=lambda item: by_name[item[0]].address):
            register = by_name[name]
            if not register.writable:
                continue
            ask(port, "wr %02x %02x" % (register.address, value), log)
            back = int(ask(port, "rd %02x 1" % register.address, log).split()[1], 16)
            written += 1
            if back != value:
                differ.append({"register": name, "wanted": value, "read": back})
        summary["registers_written"] = written
        summary["registers_differing"] = differ
        # PQI is computed only while the PQI check is on (QI.PQI_TH > 0,
        # S2LP-OPEN-07); ST's driver turns it on for a polled stream the same way.
        qi = (wanted.get("QI", 0x01) & ~0x1E) | (1 << 1)
        ask(port, "wr %02x %02x" % (by_name["QI"].address, qi), log)
        summary["QI"] = ask(port, "rd %02x 1" % by_name["QI"].address, log)
        addresses = ",".join("%02x" % by_name[name].address for name in AFTER_FRAME)
        summary["rx_start"] = ask(port, "rx start " + addresses, log)

        frames = rejects = 0
        seqs = []
        with open(out / "frames.jsonl", "w", encoding="utf-8") as records:
            end = time.monotonic() + args.seconds
            while time.monotonic() < end:
                line = port.readline().decode(errors="replace").strip()
                if not line:
                    continue
                host = time.time()
                log.write("%.6f < %s\n" % (host, line))
                words = line.split(" ")
                if words[0] == "f" and len(words) >= 5:
                    payload = bytes.fromhex(words[5]) if len(words) > 5 else b""
                    regs = bytes.fromhex(words[4]) if words[4] != "-" else b""
                    entry = {"seq": int(words[1]), "board_us": int(words[2]), "host": host,
                             "length": int(words[3]),
                             "registers": dict(zip(AFTER_FRAME, regs)), "hex": payload.hex()}
                    try:
                        entry["decoded"] = decode(payload)
                    except Exception as error:  # pylint: disable=broad-except
                        entry["decode_error"] = str(error)
                    records.write(json.dumps(entry) + "\n")
                    frames += 1
                    seqs.append(entry["seq"])
                elif words[0] == "r":
                    records.write(json.dumps({"seq": int(words[1]), "board_us": int(words[2]),
                                              "host": host, "reject_irq": words[3]}) + "\n")
                    rejects += 1
                    seqs.append(int(words[1]))
        summary["rx_stop"] = ask(port, "rx stop", log, timeout=5.0)
        summary["stat"] = ask(port, "stat", log)
        summary["frames_received"] = frames
        summary["rejects_received"] = rejects
        summary["seq_gaps"] = sum(1 for a, b in zip(seqs, seqs[1:]) if b != a + 1)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
