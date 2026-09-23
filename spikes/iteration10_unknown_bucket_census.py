"""
Census of the `unknown` bucket: what ATS or hiring pathway is each of those
careers pages actually using?

`unknown` (1,176 rows, 39.7% of failures) and `unsupported_ats:*` (297 rows,
8.1%) are DISJOINT. Both mean "we fetched the company's careers page";
`unsupported_ats` means a known-but-unsupported platform fingerprint matched,
`unknown` means nothing matched at all. So the unknown bucket is the
unexplored four-fifths, and it is the input `SPEC.md` §8.4 wants: "the
distribution IS the answer to 'should we build more adapters'."

The method matters. Every previous pass at this matched a hand-written list
of platforms, which can only ever find platforms someone already thought of -
and one such probe overstated the recoverable share badly because its regex
was looser than the real fingerprints. This does the opposite: it extracts
EVERY third-party host referenced by each careers page, drops the ones that
are obviously not recruiting infrastructure, and ranks what is left by how
many distinct companies reference it. Platforms surface by frequency instead
of by guess, and a platform nobody here has heard of ranks itself.

It also records the hiring PATHWAY, because not every answer is an ATS: a
WordPress job plugin, JobPosting structured data on the company's own domain,
an iframe embed, a JS-rendered board, or a plain mailto are all real answers
and each implies different work.

Read-only. Writes nothing to discovered_companies.csv.
"""

import argparse
import collections
import csv
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "discovered_companies.csv")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

HOST_RE = re.compile(r"""https?://([a-z0-9][a-z0-9.\-]{2,})""", re.I)
IFRAME_RE = re.compile(r"<iframe[^>]+src=[\"']https?://([a-z0-9][a-z0-9.\-]+)", re.I)
JSONLD_JOB_RE = re.compile(r'"@type"\s*:\s*"JobPosting"', re.I)
WP_RE = re.compile(r"wp-job-manager|job_listing|wpjobboard|wp-content/plugins/[^\"']*job", re.I)
MAILTO_RE = re.compile(r"mailto:[^\"'>]+", re.I)
APPLY_RE = re.compile(r"""href=["'][^"']*(?:apply|/job|/position|/vacanc)""", re.I)

# Hosts that are never recruiting infrastructure. Dropping these is what makes
# the remaining tally readable; everything not listed here survives, so a new
# platform cannot be filtered out by accident.
NOISE = re.compile(
    r"(google|gstatic|googleapis|googletagmanager|doubleclick|facebook|fbcdn|"
    r"twitter|x\.com|linkedin\.com|instagram|youtube|youtu\.be|vimeo|tiktok|"
    r"cloudflare|cloudfront|akamai|fastly|jsdelivr|unpkg|bootstrapcdn|"
    r"fontawesome|typekit|adobe|w3\.org|schema\.org|wordpress\.org|gravatar|"
    r"hubspot|hs-scripts|marketo|segment|sentry|newrelic|datadog|hotjar|"
    r"intercom|drift|zendesk|mailchimp|klaviyo|stripe|paypal|apple\.com|"
    r"microsoft|office\.com|bing|yandex|baidu|wix|squarespace|shopify|"
    r"amazonaws|azureedge|githubusercontent|github\.com|medium\.com|"
    r"substack|calendly|zoom\.us|slack\.com|notion\.so|airtable|typeform|"
    r"crunchbase|bloomberg|reuters|techcrunch|forbes|wsj|nytimes)", re.I)

_last = 0.0


def fetch(url, interval, timeout=15):
    global _last
    gap = interval - (time.monotonic() - _last)
    if gap > 0:
        time.sleep(gap)
    _last = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(600_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


def own_domain_parts(domain):
    return set(p for p in domain.lower().split(".") if len(p) > 3)


def pathway(html, hosts):
    """What is this page actually doing to list jobs?"""
    if WP_RE.search(html):
        return "wordpress job plugin"
    if JSONLD_JOB_RE.search(html):
        return "JobPosting structured data on own site"
    if hosts:
        return "third-party host referenced"
    if APPLY_RE.search(html):
        return "own-site apply links, no third party"
    if MAILTO_RE.search(html):
        return "mailto only"
    return "nothing job-like in raw HTML (likely JS-rendered)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=250)
    ap.add_argument("--interval", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=20260922)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pool = [r for r in rows
            if r["mapping_failure_reason"] == "unknown" and r["careers_page_url"]]
    sample = random.Random(args.seed).sample(pool, min(args.sample, len(pool)))
    print(f"unknown bucket: {len(pool)} rows with a careers page; "
          f"sampling {len(sample)}\n")

    host_companies = collections.defaultdict(set)
    pathways = collections.Counter()
    fetch_fail = collections.Counter()
    per_company = []

    for i, r in enumerate(sample, 1):
        domain = r["company_domain"]
        status, html = fetch(r["careers_page_url"], args.interval)
        if status != 200 or not html:
            fetch_fail[status] += 1
            continue
        own = own_domain_parts(domain)
        hosts = set()
        for h in HOST_RE.findall(html) + IFRAME_RE.findall(html):
            h = h.lower().rstrip(".")
            if NOISE.search(h):
                continue
            if any(p in h for p in own):
                continue
            hosts.add(".".join(h.split(".")[-3:]) if h.count(".") > 2 else h)
        for h in hosts:
            host_companies[h].add(domain)
        p = pathway(html, hosts)
        pathways[p] += 1
        per_company.append({"domain": domain, "pathway": p,
                            "hosts": sorted(hosts)[:8]})
        if i % 50 == 0:
            print(f"  ...{i}/{len(sample)}")

    ok = len(per_company)
    print(f"\n{ok} careers pages fetched, {sum(fetch_fail.values())} failed "
          f"({dict(fetch_fail)})")

    print("\n" + "=" * 78)
    print("HIRING PATHWAY - what the page is doing")
    print("=" * 78)
    for p, n in pathways.most_common():
        print(f"  {n:>4}  ({n/ok:5.1%})  {p}")

    print("\n" + "=" * 78)
    print("THIRD-PARTY HOSTS, ranked by how many companies reference them")
    print("=" * 78)
    print("  (anything not obviously analytics/CDN/social survives, so an")
    print("   unrecognised platform ranks itself rather than being filtered)")
    ranked = sorted(host_companies.items(), key=lambda kv: -len(kv[1]))
    for host, companies in ranked[:40]:
        if len(companies) < 2:
            continue
        print(f"  {len(companies):>4}  ({len(companies)/ok:5.1%})  {host}")

    singles = sum(1 for _, c in ranked if len(c) == 1)
    print(f"\n  ...plus {singles} hosts referenced by exactly one company "
          f"(long tail, mostly the company's own vendors)")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"sampled": len(sample), "fetched_ok": ok,
                       "pathways": dict(pathways),
                       "hosts": {h: sorted(c) for h, c in ranked if len(c) >= 2},
                       "per_company": per_company}, f, indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
