"""
Iteration 7 spike: fetch LIVE job postings from the public ATS APIs of the
companies that iteration 6's mapping cascade resolved to verified/probable.

Input:  spikes/discovered_companies.csv, rows where mapping_confidence is
        'verified' or 'probable' and ats_provider is greenhouse/lever/ashby.
Output: a JSON file in spikes/ plus a printed per-company summary.

This generalizes the single-hardcoded-example-per-provider fetch logic proven
in spikes/iteration1_ats_spike.py (parse_greenhouse / parse_lever /
parse_ashby) to run across a whole batch of mapped (provider, token) pairs.

Fields parsed are the ones SPEC.md section 6's `postings` table and section 9's
per-provider adapter notes name: ats_job_id, title_raw, department_raw,
location_raw, workplace_type_raw (Ashby only), url, posted_at, plus the
compensation fields section 11 describes.

DELIBERATELY NOT IN SCOPE HERE (all of it belongs to later milestones):
- No lifecycle. No first_seen_at / last_seen_at / closed_at / is_repost /
  content_hash. That is SPEC.md section 10, milestone M4, in src/, not here.
- No comp normalization, no currency conversion, no hour/week/month
  annualization, no collapsed comp_best_annual_usd / comp_floor_annual_usd,
  no filter predicate. That is SPEC.md section 11, milestone M5. Compensation
  is stored exactly as the provider published it.
- No classification and no filtering of any kind. No location_class, no
  city_raw, no alias grouping. Store raw (SPEC.md section 3.5).
- No database and no persistence beyond the JSON file this writes. In
  particular this script NEVER writes to discovered_companies.csv: iteration
  6's background mapping run may still be rewriting that file, and both
  writers rewrite it whole.
- No email, no notifications, no dashboard.

TWO THINGS CARRIED OVER FROM SPEC.md EVEN AT SPIKE SCALE, because this hits
real companies' live boards repeatedly across a batch:
- Section 9's "2-5 req/sec per provider": a per-host minimum interval between
  requests, default 3 req/sec, applied per provider host.
- Section 3.7's "no exception escapes a per-company loop": every company is
  wrapped, every detail call is wrapped, and fetch_json returns a result
  object instead of raising. One malformed board cannot end the batch.

DESCRIPTIONS ARE NEVER FETCHED OR STORED. SPEC.md section 6 discards them on
purpose (5-8KB per row). Practical second reason at spike scale: this output
gets committed to a public repo, and a job description is the one field likely
to contain a recruiter's email address or another third party's contact
details, which CLAUDE.md forbids committing.

Greenhouse is the one place a description is unavoidably fetched: `departments`
is only present on the list endpoint when `content=true` is passed, so the
request returns `content` too. That field is never read and never stored.
Lever's `description*` / `additional*` / `opening*` and Ashby's
`descriptionHtml` / `descriptionPlain` are not read at all. As a backstop,
every string written to the JSON passes through an email-shaped-string
redactor and the run reports how many it redacted.

Run:
  python spikes/iteration7_live_postings_spike.py --limit 12 --label batch1
  python spikes/iteration7_live_postings_spike.py --domain rondo.com --raw-keys
  python spikes/iteration7_live_postings_spike.py --all        # whole mapped set
"""

import argparse
import collections
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPANY_CSV = os.path.join(SPIKE_DIR, "discovered_companies.csv")

USER_AGENT = "first-look-spike/0.1 (+https://github.com/)"
TIMEOUT_S = 20
MAX_BYTES = 8 * 1024 * 1024        # response size cap, SECURITY.md S6 shape
MAX_RETRIES = 2                    # on timeout / 5xx / connection error only
SUPPORTED = ("greenhouse", "lever", "ashby")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


# --------------------------------------------------------------------------
# fetch: returns a result, never raises (SPEC.md section 3.7 / BUILD.md 3)
# --------------------------------------------------------------------------

class FetchResult:
    def __init__(self, ok, status=0, data=None, error=None, bytes_read=0):
        self.ok = ok
        self.status = status
        self.data = data
        self.error = error
        self.bytes_read = bytes_read


