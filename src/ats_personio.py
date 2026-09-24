"""Personio adapter. SPEC.md §9:
support.personio.de "Overview of the Personio Recruiting API" documents this
public XML feed as an officially sanctioned feature — unlike every other new
M2 provider, this is not a reverse-engineered endpoint.

Confirmed live 2026-09-24 to be genuinely inconsistent across tenants: some
200+XML, some 404, some redirect. The TLD varies per tenant (.com and .de
both seen live) — this adapter takes the full working `host`, not a bare
token, so the caller (M3's mapping cascade) is the one that resolved which
TLD works.

The XML root element is <workzag-jobs> (Personio's product was formerly
"Workzag"). Per-position <salaryInformation> (min/max/currencyCode/type) is
real structured comp, confirmed live — richer than any of the other 4 new
providers. Uses the stdlib xml.etree.ElementTree; a malformed or non-XML body
is caught by ParseError and returned as a classified failure, never raised.
"""

import xml.etree.ElementTree as ET

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, host: str) -> AdapterResult:
    url = f"https://{host}/xml?language=en"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    try:
        root = ET.fromstring(result.body)
    except (ET.ParseError, LookupError, ValueError) as exc:
        # LookupError: an <?xml encoding="..."?> declaration naming an
        # encoding Python doesn't recognize -- confirmed live 2026-09-24,
        # ET.fromstring raises this instead of ParseError for that case.
        return AdapterResult(ok=False, error=f"not valid XML: {exc}")

    if root.tag != "workzag-jobs":
        return AdapterResult(
            ok=False, error=f"unexpected root element {root.tag!r}, expected workzag-jobs"
        )

    postings = []
    for position in root.findall("position"):
        job_id = _text(position, "id")
        title = _text(position, "name")
        if not job_id or not title:
            continue
        office_parts = [_text(position, "office")]
        comp_quality, comp_summary = _comp(position)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=title,
                department_raw=_text(position, "department"),
                location_raw=", ".join(p for p in office_parts if p) or None,
                url=f"https://{host}/job/{job_id}",
                posted_at=parse_iso_or_epoch_ms(_text(position, "createdAt")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _text(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _comp(position: ET.Element) -> tuple[CompDataQuality, str | None]:
    salary = position.find("salaryInformation")
    if salary is None:
        return CompDataQuality.NONE, None
    parts = [
        _text(salary, key) for key in ("min", "max", "currencyCode", "type") if _text(salary, key)
    ]
    if parts:
        return CompDataQuality.STRUCTURED, " ".join(parts)
    return CompDataQuality.NONE, None
