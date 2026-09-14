"""SEGGER J-Link debug probe driver.

Drives a target over the J-Link GDB Server using GDB's machine interface. One
backend covers the whole feature set a test bench needs - flash, verify, run
control, breakpoints, memory, symbol-aware variable access, call stacks - and
RTT arrives over the same server on a TCP port.

Why GDB/MI rather than the J-Link DLL: reading a variable *by name* and
unwinding a *call stack* both need DWARF debug information and stack unwinding.
GDB already has both, correct and maintained. Going straight to the DLL would
mean reimplementing them, which is a large job with a long tail of wrong answers.

Why this matters for the container plan: both links are TCP. The probe is USB, so
the GDB Server runs where the USB port is; the tests can run anywhere that can
reach it. Moving this into a container changes a host name and nothing else::

    JLinkProbe.connect("jlink://192.168.1.9:2331", elf="build/app.elf")

Traces to: JLINK-FR-001 .. JLINK-FR-100, JLINK-ARC-001, JLINK-DD-PROBE.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ...core.errors import (
    BenchToolsError,
    ConfigurationError,
    ConnectionFailedError,
    MeasurementError,
    ProtocolError,
)
from ...core.firmware import MANIFEST_NAME, FirmwareBuild
from ...core.instrument import Instrument, InstrumentIdentity
from ...core.transport.base import Transport
from ...core.transport.mock import MockTransport
from ...core.transport.process import ProcessTransport
from ...core.validation import validate_range
from .constants import (
    DEFAULT_GDB_PORT,
    DEFAULT_RTT_PORT,
    DEMCR,
    DEMCR_TRCENA,
    DWT_CTRL,
    DWT_CTRL_CYCCNTENA,
    DWT_CYCCNT,
    BreakpointKind,
    DebugInterface,
    HaltReason,
    JLINK_LIMITS,
    ProbeLimits,
    ResetType,
    TimingMethod,
    WatchpointKind,
)
from .rtt import RttClient, SimulatedRttBackend, SocketRttBackend
from .server import GdbServer, find_gdb
from .session import GdbError, GdbMiSession
from .simulator import SimulatedJLink
from .swo import ItmDecoder, SwoStream
from .timing import TimingResult, TimingSample

__all__ = [
    "JLinkProbe",
    "Breakpoint",
    "Watchpoint",
    "StackFrame",
    "HaltInfo",
    "FlashResult",
    "VerifyResult",
    "SectionVerdict",
]

_LOG = logging.getLogger(__name__)

#: Matches "Loading section .text, size 0x1234 lma 0x08000000".
_LOAD_RE = re.compile(
    r"Loading section (?P<name>\S+), size (?P<size>0x[0-9a-fA-F]+) lma (?P<lma>0x[0-9a-fA-F]+)"
)
#: Matches "Section .text, range 0x08000000 -- 0x08004000: matched."
_COMPARE_RE = re.compile(
    r"Section (?P<name>\S+), range (?P<start>0x[0-9a-fA-F]+) -- (?P<end>0x[0-9a-fA-F]+): "
    r"(?P<verdict>matched|MIS-MATCHED)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Breakpoint:
    """A code breakpoint set on the target."""

    number: int
    location: str
    address: int = 0
    function: str = ""
    file: str = ""
    line: int = 0
    kind: BreakpointKind = BreakpointKind.SOFTWARE
    condition: str = ""

    @property
    def is_temporary(self) -> bool:
        """``True`` for a breakpoint GDB deletes when it is hit."""
        return self.kind is BreakpointKind.TEMPORARY


@dataclass(frozen=True)
class Watchpoint:
    """A data watchpoint set on the target."""

    number: int
    expression: str
    kind: WatchpointKind = WatchpointKind.WRITE


@dataclass(frozen=True)
class StackFrame:
    """One frame of the target's call stack."""

    level: int
    function: str
    file: str = ""
    line: int = 0
    address: int = 0

    def __str__(self) -> str:
        where = "%s:%d" % (self.file, self.line) if self.file else "0x%08x" % self.address
        return "#%d  %s at %s" % (self.level, self.function or "??", where)


@dataclass(frozen=True)
class HaltInfo:
    """Why and where the target stopped."""

    reason: HaltReason
    function: str = ""
    file: str = ""
    line: int = 0
    address: int = 0
    breakpoint_number: Optional[int] = None
    signal: str = ""

    @property
    def location(self) -> str:
        """``file:line`` when known, otherwise the address."""
        return "%s:%d" % (self.file, self.line) if self.file and self.line else "0x%08x" % self.address

    def __str__(self) -> str:
        return "%s at %s in %s" % (self.reason.value, self.location, self.function or "??")


@dataclass(frozen=True)
class SectionVerdict:
    """Whether one image section on the target matches the file."""

    name: str
    start: int
    end: int
    matched: bool

    @property
    def size(self) -> int:
        """Section size in bytes."""
        return self.end - self.start


@dataclass
class VerifyResult:
    """Outcome of comparing the target's flash against an image file."""

    sections: List[SectionVerdict] = field(default_factory=list)
    output: str = ""

    @property
    def matched(self) -> bool:
        """``True`` only when every section matched.

        An empty result is **not** a pass: it means nothing was compared, which
        usually means the file had no loadable sections or the command failed.
        Reporting that as success would pass a test that verified nothing.
        """
        return bool(self.sections) and all(section.matched for section in self.sections)

    @property
    def mismatched(self) -> List[str]:
        """Names of the sections that did not match."""
        return [section.name for section in self.sections if not section.matched]

    def as_dict(self) -> dict:
        return {
            "matched": self.matched,
            "sections": {
                section.name: {
                    "start": section.start, "size": section.size, "matched": section.matched,
                }
                for section in self.sections
            },
            "mismatched": self.mismatched,
        }


