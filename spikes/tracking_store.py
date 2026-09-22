"""
Shared CSV-based tracking store for the VC-discovery spikes (iteration 3 & 4).

Two files, both plain CSV on purpose - diffable in a text viewer, hand-editable
if a row needs correcting, no schema migration ceremony while the discovery
approach itself is still changing shape every session.

- investor_sources.csv       One row per investor we've checked, via either
                              script. Records what we found and when, so a
                              monthly re-crawl (SPEC.md 8.5's cadence, applied
                              here) can diff against last time instead of
                              starting from zero and re-guessing everything.
- discovered_companies.csv   One row per company domain discovered via any
                              investor. Includes columns for the NEXT step -
                              each company's own careers page and detected ATS
                              - that this spike doesn't populate yet but that
                              a real re-crawl will need. Schema goes in now,
                              the crawl that fills it comes later (same shape
                              as SPEC.md 11.1's observed_at).

Both are upserted (keyed on investor name / company domain), not appended, so
re-running a batch updates existing rows instead of duplicating them.
"""

import csv
import os
from datetime import datetime, timezone

INVESTOR_CSV = os.path.join(os.path.dirname(__file__), "investor_sources.csv")
COMPANY_CSV = os.path.join(os.path.dirname(__file__), "discovered_companies.csv")

INVESTOR_FIELDS = [
    "name", "website", "investor_types",
    "jobs_board_url", "jobs_board_platform", "jobs_board_how_found",
    "portfolio_page_url", "portfolio_extraction_method", "portfolio_company_count",
    "last_crawled_at", "notes",
]

COMPANY_FIELDS = [
    "company_domain", "company_website",
    "discovered_via_investors", "discovery_method",
    "first_discovered_at", "last_seen_at",
    "careers_page_url", "ats_provider", "ats_token", "last_checked_at", "notes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: str, fields: list[str]) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        key_field = fields[0]
        return {row[key_field]: row for row in reader}


def _write(path: str, fields: list[str], rows_by_key: dict) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows_by_key.values():
            writer.writerow({k: row.get(k, "") for k in fields})


def upsert_investor(row: dict) -> None:
    """row must include 'name'. Any field not given is left as-is (or blank
    for a brand-new row) rather than overwritten - a jobs-board-only run
    shouldn't blank out portfolio-page columns filled in by the other script,
    and vice versa."""
    rows = _read(INVESTOR_CSV, INVESTOR_FIELDS)
    existing = rows.get(row["name"], {})
    for k, v in row.items():
        if v is not None and v != "":
            existing[k] = v
    existing.setdefault("name", row["name"])
    rows[row["name"]] = existing
    _write(INVESTOR_CSV, INVESTOR_FIELDS, rows)


def upsert_company(domain: str, investor_name: str, discovery_method: str) -> None:
    ts = now_iso()
    rows = _read(COMPANY_CSV, COMPANY_FIELDS)
    existing = rows.get(domain)
    if existing:
        via = set(filter(None, existing.get("discovered_via_investors", "").split(";")))
        via.add(investor_name)
        existing["discovered_via_investors"] = ";".join(sorted(via))
        existing["last_seen_at"] = ts
    else:
        existing = {
            "company_domain": domain,
            "company_website": f"https://{domain}",
            "discovered_via_investors": investor_name,
            "discovery_method": discovery_method,
            "first_discovered_at": ts,
            "last_seen_at": ts,
            "careers_page_url": "",
            "ats_provider": "",
            "ats_token": "",
            "last_checked_at": "",
            "notes": "",
        }
    rows[domain] = existing
    _write(COMPANY_CSV, COMPANY_FIELDS, rows)
