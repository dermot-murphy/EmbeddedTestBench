"""Command line for the TTi 1604 multimeter.

``benchtools dmm --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
meter attached.

One deliberate choice: no sub-command selects a current function unless it is
named. ``measure dc_milliamps`` does; ``read`` and ``log`` measure whatever the
meter is set to, because selecting a current function with the leads across a
voltage source puts the meter's shunt across it.

Traces to: DMM-FR-060, DMM-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError
from .constants import MODEL, SELECTABLE_FUNCTIONS
from .dmm import Tti1604

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_ERROR = 1


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


# ---------------------------------------------------------------------------
def _cmd_info(dmm: Tti1604, args) -> int:
    identity = dmm.identify()
    _emit(
        {
            "identity": identity.raw,
            "manufacturer": identity.manufacturer,
            "model": identity.model,
            "note": "the 1604 has no identification query; it is identified by "
                    "its key echo and reading frames",
            "state": dmm.current_state().as_dict(),
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_read(dmm: Tti1604, args) -> int:
    reading = dmm.read(fresh=not args.stale)
    payload = reading.as_dict()
    if not reading.is_live:
        payload["warning"] = (
            "this reading is not a live measurement: %s"
            % ("overload (OFL)" if reading.overload else
               "the display is held or recalled" if reading.frozen else
               "the display is not a number")
        )
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_measure(dmm: Tti1604, args) -> int:
    value = dmm.measure(args.function, allow_relative=args.allow_relative)
    reading = dmm.last_reading
    _emit({"function": args.function, "value": value,
           "unit": reading.unit if reading else "",
           "range": reading.range_label if reading else ""}, args.json)
    return _EXIT_OK


def _cmd_log(dmm: Tti1604, args) -> int:
    readings = dmm.read_many(args.count)
    _emit({"count": len(readings),
           "readings": [reading.as_dict() for reading in readings]}, args.json)
    return _EXIT_OK


def _cmd_function(dmm: Tti1604, args) -> int:
    _emit(dmm.select_function(args.function).as_dict(), args.json)
    return _EXIT_OK


def _cmd_range(dmm: Tti1604, args) -> int:
    if args.full_scale.lower() == "auto":
        reading = dmm.set_auto_range()
    else:
        try:
            full_scale = float(args.full_scale)
        except ValueError:
            print("error: range must be 'auto' or a full scale in SI units, "
                  "such as 40 or 4e-3", file=sys.stderr)
            return _EXIT_ERROR
        reading = dmm.set_range(full_scale)
    _emit(reading.as_dict(), args.json)
    return _EXIT_OK


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchtools dmm",
        description="Read a TTi %s bench multimeter over RS-232." % MODEL,
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="/dev/ttyUSB1, COM6, serial://socket://host:4003 or sim:// (default)",
    )
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="seconds to wait for a reading")
    parser.add_argument("--json", metavar="PATH", help="also write the JSON result here")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="-v for progress, -vv for every byte")

    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="identify the meter and show its state")
    info.set_defaults(handler=_cmd_info)

    read = subparsers.add_parser("read", help="one reading of whatever the meter is set to")
    read.add_argument("--stale", action="store_true",
                      help="accept the next frame even if measured before the request")
    read.set_defaults(handler=_cmd_read)

    measure = subparsers.add_parser("measure", help="select a function and measure it")
    measure.add_argument("function", choices=SELECTABLE_FUNCTIONS)
    measure.add_argument("--allow-relative", action="store_true",
                         help="accept a reading with Null active")
    measure.set_defaults(handler=_cmd_measure)

    log = subparsers.add_parser("log", help="consecutive readings, 2.5 per second")
    log.add_argument("--count", "-n", type=int, default=10)
    log.set_defaults(handler=_cmd_log)

    function = subparsers.add_parser("function", help="select what the meter measures")
    function.add_argument("function", choices=SELECTABLE_FUNCTIONS)
    function.set_defaults(handler=_cmd_function)

    ranging = subparsers.add_parser("range", help="'auto', or a full scale such as 40 or 4e-3")
    ranging.add_argument("full_scale")
    ranging.set_defaults(handler=_cmd_range)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools dmm``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        dmm = Tti1604.connect(args.resource, timeout=args.timeout)
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(dmm, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        dmm.close()
