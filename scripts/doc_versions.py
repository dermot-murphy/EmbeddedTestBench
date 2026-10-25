#!/usr/bin/env python3
"""Document versions, derived from each controlled document's revision history.

    python scripts/doc_versions.py check [FILE...]
    python scripts/doc_versions.py number [FILE...]
    python scripts/doc_versions.py list
    python scripts/doc_versions.py install-driver
    python scripts/doc_versions.py merge BASE OURS THEIRS [MARKER_SIZE [PATH]]

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
history is numbered in increasing order with any ``next`` rows last, and
holds no row whose version is neither. ``list`` prints each document's ID,
version and date.

``merge`` is a git merge driver for the documents (``.gitattributes``). It
resolves a conflict only inside a revision history, and only when every line
of it, on all three sides, is a history row: theirs' rows first, then the rows
ours added, each change kept once with its number if either side numbered it,
and ``next`` rows after the numbered ones. That covers two branches appending
a row at one place, merging ``develop`` into a branch, and the back-merge
after a release, where ``main`` numbered rows that ``develop`` holds as
``next``. Any other conflict is left for a person, with markers. If the driver
fails, it falls back to git's own merge of the file. It is switched on once
per clone with ``install-driver``, which writes the ``git config`` for it;
the command it writes also falls back to git's own merge when this script or
its interpreter cannot run.

The wiki expands the links with ``expand`` (``scripts/publish_docs.py``).

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
_SEPARATOR = re.compile(r"^\|[-:| ]+\| *$")
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


def _history_lines(text):
    """The body rows of the history table, as (line index, line).

    The table's header row and separator are left out.
    """
    heading = history_heading(text)
    if heading is None:
        return []
    lines = text.split("\n")
    start = text.count("\n", 0, heading.start()) + 1
    body = []
    header_seen = False
    for index in range(start, len(lines)):
        line = lines[index]
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            continue
        if not header_seen:
            header_seen = True
        elif not _SEPARATOR.match(line):
            body.append((index, line))
    return body


def history(text):
    """The history rows as a list of (line index, version, date)."""
    rows = []
    for index, line in _history_lines(text):
        match = _ROW.match(line)
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
    if history_heading(text) is None:
        return ["no Revision History heading"]
    return _cell_problems(text, held_back) + _row_problems(text)


def _cell_problems(text, held_back):
    """What is wrong with the identification table's Version and Date cells."""
    found = []
    wanted = latest_link(text)
    last = current(text)
    for name, literal in (("Version", 0), ("Date", 1)):
        match = _cell(text, name)
        if match is None:
            found.append("no **%s** cell in the identification table" % name)
        elif held_back and last and match.group(2) == last[literal]:
            continue
        elif match.group(2) != wanted:
            hint = (" (a held-back document gives up its literal values when it is"
                    " next revised; ETB-SUP8-001 §6.2)" if held_back else "")
            found.append("**%s** is %r, not %r%s" % (name, match.group(2), wanted, hint))
    return found


def _row_problems(text):
    """What is wrong with the revision history's rows."""
    found = []
    for index, line in _history_lines(text):
        if not _ROW.match(line):
            found.append("line %d: history row whose version is neither major.minor nor %s"
                         % (index + 1, NEXT))
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
        if not is_controlled(text) or current(text) is None:
            print("%s: not a controlled document with a revision history; skipped" % rel)
            continue
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
            print("%s: section 5.3 versions updated" % SVD)
    return 0


def _is_next(row):
    match = _ROW.match(row)
    return match is not None and match.group(1) == NEXT


def _change(row):
    """A history row without its version: the change it records."""
    return "|".join(row.rstrip("\r").split("|")[2:]).strip()


def _merged_rows(ours, base, theirs):
    """One history from two sides that each changed its end, as rows.

    Theirs' rows come first, then the rows ours added; a change both sides
    hold is kept once, numbered if either side numbered it. Numbered rows
    then go before ``next`` rows, each group keeping that order.
    """
    rows = list(theirs) + [row for row in ours if row not in base]
    kept = {}
    order = []
    for row in rows:
        change = _change(row)
        if change not in kept:
            order.append(change)
            kept[change] = row
        elif _is_next(kept[change]) and not _is_next(row):
            kept[change] = row
    merged = [kept[change] for change in order]
    return ([row for row in merged if not _is_next(row)]
            + [row for row in merged if _is_next(row)])


