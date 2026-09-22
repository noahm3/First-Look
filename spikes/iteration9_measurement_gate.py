"""
SPEC.md §18's measurement gate, computed from spike data.

Four numbers. This script COMPUTES them; it does not interpret them.
`BUILD.md` M7 and `CRITERIA.md` C-7.3 are explicit that the go/no-go call is
the user's and must not be delegated, so no gate outcome is printed here.

**Caveat on provenance, stated up front because it affects how much weight
these deserve.** §18 says to run this after M4, from the real pipeline's
`--dump-facets` output over a seeded database. There is no pipeline and no
database yet - these come from `spikes/`, over the VC-discovered company set
(`discovered_companies.csv`), which is a different and narrower population
than the watchlist + ClimateTechList + ClimateBase seed §18 assumes. The
numbers are real measurements of real boards; they are not the same
measurement §18 describes.

Measurement 4 needs `location_class`, which §12.3 deliberately defers until
real `location_raw` values have been seen. They have been now, so this
applies the narrow rule §12.3 describes - structured field where a provider
gives one, narrow keyword match otherwise, never guessing onsite - and
reports the resulting `unknown` share.
"""

import collections
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "discovered_companies.csv")
RESULTS = os.path.join(HERE, "iteration7_live_postings_mapped6_results.json")

# SPEC.md 12.3: narrow, for remote and hybrid only. Never guesses onsite.
REMOTE_RE = re.compile(r"\bremote\b|\bwork from home\b|\bwfh\b|\bdistributed\b", re.I)
HYBRID_RE = re.compile(r"\bhybrid\b", re.I)
ONSITE_RE = re.compile(r"\bon-?site\b|\bin-?office\b|\bin person\b", re.I)


def location_class(posting):
    """Structured field first, then a narrow keyword match on the raw string."""
    wt = (posting.get("workplace_type_raw") or "").strip().lower()
    if wt:
        if "remote" in wt:
            return "remote"
        if "hybrid" in wt:
            return "hybrid"
        if "onsite" in wt or "on-site" in wt or "office" in wt:
            return "onsite"
    raw = posting.get("location_raw") or ""
    if HYBRID_RE.search(raw):
        return "hybrid"
    if REMOTE_RE.search(raw):
        return "remote"
    if ONSITE_RE.search(raw):
        return "onsite"
    return "unknown"


def main():
    with open(CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(RESULTS, encoding="utf-8") as f:
        res = json.load(f)
    postings = [(c, p) for c in res["companies"] if c["status"] == "ok"
                for p in c["postings"]]

    print(__doc__.strip())
    print("\n" + "=" * 78)
    print("MEASUREMENT 1 - cascade coverage")
    print("=" * 78)
    mapped = [r for r in rows if r["mapping_confidence"] in ("verified", "probable")]
    excluded = [r for r in rows if not r["last_checked_at"]]
    attempted = len(rows) - len(excluded)
    print(f"  discovered domains                 {len(rows):>6}")
    print(f"  excluded without a request         {len(excluded):>6}  "
          f"(.org rule, user's 2026-09-22 call)")
    print(f"  actually attempted                 {attempted:>6}")
    print(f"  reached verified or probable       {len(mapped):>6}  "
          f"({len(mapped)/attempted:.1%} of attempted)")
    print(f"    verified                         "
          f"{sum(1 for r in mapped if r['mapping_confidence']=='verified'):>6}")
    print(f"    probable                         "
          f"{sum(1 for r in mapped if r['mapping_confidence']=='probable'):>6}")
    print("\n  NOTE: the denominator is the open question. These 4,284 domains are")
    print("  VC-portfolio-page scrapes, not a curated company list, and the")
    print("  failure buckets contain initiatives, funds and trade associations")
    print("  that were never going to have an ATS. Coverage over 'companies that")
    print("  hire' is higher than this number by an unmeasured amount.")

    print("\n" + "=" * 78)
    print("MEASUREMENT 2 - mapping_failure_reason distribution")
    print("=" * 78)
    reasons = collections.Counter(r["mapping_failure_reason"] for r in rows
                                  if r["mapping_failure_reason"])
    total_fail = sum(reasons.values())
    for reason, n in reasons.most_common():
        print(f"  {n:>6}  ({n/total_fail:5.1%})  {reason}")
    unsup = {k: v for k, v in reasons.items() if k.startswith("unsupported_ats:")}
    print(f"\n  unsupported_ats total: {sum(unsup.values())} "
          f"({sum(unsup.values())/total_fail:.1%} of failures) - the adapter question")
    print("  largest unsupported providers:")
    for k, v in sorted(unsup.items(), key=lambda x: -x[1])[:6]:
        print(f"    {v:>5}  {k.split(':',1)[1]}")
    sr = reasons.get("unsupported_ats:smartrecruiters", 0)
    print(f"\n  SmartRecruiters specifically (SPEC 4 defers its adapter on volume): {sr}")

    print("\n" + "=" * 78)
    print("MEASUREMENT 3 - compensation disclosure on live postings")
    print("=" * 78)
    n = len(postings)
    struct = sum(1 for _, p in postings if p["comp_data_quality"] != "none")
    desc = sum(1 for _, p in postings if p["comp_in_description_confident"])
    either = sum(1 for _, p in postings
                 if p["comp_data_quality"] != "none"
                 or p["comp_in_description_confident"])
    print(f"  live postings                      {n:>6}")
    print(f"  provider structured field          {struct:>6}  ({struct/n:5.1%})")
    print(f"  description body                   {desc:>6}  ({desc/n:5.1%})")
    print(f"  EITHER                             {either:>6}  ({either/n:5.1%})")
    print("\n  by provider (combined):")
    for prov in ("greenhouse", "lever", "ashby"):
        ps = [p for c, p in postings if c["ats_provider"] == prov]
        if not ps:
            continue
        e = sum(1 for p in ps if p["comp_data_quality"] != "none"
                or p["comp_in_description_confident"])
        print(f"    {prov:11} {e:>6}/{len(ps):<6} ({e/len(ps):5.1%})")

    print("\n" + "=" * 78)
    print("MEASUREMENT 4 - location_class unknown share")
    print("=" * 78)
    classes = collections.Counter(location_class(p) for _, p in postings)
    for k in ("remote", "hybrid", "onsite", "unknown"):
        print(f"  {k:10} {classes[k]:>6}  ({classes[k]/n:5.1%})")
    struct_only = sum(1 for _, p in postings if p["workplace_type_raw"])
    print(f"\n  from a provider's structured field  {struct_only:>6}  "
          f"({struct_only/n:5.1%})")
    print(f"  recovered by the keyword rule       "
          f"{n - struct_only - classes['unknown']:>6}  "
          f"({(n - struct_only - classes['unknown'])/n:5.1%})")
    print(f"  still unknown                       {classes['unknown']:>6}  "
          f"({classes['unknown']/n:5.1%})")
    print("\n  by provider, unknown share:")
    for prov in ("greenhouse", "lever", "ashby"):
        ps = [p for c, p in postings if c["ats_provider"] == prov]
        if not ps:
            continue
        u = sum(1 for p in ps if location_class(p) == "unknown")
        print(f"    {prov:11} {u:>6}/{len(ps):<6} ({u/len(ps):5.1%})")

    print("\n" + "=" * 78)
    print("The gate outcome is not computed here. BUILD.md M7 and CRITERIA.md")
    print("C-7.3 both say the decision is the user's and must not be delegated.")
    print("=" * 78)


if __name__ == "__main__":
    sys.exit(main())
