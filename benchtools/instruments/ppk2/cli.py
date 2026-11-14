"""Command line for the PPK2 driver: ``benchtools ppk2``.

Every sub-command but ``list`` takes ``--resource sim://``, the default, so
the tool runs without a kit. ``-r ppk2://`` opens the only PPK2 on the PC.

Examples::

    benchtools ppk2 list
    benchtools ppk2 -r ppk2:// info
    benchtools ppk2 -r ppk2:// measure --duration 1
    benchtools ppk2 -r ppk2:// --voltage-limit 3.3 voltage 3.0
    benchtools ppk2 -r ppk2:// mode source
    benchtools ppk2 -r ppk2:// power on
    benchtools ppk2 -r ppk2:// measure --duration 2 --threshold 0.001 --csv run.csv

``mode``, ``voltage`` and ``power`` change what the kit supplies. Read what is
wired to it before using them.

Traces to: PPK-FR-011, PPK-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from ...core.errors import BenchToolsError
from .constants import DEFAULT_TIMEOUT, MAX_DURATION, VOLTAGE_RANGE
from .measurement import Measurement
from .ppk2 import Ppk2, find_ppk2_ports

_EXIT_OK = 0
_EXIT_ERROR = 1


def _emit(payload: object, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def write_csv(result: Measurement, path: str) -> str:
    """Write every sample of *result* to *path*: seconds, amps, D0-D7."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("time_s,current_a,logic\n")
        for index, (amps, logic) in enumerate(zip(result.amps, result.logic)):
            handle.write("%.5f,%.9g,%d\n" % (index * result.period, amps, logic))
    return path


def _cmd_info(kit: Ppk2, args: argparse.Namespace) -> int:
    _emit({"identity": kit.identity(), "info": kit.info(), "metadata": kit.metadata},
          args.json)
    return _EXIT_OK


def _cmd_measure(kit: Ppk2, args: argparse.Namespace) -> int:
    result = kit.measure(args.duration, threshold=args.threshold, release=args.release,
                         line=args.line)
    payload = result.as_dict()
    if not args.pulses and payload["pulses"] is not None:
        payload["pulses"].pop("pulses")
    if args.csv:
        payload["csv"] = write_csv(result, args.csv)
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_mode(kit: Ppk2, args: argparse.Namespace) -> int:
    _emit({"mode": kit.set_mode(args.mode), "powered": kit.powered}, args.json)
    return _EXIT_OK


def _cmd_voltage(kit: Ppk2, args: argparse.Namespace) -> int:
    _emit({"volts": kit.set_voltage(args.volts)}, args.json)
    return _EXIT_OK


def _cmd_power(kit: Ppk2, args: argparse.Namespace) -> int:
    _emit({"powered": kit.power(args.state == "on"), "mode": kit.mode, "volts": kit.volts},
          args.json)
    return _EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """The argument parser."""
    parser = argparse.ArgumentParser(
        prog="benchtools ppk2",
        description="Measure current with a Nordic Power Profiler Kit II.",
        epilog="Use --resource sim:// (the default) to run against the simulator. "
               "mode, voltage and power change what the kit supplies.",
    )
    parser.add_argument("-r", "--resource", default="sim://",
                        help="ppk2:// (the only kit), ppk2://<serial number>, a port "
                             "such as COM5, or sim:// (default)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="seconds a measurement may overrun (default %g)" % DEFAULT_TIMEOUT)
    parser.add_argument("--voltage-limit", type=float, default=VOLTAGE_RANGE[1],
                        help="highest voltage to set or power on at (default %g)"
                             % VOLTAGE_RANGE[1])
    parser.add_argument("--no-spike-filter", action="store_true",
                        help="keep the raw samples after a range change")
    parser.add_argument("--json", metavar="PATH", help="also write the result to PATH")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="list the PPK2s plugged into this PC")

    info = commands.add_parser("info", help="identify the kit and show its settings")
    info.set_defaults(handler=_cmd_info)

    measure = commands.add_parser("measure", help="record the current for a time")
    measure.add_argument("--duration", type=float, default=1.0,
                         help="seconds, at most %g (default 1)" % MAX_DURATION)
    marks = measure.add_mutually_exclusive_group()
    marks.add_argument("--threshold", type=float,
                       help="amps: report the pulses at or above it")
    marks.add_argument("--line", type=int, choices=range(8),
                       help="logic input: report the pulses while it is high")
    measure.add_argument("--release", type=float,
                         help="amps a pulse falls below to end (default: the threshold)")
    measure.add_argument("--pulses", action="store_true", help="list every pulse")
    measure.add_argument("--csv", help="write every sample to this CSV")
    measure.set_defaults(handler=_cmd_measure)

    mode = commands.add_parser("mode", help="select source or ammeter mode (DUT power off)")
    mode.add_argument("mode", choices=("source", "ammeter"))
    mode.set_defaults(handler=_cmd_mode)

    voltage = commands.add_parser("voltage", help="set the regulator voltage")
    voltage.add_argument("volts", type=float)
    voltage.set_defaults(handler=_cmd_voltage)

    power = commands.add_parser("power", help="switch the DUT power on or off")
    power.add_argument("state", choices=("on", "off"))
    power.set_defaults(handler=_cmd_power)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit status."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING if not args.verbose else logging.INFO,
                        format="%(levelname)-8s %(name)s: %(message)s")
    if args.command == "list":
        _emit(find_ppk2_ports(), args.json)
        return _EXIT_OK
    try:
        kit = Ppk2.connect(args.resource, timeout=args.timeout,
                           voltage_limit=args.voltage_limit,
                           spike_filter=not args.no_spike_filter)
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR
    try:
        return args.handler(kit, args)
    except (BenchToolsError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        kit.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
