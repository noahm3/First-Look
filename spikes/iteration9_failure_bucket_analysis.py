"""
Offline analysis of iteration 6's failure buckets.

`no_careers_page` (1,783) and `unknown` (1,176) together are ~70% of the
discovered set, and iteration 6's own entry flagged the likely cause as junk
rows in `discovered_companies.csv` rather than a weak cascade — VC-internal
tooling subdomains, CDN and asset hosts, auth portals with a coincidental
/careers path. That was never measured. It needs to be, because it is the
denominator of `SPEC.md` §18's measurement #1: "cascade coverage, % reaching
verified or probable" reads very differently over 4,284 candidate domains
than over however many of them are actually companies that hire.

No network. This only reads the CSV and characterises the domains, so it can
run over the whole set without spending a request. Its job is to size the
question and pick what a live sample should look at, not to answer it.
"""

import collections
import csv
import os
import re

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "discovered_companies.csv")

# Hosts that are infrastructure rather than a company's own site. Kept
# deliberately small and literal: this is a measurement, and an aggressive
# pattern here would manufacture the conclusion it is supposed to test.
INFRA_SUBSTRINGS = (
    "parastorage", "cloudfront", "akamai", "amazonaws", "googleusercontent",
    "wixsite", "squarespace", "herokuapp", "netlify", "vercel", "github.io",
    "cdn", "assets", "static", "sentry", "segment", "hubspot", "marketo",
)
INFRA_LABELS = (
    "auth", "login", "sso", "account", "accounts", "app", "api", "cdn",
    "assets", "static", "static1", "img", "images", "media", "files",
    "mail", "smtp", "ns1", "ns2", "portal", "dashboard", "admin", "my",
    "secure", "status", "docs", "help", "support", "blog", "news", "shop",
    "store", "careers", "jobs", "talent", "boards",
)


def registrable_root(domain):
    """Crude eTLD+1. Good enough to spot 'this row is a subdomain of another
    row', which is the only thing it is used for."""
    parts = domain.lower().split(".")
    if len(parts) <= 2:
        return domain.lower()
    # handle the common two-part public suffixes seen in this data
    if parts[-2] in ("co", "com", "org", "net", "ac", "gov") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def classify_domain(domain, all_roots):
    d = domain.lower()
    labels = d.split(".")
    reasons = []
    if any(s in d for s in INFRA_SUBSTRINGS):
        reasons.append("infra-host")
    if len(labels) > 2 and labels[0] in INFRA_LABELS:
        reasons.append(f"subdomain:{labels[0]}")
    root = registrable_root(d)
    if root != d and root in all_roots:
        reasons.append("subdomain-of-another-row")
    if len(labels) > 3:
        reasons.append("deep-subdomain")
    return reasons


def main():
    with open(CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"{len(rows)} discovered domains\n")

    print("=== outcome distribution ===")
    outcome = collections.Counter()
    for r in rows:
        if r["mapping_confidence"] in ("verified", "probable"):
            outcome[f"MAPPED:{r['mapping_confidence']}"] += 1
        elif r["mapping_failure_reason"]:
            reason = r["mapping_failure_reason"]
            outcome[reason if not reason.startswith("unsupported_ats")
                    else "unsupported_ats:*"] += 1
        else:
            outcome["(not checked / excluded)"] += 1
    for k, v in outcome.most_common():
        print(f"  {v:>5}  ({v/len(rows):5.1%})  {k}")

    # How many rows were skipped without spending a request at all?
    excluded = [r for r in rows if not r["last_checked_at"]]
    notes = collections.Counter(
        (r.get("notes") or "")[:60] for r in rows
        if not r["mapping_failure_reason"]
        and r["mapping_confidence"] not in ("verified", "probable"))
    if excluded or notes:
        print(f"\n=== rows with no mapping outcome: {sum(1 for r in rows if not r['mapping_failure_reason'] and r['mapping_confidence'] not in ('verified','probable'))} ===")
        for k, v in notes.most_common(6):
            print(f"  {v:>5}  {k!r}")

    all_roots = {r["company_domain"].lower() for r in rows}
    buckets = ("no_careers_page", "unknown")
    target = [r for r in rows if r["mapping_failure_reason"] in buckets]
    print(f"\n=== domain shape of the two big failure buckets "
          f"({len(target)} rows) ===")
    flagged = collections.Counter()
    clean = []
    for r in target:
        reasons = classify_domain(r["company_domain"], all_roots)
        if reasons:
            for x in reasons:
                flagged[x] += 1
        else:
            clean.append(r)
    n_flagged = len(target) - len(clean)
    print(f"  {n_flagged:>5}  ({n_flagged/len(target):5.1%})  flagged as probably not a "
          f"company's own site")
    for k, v in flagged.most_common(10):
        print(f"       {v:>5}  {k}")
    print(f"  {len(clean):>5}  ({len(clean)/len(target):5.1%})  plain-looking company "
          f"domains - these are the real cascade misses")

    print("\n=== same test applied to the MAPPED rows, as a control ===")
    mapped = [r for r in rows if r["mapping_confidence"] in ("verified", "probable")]
    mf = sum(1 for r in mapped if classify_domain(r["company_domain"], all_roots))
    print(f"  {mf}/{len(mapped)} ({mf/len(mapped):.1%}) of mapped rows would be "
          f"flagged by the same rules")
    print("  (if this were high, the rules would be junk - they are meant to be "
          "conservative)")

    print("\n=== TLD mix, failures vs mapped ===")
    def tlds(rs):
        return collections.Counter(r["company_domain"].rsplit(".", 1)[-1].lower()
                                   for r in rs)
    tf, tm = tlds(target), tlds(mapped)
    print(f"  {'tld':<10}{'failures':>10}{'mapped':>10}")
    for tld, _ in (tf + tm).most_common(10):
        print(f"  {tld:<10}{tf.get(tld,0):>10}{tm.get(tld,0):>10}")

    print("\n=== 25 plain-looking domains from the failure buckets ===")
    print("(the candidates a live re-check should sample from)")
    for r in clean[:25]:
        print(f"  {r['company_domain']:34} {r['mapping_failure_reason']:18} "
              f"{(r.get('notes') or '')[:46]}")


if __name__ == "__main__":
    main()
