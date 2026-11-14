"""#84 review round 1 on the kit: host commands while receiving.

    python check_r1.py COM4 st_registers_writable.json out_dir --seconds 180

Sets the radio up as kit_rx.py does, starts receiving, and sends "stat" every
0.5 s while frames arrive, with no pause for them. It checks every stat is
answered and well formed, that the firmware counted no UART overrun, and that
"rx stop" is the last line: every queued record comes before it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time

import serial

from kit_rx import AFTER_FRAME, ask  # noqa: E402  (same folder)

import sys
ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from benchtools.instruments.s2lp.registers import BY_ADDRESS  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("registers")
    parser.add_argument("out")
    parser.add_argument("--seconds", type=float, default=180.0)
    args = parser.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    by_name = {register.name: register for register in BY_ADDRESS.values()}
    wanted = json.loads(pathlib.Path(args.registers).read_text())
    result = {}
    with serial.Serial(args.port, 115200, timeout=0.05) as port, \
            open(out / "raw.txt", "w", encoding="utf-8") as log:
        port.reset_input_buffer()
        result["id"] = ask(port, "id", log)
        ask(port, "rx stop", log)
        ask(port, "sdn 1", log)
        time.sleep(0.05)
        ask(port, "sdn 0", log)
        time.sleep(0.05)
        for name, value in sorted(wanted.items(), key=lambda item: by_name[item[0]].address):
            if by_name[name].writable:
                ask(port, "wr %02x %02x" % (by_name[name].address, value), log)
        ask(port, "wr 37 03", log)
        addresses = ",".join("%02x" % by_name[name].address for name in AFTER_FRAME)
        result["rx_start"] = ask(port, "rx start " + addresses, log)

        sent = answered = frames = 0
        bad = []
        end = time.monotonic() + args.seconds
        next_stat = time.monotonic()
        buffer = b""
        while time.monotonic() < end:
            if time.monotonic() >= next_stat:
                port.write(b"stat\n")
                sent += 1
                next_stat += 0.5
            buffer += port.read(4096)
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode(errors="replace").strip()
                if not text:
                    continue
                log.write("%.6f < %s\n" % (time.time(), text))
                if text.startswith("ok running="):
                    answered += 1
                    result["last_stat"] = text
                elif text.startswith("f "):
                    frames += 1
                elif not text.startswith("r "):
                    bad.append(text)
        port.write(b"rx stop\n")
        lines = []
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            buffer += port.read(4096)
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode(errors="replace").strip()
                if text:
                    log.write("%.6f < %s\n" % (time.time(), text))
                    lines.append(text)
            if lines and lines[-1].startswith("ok frames="):
                break
        stats_late = [line for line in lines if line.startswith("ok running=")]
        answered += len(stats_late)
        frames += sum(1 for line in lines if line.startswith("f "))
        result.update({
            "stat_sent": sent, "stat_answered": answered, "unexpected_lines": bad,
            "frames_seen": frames, "rx_stop": lines[-1] if lines else None,
            "rx_stop_is_last": bool(lines) and lines[-1].startswith("ok frames="),
            "after_stop": ask(port, "stat", log),
        })
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
