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

import logging
import os
import shutil
import socket
import subprocess
import time
from typing import List, Optional

from ...core.errors import ConnectionFailedError
from .constants import (
    DEFAULT_GDB_PORT,
    DEFAULT_RTT_PORT,
    DEFAULT_SWO_PORT,
    DEFAULT_TELNET_PORT,
    DebugInterface,
)

__all__ = ["GdbServer", "find_gdb_server", "find_gdb", "port_is_open"]

_LOG = logging.getLogger(__name__)

#: Executable names to look for, in order. The Windows names come first because
#: that is where this is used first, and a POSIX host will simply not match them.
_SERVER_NAMES = (
    "JLinkGDBServerCL.exe",
    "JLinkGDBServer.exe",
    "JLinkGDBServerCLExe",
    "JLinkGDBServer",
)

#: GDB executables that can debug an ARM target.
_GDB_NAMES = (
    "arm-none-eabi-gdb",
    "arm-none-eabi-gdb.exe",
    "gdb-multiarch",
    "gdb",
)


def find_gdb_server(explicit: Optional[str] = None) -> Optional[str]:
    """Locate a J-Link GDB Server executable.

    :param explicit: A path to use if given; returned unchanged so a caller can
        always override the search.
    """
    if explicit:
        return explicit
    for name in _SERVER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_gdb(explicit: Optional[str] = None) -> Optional[str]:
    """Locate a GDB able to debug an ARM target."""
    if explicit:
        return explicit
    for name in _GDB_NAMES:
        found = shutil.which(name)
        if found:
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

        ``-nogui`` and ``-silent`` matter on Windows: without them the server
        opens a window and waits, which hangs an unattended test run.
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
            "-silent",
            "-singlerun",
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

    def _read_output(self) -> str:
        if self._process is None or self._process.stdout is None:
            return ""
        try:
            data = self._process.stdout.read(4096) or b""
        except OSError:  # pragma: no cover - pipe closed
            return ""
        text = data.decode("utf-8", errors="replace").strip()
        return ("\nServer output:\n" + text) if text else ""

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

    def __enter__(self) -> "GdbServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False
