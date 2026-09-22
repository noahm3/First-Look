"""
Live sample over iteration 6's failure buckets, to find out what those 2,959
rows actually are before deciding what to build.

Iteration 6 guessed the buckets were inflated by junk domains. The offline
pass (iteration9_failure_bucket_analysis.py) says structurally they are not:
only 2.3% look like infra hosts or subdomains, against a 0.9% false-positive
rate on mapped rows. So the question moves to two testable ones:

1. **Retryable fetch failures.** 9.3% of failures were HTTP 0 or 429 -
   connection errors and rate limiting - recorded as permanent mapping
   outcomes. `SPEC.md` §14 separates transient from permanent failures
   precisely here, and the 429s were self-inflicted. Do they succeed on a
   retry?
2. **"Homepage OK, no careers link found"** is 44.5% of failures. Is that a
   link-finding weakness, or are these organisations that simply do not hire
   the way a company does - initiatives, standards bodies, trade
   associations, funds? The offline sample was full of those, and no
   structural rule catches them.

Prints results for hand-labelling rather than classifying them itself.
Nothing is written to discovered_companies.csv.
"""

import argparse
import collections
import csv
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "discovered_companies.csv")

# A realistic browser UA. Iteration 6 used a bot-shaped one, and 4% of
# failures were 403s - worth knowing whether that is the whole story.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
MIN_INTERVAL = 1.0          # slower than the ATS limit: these are small sites
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
CAREERS_RE = re.compile(
    r"""href\s*=\s*["']([^"']*(?:career|jobs?|join-?us|work-with-us|"""
    r"""opportunit|vacanc|hiring)[^"']*)["']""", re.I)

_last = 0.0


def fetch(url, timeout=15):
    global _last
    gap = MIN_INTERVAL - (time.monotonic() - _last)
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
            return resp.status, resp.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


def note_category(row):
    n = (row.get("notes") or "").strip()
    m = re.search(r"status (\d+)", n)
    if m:
        code = m.group(1)
        return "transient" if code in ("0", "429") else f"http_{code}"
    if "no jobs/careers link found" in n:
        return "no_careers_link"
    if not n:
        return "unknown_no_note"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260922)
    args = ap.parse_args()

    with open(CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    failures = [r for r in rows
                if r["mapping_failure_reason"] in ("no_careers_page", "unknown")]

    groups = collections.defaultdict(list)
    for r in failures:
        groups[note_category(r)].append(r)

    rng = random.Random(args.seed)
    wanted = ["transient", "http_403", "no_careers_link", "unknown_no_note"]
    print(f"{len(failures)} failures; sampling {args.per_group} from each of "
          f"{', '.join(wanted)}\n")

    tally = collections.Counter()
    for group in wanted:
        pool = groups.get(group, [])
        if not pool:
            continue
        sample = rng.sample(pool, min(args.per_group, len(pool)))
        print("=" * 78)
        print(f"{group}  (population {len(pool)}, sampling {len(sample)})")
        print("=" * 78)
        for r in sample:
            domain = r["company_domain"]
            status, html = fetch(f"https://{domain}")
            title = ""
            if html:
                m = TITLE_RE.search(html)
                if m:
                    title = re.sub(r"\s+", " ", m.group(1)).strip()[:72]
            links = []
            if html:
                links = [h for h in CAREERS_RE.findall(html)][:2]
            outcome = ("OK " if status == 200 else f"{status:<3}")
            tally[(group, "reachable" if status == 200 else "unreachable")] += 1
            if status == 200 and links:
                tally[(group, "careers_link_now_found")] += 1
            print(f"  [{outcome}] {domain:32} {title}")
            if links:
                print(f"         -> careers link: {links[0][:88]}")
        print()

    print("=" * 78)
    print("TALLY")
    print("=" * 78)
    for (group, what), n in sorted(tally.items()):
        print(f"  {group:18} {what:24} {n}")


if __name__ == "__main__":
    sys.exit(main())
