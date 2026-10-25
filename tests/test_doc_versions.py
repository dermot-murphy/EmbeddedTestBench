"""Document versions derived from the revision history, in scripts/doc_versions.py.

A controlled document's Version and Date are the version and date of the last
row of its revision history; the identification table links to that row
(ETB-SUP8-001 §6.2, #210). These tests cover reading the history, the check
the suite enforces on every controlled document, numbering the ``next`` rows
at release, the ETB-SVD-001 §5.3 table, and the merge driver that keeps two
appended rows.

Traces to: SWE4-UT-DOCVER.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_doc_versions():
    spec = importlib.util.spec_from_file_location(
        "doc_versions_script", ROOT / "scripts" / "doc_versions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dv = load_doc_versions()

LINK = "[latest, §2](#2-revision-history)"


def document(rows, version=LINK, date=LINK, after=""):
    """A minimal controlled document with the given history rows."""
    return "\n".join([
        "# Plan",
        "",
        "## 1. Document Identification & Control",
        "",
        "| Field | Value | Field | Value |",
        "|---|---|---|---|",
        "| **Document ID** | ETB-X-001 | **Version** | %s |" % version,
        "| **Project** | Embedded Test Bench | **Date** | %s |" % date,
        "",
        "## 2. Revision History",
        "",
        "| Version | Date | Author | Description of Change |",
        "|---|---|---|---|",
    ] + ["| %s | %s | Claude | change |" % row for row in rows] + [
        "",
        "## 3. Body",
        "",
        after,
        "",
    ])


class TestReading:
    def test_anchor_is_the_one_github_gives_the_heading(self):
        assert dv.anchor("2. Revision History") == "#2-revision-history"
        assert dv.anchor("Revision History") == "#revision-history"

    def test_link_names_the_section_number_when_the_heading_has_one(self):
        assert dv.latest_link(document([("0.1", "2026-01-01")])) == LINK
        unnumbered = document([("0.1", "2026-01-01")]).replace(
            "## 2. Revision History", "## Revision History")
        assert dv.latest_link(unnumbered) == "[latest, Revision History](#revision-history)"

    def test_current_is_the_last_row_including_a_next_row(self):
        text = document([("0.1", "2026-01-01"), ("0.2", "2026-02-01")])
        assert dv.current(text) == ("0.2", "2026-02-01")
        text = document([("0.1", "2026-01-01"), ("next", "2026-03-01")])
        assert dv.current(text) == ("next", "2026-03-01")

    def test_rows_in_later_sections_are_not_history(self):
        text = document([("0.1", "2026-01-01")], after="| 9.9 | 2030-01-01 | x | y |")
        assert dv.current(text) == ("0.1", "2026-01-01")


class TestExpand:
    def test_both_links_are_replaced_by_the_last_rows_values(self):
        text = dv.expand(document([("0.1", "2026-01-01"), ("0.2", "2026-02-01")]))
        assert "| **Version** | 0.2 |" in text
        assert "| **Date** | 2026-02-01 |" in text
        assert "[latest" not in text

    def test_a_date_cell_after_the_history_is_left_alone(self):
        text = dv.expand(document([("0.1", "2026-01-01")],
                                  after="| **Date** | %s |" % LINK))
        assert "| **Date** | 2026-01-01 |" in text
        assert text.count(LINK) == 1

    def test_a_literal_value_is_left_alone(self):
        text = document([("0.1", "2026-01-01")], version="0.1", date="2026-01-01")
        assert dv.expand(text) == text


class TestCheck:
    def test_a_well_formed_document_has_no_problems(self):
        rows = [("0.1", "2026-01-01"), ("0.2", "2026-02-01"), ("next", "2026-03-01")]
        assert dv.problems(document(rows)) == []

    def test_a_literal_version_or_date_is_a_problem(self):
        found = dv.problems(document([("0.1", "2026-01-01")], version="0.1", date="2026-01-01"))
        assert len(found) == 2
        assert "**Version**" in found[0] and "**Date**" in found[1]

    def test_a_link_to_another_anchor_is_a_problem(self):
        found = dv.problems(document([("0.1", "2026-01-01")], version="[latest, §3](#3-body)"))
        assert len(found) == 1 and "**Version**" in found[0]

    def test_a_numbered_row_after_a_next_row_is_a_problem(self):
        found = dv.problems(document([("0.1", "a"), ("next", "b"), ("0.2", "c")]))
        assert any("after a next row" in message for message in found)

    def test_a_repeated_or_decreasing_version_is_a_problem(self):
        assert dv.problems(document([("0.2", "a"), ("0.2", "b")]))
        assert dv.problems(document([("0.10", "a"), ("0.9", "b")]))
        assert dv.problems(document([("0.9", "a"), ("0.10", "b")])) == []

    def test_a_history_that_starts_with_next_is_a_problem(self):
        assert any("first history row" in message
                   for message in dv.problems(document([("next", "a")])))

    def test_a_held_back_document_may_hold_its_last_rows_values(self):
        text = document([("0.1", "a"), ("0.2", "b")], version="0.2", date="b")
        assert dv.problems(text, held_back=True) == []
        stale = document([("0.1", "a"), ("0.2", "b")], version="0.1", date="a")
        assert len(dv.problems(stale, held_back=True)) == 2
        assert dv.problems(document([("0.1", "a")]), held_back=True) == []

    def test_every_controlled_document_passes(self):
        documents = dv.controlled_documents(ROOT)
        assert len(documents) >= 30
        offenders = ["%s: %s" % (rel, message) for rel in documents
                     for message in dv.problems(dv.read_text(ROOT / rel),
                                                rel in dv.HELD_BACK)]
        assert not offenders, "\n  ".join(["document versioning:"] + offenders)


class TestNumber:
    def test_each_next_row_is_one_minor_version_above_the_row_before(self):
        rows = [("0.9", "a"), ("next", "b"), ("next", "c")]
        numbered = dv.number(document(rows))
        assert dv.history(numbered)[-2:] == [(14, "0.10", "b"), (15, "0.11", "c")]
        assert dv.problems(numbered) == []

    def test_numbering_twice_changes_nothing_more(self):
        once = dv.number(document([("1.3", "a"), ("next", "b")]))
        assert dv.number(once) == once

    def test_a_first_row_of_next_cannot_be_numbered(self):
        with pytest.raises(ValueError):
            dv.number(document([("next", "a")]))

    def test_the_svd_table_takes_the_versions_of_known_documents(self):
        svd = "\n".join([
            "### 5.3 Documents",
            "",
            "| Document ID | Title | Version | Status |",
            "|---|---|---|---|",
            "| ETB-A-001 | A | 0.1 | Draft |",
            "| ETB-B-001 | B | 0.4 | Draft |",
            "",
            "### 5.4 Next",
            "| ETB-A-001 | A | 0.1 | Draft |",
        ])
        updated = dv.svd_table(svd, {"ETB-A-001": "0.2"})
        assert "| ETB-A-001 | A | 0.2 | Draft |" in updated
        assert "| ETB-B-001 | B | 0.4 | Draft |" in updated
        assert updated.endswith("| ETB-A-001 | A | 0.1 | Draft |")

    def test_number_on_a_copy_of_the_documents_leaves_them_all_valid(self, tmp_path):
        shutil.copytree(ROOT / "docs", tmp_path / "docs")
        dv.run_number(dv.controlled_documents(tmp_path), tmp_path)
        for rel in dv.controlled_documents(tmp_path):
            text = dv.read_text(tmp_path / rel)
            assert dv.problems(text, rel in dv.HELD_BACK) == [], rel
            assert dv.current(text)[0] != dv.NEXT, rel


class TestFiles:
    def test_write_keeps_crlf_line_endings(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_bytes(b"a\r\nb\r\n")
        dv.write_text(path, dv.read_text(path) + "c\n")
        assert path.read_bytes() == b"a\r\nb\r\nc\r\n"

    def test_write_keeps_lf_line_endings(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_bytes(b"a\nb\n")
        dv.write_text(path, dv.read_text(path) + "c\n")
        assert path.read_bytes() == b"a\nb\nc\n"


class TestMergeDriver:
    BASE = document([("0.1", "a")])

    def test_two_appended_rows_are_both_kept_numbered_first(self):
        merged = "\n".join([
            "| 0.1 | a | Claude | change |",
            "<<<<<<< ours",
            "| next | b | Claude | ours |",
            "||||||| base",
            "=======",
            "| 0.2 | c | Claude | theirs |",
            ">>>>>>> theirs",
            "",
        ])
        text, left = dv.merge_rows(merged)
        assert left == 0
        assert text.split("\n")[:3] == [
            "| 0.1 | a | Claude | change |",
            "| 0.2 | c | Claude | theirs |",
            "| next | b | Claude | ours |",
        ]

    @pytest.mark.parametrize("ours, base", [
        (["prose, not a row"], []),
        (["| next | b | Claude | ours |"], ["| 0.1 | a | Claude | change |"]),
    ])
    def test_any_other_conflict_is_left_for_a_person(self, ours, base):
        merged = "\n".join(["<<<<<<< ours"] + ours + ["||||||| base"] + base
                           + ["=======", "| next | c | Claude | theirs |", ">>>>>>> theirs"])
        text, left = dv.merge_rows(merged)
        assert left == 1
        assert text == merged

    @pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
    def test_the_driver_merges_two_appended_rows_in_files(self, tmp_path):
        base, ours, theirs = (tmp_path / name for name in ("base", "ours", "theirs"))
        base.write_text(self.BASE, encoding="utf-8")
        ours.write_text(document([("0.1", "a"), ("next", "b")]), encoding="utf-8")
        theirs.write_text(document([("0.1", "a"), ("next", "c")]), encoding="utf-8")
        assert dv.run_merge(str(base), str(ours), str(theirs)) == 0
        text = ours.read_text(encoding="utf-8")
        assert [row[1:] for row in dv.history(text)] == [
            ("0.1", "a"), ("next", "b"), ("next", "c")]
        assert "<<<<<<<" not in text
        assert dv.problems(text) == []

    @pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
    def test_the_driver_reports_a_conflict_it_cannot_resolve(self, tmp_path):
        base, ours, theirs = (tmp_path / name for name in ("base", "ours", "theirs"))
        base.write_text(self.BASE, encoding="utf-8")
        ours.write_text(self.BASE.replace("# Plan", "# Plan A"), encoding="utf-8")
        theirs.write_text(self.BASE.replace("# Plan", "# Plan B"), encoding="utf-8")
        assert dv.run_merge(str(base), str(ours), str(theirs)) == 1
        assert "<<<<<<<" in ours.read_text(encoding="utf-8")
