"""
Iteration 5 spike: follow-up for the "found a portfolio page, extracted 0
outbound domains" bucket from iteration 4.

Hypothesis (confirmed by hand on Lowercarbon Capital, see DEVLOG): most of
these aren't client-rendered at all. The portfolio index page links to
per-company DETAIL pages on the VC's own domain (e.g.
lowercarbon.com/company/antora/), and the real external company link only
appears on that detail page, one hop deeper - same shape as SPEC.md 8.1's
apply-redirect handling for Built In, just one layer earlier in the funnel.

This does NOT touch the ~3/25 sampled cases that were genuinely empty
client-rendered SPA shells (near-zero HTML, no server-rendered content at
all) - those need a headless browser (SPEC.md 4 already rejects that
project-wide) or a hand-reversed API per site, neither of which this spike
attempts.

Approach: re-fetch the already-known portfolio_page_url for a sample of
investors from investor_sources.csv, find same-domain "detail page"-shaped
links (path deeper than nav, not a CMS system path, not a generic nav
word, appearing only once on the page - real per-company grid entries
tend to appear once, repeated header/footer nav links don't), fetch a
handful of them, and run the existing outbound-domain extractor on each.

Run: python spikes/iteration5_second_hop_detail_pages.py
"""

import csv
import re
import time
from collections import Counter
from urllib.parse import urljoin, urlparse

import iteration4_vc_portfolio_discovery as base
import tracking_store as ts

SYSTEM_PATH_SUBSTRINGS = (
    "wp-json", "wp-content", "wp-admin", "wp-login", "wp-includes",
    "xmlrpc", "feed", "oembed", "embed", "cdn-cgi", "comment-page",
    "attachment", "wp-sitemap", "sitemap",
)

# Generic nav words that show up as the LAST path segment on nearly every
# site regardless of portfolio content - filtering these out is what's left
# of "is this really a company" after the system-path and asset filters.
GENERIC_NAV_WORDS = {
    "about", "about-us", "team", "our-team", "people", "contact", "contact-us",
    "blog", "news", "press", "media", "portfolio", "companies", "company",
    "careers", "jobs", "privacy", "privacy-policy", "terms", "terms-of-service",
    "cookie-policy", "cookies", "faq", "home", "investors", "approach", "thesis",
    "values", "join", "join-us", "subscribe", "newsletter", "disclosures",
    "legal", "portfolio-companies", "our-portfolio", "our-companies",
    "impact", "esg", "insights", "resources", "events", "sitemap",
    # Found via real false positives on the first 10-investor sample: none of
    # these are per-company detail pages, but each slipped through because it
    # only appears once on its page and isn't a generic nav word.
    "security-warning", "submit-a-deal", "cart", "sustainability",
    "disclosures", "disclaimer", "cookie", "accessibility",
}


def find_detail_page_candidates(page_url: str, html: str, own_root: str, max_candidates: int = 5) -> list[str]:
    hrefs = base.ALL_HREF_PATTERN.findall(html)
    counts = Counter(hrefs)
    candidates = []
    seen = set()
    for href in hrefs:
        if href in seen:
            continue
        seen.add(href)
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if href.lower().split("?")[0].endswith(base.ASSET_EXTENSIONS):
            continue
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if base.registrable_root(absolute) != own_root:
            continue  # only interested in same-domain detail pages
        if any(sysp in absolute.lower() for sysp in SYSTEM_PATH_SUBSTRINGS):
            continue
        path_segments = [s for s in parsed.path.strip("/").split("/") if s]
        if len(path_segments) < 1:
            continue
        last_segment = path_segments[-1].lower()
        if last_segment in GENERIC_NAV_WORDS:
            continue
        # Repeated header/footer nav links show up 2+ times on one page;
        # a real per-company grid entry appears once. Cheap, imperfect, but
        # the signal that separates nav chrome from content links.
        if counts[href] > 1:
            continue
        candidates.append(absolute)
        if len(candidates) >= max_candidates:
            break
    return candidates


def try_second_hop(name: str, website: str, portfolio_url: str) -> dict:
    status, html = base.fetch(portfolio_url)
    if status != 200 or not html:
        return {"investor": name, "result": f"could not re-fetch portfolio page ({status})"}

    own_root = base.registrable_root(website)
    candidates = find_detail_page_candidates(portfolio_url, html, own_root)
    if not candidates:
        return {"investor": name, "result": "no detail-page-shaped links found", "portfolio_url": portfolio_url}

    MAX_DOMAINS_PER_DETAIL_PAGE = 5  # a real per-company page yields ~1 company
    # (occasionally 2-3 alongside press mentions we don't fully filter); a
    # page returning more than this is far more likely a listicle/roundup
    # page than an actual detail page. Found on Congruent Ventures'
    # /50-by-2050-2025, a "50 companies to watch" article that isn't a
    # per-company page at all and produced 60+ domains in one shot.

    all_domains = []
    detail_results = []
    for detail_url in candidates:
        dstatus, dhtml = base.fetch(detail_url)
        if dstatus != 200 or not dhtml:
            detail_results.append({"detail_url": detail_url, "domains": []})
            continue
        domains = base.extract_outbound_domains(detail_url, dhtml, own_root)
        if len(domains) > MAX_DOMAINS_PER_DETAIL_PAGE:
            detail_results.append({
                "detail_url": detail_url,
                "domains": [],
                "note": f"discarded - {len(domains)} domains found, looks like a roundup/listicle page not a company detail page",
            })
            continue
        detail_results.append({"detail_url": detail_url, "domains": domains})
        for d in domains:
            if d not in all_domains:
                all_domains.append(d)

    return {
        "investor": name,
        "portfolio_url": portfolio_url,
        "detail_pages_tried": len(candidates),
        "detail_results": detail_results,
        "unique_domains_found": all_domains,
    }


if __name__ == "__main__":
    with open("investor_sources.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    misses = [
        r for r in rows
        if r["portfolio_page_url"]
        and not r["portfolio_company_count"]
        and r["notes"] == "page found but no outbound company links extracted"
    ]
    print(f"{len(misses)} candidates in this bucket. Running the remaining ones (first 10 already done).\n")

    sample = misses[10:]
    for r in sample:
        result = try_second_hop(r["name"], r["website"], r["portfolio_page_url"])
        print(f"=== {r['name']} ===")
        if "unique_domains_found" in result:
            print(f"  detail pages tried: {result['detail_pages_tried']}")
            for dr in result["detail_results"]:
                print(f"    {dr['detail_url']} -> {dr['domains']}")
            print(f"  unique domains found: {result['unique_domains_found']}")
            if result["unique_domains_found"]:
                for d in result["unique_domains_found"]:
                    ts.upsert_company(d, r["name"], "vc_portfolio_page_detail_hop")
        else:
            print(f"  {result['result']}")
        print()
        time.sleep(0.5)
