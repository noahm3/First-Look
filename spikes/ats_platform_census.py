"""
ATS platform census - the standing tool for "which ATS platforms do the
companies we have discovered actually run, and how many of each?"

This is the methodology to reuse for every future discovery source
(ClimateBase, Built In Boston, Greentown, Wellfound, YC). Run it after a
source has been crawled and mapped; it upserts into a persistent tally so the
picture accumulates across sources instead of being recomputed from scratch
and lost each time.

WHY IT WORKS THE WAY IT DOES. Earlier passes at this question matched a
hand-written list of ATS domains, which can only ever find platforms someone
already thought of. One such probe overstated the recoverable share by 4x
because its regex was looser than the real fingerprints. This inverts that:
it extracts EVERY third-party host each careers page references, drops hosts
that are obviously not recruiting infrastructure, names what it can from an
editable mapping file, and reports everything it could NOT name, ranked by
how many companies reference it. A platform nobody here has heard of shows up
near the top of that list rather than being silently invisible.

Naming lives in `ats_platform_hosts.csv`, hand-editable, same pattern as
SPEC.md §12.4's alias files: a lookup table the user owns, not a classifier
(§3.6). When the unnamed list surfaces something real, add a row there and
re-run - no code change.

FILES
  ats_platform_hosts.csv        host regex -> platform name. Edit by hand.
  ats_platform_detections.csv   one row per (company, platform). Upserted, so
                                re-running a source updates rather than
                                duplicates. This is the raw record.
  ats_platform_tally.csv        derived from detections on every run. Never
                                edit; it is regenerated (§3.5 store raw,
                                derive on read).

SCOPE. Companies already mapped to a supported ATS are counted from the
mapping itself and not re-fetched. Everything else with a known careers page
is fetched once.

Run:
  python spikes/ats_platform_census.py --all
  python spikes/ats_platform_census.py --bucket unknown --limit 100
  python spikes/ats_platform_census.py --source climatebase      # future
  python spikes/ats_platform_census.py --report-only             # no network
"""

import argparse
import collections
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
COMPANIES = os.path.join(HERE, "discovered_companies.csv")
HOSTS_MAP = os.path.join(HERE, "ats_platform_hosts.csv")
DETECTIONS = os.path.join(HERE, "ats_platform_detections.csv")
TALLY = os.path.join(HERE, "ats_platform_tally.csv")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
# The Chrome version here is load-bearing - see iteration6_ats_mapping_spike.py.
# Domains that 403 an old UA return 200 to a current one, and this cascade
# would record that as "no careers page".

DETECTION_FIELDS = ["company_domain", "platform", "evidence_host",
                    "discovery_source", "detected_at", "method"]

HOST_RE = re.compile(r"https?://([a-z0-9][a-z0-9.\-]{2,})", re.I)
IFRAME_RE = re.compile(r"<iframe[^>]+src=[\"']https?://([a-z0-9][a-z0-9.\-]+)", re.I)
WP_RE = re.compile(r"wp-job-manager|job_listing|wpjobboard", re.I)

