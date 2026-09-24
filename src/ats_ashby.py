"""Ashby adapter. SPEC.md §9:
developers.ashbyhq.com/docs/public-job-posting-api

publishedAt is a direct field. workplaceType is structured (capitalised:
OnSite/Hybrid/Remote) and populated on the large majority of live postings
measured (SPEC.md §9). The compensation object is truthy even when nothing
is disclosed (compensationTiers: [], summary null) — disclosure is judged on
the tiers/summary, never on the object itself; shouldDisplayCompensationOnJobPostings
is the provider's own flag and tracks this exactly, but is not stored here
(M5's normalization territory).
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
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
        comp_quality, comp_summary = _comp(job)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("title") or "",
                department_raw=job.get("department") or job.get("team"),
                location_raw=job.get("location"),
                workplace_type_raw=job.get("workplaceType"),
                url=job.get("jobUrl"),
                posted_at=parse_iso_or_epoch_ms(job.get("publishedAt")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _comp(job: dict) -> tuple[CompDataQuality, str | None]:
    comp = job.get("compensation") or {}
    tiers = comp.get("compensationTiers")
    summary = comp.get("compensationTierSummary")
    if tiers:
        return CompDataQuality.STRUCTURED, summary or str(tiers)
    if summary:
        return CompDataQuality.PARSED, summary
    return CompDataQuality.NONE, None
