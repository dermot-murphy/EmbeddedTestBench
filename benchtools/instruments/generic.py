"""Driver for any instrument that answers ``*IDN?``.

Every bench has instruments without a dedicated driver yet - a box on loan, a
new model, something being evaluated. This driver covers the part that is
always the same: prove it is reachable, find out what it is, read its error
queue, and send it raw SCPI.

It is also what the test runner falls back to when a bench configuration names
an instrument with no specific driver, so a test can at least assert the
instrument is present and responding before the rest of the rig is trusted.

Because it adds nothing to :class:`~benchtools.core.scpi.ScpiInstrument` beyond
a model name, it doubles as a demonstration that the shared core is genuinely
instrument-agnostic.

Traces to: CORE-FR-028, INST-FR-001.
"""

from __future__ import annotations

from ..core.scpi import ScpiInstrument
from ..core.simulator import SimulatedInstrument

__all__ = ["GenericScpiInstrument"]


class GenericScpiInstrument(ScpiInstrument):
    """A SCPI instrument with no model-specific behaviour.

    Uses the SCPI-1999 ``SYSTem:ERRor?`` error queue inherited from the base
    class. An instrument that reports errors differently needs its own driver.

    Example::

        from benchtools.instruments.generic import GenericScpiInstrument

        with GenericScpiInstrument.connect("192.168.1.60") as psu:
            print(psu.identify().model)
            psu.write_raw("VOLT 3.3")
            print(psu.query_raw("MEAS:VOLT?"))
    """

    SIMULATOR_CLASS = SimulatedInstrument
    MODEL_NAME = "SCPI instrument"
