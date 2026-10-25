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
import subprocess

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


class TestCheckRows:
    @pytest.mark.parametrize("version", ["Next", "NEXT", "0.7.1", "v0.7", "**next**", ""])
    def test_a_row_whose_version_is_not_recognised_is_a_problem(self, version):
        found = dv.problems(document([("0.1", "a"), (version, "b")]))
        assert any("neither major.minor nor next" in message for message in found)

    def test_a_held_back_document_given_a_next_row_must_take_the_links(self):
        text = document([("0.1", "a"), ("next", "b")], version="0.1", date="a")
        found = dv.problems(text, held_back=True)
        assert len(found) == 2 and all("held-back" in message for message in found)


class TestCommandLine:
    def test_check_exits_0_on_the_repository(self, capsys):
        assert dv.main(["check"]) == 0
        assert capsys.readouterr().out == ""

    def test_check_exits_1_and_names_the_problem(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "x.md").write_text(
            document([("0.1", "a")], version="0.1"), encoding="utf-8")
        monkeypatch.setattr(dv, "ROOT", tmp_path)
        assert dv.main(["check"]) == 1
        assert "docs/x.md: **Version**" in capsys.readouterr().out

    def test_list_names_every_controlled_document(self, capsys):
        assert dv.main(["list"]) == 0
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == len(dv.controlled_documents(ROOT))
        assert any(line.startswith("ETB-SUP8-001 ") for line in lines)

    def test_number_with_a_file_numbers_that_file_only(self, tmp_path, monkeypatch):
        (tmp_path / "docs").mkdir()
        for name in ("a.md", "b.md"):
            (tmp_path / "docs" / name).write_text(
                document([("0.1", "a"), ("next", "b")]), encoding="utf-8")
        monkeypatch.setattr(dv, "ROOT", tmp_path)
        assert dv.main(["number", "docs/a.md"]) == 0
        assert dv.current(dv.read_text(tmp_path / "docs" / "a.md"))[0] == "0.2"
        assert dv.current(dv.read_text(tmp_path / "docs" / "b.md"))[0] == "next"

    def test_number_skips_a_file_with_no_history(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "plain.md").write_text("# Notes\n", encoding="utf-8")
        monkeypatch.setattr(dv, "ROOT", tmp_path)
        assert dv.main(["number", "docs/plain.md"]) == 0
        assert "skipped" in capsys.readouterr().out


def conflict(ours, base, theirs):
    """``git merge-file --diff3`` output for one conflict in a history."""
    return "\n".join(["## 2. Revision History", "", "| Version | Date | Author | Change |",
                      "|---|---|---|---|", "| 0.1 | a | Claude | first |",
                      "<<<<<<< ours"] + ours + ["||||||| base"] + base + ["======="]
                     + theirs + [">>>>>>> theirs", "", "## 3. Body", ""])


def rows_of(text):
    return [line for line in text.split("\n") if line.startswith("| 0.") or
            line.startswith("| next")]


