"""
Iteration 4 spike: instead of looking for a shared jobs-board platform on a
VC's own site (iteration 3), look for the VC's "Portfolio" / "Companies" page
and extract outbound links to each portfolio company's own site.

Motivation (see DEVLOG): hand-checking iteration 3's misses showed several
VCs have no shared jobs board at all (Aligned Climate Capital, American
Century, American Family Insurance all just show the fund/company's OWN
hiring, not portfolio companies) - but almost every VC site has a marketing
"portfolio" page listing their companies, independent of whether they run any
job-board infra. That's structurally the same as SPEC.md 7.1's manual
watchlist (name + domain), just VC-sourced. This spike checks whether that
approach has a better hit rate than iteration 3's shared-board search.

This is a rough heuristic for a spike, not production dedupe/cleanup:
outbound links are bucketed by registrable domain and obvious junk (social
media, the VC's own domain, common SaaS/CDN domains) is filtered out. No
attempt yet to get company NAMES cleanly - domains are the signal being
tested here.

Run: python spikes/iteration4_vc_portfolio_discovery.py
"""

import json
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

PORTFOLIO_HREF_PATTERN = re.compile(
    r'href="([^"?#]*/(?:portfolio|our-portfolio|companies|our-companies|portfolio-companies)(?:/[^"?#]*)?(?:\?[^"]*)?)"',
    re.I,
)
ASSET_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".woff", ".woff2", ".pdf")

FALLBACK_PATHS = ["/portfolio", "/our-portfolio", "/companies", "/our-companies", "/portfolio-companies"]

# Domains that show up as noise on almost every site and are never a
# portfolio company: social/media, common SaaS embeds, the discovery seed
# itself, generic infra.
JUNK_DOMAIN_SUBSTRINGS = (
    "twitter.com", "x.com", "linkedin.com", "licdn.com", "lnkd.in", "facebook.com",
    "instagram.com", "youtube.com", "youtu.be", "medium.com", "substack.com",
    "crunchbase.com", "sightlineclimate.com", "google.com", "goo.gl", "bing.com",
    "apple.com", "wordpress.com", "wp.com", "vimeo.com", "typeform.com",
    "mailchimp.com", "list-manage.com", "hubspot.com", "cloudflare.com",
    "googleapis.com", "gstatic.com", "fontawesome.com", "cookiebot.com",
    "calendly.com", "docsend.com", "squarespace.com", "squarespace-cdn.com",
    "typekit.net", "website-files.com", "webflow.io", "wixstatic.com", "wix.com",
    "gmpg.org", "wpengine.com", "jsdelivr.net", "threads.net", "bit.ly",
    "tinyurl.com", "tiktok.com", "pinterest.com",
    # E-commerce/site-builder infra, found on Avaana Capital (Shopify-hosted site)
    "shopify.com", "shopifycdn.com", "shopifysvc.com", "google-analytics.com",
    "googletagmanager.com",
    # Fund-admin/investor-reporting SaaS embedded in portfolio pages - not
    # portfolio companies. Found on Azolla Ventures (fundpanel.io) and Axon
    # Partners Group (efrontcloud.com).
    "fundpanel.io", "efrontcloud.com", "dynamosoftware.com",
)


def fetch(url: str, timeout: int = 12) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def registrable_root(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def find_portfolio_link(homepage_url: str, html: str, own_root: str) -> str | None:
    matches = PORTFOLIO_HREF_PATTERN.findall(html)
    for href in matches:
        if href.startswith("mailto:"):
            continue
        if href.lower().split("?")[0].endswith(ASSET_EXTENSIONS):
            continue
        absolute = urljoin(homepage_url, href)
        # A "/companies" or "/portfolio" match is only useful if it stays on
        # the VC's own site. Found via a real bug: American Family Insurance's
        # homepage links to https://www.linkedin.com/companies/... which
        # matches the regex but points at LinkedIn, not their own portfolio
        # page - we then extracted LinkedIn's own subdomains as if they were
        # portfolio companies.
        if registrable_root(absolute) != own_root:
            continue
        return absolute
    return None


def fallback_candidates(website: str) -> list[str]:
    root = registrable_root(website)
    scheme = urlparse(website).scheme or "https"
    return [f"{scheme}://{root}{path}" for path in FALLBACK_PATHS]


ALL_HREF_PATTERN = re.compile(r'href="([^"#]+)"', re.I)


def extract_outbound_domains(page_url: str, html: str, own_root: str) -> list[str]:
    hrefs = ALL_HREF_PATTERN.findall(html)
    domains = []
    seen = set()
    for href in hrefs:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if href.lower().split("?")[0].endswith(ASSET_EXTENSIONS):
            continue
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        root = registrable_root(absolute)
        if not root or root == own_root or root.endswith("." + own_root):
            continue
        if any(junk in root for junk in JUNK_DOMAIN_SUBSTRINGS):
            continue
        if root not in seen:
            seen.add(root)
            domains.append(root)
    return domains


def investigate(name: str, website: str) -> dict:
    status, html = fetch(website)
    if status != 200 or not html:
        return {"investor": name, "website": website, "result": f"homepage fetch failed ({status})"}

    own_root = registrable_root(website)

    linked_url = find_portfolio_link(website, html, own_root)
    candidates = ([linked_url] if linked_url else []) + fallback_candidates(website)

    tried = []
    for candidate in candidates:
        if candidate in tried:
            continue
        tried.append(candidate)
        pstatus, phtml = fetch(candidate)
        if pstatus != 200 or not phtml or len(phtml) < 200:
            continue
        domains = extract_outbound_domains(candidate, phtml, own_root)
        how = "homepage link" if candidate == linked_url else "path guess"
        if domains:
            return {
                "investor": name,
                "website": website,
                "portfolio_url": candidate,
                "how_found": how,
                "outbound_company_domain_count": len(domains),
                "sample_domains": domains[:15],
                "all_domains": domains,
            }
        else:
            # Page loaded but looks JS-rendered / no plain <a> links found -
            # note this distinctly from "no page found at all".
            note = "next.js / client-rendered (no __NEXT_DATA__ parse attempted)" if "__NEXT_DATA__" in phtml else "page found but no outbound company links extracted"
            return {
                "investor": name,
                "website": website,
                "portfolio_url": candidate,
                "how_found": how,
                "result": note,
            }

    return {"investor": name, "website": website, "result": "no portfolio page found (link or guess)"}


if __name__ == "__main__":
    import sys
    import tracking_store as ts

    start = int(sys.argv[1]) if len(sys.argv) > 1 else 40
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
        print(json.dumps({k: v for k, v in r.items() if k != "all_domains"}, indent=2))
        ts.upsert_investor({
            "name": inv["name"],
            "website": inv["website"],
            "investor_types": ";".join(inv.get("investor_types") or []),
            "portfolio_page_url": r.get("portfolio_url", ""),
            "portfolio_extraction_method": r.get("how_found", ""),
            "portfolio_company_count": r.get("outbound_company_domain_count", ""),
            "last_crawled_at": ts.now_iso(),
            "notes": r.get("result", "") if "outbound_company_domain_count" not in r else "",
        })
        for domain in r.get("all_domains", []):
            ts.upsert_company(domain, inv["name"], "vc_portfolio_page")
        time.sleep(0.5)

    out_path = (
        rf"C:\Users\o439n\Desktop\First_Look\spikes\iteration4_batch_{start}_{end}_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {len(results)} results to {out_path}")
