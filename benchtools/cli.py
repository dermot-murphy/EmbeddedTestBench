"""Top-level command line: ``benchtools <command> ...``.

Dispatches to a per-tool command line rather than nesting argparse parsers, so
each tool keeps its own complete ``--help`` and can be run directly.

Traces to: RUN-FR-050, SCOPE-FR-100.
"""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Optional, Sequence

from . import __version__

__all__ = ["main"]

_USAGE = """\
usage: benchtools <command> [options]

Bench test tooling: instrument drivers, analysis and a declarative test runner.

Commands:
  run         run bench test specifications against a bench
  view        watch and control test runs in a browser (127.0.0.1 only)
  scope       control a Tektronix TDS3014B oscilloscope
  jlink       control a target through a SEGGER J-Link debug probe
  ble         scan, drive and profile a BLE sensor through a Nordic dongle
  psu         control a GW Instek GPD-3303D bench power supply
  s2lp        drive an ST S2-LP sub-1 GHz development kit
  thermo      read a Pico 2 + SHT30-D thermometer: identity and temperature
  drivers     list the instrument drivers a bench configuration can name
  backends    list the transport backends a resource string can select

Run 'benchtools <command> --help' for a command's own options.

Examples:
  benchtools scope -r sim:// idn
  benchtools jlink -r sim:// -e build/app.elf time sensor.c:40 sensor.c:75
  benchtools ble -r sim:// profile --select SENS-0A1B2C --duration 30 --interval 0.1
  benchtools psu -r sim:// set 1 -V 3.3 -I 0.5 --on
  benchtools s2lp -r sim:// registers --plain
  benchtools thermo -r /dev/ttyACM0 temp --count 10 --interval 1
  benchtools run tests/clock_skew.yaml --simulate --markdown report.md
  benchtools run tests/*.yaml --bench benches/lab1.yaml --junit results.xml

No VISA installation is required: a bare IP address uses the built-in VXI-11
transport.
"""


#: Command aliases to the module holding that tool's ``main``.
#:
#: A table rather than a chain of ``if`` statements, for the same reason the
#: transport backends and the instrument drivers are registries: adding a tool
#: should be a new row, not a new branch in a function that grows without
#: limit. The import stays inside :func:`main` so that running one tool does
#: not import the others.
_TOOLS = {
    ("run",): "benchtools.runner.cli",
    ("view", "viewer"): "benchtools.viewer.server",
    ("scope", "tek3014b"): "benchtools.instruments.tek3014b.cli",
    ("jlink", "segger", "probe"): "benchtools.instruments.jlink.cli",
    ("ble", "dongle", "nordic"): "benchtools.instruments.nordic_dongle.cli",
    ("psu", "gpd3303d", "supply"): "benchtools.instruments.gpd3303d.cli",
    ("dmm", "tti1604", "multimeter"): "benchtools.instruments.tti1604.cli",
    ("s2lp", "s2-lp", "radio"): "benchtools.instruments.s2lp.cli",
}


def _tool_for(command: str) -> Optional[str]:
    """The module implementing *command*, or ``None``."""
    for aliases, module in _TOOLS.items():
        if command in aliases:
            return module
    return None


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

    module = _tool_for(command)
    if module is not None:
        return import_module(module).main(rest)

    if command in ("thermo", "pico-sht30", "sht30"):
        from .instruments.pico_sht30.cli import main as thermo_main

        return thermo_main(rest)

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
