"""
Iteration 2 spike, part A: Getro.

SPEC.md §7.2 says Getro is a *company source only* now (no postings path - see
SPEC-REVISION-01 §R0). So unlike the iteration-1 ATS spike, this doesn't parse
"postings we'd store" - it parses "companies we'd discover", which is what
Getro is actually used for in the current design.

Confirmed live: https://breakthroughenergy.getro.com/jobs is a real,
classic-Next.js Getro board with the `__NEXT_DATA__` script tag SPEC.md
assumed. (A second candidate, jobs.a16z.com, turned out to be Next.js App
Router with a streamed RSC payload instead of `__NEXT_DATA__` - so the shape
does drift between boards, exactly as SPEC.md §7.2 warned. Worth re-checking
each real board in config/getro_boards.yml individually rather than assuming
one shape fits all.)

Run: python spikes/iteration2_getro_spike.py
"""

import json
import re
import urllib.request
from urllib.parse import urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def extract_next_data(html: str) -> dict:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    if not m:
        raise ValueError(
            "No __NEXT_DATA__ script tag found - this board uses a different "
            "Next.js rendering mode (e.g. App Router streaming). Shape needs "
            "re-verifying per-board, per SPEC.md §7.2."
        )
    return json.loads(m.group(1))


def parse_getro_companies(board_url: str, limit: int = 5) -> list[dict]:
    html = fetch_html(board_url)
    data = extract_next_data(html)
    jobs = data["props"]["pageProps"]["initialState"]["jobs"]["found"]

    seen_ids = set()
    parsed = []
    for job in jobs:
        org = job["organization"]
        if org["id"] in seen_ids:
            continue
        seen_ids.add(org["id"])

        # Getro doesn't expose the company's own domain directly - only a
        # slug, plus each job's external application URL, which is often an
        # ATS subdomain (e.g. renewco2.breezy.hr), NOT the company's own
        # domain (presumably renewco2.com). canonical_domain dedupe (SPEC.md
        # §6) would need a real domain, so this is a concrete gap: Getro
        # needs its own resolution hop, same shape as the Wellfound
        # slug->domain hop SPEC.md §7.7 already budgets for. Not currently
        # spec'd for Getro - worth flagging back to SPEC.md if this holds up
        # across more boards.
        job_url_host = urlparse(job.get("url", "")).netloc or None

        parsed.append(
            {
                "source": "getro",
                "name": org["name"],
                "slug": org.get("slug"),
                "org_id": org["id"],
                "industry_tags": org.get("industryTags"),
                "head_count": org.get("headCount"),
                "stage": org.get("stage"),
                "sample_job_url_host": job_url_host,  # NOT a confirmed domain
            }
        )
        if len(parsed) >= limit:
            break
    return parsed


if __name__ == "__main__":
    companies = parse_getro_companies("https://breakthroughenergy.getro.com/jobs")
    print(json.dumps(companies, indent=2))
