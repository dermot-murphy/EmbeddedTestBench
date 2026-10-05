"""A behavioural model of a J-Link attached to a Cortex-M target.

Speaks GDB/MI, so the driver, the session layer and the MI parser are all
exercised without a probe, a target or a GDB installation. It is also what makes
the timing and RTT tests meaningful: execution is **deterministic**, so a test
can assert an exact cycle count rather than a tolerance.

The execution model is a straight line. :class:`SimulatedFirmware` declares an
ordered ``flow`` of source locations the program passes through, with a
cumulative cycle count at each. Resuming advances along that flow to the next
location that has a breakpoint on it, updating the program counter, the DWT cycle
counter, the call stack and any RTT output declared for that location. Two
breakpoints therefore have an exactly known cycle distance, which is what a
timing measurement should recover.

What is deliberately *not* modelled: instruction semantics. Nothing here
executes code. The model answers debugger questions consistently; it is not an
emulator, and a test that needs real instruction behaviour needs real hardware.

Traces to: JLINK-FR-090, JLINK-DD-SIM.
"""

from __future__ import annotations

import logging
import shlex
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

from .constants import DEMCR, DWT_CTRL, DWT_CYCCNT

__all__ = ["SimulatedSymbol", "SimulatedFirmware", "SimulatedJLink", "DEFAULT_FIRMWARE"]

_LOG = logging.getLogger(__name__)


@dataclass
class SimulatedSymbol:
    """A variable the simulated firmware exposes.

    :param address: Address in target memory.
    :param size: Size in bytes.
    :param value: Value reported by expression evaluation. An ``int`` is also
        written into simulated memory so a raw memory read agrees with it.
    :param type_name: C type name, as GDB would report.
    """

    address: int
    size: int = 4
    value: Any = 0
    type_name: str = "int"


@dataclass
class SimulatedFirmware:
    """The program the simulated target is running.

    :param flow: Ordered locations execution passes through. Repeat a location
        to model a loop.
    :param cycles_at: Cumulative DWT cycle count on reaching each location.
    :param symbols: Variables, by name.
    :param locations: Address of each named location.
    :param stacks: Call stack at a location, innermost frame first, as
        ``(function, file, line)`` tuples.
    :param rtt_at: RTT lines the target emits on reaching a location.
    :param rtt_responses: Reply the target sends for a line written to RTT.
    :param itm_at: ITM ``(channel, value)`` written on reaching a location,
        for the SWO timing method.
    :param sections: Flash sections as ``name -> (address, size)``.
    :param core_clock_hz: Core clock, used to convert cycles to seconds.
    :param memory: Bytes present in the part rather than in the program, by
        address - an identity record programmed at manufacture, for instance.
    """

    path: str = "firmware.elf"
    flow: List[str] = field(default_factory=list)
    cycles_at: Dict[str, int] = field(default_factory=dict)
    symbols: Dict[str, SimulatedSymbol] = field(default_factory=dict)
    locations: Dict[str, int] = field(default_factory=dict)
    stacks: Dict[str, List[Tuple[str, str, int]]] = field(default_factory=dict)
    rtt_at: Dict[str, List[str]] = field(default_factory=dict)
    rtt_responses: Dict[str, str] = field(default_factory=dict)
    itm_at: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    sections: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    core_clock_hz: float = 64.0e6
    #: Bytes in target memory that are not variables of the program: an
    #: identifier programmed into the part at manufacture, a lock byte, a
    #: calibration record. Address to the raw bytes at it - raw, because such a
    #: record has its own layout and byte order, and writing it as a word here
    #: would bake this model's guess about that into the fixture.
    memory: Dict[int, bytes] = field(default_factory=dict)

    def address_of(self, location: str) -> int:
        """Return the address of *location*, inventing a stable one if unknown."""
        if location in self.locations:
            return self.locations[location]
        # A stable synthetic address, so an unlisted location still behaves
        # consistently across calls rather than differing each time.
        return 0x08000000 + (abs(hash(location)) % 0x10000) * 2


#: Where the simulated part keeps its identity record: nRF52 UICR
#: ``CUSTOMER[0]``. A real part reads 0xFFFFFFFF here until someone programs it,
#: which is an invalid record by the rule below.
DEVICE_ID_ADDRESS = 0x10001080

#: The first byte of that record says whether the rest of it means anything:
#: **zero is valid**. A part that was never programmed reads 0xFF here, so the
#: unprogrammed case fails the same check as a corrupted one.
DEVICE_ID_VALID = 0x00
SIMULATED_DEVICE_ID_VALIDITY = DEVICE_ID_VALID

