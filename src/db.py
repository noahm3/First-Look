"""Postgres access. Typed helpers, no ORM, foreign keys enforced by the schema.

SPEC.md §6 moved state off a committed SQLite file and into Postgres. The network
dependency that introduces is acceptable for exactly one reason, stated in §6: a
database outage fails the run, which exits non-zero, which emails. That is a *loud*
failure, which is what §3.3 asks for. So :class:`DatabaseUnavailable` exists to be
propagated, never swallowed — it is the one error in this codebase that should stop
a run rather than be recorded and stepped over.

Nothing here logs a connection string. The DSN carries a password, and Actions logs
are world-readable on a public repo (§15); :func:`redact_dsn` exists so that a
diagnostic can name the host without naming the credential.
"""

import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg

log = logging.getLogger(__name__)

DEFAULT_DSN_ENV_VAR = "SUPABASE_DB_URL"

# Tables that are expected to have RLS enabled and no policies at all. That
# combination is deny-all, which is the intended posture for everything the
# pipeline alone touches (SETUP-PLATFORM.md §7). Listing them explicitly means the
# live check can still catch a *new* table that was forgotten.
DENY_ALL_TABLES: frozenset[str] = frozenset(
    {
        "company_sources",
        "posting_hashes",
        "runs",
        "notifications_sent",
        "schema_migrations",
    }
)


class DatabaseUnavailable(RuntimeError):
    """The database could not be reached or a statement failed irrecoverably.

    SPEC.md §14 folds this into the aggregate anomaly rule: a DB outage must exit
    non-zero rather than retry silently forever.
    """


def redact_dsn(dsn: str) -> str:
    """Return a DSN safe to put in a log line — password replaced, host kept."""
    try:
        parts = urlsplit(dsn)
    except ValueError:
        return "<unparseable dsn>"
    if not parts.hostname:
        return "<dsn>"
    userinfo = f"{parts.username}:***@" if parts.username else ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{userinfo}{parts.hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


@dataclass(frozen=True, slots=True)
class RunRow:
    id: int
    started_at: datetime
    finished_at: datetime | None
    companies_polled: int
    http_ok: int
    http_err: int
    total_live_postings: int
    new_postings: int


class Database:
    """A single connection to Postgres, opened explicitly and closed explicitly."""

    def __init__(
        self,
        dsn: str,
        *,
        connect_fn: Callable[..., Any] = psycopg.connect,
    ) -> None:
        if not dsn:
            raise DatabaseUnavailable("no database connection string was supplied")
        self._dsn = dsn
        self._connect_fn = connect_fn
        self._conn: Any = None

    @classmethod
    def from_env(
        cls,
        var: str = DEFAULT_DSN_ENV_VAR,
        *,
        environ: dict[str, str] | None = None,
        connect_fn: Callable[..., Any] = psycopg.connect,
    ) -> "Database":
        source = os.environ if environ is None else environ
        dsn = source.get(var, "")
        if not dsn:
            # Names the variable, never its value.
            raise DatabaseUnavailable(f"{var} is not set")
        return cls(dsn, connect_fn=connect_fn)

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> None:
        if self._conn is not None:
            return
        try:
            self._conn = self._connect_fn(self._dsn, autocommit=False)
        except Exception as exc:
            # The exception text can carry the DSN. Re-raise with a message built
            # from the redacted form only.
            raise DatabaseUnavailable(
                f"could not connect to {redact_dsn(self._dsn)}: {type(exc).__name__}"
            ) from None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def redacted_dsn(self) -> str:
        """The connection target with its password removed, safe to log (§15)."""
        return redact_dsn(self._dsn)

    @property
    def connection(self) -> Any:
        if self._conn is None:
            raise DatabaseUnavailable("connect() has not been called")
        return self._conn

    # -- low-level ---------------------------------------------------------

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        with self.connection.cursor() as cur:
            cur.execute(sql, params)

    def fetch_all(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple]:
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def fetch_one(self, sql: str, params: Sequence[Any] | None = None) -> tuple | None:
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    # -- runs (SPEC.md §14) ------------------------------------------------

    def start_run(self) -> int:
        row = self.fetch_one("INSERT INTO runs (started_at) VALUES (now()) RETURNING id")
        if row is None:
            raise DatabaseUnavailable("could not open a run row")
        self.commit()
        return int(row[0])

    def finish_run(
        self,
        run_id: int,
        *,
        companies_polled: int,
        http_ok: int,
        http_err: int,
        total_live_postings: int,
        new_postings: int,
    ) -> None:
        """Close a run row. Counts only — this signature never sees an object.

        SECURITY.md §S3 makes that an interface decision rather than a discipline:
        a function that cannot accept a profile cannot print an address into a
        world-readable log.
        """
        self.execute(
            """
            UPDATE runs
               SET finished_at = now(),
                   companies_polled = %s,
                   http_ok = %s,
                   http_err = %s,
                   total_live_postings = %s,
                   new_postings = %s
             WHERE id = %s
            """,
            (companies_polled, http_ok, http_err, total_live_postings, new_postings, run_id),
        )
        self.commit()

    def previous_finished_run(self, before_run_id: int) -> RunRow | None:
        """The most recent completed run before this one — the anomaly baseline."""
        row = self.fetch_one(
            """
            SELECT id, started_at, finished_at, companies_polled, http_ok, http_err,
                   total_live_postings, new_postings
              FROM runs
             WHERE finished_at IS NOT NULL AND id < %s
             ORDER BY id DESC
             LIMIT 1
            """,
            (before_run_id,),
        )
        return RunRow(*row) if row else None

    def last_successful_run_at(self) -> datetime | None:
        """Powers the dashboard's green marker and its stale banner (§12.1)."""
        row = self.fetch_one(
            "SELECT finished_at FROM runs WHERE finished_at IS NOT NULL "
            "ORDER BY finished_at DESC LIMIT 1"
        )
        return row[0] if row else None

    # -- schema posture (SETUP-PLATFORM.md §7, live half of the RLS check) ---

    def public_tables(self) -> list[str]:
        rows = self.fetch_all(
            """
            SELECT c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
             ORDER BY c.relname
            """
        )
        return [r[0] for r in rows]

    def tables_without_rls(self) -> list[str]:
        rows = self.fetch_all(
            """
            SELECT c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relkind = 'r'
               AND NOT c.relrowsecurity
             ORDER BY c.relname
            """
        )
        return [r[0] for r in rows]

    def tables_with_rls_but_no_policies(self) -> list[str]:
        """Deny-all tables. Legitimate, but only for ones we chose deliberately."""
        rows = self.fetch_all(
            """
            SELECT c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relkind = 'r'
               AND c.relrowsecurity
               AND NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid)
             ORDER BY c.relname
            """
        )
        return [r[0] for r in rows]

    def rls_violations(self, allowlist: frozenset[str] = DENY_ALL_TABLES) -> list[str]:
        """Tables whose RLS posture is wrong. Empty list means the baseline holds."""
        problems = [f"{name}: RLS is disabled" for name in self.tables_without_rls()]
        problems += [
            f"{name}: RLS enabled with no policies, and not on the deny-all allowlist"
            for name in self.tables_with_rls_but_no_policies()
            if name not in allowlist
        ]
        return problems
