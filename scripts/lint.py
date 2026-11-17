#!/usr/bin/env python3
"""Run pylint over this project and fail on any finding.

    python scripts/lint.py

Until #379 this compared the findings with a recorded baseline and failed only
on findings beyond it. #379 cleared the baseline, so there is none: every
finding fails the check. A rule the project has decided against is disabled in
pyproject.toml with its reason; a finding the code cannot avoid is disabled
inline, on that def or class, with its reason in the same comment.

Each finding is printed as a GitHub Actions annotation, with the path written
with forward slashes whatever the platform (#81).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parent.parent

# What is linted, and the rules that do not apply to it.
#
# The test suite is held to the package's rules with four exceptions, each a
# property of how pytest is written rather than a lapse:
#
#   missing-function-docstring  a test's name is its description, and the
#   missing-class-docstring     suite's names are full sentences
#   redefined-outer-name        how a fixture is passed to a test
#   protected-access            tests reach into internals on purpose; that a
#                               private detail is verified is a feature
TARGETS = (
    ("benchtools", ()),
    ("plugins", ()),
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


def posix_path(path):
    """*path* with forward slashes, whatever separator pylint reported."""
    return PureWindowsPath(path).as_posix()


def report(messages):
    """Print each finding as an annotation. Returns how many there are."""
    for message in sorted(messages, key=lambda m: (posix_path(m["path"]), m["line"])):
        print("::error file=%s,line=%d,title=%s::%s"
              % (posix_path(message["path"]), message["line"],
                 message["symbol"], message["message"]))
    return len(messages)


def main():
    """Lint the project; return 1 if pylint reported anything, else 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    found = report(collect())
    print("pylint: %d finding(s)" % found)
    if found:
        print("::error::%d pylint finding(s); the project allows none" % found)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
