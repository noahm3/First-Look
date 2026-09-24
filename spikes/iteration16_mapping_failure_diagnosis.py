"""Iteration 16: why does the M3 cascade fail? Split each failure bucket into
sub-causes before building anything to raise the hit rate.

Measurement only -- nothing in src/ changes. Re-runs `src.mapping.map_company`
on the same seeded 300-domain sample M3 measured (spikes/discovered_companies.csv,
seed 20260924, watchlist excluded), then for each failure:

* no_careers_page -> homepage outcome: dead DNS / unreachable / blocked (401,
  403, 429) / other HTTP error / 200 with a careers-ish *anchor text* our path
  regex missed / 200 with no careers link at all. Blocked homepages are retried
  once with a browser User-Agent, to measure what the honest UA costs (not to
  adopt a spoofed one). Inputs that are subdomains (cdn.x.com) are flagged --
  a discovery data-quality problem, not a mapping one.
* weak_only -> which path (uncorroborated slug guess per provider / dead page
  token / ambiguous page), and for an uncorroborated Lever or Ashby guess:
  does the board's own posting text mention the company's domain? That is the
  candidate corroboration signal for lifting weak -> probable.
* unknown -> which method, plus a tally of unrecognised third-party hosts the
  careers pages load (candidate unsupported ATSs).

Every request goes through src/http.py. Output:
spikes/iteration16_failure_diagnosis.csv (domain-level; public company data).

    python spikes/iteration16_mapping_failure_diagnosis.py --limit 300 [--offset 0]
"""

import argparse
import csv
import logging
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import mapping  # noqa: E402
from src.http import FetchClient, FetchErrorKind  # noqa: E402
from src.mapping_extract import normalize  # noqa: E402

