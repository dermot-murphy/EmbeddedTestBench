"""Attaching to a core that a GDB Server already running left running (#349).

Traces to: SWE4-UT-JLINK, JLINK-FR-003.
"""

from __future__ import annotations

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.jlink import JLinkProbe, SimulatedJLink
from benchtools.instruments.jlink.session import GdbMiSession

from .conftest import END_LOCATION


class TestAttachingToARunningCore:
    def test_a_core_left_running_by_the_server_is_halted_on_attach(self):
        """A GDB Server already running does not halt the core for its next
        client, so the driver halts it; before #349 it took the running core
        for halted and read every register as 0xDEADBEEF."""
        simulator = SimulatedJLink()
        simulator.halted = False               # the last client let it run
        probe = JLinkProbe(
            session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
            elf="firmware.elf", target_address="simulated",
        )
        probe.initialise()
        try:
            assert simulator.halted and probe.is_halted
            assert "halt" in simulator.monitor_log
            assert probe.program_counter() == simulator.program_counter
            assert probe.program_counter() != 0xDEADBEEF
            probe.run_to(END_LOCATION)
            assert [frame.function for frame in probe.call_stack()][0] == "sensor_done"
        finally:
            probe.close()
        assert not simulator.halted            # and left running again on close

    def test_without_the_halt_the_registers_were_unreadable(self):
        """What #349 saw: GDB attached to a running core reads 0xDEADBEEF."""
        simulator = SimulatedJLink()
        simulator.halted = False
        session = GdbMiSession(MockTransport(responder=simulator), timeout=5.0)
        session.start()
        try:
            session.execute("-target-select extended-remote sim:0")
            record = session.execute("-data-list-register-values x 15")
            assert "0xdeadbeef" in str(record.results).lower()
        finally:
            session.close()

    def test_halting_a_halted_core_reports_where_it_is(self):
        """After the attach's halt, ``halt`` reports the core's own location,
        not address 0, which is what the bench showed before (#349)."""
        simulator = SimulatedJLink()
        simulator.halted = False
        probe = JLinkProbe(
            session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
            elf="firmware.elf", target_address="simulated",
        )
        probe.initialise()
        try:
            info = probe.halt()
            assert info.address == simulator.program_counter != 0
            assert info.function
        finally:
            probe.close()
