"""Command line for the J-Link probe.

``benchtools jlink --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
hardware.

Traces to: JLINK-FR-100, JLINK-DD-CLI.
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
from .constants import DebugInterface, TimingMethod
from .probe import JLinkProbe

__all__ = ["main", "build_parser"]

_LOG = logging.getLogger("benchtools.jlink")

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_USAGE = 2


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _number(text: str) -> int:
    """Parse a decimal or 0x-prefixed integer."""
    return int(text, 0)


# ---------------------------------------------------------------------------
def _cmd_info(probe: JLinkProbe, args) -> int:
    identity = probe.identify()
    _emit(
        {
            "identity": identity.raw,
            "manufacturer": identity.manufacturer,
            "model": identity.model,
            "serial_number": identity.serial_number,
            "firmware": identity.firmware,
            "attached": probe.is_attached,
            "halted": probe.is_halted,
            "elf": probe.elf_path,
            "core_clock_hz": probe.core_clock_hz,
            "program_counter": "0x%08x" % probe.program_counter(),
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_flash(probe: JLinkProbe, args) -> int:
    result = probe.flash(args.image, verify=not args.no_verify, reset=not args.no_reset)
    _emit(result.as_dict(), args.json)
    return _EXIT_OK


def _cmd_verify(probe: JLinkProbe, args) -> int:
    result = probe.verify(args.image)
    _emit(result.as_dict(), args.json)
    return _EXIT_OK if result.matched else _EXIT_ERROR


def _cmd_reset(probe: JLinkProbe, args) -> int:
    probe.reset(halt=not args.run)
    _emit({"reset": True, "halted": probe.is_halted}, args.json)
    return _EXIT_OK


def _cmd_run(probe: JLinkProbe, args) -> int:
    if args.until:
        info = probe.run_to(args.until, timeout=args.timeout)
        _emit(
            {
                "reason": info.reason.value, "location": info.location,
                "function": info.function, "address": "0x%08x" % info.address,
            },
            args.json,
        )
        return _EXIT_OK
    probe.run()
    _emit({"running": True}, args.json)
    return _EXIT_OK


def _cmd_halt(probe: JLinkProbe, args) -> int:
    info = probe.halt()
    _emit(
        {
            "reason": info.reason.value, "location": info.location,
            "function": info.function, "address": "0x%08x" % info.address,
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_read(probe: JLinkProbe, args) -> int:
    data = probe.read_memory(args.address, args.size)
    rows = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        rows.append(
            "0x%08x  %-47s  %s"
            % (
                args.address + offset,
                " ".join("%02x" % byte for byte in chunk),
                "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk),
            )
        )
    _emit(
        {
            "address": "0x%08x" % args.address, "size": len(data),
            "hex": data.hex(), "dump": rows,
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_write(probe: JLinkProbe, args) -> int:
    data = bytes.fromhex(args.data.replace(" ", ""))
    probe.write_memory(args.address, data)
    _emit({"address": "0x%08x" % args.address, "written": len(data)}, args.json)
    return _EXIT_OK


def _cmd_var(probe: JLinkProbe, args) -> int:
    if args.set is not None:
        try:
            value = _number(args.set)
        except ValueError:
            value = args.set
        probe.write_variable(args.name, value)
    payload = {
        "name": args.name,
        "value": probe.read_variable(args.name),
        "address": "0x%08x" % probe.variable_address(args.name),
        "size": probe.variable_size(args.name),
    }
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_stack(probe: JLinkProbe, args) -> int:
    frames = probe.call_stack(limit=args.limit)
    _emit(
        {
            "depth": len(frames),
            "frames": [
                {
                    "level": frame.level, "function": frame.function,
                    "file": frame.file, "line": frame.line,
                    "address": "0x%08x" % frame.address,
                }
                for frame in frames
            ],
            "backtrace": [str(frame) for frame in frames],
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_rtt(probe: JLinkProbe, args) -> int:
    probe.rtt_start(log_path=args.log)
    try:
        if args.send:
            probe.rtt_write(args.send)
        if args.expect:
            match = probe.rtt_expect(args.expect, timeout=args.duration)
            _emit(
                {
                    "matched": match.group(0), "groups": list(match.groups()),
                    "log": probe.rtt_log, "log_path": args.log,
                },
                args.json,
            )
            return _EXIT_OK
        probe.run()
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            for line in probe.rtt_read_lines():
                print(line, file=sys.stderr)
            time.sleep(0.05)
        _emit({"lines": probe.rtt_log, "log_path": args.log}, args.json)
        return _EXIT_OK
    finally:
        probe.rtt_stop()


def _cmd_time(probe: JLinkProbe, args) -> int:
    result = probe.measure_time_between(
        args.start,
        args.end,
        method=args.method,
        repeat=args.repeat,
        timer_variable=args.timer_variable,
        timer_hz=args.timer_hz,
        start_variable=args.start_variable,
        end_variable=args.end_variable,
        itm_port=args.itm_port,
    )
    payload = result.as_dict()
    if not result.is_trustworthy:
        payload["warning"] = (
            "the interval is close to this method's resolution (%.1e s); "
            "use a cycle-counting method instead of tightening the limit"
            % (result.resolution_seconds or 0.0)
        )
    _emit(payload, args.json)
    return _EXIT_OK


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for ``benchtools jlink``."""
    parser = argparse.ArgumentParser(
        prog="benchtools jlink",
        description=(
            "Control a target through a SEGGER J-Link: flash, verify, run, halt, "
            "breakpoints, memory, variables, call stack, RTT and timing."
        ),
        epilog="Use --resource sim:// to run against the built-in simulator.",
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="sim:// for the simulator, or jlink://[host][:port] for a probe "
             "(a remote host attaches to a GDB Server already running there) "
             "(default: %(default)s)",
    )
    parser.add_argument("-d", "--device", help="target device name, e.g. nRF52840_xxAA")
    parser.add_argument("-e", "--elf", help="ELF file providing symbols")
    parser.add_argument("--interface", default="SWD", choices=[m.value for m in DebugInterface])
    parser.add_argument("--speed", type=int, default=4000, help="interface speed in kHz (0 = adaptive)")
    parser.add_argument("--serial", help="probe serial number, to pick one of several")
    parser.add_argument("--core-clock", type=float, help="core clock in Hz, for cycle-to-time conversion")
    parser.add_argument("--gdb", help="path to arm-none-eabi-gdb")
    parser.add_argument("--server", help="path to the J-Link GDB Server")
    parser.add_argument("-t", "--timeout", type=float, default=30.0, help="I/O timeout in seconds")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="repeat for debug")
    parser.add_argument("--json", metavar="PATH", help="also write the result as JSON to PATH")

    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="identify the probe and report target state")
    info.set_defaults(handler=_cmd_info)

    flash = subparsers.add_parser("flash", help="program an image and verify it")
    flash.add_argument("image", nargs="?", help="image to flash; the --elf file when omitted")
    flash.add_argument("--no-verify", action="store_true", help="skip verification (not advised)")
    flash.add_argument("--no-reset", action="store_true", help="do not reset before programming")
    flash.set_defaults(handler=_cmd_flash)

    verify = subparsers.add_parser("verify", help="compare the target against an image")
    verify.add_argument("image", nargs="?", help="image to compare; the --elf file when omitted")
    verify.set_defaults(handler=_cmd_verify)

    reset = subparsers.add_parser("reset", help="reset the target")
    reset.add_argument("--run", action="store_true", help="let it run instead of halting")
    reset.set_defaults(handler=_cmd_reset)

    run = subparsers.add_parser("run", help="let the target run, optionally to a location")
    run.add_argument("--until", metavar="LOCATION", help="run to here, e.g. main.c:42")
    run.set_defaults(handler=_cmd_run)

    halt = subparsers.add_parser("halt", help="halt the target")
    halt.set_defaults(handler=_cmd_halt)

    read = subparsers.add_parser("read", help="read target memory")
    read.add_argument("address", type=_number, help="address, decimal or 0x-prefixed")
    read.add_argument("size", type=_number, help="number of bytes")
    read.set_defaults(handler=_cmd_read)

    write = subparsers.add_parser("write", help="write target memory")
    write.add_argument("address", type=_number)
    write.add_argument("data", help="hex bytes, e.g. deadbeef")
    write.set_defaults(handler=_cmd_write)

    var = subparsers.add_parser("var", help="read or write a variable by name")
    var.add_argument("name")
    var.add_argument("--set", metavar="VALUE", help="write this value first")
    var.set_defaults(handler=_cmd_var)

    stack = subparsers.add_parser("stack", help="read the call stack")
    stack.add_argument("--limit", type=int, help="deepest frame to report")
    stack.set_defaults(handler=_cmd_stack)

    rtt = subparsers.add_parser("rtt", help="read, write and log RTT")
    rtt.add_argument("--log", metavar="PATH", help="write every byte received to this file")
    rtt.add_argument("--send", metavar="TEXT", help="send this line to the target first")
    rtt.add_argument("--expect", metavar="REGEX", help="wait for a line matching this")
    rtt.add_argument("--duration", type=float, default=5.0, help="seconds to collect or wait")
    rtt.set_defaults(handler=_cmd_rtt)

    timing = subparsers.add_parser("time", help="measure the interval between two code locations")
    timing.add_argument("start", help="start location, e.g. sensor.c:40")
    timing.add_argument("end", help="end location, e.g. sensor.c:75")
    timing.add_argument(
        "--method", default=TimingMethod.CYCLE_COUNTER, type=TimingMethod.coerce,
        help="CYCLE_COUNTER (default), HOST_CLOCK, SWO_ITM or TARGET_TIMER",
    )
    timing.add_argument("--repeat", type=int, default=1, help="measure this many times")
    timing.add_argument("--timer-variable", help="TARGET_TIMER: variable read at both points")
    timing.add_argument("--timer-hz", type=float, help="TARGET_TIMER: tick rate of that timer")
    timing.add_argument("--start-variable", help="TARGET_TIMER: variable holding the start time")
    timing.add_argument("--end-variable", help="TARGET_TIMER: variable holding the end time")
    timing.add_argument("--itm-port", type=int, default=1, help="SWO_ITM: stimulus port")
    timing.set_defaults(handler=_cmd_time)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools jlink``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        probe = JLinkProbe.connect(
            args.resource,
            device=args.device,
            elf=args.elf,
            interface=args.interface,
            speed_khz=args.speed,
            serial_number=args.serial,
            core_clock_hz=args.core_clock,
            gdb_executable=args.gdb,
            server_executable=args.server,
            timeout=args.timeout,
        )
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(probe, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        probe.close()
