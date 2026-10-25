"""The Kepler sensor, as a device-under-test plugin (#238).

Kepler's RF frame decoder, its frame tables, its viewer panel and the S2-LP
register file that receives its frames. The bench loads them through
:mod:`benchtools.core.plugins`; nothing under ``benchtools/`` imports them.

This folder is the plugin until it is hosted in the Kepler repository,
innovateuk-sensor (TX-1054), and #240 removes it from here. A bench file
loads it with::

    plugins:
      - ../plugins/kepler

Provides:

* decoder ``kepler``: :func:`.decoder.decode_kepler_frame`;
* register file ``s2lp_kepler_433_rx.regs``, as
  ``plugin:kepler/s2lp_kepler_433_rx.regs``;
* viewer panel ``kepler``: :class:`.view.KeplerView`, with ``static/kepler.js``;
* hook ``twf_sample``: where a permuted TWF sample belongs, for the viewer's
  waveform reassembly.

Traces to: S2LP-FR-070, VIEW-FR-028, CORE-FR-066.
"""

from __future__ import annotations

from .decoder import decode_kepler_frame
from .tables import twf_sample
from .view import KeplerView

NAME = "kepler"


def register(plugin) -> None:
    """Add Kepler's decoder, register file, viewer panel and hook to *plugin*."""
    plugin.add_decoder("kepler", decode_kepler_frame)
    plugin.add_register_file("s2lp_kepler_433_rx.regs", "configs/s2lp_kepler_433_rx.regs")
    plugin.add_panel("kepler", KeplerView, static="static", scripts=("kepler.js",))
    plugin.add_hook("twf_sample", twf_sample)
