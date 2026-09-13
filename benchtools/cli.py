"""Top-level command line: ``benchtools <command> ...``.

Dispatches to a per-tool command line rather than nesting argparse parsers, so
each tool keeps its own complete ``--help`` and can be run directly.

Traces to: RUN-FR-050, SCOPE-FR-100.
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from . import __version__

__all__ = ["main"]

_USAGE = """\
usage: benchtools <command> [options]

Bench test tooling: instrument drivers, analysis and a declarative test runner.

Commands:
  run         run bench test specifications against a bench
  scope       control a Tektronix TDS3014B oscilloscope
  drivers     list the instrument drivers a bench configuration can name
  backends    list the transport backends a resource string can select

Run 'benchtools <command> --help' for a command's own options.

Examples:
  benchtools scope -r sim:// idn
  benchtools run tests/clock_skew.yaml --simulate --markdown report.md
  benchtools run tests/*.yaml --bench benches/lab1.yaml --junit results.xml

No VISA installation is required: a bare IP address uses the built-in VXI-11
transport.
"""


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit status."""
    arguments = list(sys.argv[1:] if argv is None else argv)

    if not arguments or arguments[0] in ("-h", "--help", "help"):
        sys.stdout.write(_USAGE)
        return 0
    if arguments[0] in ("--version", "-V"):
        print("benchtools %s" % __version__)
        return 0

    command, rest = arguments[0], arguments[1:]

    if command == "run":
        from .runner.cli import main as runner_main

        return runner_main(rest)

    if command in ("scope", "tek3014b"):
        from .instruments.tek3014b.cli import main as scope_main

        return scope_main(rest)

    if command == "drivers":
        from .runner.bench import registered_drivers

        print("Instrument drivers a bench configuration can name:")
        for name in registered_drivers():
            print("  %s" % name)
        return 0

    if command == "backends":
        from .core.transport import registered_backends

        print("Transport backends a resource string can select:")
        for name in registered_backends():
            print("  %s" % name)
        return 0

    print("benchtools: unknown command %r\n" % command, file=sys.stderr)
    sys.stderr.write(_USAGE)
    return 2
