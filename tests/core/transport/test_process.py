"""Transport over a child process's pipes.

Traces to: CORE-FR-009, SWE4-UT-PROCESS.
"""

from __future__ import annotations

import sys

import pytest

from benchtools.core.errors import ConnectionFailedError, TransportError, TransportTimeoutError
from benchtools.core.transport import ProcessTransport, registered_backends
from benchtools.core.transport.factory import parse_resource


class TestRoundTrip:
    def test_lines_echo_back(self):
        with ProcessTransport(["cat"], timeout=5.0) as link:
            link.write(b"hello")
            assert link.read_message() == b"hello"
            link.write(b"again")
            assert link.read_message() == b"again"

    def test_large_transfer(self):
        """Reads are in blocks, not byte by byte: a flash programming run's
        console output would otherwise cost one queue item per byte."""
        payload = b"x" * 200_000
        with ProcessTransport(["cat"], timeout=10.0) as link:
            link.write(payload, append_terminator=False)
            assert link.read_exactly(len(payload)) == payload

    def test_binary_data_survives(self):
        data = bytes(range(256))
        with ProcessTransport(["cat"], timeout=5.0) as link:
            link.write(data, append_terminator=False)
            assert link.read_exactly(len(data)) == data

    def test_command_as_a_string_is_split(self):
        with ProcessTransport("cat", timeout=5.0) as link:
            link.write(b"via shlex")
            assert link.read_message() == b"via shlex"

    def test_command_is_reported(self):
        assert ProcessTransport(["cat", "-u"]).command == ("cat", "-u")


class TestFailures:
    def test_missing_program_is_reported_clearly(self):
        link = ProcessTransport(["/nonexistent/tool"])
        with pytest.raises(ConnectionFailedError, match="Check the program is installed"):
            link.open()

    def test_a_program_that_exits_at_once_reports_its_stderr(self):
        """Otherwise this surfaces much later as an unexplained read timeout."""
        link = ProcessTransport(
            [sys.executable, "-c", "import sys; sys.stderr.write('bad option\\n'); sys.exit(3)"]
        )
        with pytest.raises(ConnectionFailedError, match="exited immediately"):
            link.open()

    def test_writing_to_a_dead_process_is_reported(self):
        link = ProcessTransport([sys.executable, "-c", "import time; time.sleep(30)"])
        link.open()
        link._process.kill()
        link._process.wait(timeout=5)
        with pytest.raises(ConnectionFailedError, match="exited"):
            link.write(b"anything")
        link.close()

    def test_a_silent_program_times_out(self):
        link = ProcessTransport(
            [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.3
        )
        with link:
            link.write(b"ignored")
            with pytest.raises(TransportTimeoutError, match="no output"):
                link.read_message()

    def test_io_before_open_is_rejected(self):
        with pytest.raises(TransportError, match="not open"):
            ProcessTransport(["cat"]).write(b"x")

    def test_empty_command_is_rejected(self):
        with pytest.raises(ValueError, match="command"):
            ProcessTransport([])
        with pytest.raises(ValueError, match="command"):
            ProcessTransport("")


class TestLifecycle:
    def test_exit_status_is_retained_after_close(self):
        """The exit status of a tool that failed is what a diagnostic needs."""
        link = ProcessTransport(["cat"], timeout=5.0)
        link.open()
        link.close()
        assert link.returncode is not None

    def test_close_is_idempotent(self):
        link = ProcessTransport(["cat"], timeout=5.0)
        link.open()
        link.close()
        link.close()
        assert not link.is_open

    def test_stderr_is_drained_so_the_child_cannot_block(self):
        """An unread stderr pipe fills and the child blocks, hanging the session
        for no visible reason."""
        link = ProcessTransport(
            [
                sys.executable, "-c",
                "import sys\n"
                "sys.stderr.write('noise\\n' * 5000)\n"
                "sys.stderr.flush()\n"
                "sys.stdout.write('done\\n')\n"
                "sys.stdout.flush()\n"
                "import time; time.sleep(5)\n",
            ],
            timeout=5.0,
        )
        with link:
            assert link.read_message() == b"done"
            assert "noise" in link.stderr_text

    def test_description_names_the_program(self):
        assert "cat" in ProcessTransport(["cat"]).description


class TestBackendRegistration:
    def test_registered(self):
        assert "process" in registered_backends()

    @pytest.mark.parametrize("scheme", ["process", "stdio"])
    def test_schemes_resolve(self, scheme):
        parsed = parse_resource("%s://cat -u" % scheme)
        assert parsed["backend"] == "process"
        assert parsed["resource"] == "cat -u"
