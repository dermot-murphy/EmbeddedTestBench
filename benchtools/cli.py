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
  jlink       control a target through a SEGGER J-Link debug probe
  ble         scan, drive and profile a BLE sensor through a Nordic dongle
  psu         control a GW Instek GPD-2303S bench power supply
  s2lp        drive an ST S2-LP sub-1 GHz development kit
  drivers     list the instrument drivers a bench configuration can name
  backends    list the transport backends a resource string can select

Run 'benchtools <command> --help' for a command's own options.

Examples:
  benchtools scope -r sim:// idn
  benchtools jlink -r sim:// -e build/app.elf time sensor.c:40 sensor.c:75
  benchtools ble -r sim:// profile --select SENS-01 --duration 30 --interval 0.1
  benchtools psu -r sim:// set 1 -V 3.3 -I 0.5 --on
  benchtools s2lp -r sim:// registers --plain
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

    if command in ("jlink", "segger", "probe"):
        from .instruments.jlink.cli import main as jlink_main

        return jlink_main(rest)

    if command in ("ble", "dongle", "nordic"):
        from .instruments.nordic_dongle.cli import main as ble_main

        return ble_main(rest)

    if command in ("psu", "gpd2303s", "supply"):
        from .instruments.gpd2303s.cli import main as psu_main

        return psu_main(rest)

    if command in ("s2lp", "s2-lp", "radio"):
        from .instruments.s2lp.cli import main as s2lp_main

        return s2lp_main(rest)

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
