"""Device-under-test plugins: product code loaded from outside the package.

The bench carries no product code of its own (#238). What is specific to one
device - how its radio frames decode, the S2-LP register file that receives
them, a viewer panel that shows them - comes from a **plugin**: a folder
holding a Python package, usually a checkout of the product's repository at a
pinned ref, named by the bench file (``plugins:``) or on the command line
(``--plugin``).

A plugin folder has an ``__init__.py`` defining ``register(plugin)``. It is
imported by path as ``etb_plugins.<folder>``, so it can import its own
modules, and ``register`` adds what it provides to the :class:`Plugin` it is
given:

* **decoders**, by name: ``decoder(payload: bytes) -> dict``, raising
  :class:`ValueError` for a payload that is not one of its frames. A decoded
  frame names its type in ``type`` and its sender in ``sensor_id``, and may
  give a transmission's copy number as ``frame["repeat"]``;
* **register files**, by name, found by an input path ``plugin:<name>/<file>``;
* **viewer panels**: a factory for an object with ``feed(frame)`` and
  ``view(sensor)``, and a folder of static files the viewer serves;
* **field names** that sample actions accept for a decoded field;
* **hooks**: named functions the viewer's device-specific analyses use until
  they are generic themselves.

Every report names each plugin loaded, its folder and its git ref
(:meth:`Plugin.describe`), so a result can be traced to the product code that
read it.

Traces to: CORE-FR-066 .. CORE-FR-070, CORE-DD-PLUGINS.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import subprocess
import sys
import types
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .errors import ConfigurationError

__all__ = [
    "LEGACY_KEPLER",
    "PLUGIN_PATH_PREFIX",
    "Panel",
    "Plugin",
    "Registry",
    "REGISTRY",
    "decode",
    "decoder",
    "ensure_legacy_kepler",
    "hook",
    "load_plugin",
    "loaded_plugins",
    "moved_to_plugin",
    "plugin_folders",
    "uses_legacy_kepler",
    "resolve_plugin_path",
]

#: How an input path names a file a plugin provides: ``plugin:<name>/<file>``.
PLUGIN_PATH_PREFIX = "plugin:"

#: The package every plugin is imported under.
_PACKAGE = "etb_plugins"

#: The Kepler plugin in the EmbeddedTestBench checkout, which the deprecated
#: ``kepler_*`` actions and Kepler's old register file path still reach for
#: one release when no ``kepler`` plugin is loaded (#238). #240 removes it.
LEGACY_KEPLER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "kepler")

_LOG = logging.getLogger(__name__)

#: Input files that moved into the Kepler plugin (#238): the old path, still
#: found for one release when nothing is at it, to the plugin path now.
MOVED = {"configs/s2lp_kepler_433_rx.regs": "plugin:kepler/s2lp_kepler_433_rx.regs"}

#: The deprecated actions that name Kepler (#238), kept for one release.
LEGACY_ACTIONS = ("kepler_samples", "kepler_frame")

Decoder = Callable[[bytes], Dict[str, Any]]


@dataclass
class Panel:
    """A viewer panel a plugin provides.

    :param factory: Makes the panel's state: an object with ``feed(frame)``,
        given each decoded radio frame, and ``view(sensor)``, returning what
        the panel shows for one sensor as JSON-ready data.
    :param static: Folder of the panel's static files (its script), served by
        the viewer under ``/plugin/<plugin>/``.
    :param scripts: The scripts in *static* the viewer's page loads.
    """

    name: str
    factory: Callable[[], Any]
    static: Optional[str] = None
    scripts: Tuple[str, ...] = ()


@dataclass
class Plugin:  # pylint: disable=too-many-instance-attributes
    """One loaded plugin: where it came from, and what it provides."""

    name: str
    path: str
    ref: Optional[str] = None
    dirty: bool = False
    #: The module the plugin's package was imported as.
    module: str = ""
    decoders: Dict[str, Decoder] = field(default_factory=dict)
    register_files: Dict[str, str] = field(default_factory=dict)
    panels: Dict[str, Panel] = field(default_factory=dict)
    fields: Dict[str, str] = field(default_factory=dict)
    hooks: Dict[str, Callable[..., Any]] = field(default_factory=dict)

    def add_decoder(self, name: str, function: Decoder) -> None:
        """Provide a frame decoder, chosen by *name*."""
        self.decoders[name] = function

    def add_register_file(self, name: str, path: str) -> None:
        """Provide a register file; *path* is relative to the plugin's folder."""
        self.register_files[name] = os.path.normpath(os.path.join(self.path, path))

    def add_panel(self, name: str, factory: Callable[[], Any], static: Optional[str] = None,
                  scripts: Tuple[str, ...] = ()) -> None:
        """Provide a viewer panel; *static* is relative to the plugin's folder."""
        folder = os.path.normpath(os.path.join(self.path, static)) if static else None
        self.panels[name] = Panel(name, factory, folder, tuple(scripts))

    def add_field(self, name: str, decoded_key: str) -> None:
        """Let a sample action take *name* for the decoded field *decoded_key*."""
        self.fields[name] = decoded_key

    def add_hook(self, name: str, function: Callable[..., Any]) -> None:
        """Provide a named function for a device-specific analysis."""
        self.hooks[name] = function

    def describe(self) -> Dict[str, Any]:
        """The plugin as a report records it: name, folder, git ref, dirty."""
        return {"name": self.name, "path": self.path, "ref": self.ref, "dirty": self.dirty}


