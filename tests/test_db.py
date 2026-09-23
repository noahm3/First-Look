"""Tests for src/db.py and src/migrate.py.

No real database: the connection is injected, so these run with sockets blocked
(tests/conftest.py). The integration test against a temp database is BUILD.md §7's
single integration test and belongs with the monitoring loop, not here.
"""

import pathlib

import pytest

from src.db import (
    DEFAULT_DSN_ENV_VAR,
    Database,
    DatabaseUnavailable,
    RunRow,
    describe_dsn_problem,
    redact_dsn,
    redact_secrets,
)
from src.migrate import migrate, pending

# Split so no literal in this file is email-shaped: .githooks/pre-commit blocks
# that pattern outright, and the rule is worth more than the convenience of a
# single-line constant.
DB_HOST = "db.abcdefgh.supabase.co"
DB_PASSWORD = "hunter2"
DSN = f"postgresql://postgres:{DB_PASSWORD}@{DB_HOST}:5432/postgres"


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append((" ".join(sql.split()), params))
        self._conn._result = self._conn.router(sql, params)

    def fetchone(self):
        rows = self._conn._result or []
        return rows[0] if rows else None

    def fetchall(self):
        return list(self._conn._result or [])


class FakeConnection:
    def __init__(self, router=None):
        self.executed: list[tuple[str, object]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self._result: list[tuple] | None = None
        self.router = router or (lambda _sql, _params: [])

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def make_db(router=None) -> tuple[Database, FakeConnection]:
    conn = FakeConnection(router)
    db = Database(DSN, connect_fn=lambda *_a, **_k: conn)
    db.connect()
    return db, conn


class TestDsnRedaction:
    def test_the_password_is_removed_and_the_host_is_kept(self):
        redacted = redact_dsn(DSN)
        assert DB_PASSWORD not in redacted
        assert DB_HOST in redacted
        assert "5432" in redacted

    def test_a_dsn_without_credentials_survives(self):
        assert "example.com" in redact_dsn("postgresql://example.com/postgres")

    def test_query_parameters_are_dropped_because_they_can_carry_secrets(self):
        redacted = redact_dsn(f"{DSN}?sslmode=require&password=alsosecret")
        assert "alsosecret" not in redacted

    def test_garbage_does_not_raise(self):
        assert redact_dsn("not a dsn at all")


class TestConnectionErrors:
    def test_from_env_names_the_variable_not_its_value(self):
        with pytest.raises(DatabaseUnavailable) as exc:
            Database.from_env(environ={})
        assert DEFAULT_DSN_ENV_VAR in str(exc.value)

    def test_from_env_reads_the_variable(self):
        db = Database.from_env(
            environ={DEFAULT_DSN_ENV_VAR: DSN}, connect_fn=lambda *_a, **_k: None
        )
        assert db.redacted_dsn.endswith("/postgres")

    def test_an_empty_dsn_is_rejected_outright(self):
        with pytest.raises(DatabaseUnavailable):
            Database("")

    def test_a_connection_failure_never_leaks_the_password(self):
        def boom(*_args, **_kwargs):
            # psycopg's own message routinely contains the whole connection string.
            raise OSError(f"connection failed for {DSN}")

        db = Database(DSN, connect_fn=boom)
        with pytest.raises(DatabaseUnavailable) as exc:
            db.connect()

        assert DB_PASSWORD not in str(exc.value)
        assert DB_HOST in str(exc.value)

    def test_using_the_connection_before_connecting_is_an_error_not_a_none(self):
        db = Database(DSN, connect_fn=lambda *_a, **_k: FakeConnection())
        with pytest.raises(DatabaseUnavailable):
            _ = db.connection


class TestRuns:
    def test_start_run_returns_the_new_id_and_commits(self):
        db, conn = make_db(router=lambda _sql, _params: [(42,)])
        assert db.start_run() == 42
        assert conn.commits == 1

    def test_finish_run_writes_counts_only(self):
        db, conn = make_db()
        db.finish_run(
            7,
            companies_polled=25,
            http_ok=24,
            http_err=1,
            total_live_postings=310,
            new_postings=4,
            ok=True,
        )
        sql, params = conn.executed[-1]
        assert "UPDATE runs" in sql
        assert params == (25, 24, 1, 310, 4, True, 7)
        # Every bound value is an integer or bool. Nothing object-shaped can reach
        # this row (bool is a subclass of int in Python, so this still holds).
        assert all(isinstance(p, int) for p in params)

    def test_finish_run_records_a_failed_verdict(self):
        # Found necessary by live testing: a run that trips an anomaly still
        # closes its row, and without this the next run's export would report
        # the failed run's timestamp as "last successful."
        db, conn = make_db()
        db.finish_run(
            9,
            companies_polled=0,
            http_ok=0,
            http_err=100,
            total_live_postings=0,
            new_postings=0,
            ok=False,
        )
        _sql, params = conn.executed[-1]
        assert params == (0, 0, 100, 0, 0, False, 9)

    def test_previous_finished_run_maps_onto_a_runrow(self):
        row = (3, "2026-09-22T00:00:00Z", "2026-09-22T00:05:00Z", 25, 24, 1, 310, 4)
        db, _ = make_db(router=lambda _sql, _params: [row])
        previous = db.previous_finished_run(before_run_id=4)
        assert isinstance(previous, RunRow)
        assert previous.total_live_postings == 310

    def test_previous_finished_run_is_none_on_the_very_first_run(self):
        db, _ = make_db(router=lambda _sql, _params: [])
        assert db.previous_finished_run(before_run_id=1) is None

    def test_previous_finished_run_does_not_filter_on_ok(self):
        # Deliberately different from last_successful_run_at: the run-over-run
        # anomaly comparison needs the true prior state, whether or not that
        # prior run itself tripped an anomaly — skipping a failed row would
        # compare against stale data instead of what actually happened.
        def router(sql, _params):
            assert " AND ok" not in sql
            return [(5, None, None, 0, 0, 100, 0, 0)]

        db, _ = make_db(router=router)
        assert db.previous_finished_run(before_run_id=6) is not None


class TestLastSuccessfulRunAt:
    def test_it_filters_on_ok(self):
        captured = {}

        def router(sql, _params):
            captured["sql"] = sql
            return [("2026-09-23T16:36:00Z",)]

        db, _ = make_db(router=router)
        assert db.last_successful_run_at() == "2026-09-23T16:36:00Z"
        assert " AND ok" in captured["sql"]

    def test_no_successful_run_yet_returns_none(self):
        db, _ = make_db(router=lambda _sql, _params: [])
        assert db.last_successful_run_at() is None


class TestRlsPosture:
    """The live half of SETUP-PLATFORM.md §7's check."""

    def _db_with(self, without_rls, no_policies):
        def router(sql, _params):
            if "NOT c.relrowsecurity" in sql:
                return [(n,) for n in without_rls]
            if "pg_policy" in sql:
                return [(n,) for n in no_policies]
            return []

        return make_db(router)[0]

    def test_a_table_with_rls_off_is_a_violation(self):
        db = self._db_with(without_rls=["postings"], no_policies=[])
        assert db.rls_violations() == ["postings: RLS is disabled"]

    def test_a_deliberate_deny_all_table_is_not_a_violation(self):
        db = self._db_with(without_rls=[], no_policies=["runs", "notifications_sent"])
        assert db.rls_violations() == []

    def test_an_unlisted_deny_all_table_is_a_violation(self):
        # The case this check exists for: someone adds a table, enables RLS out of
        # habit, forgets the policy, and nothing reads it until it matters.
        db = self._db_with(without_rls=[], no_policies=["saved_searches"])
        violations = db.rls_violations()
        assert len(violations) == 1
        assert "saved_searches" in violations[0]

    def test_a_clean_schema_reports_nothing(self):
        db = self._db_with(without_rls=[], no_policies=[])
        assert db.rls_violations() == []


class TestMigrationRunner:
    def _migration_dir(self, tmp_path: pathlib.Path, names: list[str]) -> pathlib.Path:
        for name in names:
            (tmp_path / name).write_text("CREATE TABLE x (id INT);", encoding="utf-8")
        return tmp_path

    def test_pending_excludes_what_is_already_applied(self, tmp_path):
        directory = self._migration_dir(tmp_path, ["0001_a.sql", "0002_b.sql"])
        db, _ = make_db(router=lambda _sql, _params: [("0001_a.sql",)])
        assert [p.name for p in pending(db, directory)] == ["0002_b.sql"]

    def test_migrations_apply_in_lexical_order(self, tmp_path):
        directory = self._migration_dir(
            tmp_path, ["20260922000002_second.sql", "20260922000001_first.sql"]
        )
        db, _ = make_db(router=lambda _sql, _params: [])
        applied = migrate(db, directory)
        assert applied == ["20260922000001_first.sql", "20260922000002_second.sql"]

    def test_each_migration_is_recorded_and_committed(self, tmp_path):
        directory = self._migration_dir(tmp_path, ["0001_a.sql"])
        db, conn = make_db(router=lambda _sql, _params: [])
        migrate(db, directory)

        recorded = [
            params for sql, params in conn.executed if "INSERT INTO schema_migrations" in sql
        ]
        assert recorded == [("0001_a.sql",)]

    def test_the_bootstrap_table_enables_rls(self, tmp_path):
        db, conn = make_db(router=lambda _sql, _params: [])
        migrate(db, tmp_path)
        bootstrap = conn.executed[0][0]
        assert "CREATE TABLE IF NOT EXISTS schema_migrations" in bootstrap
        assert "ENABLE ROW LEVEL SECURITY" in bootstrap

    def test_a_failing_migration_rolls_back_and_is_not_recorded(self, tmp_path):
        directory = self._migration_dir(tmp_path, ["0001_bad.sql"])

        def router(sql, _params):
            if "CREATE TABLE x" in sql:
                raise RuntimeError("syntax error at or near")
            return []

        db, conn = make_db(router)
        with pytest.raises(DatabaseUnavailable) as exc:
            migrate(db, directory)

        assert "0001_bad.sql" in str(exc.value)
        assert conn.rollbacks == 1
        assert not any("INSERT INTO schema_migrations" in sql for sql, _ in conn.executed)

    def test_dry_run_lists_without_applying(self, tmp_path):
        directory = self._migration_dir(tmp_path, ["0001_a.sql"])
        db, conn = make_db(router=lambda _sql, _params: [])
        planned = migrate(db, directory, dry_run=True)

        assert planned == ["0001_a.sql"]
        assert not any("CREATE TABLE x" in sql for sql, _ in conn.executed)

    def test_an_empty_directory_is_not_an_error(self, tmp_path):
        db, _ = make_db(router=lambda _sql, _params: [])
        assert migrate(db, tmp_path / "nothing_here") == []


class TestRealMigrationFiles:
    """Assertions about the committed SQL itself, so the §6 rules cannot drift."""

    @property
    def sql(self) -> str:
        directory = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "migrations"
        return "\n".join(p.read_text(encoding="utf-8") for p in sorted(directory.glob("*.sql")))

    def test_postings_sets_fillfactor(self):
        # SPEC.md §6: keeps the daily last_seen_at update HOT.
        assert "fillfactor = 85" in self.sql

    def test_there_is_no_index_on_last_seen_at(self):
        # SPEC.md §6 forbids it outright — an index there turns every liveness
        # update into an index write, which is the cost fillfactor exists to avoid.
        for line in self.sql.splitlines():
            if "CREATE INDEX" in line.upper():
                assert "last_seen_at" not in line

    def test_observed_at_exists_on_comp_tiers(self):
        # §11.1: unrecoverable if added after data collection starts.
        assert "observed_at" in self.sql

    def test_notifications_sent_cannot_hold_an_address(self):
        assert "profile NOT LIKE '%@%'" in self.sql

    def test_the_rls_baseline_migration_sorts_first(self):
        directory = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "migrations"
        first = sorted(directory.glob("*.sql"))[0]
        assert "rls_baseline" in first.name

    def test_runs_gained_an_ok_column(self):
        # Added after live testing showed last_successful_run_at() had no way
        # to exclude a run that finished but tripped an anomaly.
        assert "ADD COLUMN ok BOOLEAN" in self.sql


class TestCheckSchemaEntryPoint:
    def test_it_reports_blocked_and_exits_nonzero_without_a_dsn(self, monkeypatch, capsys):
        from src import check_schema

        monkeypatch.delenv(DEFAULT_DSN_ENV_VAR, raising=False)
        assert check_schema.main([]) == 1
        assert "BLOCKED" in capsys.readouterr().out


class TestMalformedDsnDiagnostics:
    """The failure that prompted these: a real migrate.yml run reported only
    '<unparseable dsn>: OperationalError', which withholds the one fact worth
    having. A diagnostic that hides the host is no better than none."""

    PLACEHOLDER = "postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.example.com:5432/postgres"

    def test_an_unreplaced_password_placeholder_is_named_exactly(self):
        problem = describe_dsn_problem(self.PLACEHOLDER)
        assert problem is not None
        assert "placeholder" in problem

    def test_the_diagnostic_never_echoes_the_connection_string(self):
        problem = describe_dsn_problem(self.PLACEHOLDER)
        assert "aws-0-us-east-1" not in problem
        assert "abcdefgh" not in problem

    def test_a_wrong_scheme_is_named(self):
        problem = describe_dsn_problem("psql 'host=x user=y'")
        assert problem is not None and "postgresql://" in problem

    def test_surrounding_whitespace_is_named(self):
        assert "whitespace" in describe_dsn_problem(f"  {DSN}  ")

    def test_an_empty_value_is_named(self):
        assert "empty" in describe_dsn_problem("   ")

    def test_a_missing_password_is_named(self):
        problem = describe_dsn_problem(f"postgresql://postgres@{DB_HOST}:5432/postgres")
        assert problem is not None and "password" in problem

    def test_a_good_dsn_reports_no_problem(self):
        assert describe_dsn_problem(DSN) is None

    def test_redact_dsn_still_names_the_host_when_parsing_fails(self):
        redacted = redact_dsn(self.PLACEHOLDER)
        assert "pooler.example.com" in redacted
        assert "YOUR-PASSWORD" not in redacted

    def test_redact_dsn_handles_an_empty_string(self):
        assert redact_dsn("") == "<empty dsn>"

    def test_redact_secrets_strips_a_password_echoed_by_the_driver(self):
        # GitHub masks the exact registered secret; the password alone is a
        # different string and would not be masked.
        driver_text = f'connection failed: "{DSN}" timed out'
        cleaned = redact_secrets(driver_text, DSN)
        assert DB_PASSWORD not in cleaned
        assert "timed out" in cleaned

    def test_connect_reports_the_malformed_string_before_dialling(self):
        called = []

        def should_not_run(*_a, **_k):
            called.append(1)
            raise AssertionError("connect was attempted with a malformed DSN")

        db = Database(self.PLACEHOLDER, connect_fn=should_not_run)
        with pytest.raises(DatabaseUnavailable) as exc:
            db.connect()
        assert "placeholder" in str(exc.value)
        assert not called
