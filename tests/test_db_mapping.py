"""Tests for Database.companies_to_map / record_mapping / pollable_companies.

No real database. A small stateful fake holds a `companies` table as dicts and
interprets exactly the three statements these methods issue, so the tests
exercise "record a weak result, then ask what the polling loop would poll"
end to end -- C-3.2.
"""

from datetime import UTC, datetime

import pytest

from src.db import Database
from src.models import (
    AtsProvider,
    AtsStatus,
    MappingConfidence,
    MappingFailureReason,
    MappingResult,
)

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)
COLUMNS = (
    "id",
    "name",
    "canonical_domain",
    "has_open_roles_signal",
    "ats_provider",
    "ats_token",
    "ats_status",
    "mapping_confidence",
    "mapping_method",
    "mapping_failure_reason",
    "mapping_last_attempt_at",
)


class FakeCompanies:
    """Rows as dicts; `honor_sql_filter=False` simulates a loosened WHERE."""

    def __init__(self, rows, *, honor_sql_filter=True):
        self.rows = {
            r["id"]: {c: r.get(c) for c in COLUMNS}
            | {"ats_status": r.get("ats_status", "unmapped")}
            for r in rows
        }
        self.honor = honor_sql_filter
        self.commits = 0
        self.last_sql = ""
        self._result = []

    # -- psycopg-shaped surface -------------------------------------------
    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        self.last_sql = sql
        self._result = []
        if sql.startswith("UPDATE companies SET ats_provider"):
            provider, token, status, conf, method, reason, at, cid = params
            self.rows[cid].update(
                ats_provider=provider,
                ats_token=token,
                ats_status=status,
                mapping_confidence=conf,
                mapping_method=method,
                mapping_failure_reason=reason,
                mapping_last_attempt_at=at,
            )
        elif "mapping_confidence IN ('verified', 'probable') ORDER BY id" in sql:
            rows = self.rows.values()
            if self.honor:
                rows = [
                    r
                    for r in rows
                    if r["ats_provider"]
                    and r["ats_token"]
                    and r["ats_status"] in ("ok", "unmapped")
                    and r["mapping_confidence"] in ("verified", "probable")
                ]
            self._result = [tuple(r[c] for c in COLUMNS) for r in rows]
        elif "mapping_confidence NOT IN ('verified', 'probable')" in sql:
            rows = [
                r
                for r in self.rows.values()
                if r["mapping_confidence"] not in ("verified", "probable")
            ]
            rows.sort(
                key=lambda r: (
                    not r["has_open_roles_signal"],
                    r["mapping_last_attempt_at"] is not None,
                    r["mapping_last_attempt_at"] or NOW,
                    r["id"],
                )
            )
            if params:
                rows = rows[: params[0]]
            self._result = [tuple(r[c] for c in COLUMNS) for r in rows]
        else:
            raise AssertionError(f"unexpected SQL: {sql}")


def make_db(rows, **kw):
    conn = FakeCompanies(rows, **kw)
    db = Database("postgresql://u:p@h/db", connect_fn=lambda *_a, **_k: conn)
    db.connect()
    return db, conn


def weak_result():
    return MappingResult(
        provider=AtsProvider.LEVER,
        token="acmewidgets",
        confidence=MappingConfidence.WEAK,
        method="slug_guess_uncorroborated",
        failure_reason=MappingFailureReason.WEAK_ONLY.value,
    )


def verified_result():
    return MappingResult(
        provider=AtsProvider.GREENHOUSE,
        token="acmeco",
        confidence=MappingConfidence.VERIFIED,
        method="careers_page",
    )


class TestC32WeakNeverEntersThePollingLoop:
    def test_weak_result_is_recorded_as_a_failure(self):
        db, conn = make_db([{"id": 1, "name": "Acme"}])
        db.record_mapping(1, weak_result(), NOW)
        row = conn.rows[1]
        assert row["mapping_confidence"] == "weak"
        assert row["ats_status"] == AtsStatus.UNMAPPABLE.value
        assert row["mapping_failure_reason"] == "weak_only"
        assert conn.commits == 1

    def test_weak_result_is_not_polled_but_verified_is(self):
        db, _ = make_db([{"id": 1, "name": "Weak Co"}, {"id": 2, "name": "Good Co"}])
        db.record_mapping(1, weak_result(), NOW)
        db.record_mapping(2, verified_result(), NOW)
        assert [c.id for c in db.pollable_companies()] == [2]

    def test_weak_is_excluded_even_if_the_sql_filter_were_loosened(self):
        """Defence in depth: `Company.is_pollable` re-checks every row."""
        db, conn = make_db(
            [
                {
                    "id": 1,
                    "name": "Weak Co",
                    "ats_provider": "lever",
                    "ats_token": "acmewidgets",
                    "ats_status": "unmapped",
                    "mapping_confidence": "weak",
                },
                {
                    "id": 2,
                    "name": "Good Co",
                    "ats_provider": "greenhouse",
                    "ats_token": "acmeco",
                    "ats_status": "ok",
                    "mapping_confidence": "probable",
                },
            ],
            honor_sql_filter=False,
        )
        assert [c.id for c in db.pollable_companies()] == [2]
        assert "mapping_confidence IN ('verified', 'probable')" in conn.last_sql

    def test_a_weak_company_stays_in_the_mapping_queue_for_retry(self):
        db, _ = make_db([{"id": 1, "name": "Weak Co"}])
        db.record_mapping(1, weak_result(), NOW)
        assert [c.id for c in db.companies_to_map()] == [1]


class TestRecordMapping:
    def test_accepted_mapping_clears_any_old_failure_reason(self):
        db, conn = make_db([{"id": 1, "name": "Acme", "mapping_failure_reason": "unknown"}])
        db.record_mapping(1, verified_result(), NOW)
        row = conn.rows[1]
        assert row["ats_status"] == "ok"
        assert row["mapping_failure_reason"] is None
        assert (row["ats_provider"], row["ats_token"]) == ("greenhouse", "acmeco")
        assert row["mapping_last_attempt_at"] == NOW

    def test_c_3_4_a_failure_without_a_reason_is_refused(self):
        db, _ = make_db([{"id": 1, "name": "Acme"}])
        with pytest.raises(ValueError, match="C-3.4"):
            db.record_mapping(1, MappingResult(method="x"), NOW)

    def test_accepted_companies_leave_the_mapping_queue(self):
        db, _ = make_db([{"id": 1, "name": "Acme"}])
        db.record_mapping(1, verified_result(), NOW)
        assert db.companies_to_map() == []


class TestQueueOrder:
    def test_open_roles_first_then_never_attempted_then_oldest(self):
        old = datetime(2026, 1, 1, tzinfo=UTC)
        db, _ = make_db(
            [
                {"id": 1, "name": "a", "mapping_last_attempt_at": NOW},
                {"id": 2, "name": "b", "has_open_roles_signal": True},
                {"id": 3, "name": "c"},
                {"id": 4, "name": "d", "mapping_last_attempt_at": old},
            ]
        )
        assert [c.id for c in db.companies_to_map()] == [2, 3, 4, 1]
        assert [c.id for c in db.companies_to_map(limit=2)] == [2, 3]
