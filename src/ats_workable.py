"""Workable adapter. SPEC.md §9: developer.workable.com documents the
authenticated admin API (spi/v3/jobs, bearer token, r_jobs scope,
10 req/10sec limit) — not the endpoint used here.

apply.workable.com/api/v1/widget/accounts/{company} is a separate,
undocumented, public, unauthenticated board endpoint that powers customers'
own careers pages, confirmed live 2026-09-24. No compensation field exists
on this endpoint (the documented admin API's salary object does not appear
here) — comp_data_quality is always NONE.
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'jobs' array")

    postings = []
    for job in body["jobs"]:
        if not isinstance(job, dict) or not job.get("shortcode"):
            continue
        location_parts = [job.get("city"), job.get("state"), job.get("country")]
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job["shortcode"],
                title_raw=job.get("title") or "",
                department_raw=job.get("department"),
                location_raw=", ".join(p for p in location_parts if p) or None,
                workplace_type_raw="remote" if job.get("telecommuting") is True else None,
                url=job.get("url") or job.get("application_url"),
                posted_at=parse_iso_or_epoch_ms(job.get("published_on")),
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
