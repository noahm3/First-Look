"""
One-off pass: re-validate every already-accepted mapping in
discovered_companies.csv against the provider's own board endpoint, and
demote the ones pointing at boards that do not exist.

Why this exists. Iteration 6's cascade accepted a token scraped off a
company's careers page as `verified` without ever calling the provider —
stage 1 (slug guessing) validated its guesses, stage 3 (careers-page regex)
did not. Iteration 7 then fetched all 584 mapped boards and found 30 dead
tokens, **every one of them from stage 3 and none from stage 1**. The cascade
itself is fixed in iteration6_ats_mapping_spike.py; this script repairs the
rows that the unvalidated version already wrote.

What a failure becomes. `mapping_failure_reason = weak_only`, which SPEC.md
§8.4 defines as "token found, failed validation" — exactly this case. That
puts the company back in the monthly retry set (§8.5) rather than leaving it
`verified` and silently contributing nothing, and keeps it visible in the
§8.4 distribution that the adapter decision rests on. Per SPEC.md §3.8 a
known gap beats invisible bad data.

This is the only script in the iteration 7/8 series that writes to
discovered_companies.csv, and it is safe to run only because iteration 6's
mapping run has finished — both writers rewrite the file whole.

Run:
  python spikes/iteration8_revalidate_mappings.py            # report only
  python spikes/iteration8_revalidate_mappings.py --apply    # write the CSV
"""

import argparse
import collections
import json
import sys
import time
import urllib.error
import urllib.request

import tracking_store

UA = "first-look-spike/0.1 (+https://github.com/)"
MIN_INTERVAL = 1 / 3.0          # SPEC.md §9: 2-5 req/sec per provider
SUPPORTED = ("greenhouse", "lever", "ashby")

_last_request = {}


def _throttle(host):
    last = _last_request.get(host)
    now = time.monotonic()
    if last is not None:
        gap = MIN_INTERVAL - (now - last)
        if gap > 0:
            time.sleep(gap)
            now = time.monotonic()
    _last_request[host] = now


def fetch_json(url, timeout=15, attempts=3):
    """Returns (status, parsed_or_None). Never raises.

    Retries anything that is not a definitive answer. A timeout or connection
    reset reports status 0, and status 0 must never be read as "this board is
    gone" - see the demote-on-404-only rule below.
    """
    host = url.split("/")[2]
    status, parsed = 0, None
    for attempt in range(attempts):
        _throttle(host)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, None
        except urllib.error.HTTPError as exc:
            status = exc.code
            if 400 <= status < 500 and status != 429:
                return status, None          # a definitive answer
        except Exception:
            status = 0
        if attempt < attempts - 1:
            time.sleep(2 ** attempt)
    return status, parsed


def check_greenhouse(token):
    status, data = fetch_json(
        f"https://boards-api.greenhouse.io/v1/boards/{token}")
    if status != 200 or not isinstance(data, dict):
        return status, None
    return status, {"name": data.get("name")}


def check_lever(token):
    status, data = fetch_json(
        f"https://api.lever.co/v0/postings/{token}?mode=json")
    if status != 200 or not isinstance(data, list):
        return status, None
    return status, {"name": None}


def check_ashby(token):
    status, data = fetch_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        f"?includeCompensation=false")
    if status != 200 or not isinstance(data, dict) or "jobs" not in data:
        return status, None
    return status, {"name": None}


CHECKS = {
    "greenhouse": check_greenhouse,
    "lever": check_lever,
    "ashby": check_ashby,
}


def main():
    ap = argparse.ArgumentParser(
        description="Re-validate accepted ATS mappings against the live board.")
    ap.add_argument("--apply", action="store_true",
                    help="write corrections to discovered_companies.csv "
                         "(default is report only)")
    args = ap.parse_args()

    rows = tracking_store.list_companies()
    mapped = [r for r in rows
              if r.get("mapping_confidence") in ("verified", "probable")
              and r.get("ats_provider") in SUPPORTED
              and (r.get("ats_token") or "").strip()]
    print(f"{len(rows)} rows, {len(mapped)} accepted mappings to re-validate")
    print(f"mode: {'APPLY - will write the CSV' if args.apply else 'report only'}\n")

    dead, live, inconclusive = [], [], []
    by_method = collections.Counter()
    for i, row in enumerate(mapped, 1):
        provider = row["ats_provider"]
        token = row["ats_token"].strip()
        try:                                  # SPEC.md §3.7
            status, result = CHECKS[provider](token)
        except Exception as exc:              # a bug here included
            print(f"  [{i}/{len(mapped)}] {provider} {token}: "
                  f"unhandled {type(exc).__name__}: {exc} - left alone")
            continue
        if result is None and not (400 <= status < 500 and status != 429):
            # Transient: timeout, connection reset, 5xx, rate limit. SPEC.md
            # section 14 calls these transient and permanent failures out
            # separately for exactly this reason. Demoting on one would
            # retire a live board on a bad network moment - which this script
            # did on its first run, to a board carrying 336 open postings.
            inconclusive.append((row, status))
            print(f"  ????  {provider:11} {token:26} HTTP {status:<4} "
                  f"{row['company_domain']:28} inconclusive - left alone")
            continue
        if result is None:
            dead.append((row, status))
            by_method[(row.get("mapping_method", ""),
                       row.get("mapping_confidence", ""))] += 1
            print(f"  DEAD  {provider:11} {token:26} HTTP {status:<4} "
                  f"{row['company_domain']:28} {row.get('mapping_confidence')} "
                  f"via {row.get('mapping_method')}")
        else:
            live.append(row)

    print(f"\n{len(live)} live, {len(dead)} dead, "
          f"{len(inconclusive)} inconclusive (left alone, not demoted)")
    if dead:
        print("\ndead tokens by the cascade stage that produced them:")
        for (method, conf), n in by_method.most_common():
            print(f"  {n:>3}  {conf:9} {method}")

    if not args.apply:
        print("\nreport only - nothing written. Re-run with --apply to correct "
              "these rows.")
        return 0

    for row, status in dead:
        tracking_store.update_company_mapping(
            row["company_domain"],
            ats_provider="",
            ats_token="",
            mapping_confidence="",
            mapping_method=row.get("mapping_method", ""),
            mapping_failure_reason="weak_only",
            notes=(f"revalidated 2026-09-22: token "
                   f"{row['ats_token']!r} on {row['ats_provider']} returned "
                   f"HTTP {status}; board does not exist"),
        )
    print(f"\nwrote {len(dead)} corrections to discovered_companies.csv")
    print("careers_page_url is left intact - the page was found, and it is "
          "still the right place for a monthly retry to look.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
