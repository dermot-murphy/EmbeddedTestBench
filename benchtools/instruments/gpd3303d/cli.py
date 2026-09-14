"""Command line for the GW Instek GPD-3303D supply.

``benchtools psu --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
supply attached.

Two deliberate choices, both about not damaging what is connected:

* ``set`` does not switch the output on. ``--on`` does that, explicitly.
* ``off`` with no channel opens the supply's real output switch; ``off 1``
  parks one channel at zero volts, which is not the same thing and says so.

Traces to: PSU-FR-060, PSU-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError
from .constants import (
    CHANNELS,
    DEFAULT_BAUDRATE,
    MODEL,
    TRACKED_CHANNEL,
    TrackingMode,
)
from .psu import Gpd3303D

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
def _cmd_info(psu: Gpd3303D, args) -> int:
    identity = psu.identify()
    status = psu.status()
    _emit(
        {
            "identity": identity.raw,
            "manufacturer": identity.manufacturer,
            "model": identity.model,
            "serial_number": identity.serial_number,
            "firmware": identity.firmware,
            "status": status.as_dict(),
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_read(psu: Gpd3303D, args) -> int:
    channels = [args.channel] if args.channel else list(CHANNELS)
    readings = [psu.read_channel(channel).as_dict() for channel in channels]
    tracking = psu.tracking
    payload = {"channels": readings, "output": psu.output, "tracking": tracking}
    if tracking in (TrackingMode.SERIES, TrackingMode.PARALLEL) and (
        TRACKED_CHANNEL in channels
    ):
        # Not a refusal - reading is always allowed - but the figures for the
        # slaved channel are channel 1's, and nothing in them says so.
        payload["tracking_warning"] = (
            "the supply is in %s tracking: channel %d follows channel 1, so its "
            "figures are channel 1's setting rather than one anyone made for it."
            % (tracking, TRACKED_CHANNEL)
        )
    limited = [reading["channel"] for reading in readings if reading["in_current_limit"]]
    if limited:
        payload["warning"] = (
            "channel(s) %s are in current limit: the rail is below its setpoint, "
            "so any measurement taken now is of a different circuit from the one "
            "that was asked for." % ", ".join(str(item) for item in limited)
        )
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_set(psu: Gpd3303D, args) -> int:
    """Program a channel. Switching it on is a separate decision."""
    if args.current is not None:
        psu.set_current_limit(args.channel, args.current)
    if args.voltage is not None:
        psu.set_voltage(args.channel, args.voltage)
    if args.on:
        psu.output_on(args.channel)
    _emit(psu.read_channel(args.channel).as_dict(), args.json)
    return _EXIT_OK


def _cmd_on(psu: Gpd3303D, args) -> int:
    if args.channel:
        psu.output_on(args.channel)
    else:
        psu.all_outputs_on()
    _emit({"output": psu.output,
           "channels": [reading.as_dict() for reading in psu.read_all()]}, args.json)
    return _EXIT_OK


def _cmd_off(psu: Gpd3303D, args) -> int:
    payload = {}
    if args.channel:
        psu.output_off(args.channel)
        payload["note"] = (
            "channel %d is parked at 0 V with its current limit unchanged. This "
            "supply has one output switch for both channels, so a single channel "
            "is not disconnected and this is not a safety interlock."
            % args.channel
        )
    else:
        psu.all_outputs_off()
    payload["output"] = psu.output
    payload["channels"] = [reading.as_dict() for reading in psu.read_all()]
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_status(psu: Gpd3303D, args) -> int:
    _emit(psu.status().as_dict(), args.json)
    return _EXIT_OK


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchtools psu",
        description="Control a %s bench power supply." % MODEL,
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="/dev/ttyUSB0, COM4, serial://COM4:57600 or sim:// (default)",
    )
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE,
                        help="line rate, matching the supply's own setting")
    parser.add_argument("--timeout", type=float, default=5.0, help="I/O timeout in seconds")
    parser.add_argument("--json", metavar="PATH", help="also write the JSON result here")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="-v for progress, -vv for every command")

    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="identify the supply and read its status")
    info.set_defaults(handler=_cmd_info)

    read = subparsers.add_parser("read", help="measure voltage, current and mode")
    read.add_argument("channel", nargs="?", type=int, choices=CHANNELS,
                      help="a channel, or omit for all of them")
    read.set_defaults(handler=_cmd_read)

    configure = subparsers.add_parser("set", help="set a channel's voltage and current limit")
    configure.add_argument("channel", type=int, choices=CHANNELS)
    configure.add_argument("--voltage", "-V", type=float, help="volts")
    configure.add_argument("--current", "-I", type=float, help="current limit in amps")
    configure.add_argument("--on", action="store_true", help="also switch the channel on")
    configure.set_defaults(handler=_cmd_set)

    on = subparsers.add_parser("on", help="switch a channel, or the supply, on")
    on.add_argument("channel", nargs="?", type=int, choices=CHANNELS)
    on.set_defaults(handler=_cmd_on)

    off = subparsers.add_parser("off", help="switch a channel off, or the supply off")
    off.add_argument("channel", nargs="?", type=int, choices=CHANNELS)
    off.set_defaults(handler=_cmd_off)

    status = subparsers.add_parser("status", help="decode the status word")
    status.set_defaults(handler=_cmd_status)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools psu``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        psu = Gpd3303D.connect(args.resource, baudrate=args.baudrate, timeout=args.timeout)
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(psu, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        psu.close()
