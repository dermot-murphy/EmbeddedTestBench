"""Discovery and lifetime of the J-Link GDB Server.

Nothing here starts a real server: the tool is not installed in the build
environment, and would not be on a CI runner either. What can be tested without
it is what actually goes wrong in practice - the wrong command line, a server
already running, a server on another machine, and a server that dies during
start-up.

Traces to: JLINK-FR-003 .. JLINK-FR-005, SWE4-UT-JLINKSERVER.
"""

from __future__ import annotations

import socket
import subprocess
from types import SimpleNamespace

import pytest

from benchtools.core.errors import ConnectionFailedError
from benchtools.instruments.jlink import DebugInterface, GdbServer
from benchtools.instruments.jlink import server as server_module


@pytest.fixture
def listening():
    """A socket listening on an ephemeral port, standing in for a server."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    # A backlog of one fills on Windows with the readiness check's own
    # connection, which is never accepted, so a second check would fail.
    sock.listen(8)
    yield sock.getsockname()[1]
    sock.close()


@pytest.fixture
def closed_port():
    """A port number nothing is listening on."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def nothing_installed(monkeypatch):
    """No install directory holds anything: only PATH is searched."""
    monkeypatch.setattr(server_module, "_installed", lambda patterns, names: [])


class TestDiscovery:
    def test_an_explicit_path_is_returned_unchanged(self):
        """A caller must always be able to override the search."""
        assert server_module.find_gdb_server("/opt/jlink/JLinkGDBServer") == \
            "/opt/jlink/JLinkGDBServer"
        assert server_module.find_gdb("/usr/bin/my-gdb") == "/usr/bin/my-gdb"

    @pytest.mark.usefixtures("nothing_installed")
    def test_windows_names_are_searched_first(self, monkeypatch):
        """The first deployment is a Windows PC, so its names come first."""
        asked = []

        def fake_which(name):
            asked.append(name)
            return None

        monkeypatch.setattr(server_module.shutil, "which", fake_which)
        assert server_module.find_gdb_server() is None
        assert asked[0] == "JLinkGDBServerCL.exe"
        assert asked[1] == "JLinkGDBServer.exe"

    def test_the_first_match_wins(self, monkeypatch):
        monkeypatch.setattr(
            server_module.shutil, "which",
            lambda name: "C:\\SEGGER\\" + name if name.endswith(".exe") else None,
        )
        assert server_module.find_gdb_server() == "C:\\SEGGER\\JLinkGDBServerCL.exe"

    @pytest.mark.usefixtures("nothing_installed")
    def test_gdb_search_prefers_a_cross_debugger(self, monkeypatch):
        """A host ``gdb`` is the last resort, and only if it can debug ARM."""
        asked = []

        def fake_which(name):
            asked.append(name)
            return "/usr/bin/" + name if name == "gdb" else None

        monkeypatch.setattr(server_module.shutil, "which", fake_which)
        monkeypatch.setattr(server_module, "gdb_debugs_arm", lambda executable: True)
        assert server_module.find_gdb() == "/usr/bin/gdb"
        assert asked[0] == "arm-none-eabi-gdb"

    @pytest.mark.usefixtures("nothing_installed")
    def test_a_host_gdb_that_cannot_debug_arm_is_refused(self, monkeypatch):
        """MinGW's gdb 7.6.1 is i386-only; picking it fails later, obscurely."""
        monkeypatch.setattr(
            server_module.shutil, "which",
            lambda name: r"C:\mingw\bin\gdb.exe" if name == "gdb" else None,
        )
        monkeypatch.setattr(server_module, "gdb_debugs_arm", lambda executable: False)
        assert server_module.find_gdb() is None

    def test_the_architecture_question_is_answered_by_gdb(self, monkeypatch):
        answers = {
            "host-gdb": SimpleNamespace(returncode=0, stdout=b'Undefined item: "arm".\n'),
            "arm-gdb": SimpleNamespace(
                returncode=0, stdout=b'The target architecture is set to "arm".\n'
            ),
        }
        monkeypatch.setattr(
            server_module.subprocess, "run", lambda arguments, **kwargs: answers[arguments[0]]
        )
        assert server_module.gdb_debugs_arm("host-gdb") is False
        assert server_module.gdb_debugs_arm("arm-gdb") is True

    def test_a_gdb_that_will_not_start_does_not_debug_arm(self, monkeypatch):
        def refuse(*args, **kwargs):
            raise OSError(2, "No such file")

        monkeypatch.setattr(server_module.subprocess, "run", refuse)
        assert server_module.gdb_debugs_arm("missing-gdb") is False

    def test_install_directories_are_searched_after_path(self, monkeypatch, tmp_path):
        """A standard SEGGER install works without naming the server."""
        for release in ("JLink_V924a", "JLink_V942", "JLink"):
            folder = tmp_path / "SEGGER" / release
            folder.mkdir(parents=True)
            (folder / "JLinkGDBServerCL.exe").write_text("")
        monkeypatch.setattr(server_module.shutil, "which", lambda name: None)
        monkeypatch.setattr(
            server_module, "_SERVER_DIRECTORIES", (str(tmp_path / "SEGGER" / "JLink*"),)
        )
        found = server_module.find_gdb_server()
        assert found == str(tmp_path / "SEGGER" / "JLink_V942" / "JLinkGDBServerCL.exe")

    def test_the_newest_toolchain_release_wins(self, monkeypatch, tmp_path):
        for release in ("13.3 rel1", "14.2 rel1"):
            folder = tmp_path / "Arm" / release / "bin"
            folder.mkdir(parents=True)
            (folder / "arm-none-eabi-gdb.exe").write_text("")
        monkeypatch.setattr(server_module.shutil, "which", lambda name: None)
        monkeypatch.setattr(
            server_module, "_GDB_DIRECTORIES", (str(tmp_path / "Arm" / "*" / "bin"),)
        )
        assert "14.2 rel1" in server_module.find_gdb()

    @pytest.mark.parametrize(
        "directory, release",
        [("C:/SEGGER/JLink_V942", (942,)), ("C:/SEGGER/JLink", ()),
         ("C:/Arm/14.2 rel1/bin", (14, 2, 1))],
    )
    def test_release_numbers(self, directory, release):
        assert server_module._release(directory) == release

    @pytest.mark.usefixtures("nothing_installed")
    def test_nothing_installed_returns_none(self, monkeypatch):
        monkeypatch.setattr(server_module.shutil, "which", lambda name: None)
        assert server_module.find_gdb_server() is None
        assert server_module.find_gdb() is None


