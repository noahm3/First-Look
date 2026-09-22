"""Run accounting, anomaly detection, and the run summary.

SPEC.md §14's whole subject is that absence of output must be distinguishable from
absence of jobs, because nobody is watching for two months. Three mechanisms, and
this module owns all three:

1.  **The run summary** is the final output of every run. GitHub's failure email is
    a fixed template linking to the log, so the last twenty lines have to answer
    "what's wrong" without a stack trace.
2.  **Aggregate anomalies exit non-zero**, which turns systemic breakage into an
    email for free — rather than into hundreds of individual per-company failures
    nobody reads.
3.  **The healthchecks.io ping** on success. It is the only mechanism that can
    catch "Actions stopped running at all", since no internal heartbeat can report
    a job that never started.

The counts-only shape is the load-bearing part. SECURITY.md §S3 calls it an
interface decision rather than a check: :func:`format_run_summary` takes a
:class:`RunCounts` of integers and company names, and there is no parameter it
could be handed a notification profile through. A function that cannot accept an
address cannot print one into a world-readable log.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from src.db import Database, DatabaseUnavailable, RunRow
from src.http import FetchClient

log = logging.getLogger(__name__)

# SPEC.md §14's two aggregate thresholds.
POSTING_DROP_THRESHOLD = 0.25
HTTP_ERROR_RATE_THRESHOLD = 0.10


def scrub(text: str) -> str:
    """Remove `@` from a third-party string bound for the run summary.

    SPEC.md §14 notes the tension honestly: the summary names failing companies,
    and a company name can legitimately contain `@`, so a blanket "no @ in stdout"
    grep is brittle. The resolution is to make the *summary* deterministic rather
    than to weaken the assertion — C-0.8 then holds literally, and the only cost is
    that a company called "Foo@Bar" reads as "Foo[at]Bar" in one diagnostic line.
    """
    return text.replace("@", "[at]")


class AnomalyCode(StrEnum):
    POSTING_DROP = "posting_drop"
    HTTP_ERROR_RATE = "http_error_rate"
    DATABASE_UNAVAILABLE = "database_unavailable"
    SCHEMA_POSTURE = "schema_posture"


@dataclass(frozen=True, slots=True)
class Anomaly:
    code: AnomalyCode
    detail: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.detail}"


@dataclass(frozen=True, slots=True)
class FailingCompany:
    """A company that could not be polled. Named, never auto-removed (§14)."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class RunCounts:
    """Everything the summary is allowed to know about a run.

    Integers and company names. No postings, no profiles, no addresses — there is
    nowhere in this shape to put one.
    """

    companies_polled: int = 0
    http_ok: int = 0
    http_err: int = 0
    total_live_postings: int = 0
    new_postings: int = 0
    closed_postings: int = 0
    reposts: int = 0
    profiles_matched: int = 0
    alerts_sent: int = 0
    failing: tuple[FailingCompany, ...] = ()

    @property
    def http_total(self) -> int:
        return self.http_ok + self.http_err

    @property
    def http_error_rate(self) -> float:
        return self.http_err / self.http_total if self.http_total else 0.0


def detect_anomalies(
    counts: RunCounts,
    previous: RunRow | None,
    *,
    drop_threshold: float = POSTING_DROP_THRESHOLD,
    error_rate_threshold: float = HTTP_ERROR_RATE_THRESHOLD,
) -> list[Anomaly]:
    """SPEC.md §14's aggregate checks. An empty list means the run looks sane."""
    anomalies: list[Anomaly] = []

    if previous is not None and previous.total_live_postings > 0:
        drop = (previous.total_live_postings - counts.total_live_postings) / (
            previous.total_live_postings
        )
        if drop > drop_threshold:
            anomalies.append(
                Anomaly(
                    AnomalyCode.POSTING_DROP,
                    f"live postings fell {drop:.0%} "
                    f"({previous.total_live_postings} -> {counts.total_live_postings}), "
                    f"threshold {drop_threshold:.0%}",
                )
            )

    if counts.http_total and counts.http_error_rate > error_rate_threshold:
        anomalies.append(
            Anomaly(
                AnomalyCode.HTTP_ERROR_RATE,
                f"{counts.http_err} of {counts.http_total} requests failed "
                f"({counts.http_error_rate:.0%}), threshold {error_rate_threshold:.0%}",
            )
        )

    return anomalies


