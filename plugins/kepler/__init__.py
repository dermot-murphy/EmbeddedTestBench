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
* viewer panel ``kepler``: :class:`.panel.KeplerPanel` - rf_monitor's Latest
  Data, Config, Identification, Environment, Short Interval, Ticks, TWF,
  Diagnostics and Sync, each a tab on the RF page, and the report's Kepler
  sections - with ``static/kepler.js`` and ``static/kepler.css`` (#303);
* hooks ``frame_summary`` and ``sensor_fields``: a frame's one-line summary,
  and the fields the RF page's sensor table keeps (#303);
* hook ``frame_positions``: where a TWF or CONFIG frame's values belong, for
  ``s2lp.dut_transmissions`` to compare the copies of one packet (#243).

Traces to: S2LP-FR-070, VIEW-FR-028, CORE-FR-066.
"""

from __future__ import annotations

from .decoder import decode_kepler_frame
from .panel import TABS, KeplerPanel
from .tables import frame_positions
from .view import frame_summary, sensor_fields

NAME = "kepler"


def register(plugin) -> None:
    """Add Kepler's decoder, register file, viewer panel and hooks to *plugin*."""
    plugin.add_decoder("kepler", decode_kepler_frame)
    plugin.add_register_file("s2lp_kepler_433_rx.regs", "configs/s2lp_kepler_433_rx.regs")
    plugin.add_panel("kepler", KeplerPanel, static="static", scripts=("kepler.js",),
                     tabs=TABS)
    plugin.add_hook("frame_summary", frame_summary)
    plugin.add_hook("sensor_fields", sensor_fields)
    plugin.add_hook("frame_positions", frame_positions)
