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
from .constants import BOARDS, CRC_MODES, DEFAULT_BAUDRATE, MODEL, Modulation, Strobe
from .kepler import decode_kepler_frame
from .s2lp import S2lpDevkit
from .traffic import FRAME_REGISTERS

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
            "board": radio.board or None,
            "firmware": identity.firmware,
            "library": radio.library_version,
            "silicon_version": "0x%02X" % radio.silicon_version,
            "xtal_hz": radio.xtal_hz,
            "band_hz": list(radio.band) if radio.band else None,
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


def _cmd_config(radio: S2lpDevkit, args) -> int:
    """Apply, verify or capture a register file."""
    if args.save:
        path = radio.save_configuration(args.save, only_changed=not args.all)
        _emit({"saved": path, "registers": len(open(path, encoding="utf-8").read().splitlines())},
              args.json)
        return _EXIT_OK

    configuration = radio.load_configuration(args.file)
    if args.apply:
        check = radio.apply_configuration(configuration, reset=args.reset)
    else:
        check = radio.verify_configuration(configuration, strict=args.strict)

    payload = check.as_dict()
    payload["applied"] = bool(args.apply)
    payload["reset"] = args.reset if args.apply else "none"
    payload["settings"] = [setting.as_dict() for setting in configuration]
    if not check.matches:
        payload["warning"] = (
            "the radio is not in the configuration %s describes, so any "
            "measurement taken now is of a radio set up differently from the "
            "one the test specifies." % configuration.source
        )
    _emit(payload, args.json)
    return _EXIT_OK if check.matches else _EXIT_ERROR


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
            "the radio was re-armed %d time(s) during this capture, by the %s, "
            "and heard nothing while being re-armed. Absence of a packet here "
            "is not evidence it was not transmitted." % (capture.gaps, capture.rearm)
        )
    _emit(payload, args.json)
    return _EXIT_OK if capture.count else _EXIT_ERROR


def _cmd_packets(radio: S2lpDevkit, args) -> int:
    """Show the packet handler's setup, or set it."""
    if args.sync is not None or args.crc or args.variable or args.preamble:
        info = radio.configure_packets(
            preamble=args.preamble or 64, sync_bits=args.sync_bits,
            sync_word=int(args.sync, 0) if args.sync else 0x88888888,
            variable_length=args.variable, crc=args.crc or "8")
    else:
        info = radio.packet_info()
    info["tx_source"] = radio.read_field("PCKTCTRL1", "TXSOURCE")
    _emit(info, args.json)
    return _EXIT_OK


def _cmd_stream(radio: S2lpDevkit, args) -> int:
    """Receive frames until stopped, one JSON line each, raw and decoded."""
    decoder = decode_kepler_frame if args.decode == "kepler" else None
    registers = tuple(args.registers.split(",")) if args.registers else FRAME_REGISTERS
    frames = rejected = undecoded = 0
    try:
        for packet in radio.stream(registers=registers, decoder=decoder,
                                   count=args.count, timeout=args.timeout):
            print(json.dumps(packet.as_dict(), sort_keys=True), flush=True)
            if not packet.ok:
                rejected += 1
            elif decoder is not None and packet.decoded is None:
                undecoded += 1
            frames += 1
    except KeyboardInterrupt:
        radio.stop()
    summary = {"frames": frames, "rejected": rejected, "undecoded": undecoded}
    print(json.dumps({"summary": summary}), file=sys.stderr)
    if args.json:
        _emit(summary, args.json)
    return _EXIT_OK if frames else _EXIT_ERROR


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
    parser.add_argument("--board", choices=sorted(BOARDS),
                        help="which kit board this is; the firmware does not say, "
                             "and without it only the synthesiser's range is checked")
    parser.add_argument("--timeout", type=float, default=5.0, help="reply timeout in seconds")
    parser.add_argument("--setup", metavar="REGS",
                        help="reset the radio to its register defaults and apply this "
                             "register file right after connecting, e.g. to "
                             "set up the packet handler before tx or rx")
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

    config = subparsers.add_parser(
        "config", help="apply, verify or capture a register file")
    config.add_argument("file", nargs="?", help="register file: names and hex values")
    config.add_argument("--apply", action="store_true",
                        help="write the values to the radio (default is to verify only)")
    config.add_argument("--reset", choices=S2lpDevkit.RESET_MODES, default="none",
                        help="applying: put the radio at its register defaults first. "
                             "'defaults' writes them; 'power' shuts the radio down and "
                             "back, a real power-on reset. The reset strobe does NOT "
                             "restore register defaults and is not offered here.")
    config.add_argument("--strict", action="store_true",
                        help="verifying: also require every register the file does "
                             "not name to be at its reset value")
    config.add_argument("--save", metavar="PATH",
                        help="instead, write the radio's current registers out as a file")
    config.add_argument("--all", action="store_true",
                        help="--save: include registers that are at their reset value")
    config.set_defaults(handler=_cmd_config)

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

    packets = subparsers.add_parser(
        "packets", help="show or set the basic packet handler (and TX source)")
    packets.add_argument("--preamble", type=int, help="PREAMBLE_LEN value (default 64)")
    packets.add_argument("--sync", metavar="WORD", help="sync word, e.g. 0xB19C0CA7")
    packets.add_argument("--sync-bits", type=int, default=32, help="sync length in bits")
    packets.add_argument("--variable", action="store_true", help="variable length (a length byte)")
    packets.add_argument("--crc", choices=sorted(CRC_MODES), help="CRC mode")
    packets.set_defaults(handler=_cmd_packets)

    stream = subparsers.add_parser(
        "stream", help="receive frames until stopped: one JSON line each, with registers")
    stream.add_argument("--count", type=int, help="stop after this many frames")
    stream.add_argument("--timeout", type=float, help="stop after this many seconds")
    stream.add_argument("--registers", metavar="NAMES",
                        help="comma-separated registers to read after each frame "
                             "(default %s)" % ",".join(FRAME_REGISTERS))
    stream.add_argument("--decode", choices=["kepler"], help="decode each payload")
    stream.set_defaults(handler=_cmd_stream)

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
            board=args.board or "",
            log_path=args.log,
            packet_log=args.packet_log,
        )
    except BenchToolsError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        if args.setup:
            radio.apply_configuration(args.setup, reset="defaults")
        return args.handler(radio, args)
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        radio.close()
