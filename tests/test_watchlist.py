"""Tests for src/watchlist.py and Database.ingest_manual_company.

No real database (tests/conftest.py blocks sockets): a small in-memory fake
stands in for the two tables `ingest_manual_company` touches, so these tests
exercise the real dedupe logic end to end -- including across repeated calls,
which is exactly what C-1.6 asks for -- rather than mocking the method away.
"""

import pathlib

import pytest
import yaml

from src.db import Database
from src.watchlist import (
    IngestSummary,
    WatchlistEntry,
    canonicalize_domain,
    ingest_watchlist,
    load_watchlist,
    slugify,
    source_identity,
)


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self._conn._result = self._conn.router(" ".join(sql.split()), params or ())

    def fetchone(self):
        rows = self._conn._result or []
        return rows[0] if rows else None

    def fetchall(self):
        return list(self._conn._result or [])


class FakeCompaniesDb:
    """An in-memory stand-in for the `companies` + `company_sources` tables."""

    def __init__(self):
        self.companies: dict[int, tuple[str, str | None]] = {}
        self.sources: dict[tuple[int, str], str] = {}
        self._next_id = 1

    def router(self, sql: str, params: tuple):
        if sql.startswith("SELECT company_id FROM company_sources"):
            (source_id,) = params
            for (company_id, source), sid in self.sources.items():
                if source == "manual" and sid == source_id:
                    return [(company_id,)]
            return []
        if sql.startswith("SELECT id FROM companies WHERE canonical_domain"):
            (domain,) = params
            for company_id, (_name, dom) in self.companies.items():
                if dom == domain:
                    return [(company_id,)]
            return []
        if sql.startswith("INSERT INTO companies"):
            name, domain = params
            company_id = self._next_id
            self._next_id += 1
            self.companies[company_id] = (name, domain)
            return [(company_id,)]
        if sql.startswith("INSERT INTO company_sources"):
            company_id, source_id = params
            self.sources.setdefault((company_id, "manual"), source_id)
            return []
        raise AssertionError(f"unexpected SQL in fake router: {sql}")


class FakeConnection:
    def __init__(self, backend: FakeCompaniesDb):
        self._backend = backend
        self.commits = 0
        self._result: list[tuple] | None = None

    def router(self, sql, params):
        return self._backend.router(sql, params)

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def make_db() -> tuple[Database, FakeCompaniesDb]:
    backend = FakeCompaniesDb()
    conn = FakeConnection(backend)
    db = Database("postgresql://user:pw@localhost/db", connect_fn=lambda *_a, **_k: conn)
    db.connect()
    return db, backend


class TestCanonicalizeDomain:
    def test_bare_host_passes_through(self):
        assert canonicalize_domain("x.com") == "x.com"

    def test_full_url_with_path_and_query_collapses_to_the_host(self):
        assert canonicalize_domain("https://www.x.com/careers?utm=1") == "x.com"

    def test_www_is_stripped(self):
        assert canonicalize_domain("www.x.com") == "x.com"

    def test_uppercase_is_lowered(self):
        assert canonicalize_domain("HTTPS://X.COM") == "x.com"

    def test_a_port_is_stripped(self):
        assert canonicalize_domain("x.com:8080") == "x.com"

    def test_none_and_blank_are_none(self):
        assert canonicalize_domain(None) is None
        assert canonicalize_domain("   ") is None


class TestSlugify:
    def test_lowercases_and_hyphenates(self):
        assert slugify("Acme, Inc.") == "acme-inc"

    def test_blank_name_falls_back(self):
        assert slugify("   ") == "unnamed"


