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

import pytest

from benchtools.core.errors import ConnectionFailedError
from benchtools.instruments.jlink import DebugInterface, GdbServer
from benchtools.instruments.jlink import server as server_module


@pytest.fixture
def listening():
    """A socket listening on an ephemeral port, standing in for a server."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
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


class TestDiscovery:
    def test_an_explicit_path_is_returned_unchanged(self):
        """A caller must always be able to override the search."""
        assert server_module.find_gdb_server("/opt/jlink/JLinkGDBServer") == \
            "/opt/jlink/JLinkGDBServer"
        assert server_module.find_gdb("/usr/bin/my-gdb") == "/usr/bin/my-gdb"

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

    def test_gdb_search_prefers_a_cross_debugger(self, monkeypatch):
        """A host ``gdb`` cannot debug an ARM target, so it is the last resort."""
        asked = []

        def fake_which(name):
            asked.append(name)
            return "/usr/bin/" + name if name == "gdb" else None

        monkeypatch.setattr(server_module.shutil, "which", fake_which)
        assert server_module.find_gdb() == "/usr/bin/gdb"
        assert asked[0] == "arm-none-eabi-gdb"

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
        for flag in ("-nogui", "-silent", "-singlerun", "-strict"):
            assert flag in server.command_line()

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