# Not recruiting infrastructure. Everything NOT matched here survives into the
# unnamed list, so this is deliberately a denylist of things we are sure about
# rather than an allowlist of things we recognise.
NOISE = re.compile(
    r"(google|gstatic|googleapis|googletagmanager|doubleclick|youtube|youtu\.be|"
    r"facebook|fbcdn|instagram|twitter|x\.com|tiktok|vimeo|threads\.com|bsky\.app|"
    r"pinterest|reddit|whatsapp|telegram|snap\.licdn|licdn\.com|lnkd\.in|"
    # linkedin.com is a social link on nearly every careers page. Host
    # mining cannot tell a /jobs URL from an /company link, and SPEC.md 4
    # rules LinkedIn out as a source entirely, so it is pure noise here.
    r"linkedin\.com|"
    r"cloudflare|cloudfront|akamai|fastly|jsdelivr|unpkg|bootstrapcdn|jquery|"
    r"fontawesome|typekit|fonts\.|rsms\.me|adobe|w3\.org|schema\.org|ogp\.me|"
    r"opengraphprotocol|gmpg\.org|browsehappy|"
    r"w\.org|wp\.com|wp-rocket|yoast|rankmath|monsterinsights|elementor|"
    r"website-files|webflow|framer|sanity\.io|parastorage|sqspcdn|squarespace|"
    r"wixstatic|shopify|hubspot|hs-scripts|hs-banner|hs-analytics|hubs\.ly|"
    r"marketo|segment|sentry|newrelic|datadog|hotjar|clarity\.ms|posthog|"
    r"intercom|drift|zendesk|mailchimp|klaviyo|lfeeder|intellimize|"
    r"cookielaw|cookieyes|cookiebot|osano|usercentrics|onetrust|termly|iubenda|"
    r"consentpro|acsbapp|addtoany|datatables|bugherd|vector\.co|"
    r"stripe|paypal|apple\.com|microsoft|office\.com|bing|yandex|baidu|"
    r"amazonaws|azureedge|githubusercontent|github\.com|gitlab|"
    r"medium\.com|substack|calendly|zoom\.us|slack\.com|notion\.so|airtable|"
    r"typeform|forms\.gle|docs\.google|crunchbase|bloomberg|reuters|techcrunch|"
    r"forbes|wsj|nytimes|spotify|g2\.com|goo\.gl|gravatar|recaptcha)", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_host_map():
    """[(compiled_pattern, platform, adapter_status)] from the editable CSV."""
    out = []
    with open(HOSTS_MAP, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pat = (row.get("host_pattern") or "").strip()
            if not pat:
                continue
            out.append((re.compile(pat, re.I), row["platform"].strip(),
                        (row.get("adapter_status") or "").strip()))
    return out


def read_csv(path, fields):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["company_domain"], r["platform"]): r for r in csv.DictReader(f)}


def write_csv(path, fields, rows_by_key):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows_by_key.values():
            w.writerow({k: r.get(k, "") for k in fields})


_last = 0.0


def fetch(url, interval, timeout=15):
    """Returns (status, body). Never raises (SPEC.md §3.7)."""
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


def mine_hosts(html, own_domain):
    own = set(p for p in own_domain.lower().split(".") if len(p) > 3)
    hosts = set()
    for h in HOST_RE.findall(html) + IFRAME_RE.findall(html):
        h = h.lower().rstrip(".")
        if NOISE.search(h) or any(p in h for p in own):
            continue
        hosts.add(h)
    return hosts


