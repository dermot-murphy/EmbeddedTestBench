"""Export of the GitHub-only records, in scripts/export_github_records.py.

The issues, pull requests, reviews and review threads are held by GitHub
alone, so the recovery check exports them at each release (ETB-SUP8-001 §10,
ETB-RISK-016, #387). These tests run the export against a fake ``gh``: the
calls it makes, the pages it joins, a nested list cut short by GitHub, the
output directory rules, the manifest and the hashes.

Traces to: SWE4-UT-EXPORT.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_export():
    spec = importlib.util.spec_from_file_location(
        "export_github_records_script", ROOT / "scripts" / "export_github_records.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ex = load_export()

NOW = datetime.datetime(2026, 11, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)


def connection(nodes, more=False):
    return {"pageInfo": {"hasNextPage": more}, "nodes": nodes}


def pull_request(number, reviews=None, threads=None, contexts=None):
    rollup = None if contexts is None else {"state": "SUCCESS", "contexts": connection(contexts)}
    return {
        "number": number,
        "mergedBy": {"login": "owner"},
        "mergeCommit": {"oid": "m%d" % number},
        "reviews": connection(reviews or []),
        "reviewThreads": connection(threads or []),
        "commits": {"nodes": [{"commit": {"oid": "h%d" % number,
                                          "statusCheckRollup": rollup}}]},
    }


def graphql_page(prs):
    return {"data": {"repository": {"pullRequests": {
        "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": prs}}}}


class FakeGh:  # pylint: disable=too-few-public-methods
    """Answers ``gh`` calls from canned replies, keyed on the call."""

    def __init__(self, issues=None, comments=None, graphql=None, fail=None):
        self.calls = []
        self.issues = issues if issues is not None else [
            [{"number": 1}, {"number": 2}], [{"number": 3}]]
        self.comments = comments if comments is not None else [[{"id": 10}]]
        self.graphql = graphql if graphql is not None else [
            graphql_page([pull_request(2, reviews=[{"state": "APPROVED"}])]),
            graphql_page([pull_request(3, contexts=[{"name": "pytest"}])])]
        self.fail = fail

    def __call__(self, argv, capture_output, check):
        assert capture_output and not check
        self.calls.append(argv)
        args = argv[1:]
        if self.fail and self.fail in " ".join(args):
            return subprocess.CompletedProcess(argv, 1, b"", b"HTTP 404: Not Found")
        if args == ["--version"]:
            out = "gh version 9.9.9 (2099-01-01)\nhttps://example\n"
        elif args[:1] == ["repo"]:
            out = "acme/bench\n"
        elif args[:2] == ["api", "graphql"]:
            out = json.dumps(self.graphql)
        elif "issues/comments" in args[-1]:
            out = json.dumps(self.comments)
        elif "issues/events" in args[-1]:
            out = json.dumps([[{"event": "labeled"}, {"event": "closed"}]])
        elif "/releases?" in args[-1]:
            out = json.dumps([[{"tag_name": "v1.0", "body": "notes"}]])
        elif "/milestones?" in args[-1]:
            out = json.dumps([[{"title": "M1"}], [{"title": "M2"}]])
        elif "/issues?" in args[-1]:
            out = json.dumps(self.issues)
        elif "/commits/" in args[-1]:
            out = json.dumps({"sha": "abc123"})
        else:
            raise AssertionError("unexpected gh call: %r" % argv)
        return subprocess.CompletedProcess(argv, 0, out.encode("utf-8"), b"")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestExport:
    def test_writes_every_record_joined_across_pages(self, tmp_path):
        out = tmp_path / "export"
        ex.export(out, "acme/bench", run=FakeGh(), now=NOW)
        assert [x["number"] for x in read(out / "issues.json")] == [1, 2, 3]
        assert read(out / "issue_comments.json") == [{"id": 10}]
        assert read(out / "issue_events.json") == [{"event": "labeled"}, {"event": "closed"}]
        assert read(out / "releases.json") == [{"tag_name": "v1.0", "body": "notes"}]
        assert read(out / "milestones.json") == [{"title": "M1"}, {"title": "M2"}]
        prs = read(out / "pull_requests.json")
        assert [pr["number"] for pr in prs] == [2, 3]
        assert prs[0]["reviews"]["nodes"] == [{"state": "APPROVED"}]
        assert prs[0]["mergedBy"] == {"login": "owner"}

    def test_every_list_call_pages_through_everything(self, tmp_path):
        fake = FakeGh()
        ex.export(tmp_path / "export", "acme/bench", run=fake, now=NOW)
        api = [call for call in fake.calls if call[1] == "api"]
        assert len(api) == 6
        for call in api:
            assert call[0] == "gh" and "--paginate" in call and "--slurp" in call
        rest = [call[-1] for call in api if call[2] != "graphql"]
        assert rest == ["repos/acme/bench/issues?state=all&per_page=100",
                        "repos/acme/bench/issues/comments?per_page=100",
                        "repos/acme/bench/issues/events?per_page=100",
                        "repos/acme/bench/releases?per_page=100",
                        "repos/acme/bench/milestones?state=all&per_page=100"]
        graphql = [call for call in api if call[2] == "graphql"][0]
        assert "owner=acme" in graphql and "name=bench" in graphql
        query = [arg for arg in graphql if arg.startswith("query=")][0]
        assert "$endCursor" in query and "endCursor" in query.split("pageInfo", 1)[1]

    def test_the_query_asks_for_the_approval_evidence(self):
        query = ex.PULL_REQUEST_QUERY
        for field in ("mergedBy", "mergedAt", "mergeCommit", "baseRefName", "reviews",
                      "reviewThreads", "isResolved", "statusCheckRollup", "conclusion"):
            assert field in query

    def test_manifest_counts_and_hashes_each_file(self, tmp_path):
        out = tmp_path / "export"
        manifest = ex.export(out, "acme/bench", ref="v1.0", run=FakeGh(), now=NOW)
        assert manifest == read(out / "manifest.json")
        assert manifest["repository"] == "acme/bench"
        assert manifest["exported_at"] == "2026-11-18T12:00:00Z"
        assert manifest["ref"] == "v1.0" and manifest["commit"] == "abc123"
        assert manifest["gh"] == "gh version 9.9.9 (2099-01-01)"
        assert {name: entry["records"] for name, entry in manifest["files"].items()} == {
            "issues.json": 3, "issue_comments.json": 1, "issue_events.json": 2,
            "releases.json": 1, "milestones.json": 2, "pull_requests.json": 2}
        for name, entry in manifest["files"].items():
            assert entry["sha256"] == hashlib.sha256((out / name).read_bytes()).hexdigest()

    def test_sha256sums_lists_every_file_in_sha256sum_form(self, tmp_path):
        out = tmp_path / "export"
        ex.export(out, "acme/bench", run=FakeGh(), now=NOW)
        lines = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        names = sorted(path.name for path in out.iterdir() if path.name != "SHA256SUMS")
        assert [line.split("  ", 1)[1] for line in lines] == names
        for line in lines:
            digest, name = line.split("  ", 1)
            assert digest == hashlib.sha256((out / name).read_bytes()).hexdigest()

    def test_every_file_is_written_with_lf_line_endings(self, tmp_path):
        out = tmp_path / "export"
        ex.export(out, "acme/bench", run=FakeGh(), now=NOW)
        for path in out.iterdir():
            data = path.read_bytes()
            assert b"\r" not in data and data.endswith(b"\n"), path.name

    def test_without_a_ref_no_commit_is_looked_up(self, tmp_path):
        fake = FakeGh()
        manifest = ex.export(tmp_path / "export", "acme/bench", run=fake, now=NOW)
        assert manifest["ref"] is None and manifest["commit"] is None
        assert not [call for call in fake.calls if "/commits/" in call[-1]]


class TestRefusals:
    def test_refuses_a_directory_inside_the_repository(self):
        fake = FakeGh()
        with pytest.raises(ex.ExportError, match="inside the repository"):
            ex.export(ROOT / "build" / "export", "acme/bench", run=fake, now=NOW)
        assert not fake.calls
        assert not (ROOT / "build" / "export").exists()

    def test_refuses_a_directory_that_is_not_empty(self, tmp_path):
        (tmp_path / "old.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ex.ExportError, match="not empty"):
            ex.export(tmp_path, "acme/bench", run=FakeGh(), now=NOW)

    def test_an_empty_existing_directory_is_used(self, tmp_path):
        ex.export(tmp_path, "acme/bench", run=FakeGh(), now=NOW)
        assert (tmp_path / "manifest.json").is_file()

    @pytest.mark.parametrize("cut", ["reviews", "reviewThreads", "comments", "contexts"])
    def test_a_nested_list_cut_short_fails_the_export(self, tmp_path, cut):
        thread = {"isResolved": True,
                  "comments": connection([{"body": "x"}], more=cut == "comments")}
        pr = pull_request(7, reviews=[{"state": "COMMENTED"}], threads=[thread],
                          contexts=[{"name": "lint"}])
        if cut in ("reviews", "reviewThreads"):
            pr[cut]["pageInfo"]["hasNextPage"] = True
        if cut == "contexts":
            pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"][
                "pageInfo"]["hasNextPage"] = True
        out = tmp_path / "export"
        with pytest.raises(ex.ExportError, match="#7 .*incomplete"):
            ex.export(out, "acme/bench", run=FakeGh(graphql=[graphql_page([pr])]), now=NOW)
        assert not out.exists()

    def test_a_graphql_error_fails_the_export(self, tmp_path):
        page = {"errors": [{"message": "rate limited"}]}
        with pytest.raises(ex.ExportError, match="rate limited"):
            ex.export(tmp_path / "e", "acme/bench", run=FakeGh(graphql=[page]), now=NOW)

    def test_a_failed_gh_call_fails_the_export_with_its_message(self, tmp_path):
        with pytest.raises(ex.ExportError, match="HTTP 404"):
            ex.export(tmp_path / "e", "acme/bench", run=FakeGh(fail="issues/comments"), now=NOW)
        assert not (tmp_path / "e").exists()

    def test_a_page_that_is_not_a_list_fails(self, tmp_path):
        with pytest.raises(ex.ExportError, match="not a list"):
            ex.export(tmp_path / "e", "acme/bench",
                      run=FakeGh(issues=[{"message": "x"}]), now=NOW)


class TestCommandLine:
    def test_main_reports_a_refusal_and_returns_1(self, capsys):
        assert ex.main([str(ROOT / "build" / "export"), "--repo", "acme/bench"]) == 1
        assert "inside the repository" in capsys.readouterr().err

    def test_main_exports_and_prints_the_counts(self, tmp_path, capsys, monkeypatch):
        fake = FakeGh()
        export, default_repo = ex.export, ex.default_repo
        monkeypatch.setattr(
            ex, "export", lambda out, repo, ref: export(out, repo, ref, run=fake, now=NOW))
        monkeypatch.setattr(ex, "default_repo", lambda: default_repo(run=fake))
        assert ex.main([str(tmp_path / "export")]) == 0
        assert ["gh", "repo", "view", "--json", "nameWithOwner", "-q",
                ".nameWithOwner"] in fake.calls
        printed = capsys.readouterr().out
        assert "issues.json" in printed and "3 records" in printed
        assert "exported acme/bench at 2026-11-18T12:00:00Z" in printed