@dataclass
class FlashResult:
    """Outcome of programming an image onto the target."""

    sections: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    output: str = ""
    seconds: float = 0.0
    verify: Optional[VerifyResult] = None

    @property
    def bytes_written(self) -> int:
        """Total size of the sections programmed."""
        return sum(size for _, size in self.sections.values())

    @property
    def verified(self) -> Optional[bool]:
        """Whether verification passed, or ``None`` if it was not run."""
        return None if self.verify is None else self.verify.matched

    def as_dict(self) -> dict:
        summary = {
            "bytes_written": self.bytes_written,
            "seconds": self.seconds,
            "sections": {
                name: {"address": address, "size": size}
                for name, (address, size) in self.sections.items()
            },
        }
        if self.verify is not None:
            summary["verify"] = self.verify.as_dict()
        return summary


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
class JLinkProbe(Instrument):
    """A SEGGER J-Link driving a target over the GDB Server.

    :param session: An open or unopened GDB/MI session.
    :param server: The GDB Server to manage, if this driver started one.
    :param rtt: RTT client, if RTT is available on this link.
    :param elf: Path to the ELF file providing symbols.
    :param limits: Capability envelope used to validate requests.
    :param target_address: ``host:port`` GDB should attach to.
    """

    SIMULATOR_CLASS = SimulatedJLink
    MODEL_NAME = "J-Link"

    def __init__(
        self,
        session: GdbMiSession,
        server: Optional[GdbServer] = None,
        rtt: Optional[RttClient] = None,
        elf: Optional[str] = None,
        limits: ProbeLimits = JLINK_LIMITS,
        target_address: str = "",
        auto_check_errors: bool = True,
        firmware: Optional[str] = None,
    ) -> None:
        super().__init__(auto_check_errors=auto_check_errors)
        self._session = session
        self._server = server
        if rtt is None:
            # Constructed directly over a simulator - as a test or a small script
            # does - should behave like connect() and still have RTT, rather than
            # failing later with "RTT is not available".
            responder = getattr(session.transport, "responder", None)
            if isinstance(responder, SimulatedJLink):
                rtt = RttClient(SimulatedRttBackend(responder))
        self._rtt = rtt
        self._elf = elf
        self._firmware = firmware
        self._limits = limits
        self._target_address = target_address
        self._attached = False
        self._halted = True
        self._cycle_counter_ready = False
        self._itm = ItmDecoder()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def connect(
        cls,
        resource: str = "sim://",
        device: Optional[str] = None,
        elf: Optional[str] = None,
        firmware: Optional[str] = None,
        interface: Union[DebugInterface, str] = DebugInterface.SWD,
        speed_khz: int = 4000,
        serial_number: Optional[str] = None,
        rtt_port: int = DEFAULT_RTT_PORT,
        gdb_executable: Optional[str] = None,
        server_executable: Optional[str] = None,
        core_clock_hz: Optional[float] = None,
        limits: ProbeLimits = JLINK_LIMITS,
        timeout: float = 20.0,
        auto_check_errors: bool = True,
        initialise: bool = True,
        start_server: bool = True,
        **_ignored,
    ) -> "JLinkProbe":
        """Open a link to a target through a J-Link.

        :param resource: ``sim://`` for the simulator, or ``jlink://[host][:port]``
            for a real probe. A host other than localhost attaches to a GDB
            Server already running there and never tries to spawn one - which is
            how a containerised bench reaches a probe on another machine.
        :param device: Target device name, e.g. ``"nRF52840_xxAA"``. Required
            when spawning a server.
        :param elf: ELF file providing symbols. Without it, variables by name and
            source-line breakpoints are unavailable; everything else still works.
        :param firmware: Where the target build's manifest is - a directory or
            the manifest itself. Only :meth:`image_build` uses it, so that a
            specification can ask what version it flashed without naming a path
            that belongs to the bench rather than to the test. Defaults to
            beside *elf*.
        :param core_clock_hz: Core clock, for converting cycles to time. Defaults
            to the value in *limits*.
        :param start_server: Spawn a local GDB Server if none is listening.
        """
        text = (resource or "sim://").strip()
        if core_clock_hz is not None:
            limits = ProbeLimits(**{**limits.__dict__, "core_clock_hz": float(core_clock_hz)})

        if text.lower().startswith(("sim://", "mock://")) or text.lower() in ("sim", "mock"):
            simulator = SimulatedJLink()
            transport: Transport = MockTransport(responder=simulator, timeout=timeout)
            rtt = RttClient(SimulatedRttBackend(simulator))
            server = None
            address = "simulated"
            # A simulator knows its own firmware, so it needs no ELF path
            # configured. Without this, every simulated run would have to be
            # told where a file that does not exist would have been.
            if elf is None:
                elf = simulator.firmware.path
        else:
            host, port = cls._parse_target(text)
            server = GdbServer(
                device=device,
                interface=interface,
                speed_khz=speed_khz,
                host=host,
                port=port,
                rtt_port=rtt_port,
                serial_number=serial_number,
                executable=server_executable,
            )
            if start_server:
                server.start()
            gdb = find_gdb(gdb_executable)
            if gdb is None:
                raise ConnectionFailedError(
                    "no ARM-capable GDB found. Install arm-none-eabi-gdb (it ships "
                    "with the GNU Arm Embedded toolchain) or pass "
                    "gdb_executable=... . The driver needs GDB for symbol lookup "
                    "and stack unwinding."
                )
            transport = ProcessTransport(
                [gdb, "--interpreter=mi2", "--quiet", "-nx"], timeout=timeout
            )
            rtt = RttClient(SocketRttBackend(host, rtt_port))
            address = server.address

        probe = cls(
            session=GdbMiSession(transport, timeout=timeout),
            server=server,
            rtt=rtt,
            elf=elf,
            firmware=firmware,
            limits=limits,
            target_address=address,
            auto_check_errors=auto_check_errors,
        )
        try:
            if initialise:
                probe.initialise()
        except Exception:
            probe.close()
            raise
        return probe

    @staticmethod
    def _parse_target(resource: str) -> Tuple[str, int]:
        """Split ``jlink://host:port`` into its parts."""
        text = resource
        for prefix in ("jlink://", "gdb://", "tcp://"):
            if text.lower().startswith(prefix):
                text = text[len(prefix) :]
                break
        text = text.strip("/")
        if not text:
            return "127.0.0.1", DEFAULT_GDB_PORT
        if ":" in text:
            host, _, port = text.rpartition(":")
            try:
                return (host or "127.0.0.1"), int(port)
            except ValueError:
                raise ConfigurationError("invalid port in probe resource %r" % resource)
        return text, DEFAULT_GDB_PORT

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _open(self) -> None:
        self._session.start()

    def _close(self) -> None:
        if self._rtt is not None:
            try:
                self._rtt.stop()
            except Exception:  # noqa: BLE001 - closing must not raise
                _LOG.debug("RTT did not stop cleanly", exc_info=True)
        try:
            if self._attached:
                self._session.execute("-target-detach", allow_error=True, timeout=5.0)
        except Exception:  # noqa: BLE001
            _LOG.debug("detach failed", exc_info=True)
        finally:
            self._attached = False
        try:
            self._session.close()
        finally:
            if self._server is not None:
                self._server.stop()

    @property
    def is_open(self) -> bool:
        """``True`` while the GDB session is alive."""
        return self._session.transport.is_open

    def _post_open(self) -> None:
        """Configure GDB, load symbols and attach to the target.

        ``confirm off`` and ``pagination off`` are not cosmetic: with either left
        on, GDB waits for a keypress at some point and an unattended run hangs.
        """
        for setting in (
            "-gdb-set confirm off",
            "-gdb-set pagination off",
            "-gdb-set print pretty off",
            "-gdb-set mi-async on",
            "-gdb-set mem inaccessible-by-default off",
        ):
            self._session.execute(setting, allow_error=True)

        if self._elf:
            self.load_symbols(self._elf)
        if self._target_address and self._target_address != "simulated":
            self.attach()
        elif self._target_address == "simulated":
            self.attach()

    # ------------------------------------------------------------------
    @property
    def session(self) -> GdbMiSession:
        """The underlying GDB/MI session, for commands the driver does not wrap."""
        return self._session

    @property
    def limits(self) -> ProbeLimits:
        """Capability envelope used for validation."""
        return self._limits

    @property
    def core_clock_hz(self) -> float:
        """Core clock used to convert cycles to seconds."""
        return self._limits.core_clock_hz

    @property
    def elf_path(self) -> Optional[str]:
        """Path of the ELF file currently providing symbols."""
        return self._elf

    @property
    def rtt(self) -> RttClient:
        """The RTT client.

        :raises BenchToolsError: if this link has no RTT.
        """
        if self._rtt is None:
            raise BenchToolsError("RTT is not available on this connection")
        return self._rtt

    def _read_identity(self) -> InstrumentIdentity:
        """Identify the probe using the J-Link ``monitor`` interface."""
        try:
            output = self._session.execute_console("monitor version", allow_error=True).text
        except GdbError:  # pragma: no cover - firmware without the command
            output = ""
        serial = ""
        match = re.search(r"S/?N:?\s*(\d+)", output)
        if match:
            serial = match.group(1)
        model = "J-Link"
        model_match = re.search(r"(J-Link[\w\s-]*?)(?:\s+compiled|\s*$|,)", output)
        if model_match:
            model = model_match.group(1).strip()
        firmware = ""
        firmware_match = re.search(r"(V\d+\.\d+\w*)", output)
        if firmware_match:
            firmware = firmware_match.group(1)
        return InstrumentIdentity(
            raw=output.strip() or "J-Link (no version reported)",
            manufacturer="SEGGER",
            model=model,
            serial_number=serial,
            firmware=firmware,
        )

    # ------------------------------------------------------------------
    # Symbols and attachment
    # ------------------------------------------------------------------
    def load_symbols(self, elf: str) -> None:
        """Load debug symbols from an ELF file.

        Required for variables by name, source-line breakpoints and call stacks.
        """
        if not os.path.exists(elf) and self._target_address != "simulated":
            raise ConfigurationError("no such ELF file: %s" % elf)
        self._session.execute('-file-exec-and-symbols "%s"' % elf.replace("\\", "/"))
        self._elf = elf

    def attach(self) -> None:
        """Attach GDB to the target through the GDB Server."""
        address = self._target_address if self._target_address != "simulated" else "sim:0"
        record = self._session.execute(
            "-target-select extended-remote %s" % address, allow_error=True, timeout=30.0
        )
        if record.is_error:
            raise ConnectionFailedError(
                "could not attach to the target at %s: %s. Check the probe is "
                "connected, the target is powered, and the device name is right."
                % (address, record.error_message)
            )
        self._attached = True
        self._halted = True

    @property
    def is_attached(self) -> bool:
        """``True`` once GDB is attached to the target."""
        return self._attached

    def monitor(self, command: str, timeout: Optional[float] = None) -> str:
        """Send a J-Link ``monitor`` command and return its output.

        The escape hatch for probe features the driver does not wrap -
        ``monitor reset``, ``monitor semihosting enable``, ``monitor flash
        breakpoints``.
        """
        return self._session.execute_console("monitor %s" % command, timeout=timeout).text

    # ------------------------------------------------------------------
    # Flash and verify
    # ------------------------------------------------------------------
    def flash(
        self,
        path: Optional[str] = None,
        verify: bool = True,
        reset: bool = True,
        timeout: float = 180.0,
    ) -> FlashResult:
        """Program an image onto the target.

        :param path: Image to program; the loaded ELF when omitted.
        :param verify: Compare the target against the file afterwards. On by
            default: programming that silently half-succeeded is the failure this
            catches, and it is cheap next to the write.
        :param reset: Reset and halt before programming. On by default, because
            programming a running target corrupts whatever it was doing.
        :param timeout: Seconds to allow; flashing a large image is slow.
        :raises BenchToolsError: if verification was requested and failed.
        """
        if path:
            self.load_symbols(path)
        if not self._elf:
            raise ConfigurationError(
                "no image to flash: pass path=... or construct the probe with elf=..."
            )
        if reset:
            self.reset(halt=True)

        started = time.monotonic()
        console = self._session.execute_console("load", timeout=timeout)
        elapsed = time.monotonic() - started

        sections: Dict[str, Tuple[int, int]] = {}
        for match in _LOAD_RE.finditer(console.text):
            sections[match.group("name")] = (
                int(match.group("lma"), 16),
                int(match.group("size"), 16),
            )
        if not sections:
            raise BenchToolsError(
                "flashing reported no sections loaded, so nothing was programmed.\n"
                "GDB said:\n%s" % (console.text or "(no output)")
            )
        result = FlashResult(sections=sections, output=console.text, seconds=elapsed)
        _LOG.info(
            "flashed %d bytes in %d section(s) in %.2f s",
            result.bytes_written, len(sections), elapsed,
        )

        if verify:
            result.verify = self.verify(timeout=timeout)
            if not result.verify.matched:
                raise BenchToolsError(
                    "flash verification failed: section(s) %s do not match %s"
                    % (", ".join(result.verify.mismatched) or "none reported", self._elf)
                )
        self._cycle_counter_ready = False
        return result

    def image_build(self, path: Optional[str] = None) -> FirmwareBuild:
        """What the build system said about the image on the target.

        The probe knows which file it flashed; the build that produced that file
        writes a ``firmware_manifest.json`` beside it. Reading that is how a
        test can state the version it *put* on the part, rather than repeating a
        version string into a specification where it will go stale silently.

        This is a claim about the **file**, not about the part. It is worth
        saying because that is exactly what makes it useful: comparing it with
        what the running firmware reports over its own link is a real check on
        two independent things agreeing, and a version typed into a
        specification would make that comparison circular.

        :param path: Manifest, or a directory holding one. Defaults to the
            ``firmware`` the probe was configured with, then to beside the image
            currently loaded.
        :raises ConfigurationError: if there is no image and no path, or no
            manifest where it looked.

        Traces to: JLINK-FR-024.
        """
        target = path or self._firmware or self._elf
        if not target:
            raise ConfigurationError(
                "no image to describe: pass path=..., or give the probe "
                "firmware=<build directory> (or elf=..., and the manifest "
                "beside it is used)"
            )
        if os.path.isdir(target) or os.path.basename(target) == MANIFEST_NAME:
            where = target
        else:
            # An image rather than a manifest: the manifest is its neighbour.
            where = os.path.dirname(os.path.abspath(target)) or "."
        return FirmwareBuild.load(
            where,
            hint=(
                "The manifest is written by the build that produced the image; "
                "build the target firmware, or point image_build at the "
                "directory holding its manifest."
            ),
        )

    def verify(self, path: Optional[str] = None, timeout: float = 180.0) -> VerifyResult:
        """Compare the target's memory against an image file.

        Uses GDB's ``compare-sections``, which reads the target back and
        compares against the file's loadable sections.
        """
        if path:
            self.load_symbols(path)
        console = self._session.execute_console("compare-sections", timeout=timeout)
        sections = [
            SectionVerdict(
                name=match.group("name"),
                start=int(match.group("start"), 16),
                end=int(match.group("end"), 16),
                matched=match.group("verdict").lower() == "matched",
            )
            for match in _COMPARE_RE.finditer(console.text)
        ]
        return VerifyResult(sections=sections, output=console.text)

    def erase(self, timeout: float = 120.0) -> str:
        """Erase the target's flash."""
        return self.monitor("flash erase", timeout=timeout)

    # ------------------------------------------------------------------
    # Run control
    # ------------------------------------------------------------------
    def reset(self, halt: bool = True, timeout: float = 30.0) -> None:
        """Reset the target.

        :param halt: Hold the core halted after reset. On by default: resetting
            into a running target and then halting it races the start-up code, so
            a test would sometimes catch ``main`` and sometimes the reset handler.
        """
        self.monitor("reset" if halt else "reset 0", timeout=timeout)
        if halt:
            self.monitor("halt", timeout=timeout)
            self._halted = True
        else:
            self._halted = False
        self._cycle_counter_ready = False

    def run(self, timeout: Optional[float] = None) -> None:
        """Let the target run. Returns as soon as it is running."""
        self._session.clear_async()
        self._session.execute("-exec-continue", timeout=timeout)
        self._halted = False

    #: ``resume`` reads better in a sequence that has just halted.
    resume = run

    def halt(self, timeout: float = 10.0) -> HaltInfo:
        """Halt the target and report where it stopped."""
        if self._halted:
            return self._halt_info({"reason": "signal-received"})
        self._session.execute("-exec-interrupt", timeout=timeout, allow_error=True)
        info = self.wait_for_halt(timeout=timeout)
        return info

    #: ``stop`` is the name a test author reaches for.
    stop = halt

    def step(self, over: bool = True, instruction: bool = False, timeout: float = 10.0) -> HaltInfo:
        """Execute one step and report where the target stopped.

        :param over: Step over a call rather than into it.
        :param instruction: Step one machine instruction instead of one line.
        """
        command = (
            "-exec-step-instruction" if instruction else ("-exec-next" if over else "-exec-step")
        )
        self._session.clear_async()
        self._session.execute(command, timeout=timeout)
        return self.wait_for_halt(timeout=timeout)

    def wait_for_halt(self, timeout: float = 30.0) -> HaltInfo:
        """Wait for the target to stop and report why.

        :raises TransportTimeoutError: if it does not stop, which usually means
            the breakpoint was never reached.
        """
        results = self._session.wait_for_stop(timeout=timeout)
        self._halted = True
        return self._halt_info(results)

    def _halt_info(self, results: Dict[str, Any]) -> HaltInfo:
        frame = results.get("frame") or {}
        number = results.get("bkptno")
        return HaltInfo(
            reason=HaltReason.from_mi(str(results.get("reason", "unknown"))),
            function=str(frame.get("func", "")),
            file=str(frame.get("file", "")),
            line=int(frame.get("line", 0) or 0),
            address=int(str(frame.get("addr", "0x0")), 16) if frame.get("addr") else 0,
            breakpoint_number=int(number) if number and str(number).isdigit() else None,
            signal=str(results.get("signal-name", "")),
        )

    @property
    def is_halted(self) -> bool:
        """``True`` when the driver believes the target is halted."""
        return self._halted

    def program_counter(self) -> int:
        """Read the program counter."""
        record = self._session.execute("-data-list-register-values x 15")
        values = record.results.get("register-values") or []
        for entry in values:
            if isinstance(entry, dict) and entry.get("number") == "15":
                return int(str(entry.get("value", "0")), 16)
        raise ProtocolError("GDB did not report the program counter")

    def registers(self) -> Dict[str, int]:
        """Read every core register, by name."""
        names = self._session.execute("-data-list-register-names").results.get(
            "register-names"
        ) or []
        values = self._session.execute("-data-list-register-values x").results.get(
            "register-values"
        ) or []
        out: Dict[str, int] = {}
        for entry in values:
            if not isinstance(entry, dict):
                continue
            index = int(entry.get("number", "-1"))
            if 0 <= index < len(names) and names[index]:
                try:
                    out[str(names[index])] = int(str(entry.get("value", "0")), 16)
                except ValueError:
                    continue
        return out

    # ------------------------------------------------------------------
    # Breakpoints
    # ------------------------------------------------------------------
    def set_breakpoint(
        self,
        location: str,
        temporary: bool = False,
        hardware: bool = False,
        condition: Optional[str] = None,
    ) -> Breakpoint:
        """Set a breakpoint.

        :param location: ``"file.c:123"``, a function name, or ``"*0x08001234"``.
        :param temporary: Delete the breakpoint when it is first hit.
        :param hardware: Use a hardware comparator. Needed in flash on most
            Cortex-M parts, and limited to a handful.
        :param condition: A C expression; the target stops only when it is true.
        :raises ConfigurationError: if no hardware comparator is free.
        """
        if hardware:
            used = sum(
                1 for entry in self.list_breakpoints()
                if entry.kind is BreakpointKind.HARDWARE
            )
            if used >= self._limits.max_hardware_breakpoints:
                raise ConfigurationError(
                    "all %d hardware breakpoints on the %s are in use; delete one "
                    "first, or use a software breakpoint if the location is in RAM"
                    % (self._limits.max_hardware_breakpoints, self._limits.model)
                )
        arguments = []
        if temporary:
            arguments.append("-t")
        if hardware:
            arguments.append("-h")
        if condition:
            arguments.append('-c "%s"' % condition)
        arguments.append(location)

        record = self._session.execute("-break-insert %s" % " ".join(arguments))
        return self._breakpoint_from_mi(record.results.get("bkpt") or {}, location, temporary, hardware)

    def _breakpoint_from_mi(
        self, entry: Dict[str, Any], location: str, temporary: bool, hardware: bool
    ) -> Breakpoint:
        kind = BreakpointKind.SOFTWARE
        if temporary:
            kind = BreakpointKind.TEMPORARY
        elif hardware or str(entry.get("type", "")).startswith("hw"):
            kind = BreakpointKind.HARDWARE
        return Breakpoint(
            number=int(entry.get("number", 0) or 0),
            location=location,
            address=int(str(entry.get("addr", "0x0")), 16) if entry.get("addr") else 0,
            function=str(entry.get("func", "")),
            file=str(entry.get("file", "")),
            line=int(entry.get("line", 0) or 0),
            kind=kind,
            condition=str(entry.get("cond", "")),
        )

    def set_watchpoint(
        self,
        expression: str,
        kind: Union[WatchpointKind, str] = WatchpointKind.WRITE,
    ) -> Watchpoint:
        """Stop the target when a variable is accessed.

        :param expression: Usually a variable name.
        :param kind: ``WRITE``, ``READ`` or ``ACCESS``.
        """
        chosen = WatchpointKind.coerce(kind)
        flag = {"WRITE": "", "READ": "-r", "ACCESS": "-a"}[chosen.value]
        record = self._session.execute(
            "-break-watch %s %s" % (flag, expression) if flag else "-break-watch %s" % expression
        )
        entry = (
            record.results.get("wpt")
            or record.results.get("hw-rwpt")
            or record.results.get("hw-awpt")
            or {}
        )
        return Watchpoint(
            number=int(entry.get("number", 0) or 0),
            expression=str(entry.get("exp", expression)),
            kind=chosen,
        )

    def list_breakpoints(self) -> List[Breakpoint]:
        """Return the breakpoints currently set."""
        record = self._session.execute("-break-list")
        table = record.results.get("BreakpointTable") or {}
        body = table.get("body") or []
        entries = body if isinstance(body, list) else [body]
        out: List[Breakpoint] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            location = "%s:%s" % (entry.get("file", ""), entry.get("line", "")) if entry.get("file") else str(entry.get("func", ""))
            out.append(
                self._breakpoint_from_mi(
                    entry, location, str(entry.get("disp")) == "del",
                    str(entry.get("type", "")).startswith("hw"),
                )
            )
        return out

    def delete_breakpoint(self, number: int) -> None:
        """Delete one breakpoint or watchpoint by number."""
        self._session.execute("-break-delete %d" % int(number))

    def clear_breakpoints(self) -> None:
        """Delete every breakpoint and watchpoint."""
        self._session.execute("-break-delete")

    def run_to(self, location: str, timeout: float = 30.0) -> HaltInfo:
        """Set a temporary breakpoint, run, and wait for it.

        The common shape of a bench step: get the target to a known place.
        """
        self.set_breakpoint(location, temporary=True)
        self.run()
        return self.wait_for_halt(timeout=timeout)

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    def read_memory(self, address: int, size: int) -> bytes:
        """Read *size* bytes from *address*.

        Transfers larger than the probe's limit are split, so a caller can ask
        for a whole RAM region without knowing the chunk size.
        """
        if size < 0:
            raise ConfigurationError("size must not be negative, got %r" % (size,))
        if size == 0:
            return b""
        chunk = self._limits.max_transfer_bytes
        out = bytearray()
        offset = 0
        while offset < size:
            count = min(chunk, size - offset)
            record = self._session.execute(
                "-data-read-memory-bytes 0x%x %d" % (address + offset, count)
            )
            blocks = record.results.get("memory") or []
            if not blocks:
                raise ProtocolError(
                    "GDB returned no data for %d bytes at 0x%08x" % (count, address + offset)
                )
            block = blocks[0] if isinstance(blocks, list) else blocks
            contents = str(block.get("contents", ""))
            try:
                data = bytes.fromhex(contents)
            except ValueError as exc:
                raise ProtocolError("unparsable memory contents %r" % contents[:40]) from exc
            if not data:
                raise ProtocolError("GDB returned an empty block at 0x%08x" % (address + offset))
            out += data
            offset += len(data)
        return bytes(out[:size])

    def write_memory(self, address: int, data: bytes) -> None:
        """Write *data* to *address*, splitting large transfers."""
        payload = bytes(data)
        chunk = self._limits.max_transfer_bytes
        for offset in range(0, len(payload), chunk):
            piece = payload[offset : offset + chunk]
            self._session.execute(
                '-data-write-memory-bytes 0x%x "%s"' % (address + offset, piece.hex())
            )

    def read_word(self, address: int) -> int:
        """Read one little-endian 32-bit word."""
        return int.from_bytes(self.read_memory(address, 4), "little")

    def write_word(self, address: int, value: int) -> None:
        """Write one little-endian 32-bit word."""
        self.write_memory(address, int(value & 0xFFFFFFFF).to_bytes(4, "little"))

    def read_u8(self, address: int) -> int:
        """Read one byte."""
        return self.read_memory(address, 1)[0]

    def read_u16(self, address: int) -> int:
        """Read one little-endian 16-bit halfword."""
        return int.from_bytes(self.read_memory(address, 2), "little")

    #: Reading RAM is reading memory; the alias is for readability in specs.
    read_ram = read_memory
    write_ram = write_memory

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def read_variable(self, name: str) -> Any:
        """Read a variable by name, converted to a Python value.

        Needs symbols. Integers, floats, strings, pointers and simple structures
        are converted; anything else is returned as GDB's own text, which is
        better than guessing.
        """
        record = self._session.execute(
            '-data-evaluate-expression "%s"' % name, allow_error=True
        )
        if record.is_error:
            raise MeasurementError(
                "cannot read %r: %s%s"
                % (
                    name,
                    record.error_message,
                    "" if self._elf else " (no ELF file is loaded, so there are no symbols)",
                )
            )
        return self._parse_gdb_value(str(record.results.get("value", "")))

    def write_variable(self, name: str, value: Any) -> None:
        """Write a variable by name."""
        if isinstance(value, bool):
            text = "1" if value else "0"
        elif isinstance(value, (int, float)):
            text = repr(value)
        else:
            text = '"%s"' % value
        record = self._session.execute_console(
            "set var %s=%s" % (name, text), allow_error=True
        )
        if record.record.is_error:
            raise MeasurementError(
                "cannot write %r: %s" % (name, record.record.error_message)
            )
        self._after_configuration()

    def variable_address(self, name: str) -> int:
        """Address of a variable."""
        value = self._session.execute(
            '-data-evaluate-expression "&%s"' % name, allow_error=True
        )
        if value.is_error:
            raise MeasurementError("cannot take the address of %r: %s" % (name, value.error_message))
        match = re.search(r"0x[0-9a-fA-F]+", str(value.results.get("value", "")))
        if not match:
            raise ProtocolError(
                "GDB gave no address for %r: %r" % (name, value.results.get("value"))
            )
        return int(match.group(0), 16)

    def variable_size(self, name: str) -> int:
        """Size of a variable in bytes."""
        value = self._session.execute(
            '-data-evaluate-expression "sizeof(%s)"' % name, allow_error=True
        )
        if value.is_error:
            raise MeasurementError("cannot size %r: %s" % (name, value.error_message))
        return int(str(value.results.get("value", "0")).strip(), 0)

    def evaluate(self, expression: str) -> Any:
        """Evaluate an arbitrary C expression in the target's context."""
        record = self._session.execute(
            '-data-evaluate-expression "%s"' % expression.replace('"', '\\"'),
            allow_error=True,
        )
        if record.is_error:
            raise MeasurementError(
                "cannot evaluate %r: %s" % (expression, record.error_message)
            )
        return self._parse_gdb_value(str(record.results.get("value", "")))

    @staticmethod
    def _parse_gdb_value(text: str) -> Any:
        """Convert GDB's rendering of a value into a Python object."""
        value = text.strip()
        if not value:
            return None
        # A pointer or a cast: "(uint32_t *) 0x20000104".
        pointer = re.match(r"^\([^)]*\)\s*(0x[0-9a-fA-F]+)", value)
        if pointer:
            return int(pointer.group(1), 16)
        # A quoted string, possibly preceded by an address for a char array.
        quoted = re.search(r'"((?:[^"\\]|\\.)*)"', value)
        if quoted and (value.startswith('"') or "0x" in value.split('"')[0]):
            return quoted.group(1)
        # An enum rendered as "2" or as its name.
        try:
            return int(value, 0)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        # A structure: "{a = 1, b = 2}".
        if value.startswith("{") and value.endswith("}"):
            fields: Dict[str, Any] = {}
            for part in re.split(r",(?![^{]*\})", value[1:-1]):
                if "=" not in part:
                    continue
                key, _, item = part.partition("=")
                fields[key.strip()] = JLinkProbe._parse_gdb_value(item)
            if fields:
                return fields
        return value

    # ------------------------------------------------------------------
    # Call stack
    # ------------------------------------------------------------------
    def call_stack(self, limit: Optional[int] = None) -> List[StackFrame]:
        """Return the target's call stack, innermost frame first.

        Needs symbols and the target halted. Unwinding is GDB's, so it is as good
        as the debug information in the ELF.
        """
        command = "-stack-list-frames"
        if limit is not None:
            if limit < 1:
                raise ConfigurationError("limit must be at least 1, got %r" % (limit,))
            command += " 0 %d" % (limit - 1)
        record = self._session.execute(command, allow_error=True)
        if record.is_error:
            raise MeasurementError(
                "cannot read the call stack: %s%s"
                % (
                    record.error_message,
                    "" if self._halted else " (the target must be halted)",
                )
            )
        frames = record.results.get("stack") or []
        out: List[StackFrame] = []
        for entry in frames if isinstance(frames, list) else [frames]:
            if not isinstance(entry, dict):
                continue
            out.append(
                StackFrame(
                    level=int(entry.get("level", len(out)) or 0),
                    function=str(entry.get("func", "")),
                    file=str(entry.get("file", "")),
                    line=int(entry.get("line", 0) or 0),
                    address=int(str(entry.get("addr", "0x0")), 16) if entry.get("addr") else 0,
                )
            )
        return out

    #: ``backtrace`` is what a GDB user will look for.
    backtrace = call_stack

    # ------------------------------------------------------------------
    # RTT
    # ------------------------------------------------------------------
    def rtt_start(self, log_path: Optional[str] = None, channel: int = 0) -> None:
        """Start RTT, optionally logging everything to a file."""
        if channel >= self._limits.max_rtt_channels:
            raise ConfigurationError(
                "channel %d is beyond the %d configured RTT channels"
                % (channel, self._limits.max_rtt_channels)
            )
        self.monitor("rtt start", timeout=10.0)
        self.rtt.start(log_path=log_path)

    def rtt_stop(self) -> None:
        """Stop RTT and close any log."""
        if self._rtt is not None:
            self._rtt.stop()

    def rtt_read_lines(self) -> List[str]:
        """Return and consume the RTT lines received so far."""
        return self.rtt.read_lines()

    def rtt_write(self, text: str) -> None:
        """Send a line to the target over RTT."""
        self.rtt.write(text)

    def rtt_expect(self, pattern: str, timeout: float = 5.0):
        """Wait for an RTT line matching *pattern* and return the match."""
        return self.rtt.expect(pattern, timeout=timeout)

    def rtt_lines_within(self, timeout: float = 2.0) -> int:
        """Count the RTT lines the target emits within *timeout* seconds.

        "Is it running?" is a question about output arriving at all, and a
        silent target is a **failed test**, not a broken bench. Waiting for a
        pattern raises on timeout, which a runner records as an error - the
        wrong verdict for a sensor that started and said nothing. This returns a
        count instead, so a specification bounds it like any other measurement
        (``min: 1``) and a silence is a failure with a number beside it.

        Lines are consumed, as :meth:`rtt_read_lines` consumes them; they remain
        in :attr:`rtt_log`.

        Traces to: JLINK-FR-054.
        """
        deadline = time.monotonic() + max(0.0, float(timeout))
        seen = len(self.rtt_read_lines())
        while seen == 0 and time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            seen += len(self.rtt_read_lines())
        _LOG.info("%d RTT line(s) within %.2f s", seen, timeout)
        return seen

    def rtt_command(self, text: str, pattern: str = ".+", timeout: float = 5.0):
        """Send an RTT command and wait for its reply."""
        return self.rtt.command(text, pattern=pattern, timeout=timeout)

    @property
    def rtt_log(self) -> List[str]:
        """Every RTT line received since RTT started."""
        return self.rtt.history

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------
    def enable_cycle_counter(self) -> None:
        """Enable the Cortex-M DWT cycle counter.

        Sets ``TRCENA`` in DEMCR and ``CYCCNTENA`` in DWT_CTRL. Without both, the
        cycle counter reads zero and every cycle-based measurement silently
        returns nothing.
        """
        self.write_word(DEMCR, self.read_word(DEMCR) | DEMCR_TRCENA)
        self.write_word(DWT_CTRL, self.read_word(DWT_CTRL) | DWT_CTRL_CYCCNTENA)
        self._cycle_counter_ready = True

    def read_cycle_counter(self) -> int:
        """Read the DWT cycle counter."""
        if not self._cycle_counter_ready:
            self.enable_cycle_counter()
        return self.read_word(DWT_CYCCNT)

    def measure_time_between(
        self,
        start: str,
        end: str,
        method: Union[TimingMethod, str] = TimingMethod.CYCLE_COUNTER,
        repeat: int = 1,
        timeout: float = 30.0,
        timer_variable: Optional[str] = None,
        timer_hz: Optional[float] = None,
        start_variable: Optional[str] = None,
        end_variable: Optional[str] = None,
        itm_port: int = 1,
        itm_prescaler: int = 1,
    ) -> TimingResult:
        """Measure the interval between two code locations.

        :param start: Location where the interval starts, e.g. ``"sensor.c:40"``.
        :param end: Location where it ends.
        :param method: See :class:`~benchtools.instruments.jlink.constants.TimingMethod`.
            The default counts core cycles and is the most accurate of the
            halting methods.
        :param repeat: Measure this many times and return statistics. Worth more
            than one whenever the interval might vary.
        :param timer_variable: ``TARGET_TIMER``: variable holding the target's own
            timer, read at both points.
        :param timer_hz: ``TARGET_TIMER``: tick rate of that timer.
        :param start_variable: ``TARGET_TIMER``: variable the firmware has already
            filled in at the start point, instead of reading a timer.
        :param end_variable: ``TARGET_TIMER``: the same for the end point.
        :param itm_port: ``SWO_ITM``: stimulus port the firmware writes to.
        :param itm_prescaler: ``SWO_ITM``: trace clock prescaler.
        :raises MeasurementError: if no sample could be taken.
        """
        chosen = TimingMethod.coerce(method)
        if repeat < 1:
            raise ConfigurationError("repeat must be at least 1, got %r" % (repeat,))

        if chosen is TimingMethod.SWO_ITM:
            return self._measure_swo(start, end, repeat, itm_port, itm_prescaler, timeout)
        if chosen is TimingMethod.TARGET_TIMER:
            if start_variable and end_variable:
                return self._measure_target_variables(
                    start, end, repeat, start_variable, end_variable, timer_hz, timeout
                )
            if not timer_variable:
                raise ConfigurationError(
                    "TARGET_TIMER needs either timer_variable=... (read at both "
                    "points) or both start_variable=... and end_variable=... "
                    "(filled in by the firmware)"
                )

        samples: List[TimingSample] = []
        if chosen is TimingMethod.CYCLE_COUNTER:
            self.enable_cycle_counter()

        start_bp = self.set_breakpoint(start)
        end_bp = self.set_breakpoint(end)
        try:
            for _ in range(repeat):
                self._run_to_breakpoint(start_bp, timeout)
                begin = self._sample_clock(chosen, timer_variable)
                self._run_to_breakpoint(end_bp, timeout)
                finish = self._sample_clock(chosen, timer_variable)
                samples.append(self._to_sample(chosen, begin, finish, timer_hz))
        finally:
            for breakpoint_ in (start_bp, end_bp):
                try:
                    self.delete_breakpoint(breakpoint_.number)
                except BenchToolsError:  # pragma: no cover - best effort cleanup
                    _LOG.debug("could not delete breakpoint %d", breakpoint_.number)

        return TimingResult(
            method=chosen,
            samples=samples,
            start=start,
            end=end,
            core_clock_hz=self.core_clock_hz if chosen is TimingMethod.CYCLE_COUNTER else None,
            halts_target=True,
        )

    def _run_to_breakpoint(self, breakpoint_: Breakpoint, timeout: float) -> None:
        """Resume and wait until *breakpoint_* is the one that hit."""
        deadline = time.monotonic() + timeout
        while True:
            self.run()
            info = self.wait_for_halt(timeout=max(deadline - time.monotonic(), 0.1))
            if info.breakpoint_number in (None, breakpoint_.number):
                return
            if time.monotonic() >= deadline:
                raise MeasurementError(
                    "never reached %s: stopped at %s instead"
                    % (breakpoint_.location, info.location)
                )

    def _sample_clock(self, method: TimingMethod, timer_variable: Optional[str]):
        if method is TimingMethod.CYCLE_COUNTER:
            return self.read_cycle_counter()
        if method is TimingMethod.HOST_CLOCK:
            return time.perf_counter()
        if method is TimingMethod.TARGET_TIMER:
            return int(self.read_variable(timer_variable))
        raise ConfigurationError("unsupported timing method %r" % method)

    def _to_sample(self, method: TimingMethod, begin, finish, timer_hz) -> TimingSample:
        if method is TimingMethod.CYCLE_COUNTER:
            cycles = self._counter_delta(int(begin), int(finish))
            return TimingSample(
                seconds=cycles / self.core_clock_hz, cycles=cycles,
                start_raw=begin, end_raw=finish,
            )
        if method is TimingMethod.HOST_CLOCK:
            return TimingSample(seconds=float(finish) - float(begin), start_raw=begin, end_raw=finish)
        ticks = self._counter_delta(int(begin), int(finish))
        rate = float(timer_hz) if timer_hz else self.core_clock_hz
        return TimingSample(
            seconds=ticks / rate, cycles=ticks, start_raw=begin, end_raw=finish
        )

    @staticmethod
    def _counter_delta(begin: int, finish: int) -> int:
        """Difference between two 32-bit counter readings, allowing one wrap.

        The DWT counter wraps every 2**32 cycles - 67 s at 64 MHz - and without
        this a wrapped interval reads as a huge negative number.
        """
        delta = finish - begin
        if delta < 0:
            delta += 1 << 32
        return delta

    def _measure_target_variables(
        self, start, end, repeat, start_variable, end_variable, timer_hz, timeout
    ) -> TimingResult:
        """Read two variables the firmware has already filled in."""
        samples: List[TimingSample] = []
        end_bp = self.set_breakpoint(end)
        try:
            for _ in range(repeat):
                self._run_to_breakpoint(end_bp, timeout)
                begin = int(self.read_variable(start_variable))
                finish = int(self.read_variable(end_variable))
                ticks = self._counter_delta(begin, finish)
                rate = float(timer_hz) if timer_hz else self.core_clock_hz
                samples.append(
                    TimingSample(seconds=ticks / rate, cycles=ticks, start_raw=begin, end_raw=finish)
                )
        finally:
            try:
                self.delete_breakpoint(end_bp.number)
            except BenchToolsError:  # pragma: no cover
                pass
        return TimingResult(
            method=TimingMethod.TARGET_TIMER, samples=samples, start=start, end=end,
            core_clock_hz=float(timer_hz) if timer_hz else self.core_clock_hz,
            halts_target=True,
        )

    def _measure_swo(self, start, end, repeat, port, prescaler, timeout) -> TimingResult:
        """Measure from ITM timestamps, without halting the target."""
        decoder = ItmDecoder(prescaler=prescaler)
        events = self._collect_itm(decoder, port, repeat, timeout)
        if len(events) < 2:
            raise MeasurementError(
                "SWO produced %d event(s) on port %d; two are needed for an "
                "interval. Check the SWO pin is wired, trace is enabled "
                "(monitor swo start), and the firmware writes to that port."
                % (len(events), port)
            )
        samples: List[TimingSample] = []
        for index in range(0, len(events) - 1, 2):
            begin, finish = events[index], events[index + 1]
            if begin.timestamp is None or finish.timestamp is None:
                continue
            ticks = finish.timestamp - begin.timestamp
            cycles = ticks * prescaler
            samples.append(
                TimingSample(
                    seconds=cycles / self.core_clock_hz, cycles=cycles,
                    start_raw=begin.timestamp, end_raw=finish.timestamp,
                )
            )
        return TimingResult(
            method=TimingMethod.SWO_ITM, samples=samples, start=start, end=end,
            core_clock_hz=self.core_clock_hz, halts_target=False,
        )

    def _collect_itm(self, decoder: ItmDecoder, port: int, repeat: int, timeout: float):
        """Gather ITM events, from the simulator or a real SWO stream.

        The simulator records ITM writes with their cycle counts as the target
        runs, so there is nothing to decode; a real probe streams raw ITM packets
        on the server's SWO port and those go through :class:`ItmDecoder`.
        """
        simulator = getattr(self._session.transport, "responder", None)
        if isinstance(simulator, SimulatedJLink):
            # The model records ITM writes with their cycle counts directly.
            self.run()
            for _ in range(max(repeat * 2, 2)):
                try:
                    self.wait_for_halt(timeout=1.0)
                    self.run()
                except BenchToolsError:
                    break
            return [
                type(
                    "SimEvent", (), {"timestamp": cycles, "port": channel, "value": value}
                )()
                for channel, value, cycles in simulator.itm_events
                if channel == port
            ][: repeat * 2]

        # A real probe: start trace, read the server's SWO port, decode.
        if self._server is None:
            raise MeasurementError(
                "SWO timing needs a GDB Server to read the trace stream from"
            )
        self.monitor("swo start", timeout=10.0)
        stream = SwoStream(
            host=self._server.host or "127.0.0.1",
            port=self._server.swo_port,
            prescaler=decoder.prescaler,
        )
        stream.open()
        try:
            self.run()
            return stream.collect(port=port, count=repeat * 2, timeout=timeout)
        finally:
            stream.close()