def _conflict(lines, start, marker_size):
    """The conflict opening at ``lines[start]``: its three parts, and its end line."""
    block = {"ours": [], "base": [], "theirs": []}
    part = "ours"
    end = start + 1
    while end < len(lines) and not lines[end].startswith(">" * marker_size):
        if lines[end].startswith("|" * marker_size):
            part = "base"
        elif lines[end].startswith("=" * marker_size):
            part = "theirs"
        else:
            block[part].append(lines[end])
        end += 1
    return block, end


def merge_rows(merged, marker_size=7):
    """Resolve the conflicts in ``git merge-file --diff3`` output that are rows.

    Only a conflict inside a revision history, every line of which - ours,
    the common ancestor and theirs - is a history row, is resolved
    (``_merged_rows``). Returns (text, number of conflicts left).
    """
    start_marker = "<" * marker_size
    out = []
    left = 0
    in_history = False
    lines = merged.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith(start_marker):
            if line.startswith("#"):
                in_history = _HISTORY_HEADING.match(line.rstrip("\r")) is not None
            out.append(line)
            index += 1
            continue
        block, end = _conflict(lines, index, marker_size)
        every = block["ours"] + block["base"] + block["theirs"]
        if (in_history and end < len(lines) and block["ours"] and block["theirs"]
                and all(_ROW.match(row) for row in every)):
            out.extend(_merged_rows(block["ours"], block["base"], block["theirs"]))
        else:
            out.extend(lines[index:end + 1])
            left += 1
        index = end + 1
    return "\n".join(out), left


def _merge_file(files, marker_size, label, extra=()):
    """``git merge-file`` on (base, ours, theirs), labelled with the document."""
    base, ours, theirs = files
    return subprocess.run(
        ["git", "merge-file", "--marker-size=%d" % marker_size, *extra,
         "-L", "%s (ours)" % label, "-L", "%s (base)" % label, "-L", "%s (theirs)" % label,
         ours, base, theirs],
        stdout=subprocess.PIPE, check=False)


def run_merge(base, ours, theirs, marker_size=7, label="document"):
    """The merge driver: ``git merge-file``, then the row conflicts resolved.

    ``ours`` is written only once the merge is complete. If anything fails
    before that, git's own merge of the file is written instead, so the
    result is never ours alone; the exit status is then 1, a conflict.
    """
    try:
        result = _merge_file((base, ours, theirs), marker_size, label, ("--diff3", "-p"))
        if result.returncode < 0 or result.returncode > 127:
            raise RuntimeError("git merge-file failed with %d" % result.returncode)
        merged = result.stdout.decode("utf-8")
        left = 0
        if result.returncode:
            merged, left = merge_rows(merged, marker_size)
        Path(ours).write_bytes(merged.encode("utf-8"))
        return 1 if left else 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        sys.stderr.write("doc_versions merge: %s; falling back to git merge-file\n" % error)
        fallback = _merge_file((base, ours, theirs), marker_size, label)
        return 1 if fallback.returncode >= 0 else 2


def driver_command(python=None):
    """The ``merge.etb-history.driver`` command for ``install-driver``.

    This script exits 0 or 1 only. Any other status - no interpreter, no
    script in an older checkout, a bad argument - means it did not run, and
    the command then lets git merge the file as usual.
    """
    python = Path(python or sys.executable).as_posix()
    return ('"%s" scripts/doc_versions.py merge %%O %%A %%B %%L "%%P"; status=$?; '
            'if [ $status -le 1 ]; then exit $status; fi; '
            'git merge-file --marker-size=%%L %%A %%O %%B' % python)


def run_install(root):
    """``install-driver``: write the merge driver's ``git config`` in this clone."""
    for key, value in (("merge.etb-history.name", "Embedded Test Bench revision history rows"),
                       ("merge.etb-history.driver", driver_command())):
        subprocess.run(["git", "config", key, value], cwd=str(root), check=True)
    print("merge.etb-history.driver = %s" % driver_command())
    return 0


def main(argv=None):
    """The command line; returns the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "number"):
        command = sub.add_parser(name)
        command.add_argument("files", nargs="*", help="documents (default: all controlled)")
    sub.add_parser("list")
    sub.add_parser("install-driver")
    merge = sub.add_parser("merge")
    merge.add_argument("base")
    merge.add_argument("ours")
    merge.add_argument("theirs")
    merge.add_argument("marker_size", nargs="?", type=int, default=7)
    merge.add_argument("path", nargs="?", default="document")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if args.command == "merge":
        return run_merge(args.base, args.ours, args.theirs, args.marker_size, args.path)
    if args.command == "install-driver":
        return run_install(ROOT)
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
