"""Command line for the Pico 2 + SHT30-D thermometer.

``benchtools thermo --help``. ``flash`` reflashes the Pico with no BOOTSEL
press; see :mod:`.flash`. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
Pico attached.

Traces to: PICO-FR-060, PICO-FR-061, PICO-FR-075, PICO-DD-CLI.
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
from .constants import DEFAULT_BAUDRATE, RD_OPTIONS
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


def _cmd_info(thermometer: PicoSht30, args) -> int:
    _emit(thermometer.firmware_info().as_dict(), args.json)
    return _EXIT_OK


def _cmd_rd(thermometer: PicoSht30, args) -> int:
    _emit({"option": args.option, "value": thermometer.rd(args.option)}, args.json)
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


def _cmd_ecureset(thermometer: PicoSht30, args) -> int:
    thermometer.reset()
    _emit({"rebooted": True}, args.json)
    return _EXIT_OK


def _cmd_bootsel(thermometer: PicoSht30, args) -> int:
    thermometer.enter_bootloader()
    _emit({"bootloader": True,
           "next": "copy the .uf2 to the RP2350 drive that appears"}, args.json)
    return _EXIT_OK


def _cmd_flash(args) -> int:
    """Reflash with no BOOTSEL press; exit 1 if the result does not match."""
    from .flash import SimulatedRp2350, PicoFlasher

    timeouts = {"bootloader_timeout": args.bootloader_timeout,
                "port_timeout": args.port_timeout}
    board = None
    if args.resource.startswith(("sim", "mock")):
        board = SimulatedRp2350()
        flasher = board.flasher(**timeouts)
    else:
        flasher = PicoFlasher(port=args.resource or None, drive=args.drive, **timeouts)
    try:
        result = flasher.flash(args.uf2, expect_version=args.expect_version,
                               any_image=args.any_image, verify=not args.no_verify)
    finally:
        if board is not None:
            board.close()
    _emit(result.as_dict(), args.json)
    return _EXIT_OK if result.ok else _EXIT_ERROR


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

    info = subparsers.add_parser("info", help="name, copyright, version and commit SHA")
    info.set_defaults(handler=_cmd_info)

    rd = subparsers.add_parser("rd", help="send one 'rd' command and print its value")
    rd.add_argument("option", choices=RD_OPTIONS)
    rd.set_defaults(handler=_cmd_rd)

    temp = subparsers.add_parser("temp", help="read the temperature (rd temperature)")
    temp.add_argument("--count", "-n", type=int, default=1, help="readings to take")
    temp.add_argument("--interval", "-i", type=float, default=1.0,
                      help="seconds between readings")
    temp.set_defaults(handler=_cmd_temp)

    status = subparsers.add_parser("status", help="decode the sensor status register")
    status.set_defaults(handler=_cmd_status)

    sreset = subparsers.add_parser("sreset", help="soft-reset the sensor")
    sreset.set_defaults(handler=_cmd_sreset)

    ecureset = subparsers.add_parser("ecureset", help="reboot the Pico")
    ecureset.set_defaults(handler=_cmd_ecureset)

    bootsel = subparsers.add_parser("bootsel", help="reboot into the USB bootloader")
    bootsel.set_defaults(handler=_cmd_bootsel)

    flash = subparsers.add_parser(
        "flash", help="reflash from a .uf2 with no BOOTSEL press, then check the build",
        description="Reboot the Pico into its USB bootloader (the 'bootsel' command, or "
                    "a 1200-baud reset), copy the UF2 onto the RP2350 drive, and check "
                    "'rd name', 'rd version' and 'rd sha' afterwards against the image. "
                    "A Pico already in its "
                    "bootloader is flashed as it is. With -r '' the port is found by "
                    "USB vendor ID afterwards.",
    )
    flash.add_argument("uf2", help="the image, e.g. build/pico_sht30/pico_sht30.uf2")
    flash.add_argument("--expect-version", metavar="VX.YY.ZZZZ",
                       help="the rd version the new image must report "
                            "(default: the version stored in the image)")
    flash.add_argument("--drive", help="the RP2350 drive, if it cannot be found, e.g. E:")
    flash.add_argument("--any-image", action="store_true",
                       help="allow an image that is not the thermometer firmware")
    flash.add_argument("--no-verify", action="store_true",
                       help="do not read 'rd' afterwards")
    flash.add_argument("--bootloader-timeout", type=float, default=15.0,
                       help="seconds to wait for the RP2350 drive (default 15)")
    flash.add_argument("--port-timeout", type=float, default=20.0,
                       help="seconds to wait for the port to come back (default 20)")
    flash.set_defaults(handler=_cmd_flash, standalone=True)
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

    if getattr(args, "standalone", False):
        # flash opens the port itself: the Pico may be in its bootloader, with
        # no port to open.
        try:
            return args.handler(args)
        except BenchToolsError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return _EXIT_ERROR

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
