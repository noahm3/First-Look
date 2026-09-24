"""
Iteration 15 spike: what would a real Consider adapter need? (SPEC.md §7.6,
SPEC.md §18 item #4 -- deferred behind the measurement gate, not scheduled).

Extends spikes/iteration2_consider_spike.py (which confirmed the flow against
one board, Greentown Labs) two ways:

1. Re-verifies the flow still works live today, and checks whether it holds
   across boards beyond the one already confirmed -- same "don't trust one
   board" discipline SPEC.md §7.2 already applies to Getro.
2. Confirms the `meta.sequence` cursor actually pages through results (Consider
   never documented this -- same "no authoritative docs" bucket as Getro and
   Lever v0), so a real adapter could discover every company on a board, not
   just the first page.

Run: python spikes/iteration15_consider_spike.py
"""

import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# Candidates from spikes/investor_sources.csv's "consider" / "consider (likely)"
# fingerprint column (spikes/iteration3_vc_board_discovery.py). Not all of them
# are real -- that fingerprint is a heuristic guess, same caveat as Getro's
# "getro (likely)" column. One (SOSV) 404s below, confirming the caveat.
CANDIDATE_BOARDS = [
    ("Greentown Labs", "https://jobs.greentownlabs.com/jobs"),
    ("Congruent Ventures", "https://jobs.congruentvc.com/jobs"),
    ("Bessemer Venture Partners", "https://jobs.bvp.com/jobs"),
    ("MCJ Collective", "https://jobs.mcj.vc/jobs"),
    ("SOSV", "https://techjobs.sosv.com/jobs"),
]

# Consider's own derived/inferred output -- never store or surface these
# (SPEC.md §3.6: no classifiers; §4: no scoring/ranking). Reaffirmed present on
# every job record fetched today, same set spikes/iteration2_consider_spike.py
# already flagged.
CONSIDER_DERIVED_FIELDS_TO_IGNORE = {
    "scores",
    "skills",
    "requiredSkills",
    "preferredSkills",
    "considerLevels",
    "matchingTalent",
}


def get_session_and_csrf(jobs_page_url: str, jar: http.cookiejar.CookieJar):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(jobs_page_url, headers={"User-Agent": UA})
    with opener.open(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    match = re.search(r"window\.serverInitialData\s*=\s*(\{.*?\})\s*;", html, re.S)
    if match is None:
        raise ValueError("no window.serverInitialData found -- not a Consider board (or shape drifted)")
    data = json.loads(match.group(1))
    return data["csrfToken"], data["board"]["id"], opener


def search_jobs(opener, jobs_page_url: str, csrf_token: str, board_id: str, *, size: int, sequence: str | None = None) -> dict:
    parsed = urllib.parse.urlparse(jobs_page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    meta: dict = {"size": size}
    if sequence:
        meta["sequence"] = sequence
    body = json.dumps(
        {"meta": meta, "board": {"id": board_id, "isParent": True}, "query": {"promoteFeatured": True}}
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


def probe_board(name: str, url: str) -> None:
    jar = http.cookiejar.CookieJar()
    try:
        csrf, board_id, opener = get_session_and_csrf(url, jar)
    except (urllib.error.HTTPError, ValueError) as exc:
        print(f"{name:30} {url:45} FAILED at session step: {exc}")
        return

    try:
        result = search_jobs(opener, url, csrf, board_id, size=10)
    except urllib.error.HTTPError as exc:
        print(f"{name:30} {url:45} board_id={board_id!r} FAILED at search: HTTP {exc.code}")
        return

    jobs = result.get("jobs", [])
    total = result.get("total")
    with_domain = sum(1 for j in jobs if j.get("companyDomain"))
    print(
        f"{name:30} {url:45} OK: board_id={board_id!r} total_jobs={total} "
        f"sample={len(jobs)} with_domain={with_domain}/{len(jobs)}"
    )


def probe_pagination(name: str, url: str, *, page_size: int = 50, pages: int = 3) -> None:
    """Walk `pages` pages of `page_size` each via the meta.sequence cursor.

    Checks two different things, deliberately kept separate: whether the
    cursor ever repeats the same *job* (a real pagination bug, would mean
    duplicate rows), versus the same *company* reappearing across pages
    (expected and correct -- a company with several open roles has its jobs
    spread across the ranked result set, not necessarily on one page).
    Conflating these two in an earlier version of this script briefly read as
    a pagination bug that wasn't one -- worth keeping distinct."""
    jar = http.cookiejar.CookieJar()
    csrf, board_id, opener = get_session_and_csrf(url, jar)

    seen_job_ids: set[str] = set()
    seen_slugs: set[str] = set()
    sequence = None
    for page in range(1, pages + 1):
        result = search_jobs(opener, url, csrf, board_id, size=page_size, sequence=sequence)
        jobs = result.get("jobs", [])
        job_ids = {j.get("jobId") for j in jobs if j.get("jobId")}
        slugs = {j.get("companySlug") for j in jobs if j.get("companySlug")}
        duplicate_jobs = job_ids & seen_job_ids
        print(
            f"  page {page}: {len(jobs)} jobs, {len(slugs)} distinct company slugs, "
            f"duplicate jobIds vs prior pages: {len(duplicate_jobs)} "
            f"(company reappearances: {len(slugs & seen_slugs)}, expected/fine)"
        )
        seen_job_ids |= job_ids
        seen_slugs |= slugs
        sequence = result.get("meta", {}).get("sequence")
        if not sequence or not jobs:
            print("  (no further sequence cursor / no more jobs -- stopping)")
            break
    print(f"  distinct companies seen across {pages} pages: {len(seen_slugs)}")


if __name__ == "__main__":
    print("=== board shape check ===")
    for name, url in CANDIDATE_BOARDS:
        probe_board(name, url)

    print("\n=== pagination check (Greentown Labs, 3 pages of 50) ===")
    probe_pagination("Greentown Labs", "https://jobs.greentownlabs.com/jobs")
