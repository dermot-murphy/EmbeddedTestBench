#!/usr/bin/env python3
"""Export the records GitHub alone holds: issues, pull requests and reviews.

    python scripts/export_github_records.py OUT_DIR [--repo OWNER/NAME] [--ref REF]

A git clone holds the history, the documents and the tags, but not the issue
tracker or the pull request records. Those are the project's problem, change
request, review and approval records (ETB-SUP1-001 §6.5, ETB-SUP8-001 §5.7,
ETB-SUP9-001 §6, ETB-SUP10-001 §6), and the recovery check cannot restore
them from a mirror (ETB-SUP8-002 §4.2, ETB-RISK-016). This script writes them
to files at each release, as part of the recovery check (ETB-SUP8-001 §10).

It writes, into ``OUT_DIR``, which must be empty or absent and outside this
repository's working tree:

- ``issues.json``: every issue and pull request as the issue tracker holds it
  (``GET /repos/{repo}/issues?state=all``), with labels, state and dates;
- ``issue_comments.json``: every comment on an issue or a pull request's
  conversation (``GET /repos/{repo}/issues/comments``);
- ``pull_requests.json``: every pull request with its base and head, who
  merged it, when, its merge commit, its reviews, its review threads with
  their comments and whether each is resolved, and the check results of its
  last commit (GraphQL, paged);
- ``manifest.json``: the repository, the time, the ref and its commit, the
  ``gh`` version, and each file's record count and SHA-256;
- ``SHA256SUMS``: the same hashes, in the form ``sha256sum -c`` reads.

A nested list that GitHub reports as longer than one page (reviews, review
threads, thread comments or check contexts of one pull request) fails the
export rather than being cut short silently.

Not exported: CI logs. GitHub keeps them for a limited time; the check
results of each pull request's last commit are exported instead.

The calls go through ``gh api`` (``--paginate --slurp``), authenticated as
whoever ``gh`` is logged in as. Every call is a read.

Standard library only, Python 3.8 and later.

Traces to: ETB-SUP8-001 §10, ETB-RISK-016, issue #387.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The pull requests fetched per GraphQL page. Ten keeps a page far below
#: GitHub's node limit with 100 threads of 100 comments each.
PR_PAGE = 10

PULL_REQUEST_QUERY = """
query($owner: String!, $name: String!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: %d, after: $endCursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state url createdAt closedAt mergedAt
        author { login }
        baseRefName headRefName headRefOid
        mergedBy { login }
        mergeCommit { oid }
        body
        reviews(first: 100) {
          pageInfo { hasNextPage }
          nodes { author { login } state submittedAt body commit { oid } }
        }
        reviewThreads(first: 100) {
          pageInfo { hasNextPage }
          nodes {
            isResolved isOutdated path line
            comments(first: 100) {
              pageInfo { hasNextPage }
              nodes { author { login } createdAt body url }
            }
          }
        }
        commits(last: 1) {
          nodes {
            commit {
              oid
              statusCheckRollup {
                state
                contexts(first: 100) {
                  pageInfo { hasNextPage }
                  nodes {
                    __typename
                    ... on CheckRun { name status conclusion completedAt detailsUrl }
                    ... on StatusContext { context state createdAt targetUrl }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
""" % PR_PAGE


class ExportError(Exception):
    """The export cannot be made, or would be incomplete."""


def gh(args, run=subprocess.run):
    """Run ``gh`` with ``args`` and return its standard output as text."""
    done = run(["gh"] + list(args), capture_output=True, check=False)
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", errors="replace").strip()
        raise ExportError("gh %s failed: %s" % (" ".join(args[:2]), message))
    return done.stdout.decode("utf-8")


def rest_list(endpoint, run=subprocess.run):
    """Every item of a paged REST list, as one list."""
    pages = json.loads(gh(["api", "--paginate", "--slurp", endpoint], run))
    items = []
    for page in pages:
        if not isinstance(page, list):
            raise ExportError("%s: a page is not a list" % endpoint)
        items.extend(page)
    return items


def _check_complete(pr):
    """Raise if GitHub says a nested list of ``pr`` has more pages."""
    nested = [("reviews", pr["reviews"]), ("review threads", pr["reviewThreads"])]
    nested += [("comments of a review thread", thread["comments"])
               for thread in pr["reviewThreads"]["nodes"]]
    for commit in pr["commits"]["nodes"]:
        rollup = commit["commit"].get("statusCheckRollup")
        if rollup:
            nested.append(("check contexts", rollup["contexts"]))
    for what, connection in nested:
        if connection["pageInfo"]["hasNextPage"]:
            raise ExportError(
                "pull request #%d has more %s than one page holds; "
                "the export would be incomplete" % (pr["number"], what))


def pull_requests(repo, run=subprocess.run):
    """Every pull request with its reviews, threads and checks."""
    owner, name = repo.split("/", 1)
    pages = json.loads(gh(["api", "graphql", "--paginate", "--slurp",
                           "-f", "query=" + PULL_REQUEST_QUERY,
                           "-f", "owner=" + owner, "-f", "name=" + name], run))
    prs = []
    for page in pages:
        if page.get("errors"):
            raise ExportError("GraphQL: %s" % page["errors"])
        prs.extend(page["data"]["repository"]["pullRequests"]["nodes"])
    for pr in prs:
        _check_complete(pr)
    return prs


def _inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _write(path, data):
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(out_dir, repo, ref=None, run=subprocess.run, now=None):
    """Write the records of ``repo`` into ``out_dir``; return the manifest."""
    out_dir = Path(out_dir)
    if _inside(out_dir, ROOT):
        raise ExportError("%s is inside the repository; the export is kept "
                          "outside it (ETB-SUP8-001 §10)" % out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ExportError("%s is not empty" % out_dir)
    when = (now or datetime.datetime.now(datetime.timezone.utc)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    records = {
        "issues.json": rest_list("repos/%s/issues?state=all&per_page=100" % repo, run),
        "issue_comments.json": rest_list("repos/%s/issues/comments?per_page=100" % repo, run),
        "pull_requests.json": pull_requests(repo, run),
    }
    commit = None
    if ref:
        commit = json.loads(gh(["api", "repos/%s/commits/%s" % (repo, ref)], run))["sha"]
    version = gh(["--version"], run).splitlines()[0].strip()

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, data in records.items():
        files[name] = {"records": len(data), "sha256": _write(out_dir / name, data)}
    manifest = {
        "repository": repo,
        "exported_at": when,
        "ref": ref,
        "commit": commit,
        "gh": version,
        "files": files,
    }
    files_hash = _write(out_dir / "manifest.json", manifest)
    sums = dict((name, entry["sha256"]) for name, entry in files.items())
    sums["manifest.json"] = files_hash
    (out_dir / "SHA256SUMS").write_text(
        "".join("%s  %s\n" % (digest, name) for name, digest in sorted(sums.items())),
        encoding="utf-8", newline="\n")
    return manifest


def default_repo(run=subprocess.run):
    """The repository ``gh`` resolves for this checkout."""
    return gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
              run).strip()


def main(argv=None):
    """Command line entry point; returns the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", type=Path, help="empty directory outside the repository")
    parser.add_argument("--repo", help="OWNER/NAME (default: this checkout's GitHub repository)")
    parser.add_argument("--ref", help="release tag or commit the export goes with")
    args = parser.parse_args(argv)
    try:
        repo = args.repo or default_repo()
        manifest = export(args.out_dir, repo, args.ref)
    except ExportError as error:
        print("export_github_records: %s" % error, file=sys.stderr)
        return 1
    for name, entry in sorted(manifest["files"].items()):
        print("%-22s %6d records  sha256 %s" % (name, entry["records"], entry["sha256"]))
    print("exported %s at %s to %s" % (manifest["repository"], manifest["exported_at"],
                                       args.out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
