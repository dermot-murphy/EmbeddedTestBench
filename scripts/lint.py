#!/usr/bin/env python3
"""Run pylint over this project and compare the findings with a baseline.

pylint has no baseline of its own, so this does what CStyleCheck does for the
firmware's C: it records the findings that were present when the check was
introduced, and fails only on findings beyond them. The baseline is debt, not
absolution - ETB-ANA-001 lists what is in it.

    python scripts/lint.py                  check against the baseline
    python scripts/lint.py --write-baseline regenerate it
    python scripts/lint.py --strict         ignore the baseline entirely

Findings are counted per (file, message symbol) rather than per line, so
editing a file above a finding does not report it as new.
"""

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".pylint-baseline.json"

# What is linted, and the rules that do not apply to it.
#
# The test suite is held to the package's rules with five exceptions, each a
# property of how pytest is written rather than a lapse:
#
#   missing-function-docstring  a test's name is its description, and the
#   missing-class-docstring     suite's names are full sentences
#   redefined-outer-name        how a fixture is passed to a test
#   protected-access            tests reach into internals on purpose; that a
#                               private detail is verified is a feature
TARGETS = (
    ("benchtools", ()),
    ("scripts", ()),
    (
        "tests",
        (
            "missing-function-docstring",
            "missing-class-docstring",
            "redefined-outer-name",
            "protected-access",
        ),
    ),
)


def run_pylint(target, disabled):
    """Lint one target, returning pylint's messages as a list of dicts."""
    argv = [sys.executable, "-m", "pylint", target, "--output-format=json2"]
    if disabled:
        argv.append("--disable=" + ",".join(disabled))
    completed = subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if not completed.stdout.strip():
        sys.stderr.write(completed.stderr)
        raise SystemExit("pylint produced no output for %s" % target)
    return json.loads(completed.stdout)["messages"]


def collect():
    """Lint every target and return the merged messages."""
    messages = []
    for target, disabled in TARGETS:
        if (ROOT / target).exists():
            messages.extend(run_pylint(target, disabled))
    return messages


def key_of(message):
    """The identity a finding is recorded under: its file and its rule.

    Deliberately not the line number, so that editing a file above a finding
    does not report it as new.

    This works because every rule pylint reports here is a property of one
    file. `duplicate-code` was not - it is about two modules at once, names an
    arbitrary third file as its location, and reports different pairs
    depending on the order files are walked in. It is disabled in
    pyproject.toml for that reason rather than keyed around.

    The path is written with forward slashes whatever the platform. pylint
    reports the host's separator, and the baseline records forward slashes,
    so on Windows every baselined finding used to count as new (#81).
    """
    return (posix_path(message["path"]), message["symbol"])


def posix_path(path):
    """*path* with forward slashes, as the baseline records it."""
    return PureWindowsPath(path).as_posix()


def tally(messages):
    """Count messages per key - see key_of."""
    counts = collections.Counter()
    for message in messages:
        counts[key_of(message)] += 1
    return counts


def load_baseline():
    """Read the recorded baseline, or an empty one if there is none."""
    if not BASELINE.exists():
        return collections.Counter()
    recorded = json.loads(BASELINE.read_text())
    return collections.Counter(
        {(posix_path(entry["path"]), entry["symbol"]): entry["count"]
         for entry in recorded["findings"]}
    )


def write_baseline(counts, messages):
    """Record the current findings as the baseline."""
    findings = [
        {"path": path, "symbol": symbol, "count": count}
        for (path, symbol), count in sorted(counts.items())
    ]
    BASELINE.write_text(json.dumps(
        {
            "comment": "Findings present when the pylint check was introduced. "
                       "The job fails on findings beyond these. Regenerate with "
                       "scripts/lint.py --write-baseline, and say why in the "
                       "commit that does it.",
            "total": len(messages),
            "findings": findings,
        },
        indent=2,
    ) + "\n")
    print("Baseline written: %d findings across %d file/rule pairs"
          % (len(messages), len(findings)))


def report_new(counts, baseline, messages):
    """Print the findings beyond the baseline. Returns how many there are."""
    new = 0
    for key, count in sorted(counts.items()):
        allowed = baseline.get(key, 0)
        if count <= allowed:
            continue
        path, symbol = key
        for message in messages:
            if key_of(message) == key:
                print("::error file=%s,line=%d,title=%s::%s"
                      % (path, message["line"], symbol, message["message"]))
        new += count - allowed
    return new


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-baseline", action="store_true",
                        help="record the current findings as the baseline")
    parser.add_argument("--strict", action="store_true",
                        help="fail on every finding, ignoring the baseline")
    args = parser.parse_args()

    messages = collect()
    counts = tally(messages)

    if args.write_baseline:
        write_baseline(counts, messages)
        return 0

    baseline = collections.Counter() if args.strict else load_baseline()
    new = report_new(counts, baseline, messages)
    baselined = sum(baseline.values())

    print("pylint: %d finding(s) total, %d baselined, %d new"
          % (len(messages), min(baselined, len(messages)), new))
    if new:
        print("::error::%d pylint finding(s) beyond the baseline" % new)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
