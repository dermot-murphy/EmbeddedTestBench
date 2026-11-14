"""J-Link Commander, simulated: command files run against the simulated target.

The ``segger`` backend (#71) is verifiable without a probe because this runs
the very command files the backend writes for ``JLink.exe``, against the same
:class:`~benchtools.instruments.jlink.simulator.SimulatedJLink` target the
``gdb`` backend's simulated GDB talks to. Memory, flash, the halted state and
RTT are that model's; nothing is kept twice.

Output lines are the J-Link V9.42 binary's own message texts (read from its
strings on 2026-11-13), so the backend's output checks are exercised against
the words a real run would print. ``savebin`` writes a real file, which the
backend reads back as it would from the real tool.

Traces to: JLINK-FR-091, JLINK-DD-SIMCOMMANDER.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .commander import JLinkCommander, check_output
from .image import ImageRange, read_image

__all__ = ["SimulatedCommander"]

#: Below this address the default simulated part has flash; above it, RAM.
_RAM_START = 0x20000000

#: DHCSR, and what 5C1712 read in it halted and running.
_DHCSR = 0xE000EDF0
_DHCSR_HALTED = 0x00030003
_DHCSR_RUNNING = 0x00050001

#: Commands that need no connection, and those that need the probe but not
#: the target.
_NO_CONNECTION = ("exitonerror", "eoe", "q", "qc", "quit", "exit", "sleep")
_PROBE_ONLY = ("f",)


class SimulatedCommander(JLinkCommander):
    """Runs command files against a simulated target instead of a probe.

    Everything above :meth:`run` - the command files the probe builds, the
    files ``savebin`` writes and the probe reads back, the output checks - is
    the same code as for a real probe.

    :param simulator: The simulated probe and target.
    """

    NAME = "simulated J-Link Commander"

    def __init__(self, simulator, timeout: float = 60.0) -> None:
        super().__init__(device="simulated", timeout=timeout)
        self.simulator = simulator
        #: Every command file run, as its list of lines. Tests assert on it.
        self.log: List[List[str]] = []
        #: Whether ending a run lets a halted core go. True, because on 5C1712
        #: on 2026-10-05 ending a Commander session resumed a halted core
        #: (JLink_Integration_Notes §4.3). Seen once; not verified for a halt
        #: Commander itself made.
        self.exit_resumes = True
        #: False makes ``erase`` report success and erase nothing, as
        #: ``monitor flash erase`` did on a running nRF52840 (#69), so the
        #: backend's blank check can be shown to catch it.
        self.erase_works = True
        #: Each command's handler, by lower-case name; a test may replace one.
        self.handlers: Dict[str, Callable[[str, List[str], List[str]], bool]] = {}
        for names, handler in (
            (_NO_CONNECTION, self._quiet),
            (("f",), self._firmware),
            (("h", "halt"), self._halt),
            (("g", "go"), self._go),
            (("r", "reset"), self._reset),
            (("erase",), self._erase),
            (("loadfile",), self._loadfile),
            (("savebin",), self._savebin),
            (("w1", "w4"), self._write),
        ):
            for name in names:
                self.handlers[name] = handler

    # ------------------------------------------------------------------
    def check(self) -> None:
        """Nothing to find: the simulator is the tool."""

    def run(self, commands: Sequence[str], what: str, timeout: Optional[float] = None) -> str:
        script = ["exitonerror 1"] + list(commands) + ["q"]
        self._logger.info("%s: %s", what, "; ".join(script))
        returncode, output = self.execute(script)
        check_output(output, returncode, what)
        return output

    def image(self, path: str) -> List[ImageRange]:
        """The image's ranges, or the simulated firmware's when no such file
        exists: the simulator needs no image on disk, as for ``gdb``."""
        if os.path.isfile(path):
            return read_image(path)
        return self.firmware_image()

    def firmware_image(self) -> List[ImageRange]:
        """The simulated firmware's flash sections, filled with a pattern that
        differs from byte to byte, so a read-back that lost or moved a byte
        fails. RAM sections are left out: writing them would overwrite the
        model's variables, which the simulated GDB's ``load`` does not touch."""
        sections = sorted(self.simulator.firmware.sections.items(), key=lambda item: item[1][0])
        return [
            ImageRange(name, address, bytes((address + offset) & 0xFF for offset in range(size)))
            for name, (address, size) in sections if address < _RAM_START
        ]

    def execute(self, script: Sequence[str]) -> Tuple[int, str]:
        """Run *script* as ``JLink.exe`` would and return ``(status, output)``."""
        self.log.append(list(script))
        target = self.simulator
        out = [
            "SEGGER J-Link Commander V9.42 (Compiled May  6 2026 12:31:09)",
            "DLL version V9.42, compiled May  6 2026 12:30:32",
        ]
        # Commander V9.42 connects lazily, even with -AutoConnect 1: the first
        # command that needs the probe prints the probe notice and banner, and
        # the first that needs the target prints the target notice and
        # connects (5C1712, 2026-11-14, JLINK-OPEN-05). Neither notice is an
        # error.
        probe_connected = target_connected = False
        exit_on_error, status = False, 0
        for line in script:
            text = line.strip()
            lower = text.lower()
            out.append("J-Link>%s" % text)
            name = lower.split(" ", 1)[0]
            if name and name not in _NO_CONNECTION:
                if not probe_connected:
                    probe_connected = True
                    out.extend([
                        "J-Link connection not established yet but required for command.",
                        "Connecting to J-Link via USB...O.K.",
                        "Firmware: J-Link V11 compiled Jan  1 2026 00:00:00",
                        "Hardware version: V11.00",
                        "S/N: %s" % target.serial_number,
                        "VTref=3.300V",
                    ])
                if name not in _PROBE_ONLY and not target_connected:
                    out.append("Target connection not established yet but required for command.")
                    if not target.attached:
                        out.append("Error occurred: Could not connect to the target device.")
                        return 1, "\n".join(out)
                    target_connected = target.connected = True
            if not self._command(text, out):
                status = 1
                if exit_on_error:
                    break
            if lower.startswith(("exitonerror", "eoe")):
                exit_on_error = lower.split()[-1] == "1"
            if lower in ("q", "qc", "quit", "exit"):
                break
        if self.exit_resumes:
            target.halted = False
        out.append("Script processing completed.")
        return status, "\n".join(out)

    def _command(self, line: str, out: List[str]) -> bool:
        """Carry out one command; ``False`` on an error."""
        if not line:
            return True
        name, _, rest = line.partition(" ")
        arguments = [part.strip().strip('"') for part in rest.split(",")] if rest else []
        handler = self.handlers.get(name.lower())
        if handler is None:
            out.append("Unknown command. '?' for help.")
            return False
        return handler(name.lower(), arguments, out)

    # ------------------------------------------------------------------
    def _quiet(self, _name: str, _arguments: List[str], _out: List[str]) -> bool:
        return True

    def _firmware(self, _name: str, _arguments: List[str], out: List[str]) -> bool:
        out.extend(["Firmware: J-Link V11 compiled Jan  1 2026 00:00:00", "Hardware: V11.00"])
        return True

    def _halt(self, _name: str, _arguments: List[str], out: List[str]) -> bool:
        self.simulator.halted = True
        out.append("PC = %08X, CycleCnt = %08X"
                   % (self.simulator.program_counter, self.simulator.cycles))
        return True

    def _go(self, _name: str, _arguments: List[str], _out: List[str]) -> bool:
        self.simulator.halted = False
        return True

    def _reset(self, _name: str, _arguments: List[str], out: List[str]) -> bool:
        target = self.simulator
        target.flow_index = 0
        target.location = target.firmware.flow[0] if target.firmware.flow else "main"
        target.cycles = 0
        target.halted = True
        out.append("Reset delay: 0 ms")
        return True

    def _erase(self, _name: str, _arguments: List[str], out: List[str]) -> bool:
        out.append("'erase': Performing implicit reset & halt of MCU.")
        out.append("Erasing device...")
        if self.erase_works:
            # As the simulated GDB Server's "monitor flash erase": the flash
            # sections, and the vector table the default part aliases at 0.
            for address, size in self.simulator.firmware.sections.values():
                if address < _RAM_START:
                    self.simulator.write_memory(address, b"\xff" * size)
            self.simulator.write_memory(0, b"\xff" * 4)
            self.simulator.flashed = False
        out.append("Erasing done.")
        self.simulator.halted = True
        return True

    def _write(self, name: str, arguments: List[str], out: List[str]) -> bool:
        width = 1 if name == "w1" else 4
        try:
            address, value = int(arguments[0], 16), int(arguments[1], 16)
        except (IndexError, ValueError):
            out.append("Syntax: %s [<Zone>:]<Addr>, <Data> (hex)" % name.upper())
            return False
        masked = value & ((1 << (8 * width)) - 1)
        self.simulator.write_memory(address, masked.to_bytes(width, "little"))
        return True

    def _loadfile(self, _name: str, arguments: List[str], out: List[str]) -> bool:
        if not arguments or not arguments[0]:
            out.append("Syntax: loadfile <filename> [, <Addr>] [, <noreset | reset>]")
            return False
        path = arguments[0]
        out.append("'loadfile': Performing implicit reset & halt of MCU.")
        out.append("Downloading file [%s]..." % path)
        try:
            ranges = self.image(path)
        except ValueError:
            out.append("File is of unknown / unsupported format.")
            return False
        for item in ranges:
            data = bytearray(item.data)
            if not self.simulator.flash_matches and data:
                # A programming fault the tool's own check did not report: the
                # backend's read-back is what must catch it.
                data[0] ^= 0xFF
            self.simulator.write_memory(item.address, bytes(data))
        self.simulator.flashed = True
        self.simulator.halted = True
        out.append("O.K.")
        return True

    def _savebin(self, _name: str, arguments: List[str], out: List[str]) -> bool:
        try:
            path, address, count = arguments[0], int(arguments[1], 16), int(arguments[2], 16)
        except (IndexError, ValueError):
            out.append("Syntax: savebin <filename>, <addr>, <NumBytes> (hex)")
            return False
        out.append("Opening binary file for writing... [%s]" % path)
        out.append("Reading %u bytes from addr 0x%08X into file..." % (count, address))
        data = bytearray(self.simulator.read_memory(address, count))
        # DHCSR reports the model's halted state, with the values 5C1712 gave
        # (JLink_Integration_Notes §4.3): the part's answer to "is it halted".
        state = (_DHCSR_HALTED if self.simulator.halted else _DHCSR_RUNNING).to_bytes(4, "little")
        for index in range(4):
            if address <= _DHCSR + index < address + count:
                data[_DHCSR + index - address] = state[index]
        try:
            with open(path, "wb") as handle:
                handle.write(bytes(data))
        except OSError:
            out.append("Could not write to file.")
            return False
        out.append("O.K.")
        return True
