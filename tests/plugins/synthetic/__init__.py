"""A made-up device, as a plugin: the interface tested with no product code (#238).

Its frames are invented: a magic byte ``0xA5``, a type byte, a two-byte sender
ID, a repeat counter and a value, big-endian::

    A5 <type> <id hi> <id lo> <repeat> <value hi> <value lo>

Type 1 is ``READING``, 2 is ``HELLO``. Anything else is not one of its frames.
The plugin provides decoder ``synthetic``, a register file, a viewer panel
with a script, a field name and a hook.

Traces to: SWE4-UT-PLUGINS (the synthetic test plugin).
"""

from __future__ import annotations

from .frames import decode_synthetic_frame
from .panel import SyntheticPanel

NAME = "synthetic"


def register(plugin) -> None:
    """Add the synthetic device's decoder, register file, panel, field and hook."""
    plugin.add_decoder("synthetic", decode_synthetic_frame)
    plugin.add_register_file("synthetic_rx.regs", "configs/synthetic_rx.regs")
    plugin.add_panel("synthetic", SyntheticPanel, static="static", scripts=("synthetic.js",))
    plugin.add_field("reading", "value")
    plugin.add_hook("twf_sample", lambda method, packet, slot, total, repeat=0:
                    total - 1 - (packet * 32 + slot))
