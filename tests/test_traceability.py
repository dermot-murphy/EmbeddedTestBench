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

REQUIREMENTS_DOC = DOCS / "EmbeddedTestBench_SWE1_SW_Requirements.md"
ARCHITECTURE_DOC = DOCS / "EmbeddedTestBench_SWE2_SW_Architecture.md"
DESIGN_DOC = DOCS / "EmbeddedTestBench_SWE3_Detailed_Design.md"
TEST_SPEC_DOC = DOCS / "EmbeddedTestBench_SWE4_Unit_Verification.md"
MATRIX_DOC = DOCS / "EmbeddedTestBench_Traceability_Matrix.md"
REPORT_DOC = DOCS / "EmbeddedTestBench_SWE4_Unit_Verification_Report.md"

#: Requirement identifier, e.g. CORE-FR-001, JLINK-FR-060 or CORE-NFR-007.
#: One prefix per element of SWE.1 §3; a new element is registered here.
_REQUIREMENT = r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PSU|DMM|S2LP|PICO|SER|RUN)-(?:FR|NFR)-\d{3}"

#: Design unit identifier, e.g. CORE-DD-SCPI.
_DESIGN_UNIT = r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PSU|DMM|S2LP|PICO|SER|RUN)-DD-[A-Z0-9]+"


def _text(path: pathlib.Path) -> str:
    assert path.exists(), "missing work product: %s" % path.relative_to(ROOT)
    # The documents are UTF-8; the locale default (cp1252 on Windows) cannot
    # read every byte in them (#286).
    return path.read_text(encoding="utf-8")


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
         DOCS / "EmbeddedTestBench_SWE4_Unit_Verification_Report.md",
         DOCS / "EmbeddedTestBench_IF001_GPD3303D_Remote_Control_Interface.md",
         DOCS / "EmbeddedTestBench_SWE3_002_GPD3303D_Driver_Design.md",
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

    def test_every_test_file_belongs_to_a_group(self):
        """A pytest file no group names has no test-case ID and no trace (#292)."""
        named = _named_test_files(_text(TEST_SPEC_DOC))
        unnamed = sorted(
            path.relative_to(ROOT / "tests").as_posix()
            for path in (ROOT / "tests").rglob("test_*.py")
            if "__pycache__" not in path.parts
            and path.relative_to(ROOT / "tests").as_posix() not in named)
        assert not unnamed, (
            "pytest file(s) under tests/ that no group in ETB-SWE4-001 names:\n  "
            + "\n  ".join(unnamed))

    def test_every_named_test_file_exists(self):
        """A group citing a deleted file would cite tests that do not exist."""
        missing = sorted(name for name in _named_test_files(_text(TEST_SPEC_DOC))
                         if not (ROOT / "tests" / name).is_file())
        assert not missing, (
            "file(s) named by a group in ETB-SWE4-001 that are not under tests/:\n  "
            + "\n  ".join(missing))

    def test_named_files_are_read_from_the_file_column_only(self):
        """Only the file column counts, a firmware glob is skipped, and a bare
        name is a top-level file: it does not name a nested file of that name."""
        text = (
            "| SWE4-UT-TRACE | `core/test_a.py`, `test_cli.py` "
            "| Mentions `core/test_other.py` | X |\n"
            "| SWE4-UT-FWUNIT | `firmware/x/test/*.c` | Firmware | Y |\n"
        )
        named = _named_test_files(text)
        assert named == {"core/test_a.py", "test_cli.py"}
        assert "runner/test_cli.py" not in named


def _named_test_files(text: str) -> set:
    """The pytest files the groups in *text* name: each a path under tests/.

    Only a group's file column counts, and only ``.py`` names in backticks;
    a firmware glob (``firmware/.../*.c``) is not a pytest file.
    """
    named = set()
    for match in _GROUP_CELL.finditer(text):
        named.update(re.findall(r"`([\w/]+\.py)`", match.group(2).split("|")[0]))
    return named


#: A first-column cell that names a test group, matched loosely (bold or code
#: marks, any characters to the cell's end) so that a malformed ID is caught
#: rather than silently dropped; the strict form is what an ID must be.
_GROUP_CELL = re.compile(r"^\|\s*[*`]*(SWE4-UT-[^|*`\s]*)[*`]*\s*\|(.*)$", re.M)
_GROUP_ID = re.compile(r"SWE4-UT-[A-Z0-9]+")

