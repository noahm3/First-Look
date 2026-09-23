"""
Derives the current unsupported-ATS distribution from discovered_companies.csv
and writes it to unsupported_ats_tally.csv. Deliberately not hand-maintained -
SPEC.md section 3.5 ("store raw, derive on read") applies here: the raw
per-company mapping_failure_reason in discovered_companies.csv is the source
of truth, and this is just a re-runnable view over it, so it can never drift
out of date the way a hand-updated tally would. Re-run any time iteration6
checks more companies (or discovers new domains for it to check).

This is the input to the "should we build another ATS adapter" question
(SPEC.md 8.6, 18 measurement #2) - see ats_integration_backlog.md for the
qualitative feasibility findings (confirmed endpoints, sample fields, SPEC
cross-references) that don't belong in this derived-count view.

Run: python spikes/unsupported_ats_tally.py
"""

import csv
from collections import Counter

COMPANY_CSV = "discovered_companies.csv"
OUT_CSV = "unsupported_ats_tally.csv"


def main():
    with open(COMPANY_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    checked = [r for r in rows if r.get("last_checked_at")]
    excluded = [r for r in checked if r["notes"].startswith("excluded:")]
    fail = Counter(r["mapping_failure_reason"] for r in checked if r["mapping_failure_reason"])
    unsupported = Counter({
        k.split(":", 1)[1]: v for k, v in fail.items() if k.startswith("unsupported_ats:")
    })
    mapped = sum(1 for r in checked if r["mapping_confidence"])

    print(f"{len(checked)} of {len(rows)} companies checked ({len(excluded)} excluded as .org)")
    print(f"{mapped} mapped (verified/probable) against {sum(unsupported.values())} on a "
          f"known-but-unsupported ATS\n")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ats_provider", "company_count", "share_of_checked_pct"])
        for provider, count in unsupported.most_common():
            share = 100 * count / len(checked) if checked else 0
            writer.writerow([provider, count, f"{share:.2f}"])
            print(f"  {provider:25s} {count:4d}  ({share:.1f}%)")

    print(f"\nWrote {OUT_CSV}")


if __name__ == "__main__":
    main()
