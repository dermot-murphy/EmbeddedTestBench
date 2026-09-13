"""Command line for the S2-LP development kit.

``benchtools s2lp --help``. Results are printed as JSON so the tool composes
into a larger harness, and ``--resource sim://`` runs every sub-command with no
kit attached.

Two logs, because they answer different questions. ``--log PATH`` records every
line in both directions, host-timestamped: that file is the evidence.
``--packet-log PATH`` records one JSON object per packet: that file is the data.

Traces to: S2LP-FR-060, S2LP-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError
from . import registers as reg
from .constants import DEFAULT_BAUDRATE, MODEL, Modulation, Strobe
from .s2lp import S2lpDevkit

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_ERROR = 1


def _emit(payload: dict, path: Optional[str]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _payload(text: str) -> bytes:
    """A payload from the command line: hex with ``0x``/``:``, else ASCII."""
    cleaned = text.strip()
    if cleaned.lower().startswith("0x"):
        return bytes.fromhex(cleaned[2:].replace(":", "").replace(" ", ""))
    return cleaned.encode("utf-8")


# ---------------------------------------------------------------------------
def _cmd_info(radio: S2lpDevkit, args) -> int:
    identity = radio.identify()
    _emit(
        {
            "identity": identity.raw,
            "manufacturer": identity.manufacturer,
            "board": radio.board,
            "firmware": identity.firmware,
            "xtal_hz": radio.xtal_hz,
            "band_hz": list(radio.band),
            "radio": radio.radio_info(),
            "log": radio.log_path,
            "packet_log": radio.packet_log_path,
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_registers(radio: S2lpDevkit, args) -> int:
    """Dump every register, or read or write one."""
    if args.write is not None:
        radio.write_register(args.register, int(args.write, 0))
    if args.register:
        entry = reg.lookup(args.register)
        value = radio.read_register(entry.address)
        _emit(
            {
                "name": entry.name,
                "address": "0x%02X" % entry.address,
                "value": "0x%02X" % value,
                "reset": "0x%02X" % entry.reset,
                "at_reset": value == entry.reset,
                "access": entry.access,
                "fields": {field.name: field.extract(value) for field in entry.fields},
                "line": entry.describe(value),
            },
            args.json,
        )
        return _EXIT_OK

    values = radio.read_all_registers()
    changed = radio.registers_differing_from_reset(values)
    payload = {
        "count": len(values),
        "dump": radio.dump_registers(values).splitlines(),
        "changed_from_reset": {
            name: {"reset": "0x%02X" % old, "value": "0x%02X" % new}
            for name, (old, new) in changed.items()
        },
    }
    if args.plain:
        print(radio.dump_registers(values))
        return _EXIT_OK
    _emit(payload, args.json)
    return _EXIT_OK


def _cmd_radio(radio: S2lpDevkit, args) -> int:
    if args.frequency or args.rate or args.modulation or args.deviation or args.bandwidth:
        info = radio.configure_radio(
            frequency_hz=int(args.frequency or radio.frequency_hz),
            data_rate_bps=int(args.rate or 38_400),
            modulation=args.modulation or Modulation.GFSK_2_BT1,
            deviation_hz=int(args.deviation or 20_000),
            bandwidth_hz=int(args.bandwidth or 100_000),
        )
    else:
        info = radio.radio_info()
    if args.power is not None:
        radio.set_power_dbm(args.power)
    info["power_dbm"] = radio.power_dbm
    info["rssi_dbm"] = radio.rssi_dbm
    _emit(info, args.json)
    return _EXIT_OK


def _cmd_tx(radio: S2lpDevkit, args) -> int:
    payload = _payload(args.data)
    if args.repeat > 1:
        packets = radio.transmit_batch(payload, count=args.repeat, interval_ms=args.interval)
    else:
        packets = [radio.transmit(payload)]
    _emit({"sent": len(packets), "packets": [p.as_dict() for p in packets]}, args.json)
    return _EXIT_OK


def _cmd_rx(radio: S2lpDevkit, args) -> int:
    packet = radio.receive(length=args.length, timeout=args.timeout)
    if packet is None:
        _emit(
            {
                "received": 0,
                "warning": "nothing arrived while the radio was listening. That "
                           "is not the same as the air being quiet: this "
                           "firmware receives when asked, and hears nothing "
                           "between one call and the next.",
            },
            args.json,
        )
        return _EXIT_ERROR
    _emit({"received": 1, "packet": packet.as_dict()}, args.json)
    return _EXIT_OK


def _cmd_capture(radio: S2lpDevkit, args) -> int:
    capture = radio.capture(
        count=args.count,
        timeout=args.timeout,
        length=args.length,
        continuous=not args.polled,
    )
    payload = capture.as_dict()
    payload["summary"] = capture.describe()
    if not capture.is_continuous:
        payload["warning"] = (
            "the radio was re-armed %d time(s) during this capture, and heard "
            "nothing in between. Absence of a packet here is not evidence it "
            "was not transmitted." % capture.gaps
        )
    _emit(payload, args.json)
    return _EXIT_OK if capture.count else _EXIT_ERROR


def _cmd_strobe(radio: S2lpDevkit, args) -> int:
    radio.strobe(args.name)
    _emit({"strobe": args.name, "sent": True}, args.json)
    return _EXIT_OK


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchtools s2lp",
        description="Drive an %s through ST's CLI firmware." % MODEL,
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="/dev/ttyACM0, COM7, serial://COM7 or sim:// (default)",
    )
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE,
                        help="line rate of ST's firmware (default %d)" % DEFAULT_BAUDRATE)
    parser.add_argument("--timeout", type=float, default=5.0, help="reply timeout in seconds")
    parser.add_argument("--log", metavar="PATH", help="raw session log: every line, both ways")
    parser.add_argument("--packet-log", metavar="PATH", help="structured packet log (JSON Lines)")
    parser.add_argument("--json", metavar="PATH", help="also write the JSON result here")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="-v for progress, -vv for every line")

    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="identify the board and read its radio settings")
    info.set_defaults(handler=_cmd_info)

    regs = subparsers.add_parser("registers", help="dump, read or write registers")
    regs.add_argument("register", nargs="?", help="name (PCKTCTRL3) or address (0x2E); omit for all")
    regs.add_argument("--write", metavar="VALUE", help="write this value to that register first")
    regs.add_argument("--plain", action="store_true", help="print the dump as text, not JSON")
    regs.set_defaults(handler=_cmd_registers)

    radio = subparsers.add_parser("radio", help="show or set the radio configuration")
    radio.add_argument("--frequency", type=int, help="carrier in Hz, e.g. 915000000")
    radio.add_argument("--rate", type=int, help="data rate in bps")
    radio.add_argument("--modulation", choices=sorted(Modulation.BY_NAME), help="modulation")
    radio.add_argument("--deviation", type=int, help="frequency deviation in Hz")
    radio.add_argument("--bandwidth", type=int, help="channel filter bandwidth in Hz")
    radio.add_argument("--power", type=float, help="output power in dBm")
    radio.set_defaults(handler=_cmd_radio)

    tx = subparsers.add_parser("tx", help="transmit a packet")
    tx.add_argument("data", help="payload: 0x-prefixed hex, or text")
    tx.add_argument("--repeat", type=int, default=1, help="send it this many times")
    tx.add_argument("--interval", type=int, default=100, help="ms between repeats (on the board)")
    tx.set_defaults(handler=_cmd_tx)

    rx = subparsers.add_parser("rx", help="receive one packet")
    rx.add_argument("--length", type=int, help="payload length to expect")
    rx.add_argument("--timeout", type=float, default=5.0, help="seconds to wait")
    rx.set_defaults(handler=_cmd_rx)

    capture = subparsers.add_parser("capture", help="receive packets and log them")
    capture.add_argument("--count", type=int, default=10, help="packets to capture")
    capture.add_argument("--timeout", type=float, default=30.0, help="seconds to capture for")
    capture.add_argument("--length", type=int, help="payload length to expect")
    capture.add_argument("--polled", action="store_true",
                         help="re-arm per packet instead of one board-side loop "
                              "(leaves gaps in which nothing is heard)")
    capture.set_defaults(handler=_cmd_capture)

    strobe = subparsers.add_parser("strobe", help="send a command strobe")
    strobe.add_argument("name", choices=sorted(Strobe.BY_NAME))
    strobe.set_defaults(handler=_cmd_strobe)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools s2lp``. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        radio = S2lpDevkit.connect(
            args.resource,
            baudrate=args.baudrate,
            timeout=args.timeout,
            log_path=args.log,
            packet_log=args.packet_log,
        )
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(radio, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        radio.close()
