"""Consistency between the code and the ASPICE work products.

Traceability documents rot silently: a requirement is added and never traced, a
design unit is renamed and the docstring pointing at it goes stale, an element is
deleted and its rows linger. None of that breaks a build, so none of it gets
noticed until an assessment.

These tests make the documents part of the build. They check consistency, not
content — whether a requirement is *well written* is a review question, but
whether it is *traced at all* is mechanical.

Traces to: SWE4-UT-TRACE, and the SWE.1/2/3/4 base practices for bidirectional
traceability.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "aspice"
SOURCE_DIRS = (ROOT / "benchtools", ROOT / "tests")

REQUIREMENTS_DOC = DOCS / "TestBench_SWE1_SW_Requirements.md"
ARCHITECTURE_DOC = DOCS / "TestBench_SWE2_SW_Architecture.md"
DESIGN_DOC = DOCS / "TestBench_SWE3_Detailed_Design.md"
TEST_SPEC_DOC = DOCS / "TestBench_SWE4_Unit_Verification.md"
MATRIX_DOC = DOCS / "TestBench_Traceability_Matrix.md"

#: Requirement identifier, e.g. CORE-FR-001, JLINK-FR-060 or CORE-NFR-007.
#: One prefix per element of SWE.1 §3; a new element is registered here.
_REQUIREMENT = r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PSU|DMM|S2LP|PICO|RUN)-(?:FR|NFR)-\d{3}"

#: Design unit identifier, e.g. CORE-DD-SCPI.
_DESIGN_UNIT = r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PSU|DMM|S2LP|PICO|RUN)-DD-[A-Z0-9]+"


def _text(path: pathlib.Path) -> str:
    assert path.exists(), "missing work product: %s" % path.relative_to(ROOT)
    return path.read_text()


def _declared_requirements() -> set:
    """Requirements defined in SWE.1, i.e. appearing in a table's first column."""
    return set(re.findall(r"^\| (%s)" % _REQUIREMENT, _text(REQUIREMENTS_DOC), re.M))


def _source_files():
    for directory in SOURCE_DIRS:
        for path in directory.rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path


class TestWorkProductsExist:
    @pytest.mark.parametrize(
        "path",
        [REQUIREMENTS_DOC, ARCHITECTURE_DOC, DESIGN_DOC, TEST_SPEC_DOC, MATRIX_DOC,
         DOCS / "TestBench_SWE4_Unit_Verification_Report.md",
         DOCS / "TestBench_IF001_GPD3303D_Remote_Control_Interface.md",
         DOCS / "TestBench_SWE3_002_GPD3303D_Driver_Design.md",
         ROOT / "docs" / "tek3014b" / "VISA_Determination_Report.md"],
        ids=lambda p: p.name,
    )
    def test_present(self, path):
        assert path.exists(), "missing work product: %s" % path


class TestRequirementTraceability:
    def test_requirements_are_declared(self):
        """Guard against the whole class passing on an empty set."""
        assert len(_declared_requirements()) > 50

    def test_every_requirement_appears_in_the_matrix(self):
        matrix = _text(MATRIX_DOC)
        missing = sorted(r for r in _declared_requirements() if r not in matrix)
        assert not missing, (
            "%d requirement(s) are not traced in the traceability matrix: %s"
            % (len(missing), ", ".join(missing))
        )

    def test_the_matrix_has_no_orphan_requirements(self):
        """A row naming a requirement SWE.1 does not define is a stale row."""
        declared = _declared_requirements()
        claimed = set(re.findall(_REQUIREMENT, _text(MATRIX_DOC)))
        orphans = sorted(claimed - declared)
        assert not orphans, (
            "the matrix references %d requirement(s) that SWE.1 does not define: %s"
            % (len(orphans), ", ".join(orphans))
        )

    def test_requirements_cited_in_code_are_defined(self):
        """A docstring may not cite a requirement that does not exist."""
        declared = _declared_requirements()
        offenders = []
        for path in _source_files():
            for cited in set(re.findall(_REQUIREMENT, path.read_text())):
                if cited not in declared:
                    offenders.append("%s cites %s" % (path.relative_to(ROOT), cited))
        assert not offenders, (
            "undefined requirement(s) cited in source:\n  " + "\n  ".join(sorted(offenders))
        )


class TestDesignTraceability:
    def test_design_units_are_declared(self):
        assert len(set(re.findall(_DESIGN_UNIT, _text(DESIGN_DOC)))) > 15

    def test_design_units_cited_in_code_are_defined(self):
        """Every ``Traces to: ...-DD-X`` must name a section of SWE.3."""
        declared = set(re.findall(_DESIGN_UNIT, _text(DESIGN_DOC)))
        offenders = []
        for path in (ROOT / "benchtools").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for cited in set(re.findall(_DESIGN_UNIT, path.read_text())):
                if cited not in declared:
                    offenders.append("%s cites %s" % (path.relative_to(ROOT), cited))
        assert not offenders, (
            "undefined design unit(s) cited in source:\n  " + "\n  ".join(sorted(offenders))
        )

    def test_every_module_declares_its_trace(self):
        """Upward traceability is carried in the artefact, not only in a table."""
        offenders = [
            str(path.relative_to(ROOT))
            for path in _source_files()
            if "Traces to" not in path.read_text()
        ]
        assert not offenders, (
            "module(s) with no 'Traces to' line in their docstring:\n  "
            + "\n  ".join(sorted(offenders))
        )


class TestTestGroupTraceability:
    def test_test_groups_are_declared(self):
        assert len(set(re.findall(r"SWE4-UT-[A-Z0-9]+", _text(TEST_SPEC_DOC)))) > 15

    def test_test_groups_cited_in_tests_are_declared(self):
        declared = set(re.findall(r"SWE4-UT-[A-Z0-9]+", _text(TEST_SPEC_DOC)))
        offenders = []
        for path in (ROOT / "tests").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for cited in set(re.findall(r"SWE4-UT-[A-Z0-9]+", path.read_text())):
                if cited not in declared:
                    offenders.append("%s cites %s" % (path.relative_to(ROOT), cited))
        assert not offenders, (
            "test group(s) cited in tests but absent from the test specification:\n  "
            + "\n  ".join(sorted(offenders))
        )


class TestArchitectureTraceability:
    def test_architectural_elements_cited_in_code_are_defined(self):
        declared = set(re.findall(r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PICO|RUN)-ARC-\d{3}", _text(ARCHITECTURE_DOC)))
        offenders = []
        for path in (ROOT / "benchtools").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for cited in set(re.findall(r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PICO|RUN)-ARC-\d{3}", path.read_text())):
                if cited not in declared:
                    offenders.append("%s cites %s" % (path.relative_to(ROOT), cited))
        assert not offenders, (
            "undefined architectural element(s) cited in source:\n  "
            + "\n  ".join(sorted(offenders))
        )

    def test_every_decision_is_traced_in_the_matrix(self):
        """Each AD-nn in SWE.2 must be accounted for in the matrix."""
        decisions = set(re.findall(r"^### (AD-\d+)", _text(ARCHITECTURE_DOC), re.M))
        assert len(decisions) >= 8
        matrix = _text(MATRIX_DOC)
        missing = sorted(d for d in decisions if d not in matrix)
        assert not missing, (
            "architectural decision(s) not traced in the matrix: %s" % ", ".join(missing)
        )
