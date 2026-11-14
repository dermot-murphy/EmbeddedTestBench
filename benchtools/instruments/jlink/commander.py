"""Running SEGGER's own tools: J-Link Commander command files and RTT Logger.

The ``segger`` backend (#71) drives the probe with no GDB. Each operation is
one run of ``JLink.exe`` with a command file: the tool connects, runs the
commands and exits. Nothing is held open between operations, so a run that
fails leaves no session behind to confuse the next one.

**What was checked, and how (ETB-RISK-004).** The command-line options and the
command syntax used here were read from J-Link V9.42 itself on 2026-11-13: the
help and diagnostic strings inside ``JLink.exe`` and ``JLinkRTTLogger.exe``.
The local manual, UM08001, no longer carries the command reference. Neither
tool was run against a probe to write this. What each output line means is
therefore known from the tool's own message text, not from a run; the bench
check of the ``segger`` backend is still to do.

From those strings:

* options ``-Device``, ``-If``, ``-Speed``, ``-USB``, ``-AutoConnect``,
  ``-NoGui`` and ``-CommandFile``; ``-AutoConnect`` and ``-NoGui`` take a
  value ("ERROR while parsing value for -AutoConnect.").
* commands ``ExitOnError <1|0>``, ``Halt``/``h``, ``Go``/``g``, ``Erase``
  (with no range: "'Erase Chip' will be executed"),
  ``loadfile <filename> [, <Addr>] [, <noreset | reset>]``,
  ``savebin <filename>, <addr>, <NumBytes> (hex)``, ``w1``/``w4
  [<Zone>:]<Addr>, <Data> (hex)``, and ``q`` to quit. ``r`` for reset is
  SEGGER's usual short name; its help text ("Reset CPU.") is in the binary but
  the name could not be read beside it, so ``r`` is unverified.
* banner lines ``S/N: %d``, ``Firmware: %s``, ``Hardware version: V%d.%.2d``.

Whether ``JLink.exe`` exits with a non-zero status when ``ExitOnError`` stops
it is not stated anywhere checked. A run is therefore judged by its status
**and** by its output: any line carrying one of :data:`ERROR_MARKERS`, each a
message the binary prints, fails the operation.

Traces to: JLINK-FR-007, JLINK-FR-008, JLINK-DD-COMMANDER.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Sequence

from ...core.errors import (
    BenchToolsError,
    ConfigurationError,
    ConnectionFailedError,
    TransportTimeoutError,
)
from ...core.events import SourceLogger
from .constants import DebugInterface
from .image import ImageRange, read_image
from .server import find_jlink_commander, find_rtt_logger

__all__ = [
    "ERROR_MARKERS",
    "CommanderError",
    "JLinkCommander",
    "RttLoggerBackend",
    "RttReadOnlyError",
    "SimulatedReadOnlyRtt",
    "check_output",
    "parse_banner",
    "file_argument",
    "number",
]

_LOG = logging.getLogger(__name__)

#: Messages ``JLink.exe`` V9.42 prints when a command or the connection fails,
#: each found in the binary's own strings (2026-11-13). A line holding any of
#: them fails the run, whatever the exit status says.
#:
#: Not among them: "J-Link connection not established yet but required for
#: command" and "Target connection not established yet ...". Commander prints
#: each before it connects, on every successful run, even with
#: ``-AutoConnect 1`` (5C1712, 2026-11-14, JLINK-OPEN-05). A failed connection
#: is reported by the lines that follow them.
ERROR_MARKERS = (
    "Could not connect to the target device",
    # "Connecting to J-Link via %s..." then "FAILED".
    "...FAILED",
    "Error while programming flash",
    "Writing target memory failed",
    "Could not write memory",
    "Failed to write memory",
    "Could not read memory",
    "Not all bytes could be read from target",
    "Failed to open file",
    "File is of unknown / unsupported format",
    "ERROR: Erase returned with error code",
    "Erase is not implemented",
    "Failed to halt CPU",
    "Unknown command",
    "Could not open J-Link Command File",
    "Failed to read J-Link Command File",
    "Please select a device with",
    "is unknown to this software version",
)


class CommanderError(BenchToolsError):
    """A J-Link Commander run failed.

    :param output: Everything the tool printed, which is the only diagnostic
        there is.
    """

    def __init__(self, message: str, output: str = "") -> None:
        self.output = output
        tail = "\n".join(output.strip().splitlines()[-25:])
        super().__init__("%s%s" % (message, ("\nJ-Link Commander said:\n" + tail) if tail else ""))


def number(value: int) -> str:
    """*value* as Commander's commands take it: hex, no prefix."""
    return "%X" % int(value)