class TestPortProbe:
    def test_a_listening_port_is_detected(self, listening):
        assert server_module.port_is_open("127.0.0.1", listening) is True

    def test_a_closed_port_is_not(self, closed_port):
        assert server_module.port_is_open("127.0.0.1", closed_port) is False


class TestCommandLine:
    @pytest.fixture
    def server(self, monkeypatch):
        monkeypatch.setattr(
            server_module, "find_gdb_server", lambda explicit=None: explicit or "JLinkGDBServerCL"
        )
        return GdbServer(device="nRF52840_xxAA", speed_khz=4000, port=2331)

    def test_command_line(self, server):
        arguments = server.command_line()
        assert arguments[0] == "JLinkGDBServerCL"
        assert arguments[1:3] == ["-device", "nRF52840_xxAA"]
        assert arguments[arguments.index("-if") + 1] == DebugInterface.SWD.value
        assert "-speed" in arguments and arguments[arguments.index("-speed") + 1] == "4000"
        assert arguments[arguments.index("-port") + 1] == "2331"

    def test_unattended_flags_are_present(self, server):
        """Without -nogui the server opens a window and waits, hanging a run."""
        for flag in ("-nogui", "-strict"):
            assert flag in server.command_line()

    def test_the_server_is_not_single_run(self, server):
        """-singlerun made the server exit when start()'s readiness check
        disconnected, so GDB found nothing listening (issue #69)."""
        assert "-singlerun" not in server.command_line()

    def test_the_banner_is_not_silenced(self, server):
        """The start-up banner is where the probe's serial number appears."""
        assert "-silent" not in server.command_line()

    def test_every_port_is_passed(self, server):
        arguments = server.command_line()
        for flag in ("-port", "-swoport", "-telnetport", "-rtttelnetport"):
            assert flag in arguments

    def test_adaptive_speed(self, monkeypatch):
        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")
        arguments = GdbServer(device="d", speed_khz=0).command_line()
        assert arguments[arguments.index("-speed") + 1] == "adaptive"

    def test_the_interface_is_coerced_from_a_string(self, monkeypatch):
        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")
        arguments = GdbServer(device="d", interface="jtag").command_line()
        assert arguments[arguments.index("-if") + 1] == DebugInterface.JTAG.value

    def test_a_serial_number_selects_one_of_several_probes(self, server):
        server.serial_number = "801012345"
        arguments = server.command_line()
        assert arguments[arguments.index("-select") + 1] == "usb=801012345"

    def test_extra_arguments_are_passed_verbatim(self, server):
        server.extra_arguments = ["-log", "server.log"]
        assert server.command_line()[-2:] == ["-log", "server.log"]

    def test_a_missing_tool_is_reported_with_what_to_do(self, monkeypatch):
        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: None)
        with pytest.raises(ConnectionFailedError) as caught:
            GdbServer(device="d").command_line()
        message = str(caught.value)
        assert "SEGGER" in message and "already-running server" in message

    def test_a_missing_device_is_reported(self, monkeypatch):
        """The server cannot choose a flash algorithm without one."""
        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")
        with pytest.raises(ConnectionFailedError, match="device name is required"):
            GdbServer().command_line()


