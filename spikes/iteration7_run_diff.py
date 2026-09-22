"""
Diff two iteration 7 result files to measure posting churn and, more
importantly, to test an assumption `SPEC.md` §10's entire lifecycle rests on
and that nothing has yet verified: **is `ats_job_id` stable for the same
posting across runs?**

If it is not, every lifecycle rule built on it is wrong in the same direction
at once — step 2 inserts a "new" posting that isn't new, step 4 sets
`closed_at` on one that never closed, and the §14 anomaly check sees a churn
spike. During an unattended leave that reads as a busy week, not as a bug.

The one methodological trap this avoids: the mapped pool grows between runs
while iteration 6's mapping cascade is still going, so a naive diff counts
newly-*mapped companies* as newly-*opened postings*. Everything below is
restricted to the set of (provider, token) pairs present and ok in BOTH runs.

Run:
  python spikes/iteration7_run_diff.py before.json after.json
"""

import collections
import json
import sys

# Fields compared for drift on a posting whose ats_job_id is unchanged.
# posted_at is included deliberately: if it moves under a stable id, then
# SPEC.md §6's "posted_at is informational only" is doing real work.
DRIFT_FIELDS = ("title_raw", "department_raw", "location_raw",
                "workplace_type_raw", "url", "posted_at",
                "comp_data_quality", "comp_raw_summary")


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    companies = {}
    for c in d["companies"]:
        if c["status"] != "ok":
            continue
        key = (c["ats_provider"], c["ats_token"])
        companies[key] = {p["ats_job_id"]: p for p in c["postings"]
                          if p["ats_job_id"]}
    return d["run"], companies


def main(before_path, after_path):
    run_a, a = load(before_path)
    run_b, b = load(after_path)

    shared = sorted(set(a) & set(b))
    print(f"before : {run_a['started_at']}  {run_a['companies_ok']} companies ok, "
          f"{run_a['total_postings']} postings")
    print(f"after  : {run_b['started_at']}  {run_b['companies_ok']} companies ok, "
          f"{run_b['total_postings']} postings")
    print(f"companies ok in both (the only ones compared): {len(shared)}")
    print(f"  only in before: {len(set(a) - set(b))}   only in after: "
          f"{len(set(b) - set(a))}   <- pool churn, excluded")

    opened, closed, stable = [], [], 0
    drifted = collections.Counter()
    drift_examples = collections.defaultdict(list)

    for key in shared:
        ids_a, ids_b = set(a[key]), set(b[key])
        for jid in ids_b - ids_a:
            opened.append((key, b[key][jid]))
        for jid in ids_a - ids_b:
            closed.append((key, a[key][jid]))
        for jid in ids_a & ids_b:
            stable += 1
            pa, pb = a[key][jid], b[key][jid]
            for f in DRIFT_FIELDS:
                if pa.get(f) != pb.get(f):
                    drifted[f] += 1
                    if len(drift_examples[f]) < 3:
                        drift_examples[f].append(
                            (key[1], pa.get("title_raw"), pa.get(f), pb.get(f)))

    total_a = sum(len(a[k]) for k in shared)
    print(f"\npostings on shared companies: {total_a} before, "
          f"{sum(len(b[k]) for k in shared)} after")
    print(f"  id present in both runs : {stable}")
    print(f"  id only in after (new)  : {len(opened)}")
    print(f"  id only in before (gone): {len(closed)}")
    if total_a:
        print(f"  churn as % of before    : "
              f"{(len(opened) + len(closed)) / total_a:.2%}")

    print(f"\nfield drift on the {stable} postings whose ats_job_id was stable:")
    if not drifted:
        print("  none - every compared field identical on every stable posting")
    for f, n in drifted.most_common():
        print(f"  {f:20} {n:>5}")
        for tok, title, va, vb in drift_examples[f]:
            print(f"      {tok[:18]:18} {str(title)[:34]:34} {str(va)[:32]!r} -> "
                  f"{str(vb)[:32]!r}")

    if opened[:8]:
        print("\nsample of newly-appeared postings:")
        for (prov, tok), p in opened[:8]:
            print(f"  {prov:10} {tok[:18]:18} {str(p['title_raw'])[:44]:44} "
                  f"posted_at={p['posted_at']}")
    if closed[:8]:
        print("\nsample of disappeared postings:")
        for (prov, tok), p in closed[:8]:
            print(f"  {prov:10} {tok[:18]:18} {str(p['title_raw'])[:44]:44} "
                  f"posted_at={p['posted_at']}")

    # Would a naive whole-run diff have been misled by pool growth?
    naive_new = run_b["total_postings"] - run_a["total_postings"]
    print(f"\na naive whole-run diff would have reported {naive_new:+d} postings; "
          f"restricted to shared companies the real movement is "
          f"{len(opened)} opened / {len(closed)} closed")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
