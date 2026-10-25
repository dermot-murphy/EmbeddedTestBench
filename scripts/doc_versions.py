#!/usr/bin/env python3
"""Document versions, derived from each controlled document's revision history.

    python scripts/doc_versions.py check [FILE...]
    python scripts/doc_versions.py number [FILE...]
    python scripts/doc_versions.py list
    python scripts/doc_versions.py merge BASE OURS THEIRS

A controlled document's identification table does not hold its Version and
Date. Each cell holds a link to the revision history, for example
``[latest, §2](#2-revision-history)``, and the value is the version and date
of the history's last row (ETB-SUP8-001 §6.2, #210). A change therefore
touches only the history table, so two branches that change one document do
not both edit its identification table.

On a feature branch a new history row is written with the version ``next``.
``number`` runs on the release or hotfix branch: it numbers every ``next``
row, one minor version above the row before it, and brings the version column
of ETB-SVD-001 §5.3 up to date. ``check`` is what the test suite runs: every
controlled document has both links, pointing at its own history, and its
history is numbered in increasing order with any ``next`` rows last.
``list`` prints each document's ID, version and date.

``merge`` is a git merge driver for the documents (``.gitattributes``). Two
branches that each append a row to the same history leave a conflict whose
two sides are only table rows; the driver keeps both, numbered rows first and
``next`` rows after them. Any other conflict is left for a person to resolve.
It is switched on once per clone::

    git config merge.etb-history.name "Embedded Test Bench revision history rows"
    git config merge.etb-history.driver "python scripts/doc_versions.py merge %O %A %B"

The rendered copies - the wiki and the home page - expand the links with
``expand`` (``scripts/publish_docs.py``).

Standard library only, Python 3.8 and later.

Traces to: ETB-SUP8-001 §5.6 and §6.2, issue #210.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVD = "docs/aspice/EmbeddedTestBench_SVD_Software_Version_Description.md"

#: The version written in a history row that is not numbered yet.
NEXT = "next"

#: Documents that still hold literal values, which must equal their last
#: history row. ETB-SVD-001 describes the released baseline and is changed
#: only on a release or hotfix branch (ETB-SUP8-001 §7), so it takes the
#: links when it is next revised; it is then removed from this set.
HELD_BACK = frozenset({SVD})

_HISTORY_HEADING = re.compile(r"^(#+) +((?:(\d+)\. +)?Revision History) *$", re.M)
_ROW = re.compile(r"^\| *(\d+\.\d+|%s) *\| *([^|]*?) *\|" % NEXT)
_TABLE_ROW = re.compile(r"^\|.*\| *$")
_CELL = r"(\| *\*\*%s\*\* *\| *)([^|]*?)( *\|)"
_LATEST = re.compile(r"^\[latest[^\]]*\]\((#[^)\s]+)\)$")
_ID = re.compile(r"\| *\*\*Document ID\*\* *\| *([^|]*?) *\|")


def read_text(path):
    """A file's text with LF line endings."""
    return Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")


def write_text(path, text):
    """Write the text, keeping the line endings the file has in the checkout."""
    path = Path(path)
    if path.exists() and b"\r\n" in path.read_bytes():
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def anchor(heading):
    """The anchor GitHub gives a heading: lower case, punctuation dropped."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return "#" + text.replace(" ", "-")


def is_controlled(text):
    """True for a document with an identification table."""
    return _ID.search(text) is not None


def controlled_documents(root=ROOT):
    """Every controlled document under ``docs/``, as sorted relative paths."""
    found = []
    for path in sorted((Path(root) / "docs").rglob("*.md")):
        if is_controlled(read_text(path)):
            found.append(path.relative_to(root).as_posix())
    return found


def history_heading(text):
    """The revision history heading as a match, or None."""
    return _HISTORY_HEADING.search(text)


def latest_link(text):
    """The Version and Date cell text for this document's history."""
    heading = history_heading(text)
    label = "§" + heading.group(3) if heading.group(3) else "Revision History"
    return "[latest, %s](%s)" % (label, anchor(heading.group(2)))


