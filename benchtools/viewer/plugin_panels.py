"""The viewer's side of device plugins: their panels, and a run's plugins (#238).

A device plugin (:mod:`benchtools.core.plugins`) can provide viewer panels: an
object fed each received radio frame and asked for what it shows, plus the
scripts the page loads from ``/plugin/<plugin>/``. The server keeps one fresh
state per panel for each run it follows, lists the plugins for the page, and
loads the plugins of a run it starts, so that their panels show that run. It
does not load the plugins a followed log names, and says which are missing.

Traces to: VIEW-FR-047, VIEW-DD-SERVER.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any, Dict, List, Optional

from ..core import plugins
from ..core.errors import BenchToolsError
from ..runner.bench import load_bench
from ..runner.spec import load_spec

__all__ = ["dut_panels", "missing_plugins", "plugin_file", "plugins_view", "run_plugins"]

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


def plugin_file(rest: str) -> Optional[pathlib.Path]:
    """The file ``/plugin/<rest>`` names, ``<plugin>/<file>``, or None.

    Only a file within one of the plugin's panels' static folders, links
    followed, is served.
    """
    name, _, file = rest.partition("/")
    plugin = plugins.REGISTRY.plugins.get(name)
    for panel in plugin.panels.values() if plugin is not None else ():
        if panel.static is None:
            continue
        folder = pathlib.Path(panel.static).resolve()
        target = (folder / file).resolve()
        if folder in target.parents and target.is_file():
            return target
    return None


def missing_plugins(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The plugins a ``run_start`` record names that are not loaded here.

    The viewer does not load them itself: a plugin is code, and a log can come
    from anywhere. It says so instead, once per run, so that undecoded frames
    and empty panels are explained (#238).
    """
    named = (record.get("data") or {}).get("plugins") or []
    missing = [dict(plugin) for plugin in named
               if isinstance(plugin, dict) and plugin.get("name") not in plugins.REGISTRY.plugins]
    if missing:
        _LOG.warning("the run used plugin(s) %s, not loaded in this viewer: its frames are "
                     "decoded and shown only with benchtools view --plugin %s",
                     ", ".join(str(plugin.get("name")) for plugin in missing),
                     " --plugin ".join(str(plugin.get("path")) for plugin in missing))
    return missing


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