def format_run_summary(
    counts: RunCounts,
    *,
    anomalies: tuple[Anomaly, ...] | list[Anomaly] = (),
    run_id: int | None = None,
    duration_seconds: float | None = None,
    previous_live_postings: int | None = None,
    max_failing_listed: int = 15,
) -> str:
    """The final output of every run.

    Counts only. This signature is the control — see the module docstring and
    SECURITY.md §S3.
    """
    lines: list[str] = []
    verdict = "FAILED" if anomalies else "ok"
    header = f"run {run_id}" if run_id is not None else "run"
    if duration_seconds is not None:
        header = f"{header} finished in {duration_seconds:.1f}s"
    # ASCII only. This string is the one output that has to be legible from any
    # console and any mail client, including a Windows terminal on cp1252.
    lines.append(f"=== {header} [{verdict}] ===")

    delta = ""
    if previous_live_postings is not None:
        change = counts.total_live_postings - previous_live_postings
        delta = f" ({change:+d} vs previous run)"

    lines.append(f"companies polled     {counts.companies_polled}")
    lines.append(f"http ok / error      {counts.http_ok} / {counts.http_err}")
    lines.append(f"live postings        {counts.total_live_postings}{delta}")
    lines.append(f"new postings         {counts.new_postings}")
    lines.append(f"closed postings      {counts.closed_postings}")
    lines.append(f"reposts              {counts.reposts}")
    # "2 profiles matched, 5 alerts sent" — never an address, never which profile
    # received what (SPEC.md §14).
    lines.append(f"profiles matched     {counts.profiles_matched}")
    lines.append(f"alerts sent          {counts.alerts_sent}")

    if counts.failing:
        lines.append(f"failing companies    {len(counts.failing)}")
        for company in counts.failing[:max_failing_listed]:
            lines.append(f"  - {scrub(company.name)}: {scrub(company.reason)}")
        remaining = len(counts.failing) - max_failing_listed
        if remaining > 0:
            lines.append(f"  ... and {remaining} more")
    else:
        lines.append("failing companies    0")

    if anomalies:
        lines.append("anomalies:")
        for anomaly in anomalies:
            lines.append(f"  - {scrub(str(anomaly))}")
        lines.append("exiting non-zero so this run produces a failure email")
    else:
        lines.append("anomalies            none")

    return "\n".join(lines)