def rebuild_tally(detections, host_map):
    status_of = {}
    for _, platform, status in host_map:
        status_of.setdefault(platform, status)
    by_platform = collections.defaultdict(set)
    mapped_only = collections.defaultdict(set)
    by_source = collections.defaultdict(lambda: collections.defaultdict(set))
    for (domain, platform), row in detections.items():
        by_platform[platform].add(domain)
        if row.get("method") == "ats_mapping_cascade":
            mapped_only[platform].add(domain)
        by_source[platform][row.get("discovery_source", "")].add(domain)
    rows = {}
    for platform, domains in by_platform.items():
        srcs = "; ".join(f"{s or 'unknown'}={len(d)}"
                         for s, d in sorted(by_source[platform].items()))
        # Split deliberately. "mapped" means a validated token we can actually
        # poll; "referenced" means the careers page names the platform but the
        # cascade did not produce a usable mapping. Conflating them would
        # overstate real coverage, which is the failure mode SPEC.md 3.8 cares
        # about most.
        rows[(platform, "")] = {
            "platform": platform,
            "companies": len(domains),
            "mapped": len(mapped_only[platform]),
            "referenced_not_mapped": len(domains) - len(mapped_only[platform]),
            "adapter_status": status_of.get(platform, "unnamed"),
            "by_source": srcs,
            "updated_at": now_iso(),
        }
    ordered = dict(sorted(rows.items(),
                          key=lambda kv: -int(kv[1]["companies"])))
    with open(TALLY, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["platform", "companies", "mapped",
                                          "referenced_not_mapped",
                                          "adapter_status", "by_source",
                                          "updated_at"])
        w.writeheader()
        for r in ordered.values():
            w.writerow(r)
    return ordered


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--all", action="store_true",
                    help="every unmapped company that has a known careers page")
    ap.add_argument("--bucket", action="append",
                    help="restrict to a mapping_failure_reason (repeatable)")
    ap.add_argument("--source", action="append",
                    help="restrict to a discovery_method (repeatable)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--interval", type=float, default=0.6,
                    help="seconds between requests (default 0.6; each request "
                         "goes to a different host, so this is politeness "
                         "rather than a per-host rate limit)")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild the tally from existing detections, no network")
    args = ap.parse_args()

    host_map = load_host_map()
    detections = read_csv(DETECTIONS, DETECTION_FIELDS)
    print(f"{len(host_map)} host patterns, "
          f"{len(detections)} existing detections on record")

    if not args.report_only:
        with open(COMPANIES, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Companies already mapped: the answer is known, no fetch needed.
        mapped = [r for r in rows
                  if r["mapping_confidence"] in ("verified", "probable")
                  and r["ats_provider"]]
        for r in mapped:
            key = (r["company_domain"], r["ats_provider"])
            detections[key] = {
                "company_domain": r["company_domain"],
                "platform": r["ats_provider"],
                "evidence_host": f"mapped token {r['ats_token']}",
                "discovery_source": r.get("discovery_method", ""),
                "detected_at": now_iso(),
                "method": "ats_mapping_cascade",
            }
        print(f"{len(mapped)} mapped companies folded in without a request")

        todo = [r for r in rows
                if r["careers_page_url"]
                and r["mapping_confidence"] not in ("verified", "probable")]
        if args.bucket:
            todo = [r for r in todo if r["mapping_failure_reason"] in args.bucket]
        if args.source:
            todo = [r for r in todo if r.get("discovery_method") in args.source]
        if args.limit:
            todo = todo[:args.limit]

        print(f"{len(todo)} careers pages to fetch "
              f"(~{len(todo)*args.interval/60:.0f} min at {args.interval}s)\n")

        unnamed = collections.defaultdict(set)
        fetch_status = collections.Counter()
        found = 0
        for i, r in enumerate(todo, 1):
            domain = r["company_domain"]
            status, html = fetch(r["careers_page_url"], args.interval)
            fetch_status[status] += 1
            if status != 200 or not html:
                continue
            hosts = mine_hosts(html, domain)
            hits = set()
            for host in hosts:
                for pat, platform, _ in host_map:
                    if pat.search(host):
                        hits.add((platform, host))
                        break
                else:
                    unnamed[host].add(domain)
            if WP_RE.search(html):
                hits.add(("wordpress-job-plugin", "wp-job-manager markup"))
            for platform, host in hits:
                detections[(domain, platform)] = {
                    "company_domain": domain,
                    "platform": platform,
                    "evidence_host": host,
                    "discovery_source": r.get("discovery_method", ""),
                    "detected_at": now_iso(),
                    "method": "careers_page_host_mining",
                }
            if hits:
                found += 1
            if i % 100 == 0:
                print(f"  ...{i}/{len(todo)}  ({found} with a platform so far)")

        print(f"\nfetched: {dict(fetch_status)}")
        print(f"{found}/{len(todo)} careers pages yielded a named platform")
        write_csv(DETECTIONS, DETECTION_FIELDS, detections)

        print("\n" + "=" * 74)
        print("UNNAMED HOSTS on 3+ companies - candidates for ats_platform_hosts.csv")
        print("=" * 74)
        ranked = sorted(unnamed.items(), key=lambda kv: -len(kv[1]))
        shown = 0
        for host, doms in ranked:
            if len(doms) < 3:
                break
            print(f"  {len(doms):>4}  {host}")
            shown += 1
            if shown >= 30:
                break
        if not shown:
            print("  (none)")

    tally = rebuild_tally(detections, host_map)
    print("\n" + "=" * 74)
    print("ATS PLATFORM TALLY - all sources to date")
    print("=" * 74)
    print(f"  {'platform':<24}{'total':>7}{'mapped':>8}{'ref-only':>10}  {'status':<12}")
    total = 0
    for r in tally.values():
        total += int(r["companies"])
        print(f"  {r['platform']:<24}{r['companies']:>7}{r['mapped']:>8}"
              f"{r['referenced_not_mapped']:>10}  {r['adapter_status']:<12}")
    print(f"  {'-'*24}{'-'*25}")
    print(f"  {'(platform detections)':<24}{total:>7}")
    print(f"\nwrote {os.path.relpath(TALLY, os.path.dirname(HERE))}")
    print(f"      {os.path.relpath(DETECTIONS, os.path.dirname(HERE))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