SAMPLE_CSV = pathlib.Path("spikes/discovered_companies.csv")
OUT_CSV = pathlib.Path("spikes/iteration16_failure_diagnosis.csv")
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
CAREERS_TEXT = re.compile(
    r"\b(careers?|jobs?|join (?:us|our team|the team)|we'?re hiring|hiring|work with us|"
    r"open (?:roles|positions)|vacanc(?:y|ies)|opportunities)\b",
    re.I,
)
ANCHOR = re.compile(r"<a\b[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
URL_HOST = re.compile(r"(?:src|href)\s*=\s*[\"'](?:https?:)?//([a-z0-9.-]+\.[a-z]{2,})", re.I)
NOISE_HOST = re.compile(
    r"google|gstatic|googleapis|doubleclick|youtube|facebook|fbcdn|instagram|twitter|x\.com|"
    r"linkedin|licdn|tiktok|vimeo|cloudflare|cloudfront|jsdelivr|unpkg|bootstrapcdn|jquery|"
    r"fontawesome|typekit|fonts\.|adobe|w3\.org|schema\.org|wp\.com|wordpress|yoast|"
    r"elementor|website-files|webflow|framer|squarespace|sqspcdn|wix|shopify|hubspot|hs-|"
    r"hsforms|marketo|segment|sentry|hotjar|clarity\.ms|posthog|intercom|drift|zendesk|"
    r"cookie|onetrust|osano|usercentrics|termly|iubenda|stripe|paypal|apple\.com|"
    r"microsoft|bing|amazonaws|github|medium\.com|calendly|typekit|gravatar|recaptcha|"
    r"ahrefs|vector\.co|pinterest|reddit|spotify|imgix|cdn\.|static\.|assets\.",
    re.I,
)
_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu"}


def is_subdomain_input(domain: str) -> bool:
    labels = domain.split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL:
        return len(labels) > 3
    return len(labels) > 2


def homepage_diagnosis(client: FetchClient, browser: FetchClient, domain: str) -> tuple[str, str]:
    home = client.get(f"https://{domain}/")
    if not home.ok and not (home.status and 400 <= home.status < 500):
        www = client.get(f"https://www.{domain}/")
        if www.ok or www.status:
            home = www
    if home.error is not None and home.error.kind is FetchErrorKind.DNS_FAILURE:
        return "dead_dns", ""
    if home.error is not None and home.error.kind in (
        FetchErrorKind.TIMEOUT,
        FetchErrorKind.CONNECTION_ERROR,
    ):
        return "unreachable", home.error.kind.value
    if home.status in (401, 403, 429):
        retry = browser.get(f"https://{domain}/")
        rescued = "browser_ua_200" if retry.ok else f"browser_ua_{retry.status}"
        return f"blocked_{home.status}", rescued
    if not home.ok:
        return f"http_{home.status or home.error.kind.value}", ""
    text = normalize(home.text)
    for href, inner in ANCHOR.findall(text):
        label = " ".join(TAG.sub(" ", inner).split())
        if label and len(label) < 60 and CAREERS_TEXT.search(label):
            from urllib.parse import urljoin, urlsplit

            host = (urlsplit(urljoin(home.final_url or home.requested_url, href)).hostname or "")
            own = mapping._same_brand(host, domain) or host.endswith(domain)
            kind = "careers_link_missed" if own else "careers_link_offsite"
            return kind, f"{label!r} -> {href[:80]}"
    return "no_careers_link", f"{len(home.body)} bytes"


def posting_text_mentions(client: FetchClient, provider: str, token: str, domain: str) -> str:
    if provider == "lever":
        body = client.get(f"https://api.lever.co/v0/postings/{token}?mode=json&limit=5").json()
        jobs = body if isinstance(body, list) else []
        text = " ".join(
            f"{j.get('descriptionPlain', '')} {j.get('additionalPlain', '')}"
            for j in jobs
            if isinstance(j, dict)
        )
    elif provider == "ashby":
        body = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}").json()
        jobs = body.get("jobs", []) if isinstance(body, dict) else []
        text = " ".join(
            f"{j.get('descriptionPlain', '')} {j.get('descriptionHtml', '')}"
            for j in jobs[:5]
            if isinstance(j, dict)
        )
    else:
        return "n/a"
    if not text.strip():
        return "no_text"
    low = text.lower()
    if domain.lower() in low:
        return "domain_in_text"
    label = mapping.domain_label(domain)
    if len(label) >= 6 and re.search(rf"\b{re.escape(label)}\b", low):
        return "label_word_in_text"
    return "no_mention"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--offset", type=int, default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)

    sample = mapping._read_domains_csv(SAMPLE_CSV, 300, 20260924)
    sample = sample[args.offset : args.offset + args.limit]
    rows, sub, hosts = [], Counter(), Counter()
    client = FetchClient(timeout=10.0, max_attempts=2)
    browser = FetchClient(timeout=10.0, max_attempts=1, user_agent=BROWSER_UA)
    with client, browser:
        for i, (name, domain) in enumerate(sample, 1):
            outcome = mapping.map_company(client, name, domain)
            r = outcome.result
            reason = "accepted" if r.accepted else (r.failure_reason or "")
            subcause, detail = "", ""
            if reason == "no_careers_page":
                subcause, detail = homepage_diagnosis(client, browser, domain)
                if is_subdomain_input(domain):
                    detail = f"subdomain_input; {detail}"
            elif reason == "weak_only":
                subcause = r.method or ""
                if r.method == "slug_guess_uncorroborated" and r.provider and r.token:
                    subcause = f"uncorroborated_{r.provider.value}"
                    detail = posting_text_mentions(client, r.provider.value, r.token, domain)
                    detail = f"{r.token}: {detail}"
            elif reason == "unknown":
                subcause = r.method or ""
                if r.method == "no_ats_evidence":
                    for url in outcome.careers_urls[:2]:
                        page = client.get(url)
                        for h in {h.lower() for h in URL_HOST.findall(page.text)}:
                            if not NOISE_HOST.search(h) and mapping.domain_label(
                                h
                            ) != mapping.domain_label(domain):
                                hosts[h] += 1
            if reason != "accepted":
                sub[(reason, subcause)] += 1
            rows.append(
                {
                    "domain": domain,
                    "reason": reason,
                    "method": r.method or "",
                    "subcause": subcause,
                    "detail": detail,
                }
            )
            if i % 25 == 0:
                print(f"  ... {i}/{len(sample)}", flush=True)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["domain", "reason", "method", "subcause", "detail"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} domains, {sum(1 for r in rows if r['reason'] == 'accepted')} accepted")
    print("\nfailure sub-causes:")
    for (reason, subcause), n in sorted(sub.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print(f"  {reason:28s} {subcause:40s} {n}")
    blocked = [r for r in rows if r["subcause"].startswith("blocked_")]
    print(f"\nblocked homepages: {len(blocked)}; browser UA rescued: "
          f"{sum(1 for r in blocked if 'browser_ua_200' in r['detail'])}")
    subdomains = sum(1 for r in rows if "subdomain_input" in r["detail"])
    print(f"subdomain inputs among no_careers_page: {subdomains}")
    weak = Counter(
        r["detail"].split(": ", 1)[-1] for r in rows if r["subcause"].startswith("uncorroborated_")
    )
    print(f"uncorroborated slug hits, posting-text check: {dict(weak)}")
    print("\nunrecognised third-party hosts on no-evidence careers pages (top 25):")
    for h, n in hosts.most_common(25):
        print(f"  {n:3d}  {h}")
    print(f"\nwrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