class HostRateLimiter:
    """Minimum interval between requests to the same host. Providers run
    sequentially in this spike, so one dict of last-request times is enough."""

    def __init__(self, req_per_sec):
        self.min_interval = 1.0 / req_per_sec if req_per_sec > 0 else 0.0
        self._last = {}
        self.waits = 0
        self.wait_seconds = 0.0

    def wait(self, url):
        host = urllib.parse.urlparse(url).netloc
        last = self._last.get(host)
        now = time.monotonic()
        if last is not None:
            gap = self.min_interval - (now - last)
            if gap > 0:
                time.sleep(gap)
                self.waits += 1
                self.wait_seconds += gap
                now = time.monotonic()
        self._last[host] = now


def fetch_json(url, limiter, requests_counter):
    """GET url, parse JSON. Retries timeouts/5xx/connection errors with
    backoff; never retries a 4xx, because a 404 is an answer (BUILD.md 3)."""
    attempt = 0
    while True:
        limiter.wait(url)
        requests_counter[0] += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    return FetchResult(
                        False, resp.status,
                        error=f"response exceeded {MAX_BYTES} byte cap",
                        bytes_read=len(raw),
                    )
                try:
                    return FetchResult(
                        True, resp.status, json.loads(raw.decode("utf-8")),
                        bytes_read=len(raw),
                    )
                except (ValueError, UnicodeDecodeError) as exc:
                    return FetchResult(
                        False, resp.status,
                        error=f"malformed JSON: {type(exc).__name__}: {exc}",
                        bytes_read=len(raw),
                    )
        except urllib.error.HTTPError as exc:
            status = exc.code
            if 400 <= status < 500 or attempt >= MAX_RETRIES:
                return FetchResult(False, status, error=f"HTTP {status}")
        except Exception as exc:                      # timeout, DNS, reset, TLS
            if attempt >= MAX_RETRIES:
                return FetchResult(False, 0, error=f"{type(exc).__name__}: {exc}")
        attempt += 1
        time.sleep(2 ** (attempt - 1))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def iso_utc(value):
    """Provider date -> ISO-8601 UTC string. Format conversion only; the
    provider's own value is always kept alongside as posted_at_raw."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):               # Lever: epoch ms
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    return None


def blank_posting():
    """Every posting dict has the same keys, so a missing provider field is a
    visible null rather than an absent key."""
    return {
        "ats_job_id": None,
        "title_raw": None,
        "department_raw": None,
        "location_raw": None,
        "workplace_type_raw": None,     # Ashby only (SPEC.md section 9)
        "url": None,
        "posted_at": None,
        "posted_at_raw": None,
        "posted_at_source": None,       # which provider field posted_at came from
        "provider_updated_at": None,    # Greenhouse updated_at: informational only
        "comp_data_quality": "none",    # structured | parsed | none (section 11)
        "comp_raw_summary": None,
        "comp_raw_tiers": None,         # verbatim, unnormalized
        "detail_fetched": False,
        "provider_extra": {},
    }


def comp_quality(tiers, summary):
    if tiers:
        return "structured"
    if summary:
        return "parsed"
    return "none"


# --------------------------------------------------------------------------
# per-provider parsers, generalized from iteration1_ats_spike.py
# --------------------------------------------------------------------------

def fetch_greenhouse(token, ctx):
    """Uses ?content=true on the LIST endpoint, which SPEC.md section 9 names
    but whose contents this spike measured directly (2026-09-22):

    - `departments` is ONLY present with content=true. The plain list has no
      department field at all, so department_raw is unobtainable without it.
    - `first_published` IS on the list endpoint, with or without content=true.
      SPEC.md section 9's "list returns only updated_at ... true
      first_published comes only from the detail endpoint" is wrong.
    - The per-job DETAIL endpoint returned a byte-identical object to the
      content=true list entry on 6/6 jobs across 2 boards - same key set, same
      values. So the detail call buys nothing, which is why --gh-detail-cap
      defaults to 0. Set it above 0 to re-verify that on a future board.
    - `pay_input_ranges` was not present on ANY of 384 live postings across 8
      mapped boards, on either endpoint. Greenhouse comp is simply absent for
      this population.

    `content` (the description) is fetched as part of the response and is
    never read or stored - see the module docstring."""
    base = f"https://boards-api.greenhouse.io/v1/boards/{token}"
    res = fetch_json(f"{base}/jobs?content=true", ctx["limiter"], ctx["requests"])
    if not res.ok:
        return None, res.error, res.status, None
    body = res.data
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
        return None, "unexpected list-endpoint shape (no 'jobs' array)", res.status, None
    jobs = body["jobs"]
    raw_keys = sorted({k for j in jobs[:25] if isinstance(j, dict) for k in j})

    postings = []
    detail_budget = ctx["gh_detail_cap"]
    for job in jobs:
        if not isinstance(job, dict):
            continue
        p = blank_posting()
        p["ats_job_id"] = str(job.get("id")) if job.get("id") is not None else None
        p["title_raw"] = job.get("title")
        depts = [d.get("name") for d in (job.get("departments") or [])
                 if isinstance(d, dict) and d.get("name")]
        p["department_raw"] = ", ".join(depts) or None
        p["location_raw"] = (job.get("location") or {}).get("name")
        p["url"] = job.get("absolute_url")
        p["provider_updated_at"] = job.get("updated_at")
        p["posted_at_raw"] = job.get("first_published")
        p["posted_at"] = iso_utc(job.get("first_published"))
        p["posted_at_source"] = "first_published (list, content=true)"
        tiers = job.get("pay_input_ranges") or None
        p["comp_raw_tiers"] = tiers
        p["comp_data_quality"] = comp_quality(tiers, None)
        if job.get("application_deadline"):
            p["provider_extra"]["application_deadline"] = job["application_deadline"]

        # Optional re-verification of the redundant detail endpoint. Off by
        # default; when on, it records whether detail actually differs.
        if detail_budget > 0 and p["ats_job_id"]:
            detail_budget -= 1
            dres = fetch_json(f"{base}/jobs/{p['ats_job_id']}",
                              ctx["limiter"], ctx["requests"])
            ctx["detail_calls"][0] += 1
            if dres.ok and isinstance(dres.data, dict):
                detail = dres.data
                p["detail_fetched"] = True
                differing = sorted(k for k in set(job) | set(detail)
                                   if k != "content" and job.get(k) != detail.get(k))
                p["provider_extra"]["detail_vs_list_differing_fields"] = differing
                if detail.get("pay_input_ranges"):
                    p["comp_raw_tiers"] = detail["pay_input_ranges"]
                    p["comp_data_quality"] = "structured"
                if ctx["raw_keys"]:
                    ctx["detail_raw_keys"]["greenhouse"].update(detail.keys())
            else:
                p["provider_extra"]["detail_error"] = dres.error or "detail fetch failed"
        postings.append(p)
    return postings, None, res.status, raw_keys


def fetch_lever(site, ctx):
    """Whole board in one call. createdAt is undocumented epoch ms and may be
    absent -> null, never a crash (BUILD.md section 6).

    Measured 2026-09-22: Lever DOES expose a structured `workplaceType`
    (onsite/remote/hybrid), populated on 47/47 postings across 4 mapped
    boards. SPEC.md section 9 calls Ashby "the only provider exposing a
    structured workplaceType", which is wrong, and section 12.3 consequently
    sends Lever down the keyword-matching path it does not need."""
    url = f"https://api.lever.co/v0/postings/{site}?mode=json"
    res = fetch_json(url, ctx["limiter"], ctx["requests"])
    if not res.ok:
        return None, res.error, res.status, None
    jobs = res.data
    if not isinstance(jobs, list):
        return None, "unexpected shape (expected a JSON array)", res.status, None
    raw_keys = sorted({k for j in jobs[:25] if isinstance(j, dict) for k in j})

    postings = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        cats = job.get("categories") or {}
        p = blank_posting()
        p["ats_job_id"] = job.get("id")
        p["title_raw"] = job.get("text")
        p["department_raw"] = cats.get("team") or cats.get("department")
        p["location_raw"] = cats.get("location")
        p["workplace_type_raw"] = job.get("workplaceType")   # present on some boards
        p["url"] = job.get("hostedUrl")
        p["posted_at_raw"] = job.get("createdAt")
        p["posted_at"] = iso_utc(job.get("createdAt"))
        p["posted_at_source"] = "createdAt (undocumented)"
        tiers = job.get("salaryRange") or None
        summary = job.get("salaryDescriptionPlain") or None
        p["comp_raw_tiers"] = tiers
        p["comp_raw_summary"] = summary
        p["comp_data_quality"] = comp_quality(tiers, summary)
        for key in ("commitment", "department", "allLocations"):
            value = cats.get(key)
            if value:
                p["provider_extra"][f"categories.{key}"] = value
        postings.append(p)
    return postings, None, res.status, raw_keys


def fetch_ashby(board, ctx):
    """Whole board, no pagination. Compensation is a human-readable summary
    string plus structured tier objects (SPEC.md section 9); both stored
    verbatim.

    Measured 2026-09-22: `compensation` is a truthy object on every posting
    even when nothing is disclosed (nulls and empty lists inside), so comp
    presence must be judged on compensationTiers / compensationTierSummary,
    never on the object itself. `shouldDisplayCompensationOnJobPostings` is
    the provider's own disclosure flag and tracks that exactly."""
    url = (f"https://api.ashbyhq.com/posting-api/job-board/"
           f"{board}?includeCompensation=true")
    res = fetch_json(url, ctx["limiter"], ctx["requests"])
    if not res.ok:
        return None, res.error, res.status, None
    body = res.data
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
        return None, "unexpected shape (no 'jobs' array)", res.status, None
    jobs = body["jobs"]
    raw_keys = sorted({k for j in jobs[:25] if isinstance(j, dict) for k in j})

    postings = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        comp = job.get("compensation") or {}
        p = blank_posting()
        p["ats_job_id"] = job.get("id")
        p["title_raw"] = job.get("title")
        p["department_raw"] = job.get("department") or job.get("team")
        p["location_raw"] = job.get("location")
        p["workplace_type_raw"] = job.get("workplaceType")
        p["url"] = job.get("jobUrl")
        p["posted_at_raw"] = job.get("publishedAt")
        p["posted_at"] = iso_utc(job.get("publishedAt"))
        p["posted_at_source"] = "publishedAt"
        summary = (comp.get("compensationTierSummary")
                   or job.get("compensationTierSummary") or None)
        tiers = (comp.get("compensationTiers")
                 or job.get("compensationTiers") or None)
        p["comp_raw_summary"] = summary
        p["comp_raw_tiers"] = tiers
        p["comp_data_quality"] = comp_quality(tiers, summary)
        if comp.get("summaryComponents"):
            p["provider_extra"]["comp_summary_components"] = comp["summaryComponents"]
        for key in ("employmentType", "isListed", "isRemote",
                    "secondaryLocations", "shouldDisplayCompensationOnJobPostings"):
            if job.get(key) not in (None, "", [], {}):
                p["provider_extra"][key] = job.get(key)
        postings.append(p)
    return postings, None, res.status, raw_keys


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


