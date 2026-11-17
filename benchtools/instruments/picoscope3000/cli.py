"""Command line for the PicoScope 3000D driver: ``benchtools pscope``.

Every sub-command takes ``--resource sim://``, the default, so the tool runs
without a scope. ``-r pico://`` opens the first PicoScope on USB.

Examples::

    benchtools pscope -r pico:// info
    benchtools pscope -r pico:// capture -c A B --range 2 --interval 2e-6 \\
        --samples 10000 --trigger A --level 0 --csv a.csv --plot a.png
    benchtools pscope -r pico:// capture -c A --digital 0 --digital-trigger 0:RISE
    benchtools pscope -r pico:// siggen --wave SINE --frequency 1000 --vpp 1
    benchtools pscope -r pico:// siggen --off

Traces to: PSCOPE-FR-030, PSCOPE-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Dict, List, Optional, Sequence

from ...core.errors import BenchToolsError
from .constants import Channel, DigitalDirection, ThresholdDirection, WaveType
from .scope import PicoScope3000

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_USAGE = 2


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _digital_conditions(items: Sequence[str]) -> Dict[int, str]:
    conditions: Dict[int, str] = {}
    for item in items:
        bit, _, condition = item.partition(":")
        try:
            conditions[int(bit.upper().lstrip("D"))] = condition or "RISE"
        except ValueError as exc:
            raise SystemExit("--digital-trigger takes BIT:CONDITION, e.g. 0:RISE, not %r"
                             % item) from exc
    return conditions


def _cmd_info(scope: PicoScope3000, args: argparse.Namespace) -> int:
    _emit({"identity": scope.identity(), "unit": scope.unit_info()}, args.json)
    return _EXIT_OK


def _cmd_capture(scope: PicoScope3000, args: argparse.Namespace) -> int:
    channels: List[Channel] = [Channel.parse(item) for item in args.channels]
    for channel in scope.limits.channels:
        if channel in channels:
            scope.configure_channel(channel, range_volts=args.range, coupling=args.coupling,
                                    offset=args.offset)
        else:
            scope.enable_channel(channel, False)
    for port in (0, 1):
        scope.configure_digital_port(port, port in args.digital, args.threshold)
    scope.set_sample_interval(args.interval)
    scope.set_record_length(args.samples, args.pre_trigger)
    if args.digital_trigger:
        scope.configure_digital_trigger(_digital_conditions(args.digital_trigger),
                                        auto_ms=args.auto_ms)
    elif args.trigger:
        scope.configure_edge_trigger(args.trigger, level=args.level, slope=args.slope,
                                     auto_ms=args.auto_ms)
    else:
        scope.disable_trigger()
    block = scope.capture(timeout=args.timeout)
    result = {
        "sample_interval_s": block.sample_interval,
        "timebase": block.timebase,
        "points": args.samples,
        "overrange": ["ABCD"[number - 1] for number in block.overrange],
        "channels": {
            "ABCD"[number - 1]: {
                "min_v": record.minimum, "max_v": record.maximum,
                "peak_to_peak_v": record.peak_to_peak, "mean_v": record.mean,
            } for number, record in sorted(block.analog.items())},
        "digital": {
            "D%d" % bit: {"high_fraction": record.mean,
                          "edges": sum(1 for a, b in zip(record.volts, record.volts[1:])
                                       if a != b)}
            for bit, record in sorted(block.digital.items())},
    }
    if args.csv:
        result["csv"] = block.to_csv(args.csv)
    if args.plot and block.analog:
        from ...analysis.plotting import plot_waveforms  # pylint: disable=import-outside-toplevel
        result["plot"] = plot_waveforms(block.analog, args.plot, title=args.title)
    _emit(result, args.json)
    return _EXIT_OK


def _cmd_siggen(scope: PicoScope3000, args: argparse.Namespace) -> int:
    if args.off:
        scope.signal_generator_off()
        _emit({"signal_generator": "off (0 V DC)"}, args.json)
    else:
        scope.set_signal_generator(args.wave, args.frequency, args.vpp, args.offset)
        _emit({"signal_generator": {"wave": args.wave, "frequency_hz": args.frequency,
                                    "peak_to_peak_v": args.vpp, "offset_v": args.offset}},
              args.json)
    return _EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """The argument parser."""
    parser = argparse.ArgumentParser(
        prog="benchtools pscope",
        description="Control a PicoScope 3000D series MSO (four analogue channels, "
                    "16 digital, signal generator) through the ps3000a SDK.",
        epilog="Use --resource sim:// (the default) to run against the simulator.",
    )
    parser.add_argument("-r", "--resource", default="sim://",
                        help="pico:// (first unit), pico://<serial>, or sim:// (default)")
    parser.add_argument("--sdk-path", help="folder holding the ps3000a library")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="seconds a capture waits for its trigger (default 10)")
    parser.add_argument("--json", metavar="PATH", help="also write the result to PATH")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    commands = parser.add_subparsers(dest="command", required=True)

    info = commands.add_parser("info", help="identify the scope")
    info.set_defaults(handler=_cmd_info)

    capture = commands.add_parser("capture", help="capture one block")
    capture.add_argument("-c", "--channels", nargs="*", default=["A"],
                         help="analogue channels to capture, A to D (default A)")
    capture.add_argument("--range", type=float, default=5.0,
                         help="full scale, +/- volts, rounded up to a range (default 5)")
    capture.add_argument("--coupling", default="DC", choices=("DC", "AC"))
    capture.add_argument("--offset", type=float, default=0.0, help="analogue offset, volts")
    capture.add_argument("--digital", type=int, nargs="*", default=[], choices=(0, 1),
                         help="digital ports to capture: 0 is D0-D7, 1 is D8-D15")
    capture.add_argument("--threshold", type=float, default=1.5,
                         help="digital logic threshold, volts (default 1.5)")
    capture.add_argument("--interval", type=float, default=1e-6,
                         help="seconds per sample (default 1e-6)")
    capture.add_argument("--samples", type=int, default=10000, help="points (default 10000)")
    capture.add_argument("--pre-trigger", type=float, default=0.2,
                         help="fraction of the record before the trigger (default 0.2)")
    capture.add_argument("--trigger", help="analogue trigger channel, A to D (default: none)")
    capture.add_argument("--level", type=float, default=0.0, help="trigger level, volts")
    capture.add_argument("--slope", default="RISE",
                         choices=[member.value for member in ThresholdDirection])
    capture.add_argument("--digital-trigger", nargs="*", default=[], metavar="BIT:COND",
                         help="digital trigger, e.g. 0:RISE 3:HIGH; conditions "
                              + ", ".join(member.value for member in DigitalDirection))
    capture.add_argument("--auto-ms", type=int, default=0,
                         help="capture anyway after this many ms without a trigger")
    capture.add_argument("--csv", help="write every record to this CSV")
    capture.add_argument("--plot", help="plot the analogue records to this image")
    capture.add_argument("--title", default="PicoScope capture")
    capture.set_defaults(handler=_cmd_capture)

    siggen = commands.add_parser("siggen", help="drive the signal generator")
    siggen.add_argument("--wave", default="SINE", choices=[member.value for member in WaveType])
    siggen.add_argument("--frequency", type=float, default=1e3, help="Hz (default 1000)")
    siggen.add_argument("--vpp", type=float, default=1.0, help="peak-to-peak volts (default 1)")
    siggen.add_argument("--offset", type=float, default=0.0, help="volts (default 0)")
    siggen.add_argument("--off", action="store_true", help="drive the output to 0 V DC")
    siggen.set_defaults(handler=_cmd_siggen)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit status."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING if not args.verbose else logging.INFO,
                        format="%(levelname)-8s %(name)s: %(message)s")
    try:
        scope = PicoScope3000.connect(args.resource, timeout=args.timeout,
                                      sdk_path=args.sdk_path)
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR
    try:
        return args.handler(scope, args)
    except (BenchToolsError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    except SystemExit as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_USAGE
    finally:
        scope.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
