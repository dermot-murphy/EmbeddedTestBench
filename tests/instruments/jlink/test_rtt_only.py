"""RTT without attaching, and numbers taken from RTT lines (#95).

On 5C1712 a GDB attach halted the core even with the GDB Server's -nohalt, the
halted SoftDevice dropped its BLE link and then faulted; the GDB Server alone
served RTT with the target running. These check the driver keeps to the second.

Traces to: JLINK-FR-101, JLINK-FR-102, SWE4-UT-JLINKRTTONLY.
"""

from __future__ import annotations

import threading

from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.jlink import probe as probe_module
from benchtools.instruments.jlink.probe import JLinkProbe
from benchtools.instruments.jlink.rtt import RttClient, SimulatedRttBackend
from benchtools.instruments.jlink.session import GdbMiSession
from benchtools.instruments.jlink.simulator import SimulatedJLink

MCU = r"MCU Temperature:\s*(-?\d+)mC"


def later(seconds, action):
    timer = threading.Timer(seconds, action)
    timer.start()
    return timer


class TestRttSamples:
    def test_numbers_come_from_the_matching_lines(self, probe, simulator):
        probe.rtt_start()
        lines = ["main: loop", "MCU Temperature:       30750mC", "noise",
                 "MCU Temperature:       28750mC"]
        timer = later(0.2, lambda: simulator.rtt_out.extend(lines))
        samples = probe.rtt_samples(MCU, count=2, timeout=2.0, scale=0.001, unit="C")
        timer.join()
        assert samples.values == [30.75, 28.75]
        assert samples.sources[0] == "MCU Temperature:       30750mC"

    def test_a_line_already_waiting_is_not_a_reading(self, probe, simulator):
        probe.rtt_start()
        simulator.rtt_out.append("MCU Temperature:       99000mC")
        probe.rtt_read_lines()                       # the client has it buffered
        simulator.rtt_out.append("MCU Temperature:       99000mC")
        timer = later(0.3, lambda: simulator.rtt_out.append("MCU Temperature:       26000mC"))
        samples = probe.rtt_samples(MCU, count=1, timeout=3.0, scale=0.001)
        timer.join()
        assert samples.values == [26.0]

    def test_a_quiet_target_returns_what_it_got(self, probe):
        probe.rtt_start()
        samples = probe.rtt_samples(MCU, count=5, timeout=0.3)
        assert samples.count == 0 and not samples.complete and samples.mean is None


class TestRttOnly:
    def test_the_link_opens_without_attaching(self):
        simulator = SimulatedJLink()
        probe = JLinkProbe(session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
                           rtt=RttClient(SimulatedRttBackend(simulator)),
                           target_address="simulated")
        probe.attach_on_open = False
        probe.initialise()
        try:
            assert not probe.is_attached and not probe.is_halted
            probe.rtt_start()                        # no "monitor rtt start" to a target
            assert not any("rtt start" in c for c in simulator.command_log)
        finally:
            probe.close()

    def test_the_server_is_told_not_to_halt(self, monkeypatch):
        monkeypatch.setattr(probe_module, "find_gdb", lambda explicit=None: "arm-none-eabi-gdb")
        monkeypatch.setattr("benchtools.instruments.jlink.server.find_gdb_server",
                            lambda explicit=None: "JLinkGDBServerCL")
        probe = JLinkProbe.connect("jlink://", device="nRF52840_xxAA", attach=False,
                                   initialise=False, start_server=False)
        try:
            assert "-nohalt" in probe._server.command_line()  # pylint: disable=protected-access
            assert probe.attach_on_open is False
        finally:
            probe.close()

    def test_by_default_the_server_halts_as_before(self, monkeypatch):
        monkeypatch.setattr(probe_module, "find_gdb", lambda explicit=None: "arm-none-eabi-gdb")
        monkeypatch.setattr("benchtools.instruments.jlink.server.find_gdb_server",
                            lambda explicit=None: "JLinkGDBServerCL")
        probe = JLinkProbe.connect("jlink://", device="nRF52840_xxAA",
                                   initialise=False, start_server=False)
        try:
            assert "-nohalt" not in probe._server.command_line()  # pylint: disable=protected-access
        finally:
            probe.close()