def check_output(output: str, returncode: int, what: str) -> None:
    """Raise :class:`CommanderError` if the run failed by either test."""
    for line in output.splitlines():
        for marker in ERROR_MARKERS:
            if marker.lower() in line.lower():
                raise CommanderError("%s failed: %s" % (what, line.strip()), output)
    if returncode != 0:
        raise CommanderError("%s failed: JLink.exe exited with status %d"
                             % (what, returncode), output)


def parse_banner(output: str) -> Dict[str, str]:
    """What Commander's start-up lines say about the probe.

    Keys ``serial_number``, ``firmware``, ``hardware`` and ``version`` (of
    Commander itself), each present only if stated.
    """
    found = {}
    for key, pattern in (
        ("serial_number", r"^\s*S/N:\s*(\d+)"),
        ("firmware", r"^\s*Firmware:\s*(.+?)\s*$"),
        ("hardware", r"^\s*Hardware(?: version)?:\s*(.+?)\s*$"),
        ("version", r"SEGGER J-Link Commander\s+(V\S+)"),
    ):
        match = re.search(pattern, output, re.M)
        if match:
            found[key] = match.group(1)
    return found


def file_argument(path: str) -> str:
    """A file name as a command file carries it.

    Bare when it has no white space. With white space it is quoted, which
    Commander's help text neither shows nor rules out: unverified, and logged.
    """
    if re.search(r"\s", path):
        _LOG.warning("file name with a space passed to J-Link Commander in quotes, "
                     "which is not verified to work: %s", path)
        return '"%s"' % path
    return path


