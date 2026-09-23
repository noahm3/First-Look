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
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg

from src.models import (
    Company,
    CompDataQuality,
    CompPeriod,
    CompTier,
    LocationClass,
    Posting,
)

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


# Everything between "://" and the last "@" of the authority is credentials.
# Used as the fallback when the DSN will not parse — which is exactly the case
# where a diagnostic is most needed and a structured parse is least available.
_USERINFO = re.compile(r"(?<=://)[^/@]*@")

# Supabase's Connect modal shows the URI with a literal placeholder in place of
# the password. Pasting it unchanged produces a string that will not parse (the
# brackets read as an IPv6 literal) and obviously will not connect.
_PLACEHOLDER = re.compile(r"\[[^\]]*\]")


def redact_dsn(dsn: str) -> str:
    """Return a DSN safe to log — credentials removed, host kept.

    Never returns a bare "<unparseable dsn>": when the structured parse fails,
    the host is the one thing worth knowing, so the fallback strips credentials
    textually rather than giving up. A diagnostic that withholds the host is no
    better than no diagnostic (the same reasoning SPEC.md §8.4 applies to fetch
    guards that drop silently).
    """
    if not dsn:
        return "<empty dsn>"
    try:
        parts = urlsplit(dsn)
        if parts.hostname:
            userinfo = f"{parts.username}:***@" if parts.username else ""
            port = f":{parts.port}" if parts.port else ""
            netloc = f"{userinfo}{parts.hostname}{port}"
            return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
    except ValueError:
        pass

    # Fallback: strip credentials and any query string by hand.
    stripped = _USERINFO.sub("***@", dsn.split("?", 1)[0])
    return f"{stripped} (unparseable)"


def describe_dsn_problem(dsn: str) -> str | None:
    """Explain why a DSN is malformed, or None if it looks usable.

    This exists because the failure it catches is genuinely hard to read from
    psycopg's own error: a connection string that was never valid reports the
    same OperationalError as a wrong password or an unreachable host. Naming the
    real problem here saves the 3am version of this debugging session.

    Never includes the DSN or any part of it in the message.
    """
    if not dsn.strip():
        return "the connection string is empty"

    if dsn != dsn.strip():
        return "the connection string has leading or trailing whitespace"

    scheme = dsn.split("://", 1)[0].lower() if "://" in dsn else ""
    if scheme not in ("postgres", "postgresql"):
        return (
            "the connection string does not start with postgresql:// — "
            "make sure the URI format is selected, not psql or a JDBC string"
        )

    authority = dsn.split("://", 1)[1].split("/", 1)[0]
    if _PLACEHOLDER.search(authority):
        return (
            "the password placeholder was never replaced — Supabase shows the URI "
            "with a bracketed placeholder where your database password goes. "
            "Substitute the real password (percent-encoding any of @ : / ? # [ ] "
            "it contains) and set the secret again"
        )

    try:
        parts = urlsplit(dsn)
    except ValueError:
        return (
            "the connection string will not parse as a URI. A password containing "
            "@ : / ? # [ or ] must be percent-encoded"
        )

    if not parts.hostname:
        return "the connection string has no host"
    if not parts.password:
        return "the connection string carries no password"
    return None