def _git(path: str, *args: str) -> Optional[str]:
    """``git -C path args``'s output, or None if it is not a git checkout."""
    try:
        result = subprocess.run(["git", "-C", path, *args], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


def _ref(path: str) -> Tuple[Optional[str], bool]:
    """The commit the plugin's folder is at, and whether its tree has changes."""
    ref = _git(path, "rev-parse", "HEAD")
    if ref is None:
        return None, False
    status = _git(path, "status", "--porcelain", "--", ".")
    return ref, bool(status)


def _package() -> types.ModuleType:
    """The namespace every plugin module is imported under."""
    if _PACKAGE not in sys.modules:
        package = types.ModuleType(_PACKAGE)
        package.__path__ = []  # type: ignore[attr-defined]
        sys.modules[_PACKAGE] = package
    return sys.modules[_PACKAGE]


class Registry:
    """The plugins loaded in this process, and lookups across them."""

    def __init__(self) -> None:
        self.plugins: Dict[str, Plugin] = {}

    def load(self, path: str) -> Plugin:
        """Import the plugin in folder *path* and record what it provides.

        Loading a folder already loaded returns that plugin again.

        :raises ConfigurationError: if the folder holds no plugin, its
            ``register`` fails, or another plugin already has its name.
        """
        folder = os.path.normpath(os.path.abspath(path))
        for plugin in self.plugins.values():
            if os.path.normcase(plugin.path) == os.path.normcase(folder):
                return plugin
        init = os.path.join(folder, "__init__.py")
        if not os.path.isfile(init):
            raise ConfigurationError("no plugin in %s: it has no __init__.py" % folder)
        module_name = _module_name(folder)
        try:
            module = _import(module_name, init, folder)
            register = getattr(module, "register", None)
            if not callable(register):
                raise ConfigurationError("plugin %s has no register(plugin) function" % folder)
            name = str(getattr(module, "NAME", os.path.basename(folder)))
            if name in self.plugins:
                raise ConfigurationError("two plugins are named %r: %s and %s"
                                         % (name, self.plugins[name].path, folder))
            ref, dirty = _ref(folder)
            plugin = Plugin(name=name, path=folder, ref=ref, dirty=dirty, module=module_name)
            try:
                register(plugin)  # pylint: disable=not-callable  # checked just above
            except Exception as error:
                raise ConfigurationError("plugin %s failed to register: %s"
                                         % (name, error)) from error
        except ConfigurationError:
            _forget(module_name)
            raise
        self.plugins[name] = plugin
        return plugin

    def unload(self, name: str) -> None:
        """Forget a plugin; for tests."""
        self.plugins.pop(name, None)

    def describe(self) -> List[Dict[str, Any]]:
        """Every loaded plugin, as a report records it."""
        return [plugin.describe() for plugin in self.plugins.values()]

    def decoder(self, name: Optional[str] = None) -> Decoder:
        """The decoder called *name*, or the only one loaded if *name* is None.

        :raises ConfigurationError: if no decoder has that name, or *name* is
            None and there is not exactly one decoder to choose.
        """
        found = {key: function for plugin in self.plugins.values()
                 for key, function in plugin.decoders.items()}
        if name is not None:
            if name not in found:
                raise ConfigurationError(
                    "no decoder %r is loaded; the plugins loaded provide: %s"
                    % (name, ", ".join(sorted(found)) or "none"))
            return found[name]
        if len(found) != 1:
            raise ConfigurationError(
                "name the decoder: %s" % (
                    "no plugin that provides one is loaded (bench file plugins:, or --plugin)"
                    if not found else "the plugins loaded provide %s" % ", ".join(sorted(found))))
        return next(iter(found.values()))

    def decode(self, payload: bytes) -> Dict[str, Any]:
        """*payload* decoded by the first loaded decoder that reads it.

        For a frame logged without a decode, such as one the viewer reads back:
        which device sent it is not known, so each decoder is tried in the
        order the plugins were loaded.

        :raises ValueError: if no decoder is loaded, or none reads *payload*;
            the message gives each decoder's reason.
        """
        reasons = []
        for plugin in self.plugins.values():
            for name, function in plugin.decoders.items():
                try:
                    return function(payload)
                except Exception as error:  # pylint: disable=broad-exception-caught
                    # A decoder that fails on a frame does not read it, for
                    # whatever reason: one bad frame must not stop a reader.
                    reasons.append("%s: %s" % (name, str(error) or type(error).__name__))
        if not reasons:
            raise ValueError("no decoder is loaded")
        raise ValueError("; ".join(reasons))

    def field(self, name: str) -> str:
        """The decoded key a sample action's field name stands for."""
        for plugin in self.plugins.values():
            if name in plugin.fields:
                return plugin.fields[name]
        return name

    def hook(self, name: str, default: Optional[Callable[..., Any]] = None
             ) -> Optional[Callable[..., Any]]:
        """The first loaded plugin's hook called *name*, or *default*."""
        for plugin in self.plugins.values():
            if name in plugin.hooks:
                return plugin.hooks[name]
        return default

    def panels(self) -> List[Tuple[Plugin, Panel]]:
        """Every viewer panel, with the plugin that provides it."""
        return [(plugin, panel) for plugin in self.plugins.values()
                for panel in plugin.panels.values()]

    def resolve_path(self, value: str) -> str:
        """The file an input path ``plugin:<name>/<file>`` names.

        *file* is a register file's name, or a path within the plugin's folder.

        :raises ConfigurationError: if no plugin of that name is loaded, or
            the file is not there.
        """
        rest = value[len(PLUGIN_PATH_PREFIX):]
        name, _, file = rest.partition("/")
        plugin = self.plugins.get(name)
        if plugin is None:
            raise ConfigurationError("%s names plugin %r, which is not loaded; loaded: %s"
                                     % (value, name, ", ".join(sorted(self.plugins)) or "none"))
        candidate = plugin.register_files.get(file)
        if candidate is None:
            candidate = os.path.normpath(os.path.join(plugin.path, file))
            if not _inside(candidate, plugin.path):
                raise ConfigurationError("%s is outside plugin %s" % (value, name))
        if not os.path.exists(candidate):
            raise ConfigurationError("plugin %s has no file %r (%s)" % (name, file, candidate))
        return candidate


def _module_name(folder: str) -> str:
    """A module name for the plugin in *folder*, unique to the folder.

    Two folders with one name, such as two checkouts' ``plugins/kepler``, are
    two plugins' code, so the name carries a hash of the whole path.
    """
    base = "".join(char if char.isalnum() else "_" for char in os.path.basename(folder))
    digest = hashlib.sha1(os.path.normcase(folder).encode("utf-8")).hexdigest()[:10]
    return "%s.%s_%s" % (_PACKAGE, base or "plugin", digest)


def _import(module_name: str, init: str, folder: str) -> types.ModuleType:
    """Import the package in *folder* as *module_name*."""
    _package()
    spec = importlib.util.spec_from_file_location(
        module_name, init, submodule_search_locations=[folder])
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as error:
        raise ConfigurationError("plugin %s failed to import: %s" % (folder, error)) from error
    return module


def _forget(module_name: str) -> None:
    """Remove a plugin that failed to load, and its modules, from ``sys.modules``."""
    for name in [key for key in sys.modules
                 if key == module_name or key.startswith(module_name + ".")]:
        del sys.modules[name]


def _inside(path: str, folder: str) -> bool:
    """True if *path* is *folder* or within it, links followed."""
    real, root = os.path.realpath(path), os.path.realpath(folder)
    try:
        return os.path.commonpath([os.path.normcase(real), os.path.normcase(root)]) \
            == os.path.normcase(root)
    except ValueError:                      # another drive on Windows
        return False


#: The plugins of this process.
REGISTRY = Registry()


def moved_to_plugin(value: str) -> Optional[str]:
    """The ``plugin:`` path an input file that moved into a plugin is at now."""
    return MOVED.get(value.replace("\\", "/"))


def uses_legacy_kepler(actions: List[str], values: List[Any]) -> Optional[str]:
    """What in a specification still names Kepler the old way, or None.

    *actions* are its steps' actions, *values* its steps' argument values; a
    deprecated action or a moved path is named so that the run can load the
    Kepler plugin before it starts, and record it (#238).
    """
    for action in actions:
        if action.rpartition(".")[2] in LEGACY_ACTIONS:
            return action
    for value in values:
        if isinstance(value, str) and moved_to_plugin(value) is not None:
            return value
    return None


def ensure_legacy_kepler(what: str) -> bool:
    """Load the checkout's Kepler plugin for a deprecated Kepler name, if needed.

    For one release, a specification written before #238 - ``kepler_samples``,
    ``kepler_frame``, ``configs/s2lp_kepler_433_rx.regs``, no ``plugins:`` -
    still runs: the Kepler plugin in this checkout is loaded, with a warning
    saying what to write instead. Returns whether a ``kepler`` plugin is loaded.
    """
    if "kepler" in REGISTRY.plugins:
        return True
    if not os.path.isfile(os.path.join(LEGACY_KEPLER, "__init__.py")):
        return False
    REGISTRY.load(LEGACY_KEPLER)
    _LOG.warning("%s is deprecated (#238): loaded the Kepler plugin from %s. Name it in the "
                 "specification's plugins: and use s2lp.dut_samples or s2lp.dut_frame with "
                 "decoder: kepler and plugin:kepler/ paths; this fallback goes with #240",
                 what, LEGACY_KEPLER)
    return True


def plugin_folders(value: Any, directory: Optional[str], where: str) -> Tuple[str, ...]:
    """A ``plugins:`` list from a bench file or specification, as absolute folders.

    :param directory: The declaring file's folder, which relative paths are
        taken from; the current directory if None.
    :raises ConfigurationError: if *value* is not a list of paths.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) and item
                                                       for item in value):
        raise ConfigurationError("%s: 'plugins' must be a list of plugin folders" % where)
    base = directory or os.getcwd()
    return tuple(os.path.normpath(os.path.join(base, item)) for item in value)


def load_plugin(path: str) -> Plugin:
    """Load the plugin in folder *path* into :data:`REGISTRY`."""
    return REGISTRY.load(path)


def loaded_plugins() -> List[Dict[str, Any]]:
    """Every plugin loaded, as a report records it."""
    return REGISTRY.describe()


def decoder(name: Optional[str] = None) -> Decoder:
    """The decoder called *name*, or the only one loaded (:meth:`Registry.decoder`)."""
    return REGISTRY.decoder(name)


def decode(payload: bytes) -> Dict[str, Any]:
    """*payload* decoded by the first decoder that reads it (:meth:`Registry.decode`)."""
    return REGISTRY.decode(payload)


def hook(name: str, default: Optional[Callable[..., Any]] = None
         ) -> Optional[Callable[..., Any]]:
    """A plugin's hook called *name*, or *default* (:meth:`Registry.hook`)."""
    return REGISTRY.hook(name, default)


def resolve_plugin_path(value: str) -> str:
    """The file ``plugin:<name>/<file>`` names (:meth:`Registry.resolve_path`)."""
    return REGISTRY.resolve_path(value)