# --------------------------------------------------------------------------
# input: mapped companies
# --------------------------------------------------------------------------

def read_mapped_companies():
    """Read discovered_companies.csv defensively: iteration 6's background
    mapping run rewrites this file whole, so a read can land mid-write."""
    last_error = None
    rows = []
    for _ in range(5):
        try:
            with open(COMPANY_CSV, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows and "mapping_confidence" in rows[0]:
                break
            last_error = "header missing mapping_confidence (partial read?)"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.5)
    else:
        raise SystemExit(f"could not read {COMPANY_CSV}: {last_error}")

    mapped = []
    for row in rows:
        if row.get("mapping_confidence") not in ("verified", "probable"):
            continue
        if row.get("ats_provider") not in SUPPORTED:
            continue
        if not (row.get("ats_token") or "").strip():
            continue
        mapped.append({
            "company_domain": row.get("company_domain"),
            "ats_provider": row.get("ats_provider"),
            "ats_token": row.get("ats_token").strip(),
            "mapping_confidence": row.get("mapping_confidence"),
            "mapping_method": row.get("mapping_method"),
        })
    return mapped, len(rows)


def select_batch(mapped, limit, providers, domains):
    if domains:
        wanted = {d.lower() for d in domains}
        return [c for c in mapped if (c["company_domain"] or "").lower() in wanted]
    pool = [c for c in mapped if not providers or c["ats_provider"] in providers]
    if limit is None:
        return pool
    # Round-robin across providers so a small batch covers all three.
    buckets = collections.OrderedDict()
    for provider in SUPPORTED:
        rows = [c for c in pool if c["ats_provider"] == provider]
        if rows:
            buckets[provider] = rows
    picked = []
    while len(picked) < limit and buckets:
        for provider in list(buckets):
            if not buckets[provider]:
                del buckets[provider]
                continue
            picked.append(buckets[provider].pop(0))
            if len(picked) >= limit:
                break
    return picked


