"""Breezy HR adapter. SPEC.md §9: developer.breezy.hr documents the
authenticated admin API (api.breezy.hr/v3, GET v3/company/{company_id}/
positions, requires an auth token) — not the endpoint used here.

{company}.breezy.hr/json is a separate, undocumented, public, unauthenticated
board endpoint, confirmed live 2026-09-24. salary is a free-text string
(e.g. "$110,000 - $140,000 / year") or an empty string when undisclosed, not
structured — classified PARSED only when non-empty. location.is_remote is a
boolean, not a 3-way onsite/hybrid/remote enum like Lever/Ashby; only the
True case is mapped, so an unremarked absence is never guessed as "remote"
(mirrors SPEC.md §12.3's "UNKNOWN stays visible" caution).
"""

from src.ats_common import AdapterResult, as_dict, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://{token}.breezy.hr/json"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, list):
        return AdapterResult(ok=False, error="unexpected shape: expected a JSON array")

    postings = []
    for job in body:
        if not isinstance(job, dict) or not job.get("id"):
            continue
        location = as_dict(job.get("location"))
        comp_quality, comp_summary = _comp(job)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("name") or "",
                department_raw=job.get("department"),
                location_raw=location.get("name"),
                workplace_type_raw="remote" if location.get("is_remote") is True else None,
                url=job.get("url"),
                posted_at=parse_iso_or_epoch_ms(job.get("published_date")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _comp(job: dict) -> tuple[CompDataQuality, str | None]:
    salary = job.get("salary")
    if isinstance(salary, str) and salary.strip():
        return CompDataQuality.PARSED, salary.strip()
    return CompDataQuality.NONE, None