class TestStartAndStop:
    def test_an_already_listening_port_is_used(self, listening):
        """Spawning a second server would fail on the USB device being claimed."""
        server = GdbServer(device="d", port=listening)
        server.start()
        assert server.was_spawned is False
        assert server.address == "127.0.0.1:%d" % listening

    def test_only_a_spawned_server_is_stopped(self, listening):
        server = GdbServer(device="d", port=listening)
        server.start()
        server.stop()                        # must not kill what it did not start
        assert server_module.port_is_open("127.0.0.1", listening) is True

    def test_a_remote_server_is_never_spawned(self, closed_port):
        """A container reaches a probe over TCP; it cannot start a server there."""
        server = GdbServer(device="d", host="192.0.2.5", port=closed_port)
        with pytest.raises(ConnectionFailedError, match="cannot be started on another machine"):
            server.start()
        assert server.was_spawned is False

    def test_an_unstartable_executable_is_reported(self, monkeypatch, closed_port):
        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")

        def refuse(*args, **kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(server_module.subprocess, "Popen", refuse)
        server = GdbServer(device="d", port=closed_port)
        with pytest.raises(ConnectionFailedError, match="cannot start 'srv'"):
            server.start()

    def test_a_server_that_exits_reports_its_own_output(self, monkeypatch, closed_port):
        """The server's message is the only text that says what was wrong."""

        class DeadProcess:
            returncode = 255
            stdout = None

            def __init__(self):
                self.stdout = _Output(b"ERROR: Could not connect to target.\n")

            def poll(self):
                return 255

        class _Output:
            def __init__(self, data):
                self._data = data

            def read(self, size):
                data, self._data = self._data, b""
                return data

            def close(self):
                pass

        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")
        monkeypatch.setattr(server_module.subprocess, "Popen", lambda *a, **k: DeadProcess())
        server = GdbServer(device="d", port=closed_port)
        with pytest.raises(ConnectionFailedError) as caught:
            server.start()
        message = str(caught.value)
        assert "exited with status 255" in message
        assert "Could not connect to target" in message

    def test_a_server_that_never_listens_times_out(self, monkeypatch, closed_port):
        class SilentProcess:
            returncode = None
            stdout = None

            def poll(self):
                return None

            def terminate(self):
                self.returncode = -15

            def wait(self, timeout=None):
                return self.returncode

        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")
        monkeypatch.setattr(server_module.subprocess, "Popen", lambda *a, **k: SilentProcess())
        server = GdbServer(device="d", port=closed_port, start_timeout=0.2)
        with pytest.raises(ConnectionFailedError, match="did not start listening"):
            server.start()
        assert server.was_spawned is False       # stopped again by start's own cleanup

    def test_stopping_a_server_that_was_never_started(self):
        GdbServer(device="d").stop()          # no exception, nothing to stop

    def test_context_manager(self, listening):
        with GdbServer(device="d", port=listening) as server:
            assert server.address.endswith(str(listening))

    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", ""])
    def test_local_hosts(self, host):
        assert GdbServer(device="d", host=host).is_local is True

    @pytest.mark.parametrize("host", ["192.0.2.5", "bench-pc", "probe.example.com"])
    def test_remote_hosts(self, host):
        assert GdbServer(device="d", host=host).is_local is False

    def test_the_timeout_survives_a_stubborn_process(self, monkeypatch, closed_port):
        """terminate() then kill(): a server holding the USB device must go."""
        killed = []

        class Stubborn:
            returncode = None
            stdout = None

            def poll(self):
                return None

            def terminate(self):
                pass

            def kill(self):
                killed.append(True)

            def wait(self, timeout=None):
                if not killed:
                    raise subprocess.TimeoutExpired("srv", timeout)
                return -9

        monkeypatch.setattr(server_module, "find_gdb_server", lambda explicit=None: "srv")
        monkeypatch.setattr(server_module.subprocess, "Popen", lambda *a, **k: Stubborn())
        server = GdbServer(device="d", port=closed_port, start_timeout=0.1)
        with pytest.raises(ConnectionFailedError):
            server.start()
        assert killed == [True]


class _Stream:
    """A server's stdout, delivered in pieces that split lines."""

    def __init__(self, data: bytes, piece: int = 7):
        self._pieces = [data[i : i + piece] for i in range(0, len(data), piece)]

    def read(self, _size):
        return self._pieces.pop(0) if self._pieces else b""

    def close(self):
        pass


#: The banner J-Link GDB Server V9.42 printed for the bench probe (issue #69).
_BANNER = (
    b"SEGGER J-Link GDB Server V9.42 Command Line Version\r\n"
    b"Connecting to J-Link...\r\n"
    b"J-Link is connected.\r\n"
    b"Firmware: J-Link ARM V8 compiled Nov 28 2014 13:44:46\r\n"
    b"Hardware: V8.00\r\n"
    b"S/N: 682395790\r\n"
    b"Feature(s): RDI,FlashDL,FlashBP,JFlash,GDB\r\n"
    b"Listening on TCP/IP port 2331\r\n"
)


class TestServerOutput:
    @pytest.fixture
    def drained(self):
        server = GdbServer(device="d")
        server._process = SimpleNamespace(stdout=_Stream(_BANNER))
        server._drain()
        return server

    def test_output_is_drained_into_whole_lines(self, drained):
        """An undrained pipe fills and the server blocks mid-download."""
        assert "S/N: 682395790" in drained.output
        assert all("\r" not in line for line in drained.output)

    def test_the_banner_identifies_the_probe(self, drained):
        assert drained.probe_identity() == {
            "serial_number": "682395790",
            "firmware": "J-Link ARM V8 compiled Nov 28 2014 13:44:46",
            "hardware": "V8.00",
        }

    def test_a_server_not_started_here_identifies_nothing(self):
        assert not GdbServer(device="d").probe_identity()
