"""Fail the build if a criterion identifier disappeared from CRITERIA.md.

CRITERIA.md's own rules say lines are never deleted and never renumbered — a
superseded criterion is struck through with a date and a reason, and new ones are
appended. BUILD.md §0.3 makes that a CI check rather than a review item, on the
grounds that twenty lines of Python enforce it better than a tired person at 11pm.

Striking a criterion is fine: the identifier stays on the page, so this check passes.
Deleting or renumbering one removes the identifier, and this check fails.

Usage:
    python tools/check_criteria.py [--base REV] [--file PATH]
"""

import argparse
import re
import subprocess
import sys

IDENTIFIER = re.compile(r"\bC-(?:S\.\d+|\d+\.\d+)\b")


def identifiers(text: str) -> set[str]:
    return set(IDENTIFIER.findall(text))


def read_at_revision(rev: str, path: str) -> str | None:
    """Return the file's contents at ``rev``, or None if it isn't there."""
    result = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="HEAD~1",
        help="revision to compare against (default: HEAD~1)",
    )
    parser.add_argument(
        "--file",
        default="CRITERIA.md",
        help="working-tree file to check (default: CRITERIA.md)",
    )
    parser.add_argument(
        "--base-file",
        default=None,
        help=(
            "path to read inside --base; defaults to --file. Separate from --file so the "
            "guard can be pointed at a candidate copy and compared against the committed "
            "original — which is how its failure path gets exercised."
        ),
    )
    args = parser.parse_args()

    base_path = args.base_file or args.file

    with open(args.file, encoding="utf-8") as handle:
        current = identifiers(handle.read())

    baseline_text = read_at_revision(args.base, base_path)
    if baseline_text is None:
        print(
            f"check_criteria: no {base_path} at {args.base} — nothing to compare. "
            f"Current file holds {len(current)} identifiers."
        )
        return 0

    baseline = identifiers(baseline_text)
    missing = sorted(baseline - current)

    if missing:
        print(
            f"BLOCKED: {len(missing)} criterion identifier(s) present at {args.base} "
            f"are missing from {args.file}:"
        )
        for name in missing:
            print(f"  - {name}")
        print(
            "\nCRITERIA.md is append-and-strike only. To supersede a criterion, strike it "
            "through with a date and reason and leave the identifier in place."
        )
        return 1

    added = sorted(current - baseline)
    note = f", {len(added)} appended ({', '.join(added)})" if added else ""
    print(f"check_criteria: OK — all {len(baseline)} identifiers preserved{note}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