class TestMergeRows:
    def test_two_appended_rows_keep_theirs_first(self):
        text, left = dv.merge_rows(conflict(["| next | c | Claude | ours |"], [],
                                            ["| next | b | Claude | theirs |"]))
        assert left == 0
        assert rows_of(text) == ["| 0.1 | a | Claude | first |",
                                 "| next | b | Claude | theirs |",
                                 "| next | c | Claude | ours |"]

    def test_numbered_rows_go_before_next_rows(self):
        text, _ = dv.merge_rows(conflict(["| next | c | Claude | ours |"], [],
                                         ["| 0.2 | b | Claude | theirs |"]))
        assert rows_of(text)[1:] == ["| 0.2 | b | Claude | theirs |",
                                     "| next | c | Claude | ours |"]

    def test_the_back_merge_takes_the_numbers_and_keeps_the_new_rows(self):
        """develop (ours) holds X as next and added Y; main (theirs) numbered X."""
        text, left = dv.merge_rows(conflict(
            ["| next | b | Claude | X |", "| next | c | Claude | Y |"],
            ["| next | b | Claude | X |"],
            ["| 0.2 | b | Claude | X |"]))
        assert left == 0
        assert rows_of(text)[1:] == ["| 0.2 | b | Claude | X |", "| next | c | Claude | Y |"]

    def test_a_numbered_row_on_ours_replaces_the_same_change_as_next_on_theirs(self):
        text, _ = dv.merge_rows(conflict(
            ["| 0.2 | b | Claude | X |"], ["| next | b | Claude | X |"],
            ["| next | b | Claude | X |", "| next | c | Claude | Y |"]))
        assert rows_of(text)[1:] == ["| 0.2 | b | Claude | X |", "| next | c | Claude | Y |"]

    def test_crlf_rows_are_resolved(self):
        text, left = dv.merge_rows(conflict(["| next | c | Claude | ours |\r"], [],
                                            ["| next | b | Claude | theirs |\r"]))
        assert left == 0 and "<<<<<<<" not in text

    @pytest.mark.parametrize("ours", [
        ["prose, not a row"],
        ["| Next | c | Claude | typo |"],
        ["| ETB-X-002 | another table's row |"],
    ])
    def test_a_conflict_that_is_not_only_history_rows_is_left(self, ours):
        merged = conflict(ours, [], ["| next | b | Claude | theirs |"])
        assert dv.merge_rows(merged) == (merged, 1)

    def test_a_table_conflict_outside_the_history_is_left(self):
        merged = "\n".join(["## 5. Requirements", "<<<<<<< ours", "| 0.2 | x | y | z |",
                            "||||||| base", "=======", "| 0.3 | x | y | z |", ">>>>>>> theirs"])
        assert dv.merge_rows(merged) == (merged, 1)

    def test_the_marker_size_is_honoured(self):
        merged = conflict(["| next | c | Claude | ours |"], [],
                          ["| next | b | Claude | theirs |"])
        wide = (merged.replace("<<<<<<<", "<" * 9).replace("|||||||", "|" * 9)
                .replace("=======", "=" * 9).replace(">>>>>>>", ">" * 9))
        assert dv.merge_rows(wide, 9)[1] == 0


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@needs_git
class TestMergeDriver:
    BASE = document([("0.1", "a")])

    def files(self, tmp_path, ours, theirs, newline="\n"):
        paths = [tmp_path / name for name in ("base", "ours", "theirs")]
        for path, text in zip(paths, (self.BASE, ours, theirs)):
            path.write_bytes(text.replace("\n", newline).encode("utf-8"))
        return [str(path) for path in paths]

    def test_two_appended_rows_merge_in_files(self, tmp_path):
        base, ours, theirs = self.files(tmp_path, document([("0.1", "a"), ("next", "b")]),
                                        document([("0.1", "a"), ("next", "c")]))
        assert dv.run_merge(base, ours, theirs) == 0
        text = dv.read_text(ours)
        assert [row[1:] for row in dv.history(text)] == [
            ("0.1", "a"), ("next", "c"), ("next", "b")]
        assert dv.problems(text) == []

    def test_crlf_files_merge(self, tmp_path):
        base, ours, theirs = self.files(tmp_path, document([("0.1", "a"), ("next", "b")]),
                                        document([("0.1", "a"), ("next", "c")]), "\r\n")
        assert dv.run_merge(base, ours, theirs) == 0
        assert "<<<<<<<" not in dv.read_text(ours)

    def test_a_conflict_it_cannot_resolve_is_left_with_named_markers(self, tmp_path):
        base, ours, theirs = self.files(tmp_path, self.BASE.replace("# Plan", "# Plan A"),
                                        self.BASE.replace("# Plan", "# Plan B"))
        assert dv.run_merge(base, ours, theirs, 7, "docs/x.md") == 1
        text = dv.read_text(ours)
        assert "<<<<<<< docs/x.md (ours)" in text and ">>>>>>> docs/x.md (theirs)" in text

    def test_a_failure_falls_back_to_gits_merge_not_to_ours(self, tmp_path, monkeypatch):
        def broken(*_):
            raise ValueError("broken")
        monkeypatch.setattr(dv, "merge_rows", broken)
        base, ours, theirs = self.files(tmp_path, document([("0.1", "a"), ("next", "b")]),
                                        document([("0.1", "a"), ("next", "c")]))
        assert dv.run_merge(base, ours, theirs) == 1
        text = dv.read_text(ours)
        assert "| next | b |" in text and "| next | c |" in text and "<<<<<<<" in text

    def test_the_installed_command_falls_back_when_the_script_cannot_run(self, tmp_path):
        """A git merge with the driver pointing at a missing interpreter."""
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args):
            return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                                  cwd=str(repo), stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, check=False)
        git("init", "-q", "-b", "develop")
        (repo / "docs").mkdir()
        (repo / ".gitattributes").write_text("docs/**/*.md merge=etb-history\n")
        doc = repo / "docs" / "x.md"
        doc.write_text(self.BASE, encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "base")
        for branch, row in (("a", ("next", "b")), ("b", ("next", "c"))):
            git("checkout", "-q", "-b", branch, "develop")
            doc.write_text(document([("0.1", "a"), row]), encoding="utf-8")
            git("commit", "-qam", branch)
        git("config", "merge.etb-history.driver",
            dv.driver_command(str(tmp_path / "no-such-python")))
        assert git("merge", "-q", "a").returncode != 0
        text = dv.read_text(doc)
        assert "| next | b |" in text and "| next | c |" in text and "<<<<<<<" in text
