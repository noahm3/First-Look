"""Tests for src/health.py — run accounting, anomalies, and the run summary.

C-0.8 lives here: the run summary prints counts only and contains no `@`.
"""

import dataclasses

import pytest

from src.db import Database, DatabaseUnavailable, RunRow
from src.health import (
    HTTP_ERROR_RATE_THRESHOLD,
    POSTING_DROP_THRESHOLD,
    AnomalyCode,
    FailingCompany,
    RunCounts,
    RunRecorder,
    detect_anomalies,
    format_run_summary,
    scrub,
)
from tests.test_db import DSN, FakeConnection


def run_row(**overrides) -> RunRow:
    base = {
        "id": 1,
        "started_at": None,
        "finished_at": None,
        "companies_polled": 25,
        "http_ok": 25,
        "http_err": 0,
        "total_live_postings": 400,
        "new_postings": 3,
    }
    return RunRow(**{**base, **overrides})


class FakeFetcher:
    def __init__(self, ok=True):
        self.calls: list[str] = []
        self._ok = ok

    def get(self, url, **_kwargs):
        self.calls.append(url)

        class _Result:
            ok = self._ok
            error = None if self._ok else "boom"

        return _Result()


def make_recorder(*, router=None, previous=None, **kwargs) -> tuple[RunRecorder, FakeConnection]:
    def default_router(sql, _params):
        if "INSERT INTO runs" in sql:
            return [(99,)]
        if "FROM runs" in sql and "ORDER BY id DESC" in sql:
            return (
                [
                    (
                        previous.id,
                        previous.started_at,
                        previous.finished_at,
                        previous.companies_polled,
                        previous.http_ok,
                        previous.http_err,
                        previous.total_live_postings,
                        previous.new_postings,
                    )
                ]
                if previous
                else []
            )
        return []

    conn = FakeConnection(router or default_router)
    db = Database(DSN, connect_fn=lambda *_a, **_k: conn)
    kwargs.setdefault("check_schema_posture", False)
    return RunRecorder(db, **kwargs), conn


# ---------------------------------------------------------------------------
# C-0.8 — the run summary prints counts only and contains no `@`
# ---------------------------------------------------------------------------


class TestRunSummaryIsSafe:
    def test_a_plain_summary_contains_no_at_sign(self):
        summary = format_run_summary(
            RunCounts(
                companies_polled=25,
                http_ok=24,
                http_err=1,
                total_live_postings=412,
                new_postings=6,
                profiles_matched=2,
                alerts_sent=5,
            ),
            run_id=7,
        )
        assert "@" not in summary

    def test_a_company_name_containing_an_at_sign_cannot_smuggle_one_in(self):
        # SPEC.md §14 names this exact hazard: a company name can legitimately
        # contain `@`, which is why the assertion is scoped to the deterministic
        # summary rather than to all of stdout.
        counts = RunCounts(
            failing=(FailingCompany(name="Foo@Bar Energy", reason="404 on token bar@baz"),)
        )
        summary = format_run_summary(counts)

        assert "@" not in summary
        assert "Foo[at]Bar Energy" in summary
        assert "404" in summary

    def test_every_field_of_a_fully_populated_summary_stays_clean(self):
        counts = RunCounts(
            companies_polled=2000,
            http_ok=1900,
            http_err=100,
            total_live_postings=15000,
            new_postings=42,
            closed_postings=17,
            reposts=3,
            profiles_matched=2,
            alerts_sent=9,
            failing=tuple(
                FailingCompany(name=f"Company@{i}", reason=f"reason@{i}") for i in range(30)
            ),
        )
        summary = format_run_summary(
            counts,
            anomalies=detect_anomalies(counts, run_row(total_live_postings=30000)),
            run_id=12,
            duration_seconds=94.2,
            previous_live_postings=30000,
        )
        assert "@" not in summary

    def test_scrub_is_the_only_transformation_applied(self):
        assert scrub("plain text") == "plain text"
        assert scrub("a@b@c") == "a[at]b[at]c"

    def test_the_summary_is_pure_ascii(self):
        # It has to survive any console and any mail client, including a Windows
        # terminal on cp1252. Company names are the only non-ASCII risk, so they
        # are the case worth pinning.
        counts = RunCounts(
            companies_polled=3,
            failing=(FailingCompany(name="Energia Solucoes", reason="timeout"),),
        )
        assert format_run_summary(counts, run_id=1, duration_seconds=1.0).isascii()

    def test_the_summary_is_short_enough_to_read_in_a_failure_email(self):
        # SPEC.md §14: GitHub's failure email links to the log, so the last twenty
        # lines have to answer "what's wrong".
        counts = RunCounts(failing=tuple(FailingCompany(f"c{i}", "404") for i in range(200)))
        summary = format_run_summary(counts)
        assert len(summary.splitlines()) <= 30
        assert "and 185 more" in summary


