"""Managing a J-Link GDB Server process.

The driver can either spawn a server or attach to one already running. Both
matter:

* **Spawning** is what a developer wants on a bench: one call and the probe is
  usable.
* **Attaching** is what a containerised bench needs. The probe is USB, so the
  server runs where the USB port is - on the Windows host - and the tests run
  elsewhere. Because GDB reaches the server over TCP, and RTT likewise, moving
  the tests into a container changes an address and nothing else.

Traces to: JLINK-FR-003, JLINK-FR-004, JLINK-DD-SERVER.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from typing import Deque, Iterable, List, Optional

from ...core.errors import ConnectionFailedError
from .constants import (
    DEFAULT_GDB_PORT,
    DEFAULT_RTT_PORT,
    DEFAULT_SWO_PORT,
    DEFAULT_TELNET_PORT,
    DebugInterface,
)

__all__ = ["GdbServer", "find_gdb_server", "find_gdb", "gdb_debugs_arm", "port_is_open"]

_LOG = logging.getLogger(__name__)

#: Server output kept for a diagnostic: enough to show why it stopped.
_OUTPUT_LINES = 200

#: Lines of the start-up banner kept for identifying the probe. The serial
#: number and firmware appear within the first fifty.
_BANNER_LINES = 80

#: Executable names to look for, in order. The Windows names come first because
#: that is where this is used first, and a POSIX host will simply not match them.
_SERVER_NAMES = (
    "JLinkGDBServerCL.exe",
    "JLinkGDBServer.exe",
    "JLinkGDBServerCLExe",
    "JLinkGDBServer",
)

#: GDB executables that are built to debug an ARM target.
_ARM_GDB_NAMES = (
    "arm-none-eabi-gdb",
    "arm-none-eabi-gdb.exe",
    "gdb-multiarch",
)

#: A GDB that may or may not debug ARM: a host ``gdb`` usually does not (MinGW's
#: is i386-only), so it is accepted only after asking it.
_HOST_GDB_NAMES = ("gdb",)

#: Where the SEGGER installer puts the J-Link software: one directory per
#: release, e.g. ``JLink_V942``.
_SERVER_DIRECTORIES = (
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "SEGGER", "JLink*"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 "SEGGER", "JLink*"),
    "/opt/SEGGER/JLink*",
)

#: Where the Arm GNU Toolchain installers put GDB: a ``bin`` directory below one
#: directory per release, e.g. ``14.2 rel1``.
_GDB_DIRECTORIES = (
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 "Arm GNU Toolchain arm-none-eabi", "*", "bin"),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                 "Arm GNU Toolchain arm-none-eabi", "*", "bin"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 "GNU Arm Embedded Toolchain", "*", "bin"),
    "/opt/arm-gnu-toolchain*/bin",
)


def _release(directory: str) -> tuple:
    """The release numbers in an install directory's name, for ranking.

    ``JLink_V942`` gives ``(942,)`` and beats ``JLink_V924a``; ``14.2 rel1/bin``
    gives ``(14, 2, 1)``. A directory with no number in its name, such as plain
    ``JLink``, gives ``()`` and ranks last: nothing says which release it holds.
    """
    name = os.path.basename(directory.rstrip("/\\"))
    if name.lower() == "bin":
        name = os.path.basename(os.path.dirname(directory.rstrip("/\\")))
    return tuple(int(number) for number in re.findall(r"\d+", name))


def _installed(patterns: Iterable[str], names: Iterable[str]) -> List[str]:
    """Executables named *names* in the install directories *patterns*, newest
    release first."""
    found = []
    for pattern in patterns:
        for directory in glob.glob(pattern):
            for name in names:
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    found.append((_release(directory), candidate))
    found.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in found]


def find_gdb_server(explicit: Optional[str] = None) -> Optional[str]:
    """Locate a J-Link GDB Server executable.

    PATH is searched first, then the directories the SEGGER installer uses, so a
    standard installation works without naming the server on every call.

    :param explicit: A path to use if given; returned unchanged so a caller can
        always override the search.
    """
    if explicit:
        return explicit
    for name in _SERVER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    installed = _installed(_SERVER_DIRECTORIES, _SERVER_NAMES)
    return installed[0] if installed else None


def gdb_debugs_arm(executable: str, timeout: float = 10.0) -> bool:
    """Ask *executable* whether it can debug an ARM target.

    A host ``gdb`` answers ``Undefined item: "arm"``; picking one would fail
    only later, at attach, with an error that does not mention the cause.
    """
    try:
        completed = subprocess.run(
            [executable, "--batch", "-nx", "-ex", "set architecture arm"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = completed.stdout.decode("utf-8", errors="replace")
    return completed.returncode == 0 and "Undefined item" not in output


def find_gdb(explicit: Optional[str] = None) -> Optional[str]:
    """Locate a GDB able to debug an ARM target.

    A cross GDB on PATH wins, then one in the Arm toolchain's install
    directories, then a host ``gdb`` - but only if it says it can debug ARM.
    """
    if explicit:
        return explicit
    for name in _ARM_GDB_NAMES:
        found = shutil.which(name)
        if found:
            return found
    installed = _installed(_GDB_DIRECTORIES, _ARM_GDB_NAMES)
    if installed:
        return installed[0]
    for name in _HOST_GDB_NAMES:
        found = shutil.which(name)
        if found and gdb_debugs_arm(found):
            return found
    return None


def port_is_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return ``True`` if something is listening on *host*:*port*."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


class GdbServer:
    """A J-Link GDB Server, either spawned here or already running elsewhere.

    :param device: Target device name, e.g. ``"nRF52840_xxAA"``. Required when
        spawning: the server cannot choose a flash algorithm without it.
    :param interface: Debug interface.
    :param speed_khz: Interface speed in kHz; ``0`` selects adaptive.
    :param host: Host the server runs on. Anything but localhost implies an
        existing server, since one cannot be spawned remotely.
    :param port: GDB port.
    :param rtt_port: Port on which the server republishes RTT channel 0.
    :param serial_number: Probe serial number, to pick one of several probes.
    :param executable: Server path; searched for when omitted.
    :param extra_arguments: Further command-line arguments, verbatim.
    """

    def __init__(
        self,
        device: Optional[str] = None,
        interface: DebugInterface = DebugInterface.SWD,
        speed_khz: int = 4000,
        host: str = "127.0.0.1",
        port: int = DEFAULT_GDB_PORT,
        rtt_port: int = DEFAULT_RTT_PORT,
        swo_port: int = DEFAULT_SWO_PORT,
        telnet_port: int = DEFAULT_TELNET_PORT,
        serial_number: Optional[str] = None,
        executable: Optional[str] = None,
        extra_arguments: Optional[List[str]] = None,
        start_timeout: float = 15.0,
    ) -> None:
        self.device = device
        self.interface = DebugInterface.coerce(interface)
        self.speed_khz = int(speed_khz)
        self.host = host
        self.port = int(port)
        self.rtt_port = int(rtt_port)
        self.swo_port = int(swo_port)
        self.telnet_port = int(telnet_port)
        self.serial_number = serial_number
        self.executable = executable
        self.extra_arguments = list(extra_arguments or [])
        self.start_timeout = float(start_timeout)
        self._process: Optional[subprocess.Popen] = None
        self._spawned = False
        self._output: Deque[str] = deque(maxlen=_OUTPUT_LINES)
        self._banner: List[str] = []
        self._reader: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    @property
    def is_local(self) -> bool:
        """``True`` when the server is on this machine and may be spawned."""
        return self.host in ("localhost", "127.0.0.1", "::1", "")

    @property
    def was_spawned(self) -> bool:
        """``True`` if this object started the server and so must stop it."""
        return self._spawned

    @property
    def address(self) -> str:
        """Address GDB should connect to."""
        return "%s:%d" % (self.host or "127.0.0.1", self.port)

    def command_line(self) -> List[str]:
        """Build the server command line.

        ``-nogui`` matters on Windows: without it the server opens a window and
        waits, which hangs an unattended test run.

        ``-singlerun`` is deliberately absent. It makes the server exit when its
        first client disconnects, and the first client is :meth:`start`'s own
        readiness check, so GDB would find nothing listening. The server is
        stopped by :meth:`stop` instead. ``-silent`` is absent too: the
        server's output is drained, and its start-up banner is the only place
        the probe's serial number and firmware are reported.
        """
        executable = find_gdb_server(self.executable)
        if executable is None:
            raise ConnectionFailedError(
                "no J-Link GDB Server found. Install the SEGGER J-Link software, "
                "or pass server_executable=..., or point the driver at an "
                "already-running server with a host and port."
            )
        if not self.device:
            raise ConnectionFailedError(
                "a device name is required to start a GDB Server (for example "
                "device='nRF52840_xxAA'); the server cannot pick a flash "
                "algorithm without it"
            )
        arguments = [
            executable,
            "-device", str(self.device),
            "-if", self.interface.value,
            "-speed", ("adaptive" if self.speed_khz == 0 else str(self.speed_khz)),
            "-port", str(self.port),
            "-swoport", str(self.swo_port),
            "-telnetport", str(self.telnet_port),
            "-rtttelnetport", str(self.rtt_port),
            "-nogui",
            "-strict",
        ]
        if self.serial_number:
            arguments += ["-select", "usb=%s" % self.serial_number]
        return arguments + self.extra_arguments

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Ensure a server is reachable, spawning one if needed.

        An already-listening port is used as it stands. That is deliberate: on a
        shared bench the server is often started by hand or by a service, and
        spawning a second one would fail obscurely on the USB device already
        being claimed.
        """
        if port_is_open(self.host or "127.0.0.1", self.port):
            _LOG.info("using the GDB Server already listening on %s", self.address)
            return
        if not self.is_local:
            raise ConnectionFailedError(
                "nothing is listening on %s, and a GDB Server cannot be started "
                "on another machine. Start it on that host, or use a local probe."
                % self.address
            )

        arguments = self.command_line()
        _LOG.info("starting %s", " ".join(arguments))
        try:
            self._process = subprocess.Popen(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            raise ConnectionFailedError(
                "cannot start %r: %s" % (arguments[0], exc)
            ) from exc
        self._spawned = True
        self._output.clear()
        self._banner = []
        self._reader = threading.Thread(
            target=self._drain, name="jlink-gdb-server-output", daemon=True
        )
        self._reader.start()

        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            if port_is_open(self.host or "127.0.0.1", self.port):
                _LOG.info("GDB Server listening on %s", self.address)
                return
            if self._process.poll() is not None:
                output = self._read_output()
                raise ConnectionFailedError(
                    "the GDB Server exited with status %s before it started "
                    "listening.%s" % (self._process.returncode, output)
                )
            time.sleep(0.1)

        output = self._read_output()
        self.stop()
        raise ConnectionFailedError(
            "the GDB Server did not start listening on %s within %.0f s.%s"
            % (self.address, self.start_timeout, output)
        )

    def _drain(self) -> None:
        """Read the server's output until it closes.

        An undrained pipe fills, and the server then blocks on its next write -
        in the middle of a flash download, as likely as anywhere.
        """
        process = self._process
        stream = process.stdout if process is not None else None
        if stream is None:
            return
        pending = b""
        while True:
            try:
                data = stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096)
            except (OSError, ValueError):  # pragma: no cover - pipe closed under us
                break
            if not data:
                break
            pending += data
            *lines, pending = pending.split(b"\n")
            for line in lines:
                self._keep(line)
        if pending:
            self._keep(pending)

    def _keep(self, raw: bytes) -> None:
        line = raw.decode("utf-8", errors="replace").rstrip("\r")
        self._output.append(line)
        if len(self._banner) < _BANNER_LINES:
            self._banner.append(line)

    def _read_output(self) -> str:
        if self._reader is not None:
            self._reader.join(timeout=1.0)
        text = "\n".join(self._output).strip()
        return ("\nServer output:\n" + text) if text else ""

    @property
    def output(self) -> List[str]:
        """The most recent lines the server printed, if this object started it."""
        return list(self._output)

    def probe_identity(self) -> dict:
        """What the server's start-up banner says about the probe.

        Keys ``serial_number``, ``firmware`` and ``hardware``, each present only
        if the banner stated it. Empty for a server this object did not start:
        a server that was already running printed its banner elsewhere.
        """
        text = "\n".join(self._banner)
        found = {}
        for key, pattern in (
            ("serial_number", r"^S/N:\s*(\d+)"),
            ("firmware", r"^Firmware:\s*(.+?)\s*$"),
            ("hardware", r"^Hardware:\s*(.+?)\s*$"),
        ):
            match = re.search(pattern, text, re.M)
            if match:
                found[key] = match.group(1)
        return found

    def stop(self) -> None:
        """Stop the server, but only if this object started it."""
        process, self._process = self._process, None
        if process is None or not self._spawned:
            return
        self._spawned = False
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:  # pragma: no cover - stubborn server
                process.kill()
                process.wait(timeout=5.0)
        if process.stdout is not None:
            try:
                process.stdout.close()
            except OSError:  # pragma: no cover
                pass
        if self._reader is not None:
            self._reader.join(timeout=1.0)
            self._reader = None

    def __enter__(self) -> "GdbServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False
