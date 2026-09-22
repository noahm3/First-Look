"""
Iteration 2 spike, part B (completed): Consider.

The endpoint and payload shape here came from the user's own browser devtools
session against https://jobs.greentownlabs.com/jobs - not guessed. This script
just confirms the flow is reproducible headlessly: load the page once to get a
session cookie + CSRF token pair, then POST the real search-jobs request.

Flow, confirmed real:
1. GET the board's /jobs page. It embeds `window.serverInitialData`, which
   contains a `csrfToken` scoped to the session cookie the same response set.
2. POST to /api-boards/search-jobs with that cookie jar and the token as
   `x-csrf-token`, body: {"meta": {"size": N}, "board": {"id": "<slug>",
   "isParent": true}, "query": {...filters...}}.

Run: python spikes/iteration2_consider_spike.py
"""

import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# Fields Consider returns that are its OWN inferred/derived output, not the
# employer's raw posting - never store or surface these per SPEC.md §3.6 (no
# classifiers) and §4 (no scoring field, no ranking score). Listed here so
# nobody copies them into src/ later without noticing what they are.
CONSIDER_DERIVED_FIELDS_TO_IGNORE = {
    "scores",  # proprietary relevance/match/age/richness scoring
    "skills",
    "requiredSkills",
    "preferredSkills",  # resume-matching tags, inferred, not employer-supplied
    "considerLevels",  # inferred seniority-level ranges
    "matchingTalent",  # Consider's own talent-matching feature
}


def get_session_and_csrf(jobs_page_url: str, cookie_jar: http.cookiejar.CookieJar):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    req = urllib.request.Request(jobs_page_url, headers={"User-Agent": UA})
    with opener.open(req, timeout=15) as resp:
        html = resp.read().decode("utf-8")
    m = re.search(r"window\.serverInitialData\s*=\s*(\{.*?\})\s*;", html, re.S)
    data = json.loads(m.group(1))
    return data["csrfToken"], data["board"]["id"], opener


def search_jobs(opener, jobs_page_url: str, csrf_token: str, board_id: str, size: int = 5) -> dict:
    parsed = urllib.parse.urlparse(jobs_page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    body = json.dumps(
        {
            "meta": {"size": size},
            "board": {"id": board_id, "isParent": True},
            "query": {"promoteFeatured": True},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{origin}/api-boards/search-jobs",
        data=body,
        method="POST",
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": origin,
            "Referer": jobs_page_url,
            "x-csrf-token": csrf_token,
        },
    )
    with opener.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_for_storage(job: dict) -> dict:
    """Only the fields that match what SPEC.md §6/§7 would actually want -
    i.e. company-discovery fields, since Consider is company-source only
    (SPEC.md §4/§7.6), same rule as Getro."""
    return {
        "source": "consider",
        "company_name": job.get("companyName"),
        "company_domain": job.get("companyDomain"),  # <- the exact gap
        # flagged for Getro (spikes/iteration2_getro_spike.py) - Consider
        # gives this for free, no resolution hop needed.
        "company_slug": job.get("companySlug"),
        "company_staff_count": job.get("companyStaffCount"),
        "markets": [m["label"] for m in job.get("markets", [])],
        # Included for interest, NOT to be stored/used as postings per §3.10 -
        # Consider is discovery-only, monitoring stays on the employer's ATS:
        "sample_job_title": job.get("title"),
        "sample_apply_url": job.get("applyUrl"),
        "sample_remote_flag": job.get("remote"),
    }


if __name__ == "__main__":
    JOBS_PAGE = "https://jobs.greentownlabs.com/jobs"
    jar = http.cookiejar.CookieJar()
    csrf_token, board_id, opener = get_session_and_csrf(JOBS_PAGE, jar)
    print(f"got csrf token: {csrf_token[:12]}...  board id: {board_id}")

    result = search_jobs(opener, JOBS_PAGE, csrf_token, board_id, size=5)
    jobs = result.get("jobs", [])
    print(f"\nfetched {len(jobs)} jobs\n")
    for job in jobs:
        print(json.dumps(parse_for_storage(job), indent=2))
