"""Greenhouse adapter. SPEC.md §9:
docs.greenhouse.io/job-board.html

content=true is mandatory, not optional — `departments` is absent without it
(confirmed live 2026-09-22 against 8 mapped boards). The per-job detail
endpoint is never called: it returned a byte-identical object to the
content=true list entry on 6/6 jobs across two boards, so it buys nothing
(SPEC.md §9). `pay_input_ranges` appeared on none of 384 live postings
measured — comp is classified NONE unconditionally here; if a future board
ever populates it, that is a real finding worth a fresh look, not something
to guess a mapping for now.
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
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
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        departments = [
            d.get("name")
            for d in (job.get("departments") or [])
            if isinstance(d, dict) and d.get("name")
        ]
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("title") or "",
                department_raw=", ".join(departments) or None,
                location_raw=(job.get("location") or {}).get("name"),
                url=job.get("absolute_url"),
                posted_at=parse_iso_or_epoch_ms(job.get("first_published")),
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
