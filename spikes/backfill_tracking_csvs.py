"""
One-time backfill: populate investor_sources.csv / discovered_companies.csv
from the JSON result files already produced by iteration3/iteration4 before
tracking_store.py existed. Going forward, both scripts write to the CSVs
directly - this script only needs to run once.
"""

import json
import tracking_store as ts

with open("sightline_investors_raw.json", encoding="utf-8") as f:
    investors_by_name = {inv["name"]: inv for inv in json.load(f)}


def investor_types_for(name: str) -> str:
    inv = investors_by_name.get(name)
    return ";".join(inv.get("investor_types") or []) if inv else ""


# --- iteration 3 (jobs-board discovery) result files ---
for path in ["iteration3_batch1_results_v2.json", "iteration3_batch_20_40_results.json"]:
    with open(path, encoding="utf-8") as f:
        for r in json.load(f):
            ts.upsert_investor({
                "name": r["investor"],
                "website": r["website"],
                "investor_types": investor_types_for(r["investor"]),
                "jobs_board_url": r.get("jobs_url", ""),
                "jobs_board_platform": r.get("platform", ""),
                "jobs_board_how_found": r.get("how_found", ""),
                "last_crawled_at": "2026-09-20/21 (backfilled, exact time not recorded)",
                "notes": r.get("result", "") if "platform" not in r else "",
            })

# --- iteration 4 (portfolio-page discovery) result file ---
with open("iteration4_batch_40_60_results.json", encoding="utf-8") as f:
    for r in json.load(f):
        ts.upsert_investor({
            "name": r["investor"],
            "website": r["website"],
            "investor_types": investor_types_for(r["investor"]),
            "portfolio_page_url": r.get("portfolio_url", ""),
            "portfolio_extraction_method": r.get("how_found", ""),
            "portfolio_company_count": r.get("outbound_company_domain_count", ""),
            "last_crawled_at": "2026-09-21 (backfilled, exact time not recorded)",
            "notes": r.get("result", "") if "outbound_company_domain_count" not in r else "",
        })
        for domain in r.get("all_domains", r.get("sample_domains", [])):
            ts.upsert_company(domain, r["investor"], "vc_portfolio_page")

print("Backfill done.")
print(f"  investor_sources.csv rows: {len(ts._read(ts.INVESTOR_CSV, ts.INVESTOR_FIELDS))}")
print(f"  discovered_companies.csv rows: {len(ts._read(ts.COMPANY_CSV, ts.COMPANY_FIELDS))}")
