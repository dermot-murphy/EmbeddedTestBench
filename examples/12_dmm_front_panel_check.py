#!/usr/bin/env python3
"""Exercise a real TTi 1604 step by step, and check the front panel agrees.

    python examples/12_dmm_front_panel_check.py COM6
    python examples/12_dmm_front_panel_check.py /dev/ttyUSB0
    python examples/12_dmm_front_panel_check.py COM6 --hold 10     # unattended
    python examples/12_dmm_front_panel_check.py sim://              # dry run
    python examples/12_dmm_front_panel_check.py COM6 --signal       # a signal on V

Each step changes the meter through the driver, reads it back - function,
range, auto or manual, and the display text - and says what the front panel
should now show. At the prompt, press Enter if the panel matches, or type what
it shows instead. ``q`` stops early. The answers are written to a JSON log,
which is the evidence for the bench confirmation items DMM-OPEN-01 … -08: the
frame and the panel are the meter's two accounts of one state, and this is
where they are compared.

**Leave the inputs open.** No current function is selected; the resistance
step drives the meter's test current into the open input, which is safe.

The two frequency steps are skipped unless ``--signal`` says an AC signal is on
the V input. With no signal a real 1604 in Hz sends nothing and ignores the
link until V is pressed on its front panel (#181), so on open inputs they would
stop the check.

Whatever happens, the meter is left on DC volts, auto-ranging, and handed back
to its front panel (local mode).

Traces to: DMM-FR-029, DMM-FR-030, DMM-FR-033, DMM-FR-081.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time

from benchtools.core.errors import BenchToolsError
from benchtools.instruments.tti1604 import Tti1604


def _readback(dmm: Tti1604) -> dict:
    """What the driver sees, from a reading taken now."""
    reading = dmm.current_state()
    return {
        "function": reading.function,
        "range": reading.range_label or reading.range_description,
        "auto": bool(reading.flags.get("auto_range")),
        "display": reading.text,
        "overrange": reading.overrange,
        "held": reading.held,
        "gate_10s": bool(reading.status.get("gate_ten_seconds")),
        "raw": reading.raw.hex(),
    }


def _print_readback(state: dict) -> None:
    print("  driver reads: %s, %s range, %s, display %r%s"
          % (state["function"], state["range"], "auto" if state["auto"] else "manual",
             state["display"], ", 10 s gate" if state["gate_10s"] else ""))


def _dc_volts(dmm: Tti1604) -> None:
    dmm.select_volts()
    dmm.select_dc()
    dmm.select_auto_range()


def _steps():
    """(title, action, what the front panel should show)."""
    return [
        ("Remote mode (connecting)",
         lambda d: None,
         "Note whether a REMOTE (or similar) indicator is lit. Press Auto/Man "
         "once: do the front-panel keys still work in remote mode? (The next "
         "step puts the range back.)"),
        ("DC volts, auto-ranging",
         _dc_volts,
         "V and DC annunciators lit, AUTO lit. With the input open the display "
         "reads close to zero."),
        ("AC volts",
         lambda d: d.select_ac(),
         "AC annunciator lit, DC off, V still lit."),
        ("DC millivolts",
         lambda d: (d.select_millivolts(), d.select_dc()),
         "mV and DC annunciators lit: the 400 mV range, two digits after the point."),
        ("DC volts, 40 V range locked",
         lambda d: (d.select_volts(), d.select_dc(), d.set_range(40)),
         "AUTO off. Three digits after the decimal point (00.000)."),
        ("DC volts, 1000 V range locked",
         lambda d: d.set_range(1000),
         "AUTO off. One digit after the decimal point (0000.0)."),
        ("Auto-ranging again",
         lambda d: d.select_auto_range(),
         "AUTO lit again."),
        ("Resistance, input open",
         lambda d: d.select_ohms(),
         "Ohm annunciator lit; the display reads OFL, because nothing is connected."),
        ("Frequency, 40 kHz range",
         lambda d: (d.select_volts(), d.select_ac(), d.select_hertz()),
         "Hz annunciator lit and steady: the 40 kHz range, 1 s gate."),
        ("Frequency, 4 kHz range",
         lambda d: d.set_range(4000),
         "The manual says the Hz annunciator now flashes slowly: the 4 kHz "
         "range, 10 s gate. (The driver waits up to about 25 s for this.)"),
        ("Back to DC volts, auto-ranging",
         _dc_volts,
         "Hz off; V, DC and AUTO lit."),
        ("Local mode",
         lambda d: d.local(),
         "Any REMOTE indicator off, and the front-panel keys work again. The "
         "driver reads nothing in local mode, so its read-back above is from "
         "the step before."),
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


def _run_steps(dmm: Tti1604, record: dict, hold: float, interactive: bool,
               signal: bool = False) -> bool:
    """Take every step, logging each. True if the operator stopped early.

    Without *signal* the frequency steps are logged as skipped (#181).
    """
    state = None
    for number, (title, action, expect) in enumerate(_steps(), 1):
        if title.startswith("Frequency") and not signal:
            print("Step %d - %s: skipped, no signal on the input (--signal)\n"
                  % (number, title))
            record["steps"].append({"step": number, "title": title, "expect": expect,
                                    "driver": None, "panel": "(skipped - no signal)"})
            continue
        print("Step %d - %s" % (number, title))
        action(dmm)
        if dmm.is_remote:
            state = _readback(dmm)
        _print_readback(state)
        print("  front panel should show: %s" % expect)
        answer = _ask(hold, interactive)
        verdict = "match" if answer == "" else (
            "stopped" if answer.lower() == "q" else answer)
        record["steps"].append({"step": number, "title": title, "expect": expect,
                                "driver": state, "panel": verdict})
        print()
        if verdict == "stopped":
            return True
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("resource", nargs="?", default="sim://",
                        help="COM6, /dev/ttyUSB0 or sim:// (default)")
    parser.add_argument("--hold", type=float, default=None,
                        help="seconds to hold each step instead of prompting")
    parser.add_argument("--log", default=None, help="JSON log path")
    parser.add_argument("--signal", action="store_true",
                        help="an AC signal is on the V input: take the frequency steps")
    args = parser.parse_args(argv)

    interactive = args.hold is None and sys.stdin.isatty()
    hold = args.hold if args.hold is not None else 8.0
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = args.log or "dmm_front_panel_check_%s.json" % stamp
    record = {"resource": args.resource, "started": stamp, "steps": [],
              "signal": bool(args.signal)}

    print("Leave the meter's inputs open%s. Watch its front panel."
          % (" but for the signal on V" if args.signal else ""))
    if interactive:
        if input("Ready? [y/N] ").strip().lower() != "y":
            return 1

    try:
        dmm = Tti1604.connect(args.resource)
    except BenchToolsError as exc:
        print("error: %s" % exc)
        return 1

    with dmm:
        record["identity"] = dmm.identify().raw
        record["original"] = _readback(dmm)
        print("Meter: %s, found on %s\n" % (record["identity"], record["original"]["function"]))
        stopped = False
        try:
            stopped = _run_steps(dmm, record, hold, interactive, signal=args.signal)
        except BenchToolsError as exc:
            print("error: %s" % exc)
            record["error"] = str(exc)
        finally:
            # Leave the meter safe and on its own front panel, whatever happened.
            try:
                if not dmm.is_remote:
                    dmm.remote()
                _dc_volts(dmm)
                record["restored"] = _readback(dmm)
            finally:
                dmm.local()
            print("Meter left on DC volts, auto-ranging, in local mode.")

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
