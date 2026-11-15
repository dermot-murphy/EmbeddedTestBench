"""A variable GDB places at address 0 is refused, not read (#352).

Traces to: SWE4-UT-JLINK, JLINK-FR-041.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import MeasurementError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.jlink import JLinkProbe, SimulatedJLink, SimulatedSymbol
from benchtools.instruments.jlink.session import GdbMiSession
from benchtools.instruments.jlink.simulator import DEFAULT_FIRMWARE

#: As on 5C1712: the vector table's initial stack pointer at address 0.
INITIAL_SP = 0x20000400


@pytest.fixture
def simulator() -> SimulatedJLink:
    """A target whose ELF still describes a variable the linker discarded."""
    firmware = DEFAULT_FIRMWARE()
    firmware.symbols["m_freq"] = SimulatedSymbol(address=0, size=4, type_name="uint32_t")
    instance = SimulatedJLink(firmware=firmware)
    instance.write_memory(0, INITIAL_SP.to_bytes(4, "little"))
    return instance


@pytest.fixture
def probe(simulator):
    instance = JLinkProbe(
        session=GdbMiSession(MockTransport(responder=simulator), timeout=5.0),
        elf="firmware.elf", target_address="simulated",
    )
    instance.initialise()
    yield instance
    instance.close()


class TestAVariableAtAddressZero:
    def test_reading_it_is_refused(self, probe):
        """Before #352 this returned 0x20000400, the initial stack pointer."""
        with pytest.raises(MeasurementError,
                           match="cannot read 'm_freq'.*address 0.*not in the image"):
            probe.read_variable("m_freq")

    def test_writing_it_is_refused_and_nothing_is_written(self, probe, simulator):
        with pytest.raises(MeasurementError, match="cannot write 'm_freq'.*address 0"):
            probe.write_variable("m_freq", 5)
        assert simulator.read_memory(0, 4) == INITIAL_SP.to_bytes(4, "little")

    def test_its_address_is_refused(self, probe):
        with pytest.raises(MeasurementError, match="cannot locate 'm_freq'.*address 0"):
            probe.variable_address("m_freq")

    def test_a_variable_elsewhere_still_reads(self, probe):
        name = next(n for n in DEFAULT_FIRMWARE().symbols if n != "m_freq")
        probe.read_variable(name)
        assert probe.variable_address(name) != 0

    def test_an_expression_with_no_address_is_not_checked(self, probe):
        """``&$pc`` has no meaning, so ``$pc`` is evaluated unchecked."""
        assert isinstance(probe.read_variable("$pc"), int)

    def test_the_check_takes_the_address_of_the_whole_expression(self, probe, simulator):
        """``&(name)``, so ``a + 1`` is not taken as ``(&a) + 1``."""
        with pytest.raises(MeasurementError):
            probe.read_variable("m_freq")
        assert any("&(m_freq)" in command for command in simulator.command_log)

    @pytest.mark.parametrize("expression", ["m_freq++", "m_freq = 5", "m_freq >>= 1", "m_freq <<= 1", "reset_count()"])
    def test_an_expression_with_a_side_effect_is_not_evaluated_twice(
            self, probe, simulator, expression):
        """The check would evaluate it once more, so it is skipped."""
        before = len(simulator.command_log)
        with pytest.raises(MeasurementError):     # the simulator cannot evaluate these
            probe.read_variable(expression)
        sent = simulator.command_log[before:]
        assert not any(command.startswith("-data-evaluate-expression \"&") for command in sent)
        assert len(sent) == 1
