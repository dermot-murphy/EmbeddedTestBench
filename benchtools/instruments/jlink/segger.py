"""The ``segger`` backend: a J-Link driven by SEGGER's own tools, no GDB.

Selected by ``backend: segger`` in a bench file's probe options, or
``--backend segger`` on ``benchtools jlink`` (#71). ``gdb`` stays the default.

What it does, and how:

========================  ==================================================
identify                  Commander's start-up banner: S/N, firmware, hardware
flash (HEX, ELF)          ``r``, ``h``, ``loadfile``; then every range of the
                          image read back with ``savebin`` and compared
verify                    the same read-back, range by range
erase                     ``r``, ``h``, ``erase``; then a flash word read back
                          and required to be erased
read / write memory       ``savebin`` / ``w4`` and ``w1``; a write to memory
                          read back in a new Commander run
reset, run, halt          ``r`` with ``h`` or ``g``, ``g``, ``h``; then DHCSR
                          read in a new run
restore                   as for ``gdb``: built on flash and memory access
RTT (read only)           J-Link RTT Logger, written to a file and read back
========================  ==================================================

Everything that needs symbols or a debugger - variables by name, breakpoints,
watchpoints, stepping, the call stack, registers, timing between two code
locations, ``monitor`` commands - is refused **before anything is sent to the
probe**, by :class:`UnsupportedOperationError`, which names the operation and
the backend. A specification written for ``gdb`` run on a ``segger`` bench
then fails at its first such step and says why, instead of failing later on
an error from a tool that was never asked.

Behaviour kept equal to ``gdb`` (issue #69's lessons):

* an erase is confirmed by reading flash back, never by the tool's report;
* a write to memory - UICR, flash, RAM - is read back, in a separate
  Commander run so that the read is the part's and not a cached copy (a
  register write is not, by default: see :meth:`write_memory`);
* the core is left running on close unless :attr:`leave_halted` is set.

Each operation is one Commander run, which connects and disconnects. Whether
a core halted by one run stays halted after Commander exits is **not
verified**: on 2026-10-05 ending a Commander session resumed a core that was
halted (JLink_Integration_Notes §4.3). So after run control the core's state
is read from DHCSR, :attr:`is_halted` reports that, and a halt that did not
hold raises. The simulator models the resume.

Traces to: JLINK-FR-006, JLINK-FR-007, JLINK-FR-008, JLINK-FR-009,
JLINK-DD-SEGGER.
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Sequence, Tuple, Union

from ...core.errors import BenchToolsError, ConfigurationError
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.paths import input_paths
from ...simulated.world import rtt_source
from .commander import (
    JLinkCommander,
    SimulatedReadOnlyRtt,
    file_argument,
    number,
    parse_banner,
)
from .constants import DebugInterface, HaltReason, JLINK_LIMITS, ProbeLimits

from .image import ImageRange
from .probe import (
    FlashResult,
    HaltInfo,
    JLinkProbe,
    SectionVerdict,
    VerifyResult,
    register_backend,
)
from .rtt import RttClient, SimulatedRttBackend
from .simcommander import SimulatedCommander
from .simulator import SimulatedJLink

#: Debug Halting Control and Status Register, and its S_HALT bit (ARMv7-M).
#: On 5C1712 it read 0x00030003 halted and 0x00050001 running (notes §4.3).
DHCSR = 0xE000EDF0
DHCSR_S_HALT = 1 << 17


def is_register_address(address: int, size: int = 1) -> bool:
    """Whether any byte of *size* bytes from *address* is in a Cortex-M
    peripheral or system region, where registers live and a write need not
    read back as written (ARMv7-M memory map: peripherals
    0x40000000-0x5FFFFFFF, system from 0xE0000000). A range that only starts
    in memory and runs into a register counts: the register in it would fail
    the read-back."""
    end = address + max(int(size), 1)
    return (address < 0x60000000 and end > 0x40000000) or end > 0xE0000000


__all__ = [
    "SeggerJLinkProbe",
    "UnsupportedOperationError",
    "GDB_ONLY_OPERATIONS",
    "DHCSR",
    "is_register_address",
]


class UnsupportedOperationError(ConfigurationError):
    """An operation the selected J-Link backend does not provide.

    :param operation: The method asked for.
    :param backend: The backend that was selected.
    """

    def __init__(self, operation: str, backend: str = "segger", reason: str = "") -> None:
        self.operation = operation
        self.backend = backend
        super().__init__(
            "%s is not available on the J-Link %r backend%s. Select backend: gdb "
            "(the J-Link GDB Server and arm-none-eabi-gdb) for it."
            % (operation, backend, (": " + reason) if reason else "")
        )


#: Operations only the ``gdb`` backend provides, with the reason given when
#: the ``segger`` backend refuses one.
GDB_ONLY_OPERATIONS: Dict[str, str] = {
    "monitor": "it is a J-Link GDB Server command",
    "load_symbols": "symbols are read by GDB",
    "attach": "there is no GDB to attach",
    "step": "single-stepping needs a debugger",
    "wait_for_halt": "halt notification needs a debugger",
    "program_counter": "registers are read through GDB",
    "registers": "registers are read through GDB",
    "set_breakpoint": "breakpoints need a debugger",
    "set_watchpoint": "watchpoints need a debugger",
    "list_breakpoints": "breakpoints need a debugger",
    "delete_breakpoint": "breakpoints need a debugger",
    "clear_breakpoints": "breakpoints need a debugger",
    "run_to": "it needs a breakpoint",
    "read_variable": "variables by name need GDB's symbols",
    "write_variable": "variables by name need GDB's symbols",
    "variable_address": "variables by name need GDB's symbols",
    "variable_size": "variables by name need GDB's symbols",
    "evaluate": "expressions need GDB's symbols",
    "call_stack": "unwinding the stack needs GDB",
    "backtrace": "unwinding the stack needs GDB",
    "measure_time_between": "timing between code locations needs breakpoints",
}


def _refuse(operation: str, reason: str):
    """A method that raises :class:`UnsupportedOperationError` for *operation*."""

    def refused(self, *_args, **_kwargs):
        raise UnsupportedOperationError(operation, self.backend, reason)

    refused.__name__ = operation
    refused.__doc__ = "Not available on the ``segger`` backend: %s." % reason
    return refused


class SeggerJLinkProbe(JLinkProbe):  # pylint: disable=too-many-instance-attributes
    """A J-Link driven through J-Link Commander and J-Link RTT Logger.

    Made by :meth:`JLinkProbe.connect` with ``backend="segger"``; it is a
    :class:`JLinkProbe`, so a bench registers and checks it as one.

    :param commander: Runs the command files, on a probe or on the simulator.
    :param rtt: RTT client, read only.
    :param elf: Image flashed and verified when no path is given.
    """

    #: Which mechanism produced a result, recorded in each result (#71).
    backend = "segger"

    # The base class's __init__ builds a GDB session, which this backend
    # does not have; Instrument's is called directly.
    # pylint: disable-next=super-init-not-called,non-parent-init-called,too-many-arguments
    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        commander: JLinkCommander,
        rtt: Optional[RttClient] = None,
        elf: Optional[str] = None,
        limits: ProbeLimits = JLINK_LIMITS,
        auto_check_errors: bool = True,
        firmware: Optional[str] = None,
        rtt_stream=None,
    ) -> None:
        Instrument.__init__(  # pylint: disable=non-parent-init-called
            self, auto_check_errors=auto_check_errors)
        self._commander = commander
        self._server = None
        self._session = None
        self._rtt = rtt
        #: The RTT client's source, kept so the logger can be stopped and its
        #: file read out before the client stops collecting.
        self._rtt_source = rtt_stream
        self._elf = elf
        self._firmware = firmware
        self._limits = limits
        self._target_address = "simulated" if isinstance(commander, SimulatedCommander) else "usb"
        self._attached = False
        self._halted = False
        self._open_flag = False
        self._touched = False
        self._cycle_counter_ready = False
        self._adopt(commander, rtt)
        self.leave_halted = False
        self.attach_on_open = True

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    # pylint: disable-next=too-many-arguments,too-many-locals,too-many-positional-arguments
    def open_segger(
        cls,
        resource: str,
        device: Optional[str] = None,
        elf: Optional[str] = None,
        firmware: Optional[str] = None,
        interface: Union[DebugInterface, str] = DebugInterface.SWD,
        speed_khz: int = 4000,
        serial_number: Optional[str] = None,
        commander_executable: Optional[str] = None,
        rtt_logger_executable: Optional[str] = None,
        limits: ProbeLimits = JLINK_LIMITS,
        timeout: float = 20.0,
        auto_check_errors: bool = True,
        initialise: bool = True,
        attach: bool = True,
        simulated_target: Optional[str] = None,
    ) -> "SeggerJLinkProbe":
        """Open a ``segger``-backend link; :meth:`JLinkProbe.connect` calls this.

        :param resource: ``sim://`` for the simulator, or ``jlink://`` for a
            probe on this machine's USB. A host is refused: Commander can
            reach a probe over IP, but that is not verified on this bench, and
            a host here means a GDB Server to the ``gdb`` backend.
        """
        text = (resource or "sim://").strip()
        lower = text.lower()
        if lower.startswith(("sim://", "mock://")) or lower in ("sim", "mock"):
            simulator = SimulatedJLink()
            if simulated_target:
                try:
                    simulator.periodic_rtt = rtt_source(simulated_target)
                except ValueError as exc:
                    raise ConfigurationError(str(exc)) from exc
            commander: JLinkCommander = SimulatedCommander(simulator, timeout=max(timeout, 1.0))
            source = SimulatedReadOnlyRtt(SimulatedRttBackend(simulator))
            if elf is None:
                elf = simulator.firmware.path
        else:
            host, _port = cls._parse_target(text)
            if host not in ("127.0.0.1", "localhost", "::1", ""):
                raise ConfigurationError(
                    "the J-Link 'segger' backend drives a probe on this machine's USB; "
                    "%r names host %r. Use backend: gdb to reach a GDB Server on "
                    "another machine." % (resource, host))
            commander = JLinkCommander(
                device=device, interface=interface, speed_khz=speed_khz,
                serial_number=serial_number, executable=commander_executable,
                timeout=max(timeout, 60.0),
            )
            source = commander.rtt_backend(executable=rtt_logger_executable)
        probe = cls(commander=commander, rtt=RttClient(source), elf=elf, limits=limits,
                    auto_check_errors=auto_check_errors, firmware=firmware,
                    rtt_stream=source)
        probe.attach_on_open = bool(attach)
        try:
            if initialise:
                probe.initialise()
        except Exception:
            probe.close()
            raise
        return probe

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _open(self) -> None:
        self._commander.check()
        self._open_flag = True

    def _post_open(self) -> None:
        """Nothing is attached: each operation is a Commander run of its own.

        ``is_attached`` means "operations other than RTT are allowed", so a
        probe opened with ``attach=False`` refuses them, as the ``gdb``
        backend's RTT-only link does.
        """
        self._attached = bool(self.attach_on_open)

    def _close(self) -> None:
        try:
            self._finish_rtt()
        except Exception:  # pylint: disable=broad-exception-caught
            self._logger.debug("RTT did not stop cleanly", exc_info=True)
        try:
            if self._open_flag and self._attached and self._touched and not self.leave_halted:
                # JLINK-FR-006 on this backend: a run of its own that lets the
                # core go, rather than relying on Commander's exit to do it.
                self._commander.run(["g"], "resume on close", timeout=10.0)
                self._halted = False
        except Exception:  # pylint: disable=broad-exception-caught
            self._logger.debug("resume on close failed", exc_info=True)
        finally:
            self._attached = False
            self._open_flag = False
            self._commander.close()

    @property
    def is_open(self) -> bool:
        """``True`` between opening and closing; no link is held in between."""
        return self._open_flag

    @property
    def session(self):
        """There is no GDB session on this backend."""
        raise UnsupportedOperationError("session", self.backend, "there is no GDB session")

    @property
    def commander(self) -> JLinkCommander:
        """What runs the command files, for commands the driver does not wrap."""
        return self._commander

    def _run(self, commands: Sequence[str], what: str, timeout: Optional[float] = None) -> str:
        """One Commander run, refused on a link opened for RTT only."""
        if not self._attached:
            raise UnsupportedOperationError(
                what, self.backend,
                "this link was opened for RTT only (attach=False), so nothing but "
                "RTT is sent to the target")
        self._touched = True
        return self._commander.run(commands, what, timeout=timeout)

    def _read_identity(self) -> InstrumentIdentity:
        """Identify the probe from the banner Commander prints when it connects.

        Commander connects only when a command needs it, so an empty command
        file prints no ``S/N:`` or ``Firmware:`` line. ``f`` (firmware info)
        connects to the probe and not to the target (5C1712, 2026-11-14).
        """
        output = self._commander.run(["f"], "identify", timeout=30.0)
        banner = parse_banner(output)
        parts = ["%s: %s" % (label, banner[key]) for key, label in (
            ("firmware", "Firmware"), ("hardware", "Hardware"), ("serial_number", "S/N"),
            ("version", "J-Link Commander")) if key in banner]
        return InstrumentIdentity(
            raw=", ".join(parts) or "J-Link (no version reported)",
            manufacturer="SEGGER",
            model="J-Link",
            serial_number=banner.get("serial_number", ""),
            firmware=banner.get("firmware", ""),
        )

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------
    def _image(self, path: Optional[str]) -> Tuple[str, List[ImageRange]]:
        target = path or self._elf
        if not target:
            raise ConfigurationError(
                "no image to flash: pass path=... or construct the probe with elf=...")
        if not isinstance(self._commander, SimulatedCommander) and not os.path.exists(target):
            raise ConfigurationError("no such image file: %s" % target)
        ranges = self._commander.image(target)
        if not ranges:
            raise BenchToolsError("%s writes nothing: it holds no loadable data" % target)
        return target, ranges

    @input_paths("path")
    def flash(
        self,
        path: Optional[str] = None,
        verify: bool = True,
        reset: bool = True,
        timeout: float = 180.0,
        preserve: Sequence[Tuple[int, int]] = (),
    ) -> FlashResult:
        """Program an image with Commander's ``loadfile``, then read it back.

        As :meth:`JLinkProbe.flash`. Two differences, both stated rather than
        hidden: the sections reported are the image's own ranges (ELF
        segments, HEX runs), since nothing here reads section names; and
        ``loadfile`` resets and halts the MCU itself before downloading
        ("'loadfile': Performing implicit reset & halt of MCU." in V9.42), so
        ``reset=False`` still sees a reset - only the explicit one before it
        is left out.

        Verification is this driver's own: every range read back with
        ``savebin`` and compared, not ``loadfile``'s own check alone.
        """
        target, ranges = self._image(path)
        kept = [(address, self.read_memory(address, size)) for address, size in preserve]
        commands = (["r", "h"] if reset else []) + ["loadfile %s" % file_argument(target)]
        started = time.monotonic()
        output = self._run(commands, "flash %s" % os.path.basename(target), timeout=timeout)
        elapsed = time.monotonic() - started
        self._halted = True
        self._elf = target
        result = FlashResult(
            sections={item.name: (item.address, len(item.data)) for item in ranges},
            output=output, seconds=elapsed, backend=self.backend,
        )
        self._logger.info("flashed %d bytes in %d range(s) in %.2f s",
                          result.bytes_written, len(ranges), elapsed)
        if verify:
            result.verify = self._compare(target, ranges, timeout=timeout)
            if not result.verify.matched:
                raise BenchToolsError(
                    "flash verification failed: range(s) %s do not match %s"
                    % (", ".join(result.verify.mismatched) or "none reported", target))
        result.preserved = self._restore(kept)
        self._cycle_counter_ready = False
        return result

    @input_paths("path")
    def verify(self, path: Optional[str] = None, timeout: float = 180.0) -> VerifyResult:
        """Compare the target with an image, range by range, by reading back."""
        target, ranges = self._image(path)
        return self._compare(target, ranges, timeout=timeout)

    def _compare(self, target: str, ranges: Sequence[ImageRange], timeout: float) -> VerifyResult:
        files = [self._commander.scratch("verify_%08x.bin" % item.address) for item in ranges]
        commands = ["savebin %s, %s, %s" % (file_argument(name), number(item.address),
                                            number(len(item.data)))
                    for name, item in zip(files, ranges)]
        output = self._run(commands, "verify %s" % os.path.basename(target), timeout=timeout)
        sections = []
        for name, item in zip(files, ranges):
            data = self._read_back(name, len(item.data), item.address)
            sections.append(SectionVerdict(name=item.name, start=item.address,
                                           end=item.end, matched=data == item.data))
        return VerifyResult(sections=sections, output=output, backend=self.backend)

    def erase(self, timeout: float = 120.0, blank_check_address: Optional[int] = 0) -> str:
        """Erase the chip with Commander's ``erase``, and check that it did.

        Reset and halt first, as on ``gdb`` (issue #69); then a flash word is
        read back in a run of its own and must read ``0xFFFFFFFF``. Whether a
        Commander chip erase also erases an nRF52840's UICR is not verified.
        """
        output = self._run(["r", "h", "erase"], "erase", timeout=timeout)
        self._halted = True
        if blank_check_address is not None:
            word = self.read_word(blank_check_address)
            if word != 0xFFFFFFFF:
                raise BenchToolsError(
                    "flash erase reported %r but 0x%08x still reads 0x%08x"
                    % (self._last_line(output), blank_check_address, word))
        return output

    @staticmethod
    def _last_line(output: str) -> str:
        lines = [line.strip() for line in output.splitlines() if "rasing" in line]
        return lines[-1] if lines else "nothing"

    # ------------------------------------------------------------------
    # Run control
    # ------------------------------------------------------------------
    def core_is_halted(self) -> bool:
        """Whether the core is halted, read from DHCSR in a Commander run of
        its own: ``S_HALT``, bit 17, of ``0xE000EDF0``.

        This is the part's answer, not the driver's belief. It matters here
        because each operation is a Commander run that ends, and on 5C1712 on
        2026-10-05 ending a Commander session let a halted core run again
        (JLink_Integration_Notes §4.3). That session read DHCSR with
        ``mem32`` without halting the core; reading it with ``savebin``, as
        here, is not yet verified on the bench.

        **Unverified: that the read leaves the core as it was.** The run that
        reads DHCSR connects with ``-AutoConnect 1``. If that connect halted a
        running core, this would report "halted" for a core that ran, and
        :meth:`run` and ``reset(halt=False)`` would raise falsely. The bench
        check JLINK-OPEN-05 (notes §4.9) settles it: ``reset --run``, DHCSR
        read twice in separate runs, then ``halt`` and DHCSR read again.
        """
        halted = bool(self.read_word(DHCSR) & DHCSR_S_HALT)
        self._halted = halted
        return halted

    def reset(self, halt: bool = True, timeout: float = 30.0) -> None:
        """Reset the target, then hold it halted (``h``) or let it run (``g``).

        The core's state is then read back from DHCSR (:meth:`core_is_halted`)
        and :attr:`is_halted` reports that, not the request. A reset that was
        to let the core run and left it halted raises, as #177 was on
        ``gdb``. A reset that was to leave it halted and found it running is
        logged, not raised: Commander's exit may resume the core, and
        :meth:`restore` resets halted before programming, which ``loadfile``
        halts for itself anyway.

        :raises BenchToolsError: if ``reset(halt=False)`` left the core halted.
        """
        self._run(["r", "h" if halt else "g"], "reset", timeout=timeout)
        self._cycle_counter_ready = False
        halted = self.core_is_halted()
        if not halt and halted:
            raise BenchToolsError(
                "reset with the core to run, but DHCSR says it is halted afterwards")
        if halt and not halted:
            self._logger.warning(
                "reset with the core halted, but it was running once J-Link "
                "Commander exited")

    def run(self, timeout: Optional[float] = None) -> None:
        """Let the target run: always ``g``, whatever the driver last did,
        since another run - the command line's ``halt``, another tool - may
        have halted it. The core's state is then read back from DHCSR.

        :raises BenchToolsError: if the core is still halted.
        """
        self._run(["g"], "run", timeout=timeout)
        if self.core_is_halted():
            raise BenchToolsError("sent 'g' but DHCSR says the core is still halted")

    resume = run

    def halt(self, timeout: float = 10.0) -> HaltInfo:
        """Halt the core with ``h``, then read DHCSR in a new run to see
        whether it stayed halted. Where it stopped is not reported: there are
        no symbols, and the registers are read through GDB.

        :raises BenchToolsError: if the core was running once Commander had
            exited - this backend cannot then hold a core halted between
            operations, and saying "halted" would be false.
        """
        self._run(["h"], "halt", timeout=timeout)
        if not self.core_is_halted():
            raise BenchToolsError(
                "J-Link Commander halted the core, but it was running again once "
                "Commander exited (DHCSR S_HALT clear). The segger backend cannot "
                "hold a core halted between operations here; use backend: gdb "
                "to keep it halted.")
        return HaltInfo(reason=HaltReason.SIGNAL, signal="halted by J-Link Commander")

    stop = halt

    def _stop_if_running(self, timeout: float = 10.0) -> None:
        """Nothing to do: each Commander run connects afresh."""

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    def read_memory(self, address: int, size: int) -> bytes:
        """Read *size* bytes with ``savebin`` into a file, and read the file."""
        if size < 0:
            raise ConfigurationError("size must not be negative, got %r" % (size,))
        if size == 0:
            return b""
        name = self._commander.scratch("read_%08x.bin" % address)
        self._run(["savebin %s, %s, %s" % (file_argument(name), number(address), number(size))],
                  "read 0x%08x" % address)
        return self._read_back(name, size, address)

    @staticmethod
    def _read_back(name: str, size: int, address: int) -> bytes:
        try:
            with open(name, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            raise BenchToolsError(
                "J-Link Commander wrote no file for %d byte(s) at 0x%08x" % (size, address)
            ) from exc
        finally:
            try:
                os.remove(name)
            except OSError:
                pass
        if len(data) != size:
            raise BenchToolsError(
                "J-Link Commander read %d of %d byte(s) at 0x%08x" % (len(data), size, address))
        return data

    def write_memory(self, address: int, data: bytes, verify: Optional[bool] = None) -> None:
        """Write *data* with ``w4`` for whole aligned words and ``w1`` for the
        rest, then read it back in a new run.

        :param verify: Read back and raise if the part does not hold *data*.
            ``None``, the default, reads back memory - flash, UICR, RAM -
            and not a register: in the Cortex-M peripheral and system regions
            (:func:`is_register_address`) a write-1-to-clear or write-1-to-set
            bit reads back differently from what was written, so a read-back
            there would fail a correct write. ``True`` or ``False`` decides
            either way. Whether ``w4`` into flash or UICR programs the part or
            only J-Link's flash cache is not verified on this backend; the
            read-back is what would show it.
        """
        payload = bytes(data)
        if verify is None:
            verify = not is_register_address(address, len(payload))
        if not payload:
            return
        commands: List[str] = []
        offset = 0
        while offset < len(payload):
            here = address + offset
            if here % 4 == 0 and len(payload) - offset >= 4:
                word = int.from_bytes(payload[offset:offset + 4], "little")
                commands.append("w4 %s, %s" % (number(here), number(word)))
                offset += 4
            else:
                commands.append("w1 %s, %s" % (number(here), number(payload[offset])))
                offset += 1
        self._run(commands, "write 0x%08x" % address)
        if verify:
            back = self.read_memory(address, len(payload))
            if back != payload:
                raise BenchToolsError(
                    "wrote %d byte(s) at 0x%08x with J-Link Commander but they read back "
                    "as %s, not %s" % (len(payload), address, back.hex(), payload.hex()))
        self._after_configuration()

    write_ram = write_memory

    def read_ram(self, address: int, size: int) -> bytes:
        """Reading RAM is reading memory."""
        return self.read_memory(address, size)

    # ------------------------------------------------------------------
    # RTT
    # ------------------------------------------------------------------
    def rtt_start(self, log_path: Optional[str] = None, channel: int = 0) -> None:
        """Start reading RTT with J-Link RTT Logger.

        The logger reads a running target, so a core the driver halted is let
        go first. Only up-channel 0 is read, as on ``gdb``.
        """
        if channel >= self._limits.max_rtt_channels:
            raise ConfigurationError(
                "channel %d is beyond the %d configured RTT channels"
                % (channel, self._limits.max_rtt_channels))
        if self._attached:
            self.run()
        try:
            self.rtt.start(log_path=log_path)
        except BaseException:
            # The logger may already be running (a log file that cannot be
            # opened fails after it starts); it must not outlive the failure.
            if self._rtt_source is not None:
                self._rtt_source.rtt_close()
            raise

    def rtt_stop(self) -> None:
        """Stop the logger so it writes out what it holds, then take the last
        bytes from its file and stop collecting."""
        self._finish_rtt()

    def _finish_rtt(self) -> None:
        finish = getattr(self._rtt_source, "finish", None)
        try:
            if finish is not None:
                finish()
        finally:
            if self._rtt is not None:
                self._rtt.stop()


def _install_refusals() -> None:
    """Give the probe a refusing method for each GDB-only operation."""
    for operation, reason in GDB_ONLY_OPERATIONS.items():
        setattr(SeggerJLinkProbe, operation, _refuse(operation, reason))


_install_refusals()
register_backend("segger", SeggerJLinkProbe.open_segger)