#: The three bytes after it are the identifier, most significant first - the
#: order they are printed in, and the order the board advertises them in. This
#: one renders as ``0A1B2C``, which is in the name of the device the simulated
#: dongle advertises, so a specification that reads the identifier off the part
#: and then goes looking for that board works end to end with no hardware.
SIMULATED_DEVICE_ID = 0x0A1B2C


def _default_firmware() -> SimulatedFirmware:
    """A small firmware exercising every feature the driver offers.

    Cycle counts are chosen so intervals are exact round numbers at 64 MHz:
    ``sensor_start`` to ``sensor_done`` is 64 000 cycles, i.e. exactly 1.000 ms.
    """
    return SimulatedFirmware(
        path="firmware.elf",
        flow=[
            "main.c:100",          # main entered
            "sensor.c:40",         # sensor_start
            "sensor.c:75",         # sensor_done
            "main.c:130",          # loop body
            "sensor.c:40",         # second iteration
            "sensor.c:75",
            "main.c:130",
        ],
        cycles_at={
            "main.c:100": 1_000,
            "sensor.c:40": 5_000,
            "sensor.c:75": 69_000,     # 64 000 cycles after sensor.c:40 => 1.000 ms
            "main.c:130": 70_000,
        },
        locations={
            "main": 0x08000400,
            "main.c:100": 0x08000400,
            "main.c:130": 0x08000460,
            "sensor_start": 0x08001200,
            "sensor.c:40": 0x08001200,
            "sensor_done": 0x080012C0,
            "sensor.c:75": 0x080012C0,
        },
        symbols={
            "sensor_count": SimulatedSymbol(0x20000100, 4, 7, "uint32_t"),
            "sensor_mv": SimulatedSymbol(0x20000104, 4, 1234, "uint32_t"),
            "device_state": SimulatedSymbol(0x20000108, 4, 2, "enum state_t"),
            "firmware_version": SimulatedSymbol(0x2000010C, 8, "1.4.2", "char [8]"),
            "timer_start": SimulatedSymbol(0x20000120, 4, 5_000, "uint32_t"),
            "timer_end": SimulatedSymbol(0x20000124, 4, 69_000, "uint32_t"),
        },
        stacks={
            "sensor.c:75": [
                ("sensor_done", "sensor.c", 75),
                ("sensor_read", "sensor.c", 120),
                ("main", "main.c", 130),
            ],
            "sensor.c:40": [
                ("sensor_start", "sensor.c", 40),
                ("main", "main.c", 100),
            ],
        },
        rtt_at={
            "sensor.c:40": ["sensor: start"],
            "sensor.c:75": ["sensor: done mv=1234", "sensor: count=7"],
            "main.c:130": ["main: loop"],
        },
        rtt_responses={
            "version": "1.4.2",
            "status": "ok",
            "reset": "resetting",
        },
        itm_at={
            "sensor.c:40": (1, 0xAA),
            "sensor.c:75": (1, 0xBB),
        },
        sections={
            ".text": (0x08000000, 0x4000),
            ".rodata": (0x08004000, 0x200),
            ".data": (0x20000000, 0x180),
        },
        memory={
            # The identity record: a validity byte, then three identifier bytes
            # in address order. It is not a variable of the program - it is
            # programmed once, at manufacture, and outlives any image flashed
            # over it, which is exactly why a test reads it to find out which
            # board it has.
            DEVICE_ID_ADDRESS: (
                bytes([SIMULATED_DEVICE_ID_VALIDITY])
                + SIMULATED_DEVICE_ID.to_bytes(3, "big")
            ),
        },
    )


#: The firmware used when a simulator is created without one.
DEFAULT_FIRMWARE = _default_firmware


