"""Architectural constraints on the dependency graph.

The restructure that produced this layout exists to make the shared layers
reusable by instruments that do not exist yet. That property is easy to state
and easy to lose: one convenient import from ``core`` into an instrument package
and the core stops being shareable. These tests enforce the rule mechanically,
by reading the source rather than trusting review.

The rule is that dependencies point one way only::

    runner  ->  instruments  ->  analysis  ->  core

Traces to: CORE-NFR-001, CORE-ARC-001, ANA-ARC-001, SWE4-UT-LAYERING.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent / "benchtools"

#: Layer to the layers it may import from. A layer may always import itself.
ALLOWED = {
    "core": {"core"},
    "analysis": {"core", "analysis"},
    "instruments": {"core", "analysis", "instruments"},
    "runner": {"core", "analysis", "instruments", "runner"},
}


def _layer_of(path: pathlib.Path) -> str:
    relative = path.relative_to(ROOT)
    return relative.parts[0] if len(relative.parts) > 1 else ""


def _imported_layers(path: pathlib.Path):
    """Return the benchtools layers *path* imports from.

    Handles both absolute (``benchtools.core.x``) and relative (``..core.x``)
    imports, resolving the relative ones against the file's own package.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    package_parts = path.relative_to(ROOT).parts[:-1]
    found = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("benchtools."):
                    found.add(alias.name.split(".")[1])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module and node.module.startswith("benchtools."):
                    found.add(node.module.split(".")[1])
                continue
            # Relative: walk up `level - 1` packages from this file's package.
            base = list(package_parts)
            up = node.level - 1
            base = base[: len(base) - up] if up else base
            parts = base + ((node.module or "").split(".") if node.module else [])
            parts = [part for part in parts if part]
            if parts:
                found.add(parts[0])
            else:
                # `from ... import x` resolving to the benchtools root: the
                # imported names themselves may be layer packages.
                for alias in node.names:
                    if alias.name in ALLOWED:
                        found.add(alias.name)
    return found


def _sources():
    return sorted(
        path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_sources_are_discovered():
    """Guard against the whole suite silently passing on an empty file list."""
    assert len(_sources()) >= 15


@pytest.mark.parametrize("path", _sources(), ids=lambda p: str(p.relative_to(ROOT)))
def test_layer_dependencies_point_one_way(path):
    layer = _layer_of(path)
    if layer not in ALLOWED:
        return                      # benchtools/__init__.py, cli.py, __main__.py
    permitted = ALLOWED[layer]
    for imported in _imported_layers(path):
        if imported not in ALLOWED:
            continue
        assert imported in permitted, (
            "%s (layer %r) imports from layer %r, which is not allowed. "
            "Permitted: %s. Dependencies must point core <- analysis <- "
            "instruments <- runner."
            % (path.relative_to(ROOT), layer, imported, ", ".join(sorted(permitted)))
        )


#: Identifiers that would betray an instrument dependency in the core.
#: Prose in a docstring may legitimately name an instrument - socket_raw.py
#: documents that the TDS3014B has no raw socket - so this is checked against
#: code identifiers, not raw text.
_INSTRUMENT_IDENTIFIERS = {
    "Tek3014B",
    "SimulatedTDS3014B",
    "ChannelSignal",
    "ChannelSetup",
    "tek3014b",
    "instruments",
}


def _code_identifiers(path: pathlib.Path):
    """Return identifiers used in code, excluding strings and docstrings."""
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            for part in (node.module or "").split("."):
                if part:
                    names.add(part)
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for part in alias.name.split("."):
                    names.add(part)
    return names


def test_core_never_references_an_instrument():
    """The specific regression that motivated this layout.

    ``transport/mock.py`` previously imported the TDS3014B simulator, which made
    the whole transport package - and therefore any future driver - depend on one
    particular oscilloscope.
    """
    offenders = []
    for path in _sources():
        if _layer_of(path) != "core":
            continue
        used = _code_identifiers(path) & _INSTRUMENT_IDENTIFIERS
        if used:
            offenders.append(
                "%s uses %s" % (path.relative_to(ROOT), ", ".join(sorted(used)))
            )
    assert not offenders, (
        "benchtools.core must not reference any instrument:\n  " + "\n  ".join(offenders)
    )


def test_core_is_importable_on_its_own():
    """Importing core must not drag in analysis, instruments or the runner."""
    import subprocess
    import sys

    script = (
        "import sys, benchtools.core\n"
        "leaked = sorted(\n"
        "    name for name in sys.modules\n"
        "    if name.startswith('benchtools.')\n"
        "    and not name.startswith('benchtools.core')\n"
        ")\n"
        "print(','.join(leaked))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT.parent),
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = [name for name in result.stdout.strip().split(",") if name]
    assert leaked == [], "importing benchtools.core also imported %s" % ", ".join(leaked)


def test_analysis_is_importable_without_instruments():
    """Analysis must be usable on stored records with no instrument present."""
    import subprocess
    import sys

    script = (
        "import sys, benchtools.analysis\n"
        "print(','.join(sorted(\n"
        "    name for name in sys.modules\n"
        "    if name.startswith('benchtools.instruments')\n"
        "    or name.startswith('benchtools.runner')\n"
        ")))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT.parent),
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = [name for name in result.stdout.strip().split(",") if name]
    assert leaked == [], "importing benchtools.analysis also imported %s" % ", ".join(leaked)