class JLinkCommander:  # pylint: disable=too-many-instance-attributes
    """Runs ``JLink.exe`` command files against a local probe.

    :param device: Target device name, e.g. ``"nRF52840_xxAA"``. Required:
        Commander cannot connect, erase or program without it.
    :param interface: Debug interface.
    :param speed_khz: Interface speed; ``0`` is adaptive.
    :param serial_number: Probe to use, by USB serial number.
    :param executable: ``JLink.exe``; searched for when omitted.
    :param timeout: Default seconds a run may take.
    """

    #: The tool's name in messages.
    NAME = "J-Link Commander"

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        device: Optional[str],
        interface: DebugInterface = DebugInterface.SWD,
        speed_khz: int = 4000,
        serial_number: Optional[str] = None,
        executable: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        self._logger = SourceLogger(_LOG)
        self.device = device
        self.interface = DebugInterface.coerce(interface)
        self.speed_khz = int(speed_khz)
        self.serial_number = serial_number
        self.executable = executable
        self.timeout = float(timeout)
        self._directory: Optional[str] = None
        self._runs = 0

    # ------------------------------------------------------------------
    @property
    def directory(self) -> str:
        """Where command files and read-back files go; made on first use."""
        if self._directory is None:
            self._directory = tempfile.mkdtemp(prefix="benchtools-jlink-")
        return self._directory

    def scratch(self, name: str) -> str:
        """A path for a file a command writes, unique within this runner."""
        self._runs += 1
        return os.path.join(self.directory, "%03d_%s" % (self._runs, name))

    def command_line(self, command_file: str) -> List[str]:
        """The ``JLink.exe`` command line for one command file."""
        executable = find_jlink_commander(self.executable)
        if executable is None:
            raise ConnectionFailedError(
                "no J-Link Commander (JLink.exe) found. Install the SEGGER J-Link "
                "software - it is normally in C:\\Program Files\\SEGGER\\JLink_<version> "
                "- or pass commander_executable=..., or use backend: gdb."
            )
        if not self.device:
            raise ConnectionFailedError(
                "a device name is required for the segger backend (for example "
                "device='nRF52840_xxAA'): J-Link Commander cannot connect to a "
                "target without it"
            )
        arguments = [
            executable,
            "-NoGui", "1",
            "-Device", str(self.device),
            "-If", self.interface.value,
            "-Speed", ("adaptive" if self.speed_khz == 0 else str(self.speed_khz)),
            "-AutoConnect", "1",
        ]
        if self.serial_number:
            arguments += ["-USB", str(self.serial_number)]
        return arguments + ["-CommandFile", command_file]

    def check(self) -> None:
        """Raise now, at connect, if the tool or the device name is missing,
        rather than at the first operation."""
        self.command_line("<command file>")

    def run(self, commands: Sequence[str], what: str, timeout: Optional[float] = None) -> str:
        """Run *commands* as one command file and return what the tool printed.

        ``ExitOnError 1`` is put first, so a failing command stops the file
        rather than letting the rest run on a target in an unknown state, and
        ``q`` last, so the tool never waits at its prompt.

        :raises CommanderError: if the run failed (see :func:`check_output`).
        :raises TransportTimeoutError: if it did not finish in time.
        """
        script = ["exitonerror 1"] + list(commands) + ["q"]
        path = self.scratch("commands.jlink")
        with open(path, "w", encoding="ascii", newline="\n") as handle:
            handle.write("\n".join(script) + "\n")
        arguments = self.command_line(path)
        limit = float(timeout if timeout is not None else self.timeout)
        self._logger.info("%s: %s", what, "; ".join(script))
        started = time.monotonic()
        try:
            completed = subprocess.run(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=limit,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportTimeoutError(
                "%s did not finish within %.0f s (%s)" % (self.NAME, limit, what)
            ) from exc
        except OSError as exc:
            raise ConnectionFailedError("cannot start %r: %s" % (arguments[0], exc)) from exc
        output = completed.stdout.decode("utf-8", errors="replace")
        self._logger.debug("%s took %.2f s:\n%s", what, time.monotonic() - started, output)
        check_output(output, completed.returncode, what)
        return output

    def image(self, path: str) -> List[ImageRange]:
        """The ranges the image at *path* writes."""
        return read_image(path)

    def rtt_backend(self, executable: Optional[str] = None, channel: int = 0) -> "RttLoggerBackend":
        """An RTT source that runs J-Link RTT Logger against this runner's probe."""
        return RttLoggerBackend(
            device=self.device, interface=self.interface, speed_khz=self.speed_khz,
            serial_number=self.serial_number, executable=executable, channel=channel,
            directory=self.directory,
        )

    def close(self) -> None:
        """Remove the command and read-back files."""
        directory, self._directory = self._directory, None
        if directory:
            shutil.rmtree(directory, ignore_errors=True)


class RttLoggerBackend:  # pylint: disable=too-many-instance-attributes
    """RTT through J-Link RTT Logger, written to a file and read from it.

    ``JLinkRTTLogger.exe -Device <d> -If <i> -Speed <s> -RTTChannel 0 <file>``
    read RTT from 5C1712 without halting it on 2026-09-26 (owner's bench
    notes). Its options were checked against the V9.42 binary's help strings on
    2026-11-13: ``-Device``, ``-If``, ``-Speed``, ``-USB``, ``-RTTChannel`` and
    the output file last. Its default channel is 1, not 0 ("RTT Channel name or
    index. Default: channel 1"), so the channel is always given.

    The logger reads only: it has no way to send to the target, so
    :meth:`rtt_send` refuses. It runs until it is stopped: see :meth:`finish`.
    Each session writes its own file.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, device: Optional[str], interface: DebugInterface = DebugInterface.SWD,
                 speed_khz: int = 4000, serial_number: Optional[str] = None,
                 executable: Optional[str] = None, channel: int = 0,
                 directory: Optional[str] = None, start_timeout: float = 10.0) -> None:
        self.device = device
        self.interface = DebugInterface.coerce(interface)
        self.speed_khz = int(speed_khz)
        self.serial_number = serial_number
        self.executable = executable
        self.channel = int(channel)
        self.directory = directory
        self.start_timeout = float(start_timeout)
        self._process: Optional[subprocess.Popen] = None
        self._path = ""
        self._console = ""
        self._offset = 0
        self._sessions = 0
        #: Seconds the logger is given to quit by itself before it is
        #: terminated.
        self.quit_timeout = 2.0

    def command_line(self, output_path: str) -> List[str]:
        """The logger's command line, writing RTT to *output_path*."""
        executable = find_rtt_logger(self.executable)
        if executable is None:
            raise ConnectionFailedError(
                "no J-Link RTT Logger (JLinkRTTLogger.exe) found. It is part of the "
                "SEGGER J-Link software; pass rtt_logger_executable=..., or use "
                "backend: gdb."
            )
        if not self.device:
            raise ConnectionFailedError("a device name is required to read RTT with "
                                        "J-Link RTT Logger")
        arguments = [executable, "-Device", str(self.device), "-If", self.interface.value,
                     "-Speed", str(self.speed_khz or 4000)]
        if self.serial_number:
            arguments += ["-USB", str(self.serial_number)]
        return arguments + ["-RTTChannel", str(self.channel), output_path]

    def rtt_open(self) -> None:
        """Start the logger and wait, briefly, for its output file.

        Each session writes a file of its own, so a second session never
        reads the first one's bytes, and its read position starts at 0 in a
        file nothing else has written. If anything - an exception, Ctrl-C -
        interrupts the start, the logger is stopped before it propagates.
        """
        if self._process is not None:
            return
        directory = self.directory or tempfile.mkdtemp(prefix="benchtools-rtt-")
        self._sessions += 1
        stem = "rtt_channel_%d_%03d" % (self.channel, self._sessions)
        self._path = os.path.join(directory, stem + ".log")
        self._console = os.path.join(directory, stem + "_console.txt")
        self._offset = 0
        if os.path.exists(self._path):
            try:
                os.remove(self._path)
            except OSError as exc:
                # On Windows a file another process still has open cannot be
                # removed: most likely a logger from an earlier session.
                raise ConnectionFailedError(
                    "cannot start a new RTT session: the old RTT file %s cannot be "
                    "removed (%s). Another J-Link RTT Logger may still be writing it; "
                    "stop it and try again." % (self._path, exc)) from exc
        arguments = self.command_line(self._path)
        with open(self._console, "wb") as console:
            try:
                # Not "with": the logger runs until rtt_close stops it.
                self._process = subprocess.Popen(  # pylint: disable=consider-using-with
                    arguments, stdin=subprocess.PIPE, stdout=console, stderr=subprocess.STDOUT)
            except OSError as exc:
                raise ConnectionFailedError("cannot start %r: %s" % (arguments[0], exc)) from exc
        try:
            self._wait_for_start()
        except BaseException:
            self._stop_process()
            raise

    def _wait_for_start(self) -> None:
        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            status = self._process.poll() if self._process is not None else None
            if status is not None:
                self._process = None
                raise ConnectionFailedError(
                    "J-Link RTT Logger exited with status %s before it read anything.%s"
                    % (status, self._said()))
            if os.path.exists(self._path):
                return
            time.sleep(0.1)
        # No file yet is not fatal: the logger may still be searching for the
        # control block. rtt_poll reports a logger that gives up.

    def _said(self) -> str:
        try:
            with open(self._console, "rb") as handle:
                text = handle.read().decode("utf-8", errors="replace").strip()
        except OSError:
            return ""
        return ("\nIt said:\n" + text) if text else ""

    def rtt_poll(self) -> bytes:
        """Bytes the logger has written since the last poll.

        After :meth:`finish` this still returns what the logger wrote before
        it stopped, so the last bytes are not lost.

        :raises ConnectionFailedError: if the logger stopped by itself.
        """
        if not self._path:
            return b""
        data = b""
        if os.path.exists(self._path):
            with open(self._path, "rb") as handle:
                handle.seek(self._offset)
                data = handle.read()
            self._offset += len(data)
        process = self._process
        if not data and process is not None and process.poll() is not None:
            said = self._said()
            self._process = None
            raise ConnectionFailedError("J-Link RTT Logger stopped.%s" % said)
        return data

    def rtt_send(self, data: bytes) -> None:
        """Refused: the logger only reads."""
        raise RttReadOnlyError()

    def finish(self) -> None:
        """Stop the logger so that what it holds reaches its file, and keep
        the file readable for a last :meth:`rtt_poll`.

        It is first asked to quit as it asks to be ("Press any key to
        quit"): a newline on its input, which is then closed, and up to
        :attr:`quit_timeout` seconds to exit and close its file. Only then is
        it terminated; a terminated process cannot flush what it buffered.
        Whether the logger reads the key from that pipe, rather than from the
        console only, is unverified, so terminating remains the fallback.
        """
        self._stop_process()

    def _stop_process(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.poll() is None and process.stdin is not None:
            try:
                process.stdin.write(b"\n")
                process.stdin.flush()
            except OSError:
                pass
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:  # pragma: no cover
                pass
        try:
            process.wait(timeout=self.quit_timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:  # pragma: no cover - stubborn logger
                process.kill()
                process.wait(timeout=5.0)

    def rtt_close(self) -> None:
        """Stop the logger and stop reading its file."""
        try:
            self._stop_process()
        finally:
            self._path = ""


class RttReadOnlyError(ConfigurationError):
    """RTT on the ``segger`` backend reads and cannot write."""

    def __init__(self) -> None:
        super().__init__(
            "writing to RTT is not available on the J-Link 'segger' backend: J-Link "
            "RTT Logger only reads. Use backend: gdb to send to the target over RTT."
        )


class SimulatedReadOnlyRtt:
    """The simulator's RTT, read-only as the logger is, so the simulated
    ``segger`` backend refuses a write exactly as the real one does."""

    def __init__(self, source) -> None:
        self._source = source

    def rtt_open(self) -> None:
        """Start the simulated RTT."""
        self._source.rtt_open()

    def rtt_close(self) -> None:
        """Stop the simulated RTT."""
        self._source.rtt_close()

    def rtt_poll(self) -> bytes:
        """What the simulated target has written."""
        return self._source.rtt_poll()

    def rtt_send(self, data: bytes) -> None:
        """Refused, as the logger refuses."""
        raise RttReadOnlyError()
