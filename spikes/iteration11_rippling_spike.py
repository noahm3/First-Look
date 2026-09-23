"""
Iteration 11: fetch live postings from Rippling, the largest unpollable
platform iteration 11's census found (62 companies, spikes/ats_platform_census.py).

Reuses iteration7_live_postings_spike.py's proven infra (rate limiter, fetch
helper, blank_posting shape, comp-in-description extraction, redaction) via
import rather than copying it - same fields, same public-repo hygiene, same
SPEC.md 3.7/9 discipline (per-host rate limit, no exception escapes the loop).

TWO STEPS, because the census recorded which HOST each company references
(ats.rippling.com or static-assets.ripplingcdn.com), never the board token
itself:

1. Resolve the actual token per company. Confirmed live 2026-09-22 on a
   6-company hand sample: two distinct patterns point at the SAME API.
     - Hosted page:  https://ats.rippling.com/{token}/jobs           (token in URL)
     - Embed widget: <div data-job-board-id="{token}"> + a script tag
       from static-assets.ripplingcdn.com                            (token in HTML)
   Both resolve against api.rippling.com/platform/api/ats/v2/board/{token}/jobs.

2. Fetch postings for every resolved token, small batch first.

API SHAPE, confirmed live (not documented anywhere found):
  GET api.rippling.com/platform/api/ats/v2/board/{token}/jobs[?page=N]
    -> {"items": [...], "page", "pageSize" (20), "totalItems", "totalPages"}
    List item: id, name, url, department.name, locations[] (name, country,
    countryCode, state, stateCode, city, workplaceType - structured, like
    Ashby), language. NO date, NO comp on the list endpoint.
  GET .../board/{token}/jobs/{id}
    -> adds createdOn (real posted date, unlike Greenhouse's list-only
    first_published - this detail call is NOT redundant, unlike Greenhouse's),
    payRangeDetails (structured comp: location/currency/frequency/rangeStart/
    rangeEnd - clean, no prose parsing needed), description.company /
    description.role (HTML - comp-in-description extraction applies here too,
    confirmed on formant-careers).

Run:
  python spikes/iteration11_rippling_spike.py --resolve             # step 1 only
  python spikes/iteration11_rippling_spike.py --limit 10            # small batch
  python spikes/iteration11_rippling_spike.py --all                 # whole set
"""

import argparse
import collections
import csv
import html as html_module
import json
import os
import re
import sys
import time

import iteration7_live_postings_spike as base

HERE = os.path.dirname(os.path.abspath(__file__))
DETECTIONS = os.path.join(HERE, "ats_platform_detections.csv")
COMPANIES = os.path.join(HERE, "discovered_companies.csv")
TOKENS_OUT = os.path.join(HERE, "iteration11_rippling_tokens.csv")

API_BASE = "https://api.rippling.com/platform/api/ats/v2/board"

# Confirmed live 2026-09-22, in this priority order, against 62 real careers
# pages - the token shows up in more shapes than a first 6-company sample
# suggested:
#   1. The literal API call in inline JS ("api.rippling.com/platform/api/ats/
#      v2/board/{token}/jobs") - the most reliable signal, since it IS the
#      endpoint, wherever it happens to appear on the page.
#   2. The embed widget's own data-job-board-id attribute.
#   3. The hosted page URL - which turned out to have three sub-variants:
#      bare (ats.rippling.com/{token}, no /jobs), /embed/{token}/jobs, and a
#      locale-prefixed /en-GB/{token}/jobs.
# HTML entities are unescaped BEFORE matching, not after - the same ordering
# bug already found once this session on Greenhouse's content field. One
# company (gradientcomfort.com) had its embed snippet double-encoded
# (data-job-board-id=&quot;gradientcomfort&quot;), which a match-then-unescape
# order would silently miss entirely.
API_URL_TOKEN_RE = re.compile(
    r"api\.rippling\.com/platform/api/ats/v2/board/([a-z0-9][a-z0-9-]*)/jobs", re.I)
EMBED_TOKEN_RE = re.compile(r'data-job-board-id=["\']([a-z0-9][a-z0-9-]*)["\']', re.I)
HOSTED_TOKEN_RE = re.compile(
    r"ats\.rippling\.com/(?:embed/)?(?:[a-z]{2}(?:-[A-Z]{2})?/)?"
    r"([a-z0-9][a-z0-9-]{2,})(?:/jobs)?(?=[/?\"'\s]|$)", re.I)


# --------------------------------------------------------------------------
# step 1: resolve the real board token per company
# --------------------------------------------------------------------------

