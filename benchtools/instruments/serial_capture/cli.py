"""Command line for the serial capture instrument: ``benchtools serial``.

Each argument is one command of the command set (:mod:`.console`), run in
order, and its reply is printed. With no commands, commands are read from
standard input, one per line, until it ends: an interactive console.

If a capture is still running when the commands run out, the tool waits for
it to end and prints ``ROUTINE RESULTS CAPTURE``. Ctrl-C aborts it. So::

    benchtools serial -r COM5 "WR WINDOW 10000" "WR LINES ON" "ROUTINE START CAPTURE"

shows ten seconds of what the device on COM5 prints, as ``LINE <n> = <text>``,
then the result. The exit status is 1 if any reply was ``NACK``.

Traces to: SER-FR-012, SER-DD-CLI.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

from ... import __version__
from ...core.errors import BenchToolsError
from .capture import SerialCapture
from .constants import DEFAULT_BAUDRATE, DEFAULT_FORMAT, DEFAULT_TIMEOUT

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    """The argument parser for ``benchtools serial``."""
    parser = argparse.ArgumentParser(
        prog="benchtools serial",
        description="Capture the lines a device prints on its serial port. Each "
                    "argument is one command (RD, WR, ROUTINE); with none, commands "
                    "are read from standard input.",
    )
    parser.add_argument("--version", action="version", version="benchtools %s" % __version__)
    parser.add_argument("-r", "--resource", default="sim://",
                        help="serial port (/dev/ttyUSB0, COM5) or sim:// (default)")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE,
                        help="line rate (default %d)" % DEFAULT_BAUDRATE)
    parser.add_argument("--format", dest="char_format", default=DEFAULT_FORMAT,
                        help="character format (default %s)" % DEFAULT_FORMAT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="seconds to wait for the port beyond a capture window")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="log more; repeat for debug output")
    parser.add_argument("commands", nargs="*", metavar="COMMAND",
                        help='a command such as "RD COUNT"; quote each one')
    return parser


def _show(text: str) -> None:
    print(text, flush=True)


def _run(capture: SerialCapture, text: str) -> bool:
    # Holding the driver's output lock while the command runs and its reply
    # is printed puts the reply before the live lines that follow it: without
    # it, the first line of a capture can beat ROUTINE START CAPTURE's reply.
    with capture.output_lock:
        reply = capture.command(text)
        print(reply.text, flush=True)
    return reply.ok


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``benchtools serial``. Returns a process exit status."""
    args = build_parser().parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        capture = SerialCapture.connect(
            args.resource, baudrate=args.baudrate, timeout=args.timeout,
            char_format=args.char_format,
            on_line=_show,
        )
    except (BenchToolsError, ValueError) as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    ok = True
    try:
        commands = args.commands if args.commands else (
            line for line in sys.stdin if line.strip())
        for text in commands:
            ok = _run(capture, text) and ok
        if capture.running:
            try:
                capture.wait_capture()
            except KeyboardInterrupt:
                capture.abort_capture()
            ok = _run(capture, "ROUTINE RESULTS CAPTURE") and ok
        # A capture that ended before the commands did keeps its live lines;
        # close() shows the ones still queued before the port is closed.
    except KeyboardInterrupt:
        capture.abort_capture()
        ok = False
    except BenchToolsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    finally:
        capture.close()
    return _EXIT_OK if ok else _EXIT_ERROR