def redact_secrets(text: str, dsn: str) -> str:
    """Strip anything credential-shaped out of third-party error text.

    psycopg's messages can echo the connection string back. Actions logs are
    world-readable on a public repo (SPEC.md §15), and GitHub only masks the
    exact registered secret value — a substring of it, such as the password on
    its own, is a different string and will not be masked (the same trap
    SECURITY.md §S3 describes for NOTIFY_PROFILES).
    """
    cleaned = _USERINFO.sub("***@", text)
    try:
        password = urlsplit(dsn).password
    except ValueError:
        password = None
    if password:
        cleaned = cleaned.replace(password, "***")
    return cleaned


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
        # A malformed connection string reports the same OperationalError as a
        # wrong password or an unreachable host. Say which it is before trying.
        problem = describe_dsn_problem(self._dsn)
        if problem is not None:
            raise DatabaseUnavailable(f"{DEFAULT_DSN_ENV_VAR} is malformed: {problem}")

        try:
            self._conn = self._connect_fn(self._dsn, autocommit=False)
        except Exception as exc:
            # psycopg's own text can echo the connection string, so it goes
            # through redact_secrets before anything reaches a log.
            detail = redact_secrets(str(exc), self._dsn).strip() or type(exc).__name__
            raise DatabaseUnavailable(
                f"could not connect to {redact_dsn(self._dsn)}: {type(exc).__name__}: {detail}"
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
        ok: bool,
    ) -> None:
        """Close a run row. Counts only — this signature never sees an object.

        SECURITY.md §S3 makes that an interface decision rather than a discipline:
        a function that cannot accept a profile cannot print an address into a
        world-readable log.

        `ok` is this run's own verdict — whether its anomaly check passed —
        recorded once at close time. Found necessary by live testing: without
        it, `last_successful_run_at()` cannot tell a clean run apart from one
        that finished but tripped an anomaly, which a C-0.6 forced-failure test
        exposed directly (its row closed normally, so the next run's export
        reported it as the "last successful" run).
        """
        self.execute(
            """
            UPDATE runs
               SET finished_at = now(),
                   companies_polled = %s,
                   http_ok = %s,
                   http_err = %s,
                   total_live_postings = %s,
                   new_postings = %s,
                   ok = %s
             WHERE id = %s
            """,
            (companies_polled, http_ok, http_err, total_live_postings, new_postings, ok, run_id),
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
        """Powers the dashboard's green marker and its stale banner (§12.1).

        Filters on `ok = true` deliberately — a run that finished but tripped
        an anomaly must not read as "successful" here, or the stale banner's
        "last run failed" half (§12.1) can never fire.
        """
        row = self.fetch_one(
            "SELECT finished_at FROM runs WHERE finished_at IS NOT NULL AND ok "
            "ORDER BY finished_at DESC LIMIT 1"
        )
        return row[0] if row else None

    # -- the dashboard export (SPEC.md §12.8) ------------------------------

    def open_postings_for_export(self) -> list[tuple[Posting, Company]]:
        """Open postings with their company and every compensation tier.

        Only `closed_at IS NULL`, and only the columns the cards use (§12.8).
        Tiers come along in full because §11's filter predicate asks whether any
        *single* tier satisfies all conditions — collapsing them here would make
        C-5.2 unanswerable in the browser.

        Returns an empty list when there are no postings, which at M0 is the
        expected and correct answer rather than a stub.
        """
        rows = self.fetch_all(
            """
            SELECT p.id, p.company_id, p.ats_job_id, p.title_raw, p.department_raw,
                   p.location_raw, p.workplace_type_raw, p.location_class, p.city_raw,
                   p.url, p.first_seen_at, p.last_seen_at, p.posted_at, p.is_repost,
                   p.comp_data_quality, p.comp_raw_summary, p.comp_best_annual_usd,
                   p.comp_floor_annual_usd, p.comp_tier_count,
                   c.name, c.canonical_domain, c.is_climate, c.industry_tags
              FROM postings p
              JOIN companies c ON c.id = p.company_id
             WHERE p.closed_at IS NULL
             ORDER BY p.first_seen_at DESC
            """
        )
        if not rows:
            return []

        tiers = self._comp_tiers_by_posting([r[0] for r in rows])
        return [(self._posting_from_row(r, tiers), self._company_from_row(r)) for r in rows]

    def _comp_tiers_by_posting(self, posting_ids: Sequence[int]) -> dict[int, list[CompTier]]:
        rows = self.fetch_all(
            """
            SELECT posting_id, tier_label, min_amount, max_amount, currency, period,
                   observed_at, id
              FROM posting_comp_tiers
             WHERE posting_id = ANY(%s)
             ORDER BY posting_id, id
            """,
            (list(posting_ids),),
        )
        grouped: dict[int, list[CompTier]] = {}
        for posting_id, label, low, high, currency, period, observed_at, tier_id in rows:
            grouped.setdefault(posting_id, []).append(
                CompTier(
                    tier_label=label,
                    min_amount=low,
                    max_amount=high,
                    currency=currency,
                    period=CompPeriod(period) if period else None,
                    observed_at=observed_at,
                    id=tier_id,
                    posting_id=posting_id,
                )
            )
        return grouped

    @staticmethod
    def _company_from_row(row: tuple) -> Company:
        tags = row[22] or []
        return Company(
            name=row[19],
            canonical_domain=row[20],
            id=row[1],
            is_climate=bool(row[21]),
            industry_tags=tuple(tags),
        )

    @staticmethod
    def _posting_from_row(row: tuple, tiers: dict[int, list[CompTier]]) -> Posting:
        return Posting(
            id=row[0],
            company_id=row[1],
            ats_job_id=row[2],
            title_raw=row[3],
            department_raw=row[4],
            location_raw=row[5],
            workplace_type_raw=row[6],
            location_class=LocationClass(row[7]) if row[7] else LocationClass.UNKNOWN,
            city_raw=row[8],
            url=row[9],
            first_seen_at=row[10],
            last_seen_at=row[11],
            posted_at=row[12],
            is_repost=bool(row[13]),
            comp_data_quality=(CompDataQuality(row[14]) if row[14] else CompDataQuality.NONE),
            comp_raw_summary=row[15],
            comp_best_annual_usd=row[16],
            comp_floor_annual_usd=row[17],
            comp_tier_count=row[18] or 0,
            tiers=tuple(tiers.get(row[0], ())),
        )

    # -- companies (SPEC.md §7.1, watchlist ingest -- BUILD.md M1) ----------

    def ingest_manual_company(
        self, *, name: str, canonical_domain: str | None, source_id: str
    ) -> tuple[int, bool]:
        """Idempotently attach one `manual`-source company. Returns (company_id, created).

        Looked up first by `company_sources.source_id` under the `manual` source,
        because `canonical_domain` can't serve as the identity key for a company
        with none (C-1.8) -- NULL never equals NULL under a UNIQUE constraint, so
        re-running the ingest against a no-domain entry would otherwise insert a
        fresh row every time (violating C-1.6). When a domain *is* present, a
        second lookup by `canonical_domain` attaches to a company already known
        via another source rather than creating a duplicate row for it.
        """
        row = self.fetch_one(
            "SELECT company_id FROM company_sources WHERE source = 'manual' AND source_id = %s",
            (source_id,),
        )
        if row:
            return int(row[0]), False

        company_id: int | None = None
        if canonical_domain:
            row = self.fetch_one(
                "SELECT id FROM companies WHERE canonical_domain = %s", (canonical_domain,)
            )
            if row:
                company_id = int(row[0])

        created = company_id is None
        if created:
            row = self.fetch_one(
                "INSERT INTO companies (name, canonical_domain) VALUES (%s, %s) RETURNING id",
                (name, canonical_domain),
            )
            if row is None:
                raise DatabaseUnavailable("could not insert company row")
            company_id = int(row[0])

        self.execute(
            "INSERT INTO company_sources (company_id, source, source_id) "
            "VALUES (%s, 'manual', %s) ON CONFLICT (company_id, source) DO NOTHING",
            (company_id, source_id),
        )
        self.commit()
        return company_id, created

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