def fetch_html(url, limiter, requests_counter):
    """Like base.fetch_json but for HTML, not JSON. Same never-raises contract."""
    import urllib.error
    import urllib.request

    attempt = 0
    while True:
        limiter.wait(url)
        requests_counter[0] += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": base.USER_AGENT})
            with urllib.request.urlopen(req, timeout=base.TIMEOUT_S) as resp:
                raw = resp.read(base.MAX_BYTES + 1)
                if len(raw) > base.MAX_BYTES:
                    return base.FetchResult(False, resp.status,
                                            error="response exceeded byte cap")
                return base.FetchResult(True, resp.status,
                                        raw.decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 or attempt >= base.MAX_RETRIES:
                return base.FetchResult(False, exc.code, error=f"HTTP {exc.code}")
        except Exception as exc:
            if attempt >= base.MAX_RETRIES:
                return base.FetchResult(False, 0, error=f"{type(exc).__name__}: {exc}")
        attempt += 1
        time.sleep(2 ** (attempt - 1))


def resolve_all_tokens(interval):
    with open(DETECTIONS, newline="", encoding="utf-8") as f:
        detected = sorted({r["company_domain"] for r in csv.DictReader(f)
                           if r["platform"] == "rippling"})
    companies = {r["company_domain"]: r for r in
                csv.DictReader(open(COMPANIES, newline="", encoding="utf-8"))}

    limiter = base.HostRateLimiter(1.0 / interval)
    requests = [0]
    resolved, unresolved = [], []
    for domain in detected:
        url = companies.get(domain, {}).get("careers_page_url")
        if not url:
            unresolved.append((domain, "no careers_page_url on record"))
            continue
        try:                                     # SPEC.md 3.7
            res = fetch_html(url, limiter, requests)
        except Exception as exc:
            unresolved.append((domain, f"unhandled {type(exc).__name__}: {exc}"))
            continue
        if not res.ok:
            unresolved.append((domain, res.error))
            continue
        text = html_module.unescape(res.data)          # BEFORE matching, not after
        m = (API_URL_TOKEN_RE.search(text) or EMBED_TOKEN_RE.search(text)
             or HOSTED_TOKEN_RE.search(text))
        if m:
            resolved.append((domain, m.group(1)))
        else:
            unresolved.append((domain, "host referenced but no token pattern matched"))

    with open(TOKENS_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company_domain", "rippling_token"])
        for domain, token in resolved:
            w.writerow([domain, token])

    print(f"resolved {len(resolved)}/{len(detected)} tokens "
          f"({requests[0]} requests)")
    if unresolved:
        print(f"{len(unresolved)} unresolved:")
        for domain, why in unresolved:
            print(f"  {domain:32} {why}")
    print(f"wrote {os.path.relpath(TOKENS_OUT, os.path.dirname(HERE))}")
    return resolved


def load_resolved_tokens():
    if not os.path.exists(TOKENS_OUT):
        return []
    with open(TOKENS_OUT, newline="", encoding="utf-8") as f:
        return [(r["company_domain"], r["rippling_token"])
                for r in csv.DictReader(f)]


# --------------------------------------------------------------------------
# step 2: fetch postings
# --------------------------------------------------------------------------

def fetch_rippling(token, ctx):
    """List (paginated) + one detail call per posting for createdOn and
    payRangeDetails - unlike Greenhouse, these are NOT on the list endpoint,
    so the detail call is load-bearing here, not redundant."""
    postings = []
    page = 0
    total_pages = 1
    raw_keys = None
    while page < total_pages:
        url = f"{API_BASE}/{token}/jobs" + (f"?page={page}" if page else "")
        res = base.fetch_json(url, ctx["limiter"], ctx["requests"])
        if not res.ok:
            if page == 0:
                return None, res.error, res.status, None
            break                                # partial result beats none
        body = res.data
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            if page == 0:
                return None, "unexpected shape (no 'items' array)", res.status, None
            break
        items = body["items"]
        total_pages = body.get("totalPages", 1) or 1
        if raw_keys is None:
            raw_keys = sorted({k for j in items if isinstance(j, dict) for k in j})

        for job in items:
            if not isinstance(job, dict):
                continue
            p = base.blank_posting()
            p["ats_job_id"] = job.get("id")
            p["title_raw"] = job.get("name")
            p["department_raw"] = (job.get("department") or {}).get("name")
            locs = job.get("locations") or []
            p["location_raw"] = ", ".join(
                l.get("name") for l in locs if isinstance(l, dict) and l.get("name")
            ) or None
            wtypes = sorted({l.get("workplaceType") for l in locs
                            if isinstance(l, dict) and l.get("workplaceType")})
            p["workplace_type_raw"] = wtypes[0] if len(wtypes) == 1 else (
                "/".join(wtypes) if wtypes else None)
            p["url"] = job.get("url")

            if p["ats_job_id"]:
                dres = base.fetch_json(f"{API_BASE}/{token}/jobs/{p['ats_job_id']}",
                                       ctx["limiter"], ctx["requests"])
                if dres.ok and isinstance(dres.data, dict):
                    detail = dres.data
                    p["detail_fetched"] = True
                    p["posted_at_raw"] = detail.get("createdOn")
                    p["posted_at"] = base.iso_utc(detail.get("createdOn"))
                    p["posted_at_source"] = "createdOn (detail)"
                    tiers = detail.get("payRangeDetails") or None
                    p["comp_raw_tiers"] = tiers
                    p["comp_data_quality"] = base.comp_quality(tiers, None)
                    desc = detail.get("description") or {}
                    base.attach_description_comp(
                        p, desc.get("company"), desc.get("role"))
                    if detail.get("employmentType", {}).get("id"):
                        p["provider_extra"]["employmentType"] = \
                            detail["employmentType"]["id"]
                    dept_tree = (detail.get("department") or {}).get("department_tree")
                    if dept_tree and dept_tree != [p["department_raw"]]:
                        p["provider_extra"]["department_tree"] = dept_tree
                else:
                    p["provider_extra"]["detail_error"] = dres.error or "detail failed"
            postings.append(p)
        page += 1
    return postings, None, 200, raw_keys


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fetch live Rippling postings for the companies the census found.")
    ap.add_argument("--resolve", action="store_true",
                    help="only resolve tokens (step 1), don't fetch postings")
    ap.add_argument("--limit", type=int, default=10,
                    help="companies in this batch (default 10)")
    ap.add_argument("--all", action="store_true", help="run the entire resolved set")
    ap.add_argument("--interval", type=float, default=0.6)
    ap.add_argument("--label", default=None)
    args = ap.parse_args(argv)

    resolved = load_resolved_tokens()
    if args.resolve or not resolved:
        print("resolving Rippling board tokens from careers pages "
              "(the census only recorded the host, not the token)...")
        resolved = resolve_all_tokens(args.interval)
        if args.resolve:
            return 0

    batch = resolved if args.all else resolved[:args.limit]
    print(f"\n{len(resolved)} tokens resolved; fetching postings for "
          f"{len(batch)} companies\n")

    ctx = {"limiter": base.HostRateLimiter(1.0 / args.interval), "requests": [0]}
    results = []
    started = base.datetime.now(base.timezone.utc)
    for i, (domain, token) in enumerate(batch, 1):
        entry = {"company_domain": domain, "ats_provider": "rippling",
                 "ats_token": token, "status": "ok", "error": None,
                 "posting_count": 0, "postings": []}
        t0 = time.monotonic()
        try:                                         # SPEC.md 3.7
            postings, error, status, raw_keys = fetch_rippling(token, ctx)
            if error:
                entry.update(status="error", error=error)
            else:
                entry["postings"] = postings
                entry["posting_count"] = len(postings)
        except Exception as exc:
            entry.update(status="error", error=f"unhandled {type(exc).__name__}: {exc}")
        elapsed = round(time.monotonic() - t0, 2)
        if entry["status"] == "ok":
            comp = sum(1 for p in entry["postings"] if p["comp_data_quality"] != "none")
            desc_comp = sum(1 for p in entry["postings"]
                            if p["comp_in_description_confident"])
            print(f"[{i:>3}/{len(batch)}] {token:24} {domain:26} "
                  f"{entry['posting_count']:>3} postings  "
                  f"comp(structured) {comp:>2}  comp(desc) {desc_comp:>2}  "
                  f"({elapsed}s)")
        else:
            print(f"[{i:>3}/{len(batch)}] {token:24} {domain:26} "
                  f"FAILED  {entry['error']}  ({elapsed}s)")
        results.append(entry)

    ok = [r for r in results if r["status"] == "ok"]
    all_postings = [p for r in ok for p in r["postings"]]
    redactions = [0]
    run = {
        "spike": "iteration11_rippling",
        "label": args.label,
        "started_at": started.isoformat(),
        "companies_attempted": len(batch),
        "companies_ok": len(ok),
        "companies_failed": len(results) - len(ok),
        "total_postings": len(all_postings),
        "http_requests": ctx["requests"][0],
        "field_coverage": {
            f: sum(1 for p in all_postings if p[f])
            for f in ("title_raw", "department_raw", "location_raw",
                      "workplace_type_raw", "url", "posted_at")
        },
        "comp_data_quality": dict(collections.Counter(
            p["comp_data_quality"] for p in all_postings)),
        "comp_in_description_confident": sum(
            1 for p in all_postings if p["comp_in_description_confident"]),
    }
    payload = base.redact({"run": run, "companies": results}, redactions)
    payload["run"]["emails_redacted"] = redactions[0]

    label = args.label or ("all" if args.all else f"limit{args.limit}")
    out = os.path.join(HERE, f"iteration11_rippling_{label}_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n--- run summary ---")
    print(f"companies: {run['companies_ok']} ok / {run['companies_failed']} failed")
    print(f"postings:  {run['total_postings']}")
    print(f"requests:  {run['http_requests']}")
    print(f"coverage:  {run['field_coverage']}")
    print(f"comp:      {run['comp_data_quality']}  "
          f"(+{run['comp_in_description_confident']} in description)")
    print(f"redacted:  {redactions[0]} email-shaped strings")
    print(f"wrote:     {os.path.relpath(out, os.path.dirname(HERE))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
