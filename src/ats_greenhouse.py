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

A board with full descriptions can exceed src/http.py's response-size cap
with content=true (a real 400+ posting board hit this and recovered 618
postings via this exact fallback, per DEVLOG.md's iteration7 entry) — on
RESPONSE_TOO_LARGE, falls back to the plain list. `department_raw` is lost
for that company (the plain list has no `departments` field at all), which
beats losing the company outright.
"""

from src.ats_common import AdapterResult, as_dict, parse_iso_or_epoch_ms
from src.http import FetchClient, FetchErrorKind
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    base = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    result = client.get(f"{base}?content=true")
    if not result.ok and result.error and result.error.kind is FetchErrorKind.RESPONSE_TOO_LARGE:
        result = client.get(base)
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
                location_raw=as_dict(job.get("location")).get("name"),
                url=job.get("absolute_url"),
                posted_at=parse_iso_or_epoch_ms(job.get("first_published")),
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