def history(text):
    """The history rows as a list of (line index, version, date)."""
    heading = history_heading(text)
    if heading is None:
        return []
    lines = text.split("\n")
    start = text.count("\n", 0, heading.start()) + 1
    rows = []
    for index in range(start, len(lines)):
        if lines[index].startswith("#"):
            break
        match = _ROW.match(lines[index])
        if match:
            rows.append((index, match.group(1), match.group(2)))
    return rows


def current(text):
    """The document's (version, date): those of its last history row."""
    rows = history(text)
    if not rows:
        return None
    return rows[-1][1], rows[-1][2]


def _identification(text):
    """The part of the document before its revision history."""
    heading = history_heading(text)
    return text[:heading.start()] if heading else text


def _cell(text, name):
    """The first ``**name**`` cell of the identification table as a match."""
    return re.search(_CELL % re.escape(name), _identification(text))


def expand(text):
    """The text with its Version and Date links replaced by their values."""
    value = current(text)
    if value is None:
        return text
    for name, replacement in (("Version", value[0]), ("Date", value[1])):
        match = _cell(text, name)
        if match and _LATEST.match(match.group(2)):
            text = text[:match.start(2)] + replacement + text[match.end(2):]
    return text


def _version(value):
    major, minor = value.split(".")
    return int(major), int(minor)


def problems(text, held_back=False):
    """What is wrong with a controlled document's versioning, as messages.

    ``held_back`` accepts literal values in place of the links, if they are
    those of the last history row (``HELD_BACK``).
    """
    found = []
    heading = history_heading(text)
    if heading is None:
        return ["no Revision History heading"]
    wanted = latest_link(text)
    last = current(text)
    for name, literal in (("Version", 0), ("Date", 1)):
        match = _cell(text, name)
        if match is None:
            found.append("no **%s** cell in the identification table" % name)
        elif held_back and last and match.group(2) == last[literal]:
            continue
        elif match.group(2) != wanted:
            found.append("**%s** is %r, not %r" % (name, match.group(2), wanted))
    rows = history(text)
    if not rows:
        found.append("the revision history has no rows")
    seen_next = False
    previous = None
    for index, version, _ in rows:
        if version == NEXT:
            seen_next = True
            continue
        if seen_next:
            found.append("line %d: numbered row %s after a %s row" % (index + 1, version, NEXT))
        if previous is not None and _version(version) <= _version(previous):
            found.append("line %d: version %s does not follow %s" % (index + 1, version, previous))
        previous = version
    if rows and rows[0][1] == NEXT:
        found.append("the first history row is %s; nothing to number it from" % NEXT)
    return found


def number(text):
    """The text with every ``next`` history row given its version."""
    lines = text.split("\n")
    previous = None
    for index, version, _ in history(text):
        if version != NEXT:
            previous = version
            continue
        if previous is None:
            raise ValueError("line %d: first history row is %s" % (index + 1, NEXT))
        major, minor = _version(previous)
        previous = "%d.%d" % (major, minor + 1)
        lines[index] = re.sub(r"^\| *%s *\|" % NEXT, "| %s |" % previous, lines[index], count=1)
    return "\n".join(lines)


def svd_table(text, versions):
    """ETB-SVD-001 with the version column of §5.3 set from ``versions``.

    ``versions`` maps a document ID to its version. A row for a document ID
    not in the map is left alone.
    """
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("### 5.3 ")), None)
    if start is None:
        raise ValueError("ETB-SVD-001 has no §5.3")
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("#"):
            break
        cells = line.split("|")
        if len(cells) < 5 or cells[1].strip() not in versions:
            continue
        cells[3] = " %s " % versions[cells[1].strip()]
        lines[index] = "|".join(cells)
    return "\n".join(lines)


