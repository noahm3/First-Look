"""
Iteration 6 spike: for each discovered company (spikes/discovered_companies.csv),
find its own careers page and detect which ATS it runs - Greenhouse, Lever, or
Ashby to start - using the same cascade shape SPEC.md section 8.1 designs for
the real system: slug guess -> careers-page regex -> classified failure, never
a silent drop. Reuses the fetch pattern from iteration1_ats_spike.py and the
careers-page-finding logic from iteration3_vc_board_discovery.py (href regex +
subdomain-first fallback guessing), applied to a plain company domain instead
of a VC site.

Validation follows SPEC.md section 8.2's three confidence levels
(verified/probable/weak) plus the negative guard for short/collision-prone
slugs. Confirmed live 2026-09-22 before writing this: Greenhouse's
/v1/boards/{token} returns a "name" field usable for a probable fuzzy match,
but Ashby's public job-board API does NOT return any organization-name field
(only {"jobs": [...], "apiVersion": ...}) - this contradicts SPEC.md section
8.2's claim that "Ashby carries the org name." Lever's list endpoint has no
company-name field either. So only Greenhouse can reach "probable" from the
API alone; Lever and Ashby slug guesses cap at "weak" unless the company's own
careers page independently references the same token, which promotes the
result to "verified" instead.

Only Greenhouse/Lever/Ashby are guessed at in stage 1 (SmartRecruiters and
other ATSes are detection-only, via stage 3's careers-page regex, per this
spike's scope - no polling adapter exists for them regardless).

Run: python spikes/iteration6_ats_mapping_spike.py [start] [end] [--recheck]
  start/end index into the list of NOT-YET-CHECKED companies (i.e. rows with
  no last_checked_at), in discovered_companies.csv file order - so re-running
  with the same start/end after a batch naturally advances to the next batch.
  --recheck processes already-checked rows again instead of skipping them.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse

import tracking_store as ts

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# SPEC.md section 8.2's negative guard: a short or common-word slug can return
# an unrelated company's real board (confirmed for real in the 2026-09-21
# Getro-slug-guessing spike - lowercarbon/prelude/closedloop). A guess on one
# of these may only be accepted at "verified," never "probable."
COLLISION_WORDS = {"atlas", "square", "ramp", "notion", "arc", "level", "front", "scale"}
MIN_SLUG_LEN = 6

# Same bugs already found and fixed in iteration3_vc_board_discovery.py apply
# here verbatim: the keyword must be a whole path segment (not a substring -
# the AgFunder CSS-file bug), and asset extensions are excluded.
JOB_HREF_PATTERN = re.compile(
    r'href="([^"?#]*/(?:jobs?|careers?|open-positions?)(?:/[^"?#]*)?(?:\?[^"]*)?)"',
    re.I,
)
ASSET_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".woff", ".woff2")
FALLBACK_PATHS = ["/careers", "/jobs", "/company/careers", "/about/careers"]

# Found live 2026-09-22: jetzero.au fuzzy-name-matched a real Greenhouse
# board ("JetZero") at "probable" confidence, but jetzero.au is actually a
# suspended-hosting parked domain with no connection to the real company
# (jetzero.com) - the fuzzy match only compares strings, never checks whether
# the discovered domain is a live site at all. Same class of problem as the
# short/collision-word guard (SPEC.md 8.2): force these to require
# "verified" too, never accepted at "probable" on name-match alone.
PARKED_DOMAIN_PATTERN = re.compile(
    r"account suspended|domain (?:is )?(?:for sale|parked)|buy this domain|"
    r"this (?:web ?site|domain) (?:is )?(?:currently )?(?:unavailable|suspended|disabled)|"
    r"pending renewal or deletion",
    re.I,
)

# Stage 3: the three supported providers (token extracted from the URL), plus
# other recognizable ATS domains fed into unsupported_ats:{name} per SPEC.md
# section 8.4 rather than losing that signal.
SUPPORTED_ATS_PATTERNS = {
    "greenhouse": re.compile(
        r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I
    ),
    "lever": re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.I),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.I),
}
OTHER_ATS_DOMAINS = {
    "smartrecruiters": re.compile(r"smartrecruiters\.com", re.I),
    "workday": re.compile(r"myworkdayjobs\.com", re.I),
    "workable": re.compile(r"workable\.com", re.I),
    "recruitee": re.compile(r"recruitee\.com", re.I),
    "breezy": re.compile(r"breezy\.hr", re.I),
    "bamboohr": re.compile(r"bamboohr\.com", re.I),
    "personio": re.compile(r"personio\.", re.I),
    "applytojob": re.compile(r"applytojob\.com", re.I),
    # Found live 2026-09-22 via manual spot-check of the "unknown" bucket:
    "polymer": re.compile(r"polymer\.co", re.I),               # addisenergy.com
    "careers-page": re.compile(r"careers-page\.com", re.I),    # mati.earth (India-focused; deprioritized per user)
    "pyjamahr": re.compile(r"pyjamahr\.com", re.I),             # unifyndlabs.com
    "phenompeople": re.compile(r"phenompeople\.com", re.I),    # nature.org's careers.tnc.org, one hop deep - see NOTE below
    # Found live 2026-09-22 via the random-sample review of no_careers_page/unknown:
    "rippling": re.compile(r"ats\.rippling\.com", re.I),       # getdelos.com
    "linkedin-jobs": re.compile(r"linkedin\.com/(?:company/[^/\"]+/jobs|jobs/)", re.I),  # xplorobot.com -
    # not a real ATS and never pollable (SPEC.md section 4 rules out LinkedIn
    # scraping entirely) - measurement only, same as every other entry here.
}
# Restored from iteration3_vc_board_discovery.py's fingerprint() - dropped
# when this script was written from scratch, then found missing again via
# genh2.com (RSS feed + wp-job-manager CSS/JS handles, no literal ATS domain
# to match on).
WORDPRESS_JOB_MANAGER_PATTERN = re.compile(r"job_listing|wp-job-manager|feed=job_feed", re.I)


def fetch(url: str, timeout: int = 6) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def fetch_json(url: str, timeout: int = 6):
    status, body = fetch(url, timeout)
    if status != 200 or not body:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, None


def domain_label(domain: str) -> str:
    return domain.split(".")[0].lower()


def slug_candidates(domain: str) -> list[str]:
    """SPEC.md section 8.1's two cheap slug variants, applied to the domain's
    second-level label since discovered_companies.csv has no clean company
    name field - only domain/website. SPEC.md itself notes the domain
    candidate hits more often than name-derived ones anyway."""
    label = domain_label(domain)
    stripped = re.sub(r"[^a-z0-9]", "", label)
    candidates = [label]
    if stripped and stripped != label:
        candidates.append(stripped)
    return candidates


def fuzzy_name_match(label: str, returned_name: str | None) -> bool:
    if not returned_name:
        return False
    a = re.sub(r"[^a-z0-9]", "", label.lower())
    b = re.sub(r"[^a-z0-9]", "", returned_name.lower())
    if not a or not b:
        return False
    return a in b or b in a


def guard_requires_verified(token: str) -> bool:
    return len(token) < MIN_SLUG_LEN or token.lower() in COLLISION_WORDS


def try_greenhouse(token: str) -> dict | None:
    status, data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{token}")
    if status != 200 or not isinstance(data, dict):
        return None
    return {"name": data.get("name")}


def try_lever(token: str) -> dict | None:
    status, data = fetch_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    if status != 200 or not isinstance(data, list):
        return None
    return {"name": None}  # no company-name field - confirmed live 2026-09-22


def try_ashby(token: str) -> dict | None:
    status, data = fetch_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false"
    )
    if status != 200 or not isinstance(data, dict) or "jobs" not in data:
        return None
    return {"name": None}  # no org-name field - confirmed live 2026-09-22,
    # contradicts SPEC.md section 8.2's "Ashby carries the org name"


PROVIDER_CHECKS = {
    "greenhouse": try_greenhouse,
    "lever": try_lever,
    "ashby": try_ashby,
}


def find_jobs_link(homepage_url: str, html: str) -> str | None:
    for href in JOB_HREF_PATTERN.findall(html):
        if href.startswith("mailto:"):
            continue
        if href.lower().split("?")[0].endswith(ASSET_EXTENSIONS):
            continue
        return urljoin(homepage_url, href)
    return None


def registrable_root(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def fallback_candidates(website: str) -> list[str]:
    root = registrable_root(website)
    scheme = urlparse(website).scheme or "https"
    return [f"{scheme}://{root}{path}" for path in FALLBACK_PATHS]


def find_careers_page(website: str) -> dict:
    """Returns {'url', 'html', 'reason', 'note', 'parked'}. 'reason'/'note' are
    only set when 'url' is None - a section-8.4 failure code plus a
    human-readable detail, used only if stage 1 (slug guessing) also finds
    nothing. 'parked' flags a dead/suspended-hosting homepage regardless of
    whether a careers page was otherwise found - see PARKED_DOMAIN_PATTERN."""
    status, html = fetch(website)
    parked = bool(html and PARKED_DOMAIN_PATTERN.search(html))
    if status != 200 or not html:
        return {"url": None, "html": "", "reason": "no_careers_page",
                "note": f"homepage fetch failed (status {status})", "parked": parked}

    # Found live 2026-09-22 (loamist.com): a "Careers" link can resolve to a
    # page byte-identical to the homepage - a same-page anchor/placeholder
    # link, or an SPA that serves the same shell for every route. That's not
    # a real distinct page, so don't treat it as a successful find.
    linked = find_jobs_link(website, html)
    if linked:
        lstatus, lhtml = fetch(linked)
        if lstatus == 200 and lhtml and lhtml != html:
            return {"url": linked, "html": lhtml, "reason": "", "note": "", "parked": parked}

    for candidate in fallback_candidates(website):
        cstatus, chtml = fetch(candidate)
        if cstatus == 200 and chtml and chtml != html:
            return {"url": candidate, "html": chtml, "reason": "", "note": "", "parked": parked}

    if len(html) < 1000:
        return {"url": None, "html": html, "reason": "js_rendered",
                "note": "homepage tiny / likely JS-rendered shell, no jobs/careers link found",
                "parked": parked}
    return {"url": None, "html": html, "reason": "no_careers_page",
            "note": "homepage fetched, no jobs/careers link found, fallback paths also failed",
            "parked": parked}


def detect_ats_from_html(html: str) -> tuple[str, str | None]:
    for provider, pattern in SUPPORTED_ATS_PATTERNS.items():
        m = pattern.search(html)
        if m:
            return provider, m.group(1)
    for name, pattern in OTHER_ATS_DOMAINS.items():
        if pattern.search(html):
            return name, None
    if WORDPRESS_JOB_MANAGER_PATTERN.search(html):
        return "wordpress-wp-job-manager", None
    return "", None


def classify_and_map(domain: str, website: str) -> dict:
    """Runs the full cascade (stage 1 slug guess, stage 3 careers-page regex -
    stage 2 apply-redirect is N/A, these aren't Built In postings). Returns a
    dict with careers_page_url, ats_provider, ats_token, mapping_confidence,
    mapping_method, mapping_failure_reason, notes - exactly one of
    (mapping_confidence) or (mapping_failure_reason) is non-empty."""
    result = {
        "careers_page_url": "",
        "ats_provider": "",
        "ats_token": "",
        "mapping_confidence": "",
        "mapping_method": "",
        "mapping_failure_reason": "",
        "notes": "",
    }

    label = domain_label(domain)

    stage1_hit = None  # (provider, token, api_result)
    for candidate in slug_candidates(domain):
        for provider, check in PROVIDER_CHECKS.items():
            api_result = check(candidate)
            if api_result is not None:
                stage1_hit = (provider, candidate, api_result)
                break
        if stage1_hit:
            break

    # Stage 3 always runs: it's both the fallback when stage 1 finds nothing,
    # and the corroborating "verified" source when stage 1 does.
    careers = find_careers_page(website)
    careers_provider, careers_token = ("", None)
    if careers["html"]:
        careers_provider, careers_token = detect_ats_from_html(careers["html"])

    if stage1_hit:
        provider, token, api_result = stage1_hit
        needs_verified = guard_requires_verified(token) or careers["parked"]
        corroborated = (
            careers_provider == provider
            and careers_token is not None
            and careers_token.lower() == token.lower()
        )
        probable = (not needs_verified) and fuzzy_name_match(label, api_result.get("name"))

        result["careers_page_url"] = careers["url"] or ""
        result["ats_provider"] = provider
        result["ats_token"] = token

        if corroborated:
            result["mapping_confidence"] = "verified"
            result["mapping_method"] = "slug_guess+careers_page_corroboration"
        elif probable:
            result["mapping_confidence"] = "probable"
            result["mapping_method"] = "slug_guess+name_match"
        else:
            result["mapping_failure_reason"] = "weak_only"
            result["mapping_method"] = "slug_guess"
            guard_reasons = []
            if guard_requires_verified(token):
                guard_reasons.append("collision-guarded")
            if careers["parked"]:
                guard_reasons.append("discovered domain looks dead/parked")
            result["notes"] = (
                f"guessed token {token!r} on {provider}, unconfirmed"
                + (f" ({'; '.join(guard_reasons)})" if guard_reasons else "")
            )
        return result

    # No stage-1 hit: rely on stage 3 alone.
    if careers_provider in SUPPORTED_ATS_PATTERNS:
        token = careers_token
        needs_verified = guard_requires_verified(token) or careers["parked"]
        result["careers_page_url"] = careers["url"] or ""
        result["ats_provider"] = careers_provider
        result["ats_token"] = token

        # A token scraped off a careers page is NOT self-validating, even
        # though the page is the company's own. It can name a board that has
        # since been renamed or closed, embed a third-party widget carrying
        # somebody else's token, or hand the regex a wrong substring.
        #
        # Measured 2026-09-22 by iteration 7, which fetched all 584 mapped
        # boards: **all 30 dead tokens came from this stage and zero from
        # stage 1** - a perfectly clean split, because stage 1 has always
        # called the provider and this branch never did. ~5% of the mapped
        # set was pointing at boards that do not exist, at "verified".
        # SPEC.md 3.8: an unmapped company is a known gap, a wrongly-mapped
        # one is invisible bad data nobody catches for two months.
        api_result = PROVIDER_CHECKS[careers_provider](token)
        if api_result is None:
            result["mapping_failure_reason"] = "weak_only"
            result["mapping_method"] = "careers_page_regex"
            result["notes"] = (
                f"careers page names token {token!r} on {careers_provider}, "
                f"but that board does not resolve"
            )
            return result

        if not needs_verified:
            # The company's own careers page naming its own ATS token, AND
            # that board resolving live, are the two independent sources
            # SPEC.md 8.2 asks for. The second half of that was missing until
            # 2026-09-22; the page alone was being treated as sufficient.
            result["mapping_confidence"] = "verified"
            result["mapping_method"] = "careers_page_regex"
            if careers_provider == "greenhouse" and not fuzzy_name_match(
                    label, api_result.get("name")):
                # Not disqualifying - a rebrand that kept the old slug is
                # real and correct (voltacharging.com -> lever "joltcharge").
                # Recorded so the review pass can eyeball it.
                result["notes"] = (
                    f"board resolves but its name "
                    f"{api_result.get('name')!r} does not match {label!r}"
                )
        else:
            result["mapping_failure_reason"] = "weak_only"
            result["mapping_method"] = "careers_page_regex"
            result["notes"] = f"careers page names token {token!r} on {careers_provider}, collision-guarded"
        return result

    if careers_provider:  # a recognized-but-unsupported ATS domain
        result["careers_page_url"] = careers["url"] or ""
        result["mapping_failure_reason"] = f"unsupported_ats:{careers_provider}"
        return result

    result["careers_page_url"] = careers["url"] or ""
    result["mapping_failure_reason"] = careers["reason"] or "unknown"
    result["notes"] = careers["note"]
    return result


def is_excluded_domain(domain: str) -> str | None:
    """Returns an exclusion note, or None if the domain should be processed.
    Per the user's 2026-09-22 review of the first 45 results: most .org hits
    so far were industry associations / advocacy groups, not real hiring
    companies - not worth spending crawl budget on (SPEC.md section 7's
    "source selection is a sourcing decision, not user criteria" applies
    here). Note: this is a blunt rule - rmi.org is a counterexample, a real
    nonprofit that hires and mapped cleanly to unsupported_ats:workday in the
    same batch - so it's worth revisiting per-domain if .org coverage turns
    out to matter."""
    if domain.split(".")[-1].lower() == "org":
        return "excluded: .org domain (assumed non-profit/institutional, not a target company)"
    return None


def main():
    args = [a for a in sys.argv[1:] if a != "--recheck"]
    recheck = "--recheck" in sys.argv[1:]
    start = int(args[0]) if len(args) > 0 else 0
    end = int(args[1]) if len(args) > 1 else start + 15

    all_companies = ts.list_companies()
    pending = all_companies if recheck else [
        c for c in all_companies if not c.get("last_checked_at")
    ]
    batch = pending[start:end]

    print(f"{len(all_companies)} total companies, {len(pending)} pending, "
          f"processing batch [{start}:{end}] = {len(batch)} companies\n")

    results = []
    for company in batch:
        domain = company["company_domain"]
        website = company.get("company_website") or f"https://{domain}"

        exclusion = is_excluded_domain(domain)
        if exclusion:
            mapping = {
                "careers_page_url": "", "ats_provider": "", "ats_token": "",
                "mapping_confidence": "", "mapping_method": "",
                "mapping_failure_reason": "", "notes": exclusion,
            }
        else:
            mapping = classify_and_map(domain, website)

        row = {"company_domain": domain, "company_website": website, **mapping}
        results.append(row)
        print(json.dumps(row, indent=2))
        ts.update_company_mapping(domain, **mapping)
        if not exclusion:
            time.sleep(0.5)

    out_path = f"iteration6_batch_{start}_{end}_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {len(results)} results to {out_path}")

    confidences = [r["mapping_confidence"] for r in results if r["mapping_confidence"]]
    failures = [r["mapping_failure_reason"] for r in results if r["mapping_failure_reason"]]
    print(f"\n{len(confidences)}/{len(results)} mapped ({confidences.count('verified')} verified, "
          f"{confidences.count('probable')} probable)")
    for reason in sorted(set(failures)):
        print(f"  {reason}: {failures.count(reason)}")


if __name__ == "__main__":
    main()
