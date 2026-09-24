"""Lever adapter. SPEC.md §9:
hire.lever.co/developer/documentation documents the authenticated v1 Data API.
The public v0 Postings API used here is not officially documented.

createdAt is undocumented epoch ms and is not a reliable publication date —
9 of 28 sampled live postings carried a createdAt over a year old (SPEC.md
§9) — but it is still the best available signal, stored as-is via
parse_iso_or_epoch_ms, which returns None rather than raising when the field
is absent (C-2.6). workplaceType is a structured onsite/hybrid/remote field,
confirmed live 2026-09-24 (lowercase), populated on 363/363 live postings
measured in September (SPEC.md §9).

Comp: salaryRange, when present, is structured but its sub-field shape has
not been independently re-verified this milestone (open item — see the M2
DEVLOG entry). Classified STRUCTURED with a best-effort rendered summary
rather than parsed into CompTier rows, per this plan's Global Constraints
(CompTier construction is M5's job).
"""

from src.ats_common import AdapterResult, as_dict, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
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
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        cats = as_dict(job.get("categories"))
        comp_quality, comp_summary = _comp(job)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("text") or "",
                department_raw=cats.get("team") or cats.get("department"),
                location_raw=cats.get("location"),
                workplace_type_raw=job.get("workplaceType"),
                url=job.get("hostedUrl"),
                posted_at=parse_iso_or_epoch_ms(job.get("createdAt")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _comp(job: dict) -> tuple[CompDataQuality, str | None]:
    salary_range = job.get("salaryRange")
    if isinstance(salary_range, dict) and salary_range:
        parts = [
            str(salary_range.get(key))
            for key in ("min", "max", "currency", "interval")
            if salary_range.get(key) is not None
        ]
        return CompDataQuality.STRUCTURED, " ".join(parts) or None
    summary = job.get("salaryDescriptionPlain")
    if summary:
        return CompDataQuality.PARSED, summary
    return CompDataQuality.NONE, None
