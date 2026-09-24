"""BambooHR adapter. SPEC.md §9: no authoritative documentation of any kind
(same bucket as Lever v0/Getro) — this is an internal endpoint powering
BambooHR's own careers-page widget, shape reported to change between
BambooHR releases without notice.

Confirmed live 2026-09-24: the list endpoint has no per-job URL and no date
field at all. The URL is constructed from the known
{token}.bamboohr.com/careers/{id} pattern (confirmed live, 200). posted_at
is always None — there is no field to read it from, and no comp field was
observed either, so comp_data_quality is always NONE.

Also confirmed live: an invalid subdomain does not 404 — it 302-redirects to
the www.bamboohr.com marketing homepage, which is itself 200 HTML.
src.http.FetchClient follows that redirect, so this adapter never sees a 404
for a bad token; the "unexpected shape" branch below is what actually
catches it.
"""

from src.ats_common import AdapterResult, as_dict
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://{token}.bamboohr.com/careers/list"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("result"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'result' array")

    postings = []
    for job in body["result"]:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        job_id = str(job["id"])
        location = as_dict(job.get("location"))
        location_parts = [location.get("city"), location.get("state")]
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=job.get("jobOpeningName") or "",
                department_raw=job.get("departmentLabel"),
                location_raw=", ".join(p for p in location_parts if p) or None,
                workplace_type_raw="remote" if job.get("isRemote") is True else None,
                url=f"https://{token}.bamboohr.com/careers/{job_id}",
                posted_at=None,
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
