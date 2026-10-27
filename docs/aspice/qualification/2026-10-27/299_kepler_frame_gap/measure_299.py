"""#299 on the bench: how long the kit is deaf between two kepler_frame calls,
and whether three calls get the three copies of one ALIVE packet.

Listens only: no command goes to the sensor, and no other instrument is used.
Run from the repository root with the branch fix/293-kepler-frame-between-calls.

    python <this file> <out_dir>
"""

import json
import pathlib
import sys
import time

from benchtools.core.errors import MeasurementError
from benchtools.instruments.s2lp import S2lpDevkit

OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
SENSOR = "5C1712"
FIRST_WAIT_S = 720.0       # ALIVE every 10 min
NEXT_WAIT_S = 3.0          # copies are about 0.25 s apart

events = []                # (monotonic, what, detail)


def note(what, detail=""):
    events.append((time.monotonic(), what, detail))


def run_phase(radio, label, since_last):
    """Three kepler_frame calls on one ALIVE packet."""
    results = []
    for call in range(3):
        timeout = FIRST_WAIT_S if call == 0 else NEXT_WAIT_S
        note("call_start", "%s call %d" % (label, call))
        try:
            frame = radio.kepler_frame("ALIVE", source=SENSOR, timeout=timeout,
                                       since_last=since_last)
            note("call_return", "%s call %d repeat %s" % (label, call, frame["frame"]["repeat"]))
            results.append({"call": call, "repeat": frame["frame"]["repeat"],
                            "raw": frame["raw"]})
        except MeasurementError as exc:
            note("call_error", "%s call %d: %s" % (label, call, exc))
            results.append({"call": call, "error": str(exc)})
    return results


def main():
    with S2lpDevkit.connect("COM4", board="STEVAL-FKI433V2",
                            log_path=str(OUT / "s2lp_session.log"),
                            packet_log=str(OUT / "s2lp_packets.jsonl")) as radio:
        radio.apply_configuration("plugins/kepler/configs/s2lp_kepler_433_rx.regs", reset="defaults")
        session = radio._session  # pylint: disable=protected-access
        send, stop, record = session.send, session.stop, radio._record  # pylint: disable=protected-access

        def timed_send(name, *arguments):
            note("send", name)
            return send(name, *arguments)

        def timed_stop(*args, **kwargs):
            note("stop_sent")
            replies = stop(*args, **kwargs)
            note("stop_done", "%d replies with it" % len(replies))
            return replies

        def timed_record(packet):
            if packet.direction == "rx":
                decoded = packet.decoded or {}
                note("rx", "%s %s repeat %s board_us %s" % (
                    decoded.get("sensor_id"), decoded.get("type"),
                    (decoded.get("frame") or {}).get("repeat"), packet.board_time_us))
            return record(packet)

        session.send = timed_send
        session.stop = timed_stop
        radio._record = timed_record  # pylint: disable=protected-access

        phases = {
            "A_default": run_phase(radio, "A", since_last=False),
            "B_since_last": run_phase(radio, "B", since_last=True),
        }

    t0 = events[0][0]
    with open(OUT / "events.tsv", "w", encoding="utf-8") as handle:
        for when, what, detail in events:
            handle.write("%.4f\t%s\t%s\n" % (when - t0, what, detail))
    with open(OUT / "results.json", "w", encoding="utf-8") as handle:
        json.dump(phases, handle, indent=2)
    print(json.dumps(phases, indent=2))


if __name__ == "__main__":
    main()
