"""Command line for the Nordic BLE dongle.

``benchtools ble --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
dongle and no sensor.

``--log PATH`` records the whole session - every line in both directions, host
timestamped - beside whatever the sub-command prints. That file is the evidence
for a measurement; the JSON is the summary.

Traces to: BLE-FR-070, BLE-FR-071, BLE-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError, ConfigurationError
from .constants import DEFAULT_BAUDRATE, DEFAULT_COMMAND_TIMEOUT
from .dongle import NordicDongle, Sensor
from .latency import LatencySource
from .protocol import normalise_address

__all__ = ["main", "build_parser"]

_LOG = logging.getLogger("benchtools.ble")

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_USAGE = 2


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _is_address(text: str) -> bool:
    try:
        normalise_address(text)
    except BenchToolsError:
        return False
    return True


def _choose(dongle: NordicDongle, target: str, scan_seconds: float) -> Sensor:
    """Select *target*: an address as given, otherwise a name or part of one.

    A name is what an operator types, and usually only part of it: the
    advertised name carries the firmware version and changes on every reflash.
    The first scan uses the firmware's name filter, which is case-sensitive;
    if that finds nothing, an unfiltered scan lets the host match ignoring
    case. The strongest sensor whose name contains *target* is chosen (#124).
    """
    if _is_address(target):
        return dongle.select(target)
    dongle.scan(scan_seconds, name=target)
    if not any(target.casefold() in (sensor.name or "").casefold() for sensor in dongle.sensors):
        dongle.scan(scan_seconds)
    return dongle.select_by_name(target)


def _select(dongle: NordicDongle, args) -> None:
    """Apply ``--select``: an address, a name, or part of a name."""
    target = getattr(args, "select", None)
    if target:
        _choose(dongle, target, args.scan_seconds)


# ---------------------------------------------------------------------------
def _cmd_info(dongle: NordicDongle, args) -> int:
    identity = dongle.identify()
    _emit(
        {
            "identity": identity.raw,
            "manufacturer": identity.manufacturer,
            "model": identity.model,
            "firmware": dongle.firmware_version,
            "built": dongle.firmware_built,
            "protocol": dongle.protocol_version,
            "driver_protocol": dongle.limits.model,
            "dongle_time_us": dongle.dongle_time_us(),
            "log": dongle.log_path,
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_firmware(dongle: NordicDongle, args) -> int:
    """Report the build on the dongle, and refresh it when asked."""
    status = dongle.check_firmware(args.build)
    if args.update and not status.matches and status.compared:
        status = dongle.update_firmware(args.build, port=args.port)

    payload = dict(status.as_dict())
    payload["protocol"] = dongle.protocol_version
    payload["protocol_compatible"] = dongle.protocol_is_compatible
    if status.compared and not status.matches and not args.update:
        payload["warning"] = (
            "the dongle is not running the build in %s. Measurements taken with "
            "it answer a different question from the one this build asks. "
            "Re-run with --update to refresh it."
            % (args.build or "the configured build")
        )
    _emit(payload, args.json)
    if status.compared and not status.matches:
        return _EXIT_ERROR
    return _EXIT_OK


def _cmd_scan(dongle: NordicDongle, args) -> int:
    sensors = dongle.scan(
        args.duration,
        name=args.name,
        address=args.addr,
        active=args.active,
        min_rssi=args.rssi,
    )
    _emit(
        {
            "duration_s": args.duration,
            "count": len(sensors),
            "sensors": [sensor.as_dict() for sensor in sensors],
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_profile(dongle: NordicDongle, args) -> int:
    _select(dongle, args)
    profile = dongle.measure_advertising_profile(
        args.duration,
        address=args.addr,
        expected_interval=args.interval,
    )
    payload = dict(profile.as_dict())
    if not profile.is_complete:
        payload["warning"] = (
            "the host did not receive every report the dongle sent (%d lost, %d "
            "dropped by the dongle). Missed advertising events cannot be "
            "attributed to the sensor from this capture."
            % (profile.lost_reports, profile.dongle_dropped)
        )
    if args.events:
        payload["events"] = [event.as_dict() for event in profile.advertising_events]
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_cmd(dongle: NordicDongle, args) -> int:
    _select(dongle, args)
    if args.addr:
        dongle.select(args.addr)
    dongle.open_link()
    try:
        timing = dongle.measure_response_time(
            args.text,
            repeat=args.repeat,
            timeout=args.timeout_s,
            source=LatencySource.HOST if args.host_clock else LatencySource.DONGLE,
        )
    finally:
        dongle.close_link()

    payload = dict(timing.as_dict())
    payload["samples"] = [sample.as_dict() for sample in timing.samples]
    if not timing.is_trustworthy:
        payload["warning"] = (
            "the measured round trip (%.3f ms) is not large enough to be told "
            "apart from the link's own floor: the connection interval is "
            "%.1f ms and the clock resolves %.3f ms. The figure is about the "
            "connection parameters, not the sensor."
            % (
                timing.milliseconds,
                timing.quantisation_s * 1000.0,
                timing.resolution_s * 1000.0,
            )
        )
    _emit(payload, args.json)
    return _EXIT_OK


def _parse_variables(pairs: Sequence[str]) -> dict:
    """``NAME=VALUE`` pairs from ``--var``, as a mapping."""
    values = {}
    for pair in pairs or ():
        name, separator, value = pair.partition("=")
        if not separator or not name.strip():
            raise ConfigurationError("--var takes NAME=VALUE, not %r" % pair)
        values[name.strip()] = value
    return values


def _parse_timeouts(pairs: Sequence[str]) -> dict:
    """``PREFIX=MS`` pairs from ``--timeout``, as a mapping; the document checks the values."""
    timeouts = {}
    for pair in pairs or ():
        prefix, separator, value = pair.rpartition("=")
        if not separator or not prefix.strip() or not value.strip():
            raise ConfigurationError(
                "--timeout takes PREFIX=MS - a command prefix and its timeout in "
                "milliseconds, WR=45000 - not %r. The run's default is --timeout-s." % pair)
        timeouts[prefix.strip()] = value.strip()
    return timeouts


def _cmd_script(dongle: NordicDongle, args) -> int:
    """Run a command document: connect, send, check, report. Exit 1 on a fail."""
    run = dongle.run_script(
        args.document,
        report=args.report,
        timeout=args.timeout_s,
        listen=args.listen,
        variables=_parse_variables(args.var),
        events=args.events,
        timeouts=_parse_timeouts(args.prefix_timeouts),
    )
    payload = run.as_dict()
    payload["report"] = args.report
    payload["events"] = args.events
    payload["log"] = dongle.log_path
    _emit(payload, args.json)
    return _EXIT_OK if run.is_pass else _EXIT_ERROR


def _cmd_monitor(dongle: NordicDongle, args) -> int:
    """Stream events to the log and to the terminal."""
    _select(dongle, args)
    if args.addr or dongle.selected is not None:
        address = args.addr or dongle.selected.qualified_address
        dongle.session.execute("scan", "start", int(args.duration * 1000.0) + 1000)
        dongle.session.execute("adv", "start", address)
    else:
        dongle.session.execute("scan", "start", int(args.duration * 1000.0) + 1000)

    seen = 0
    try:
        for _event in dongle.session.collect(args.duration, on_event=lambda item: print(item.raw)):
            seen += 1
    finally:
        dongle.session.execute("adv", "stop", allow_error=True)
        dongle.session.execute("scan", "stop", allow_error=True)

    _emit({"events": seen, "duration_s": args.duration, "log": dongle.log_path}, args.json)
    return _EXIT_OK


def _cmd_select(dongle: NordicDongle, args) -> int:
    sensor = _choose(dongle, args.target, args.scan_seconds)
    _emit(sensor.as_dict(), args.json)
    return _EXIT_OK


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``benchtools ble``."""
    parser = argparse.ArgumentParser(
        prog="benchtools ble",
        description="Nordic BLE dongle: scan, select, UART over BLE, advertising profile.",
        epilog="Options naming the dongle come before the sub-command.",
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="sim:// for the simulator, or a serial port: COM5, /dev/ttyACM0, "
             "serial://socket://host:4001 for a port published over TCP "
             "(default: %(default)s)",
    )
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="line rate (USB CDC ignores it)")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="link timeout in seconds")
    parser.add_argument("--log", metavar="PATH", help="append the whole session to this text file")
    parser.add_argument("--firmware", metavar="PATH",
                        help="the firmware build the dongle should be running: a manifest, "
                             "or a directory holding one")
    parser.add_argument("--json", metavar="PATH", help="also write the result as JSON to PATH")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="repeat for debug")

    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="identify the dongle")
    info.set_defaults(handler=_cmd_info)

    firmware = subparsers.add_parser(
        "firmware",
        help="report the firmware on the dongle, and refresh it if it is not the build",
    )
    firmware.add_argument(
        "build", nargs="?",
        help="firmware manifest, or a directory holding one "
             "(firmware/nordic_dongle/_build after a build)",
    )
    firmware.add_argument("--update", action="store_true",
                          help="flash the build when the dongle is running something else")
    firmware.add_argument("--port", help="serial port the bootloader appears on, if it differs")
    firmware.set_defaults(handler=_cmd_firmware)

    scan = subparsers.add_parser("scan", help="list the sensors in range")
    scan.add_argument("--duration", type=float, default=3.0, help="seconds to scan")
    scan.add_argument("--name", help="keep only names containing this text")
    scan.add_argument("--addr", help="keep only this address")
    scan.add_argument("--active", action="store_true", help="request scan responses")
    scan.add_argument("--rssi", type=int, help="reject anything weaker, in dBm")
    scan.set_defaults(handler=_cmd_scan)

    select = subparsers.add_parser(
        "select", help="choose a sensor by address, name or part of a name")
    select.add_argument("target", help="an address, or a name or part of one (any case); "
                        "the strongest match is chosen")
    select.add_argument("--scan-seconds", type=float, default=3.0, help="scan first, for this long")
    select.set_defaults(handler=_cmd_select)

    profile = subparsers.add_parser("profile", help="measure the advertising profile")
    profile.add_argument("--duration", type=float, default=10.0, help="seconds to capture")
    profile_target = profile.add_mutually_exclusive_group()
    profile_target.add_argument("--addr", help="address to profile")
    profile_target.add_argument(
        "--select",
        help="scan for this name and profile it; part of a name, any case, "
             "chooses the strongest match")
    profile.add_argument("--scan-seconds", type=float, default=3.0)
    profile.add_argument("--interval", type=float, help="nominal advertising interval in seconds")
    profile.add_argument("--events", action="store_true", help="include every event in the output")
    profile.set_defaults(handler=_cmd_profile)

    command = subparsers.add_parser("cmd", help="send a command over BLE UART and time the reply")
    command.add_argument("text", help="command text, as the sensor's console expects it")
    command.add_argument("--repeat", type=int, default=1, help="exchanges to perform")
    command_target = command.add_mutually_exclusive_group()
    command_target.add_argument("--addr", help="address to connect to")
    command_target.add_argument(
        "--select",
        help="scan for this name and connect to it; part of a name, any case, "
             "chooses the strongest match")
    command.add_argument("--scan-seconds", type=float, default=3.0)
    command.add_argument("--timeout-s", type=float, default=DEFAULT_COMMAND_TIMEOUT,
                         help="seconds to wait for the sensor's reply")
    command.add_argument("--host-clock", action="store_true",
                         help="report the host's round trip instead of the dongle's")
    command.set_defaults(handler=_cmd_cmd)

    script = subparsers.add_parser(
        "script",
        help="run a command document: connect, send commands, check replies",
        description="Run a markdown command document against a sensor. Exit status "
        "0 when every checked step passed, 1 when one failed or the run could not "
        "start. See specs/templates/ble_sensor_test.md.",
    )
    script.add_argument("document", help="the markdown command document")
    script.add_argument("--var", action="append", metavar="NAME=VALUE",
                        help="value for a ${NAME} the document declares; repeatable")
    script.add_argument("--report", metavar="PATH", help="write the markdown report here")
    script.add_argument("--events", metavar="PATH",
                        help="write the event log here: time, event, step, data, result")
    script.add_argument("--timeout-s", type=float, default=DEFAULT_COMMAND_TIMEOUT,
                        help="default seconds to wait for a reply; a step's Timeout "
                        "cell, then the document's timeout for its command prefix, "
                        "override it")
    script.add_argument("--timeout", action="append", dest="prefix_timeouts",
                        metavar="PREFIX=MS",
                        help="timeout in milliseconds for commands starting with "
                        "PREFIX (any case), over the document's Command prefix "
                        "table; repeatable")
    script.add_argument("--listen", type=float, default=0.5,
                        help="seconds to listen after a command with no expected reply")
    script.set_defaults(handler=_cmd_script)

    monitor = subparsers.add_parser("monitor", help="stream events to the terminal and the log")
    monitor.add_argument("--duration", type=float, default=10.0, help="seconds to listen")
    monitor_target = monitor.add_mutually_exclusive_group()
    monitor_target.add_argument("--addr", help="report only this address")
    monitor_target.add_argument(
        "--select",
        help="scan for this name and follow it; part of a name, any case, "
             "chooses the strongest match")
    monitor.add_argument("--scan-seconds", type=float, default=3.0)
    monitor.set_defaults(handler=_cmd_monitor)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools ble``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        dongle = NordicDongle.connect(
            args.resource,
            baudrate=args.baud,
            timeout=args.timeout,
            log_path=args.log,
            firmware=args.firmware,
            # The firmware sub-command must be able to reach a dongle running
            # something incompatible: that is the one it is there to fix.
            update_firmware=(args.command == "firmware" and getattr(args, "update", False)),
        )
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(dongle, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        dongle.close()