class TestLoadWatchlist:
    def test_parses_name_and_domain(self, tmp_path: pathlib.Path):
        path = tmp_path / "watchlist.yml"
        path.write_text(yaml.safe_dump([{"name": "Acme", "domain": "acme.com"}]), encoding="utf-8")
        entries = load_watchlist(path)
        assert entries == [WatchlistEntry(name="Acme", domain="acme.com")]

    def test_a_missing_domain_is_none_not_dropped(self, tmp_path: pathlib.Path):
        path = tmp_path / "watchlist.yml"
        path.write_text(yaml.safe_dump([{"name": "No Domain Co"}]), encoding="utf-8")
        entries = load_watchlist(path)
        assert entries == [WatchlistEntry(name="No Domain Co", domain=None)]

    def test_a_missing_name_is_rejected(self, tmp_path: pathlib.Path):
        path = tmp_path / "watchlist.yml"
        path.write_text(yaml.safe_dump([{"domain": "acme.com"}]), encoding="utf-8")
        with pytest.raises(ValueError):
            load_watchlist(path)

    def test_the_real_committed_watchlist_is_a_small_hand_verified_set(self):
        """A deliberately small, hand-verified ground-truth set (BUILD.md M1) --
        not a fixed count. See config/watchlist.yml's own header for provenance."""
        entries = load_watchlist(pathlib.Path("config/watchlist.yml"))
        assert len(entries) >= 10
        assert all(e.domain for e in entries)


class TestIngestWatchlist:
    def test_c_1_6_ingesting_twice_creates_zero_duplicate_companies(self):
        db, backend = make_db()
        entries = [WatchlistEntry(name="Acme", domain="acme.com")]

        first = ingest_watchlist(db, entries)
        second = ingest_watchlist(db, entries)

        assert first == IngestSummary(created=1, already_present=0, no_domain=0)
        assert second == IngestSummary(created=0, already_present=1, no_domain=0)
        assert len(backend.companies) == 1

    def test_c_1_7_a_url_variant_and_a_bare_host_resolve_to_one_company(self):
        db, backend = make_db()
        entries = [
            WatchlistEntry(name="Acme", domain="https://www.acme.com/careers?utm=1"),
            WatchlistEntry(name="Acme (dup entry)", domain="acme.com"),
        ]

        ingest_watchlist(db, entries)

        assert len(backend.companies) == 1
        (_name, domain) = next(iter(backend.companies.values()))
        assert domain == "acme.com"

    def test_c_1_8_a_company_with_no_resolvable_domain_is_ingested_and_flagged(self):
        db, backend = make_db()
        entries = [WatchlistEntry(name="Stealth Startup", domain=None)]

        summary = ingest_watchlist(db, entries)

        assert summary == IngestSummary(created=1, already_present=0, no_domain=1)
        assert len(backend.companies) == 1
        (name, domain) = next(iter(backend.companies.values()))
        assert name == "Stealth Startup"
        assert domain is None

    def test_c_1_8_re_ingesting_a_no_domain_company_does_not_duplicate_it(self):
        db, _backend = make_db()
        entries = [WatchlistEntry(name="Stealth Startup", domain=None)]

        first = ingest_watchlist(db, entries)
        second = ingest_watchlist(db, entries)

        assert first.created == 1
        assert second.created == 0
        assert second.already_present == 1

    def test_two_different_no_domain_companies_are_not_merged(self):
        db, backend = make_db()
        entries = [
            WatchlistEntry(name="Stealth Startup One", domain=None),
            WatchlistEntry(name="Stealth Startup Two", domain=None),
        ]

        summary = ingest_watchlist(db, entries)

        assert summary.created == 2
        assert len(backend.companies) == 2

    def test_a_company_already_known_via_another_source_is_attached_not_duplicated(self):
        db, backend = make_db()
        # Simulates a company already discovered by some other source (VC portfolio,
        # Getro, etc.) before the watchlist ever ingests it -- same canonical_domain,
        # a different `company_sources` row already present.
        backend.companies[99] = ("Acme (auto-discovered)", "acme.com")
        backend.sources[(99, "vc_portfolio_page")] = "acme.com"

        summary = ingest_watchlist(db, [WatchlistEntry(name="Acme", domain="acme.com")])

        assert summary == IngestSummary(created=0, already_present=1, no_domain=0)
        assert len(backend.companies) == 1
        assert backend.sources[(99, "manual")] == "acme.com"


class TestSourceIdentity:
    def test_domain_present_uses_the_canonical_domain_as_the_identity(self):
        domain, source_id = source_identity(WatchlistEntry(name="Acme", domain="acme.com"))
        assert domain == "acme.com"
        assert source_id == "acme.com"

    def test_no_domain_uses_a_name_derived_identity(self):
        domain, source_id = source_identity(WatchlistEntry(name="Stealth Co", domain=None))
        assert domain is None
        assert source_id == "name:stealth-co"
