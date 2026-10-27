"""#299 bench probes on the S2-LP kit (COM4). Listens only; no sensor commands.

E1: after the driver's own batch stop and IRQ_STATUS read, does nIRQ ever read
    low? Many short batch receives, each stopped by the host, then the same
    clear and line check the driver does.
E2: does S2LPGetNBytesReportAll stay on across a stop? Turn it on once, then
    start batches without it and look for the report-all fields
    ({seq_num...}) in the reports that arrive (noise receptions will do).

    python probe_299.py <out_dir> <cycles>
"""

import json
import pathlib
import sys
import time

from benchtools.instruments.s2lp import S2lpDevkit

OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
CYCLES = int(sys.argv[2])


def main():
    result = {"e1_cycles": 0, "e1_low": 0, "e1_irq_values": {},
              "e2_batches": 0, "e2_reports": 0, "e2_with_report_all_fields": 0}
    with S2lpDevkit.connect("COM4", board="STEVAL-FKI433V2",
                            log_path=str(OUT / "s2lp_session.log"),
                            packet_log=str(OUT / "s2lp_packets.jsonl")) as radio:
        radio.apply_configuration("plugins/kepler/configs/s2lp_kepler_433_rx.regs", reset="defaults")
        session = radio._session  # pylint: disable=protected-access
        radio.prepare_receive()

        # E1: start a batch, let it run a varying short time, stop it, clear, check.
        for cycle in range(CYCLES):
            session.execute("S2LPGetNBytesReportAll", 1)
            session.send("S2LPGetNBytesBatch", 0, 4294967295)
            deadline = time.monotonic() + 0.05 + (cycle % 10) * 0.03
            while time.monotonic() < deadline:
                try:
                    session.read_reply(timeout=deadline - time.monotonic(),
                                       command="S2LPGetNBytesBatch")
                except Exception:  # pylint: disable=broad-except
                    break
            session.stop()
            irq = session.execute("S2LPIrqGetStatus").raw
            level = session.execute("S2MGpioGetValue", 3).hex_number("value")
            result["e1_cycles"] += 1
            if level != 1:
                result["e1_low"] += 1
            key = irq.split("value:")[-1][:8] if "value:" in irq else "?"
            result["e1_irq_values"][key] = result["e1_irq_values"].get(key, 0) + 1

        # E2: ReportAll on once (above); batches without re-sending it.
        for _ in range(20):
            session.send("S2LPGetNBytesBatch", 0, 4294967295)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    reply = session.read_reply(timeout=deadline - time.monotonic(),
                                               command="S2LPGetNBytesBatch")
                except Exception:  # pylint: disable=broad-except
                    break
                result["e2_reports"] += 1
                if "seq_num" in reply.raw:
                    result["e2_with_report_all_fields"] += 1
            session.stop()
            session.execute("S2LPIrqGetStatus")
            result["e2_batches"] += 1

    (OUT / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
