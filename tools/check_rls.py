"""Static half of the RLS baseline check: every created table must enable RLS.

SETUP-PLATFORM.md §7 asks for a CI check that fails the build if a public-schema
table has RLS disabled. That check needs a database connection, and test.yml must
never have one in scope (C-S.7, SECURITY.md §S2). So it is split in two:

  * this script reads the migration SQL and enforces the rule at authoring time,
    which is when the fix is cheap and needs no credentials;
  * the live counterpart runs inside monitor.yml, which does hold SUPABASE_DB_URL,
    and asserts the same property against pg_tables / pg_policies.

A table may legitimately have RLS enabled and zero policies — that is default-deny,
and SETUP-PLATFORM.md §7 expects it for tables nothing outside the pipeline reads.
Policy presence is therefore the live check's business, not this one's.

Usage:
    python tools/check_rls.py [--dir supabase/migrations]
"""

import argparse
import pathlib
import re
import sys

CREATE_TABLE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?   # optional guard
        (?:(?P<schema>"?[\w]+"?)\s*\.\s*)?           # optional schema qualifier
        (?P<name>"?[\w]+"?)""",
    re.IGNORECASE | re.VERBOSE,
)

ENABLE_RLS = re.compile(
    r"""ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?
        (?:(?:"?[\w]+"?)\s*\.\s*)?
        (?P<name>"?[\w]+"?)
        \s+ENABLE\s+ROW\s+LEVEL\s+SECURITY""",
    re.IGNORECASE | re.VERBOSE,
)


def unquote(name: str) -> str:
    return name.strip().strip('"').lower()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="supabase/migrations")
    args = parser.parse_args()

    root = pathlib.Path(args.dir)
    if not root.is_dir():
        print(f"check_rls: no migration directory at {root} — nothing to check yet.")
        return 0

    files = sorted(root.glob("*.sql"))
    if not files:
        print(f"check_rls: no .sql files under {root} — nothing to check yet.")
        return 0

    sql = "\n".join(path.read_text(encoding="utf-8") for path in files)

    created: dict[str, str] = {}
    for match in CREATE_TABLE.finditer(sql):
        schema = unquote(match.group("schema") or "public")
        if schema != "public":
            continue
        created[unquote(match.group("name"))] = match.group(0).strip()

    protected = {unquote(m.group("name")) for m in ENABLE_RLS.finditer(sql)}
    unprotected = sorted(created.keys() - protected)

    if unprotected:
        print(
            f"BLOCKED: {len(unprotected)} public table(s) created without "
            f"ENABLE ROW LEVEL SECURITY:"
        )
        for name in unprotected:
            print(f"  - {name}")
        print(
            "\nAdd 'ALTER TABLE <name> ENABLE ROW LEVEL SECURITY;' in the same migration "
            "that creates the table. No policies means deny-all, which is the intended "
            "default (SETUP-PLATFORM.md §7)."
        )
        return 1

    print(
        f"check_rls: OK — {len(created)} public table(s) across {len(files)} migration(s), "
        "all with RLS enabled."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
