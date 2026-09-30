"""Command line for the Pico 2 + SHT30-D thermometer.

``benchtools thermo --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
Pico attached.

Traces to: PICO-FR-060, PICO-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError
from .constants import DEFAULT_BAUDRATE
from .thermometer import PicoSht30

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_ERROR = 1


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _cmd_ver(thermometer: PicoSht30, args) -> int:
    _emit(thermometer.firmware_info().as_dict(), args.json)
    return _EXIT_OK


def _cmd_temp(thermometer: PicoSht30, args) -> int:
    readings = []
    for index in range(args.count):
        if index and args.interval > 0:
            time.sleep(args.interval)
        readings.append(thermometer.read().as_dict())
    payload = readings[0] if args.count == 1 else {"readings": readings}
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_status(thermometer: PicoSht30, args) -> int:
    _emit(thermometer.status().as_dict(), args.json)
    return _EXIT_OK


def _cmd_sreset(thermometer: PicoSht30, args) -> int:
    thermometer.soft_reset_sensor()
    _emit({"sensor_reset": True}, args.json)
    return _EXIT_OK


def _cmd_bootsel(thermometer: PicoSht30, args) -> int:
    thermometer.enter_bootloader()
    _emit({"bootloader": True,
           "next": "copy the .uf2 to the RP2350 drive that appears"}, args.json)
    return _EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """The argument parser for ``benchtools thermo``."""
    parser = argparse.ArgumentParser(
        prog="benchtools thermo",
        description="Read a Raspberry Pi Pico 2 + SHT30-D thermometer.",
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="serial port (/dev/ttyACM0, COM5) or sim:// (default)",
    )
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE,
                        help="line rate; ignored by USB CDC but needed to open the port")
    parser.add_argument("--timeout", type=float, default=2.0, help="I/O timeout in seconds")
    parser.add_argument("--json", metavar="PATH", help="also write the JSON result here")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="log more; repeat for debug output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    ver = subparsers.add_parser("ver", help="title, firmware version and identity")
    ver.set_defaults(handler=_cmd_ver)

    temp = subparsers.add_parser("temp", help="read temperature and humidity")
    temp.add_argument("--count", "-n", type=int, default=1, help="readings to take")
    temp.add_argument("--interval", "-i", type=float, default=1.0,
                      help="seconds between readings")
    temp.set_defaults(handler=_cmd_temp)

    status = subparsers.add_parser("status", help="decode the sensor status register")
    status.set_defaults(handler=_cmd_status)

    sreset = subparsers.add_parser("sreset", help="soft-reset the sensor")
    sreset.set_defaults(handler=_cmd_sreset)

    bootsel = subparsers.add_parser("bootsel", help="reboot into the USB bootloader")
    bootsel.set_defaults(handler=_cmd_bootsel)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools thermo``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "count", 1) < 1:
        parser.error("--count must be at least 1")

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        thermometer = PicoSht30.connect(args.resource, baudrate=args.baudrate,
                                        timeout=args.timeout)
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(thermometer, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        thermometer.close()