class TestRunSummaryContent:
    def test_it_reports_the_things_section_14_asks_for(self):
        summary = format_run_summary(
            RunCounts(
                companies_polled=25, new_postings=6, failing=(FailingCompany("Acme", "404"),)
            ),
            run_id=3,
        )
        assert "companies polled     25" in summary
        assert "new postings         6" in summary
        assert "Acme: 404" in summary

    def test_a_clean_run_says_so_rather_than_saying_nothing(self):
        summary = format_run_summary(RunCounts(companies_polled=25))
        assert "anomalies            none" in summary
        assert "failing companies    0" in summary

    def test_a_failed_run_says_why_it_will_exit_non_zero(self):
        counts = RunCounts(http_ok=1, http_err=9)
        summary = format_run_summary(counts, anomalies=detect_anomalies(counts, None))
        assert "FAILED" in summary
        assert "exiting non-zero" in summary

    def test_the_posting_delta_against_the_previous_run_is_shown(self):
        summary = format_run_summary(RunCounts(total_live_postings=390), previous_live_postings=400)
        assert "(-10 vs previous run)" in summary


# ---------------------------------------------------------------------------
# Anomaly detection — SPEC.md §14
# ---------------------------------------------------------------------------


class TestAnomalyDetection:
    def test_a_posting_drop_over_the_threshold_is_an_anomaly(self):
        counts = RunCounts(total_live_postings=200)
        anomalies = detect_anomalies(counts, run_row(total_live_postings=400))
        assert [a.code for a in anomalies] == [AnomalyCode.POSTING_DROP]
        assert "50%" in anomalies[0].detail

    def test_a_drop_just_under_the_threshold_is_not(self):
        previous = 400
        current = int(previous * (1 - POSTING_DROP_THRESHOLD)) + 1
        anomalies = detect_anomalies(
            RunCounts(total_live_postings=current), run_row(total_live_postings=previous)
        )
        assert anomalies == []

    def test_growth_is_never_an_anomaly(self):
        anomalies = detect_anomalies(
            RunCounts(total_live_postings=900), run_row(total_live_postings=400)
        )
        assert anomalies == []

    def test_the_first_ever_run_has_no_baseline_and_so_no_drop(self):
        assert detect_anomalies(RunCounts(total_live_postings=0), None) == []

    def test_a_previous_run_with_zero_postings_is_not_a_divide_by_zero(self):
        assert (
            detect_anomalies(RunCounts(total_live_postings=0), run_row(total_live_postings=0)) == []
        )

    def test_an_http_error_rate_over_the_threshold_is_an_anomaly(self):
        counts = RunCounts(http_ok=80, http_err=20)
        anomalies = detect_anomalies(counts, None)
        assert [a.code for a in anomalies] == [AnomalyCode.HTTP_ERROR_RATE]

    def test_an_error_rate_at_the_threshold_is_not(self):
        counts = RunCounts(http_ok=90, http_err=10)
        assert counts.http_error_rate == pytest.approx(HTTP_ERROR_RATE_THRESHOLD)
        assert detect_anomalies(counts, None) == []

    def test_zero_requests_is_not_an_error_rate_of_anything(self):
        assert detect_anomalies(RunCounts(), None) == []

    def test_both_anomalies_can_fire_at_once(self):
        counts = RunCounts(http_ok=10, http_err=90, total_live_postings=10)
        codes = {a.code for a in detect_anomalies(counts, run_row(total_live_postings=400))}
        assert codes == {AnomalyCode.POSTING_DROP, AnomalyCode.HTTP_ERROR_RATE}


# ---------------------------------------------------------------------------
# RunRecorder
# ---------------------------------------------------------------------------


