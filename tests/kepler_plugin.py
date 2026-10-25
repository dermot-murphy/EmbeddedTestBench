"""The Kepler plugin in ``plugins/kepler``, loaded for the tests that use it.

Kepler's decoder, frame tables and viewer panel are a device plugin (#238),
loaded by path rather than imported from ``benchtools``. The tests of that
code, and the viewer tests that feed it Kepler frames, import its modules from
here. The plugin is in this repository until #240 removes it.

Traces to: SWE4-UT-ENV (shared test environment).
"""

from __future__ import annotations

import importlib
import pathlib

from benchtools.core import plugins

FOLDER = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "kepler"
PLUGIN = plugins.load_plugin(str(FOLDER))

decoder = importlib.import_module("etb_plugins.kepler.decoder")
tables = importlib.import_module("etb_plugins.kepler.tables")
view = importlib.import_module("etb_plugins.kepler.view")

decode_kepler_frame = decoder.decode_kepler_frame
SETUP = str(FOLDER / "configs" / "s2lp_kepler_433_rx.regs")
