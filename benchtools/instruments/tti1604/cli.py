"""Command line for the TTi 1604 multimeter.

``benchtools dmm --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
meter attached.

Two deliberate choices, both about not reporting a number that is not true:

* ``read`` reports ``held`` alongside the value, and ``--reject-held`` turns a
  frozen display into a non-zero exit rather than a reading.
* There is no ``on`` sub-command. The Operate key toggles, so a command named
  for switching the meter on would switch off a meter that already was.

Traces to: DMM-FR-070, DMM-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError
from .constants import DEFAULT_BAUDRATE, KEYS, MODEL
from .dmm import Tti1604

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_HELD = 2


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _as_dict(reading) -> dict:
    return {
        "value": reading.value,
        "unit": reading.unit,
        "display": reading.text,
        "measurement": reading.measurement,
        "coupling": "AC" if reading.ac else "DC",
        "range": reading.range_description,
        "overrange": reading.overrange,
        "held": reading.held,
        "flags": {name: state for name, state in sorted(reading.flags.items()) if state},
        "status": {name: state for name, state in sorted(reading.status.items()) if state},
    }


def _cmd_info(dmm: Tti1604, args) -> int:
    _emit(
        {
            "model": MODEL,
            "manufacturer": dmm.manufacturer,
            "identity": dmm.identity(),
            "remote": dmm.is_remote,
            "note": "the 1604 answers no identification query; this is the driver's own",
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_read(dmm: Tti1604, args) -> int:
    readings = dmm.read_many(args.count)
    payload = [_as_dict(reading) for reading in readings]
    _emit(payload[0] if args.count == 1 else payload, args.json)
    if args.reject_held and any(reading.held for reading in readings):
        print(
            "error: the display is frozen (Hold, Touch-Hold or Min-Max review), so "
            "that reading is not this moment's measurement",
            file=sys.stderr,
        )
        return _EXIT_HELD
    return _EXIT_OK


def _cmd_press(dmm: Tti1604, args) -> int:
    for key in args.keys:
        dmm.press(key)
    _emit({"pressed": list(args.keys)}, args.json)
    return _EXIT_OK


def _cmd_keys(_dmm, args) -> int:
    _emit({"keys": dict(sorted(KEYS.items()))}, args.json)
    return _EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``benchtools dmm``."""
    parser = argparse.ArgumentParser(
        prog="benchtools dmm",
        description="Read a TTi 1604 bench multimeter over RS-232.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="/dev/ttyUSB0, COM5, serial://COM5 or sim:// (default)",
    )
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE,
                        help="line rate; the 1604's is fixed at 9600")
    parser.add_argument("--timeout", type=float, default=5.0, help="I/O timeout in seconds")
    parser.add_argument("--json", metavar="PATH", help="also write the JSON result here")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="-v for progress, -vv for every command")

    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="what the driver is talking to")
    info.set_defaults(handler=_cmd_info)

    read = subparsers.add_parser("read", help="take one or more measurements")
    read.add_argument("-n", "--count", type=int, default=1, help="how many readings")
    read.add_argument("--reject-held", action="store_true",
                      help="exit non-zero if the display is frozen")
    read.set_defaults(handler=_cmd_read)

    press = subparsers.add_parser("press", help="press front-panel keys by name")
    press.add_argument("keys", nargs="+", help="for example: volts dc auto")
    press.set_defaults(handler=_cmd_press)

    keys = subparsers.add_parser("keys", help="list the key names this driver knows")
    keys.set_defaults(handler=_cmd_keys)

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
        dmm = Tti1604.connect(args.resource, baudrate=args.baudrate, timeout=args.timeout)
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
