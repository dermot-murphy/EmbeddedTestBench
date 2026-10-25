"""The viewer's side of device plugins: their panels, and a run's plugins (#238).

A device plugin (:mod:`benchtools.core.plugins`) can provide viewer panels: an
object fed each received radio frame and asked for what it shows, plus the
scripts the page loads from ``/plugin/<plugin>/``. The server keeps one fresh
state per panel for each run it follows, lists the plugins for the page, and
loads the plugins of a run it starts, so that their panels show that run.

Traces to: VIEW-FR-047, VIEW-DD-SERVER.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..core import plugins
from ..core.errors import BenchToolsError
from ..runner.bench import load_bench
from ..runner.spec import load_spec

__all__ = ["dut_panels", "plugins_view", "run_plugins"]

_LOG = logging.getLogger(__name__)


def dut_panels() -> Dict[str, Any]:
    """A fresh state for every panel the loaded plugins provide, by name."""
    return {panel.name: panel.factory() for _plugin, panel in plugins.REGISTRY.panels()}


def plugins_view() -> List[Dict[str, Any]]:
    """The plugins loaded, and the scripts of their panels the page loads."""
    listed = []
    for plugin in plugins.REGISTRY.plugins.values():
        entry = plugin.describe()
        entry["panels"] = [{"name": panel.name,
                            "scripts": ["/plugin/%s/%s" % (plugin.name, script)
                                        for script in panel.scripts]}
                           for panel in plugin.panels.values()]
        listed.append(entry)
    return listed


def run_plugins(spec_path: str, bench_path: Optional[str]) -> List[str]:
    """The plugin folders a run of *spec_path* on *bench_path* loads (#238).

    The viewer loads them too, so that their panels show the run.
    """
    folders: List[str] = []
    try:
        folders.extend(load_spec(spec_path).plugins)
        if bench_path:
            folders.extend(load_bench(bench_path).plugins)
    except (BenchToolsError, OSError) as exc:
        _LOG.warning("cannot read the plugins of %s: %s", spec_path, exc)
    return list(dict.fromkeys(folders))
