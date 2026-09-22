"""
Iteration 3 spike: for each VC in the Sightline investor list, find their own
jobs/careers link from their homepage, then fingerprint what platform it runs
on (Getro, Consider, Kardow, or unknown/other).

This does NOT use Sightline for anything beyond name+website - we already
decided (see DEVLOG 2026-09-2x) that reusing their public investor list as a
discovery seed is fine. Everything from here on is each VC's own public site,
one hop away.

Run: python spikes/iteration3_vc_board_discovery.py
"""

import json
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# Match on the URL PATH itself, not the visible link text - a lot of these
# sites are SPAs where nav text isn't in the raw HTML at all, but an <a href>
# with "/jobs" or "/careers" in it often survives even in a client-rendered
# page's initial markup (e.g. a footer link, or a link Next.js pre-renders).
#
# The keyword must be a whole path SEGMENT (bounded by / or end-of-path or a
# query string), not just a substring - a first version of this matched
# ".../wp-job-manager/assets/dist/css/job-listings.css" as a "jobs" link,
# which is a CSS file, not a page. Found on AgFunder; real bug, not
# hypothetical.
JOB_HREF_PATTERN = re.compile(
    r'href="([^"?#]*/(?:jobs?|careers?|open-positions?|portfolio-?jobs?)(?:/[^"?#]*)?(?:\?[^"]*)?)"',
    re.I,
)
ASSET_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".woff", ".woff2")

FALLBACK_PATHS = ["/jobs", "/careers", "/open-positions", "/portfolio-jobs", "/portfolio-careers"]


def fetch(url: str, timeout: int = 12) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def find_jobs_link(homepage_url: str, html: str) -> str | None:
    matches = JOB_HREF_PATTERN.findall(html)
    for href in matches:
        if href.startswith("mailto:"):
            continue
        if href.lower().split("?")[0].endswith(ASSET_EXTENSIONS):
            continue
        return urljoin(homepage_url, href)
    return None


def registrable_root(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def fallback_candidates(website: str) -> list[str]:
    root = registrable_root(website)
    scheme = urlparse(website).scheme or "https"
    # Subdomain guesses FIRST. A same-domain "/jobs" path is often just a
    # redirect stub pointing at a subdomain-hosted board (Consider in
    # particular seems to like this) - a plain HTTP fetch doesn't follow a
    # client-side JS redirect, so it sees the stub and misreports "unknown."
    # Found via a real regression (360 Capital, Airbus Ventures) after
    # tightening the homepage-link regex to stop matching subdomains.
    candidates = [f"{scheme}://jobs.{root}", f"{scheme}://careers.{root}"]
    candidates += [f"{scheme}://{root}{path}" for path in FALLBACK_PATHS]
    return candidates


def fingerprint(url: str, html: str) -> str:
    if "__NEXT_DATA__" in html and (
        "getro" in html.lower() or re.search(r'"organization"\s*:\s*{', html)
    ):
        return "getro (likely)"
    if "__NEXT_DATA__" in html:
        return "next.js, unconfirmed vendor"
    if "consider.com" in html.lower() or "serverInitialData" in html:
        return "consider"
    if "kardow" in html.lower():
        return "kardow"
    if "greenhouse.io" in html.lower():
        return "greenhouse (direct)"
    if "lever.co" in html.lower():
        return "lever (direct)"
    if "ashbyhq.com" in html.lower():
        return "ashby (direct)"
    if (
        "job_listing" in html
        or "wp-job-manager" in html.lower()
        or "feed=job_feed" in html
    ):
        # WordPress + WP Job Manager plugin. Found via a real example
        # (AgFunder): the plugin exposes an RSS feed of postings, often
        # aggregating PORTFOLIO company jobs, not just the VC's own hires -
        # same shape as Getro/Consider, worth checking per-firm which it is.
        return "wordpress (wp job manager) - check for RSS feed"
    if len(html) < 500:
        return "empty/blocked response"
    return "unknown"


def try_jobs_url(name: str, website: str, jobs_url: str, how_found: str) -> dict | None:
    jstatus, jhtml = fetch(jobs_url)
    if jstatus != 200 or not jhtml or len(jhtml) < 200:
        return None
    return {
        "investor": name,
        "website": website,
        "jobs_url": jobs_url,
        "how_found": how_found,
        "platform": fingerprint(jobs_url, jhtml),
    }


def investigate(name: str, website: str) -> dict:
    status, html = fetch(website)
    if status != 200 or not html:
        return {"investor": name, "website": website, "result": f"homepage fetch failed ({status})"}

    # 1. Try a link found on the homepage itself.
    linked_url = find_jobs_link(website, html)
    if linked_url:
        result = try_jobs_url(name, website, linked_url, "homepage link")
        if result:
            return result

    # 2. Fall back to guessing common paths/subdomains directly.
    for candidate in fallback_candidates(website):
        result = try_jobs_url(name, website, candidate, "path/subdomain guess")
        if result:
            return result

    return {"investor": name, "website": website, "result": "no jobs page found (link or guess)"}


if __name__ == "__main__":
    import sys
    import tracking_store as ts

    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else start + 20

    with open(
        r"C:\Users\o439n\Desktop\First_Look\spikes\sightline_investors_raw.json",
        encoding="utf-8",
    ) as f:
        investors = json.load(f)

    batch = investors[start:end]
    results = []
    for inv in batch:
        r = investigate(inv["name"], inv["website"])
        results.append(r)
        print(json.dumps(r, indent=2))
        ts.upsert_investor({
            "name": inv["name"],
            "website": inv["website"],
            "investor_types": ";".join(inv.get("investor_types") or []),
            "jobs_board_url": r.get("jobs_url", ""),
            "jobs_board_platform": r.get("platform", ""),
            "jobs_board_how_found": r.get("how_found", ""),
            "last_crawled_at": ts.now_iso(),
            "notes": r.get("result", "") if "platform" not in r else "",
        })
        time.sleep(0.5)

    out_path = (
        rf"C:\Users\o439n\Desktop\First_Look\spikes\iteration3_batch_{start}_{end}_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {len(results)} results to {out_path}")