#: What a result cell may say: a verdict, optionally with a note in brackets,
#: or "Not run:" with the reason.
_VERDICT = re.compile(r"^(?:(?:Pass|Fail|\d+ failed|Pass, \d+ skipped)(?: \(.+\))?|Not run: .+)$")


def _report_section() -> str:
    text = _text(REPORT_DOC)
    start = text.index("## 5. Results by test group")
    return text[start:text.index("\n## ", start + 1)]


def _report_rows() -> dict:
    """Test group -> its (tests, result) cells in the report's results table (section 5)."""
    rows = {}
    for match in _GROUP_CELL.finditer(_report_section()):
        cells = [cell.strip() for cell in match.group(2).split("|")]
        rows[match.group(1)] = (cells[1] if len(cells) > 1 else "",
                                cells[2] if len(cells) > 2 else "")
    return rows


def _report_results() -> set:
    """Test groups with a row in the report's results table (section 5)."""
    return set(_report_rows())


def _specified_groups() -> set:
    """Test groups defined in the specification, i.e. a table's first column."""
    return {match.group(1) for match in _GROUP_CELL.finditer(_text(TEST_SPEC_DOC))}


class TestVerificationReport:
    """Every specified test group has a result in the report, and the report has
    no result for a group the specification does not define (#286)."""

    def test_the_report_has_results(self):
        """Guard against the class passing on an empty table."""
        assert len(_report_results()) > 50

    def test_every_group_id_is_well_formed(self):
        malformed = sorted(group for group in _specified_groups() | _report_results()
                           if not _GROUP_ID.fullmatch(group))
        assert not malformed, "malformed test group ID(s): %s" % ", ".join(malformed)

    def test_every_specified_group_has_a_result(self):
        missing = sorted(_specified_groups() - _report_results())
        assert not missing, (
            "test group(s) with no row in ETB-SWE4-002 section 5:\n  " + "\n  ".join(missing))

    def test_every_result_is_for_a_specified_group(self):
        extra = sorted(_report_results() - _specified_groups())
        assert not extra, (
            "row(s) in ETB-SWE4-002 section 5 for groups ETB-SWE4-001 does not define:\n  "
            + "\n  ".join(extra))

    def test_every_result_has_a_count_and_a_verdict(self):
        offenders = []
        for group, (tests, result) in sorted(_report_rows().items()):
            if not tests.isdigit():
                offenders.append("%s: tests %r is not a count" % (group, tests))
            elif tests == "0" and not result.startswith("Not run:"):
                offenders.append("%s: %r with no tests" % (group, result))
            if not _VERDICT.match(result):
                offenders.append("%s: result %r is not a verdict" % (group, result))
        assert not offenders, "ETB-SWE4-002 section 5:\n  " + "\n  ".join(offenders)


class TestArchitectureTraceability:
    def test_architectural_elements_cited_in_code_are_defined(self):
        declared = set(re.findall(r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PICO|SER|RUN)-ARC-\d{3}", _text(ARCHITECTURE_DOC)))
        offenders = []
        for path in (ROOT / "benchtools").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for cited in set(re.findall(r"(?:CORE|ANA|INST|SCOPE|JLINK|BLE|PICO|SER|RUN)-ARC-\d{3}", path.read_text())):
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


class TestRevisionHistoryOrder:
    """Every history table lists its entries oldest first (ETB-SUP8-001 §6.2)."""

    _HEADING = re.compile(r"^#+ .*(?:revision|change) history", re.I)
    _VERSION_ROW = re.compile(r"^\| *(\d+)\.(\d+) *\|")

    def _history_tables(self):
        for path in sorted((ROOT / "docs").rglob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for start, line in enumerate(lines):
                if not self._HEADING.match(line):
                    continue
                versions = []
                for row in lines[start + 1:]:
                    if row.startswith("#"):
                        break
                    match = self._VERSION_ROW.match(row)
                    if match:
                        versions.append((int(match.group(1)), int(match.group(2))))
                yield "%s:%d" % (path.relative_to(ROOT).as_posix(), start + 1), versions

    def test_the_documents_have_revision_histories(self):
        assert sum(1 for _, versions in self._history_tables() if versions) >= 30

    def test_every_revision_history_is_oldest_first(self):
        offenders = [
            where for where, versions in self._history_tables()
            if any(later < earlier for earlier, later in zip(versions, versions[1:]))
        ]
        assert not offenders, (
            "revision history not listed oldest first:\n  " + "\n  ".join(offenders)
        )
