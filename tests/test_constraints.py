"""The per-Python constraints CI and the CI image install from (#282).

pip ignores a constraints file that leaves a package out, and installs the
newest release instead. A requirement added to the ``test`` extra without
running ``etb-ci lock`` would then reach CI unpinned, and the image and CI
would drift apart without anything failing. These tests catch that.

Traces to: SWE4-UT-CONSTRAINTS.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "constraints"

#: Each constraints file and the Python leg that installs it.
FILES = ("py3.8.txt", "py3.9.txt", "py3.12.txt", "lint.txt")


def _name(requirement: str) -> str:
    """The normalised project name at the start of *requirement* (PEP 503)."""
    return re.sub(r"[-_.]+", "-", re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
                  .group(0)).lower()


def _test_extra() -> list:
    """The ``test`` extra in pyproject.toml, read without tomllib (Python 3.8)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^test = \[(.*?)^\]", text, re.M | re.S)
    assert block, "no test extra in pyproject.toml"
    return re.findall(r'"([^"]+)"', block.group(1))


def _pins(name: str) -> dict:
    pins = {}
    for line in (CONSTRAINTS / name).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            assert "==" in line, "%s: not an exact pin: %s" % (name, line)
            pins[_name(line)] = line.split("==", 1)[1].split(";", 1)[0].strip()
    return pins


@pytest.mark.parametrize("name", FILES)
def test_every_test_requirement_is_pinned(name):
    pins = _pins(name)
    missing = [r for r in _test_extra() if _name(r) not in pins]
    assert not missing, "%s does not pin %s; run etb-ci lock" % (name, missing)


@pytest.mark.parametrize("name", FILES)
def test_the_package_itself_is_not_pinned(name):
    assert "benchtools" not in _pins(name)


def test_the_lint_pin_is_the_one_lint_in_states():
    wanted = [line.strip() for line in (CONSTRAINTS / "lint.in").read_text().splitlines()
              if line.strip() and not line.startswith("#")]
    pins = _pins("lint.txt")
    for requirement in wanted:
        name, version = requirement.split("==")
        assert pins.get(_name(name)) == version, "lint.txt is stale; run etb-ci lock"


def test_each_workflow_leg_has_its_file():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    for version in re.findall(r"python-version: '([0-9.]+)'", workflow):
        assert (CONSTRAINTS / ("py%s.txt" % version)).is_file(), version
    assert "constraints/py${{ matrix.python-version }}.txt" in workflow
    lint = (ROOT / ".github" / "workflows" / "lint.yml").read_text(encoding="utf-8")
    assert "constraints/lint.txt" in lint
