#!/usr/bin/env python3
"""Exercise a real GPD-3303D step by step, and check the front panel agrees.

    python examples/10_psu_front_panel_check.py COM11
    python examples/10_psu_front_panel_check.py COM11 --hold 10     # unattended
    python examples/10_psu_front_panel_check.py sim://               # dry run

Each step changes one thing, reads the supply back through the driver, and
says what the front panel should now show. At the prompt, press Enter if the
panel matches, or type what it shows instead. ``q`` stops early. The answers are
written to a JSON log, which is the evidence for TB-SIT-03 ("accepts a setpoint
that the front panel then shows").

**Nothing may be connected to either output.** The outputs are energised at up
to 12 V with current limits of up to 1 A. The supply must be in INDEPENDENT
tracking.

Whatever happens, the supply is left with its output off and its original
setpoints and current limits restored, as far as the 0.1 V / 0.01 A read-back
lets them be known.

Traces to: TB-SIT-03, PSU-FR-030, PSU-FR-040, PSU-FR-043.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.gpd3303d import Gpd3303D


def _readback(psu: Gpd3303D) -> dict:
    """Everything the driver can see, in one line per channel."""
    status = psu.status()
    channels = {}
    for reading in psu.read_all():
        channels["CH%d" % reading.channel] = {
            "set_V": reading.voltage_setpoint,
            "limit_A": reading.current_limit,
            "out_V": reading.voltage,
            "out_A": reading.current,
            "mode": ("-" if not status.output
                     else "parked at 0 V" if not reading.is_on else reading.mode),
            "on": reading.is_on,
        }
    return {"output": status.output, "tracking": status.tracking,
            "raw": status.raw, "channels": channels}


def _print_readback(state: dict) -> None:
    print("  driver reads: output %s, tracking %s, STATUS? %r"
          % ("ON" if state["output"] else "off", state["tracking"], state["raw"]))
    for name, ch in state["channels"].items():
        print("    %s  set %5.1f V  limit %4.2f A  |  out %5.1f V  %4.2f A  %s"
              % (name, ch["set_V"], ch["limit_A"], ch["out_V"], ch["out_A"], ch["mode"]))


def _steps():
    """(title, action, what the front panel should show)."""
    return [
        ("Connect only",
         lambda p: None,
         "Nothing changed by connecting. Note whether a REMOTE (or similar) "
         "indicator is lit, and what the OUTPUT indicator shows."),
        ("Output off; CH1 5.00 V / 0.50 A; CH2 12.00 V / 1.00 A",
         lambda p: (p.all_outputs_off(),
                    p.configure_channel(1, 5.0, 0.5),
                    p.configure_channel(2, 12.0, 1.0)),
         "OUTPUT indicator off. With the output off the displays show the "
         "settings: CH1 about 5.00 V and 0.500 A, CH2 about 12.00 V and 1.000 A."),
        ("CH1 changed to 3.30 V",
         lambda p: p.set_voltage(1, 3.3),
         "CH1 voltage display about 3.30 V. CH2 unchanged."),
        ("CH2 current limit changed to 0.25 A",
         lambda p: p.set_current_limit(2, 0.25),
         "CH2 current display about 0.250 A. CH1 unchanged."),
        ("Output on (the one switch, both channels)",
         lambda p: p.all_outputs_on(),
         "OUTPUT indicator on. CV indicators lit on both channels. The "
         "displays now show the output: CH1 about 3.3 V, CH2 about 12.0 V, "
         "both about 0.000 A with nothing connected."),
        ("CH1 switched off on its own (parked at 0 V)",
         lambda p: p.output_off(1),
         "CH1 falls to about 0.00 V. CH2 stays at about 12.0 V. The OUTPUT "
         "indicator stays ON - the supply has one switch, so a single channel "
         "is parked at zero volts, not disconnected."),
        ("CH1 switched back on",
         lambda p: p.output_on(1),
         "CH1 back at about 3.3 V. CH2 still about 12.0 V. OUTPUT on."),
        ("CH1 changed to 1.80 V while on",
         lambda p: p.set_voltage(1, 1.8),
         "CH1 about 1.8 V. CH2 unchanged."),
        ("Output off",
         lambda p: p.all_outputs_off(),
         "OUTPUT indicator off. Displays back to the settings: CH1 about "
         "1.80 V / 0.500 A, CH2 about 12.00 V / 0.250 A. CV indicators off."),
        ("Safe state (reset)",
         lambda p: p.reset(),
         "Output off, both voltage displays about 0.00 V. The current limits "
         "are deliberately left alone: CH1 0.500 A, CH2 0.250 A."),
    ]


def _ask(hold: float, interactive: bool) -> str:
    if not interactive:
        time.sleep(hold)
        return "(not checked - unattended)"
    try:
        answer = input("  Panel matches? [Enter = yes, q = stop, or type what you see] ")
    except EOFError:
        return "(no answer)"
    return answer.strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("resource", nargs="?", default="sim://",
                        help="COM11, /dev/ttyUSB0 or sim:// (default)")
    parser.add_argument("--hold", type=float, default=None,
                        help="seconds to hold each step instead of prompting")
    parser.add_argument("--log", default=None, help="JSON log path")
    args = parser.parse_args(argv)

    interactive = args.hold is None and sys.stdin.isatty()
    hold = args.hold if args.hold is not None else 8.0
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = args.log or "psu_front_panel_check_%s.json" % stamp
    record = {"resource": args.resource, "started": stamp, "steps": []}

    print("Nothing may be connected to either output. Tracking must be INDEPENDENT.")
    if interactive:
        if input("Ready? [y/N] ").strip().lower() != "y":
            return 1

    try:
        psu = Gpd3303D.connect(args.resource)
    except BenchToolsError as exc:
        print("error: %s" % exc)
        return 1

    with psu:
        identity = psu.identify()
        record["identity"] = identity.raw
        original = {ch: (psu.voltage_setpoint(ch), psu.current_limit(ch)) for ch in (1, 2)}
        record["original"] = original
        print("Supply: %s\n" % identity.raw)
        stopped = False
        try:
            for number, (title, action, expect) in enumerate(_steps(), 1):
                print("Step %d - %s" % (number, title))
                action(psu)
                time.sleep(0.5)                  # let the display and output settle
                state = _readback(psu)
                _print_readback(state)
                print("  front panel should show: %s" % expect)
                answer = _ask(hold, interactive)
                verdict = "match" if answer == "" else (
                    "stopped" if answer.lower() == "q" else answer)
                record["steps"].append({"step": number, "title": title, "expect": expect,
                                        "driver": state, "panel": verdict})
                print()
                if verdict == "stopped":
                    stopped = True
                    break
        except BenchToolsError as exc:
            print("error: %s" % exc)
            record["error"] = str(exc)
        finally:
            psu.all_outputs_off()
            for ch, (volts, amps) in original.items():
                psu.set_current_limit(ch, amps)
                psu.set_voltage(ch, volts)
            record["restored"] = _readback(psu)
            print("Output off; setpoints restored to %s." % {
                "CH%d" % ch: "%.1f V / %.2f A" % v for ch, v in original.items()})

    with open(log_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, default=str)
    mismatches = [s for s in record["steps"] if s["panel"] not in ("match", "stopped")
                  and not s["panel"].startswith("(")]
    print("Log: %s" % log_path)
    print("%d step(s) run, %d reported different from expected%s."
          % (len(record["steps"]), len(mismatches), ", stopped early" if stopped else ""))
    for step in mismatches:
        print("  step %d (%s): %s" % (step["step"], step["title"], step["panel"]))
    return 1 if mismatches or "error" in record else 0


if __name__ == "__main__":
    sys.exit(main())