class TestRunRecorder:
    def test_a_clean_run_exits_zero_and_pings(self):
        fetcher = FakeFetcher()
        recorder, _ = make_recorder(healthcheck_url="https://hc-ping.example/abc", fetcher=fetcher)
        lines: list[str] = []
        recorder._emit = lines.append

        with recorder:
            recorder.bump("companies_polled", 25)
            recorder.bump("http_ok", 25)
            recorder.set_count("total_live_postings", 400)

        assert recorder.should_fail_run() is False
        assert fetcher.calls == ["https://hc-ping.example/abc"]
        assert "[ok] ===" in lines[0]

    def test_a_failing_run_exits_non_zero_and_does_not_ping(self):
        # A dead-man's switch that gets pinged on a broken run is not a switch.
        fetcher = FakeFetcher()
        recorder, _ = make_recorder(
            healthcheck_url="https://hc-ping.example/abc",
            fetcher=fetcher,
            previous=run_row(total_live_postings=400),
        )
        recorder._emit = lambda _s: None

        with recorder:
            recorder.set_count("total_live_postings", 10)

        assert recorder.should_fail_run() is True
        assert fetcher.calls == []

    def test_finish_returns_the_exit_code(self):
        recorder, _ = make_recorder()
        recorder._emit = lambda _s: None
        with recorder:
            pass
        assert recorder.finish() == 0

    def test_a_database_failure_is_an_anomaly_not_a_crash(self):
        # SPEC.md §14 / §6: an outage must be loud. It must also still produce a
        # summary, or the log's tail explains nothing.
        def boom(*_a, **_k):
            raise OSError("connection refused")

        db = Database(DSN, connect_fn=boom)
        lines: list[str] = []
        recorder = RunRecorder(db, emit=lines.append, check_schema_posture=False)

        with recorder:
            pass

        assert recorder.should_fail_run() is True
        assert AnomalyCode.DATABASE_UNAVAILABLE in {a.code for a in recorder.anomalies}
        assert "FAILED" in lines[0]
        assert "@" not in lines[0]

    def test_a_database_failure_summary_does_not_leak_the_password(self):
        def boom(*_a, **_k):
            raise OSError(f"could not connect using {DSN}")

        db = Database(DSN, connect_fn=boom)
        lines: list[str] = []
        with RunRecorder(db, emit=lines.append, check_schema_posture=False):
            pass

        assert "hunter2" not in lines[0]

    def test_a_bad_rls_posture_fails_the_run(self):
        def router(sql, _params):
            if "INSERT INTO runs" in sql:
                return [(99,)]
            if "NOT c.relrowsecurity" in sql:
                return [("postings",)]
            return []

        recorder, _ = make_recorder(router=router, check_schema_posture=True)
        recorder._emit = lambda _s: None
        with recorder:
            pass

        assert AnomalyCode.SCHEMA_POSTURE in {a.code for a in recorder.anomalies}
        assert recorder.should_fail_run() is True

    def test_failing_companies_are_recorded_never_removed(self):
        recorder, _ = make_recorder()
        recorder._emit = lambda _s: None
        with recorder:
            recorder.record_failing_company("Acme Energy", "404 invalid token")
            recorder.record_failing_company("Beta Grid", "timeout x3")

        assert [c.name for c in recorder.counts.failing] == ["Acme Energy", "Beta Grid"]

    def test_an_unknown_counter_is_a_programming_error(self):
        recorder, _ = make_recorder()
        with pytest.raises(KeyError):
            recorder.bump("not_a_counter")

    def test_the_run_row_is_closed_with_the_accumulated_counts(self):
        recorder, conn = make_recorder()
        recorder._emit = lambda _s: None
        with recorder:
            recorder.bump("companies_polled", 25)
            recorder.bump("http_ok", 24)
            recorder.bump("http_err", 1)
            recorder.set_count("total_live_postings", 412)
            recorder.bump("new_postings", 6)

        updates = [p for sql, p in conn.executed if "UPDATE runs" in sql]
        assert updates == [(25, 24, 1, 412, 6, 99)]

    def test_a_ping_failure_does_not_fail_the_run(self):
        # If the ping does not land the dead-man's switch fires on its own, which
        # is correct. Failing here would turn a working alarm into a false one.
        recorder, _ = make_recorder(
            healthcheck_url="https://hc-ping.example/abc", fetcher=FakeFetcher(ok=False)
        )
        recorder._emit = lambda _s: None
        with recorder:
            pass
        assert recorder.should_fail_run() is False

    def test_the_healthcheck_url_never_reaches_the_summary(self):
        # SECURITY.md §S4: a leaked ping URL lets someone suppress the alert.
        secret_url = "https://hc-ping.example/9f3c-secret-uuid"
        lines: list[str] = []
        recorder, _ = make_recorder(healthcheck_url=secret_url, fetcher=FakeFetcher())
        recorder._emit = lines.append
        with recorder:
            pass
        assert secret_url not in lines[0]
        assert "9f3c-secret-uuid" not in lines[0]


class TestCountsOnlyInterface:
    """SECURITY.md §S3 calls this an interface decision, not a check."""

    def test_run_counts_holds_no_field_that_could_carry_an_address(self):
        counts = RunCounts()
        for spec in dataclasses.fields(counts):
            if spec.name == "failing":
                continue
            assert isinstance(getattr(counts, spec.name), int), f"{spec.name} is not a count"

        # The one nested type, and both of its fields are company-level strings.
        assert {f.name for f in dataclasses.fields(FailingCompany)} == {"name", "reason"}

    def test_format_run_summary_rejects_being_handed_an_object(self):
        with pytest.raises(TypeError):
            format_run_summary(RunCounts(), profile={"email": "x"})  # type: ignore[call-arg]

    def test_finish_run_has_no_kwargs_escape_hatch(self):
        db = Database(DSN, connect_fn=lambda *_a, **_k: FakeConnection())
        db.connect()
        # Every count is required and named. There is no **kwargs an object could
        # be smuggled through, which is the property SECURITY.md §S3 is after.
        with pytest.raises(TypeError):
            db.finish_run(1, companies_polled=1)


class TestDatabaseUnavailableIsExported:
    def test_it_is_importable_for_callers_that_must_propagate_it(self):
        assert issubclass(DatabaseUnavailable, RuntimeError)
