"""GDB's view of the core after ``monitor`` commands: design rule J1 (#396).

Traces to: SWE4-UT-JLINK, SWE4-UT-GDBSESSION, JLINK-FR-002.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.jlink.gdbmi import parse_line

from .test_session import session_for


@pytest.mark.parametrize("command", ["version", "flash erase", "halt"])
def test_every_monitor_command_flushes_gdb_s_register_cache(probe, command):
    """Rule J1 holds for a caller's own command too, not only reset."""
    log = probe.session.transport.responder.command_log
    probe.monitor(command)
    sent = max(i for i, c in enumerate(log) if "monitor %s" % command in c)
    assert any("maintenance flush register-cache" in c for c in log[sent + 1:])


def test_a_running_record_marks_the_core_running(probe):
    """GDB's *running record is followed, not only the driver's own calls."""
    assert probe.is_halted
    probe.session._file(  # pylint: disable=protected-access  # inject GDB's record
        parse_line('*running,thread-id="all"')
    )
    assert not probe.is_halted
    probe.session._file(  # pylint: disable=protected-access
        parse_line('*stopped,reason="signal-received"')
    )
    assert probe.is_halted


def test_the_session_reports_the_last_run_record_once():
    instance, _ = session_for({
        "-exec-continue": '{t}^running\n*running,thread-id="all"\n(gdb)',
    })
    assert instance.take_exec_state() is None
    instance.execute("-exec-continue")
    assert instance.take_exec_state() == "running"
    assert instance.take_exec_state() is None