class SimulatedJLink:
    """A J-Link and Cortex-M target answering GDB/MI.

    Satisfies :class:`~benchtools.core.simulator.Responder`, so it plugs into
    :class:`~benchtools.core.transport.mock.MockTransport` unchanged.

    :param firmware: The program to model; a default one is built when omitted.
    :param serial_number: Probe serial number reported by ``monitor``.
    :param flash_matches: Whether ``compare-sections`` reports every section as
        matched. Set ``False`` to exercise the verification-failure path.
    :param attached: Whether a target is present. ``False`` makes connection
        fail the way a disconnected probe does.
    """

    #: Identification the probe reports.
    DEFAULT_IDN = "SEGGER,J-Link V11,801012345,V7.94e"

    def __init__(
        self,
        firmware: Optional[SimulatedFirmware] = None,
        serial_number: str = "801012345",
        flash_matches: bool = True,
        attached: bool = True,
    ) -> None:
        self.firmware = firmware if firmware is not None else DEFAULT_FIRMWARE()
        self.serial_number = serial_number
        self.flash_matches = bool(flash_matches)
        self.attached = bool(attached)
        self.idn = self.DEFAULT_IDN
        #: Every MI command received, in order. Tests assert on this.
        self.command_log: List[str] = []
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Return the model to its state just after a reset-and-halt."""
        self.memory: Dict[int, int] = defaultdict(int)
        self.breakpoints: Dict[int, Dict[str, Any]] = {}
        self.watchpoints: Dict[int, Dict[str, Any]] = {}
        self._next_breakpoint = 1
        self.flow_index = 0
        self.location = self.firmware.flow[0] if self.firmware.flow else "main"
        self.cycles = 0
        self.halted = True
        self.connected = False
        self.symbols_loaded = False
        self.flashed = False
        self.rtt_started = False
        self.rtt_out: Deque[str] = deque()
        self.rtt_in: List[str] = []
        self.itm_events: List[Tuple[int, int, int]] = []
        self.monitor_log: List[str] = []
        #: The registers as GDB last read them, by register number, or ``None``
        #: when GDB would read them from the target. See :meth:`_gdb_registers`.
        self.register_cache: Optional[Dict[int, int]] = None
        self._load_symbol_values()
        self._load_preset_memory()

    def _load_preset_memory(self) -> None:
        """Write the firmware's preset words into memory.

        After the symbols, so a firmware that presets an address a variable also
        occupies gets the preset - the preset describes the part, the symbol
        describes the program, and the part wins.
        """
        for address, raw in self.firmware.memory.items():
            for offset, byte in enumerate(bytes(raw)):
                self.memory[address + offset] = byte

    def _load_symbol_values(self) -> None:
        """Write integer symbol values into memory so raw reads agree."""
        for symbol in self.firmware.symbols.values():
            if isinstance(symbol.value, int):
                self._write_int(symbol.address, symbol.value, symbol.size)

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    def _write_int(self, address: int, value: int, size: int = 4) -> None:
        raw = int(value) & ((1 << (8 * size)) - 1)
        for offset in range(size):
            self.memory[address + offset] = (raw >> (8 * offset)) & 0xFF

    def _read_int(self, address: int, size: int = 4) -> int:
        value = 0
        for offset in range(size):
            value |= self.memory[address + offset] << (8 * offset)
        return value

    def read_memory(self, address: int, count: int) -> bytes:
        """Read *count* bytes, honouring the DWT registers.

        ``DWT_CYCCNT`` returns the live cycle count, which is what makes the
        cycle-counter timing method testable end to end rather than only at the
        arithmetic level.
        """
        out = bytearray()
        for offset in range(count):
            location = address + offset
            base = location & ~0x3
            if base == DWT_CYCCNT:
                word = self.cycles & 0xFFFFFFFF
                out.append((word >> (8 * (location - base))) & 0xFF)
            else:
                out.append(self.memory[location])
        return bytes(out)

    def write_memory(self, address: int, data: bytes) -> None:
        """Write *data*, tracking the DWT enable bits as a real target would."""
        for offset, byte in enumerate(data):
            self.memory[address + offset] = byte
        base = address & ~0x3
        if base in (DEMCR, DWT_CTRL):
            self.monitor_log.append("trace register 0x%08X written" % base)
        if base == DWT_CYCCNT:
            self.cycles = self._read_int(DWT_CYCCNT, 4)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    @property
    def program_counter(self) -> int:
        """Current program counter."""
        return self.firmware.address_of(self.location)

    def _enter(self, location: str) -> None:
        """Arrive at *location*: update cycles, RTT and trace output."""
        self.location = location
        if location in self.firmware.cycles_at:
            self.cycles = self.firmware.cycles_at[location]
        for line in self.firmware.rtt_at.get(location, []):
            if self.rtt_started:
                self.rtt_out.append(line)
        if location in self.firmware.itm_at:
            channel, value = self.firmware.itm_at[location]
            self.itm_events.append((channel, value, self.cycles))

    def _breakpoint_locations(self) -> Dict[str, int]:
        return {
            entry["location"]: number
            for number, entry in self.breakpoints.items()
            if entry.get("enabled", True)
        }

    def resume(self) -> Dict[str, Any]:
        """Run to the next breakpoint and return the ``*stopped`` results."""
        self.halted = False
        targets = self._breakpoint_locations()
        flow = self.firmware.flow
        steps = 0
        index = self.flow_index
        while steps < len(flow) * 4:
            index = (index + 1) % len(flow) if flow else 0
            steps += 1
            location = flow[index] if flow else self.location
            self._enter(location)
            if location in targets:
                self.flow_index = index
                self.halted = True
                number = targets[location]
                temporary = self.breakpoints[number].get("temporary")
                if temporary:
                    self.breakpoints.pop(number, None)
                return {
                    "reason": "breakpoint-hit",
                    "disp": "del" if temporary else "keep",
                    "bkptno": str(number),
                    "frame": self._frame(),
                }
        # No breakpoint reachable: behave like a target that keeps running until
        # it is interrupted, which is what really happens.
        self.flow_index = index
        self.halted = False
        return {}

    def step(self) -> Dict[str, Any]:
        """Advance one location in the flow and report the stop."""
        flow = self.firmware.flow
        if flow:
            self.flow_index = (self.flow_index + 1) % len(flow)
            self._enter(flow[self.flow_index])
        self.halted = True
        return {"reason": "end-stepping-range", "frame": self._frame()}

    def interrupt(self) -> Dict[str, Any]:
        """Halt a running target."""
        self.halted = True
        return {"reason": "signal-received", "signal-name": "SIGINT", "frame": self._frame()}

    def _frame(self, level: int = 0) -> Dict[str, str]:
        stack = self.firmware.stacks.get(self.location)
        if stack and level < len(stack):
            function, filename, line = stack[level]
        else:
            function, filename, line = self._location_parts()
        return {
            "level": str(level),
            "addr": "0x%08x" % self.program_counter,
            "func": function,
            "file": filename,
            "fullname": "/project/%s" % filename,
            "line": str(line),
        }

    def _location_parts(self) -> Tuple[str, str, int]:
        if ":" in self.location:
            filename, _, line = self.location.rpartition(":")
            if line.isdigit():
                return filename.split(".")[0], filename, int(line)
        return self.location, "main.c", 1

    def call_stack(self) -> List[Dict[str, str]]:
        """Frames at the current location, innermost first."""
        stack = self.firmware.stacks.get(self.location)
        if not stack:
            return [self._frame(0)]
        return [self._frame(level) for level in range(len(stack))]

    # ------------------------------------------------------------------
    # RTT
    # ------------------------------------------------------------------
    def rtt_read(self) -> str:
        """Drain the RTT output buffer."""
        lines: List[str] = []
        while self.rtt_out:
            lines.append(self.rtt_out.popleft())
        return "".join(line + "\n" for line in lines)

    def rtt_write(self, text: str) -> None:
        """Accept RTT input, replying as the firmware would."""
        for line in text.replace("\r", "\n").split("\n"):
            line = line.strip()
            if not line:
                continue
            self.rtt_in.append(line)
            reply = self.firmware.rtt_responses.get(line)
            if reply is not None and self.rtt_started:
                self.rtt_out.append(reply)

    # ------------------------------------------------------------------
    # Expression evaluation
    # ------------------------------------------------------------------
    def evaluate(self, expression: str) -> str:
        """Evaluate a C expression the way GDB would, for the cases used here."""
        text = expression.strip()
        if text.startswith("&"):
            name = text[1:].strip()
            symbol = self.firmware.symbols.get(name)
            if symbol is None:
                raise KeyError(name)
            return "(%s *) 0x%08x" % (
                self.firmware.symbols[name].type_name.split("[")[0].strip(), symbol.address
            )
        if text.startswith("sizeof"):
            name = text[text.find("(") + 1 : text.rfind(")")].strip()
            symbol = self.firmware.symbols.get(name)
            if symbol is None:
                raise KeyError(name)
            return str(symbol.size)
        if text.startswith("$"):
            if text == "$pc":
                return "0x%08x" % self._gdb_registers()[15]
            raise KeyError(text)
        symbol = self.firmware.symbols.get(text)
        if symbol is None:
            raise KeyError(text)
        if isinstance(symbol.value, int):
            stored = self._read_int(symbol.address, symbol.size)
            return str(stored)
        return '"%s"' % symbol.value

    def set_variable(self, name: str, value: Any) -> None:
        """Write a variable, keeping memory and the model in step."""
        symbol = self.firmware.symbols.get(name)
        if symbol is None:
            raise KeyError(name)
        symbol.value = value
        if isinstance(value, int):
            self._write_int(symbol.address, value, symbol.size)

    # ------------------------------------------------------------------
    # GDB/MI protocol adapter
    # ------------------------------------------------------------------
    #: Register names reported, in GDB's Cortex-M order.
    REGISTER_NAMES = [
        "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
        "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc", "xpsr",
    ]

    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one MI command, as :class:`~benchtools.core.simulator.Responder`.

        Every reply ends with the ``(gdb)`` prompt, as GDB's does. A command that
        resumes the target emits ``^running`` then, after the prompt, the
        ``*stopped`` notification - the same ordering as the real thing, so the
        session's asynchronous handling is genuinely exercised.
        """
        text = message.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        # Strip the MI token, echoing it back on the result as GDB does.
        index = 0
        while index < len(text) and text[index].isdigit():
            index += 1
        token, command = text[:index], text[index:]
        self.command_log.append(command)
        lines = self._dispatch(command.strip(), token)
        return ("\n".join(lines) + "\n").encode("utf-8")

    # ------------------------------------------------------------------
    def _dispatch(self, command: str, token: str) -> List[str]:
        verb, _, argument = command.partition(" ")
        argument = argument.strip()
        handler = {
            "-gdb-exit": self._mi_exit,
            "-gdb-set": self._mi_done,
            "-gdb-show": self._mi_done,
            "-enable-pretty-printing": self._mi_done,
            "-file-exec-and-symbols": self._mi_file,
            "-target-select": self._mi_target_select,
            "-target-detach": self._mi_detach,
            "-break-insert": self._mi_break_insert,
            "-break-delete": self._mi_break_delete,
            "-break-list": self._mi_break_list,
            "-break-watch": self._mi_break_watch,
            "-exec-continue": self._mi_continue,
            "-exec-interrupt": self._mi_interrupt,
            "-exec-step": self._mi_step,
            "-exec-next": self._mi_step,
            "-exec-step-instruction": self._mi_step,
            "-data-read-memory-bytes": self._mi_read_memory,
            "-data-write-memory-bytes": self._mi_write_memory,
            "-data-evaluate-expression": self._mi_evaluate,
            "-stack-list-frames": self._mi_stack,
            "-data-list-register-names": self._mi_register_names,
            "-data-list-register-values": self._mi_register_values,
            "-interpreter-exec": self._mi_interpreter_exec,
        }.get(verb)
        if handler is None:
            return self._error(token, 'Undefined MI command: "%s"' % verb.lstrip("-"))
        return handler(argument, token)

    # -- helpers --------------------------------------------------------
    @staticmethod
    def _quote(text: str) -> str:
        """Escape a value as an MI C-string body."""
        return (
            str(text)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

    def _ok(self, token: str, results: str = "") -> List[str]:
        return ["%s^done%s" % (token, ("," + results) if results else ""), "(gdb)"]

    def _error(self, token: str, message: str) -> List[str]:
        return ['%s^error,msg="%s"' % (token, self._quote(message)), "(gdb)"]

    def _mi_done(self, _argument: str, token: str) -> List[str]:
        return self._ok(token)

    def _mi_exit(self, _argument: str, token: str) -> List[str]:
        return ["%s^exit" % token]

    def _stopped_lines(self, results: Dict[str, Any]) -> List[str]:
        if not results:
            return []
        return ["*stopped," + self._results_to_mi(results), "(gdb)"]

    def _results_to_mi(self, results: Dict[str, Any]) -> str:
        parts = []
        for name, value in results.items():
            parts.append("%s=%s" % (name, self._value_to_mi(value)))
        return ",".join(parts)

    def _value_to_mi(self, value: Any) -> str:
        if isinstance(value, dict):
            return "{%s}" % self._results_to_mi(value)
        if isinstance(value, (list, tuple)):
            return "[%s]" % ",".join(self._value_to_mi(item) for item in value)
        return '"%s"' % self._quote(value)

    # -- connection -----------------------------------------------------
    def _mi_file(self, argument: str, token: str) -> List[str]:
        self.firmware.path = argument.strip('"')
        self.symbols_loaded = True
        return self._ok(token)

    def _mi_target_select(self, argument: str, token: str) -> List[str]:
        if not self.attached:
            return self._error(
                token,
                "Remote communication error. Target disconnected.: "
                "No target connected to the J-Link.",
            )
        self.connected = True
        self._registers_seen_by_gdb()
        return ["%s^connected" % token, "(gdb)"]

    def _mi_detach(self, _argument: str, token: str) -> List[str]:
        self.connected = False
        self._registers_forgotten_by_gdb()
        return self._ok(token)

    # -- breakpoints ----------------------------------------------------
    def _mi_break_insert(self, argument: str, token: str) -> List[str]:
        # shlex, not split(): a condition is a quoted expression that contains
        # spaces, and splitting on whitespace truncates it to its first word.
        try:
            tokens = shlex.split(argument)
        except ValueError:
            return self._error(token, "Unbalanced quotes in breakpoint arguments.")
        temporary = "-t" in tokens
        hardware = "-h" in tokens
        condition = ""
        if "-c" in tokens:
            position = tokens.index("-c")
            condition = tokens[position + 1] if position + 1 < len(tokens) else ""
            del tokens[position : position + 2]
        location = " ".join(item for item in tokens if not item.startswith("-")).strip()
        if not location:
            return self._error(token, "No default breakpoint address now.")
        if hardware and sum(
            1 for entry in self.breakpoints.values() if entry.get("hardware")
        ) >= 4:
            return self._error(token, "Cannot insert hardware breakpoint: no comparator free.")

        number = self._next_breakpoint
        self._next_breakpoint += 1
        function, filename, line = self._parts_of(location)
        entry = {
            "number": number,
            "location": location,
            "address": self.firmware.address_of(location),
            "temporary": temporary,
            "hardware": hardware,
            "condition": condition,
            "enabled": True,
            "func": function,
            "file": filename,
            "line": line,
        }
        self.breakpoints[number] = entry
        return self._ok(token, "bkpt=%s" % self._value_to_mi(self._bkpt_to_mi(entry)))

    def _parts_of(self, location: str) -> Tuple[str, str, int]:
        if ":" in location:
            filename, _, line = location.rpartition(":")
            if line.isdigit():
                return filename.split(".")[0], filename, int(line)
        return location, "main.c", 1

    def _bkpt_to_mi(self, entry: Dict[str, Any]) -> Dict[str, str]:
        record = {
            "number": str(entry["number"]),
            # GDB reports "hw breakpoint" for -break-insert -h, and the driver
            # counts hardware comparators from this field.
            "type": "hw breakpoint" if entry["hardware"] else "breakpoint",
            "disp": "del" if entry["temporary"] else "keep",
            "enabled": "y" if entry["enabled"] else "n",
            "addr": "0x%08x" % entry["address"],
            "func": entry["func"],
            "file": entry["file"],
            "fullname": "/project/%s" % entry["file"],
            "line": str(entry["line"]),
            "times": "0",
        }
        if entry["condition"]:
            record["cond"] = entry["condition"]
        return record

    def _mi_break_delete(self, argument: str, token: str) -> List[str]:
        if not argument.strip():
            self.breakpoints.clear()
            self.watchpoints.clear()
            return self._ok(token)
        for item in argument.split():
            if item.isdigit():
                self.breakpoints.pop(int(item), None)
                self.watchpoints.pop(int(item), None)
        return self._ok(token)

    def _mi_break_list(self, _argument: str, token: str) -> List[str]:
        entries = [self._bkpt_to_mi(entry) for entry in self.breakpoints.values()]
        body = ",".join("bkpt=%s" % self._value_to_mi(entry) for entry in entries)
        table = (
            'BreakpointTable={nr_rows="%d",nr_cols="6",body=[%s]}'
            % (len(entries), body)
        )
        return self._ok(token, table)

    def _mi_break_watch(self, argument: str, token: str) -> List[str]:
        tokens = argument.split()
        expression = " ".join(item for item in tokens if not item.startswith("-")).strip()
        if len(self.watchpoints) >= 4:
            return self._error(token, "Cannot insert watchpoint: no comparator free.")
        number = self._next_breakpoint
        self._next_breakpoint += 1
        self.watchpoints[number] = {"number": number, "exp": expression}
        key = "wpt"
        if "-r" in tokens:
            key = "hw-rwpt"
        elif "-a" in tokens:
            key = "hw-awpt"
        return self._ok(
            token,
            "%s={number=\"%d\",exp=\"%s\"}" % (key, number, self._quote(expression)),
        )

    # -- execution ------------------------------------------------------
    def _mi_continue(self, _argument: str, token: str) -> List[str]:
        if not self.connected:
            return self._error(token, "The program is not being run.")
        results = self.resume()
        if results:
            self._registers_seen_by_gdb()
        else:
            self._registers_forgotten_by_gdb()
        return ["%s^running" % token, "(gdb)"] + self._stopped_lines(results)

    def _mi_step(self, _argument: str, token: str) -> List[str]:
        if not self.connected:
            return self._error(token, "The program is not being run.")
        results = self.step()
        self._registers_seen_by_gdb()
        return ["%s^running" % token, "(gdb)"] + self._stopped_lines(results)

    def _mi_interrupt(self, _argument: str, token: str) -> List[str]:
        results = self.interrupt()
        self._registers_seen_by_gdb()
        return self._ok(token) + self._stopped_lines(results)

    # -- memory ---------------------------------------------------------
    def _mi_read_memory(self, argument: str, token: str) -> List[str]:
        tokens = argument.split()
        if len(tokens) < 2:
            return self._error(token, "Usage: -data-read-memory-bytes ADDRESS COUNT")
        try:
            address = int(tokens[0].strip('"'), 0)
            count = int(tokens[1])
        except ValueError:
            return self._error(token, "Invalid address or count.")
        if count <= 0:
            return self._error(token, "Invalid number of bytes requested.")
        contents = self.read_memory(address, count).hex()
        block = (
            '{begin="0x%08x",offset="0x00000000",end="0x%08x",contents="%s"}'
            % (address, address + count, contents)
        )
        return self._ok(token, "memory=[%s]" % block)

    def _mi_write_memory(self, argument: str, token: str) -> List[str]:
        tokens = argument.split()
        if len(tokens) < 2:
            return self._error(token, "Usage: -data-write-memory-bytes ADDRESS CONTENTS")
        try:
            address = int(tokens[0].strip('"'), 0)
            data = bytes.fromhex(tokens[1].strip('"'))
        except ValueError:
            return self._error(token, "Invalid address or contents.")
        self.write_memory(address, data)
        return self._ok(token)

    def _mi_evaluate(self, argument: str, token: str) -> List[str]:
        expression = argument.strip().strip('"')
        try:
            value = self.evaluate(expression)
        except KeyError:
            return self._error(
                token, 'No symbol "%s" in current context.' % expression.lstrip("&")
            )
        return self._ok(token, 'value="%s"' % self._quote(value))

    # -- stack and registers -------------------------------------------
    def _mi_stack(self, argument: str, token: str) -> List[str]:
        frames = self.call_stack()
        tokens = [item for item in argument.split() if item.isdigit()]
        if len(tokens) >= 2:
            low, high = int(tokens[0]), int(tokens[1])
            frames = frames[low : high + 1]
        body = ",".join("frame=%s" % self._value_to_mi(frame) for frame in frames)
        return self._ok(token, "stack=[%s]" % body)

    def _mi_register_names(self, _argument: str, token: str) -> List[str]:
        names = ",".join('"%s"' % name for name in self.REGISTER_NAMES)
        return self._ok(token, "register-names=[%s]" % names)

    def core_registers(self) -> Dict[int, int]:
        """The core's registers as they are now, by GDB register number."""
        registers = {}
        for index in range(len(self.REGISTER_NAMES)):
            if index == 15:
                registers[index] = self.program_counter
            elif index == 13:
                registers[index] = 0x20008000
            else:
                registers[index] = index * 0x11111111 & 0xFFFFFFFF
        return registers

    def _gdb_registers(self) -> Dict[int, int]:
        """The registers as GDB reports them, which is not always the core's.

        GDB reads the registers when the target stops and keeps them until it
        sees the target run or stop again, or is told to flush them. A
        ``monitor`` command goes to the GDB Server and GDB never sees what it
        does, so after ``monitor reset`` GDB still reports the registers from
        before the reset: on 5C1712 the PC from before the reset where the
        server said 0x00000A80 (issue #178). Without this a driver that never
        flushed the cache read correct registers here and wrong ones on a probe.
        """
        if self.register_cache is None:
            self.register_cache = self.core_registers()
        return self.register_cache

    def _registers_seen_by_gdb(self) -> None:
        """GDB saw the target stop: it reads the registers afresh."""
        self.register_cache = self.core_registers()

    def _registers_forgotten_by_gdb(self) -> None:
        """GDB saw the target run, or was told to flush: nothing is cached."""
        self.register_cache = None

    def _mi_register_values(self, argument: str, token: str) -> List[str]:
        wanted = [item for item in argument.split() if item.isdigit()]
        indices = [int(item) for item in wanted] or list(range(len(self.REGISTER_NAMES)))
        registers = self._gdb_registers()
        entries = [
            '{number="%d",value="0x%08x"}' % (index, registers[index])
            for index in indices if index in registers
        ]
        return self._ok(token, "register-values=[%s]" % ",".join(entries))

    # -- console commands ----------------------------------------------
    def _mi_interpreter_exec(self, argument: str, token: str) -> List[str]:
        _, _, rest = argument.partition(" ")
        command = rest.strip()
        if command.startswith('"') and command.endswith('"'):
            command = command[1:-1]
        command = command.replace('\\"', '"').replace("\\\\", "\\")
        return self._console_command(command, token)

    def _console_command(self, command: str, token: str) -> List[str]:
        text = command.strip()
        lower = text.lower()
        output: List[str] = []

        if lower == "load" or lower.startswith("load "):
            if not self.connected:
                return self._error(token, "The load command requires a target.")
            total = 0
            for name, (address, size) in self.firmware.sections.items():
                output.append("Loading section %s, size 0x%x lma 0x%08x" % (name, size, address))
                total += size
            output.append("Start address 0x%08x, load size %d"
                          % (self.firmware.address_of("main"), total))
            output.append("Transfer rate: 120 KB/sec, 4096 bytes/write.")
            self.flashed = True
            return self._stream(output) + self._ok(token)

        if lower.startswith("compare-sections"):
            if not self.flashed and not self.flash_matches:
                pass
            for name, (address, size) in self.firmware.sections.items():
                verdict = "matched" if self.flash_matches else "MIS-MATCHED"
                output.append(
                    "Section %s, range 0x%08x -- 0x%08x: %s"
                    % (name, address, address + size, verdict)
                )
            if not self.flash_matches:
                output.append("warning: One or more sections of the target image does "
                              "not match the loaded file")
            return self._stream(output) + self._ok(token)

        if lower in ("maintenance flush register-cache", "flushregs"):
            self._registers_forgotten_by_gdb()
            return self._stream(["Register cache flushed."]) + self._ok(token)

        if lower.startswith("monitor"):
            return self._monitor(text[len("monitor"):].strip(), token)

        if lower.startswith("set var "):
            assignment = text[len("set var "):]
            name, _, value = assignment.partition("=")
            try:
                self.set_variable(name.strip(), int(value.strip(), 0))
            except KeyError:
                return self._error(token, 'No symbol "%s" in current context.' % name.strip())
            except ValueError:
                self.set_variable(name.strip(), value.strip())
            return self._ok(token)

        if lower.startswith("print ") or lower.startswith("p "):
            expression = text.split(" ", 1)[1]
            try:
                return self._stream(["$1 = %s" % self.evaluate(expression)]) + self._ok(token)
            except KeyError:
                return self._error(token, 'No symbol "%s" in current context.' % expression)

        # An unrecognised console command is reported, not silently accepted:
        # a driver sending the wrong thing should fail a test.
        return self._error(token, 'Undefined command: "%s".' % text.split()[0] if text else "empty")

    def _stream(self, lines: List[str]) -> List[str]:
        return ['~"%s\\n"' % self._quote(line) for line in lines]

    def _erase_flash(self) -> None:
        """Make flash read erased: the image's flash sections, and the vector
        table at address 0, which the default part aliases to flash as an STM32
        does at boot. RAM sections keep their contents."""
        for address, size in self.firmware.sections.values():
            if address < 0x20000000:
                for offset in range(size):
                    self.memory[address + offset] = 0xFF
        for offset in range(4):
            self.memory[offset] = 0xFF
        self.flashed = False

    def _monitor(self, command: str, token: str) -> List[str]:
        self.monitor_log.append(command)
        lower = command.lower()
        if lower.startswith("reset"):
            # Every reset type leaves the core halted, as the J-Link GDB Server
            # does: "monitor reset 0" on a real probe left the nRF52840 halted
            # (DHCSR 0x00030003) until something resumed it (issue #177). An
            # earlier model ran the target after "reset 0", which is why a
            # driver that never resumed it passed here and failed on the bench.
            self.flow_index = 0
            self.location = self.firmware.flow[0] if self.firmware.flow else "main"
            self.cycles = 0
            self.halted = True
            return self._stream(["Resetting target"]) + self._ok(token)
        if lower in ("halt", "h"):
            self.halted = True
            return self._stream(["Target halted"]) + self._ok(token)
        if lower in ("go", "g"):
            self.halted = False
            return self._ok(token)
        if lower == "flash erase":
            self._erase_flash()
            return self._stream(["Erasing flash (may take a while)...",
                                 "Flash erase: O.K."]) + self._ok(token)
        if lower.startswith("semihosting"):
            return self._ok(token)
        if lower.startswith("swo"):
            return self._stream(["SWO started"]) + self._ok(token)
        if lower.startswith("jlinkinfo") or lower.startswith("version"):
            return self._stream([
                self.idn,
                "S/N: %s" % self.serial_number,
            ]) + self._ok(token)
        if lower.startswith("rtt"):
            if "start" in lower:
                self.rtt_started = True
                return self._stream(["RTT started"]) + self._ok(token)
            if "stop" in lower:
                self.rtt_started = False
                return self._ok(token)
        return self._stream(["Executed: %s" % command]) + self._ok(token)