# --------------------------------------------------------------------------
# public-repo output hygiene
# --------------------------------------------------------------------------

def redact(obj, counter):
    """Backstop only. No description field is read, so nothing here is
    expected to match; if something does, it is redacted before it can reach a
    committed file, and the run reports the count."""
    if isinstance(obj, str):
        scrubbed, n = EMAIL_RE.subn("[redacted-email]", obj)
        counter[0] += n
        return scrubbed
    if isinstance(obj, dict):
        return {k: redact(v, counter) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v, counter) for v in obj]
    return obj


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fetch live postings for verified/probable-mapped companies.")
    ap.add_argument("--limit", type=int, default=12,
                    help="companies in this batch, round-robin across providers "
                         "(default 12)")
    ap.add_argument("--all", action="store_true",
                    help="run the ENTIRE mapped set instead of a batch")
    ap.add_argument("--provider", action="append", choices=SUPPORTED,
                    help="restrict to a provider (repeatable)")
    ap.add_argument("--domain", action="append",
                    help="run these exact company domains (repeatable)")
    ap.add_argument("--gh-detail-cap", type=int, default=0,
                    help="max Greenhouse per-job detail calls per company. "
                         "Default 0: the detail endpoint was measured to return "
                         "a byte-identical object to the content=true list "
                         "entry, so it buys nothing. Set above 0 to re-verify "
                         "that on a new board.")
    ap.add_argument("--rps", type=float, default=3.0,
                    help="max requests/sec per provider host, SPEC 9 says 2-5 "
                         "(default 3)")
    ap.add_argument("--label", default=None, help="label used in the output filename")
    ap.add_argument("--out", default=None, help="explicit output path")
    ap.add_argument("--raw-keys", action="store_true",
                    help="also report the raw JSON keys each provider returned, "
                         "to show what is available but unparsed")
    args = ap.parse_args(argv)

    mapped, total_rows = read_mapped_companies()
    limit = None if (args.all or args.domain) else args.limit
    batch = select_batch(mapped, limit, set(args.provider or []), args.domain)

    if not batch:
        print("No mapped companies matched the selection.")
        return 1

    print(f"discovered_companies.csv: {total_rows} rows, "
          f"{len(mapped)} verified/probable on a supported provider")
    print(f"batch: {len(batch)} companies  "
          f"({dict(collections.Counter(c['ats_provider'] for c in batch))})")
    print(f"rate limit: {args.rps} req/sec per provider host - "
          f"greenhouse detail cap: {args.gh_detail_cap}/company\n")

    ctx = {
        "limiter": HostRateLimiter(args.rps),
        "requests": [0],
        "detail_calls": [0],
        "gh_detail_cap": args.gh_detail_cap,
        "raw_keys": args.raw_keys,
        "detail_raw_keys": collections.defaultdict(set),
    }
    list_raw_keys = {}
    started = datetime.now(timezone.utc)
    results = []

    for i, company in enumerate(batch, 1):
        provider = company["ats_provider"]
        token = company["ats_token"]
        entry = dict(company)
        entry.update(status="ok", error=None, http_status=None,
                     posting_count=0, postings=[])
        t0 = time.monotonic()
        try:                                   # SPEC.md 3.7: nothing escapes
            postings, error, status, raw_keys = FETCHERS[provider](token, ctx)
            entry["http_status"] = status
            if error:
                entry.update(status="error", error=error)
            else:
                entry["postings"] = postings
                entry["posting_count"] = len(postings)
                if raw_keys and provider not in list_raw_keys:
                    list_raw_keys[provider] = raw_keys
        except Exception as exc:               # a bug in our own parser included
            entry.update(status="error",
                         error=f"unhandled {type(exc).__name__}: {exc}")
        entry["elapsed_s"] = round(time.monotonic() - t0, 2)

        if entry["status"] == "ok":
            with_comp = sum(1 for p in entry["postings"]
                            if p["comp_data_quality"] != "none")
            with_dept = sum(1 for p in entry["postings"] if p["department_raw"])
            with_date = sum(1 for p in entry["postings"] if p["posted_at"])
            with_wt = sum(1 for p in entry["postings"] if p["workplace_type_raw"])
            print(f"[{i:>3}/{len(batch)}] {provider:<10} {token:<28} "
                  f"{entry['posting_count']:>4} postings  "
                  f"dept {with_dept:>3} / date {with_date:>3} / "
                  f"wtype {with_wt:>3} / comp {with_comp:>3}  "
                  f"({entry['elapsed_s']}s)")
        else:
            print(f"[{i:>3}/{len(batch)}] {provider:<10} {token:<28} "
                  f"FAILED  {entry['error']}  ({entry['elapsed_s']}s)")
        results.append(entry)

    finished = datetime.now(timezone.utc)
    ok_rows = [r for r in results if r["status"] == "ok"]
    all_postings = [p for r in ok_rows for p in r["postings"]]
    redactions = [0]

    run = {
        "spike": "iteration7_live_postings",
        "label": args.label,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_s": round((finished - started).total_seconds(), 1),
        "mapped_pool_size": len(mapped),
        "companies_attempted": len(batch),
        "companies_ok": len(ok_rows),
        "companies_failed": len(results) - len(ok_rows),
        "companies_ok_zero_postings": sum(1 for r in ok_rows
                                          if r["posting_count"] == 0),
        "total_postings": len(all_postings),
        "http_requests": ctx["requests"][0],
        "greenhouse_detail_calls": ctx["detail_calls"][0],
        "rate_limit_req_per_sec": args.rps,
        "rate_limit_waits": ctx["limiter"].waits,
        "rate_limit_wait_seconds": round(ctx["limiter"].wait_seconds, 1),
        "greenhouse_detail_cap": args.gh_detail_cap,
        "field_coverage": {
            field: sum(1 for p in all_postings if p[field])
            for field in ("title_raw", "department_raw", "location_raw",
                          "workplace_type_raw", "url", "posted_at")
        },
        "comp_data_quality": dict(collections.Counter(
            p["comp_data_quality"] for p in all_postings)),
        "postings_by_provider": dict(collections.Counter(
            r["ats_provider"] for r in ok_rows for _ in r["postings"])),
    }
    if args.raw_keys:
        run["raw_list_keys_available"] = list_raw_keys
        run["raw_detail_keys_available"] = {
            k: sorted(v) for k, v in ctx["detail_raw_keys"].items()}

    label = args.label or ("all" if args.all else f"limit{args.limit}")
    out_path = args.out or os.path.join(
        SPIKE_DIR, f"iteration7_live_postings_{label}_results.json")
    payload = redact({"run": run, "companies": results}, redactions)
    payload["run"]["emails_redacted"] = redactions[0]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n--- run summary ---")
    print(f"companies: {run['companies_ok']} ok / {run['companies_failed']} failed"
          f"  ({run['companies_ok_zero_postings']} ok with zero postings)")
    print(f"postings:  {run['total_postings']}  {run['postings_by_provider']}")
    print(f"requests:  {run['http_requests']} "
          f"({run['greenhouse_detail_calls']} greenhouse detail), "
          f"{run['rate_limit_waits']} rate-limit waits "
          f"totalling {run['rate_limit_wait_seconds']}s")
    print(f"coverage:  {run['field_coverage']}")
    print(f"comp:      {run['comp_data_quality']}")
    print(f"redacted:  {redactions[0]} email-shaped strings")
    print(f"wrote:     {os.path.relpath(out_path, os.path.dirname(SPIKE_DIR))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