class RunRecorder:
    """Opens a run, accumulates counters, closes it, and decides the exit code.

    Used as a context manager. The summary prints on the way out whatever happened,
    including when the database was never reachable — a run that dies silently is
    the exact failure SPEC.md §3.3 forbids.
    """

    def __init__(
        self,
        db: Database,
        *,
        healthcheck_url: str | None = None,
        fetcher: FetchClient | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        emit: Callable[[str], None] = print,
        check_schema_posture: bool = True,
    ) -> None:
        self._db = db
        self._healthcheck_url = healthcheck_url
        self._fetcher = fetcher
        self._now = now
        self._emit = emit
        self._check_schema_posture = check_schema_posture

        self.run_id: int | None = None
        self._started: datetime | None = None
        self._previous: RunRow | None = None
        self._anomalies: list[Anomaly] = []
        self._failing: list[FailingCompany] = []
        self._counters: dict[str, int] = {
            "companies_polled": 0,
            "http_ok": 0,
            "http_err": 0,
            "total_live_postings": 0,
            "new_postings": 0,
            "closed_postings": 0,
            "reposts": 0,
            "profiles_matched": 0,
            "alerts_sent": 0,
        }

    # -- accumulation ------------------------------------------------------

    def bump(self, counter: str, amount: int = 1) -> None:
        if counter not in self._counters:
            raise KeyError(f"unknown counter {counter!r}")
        self._counters[counter] += amount

    def set_count(self, counter: str, value: int) -> None:
        if counter not in self._counters:
            raise KeyError(f"unknown counter {counter!r}")
        self._counters[counter] = value

    def record_failing_company(self, name: str, reason: str) -> None:
        """Flag a company. Never removes it — §14 is explicit about that."""
        self._failing.append(FailingCompany(name=name, reason=reason))

    @property
    def counts(self) -> RunCounts:
        return RunCounts(failing=tuple(self._failing), **self._counters)

    @property
    def anomalies(self) -> tuple[Anomaly, ...]:
        return tuple(self._anomalies)

    def should_fail_run(self) -> bool:
        """Whether this run must exit non-zero (SPEC.md §14)."""
        return bool(self._anomalies)

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "RunRecorder":
        self._started = self._now()
        try:
            self._db.connect()
            self.run_id = self._db.start_run()
            self._previous = self._db.previous_finished_run(self.run_id)
            if self._check_schema_posture:
                violations = self._db.rls_violations()
                if violations:
                    self._anomalies.append(
                        Anomaly(
                            AnomalyCode.SCHEMA_POSTURE,
                            f"{len(violations)} table(s) with the wrong RLS posture: "
                            + "; ".join(violations),
                        )
                    )
        except DatabaseUnavailable as exc:
            # SPEC.md §14: a DB connection failure is part of the same aggregate
            # rule. It must be loud, not a silent forever-retry.
            self._anomalies.append(Anomaly(AnomalyCode.DATABASE_UNAVAILABLE, str(exc)))
        return self

    def __exit__(self, exc_type: type | None, exc: BaseException | None, _tb: Any) -> bool:
        if exc_type is not None and not isinstance(exc, DatabaseUnavailable):
            # Let a genuine programming error surface, but still print a summary
            # first so the log's tail says something useful.
            self._anomalies.append(
                Anomaly(AnomalyCode.DATABASE_UNAVAILABLE, f"run aborted: {exc_type.__name__}")
            )
        self.finish()
        return False

    def finish(self) -> int:
        """Close the run, ping on success, print the summary, return an exit code."""
        counts = self.counts
        self._anomalies.extend(detect_anomalies(counts, self._previous))

        if self.run_id is not None:
            try:
                self._db.finish_run(
                    self.run_id,
                    companies_polled=counts.companies_polled,
                    http_ok=counts.http_ok,
                    http_err=counts.http_err,
                    total_live_postings=counts.total_live_postings,
                    new_postings=counts.new_postings,
                )
            except DatabaseUnavailable as exc:
                self._anomalies.append(Anomaly(AnomalyCode.DATABASE_UNAVAILABLE, str(exc)))

        failed = self.should_fail_run()
        if not failed:
            self._ping_healthcheck()

        duration = None
        if self._started is not None:
            duration = (self._now() - self._started).total_seconds()

        self._emit(
            format_run_summary(
                counts,
                anomalies=self.anomalies,
                run_id=self.run_id,
                duration_seconds=duration,
                previous_live_postings=(
                    self._previous.total_live_postings if self._previous else None
                ),
            )
        )
        return 1 if failed else 0

    # -- dead-man's switch -------------------------------------------------

    def _ping_healthcheck(self) -> None:
        if not self._healthcheck_url or self._fetcher is None:
            return
        result = self._fetcher.get(self._healthcheck_url)
        # Never log the URL. SECURITY.md §S4: a leaked ping URL lets someone
        # suppress the dead-man's-switch alert by pinging it themselves, which
        # makes it a confidentiality matter and not merely a nuisance.
        if result.ok:
            log.info("healthcheck ping accepted")
        else:
            # Deliberately not an anomaly. If the ping does not land, the
            # dead-man's switch fires on its own, which is the correct outcome —
            # failing the run here would convert a working alarm into a false one.
            log.warning("healthcheck ping did not succeed (%s)", result.error)
