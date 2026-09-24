"""Rippling adapter. SPEC.md §9:
developer.rippling.com/documentation/job-board-api documents `v1`, which
requires a paid Recruiting Pro subscription and an API key. The `v2`
endpoint used here is undocumented, public, and unauthenticated — the same
endpoint Rippling's own embed widget and hosted careers page call, confirmed
live against 62 companies (spikes/iteration11_rippling_spike.py).

Unlike Greenhouse, the per-job detail call is NOT redundant: createdOn and
structured payRangeDetails exist only there. A failed detail call degrades
that one posting (posted_at/comp stay None/NONE, counted in
`AdapterResult.degraded_count`) rather than dropping the whole company —
"a known gap beats invisible bad data" (SPEC.md §3.8). Token resolution
from a careers page is M3's mapping-cascade job, not this adapter's — this
takes an already-known token.

Paginated: `totalPages` in the list response is followed until exhausted
(confirmed live 2026-09-24 that real boards exceed the 20-item pageSize —
`spikes/iteration11_rippling_full_results.json` has boards with 33-112
postings). Fixed at a defensive `MAX_PAGES` cap rather than trusting
`totalPages` unconditionally.
"""

from datetime import datetime

from src.ats_common import AdapterResult, as_dict, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting

API_BASE = "https://api.rippling.com/platform/api/ats/v2/board"

# Defensive only: real boards top out in the low hundreds of postings
# (spikes/iteration11_rippling_full_results.json), so 50 pages (1,000
# postings at pageSize 20) is far beyond anything observed. A cap avoids an
# unbounded loop if a future response ever reports totalPages incorrectly.
MAX_PAGES = 50


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    items = []
    page = 0
    total_pages = 1
    while page < total_pages and page < MAX_PAGES:
        url = f"{API_BASE}/{token}/jobs" + (f"?page={page}" if page else "")
        result = client.get(url)
        if not result.ok:
            return AdapterResult(
                ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
            )
        body = result.json()
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            return AdapterResult(ok=False, error="unexpected shape: no 'items' array")
        items.extend(body["items"])
        total_pages = body.get("totalPages") if isinstance(body.get("totalPages"), int) else 1
        page += 1

    postings = []
    degraded_count = 0
    for job in items:
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
        posted_at, comp_quality, comp_summary, detail_ok = _fetch_detail(client, token, job_id)
        if not detail_ok:
            degraded_count += 1
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=job.get("name") or "",
                department_raw=as_dict(job.get("department")).get("name"),
                location_raw=", ".join(location_names) or None,
                workplace_type_raw=(workplace_types[0] if len(workplace_types) == 1 else None),
                url=job.get("url"),
                posted_at=posted_at,
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings), degraded_count=degraded_count)


def _fetch_detail(
    client: FetchClient, token: str, job_id: str
) -> tuple[datetime | None, CompDataQuality, str | None, bool]:
    """Returns (posted_at, comp_quality, comp_summary, ok).

    `ok` is False whenever the detail call itself failed or returned an
    unusable shape — the caller counts that in `degraded_count` so a
    posting silently losing its date/comp stays visible, not silent
    (SPEC.md §3.8).
    """
    detail_result = client.get(f"{API_BASE}/{token}/jobs/{job_id}")
    if not detail_result.ok:
        return None, CompDataQuality.NONE, None, False
    detail = detail_result.json()
    if not isinstance(detail, dict):
        return None, CompDataQuality.NONE, None, False
    posted_at = parse_iso_or_epoch_ms(detail.get("createdOn"))
    range_details = detail.get("payRangeDetails")
    if isinstance(range_details, list) and range_details and isinstance(range_details[0], dict):
        first = range_details[0]
        parts = [
            str(first.get(key))
            for key in ("rangeStart", "rangeEnd", "currency", "frequency")
            if first.get(key) is not None
        ]
        return posted_at, CompDataQuality.STRUCTURED, " ".join(parts) or None, True
    return posted_at, CompDataQuality.NONE, None, True
