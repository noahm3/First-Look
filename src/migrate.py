"""Forward-only migration runner.

SETUP-PLATFORM.md §6 asks for three things and this provides exactly them:
migrations live in the repo, they are applied by CI rather than by hand in the SQL
editor, and seeding is a separate concern. What it deliberately does not provide is
schema generation — the migrations here are hand-authored SQL, which is why the
Supabase CLI's `db diff` bought nothing and this runs on psycopg, already a
dependency, instead of adding a second toolchain to a workflow that holds secrets
(SECURITY.md §S5).

Each file applies inside its own transaction together with the row recording it, so
a migration either lands completely and is marked applied, or does neither. There is
no `down`: SPEC.md §6 accepts that "delete the file and re-seed" stopped being
available when state moved to Postgres, and a half-applied rollback during an
unattended window is worse than a forward fix.

Usage:
    python -m src.migrate [--dir supabase/migrations] [--dry-run]
"""

import argparse
import logging
import pathlib
import sys

from src.db import Database, DatabaseUnavailable

log = logging.getLogger(__name__)

DEFAULT_MIGRATIONS_DIR = pathlib.Path("supabase/migrations")

# RLS is enabled here for the same reason as every other table: tools/check_rls.py
# only sees CREATE TABLE inside migration files, so a table created from Python
# would otherwise be the one gap the static guard cannot see. No policies, so it is
# deny-all, and src.db.DENY_ALL_TABLES lists it for the live check.
_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT PRIMARY KEY,
  applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;
"""


def discover(directory: pathlib.Path) -> list[pathlib.Path]:
    """Migration files in lexical order, which the timestamp prefix makes chronological."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.sql"))


def applied_versions(db: Database) -> set[str]:
    return {row[0] for row in db.fetch_all("SELECT version FROM schema_migrations")}


def pending(db: Database, directory: pathlib.Path) -> list[pathlib.Path]:
    done = applied_versions(db)
    return [path for path in discover(directory) if path.name not in done]


def apply_one(db: Database, path: pathlib.Path) -> None:
    """Apply one migration and record it, in a single transaction."""
    sql = path.read_text(encoding="utf-8")
    try:
        db.execute(sql)
        db.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailable(
            f"migration {path.name} failed: {type(exc).__name__}: {exc}"
        ) from None


def migrate(db: Database, directory: pathlib.Path, *, dry_run: bool = False) -> list[str]:
    """Apply every pending migration. Returns the versions applied, in order."""
    db.execute(_BOOTSTRAP)
    db.commit()

    outstanding = pending(db, directory)
    if not outstanding:
        log.info("no pending migrations in %s", directory)
        return []

    if dry_run:
        for path in outstanding:
            log.info("would apply %s", path.name)
        return [path.name for path in outstanding]

    applied: list[str] = []
    for path in outstanding:
        log.info("applying %s", path.name)
        apply_one(db, path)
        applied.append(path.name)
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply pending database migrations.")
    parser.add_argument("--dir", default=str(DEFAULT_MIGRATIONS_DIR))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be applied without touching the schema",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        db = Database.from_env()
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    try:
        with db:
            # Redacted: the DSN carries a password and Actions logs are public (§15).
            log.info("connected to %s", db.redacted_dsn)
            applied = migrate(db, pathlib.Path(args.dir), dry_run=args.dry_run)
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    verb = "would apply" if args.dry_run else "applied"
    if applied:
        print(f"migrate: {verb} {len(applied)} migration(s): {', '.join(applied)}")
    else:
        print("migrate: schema is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