def doc_id(text):
    """The document's ID from its identification table, or ""."""
    match = _ID.search(text)
    return match.group(1) if match else ""


def run_check(paths, root):
    """``check``: print each problem; 1 if there was any."""
    failed = False
    for rel in paths:
        for message in problems(read_text(Path(root) / rel), rel in HELD_BACK):
            print("%s: %s" % (rel, message))
            failed = True
    return 1 if failed else 0


def run_number(paths, root):
    """``number``: number the ``next`` rows, then set ETB-SVD-001 §5.3."""
    versions = {}
    for rel in paths:
        path = Path(root) / rel
        text = read_text(path)
        numbered = number(text)
        if numbered != text:
            write_text(path, numbered)
            print("%s: numbered" % rel)
        versions[doc_id(numbered)] = current(numbered)[0]
    svd = Path(root) / SVD
    if svd.exists():
        text = read_text(svd)
        updated = svd_table(text, versions)
        if updated != text:
            write_text(svd, updated)
            print("%s: §5.3 versions updated" % SVD)
    return 0


def _is_next(row):
    match = _ROW.match(row)
    return match is not None and match.group(1) == NEXT


def merge_rows(merged):
    """Resolve the conflicts in ``git merge-file --diff3`` output that are rows.

    A conflict whose common ancestor is empty and whose two sides are only
    table rows is two rows appended at one place. It is replaced by both
    sides' rows, numbered rows first and ``next`` rows after, each in the
    order it had. Returns (text, number of conflicts left).
    """
    out = []
    left = 0
    lines = merged.split("\n")
    index = 0
    while index < len(lines):
        if not lines[index].startswith("<<<<<<<"):
            out.append(lines[index])
            index += 1
            continue
        block = {"ours": [], "base": [], "theirs": []}
        part = "ours"
        end = index + 1
        while end < len(lines) and not lines[end].startswith(">>>>>>>"):
            if lines[end].startswith("|||||||"):
                part = "base"
            elif lines[end].startswith("======="):
                part = "theirs"
            else:
                block[part].append(lines[end])
            end += 1
        rows = block["ours"] + block["theirs"]
        if not block["base"] and rows and all(_TABLE_ROW.match(row.rstrip("\r")) for row in rows):
            out.extend(row for row in rows if not _is_next(row))
            out.extend(row for row in rows if _is_next(row))
        else:
            out.extend(lines[index:end + 1])
            left += 1
        index = end + 1
    return "\n".join(out), left


def run_merge(base, ours, theirs):
    """The merge driver: ``git merge-file``, then the row conflicts resolved."""
    result = subprocess.run(
        ["git", "merge-file", "--diff3", "-p", ours, base, theirs],
        stdout=subprocess.PIPE, check=False)
    if result.returncode < 0 or result.returncode > 127:
        return 2
    merged = result.stdout.decode("utf-8")
    if result.returncode == 0:
        left = 0
    else:
        merged, left = merge_rows(merged)
    Path(ours).write_bytes(merged.encode("utf-8"))
    return 1 if left else 0


def main(argv=None):
    """The command line; returns the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "number"):
        command = sub.add_parser(name)
        command.add_argument("files", nargs="*", help="documents (default: all controlled)")
    sub.add_parser("list")
    merge = sub.add_parser("merge")
    merge.add_argument("base")
    merge.add_argument("ours")
    merge.add_argument("theirs")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if args.command == "merge":
        return run_merge(args.base, args.ours, args.theirs)
    paths = getattr(args, "files", None) or controlled_documents(ROOT)
    if args.command == "check":
        return run_check(paths, ROOT)
    if args.command == "number":
        return run_number(paths, ROOT)
    for rel in paths:
        text = read_text(ROOT / rel)
        version, date = current(text) or ("?", "?")
        print("%-14s %-6s %s  %s" % (doc_id(text), version, date, rel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
