"""Live half of the RLS baseline check — asks the database, not the SQL files.

SETUP-PLATFORM.md §7: "A test that fails the build if any table in the public
schema has RLS disabled, or has RLS enabled with zero policies and is not on an
explicit allow-list."

Split from tools/check_rls.py because that one runs inside test.yml, which must
never hold a credential (C-S.7). This one needs SUPABASE_DB_URL and therefore runs
only from workflows that legitimately carry it: migrate.yml after a real apply, and
monitor.yml at run start.

The two halves catch different things. The static one catches a migration authored
without RLS, before it is ever applied. This one catches a table that reached the
database some other way — a hand-run statement in the SQL editor, a Supabase
feature that creates its own table — which is the failure SETUP-PLATFORM.md §7
actually calls the realistic breach path.

Usage:
    python -m src.check_schema
"""

import logging
import sys

from src.db import DENY_ALL_TABLES, Database, DatabaseUnavailable

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        db = Database.from_env()
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    try:
        with db:
            log.info("checking RLS posture on %s", db.redacted_dsn)
            violations = db.rls_violations()
            table_count = len(db.public_tables())
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    if violations:
        print(f"BLOCKED: {len(violations)} table(s) have the wrong RLS posture:")
        for problem in violations:
            print(f"  - {problem}")
        print(
            "\nEvery public table must have RLS enabled. A table with RLS and no "
            "policies is deny-all, which is fine, but it has to be a deliberate "
            f"choice — add it to DENY_ALL_TABLES in src/db.py. Currently allowed: "
            f"{', '.join(sorted(DENY_ALL_TABLES))}."
        )
        return 1

    print(
        "check_schema: OK — every public table has RLS enabled, and every deny-all "
        f"table is on the allowlist ({table_count} inspected)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
