"""Rippling adapter. SPEC.md §9:
developer.rippling.com/documentation/job-board-api documents `v1`, which
requires a paid Recruiting Pro subscription and an API key. The `v2`
endpoint used here is undocumented, public, and unauthenticated — the same
endpoint Rippling's own embed widget and hosted careers page call, confirmed
live against 62 companies (spikes/iteration11_rippling_spike.py).

Unlike Greenhouse, the per-job detail call is NOT redundant: createdOn and
structured payRangeDetails exist only there. A failed detail call degrades
that one posting (posted_at/comp stay None/NONE) rather than dropping the
whole company, mirroring Greenhouse's size-cap degrade precedent (SPEC.md
§9). Token resolution from a careers page is M3's mapping-cascade job, not
this adapter's — this takes an already-known token.
"""

from datetime import datetime

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting

API_BASE = "https://api.rippling.com/platform/api/ats/v2/board"


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    result = client.get(f"{API_BASE}/{token}/jobs")
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'items' array")

    postings = []
    for job in body["items"]:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        job_id = str(job["id"])
        locations = job.get("locations") or []
        location_names = [
            loc.get("name") for loc in locations if isinstance(loc, dict) and loc.get("name")
        ]
        workplace_types = sorted(
            {
                loc.get("workplaceType")
                for loc in locations
                if isinstance(loc, dict) and loc.get("workplaceType")
            }
        )
        posted_at, comp_quality, comp_summary = _fetch_detail(client, token, job_id)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=job.get("name") or "",
                department_raw=(job.get("department") or {}).get("name"),
                location_raw=", ".join(location_names) or None,
                workplace_type_raw=(
                    workplace_types[0] if len(workplace_types) == 1 else None
                ),
                url=job.get("url"),
                posted_at=posted_at,
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _fetch_detail(
    client: FetchClient, token: str, job_id: str
) -> tuple[datetime | None, CompDataQuality, str | None]:
    detail_result = client.get(f"{API_BASE}/{token}/jobs/{job_id}")
    if not detail_result.ok:
        return None, CompDataQuality.NONE, None
    detail = detail_result.json()
    if not isinstance(detail, dict):
        return None, CompDataQuality.NONE, None
    posted_at = parse_iso_or_epoch_ms(detail.get("createdOn"))
    range_details = detail.get("payRangeDetails")
    if isinstance(range_details, list) and range_details:
        first = range_details[0]
        parts = [
            str(first.get(key))
            for key in ("rangeStart", "rangeEnd", "currency", "frequency")
            if isinstance(first, dict) and first.get(key) is not None
        ]
        return posted_at, CompDataQuality.STRUCTURED, " ".join(parts) or None
    return posted_at, CompDataQuality.NONE, None
