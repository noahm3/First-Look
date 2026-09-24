"""SPEC.md §8.1: the ATS mapping cascade.

Gathers evidence for one company and hands it to src/mapping_validate.py's
`decide()` -- nothing in this module decides confidence itself.

1. **Slug guessing** against Greenhouse, Lever and Ashby, from the
   company name and the domain's second-level label.
2. **Apply-redirect** -- a deliberate no-op until M8 supplies Built In apply
   links; there is no input for it to follow yet.
3. **Careers page** -- the homepage, a careers link on it, or a fallback path;
   extract board tokens and unsupported-ATS hosts from raw HTML, then probe
   every token found.
4. **Classified failure** -- `decide()` never returns a failure without a
   reason (C-3.4).

Stages 1 and 3 both always run: a guess that "wins" stage 1 is still checked
against what the company's own careers page says, because agreement between
the two is what `verified` means and disagreement is what `ambiguous` means.
"""

import argparse
import csv
import logging
import pathlib
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from urllib.parse import urljoin, urlsplit

import yaml

from src.domain_quality import classify_input_domain
from src.http import FetchClient, FetchErrorKind, FetchResult
from src.mapping_extract import extract
from src.mapping_probe import postings_text, probe
from src.mapping_validate import (
    BoardProbe,
    CareersPage,
    Evidence,
    decide,
    mentions_domain,
    normalize_token,
)
from src.models import AtsProvider, Company, MappingFailureReason, MappingResult

log = logging.getLogger(__name__)

# Workable was in this list until the first 50-domain dry run (2026-09-24):
# three guesses per company tripped a sustained HTTP 429 on
# apply.workable.com (Retry-After: 0, still throttled minutes later), which
# then made real Workable tokens found on careers pages probe as
# `inconclusive`. Guessing cost more verified mappings than it could add, so
# Workable is probed only when a careers page names a token.
SLUG_GUESS_PROVIDERS = (
    AtsProvider.GREENHOUSE,
    AtsProvider.LEVER,
    AtsProvider.ASHBY,
)
MAX_SLUG_CANDIDATES = 3
MAX_CAREERS_LINKS = 2
MAX_OFFSITE_LINKS = 1
MAX_PAGE_TOKENS = 6
FALLBACK_PATHS = ("/careers", "/jobs", "/company/careers", "/about/careers")
FALLBACK_SUBDOMAINS = ("careers", "jobs")

# SPEC §8.1's name stripping for slug candidates, plus common legal forms.
_NAME_SUFFIXES = frozenset(
    {"inc", "llc", "ltd", "corp", "co", "gmbh", "labs", "technologies", "technology", "ai"}
)
_SECOND_LEVEL_SUFFIXES = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})

# A link whose path has a whole careers-ish segment (not a substring -- the
# iteration 3 AgFunder bug matched `careers` inside a CSS filename).
_CAREERS_SEGMENT = re.compile(
    r"/(?:careers?|jobs?|join(?:-us)?|work-with-us|open-(?:positions|roles)|hiring|vacancies)"
    r"(?:[/?#]|\.html?$|$)",
    re.I,
)
_ANCHOR = re.compile(
    r"""<a\b[^>]*?href\s*=\s*["']([^"'<>\s]+)["'][^>]*>(.*?)</a\s*>""", re.I | re.S
)
# A careers link found by its *text* -- iteration 16 found real careers links
# whose paths no segment regex could know: "Join The Team" -> /join-the-team/,
# "Work with us" -> /?page_id=3772, "Careers" -> /company#careers.
_CAREERS_TEXT = re.compile(
    r"\b(?:careers?|jobs?|join (?:us|our team|the team)|we'?re hiring|hiring|"
    r"work with us|open (?:roles|positions)|vacanc(?:y|ies))\b",
    re.I,
)
MAX_LINK_TEXT = 60
# Offsite careers links to these are profiles, not the company's careers
# page (iteration 16: LinkedIn x2, Wellfound). Never followed.
_PROFILE_HOSTS = re.compile(
    r"(?:^|\.)(?:linkedin\.com|wellfound\.com|angel\.co|glassdoor\.[a-z.]+|indeed\.[a-z.]+|"
    r"crunchbase\.com|builtin[a-z]*\.(?:com|org)|facebook\.com|twitter\.com|x\.com|"
    r"instagram\.com|youtube\.com|medium\.com|workatastartup\.com|ycombinator\.com)$"
)
_ASSET_EXT = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".woff", ".woff2")
_ATS_HOST = re.compile(
    r"(?:^|\.)(?:greenhouse\.io|lever\.co|ashbyhq\.com|rippling\.com|bamboohr\.com|"
    r"workable\.com|personio\.(?:de|com)|breezy\.hr)$"
)
# jetzero.au (DEVLOG iteration 6): a parked domain fuzzy-matched a real board.
_PARKED = re.compile(
    r"account suspended|domain (?:is )?(?:for sale|parked)|buy this domain|"
    r"this (?:web ?site|domain) (?:is )?(?:currently )?(?:unavailable|suspended|disabled)|"
    r"pending renewal or deletion",
    re.I,
)
_SCRIPT_OR_STYLE = re.compile(r"<(script|style|noscript)\b.*?</\1\s*>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
JS_RENDERED_MAX_VISIBLE_CHARS = 200


@dataclass(frozen=True, slots=True)
class MappingOutcome:
    """One company's result plus the evidence behind it, for review and stats."""

    result: MappingResult
    evidence: Evidence
    careers_urls: tuple[str, ...] = ()

    @property
    def slug_hit(self) -> bool:
        """A stage-1 guess found a live board (whatever it was later judged)."""
        return any(p.live for p in self.evidence.slug_probes)


# -- stage 1 ------------------------------------------------------------------


def domain_label(domain: str) -> str:
    """The registrable label: `cfs.energy` -> `cfs`, `acme.co.uk` -> `acme`."""
    labels = [part for part in domain.lower().split(".") if part]
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL_SUFFIXES:
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else (labels[0] if labels else "")


def slug_candidates(name: str, domain: str | None) -> list[str]:
    """Domain label first -- SPEC §8.1: it "hits noticeably more often"."""
    out: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in out:
            out.append(candidate)

    if domain:
        label = domain_label(domain)
        add(re.sub(r"[^a-z0-9-]", "", label))
        add(re.sub(r"[^a-z0-9]", "", label))
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower())]
    while len(words) > 1 and words[-1] in _NAME_SUFFIXES:
        words.pop()
    add("".join(words))
    add("-".join(words))
    return out[:MAX_SLUG_CANDIDATES]


def run_slug_guesses(client: FetchClient, name: str, domain: str | None) -> list[BoardProbe]:
    return [
        probe(client, provider, candidate)
        for candidate in slug_candidates(name, domain)
        for provider in SLUG_GUESS_PROVIDERS
    ]


# -- stage 3 ------------------------------------------------------------------


def _host(url: str | None) -> str:
    return (urlsplit(url).hostname or "").lower() if url else ""


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def _is_own(host: str, own_roots: Iterable[str]) -> bool:
    host = _strip_www(host)
    return any(host == root or host.endswith("." + root) for root in own_roots)


def _same_brand(a: str, b: str) -> bool:
    """Do two domains plausibly belong to one brand? Equal labels, or one a
    prefix of the other (galileohealth.com -> galileo.io, loyalfordogs.com ->
    loyal.com). capsule8.com -> sophos.com and voltacharging.com ->
    joltcharge.com share nothing and are not."""
    la, lb = domain_label(a), domain_label(b)
    short, long_ = sorted((la, lb), key=len)
    return la == lb or (len(short) >= 4 and long_.startswith(short))


def _visible_text_len(html: str) -> int:
    return len(" ".join(_TAG.sub(" ", _SCRIPT_OR_STYLE.sub(" ", html)).split()))


def _careers_links(
    html: str, base_url: str, own_roots: Sequence[str]
) -> tuple[list[str], list[str]]:
    """(own-site careers links, offsite careers links) found on a page.

    A link counts if its path has a careers segment *or* its anchor text says
    careers. Own-site links with a careers path come first. Offsite links to
    an ATS are skipped (the token is already in the page text), and so are
    profile sites -- a LinkedIn "Careers" link is not a careers page.
    """
    by_path: list[str] = []
    by_text: list[str] = []
    offsite: list[str] = []
    for href, inner in _ANCHOR.findall(html):
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(base_url, href)
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or not host:
            continue
        if parts.path.lower().endswith(_ASSET_EXT):
            continue
        label = " ".join(_TAG.sub(" ", inner).split())
        path_hit = bool(_CAREERS_SEGMENT.search(parts.path))
        text_hit = bool(label) and len(label) <= MAX_LINK_TEXT and bool(_CAREERS_TEXT.search(label))
        if not (path_hit or text_hit):
            continue
        url = url.split("#", 1)[0]
        if _is_own(host, own_roots):
            bucket = by_path if path_hit else by_text
        elif _ATS_HOST.search(host) or _PROFILE_HOSTS.search(host):
            continue
        else:
            bucket = offsite
        if url not in bucket:
            bucket.append(url)
    own = by_path + [u for u in by_text if u not in by_path]
    return own, offsite


@dataclass
class _PageSet:
    """Pages fetched for one company. Only own-site pages count as evidence."""

    own_roots: list[str]
    homepage: str = ""
    # (url, final_url, html, offsite) -- offsite: reached by a careers link the
    # company itself put on its site pointing at another domain.
    pages: list[tuple[str, str, str, bool]] = field(default_factory=list)

    def accept(self, result: FetchResult, *, offsite: bool = False) -> bool:
        """Keep a fetched page if it's the company's own, an ATS board it
        redirected to (ohmconnect.com/careers -> apply.workable.com/renewhome),
        or -- `offsite` -- the page its own careers link pointed at."""
        if not result.ok:
            return False
        final_host = _host(result.final_url or result.requested_url)
        if not (offsite or _is_own(final_host, self.own_roots) or _ATS_HOST.search(final_host)):
            return False
        text = result.text
        if text == self.homepage:  # loamist.com: the "careers" link served the homepage
            return False
        final = result.final_url or result.requested_url
        self.pages.append((result.requested_url, final, text, offsite))
        return True


def _homepage(client: FetchClient, domain: str) -> FetchResult:
    result = client.get(f"https://{domain}/")
    if result.ok or (result.status is not None and 400 <= result.status < 500):
        return result
    www = client.get(f"https://www.{domain}/")
    return www if www.ok else result


BLOCKED_STATUSES = frozenset({401, 403, 429})


def gather_careers_evidence(
    client: FetchClient, domain: str
) -> tuple[CareersPage, list[tuple[str, str, str, bool]]]:
    """(page status, own pages fetched). The homepage counts as a page: many
    companies link their ATS board straight from it."""
    home = _homepage(client, domain)
    if not home.ok:
        if home.error is not None and home.error.kind in (
            FetchErrorKind.TIMEOUT,
            FetchErrorKind.CONNECTION_ERROR,
        ):
            return CareersPage.INCONCLUSIVE, []
        if home.status is not None and home.status >= 500:
            return CareersPage.INCONCLUSIVE, []
        if home.status in BLOCKED_STATUSES:
            return CareersPage.BLOCKED, []
        return CareersPage.NONE, []

    home_text = home.text
    if _PARKED.search(home_text):
        return CareersPage.PARKED, []

    roots = [domain]
    redirected_root = _strip_www(_host(home.final_url))
    if redirected_root and not _is_own(redirected_root, roots):
        # The homepage left the company's domain -- the company controls that
        # redirect, so where it lands is the company's site now. That covers the
        # same brand on another TLD (algorand.com -> algorand.co), a rebrand
        # (voltacharging.com -> joltcharge.com) and an acquisition (capsule8.com
        # -> sophos.com). User's call 2026-09-24: acquisitions are let in; a
        # differently named landing domain is labelled in the method instead.
        roots.append(redirected_root)
    pages = _PageSet(own_roots=roots)
    pages.pages.append((home.requested_url, home.final_url or home.requested_url, home_text, False))
    pages.homepage = home_text

    base = home.final_url or home.requested_url
    own_links, offsite_links = _careers_links(home_text, base, roots)
    followed = 0
    for link in own_links:
        if followed >= MAX_CAREERS_LINKS:
            break
        if pages.accept(client.get(link)):
            followed += 1

    # The company's own careers link to another domain (a parent company, an
    # acquirer) -- consistent with following homepage redirects.
    if not followed:
        for link in offsite_links[:MAX_OFFSITE_LINKS]:
            if pages.accept(client.get(link), offsite=True):
                followed += 1

    if not followed:
        root = _strip_www(_host(base)) or domain
        fallbacks = [f"https://{root}{path}" for path in FALLBACK_PATHS]
        fallbacks += [f"https://{sub}.{root}/" for sub in FALLBACK_SUBDOMAINS]
        for url in fallbacks:
            if pages.accept(client.get(url)):
                followed += 1
                break

    if followed == 0 and _visible_text_len(home_text) < JS_RENDERED_MAX_VISIBLE_CHARS:
        has_evidence = extract(home_text)
        if not has_evidence.tokens and not has_evidence.unsupported:
            return CareersPage.JS_RENDERED, pages.pages
    if followed == 0:
        # Only the homepage: still evidence if it links a board directly.
        home_evidence = extract(home_text)
        if home_evidence.tokens or home_evidence.unsupported:
            return CareersPage.FOUND, pages.pages
        return CareersPage.NONE, pages.pages
    return CareersPage.FOUND, pages.pages


# -- the cascade --------------------------------------------------------------


def map_company(client: FetchClient, name: str, domain: str | None) -> MappingOutcome:
    """Run the cascade for one company. Never raises (CLAUDE.md: no exception
    escapes the per-company loop) -- an unexpected error is an `unknown`."""
    try:
        return _map_company(client, name, domain)
    except Exception as exc:
        log.exception("mapping cascade raised for one company")
        evidence = Evidence(company_name=name, careers_page=CareersPage.INCONCLUSIVE)
        return MappingOutcome(
            result=MappingResult(
                method=f"cascade_error:{type(exc).__name__}",
                failure_reason=MappingFailureReason.UNKNOWN.value,
            ),
            evidence=evidence,
        )


def _map_company(client: FetchClient, name: str, domain: str | None) -> MappingOutcome:
    if domain and classify_input_domain(domain):
        # Not a company's own site -- fail before spending any request on it.
        evidence = Evidence(company_name=name, careers_page=CareersPage.NOT_A_COMPANY)
        return MappingOutcome(result=decide(evidence), evidence=evidence)

    slug_probes = run_slug_guesses(client, name, domain)

    if not domain:
        evidence = Evidence(
            company_name=name, careers_page=CareersPage.NO_DOMAIN, slug_probes=tuple(slug_probes)
        )
        return MappingOutcome(result=decide(evidence), evidence=evidence)

    status, pages = gather_careers_evidence(client, domain)
    page_tokens: dict[tuple[AtsProvider, str], None] = {}
    own_tokens: set[tuple[AtsProvider, str]] = set()
    unsupported: dict[str, None] = {}
    for _url, final_url, html, offsite in pages:
        found = extract(html + " " + final_url)
        for pair in found.tokens:
            page_tokens.setdefault(pair, None)
            if not offsite:
                own_tokens.add(pair)
        for platform in found.unsupported:
            unsupported.setdefault(platform, None)

    known = {(p.provider, p.token): p for p in slug_probes}
    page_probes = []
    for provider, token in list(page_tokens)[:MAX_PAGE_TOKENS]:
        page_probes.append(known.get((provider, token)) or probe(client, provider, token))

    # Lever and Ashby return no org name; the board's own postings naming the
    # company's exact domain is the corroboration they can offer (iteration 16).
    domain_mentions = tuple(
        (p.provider, p.token)
        for p in slug_probes
        if p.live
        and p.provider in (AtsProvider.LEVER, AtsProvider.ASHBY)
        and (p.provider, p.token) not in page_tokens
        and mentions_domain(postings_text(client, p.provider, p.token), domain)
    )

    evidence = Evidence(
        company_name=name,
        careers_page=status,
        page_tokens=tuple(page_tokens),
        page_probes=tuple(page_probes),
        slug_probes=tuple(slug_probes),
        unsupported=tuple(unsupported),
        domain_mentions=domain_mentions,
    )
    careers_urls = tuple(final for _u, final, _h, _o in pages[1:])
    result = decide(evidence)
    chosen = (result.provider, result.token)
    if result.accepted and chosen in page_tokens and chosen not in own_tokens:
        # Found only on the page the company's careers link sent us to.
        result = replace(result, method=f"{result.method}+offsite_careers_link")
    landed = _strip_www(_host(pages[0][1])) if pages else ""
    if result.accepted and landed and not _same_brand(landed, domain):
        # Rebrand or acquisition: accepted, but visible as such in review.
        result = replace(result, method=f"{result.method}+redirected_domain")
    return MappingOutcome(result=result, evidence=evidence, careers_urls=careers_urls)


def order_for_mapping(companies: Iterable[Company]) -> list[Company]:
    """SPEC §8.3: companies with an open-roles signal first; never-attempted
    before previously attempted, oldest attempt first."""

    def key(c: Company):
        attempted = c.mapping_last_attempt_at
        return (not c.has_open_roles_signal, attempted is not None, attempted or 0)

    return sorted(companies, key=key)


# -- reporting ----------------------------------------------------------------

REVIEW_COLUMNS = ("company", "domain", "provider", "token", "confidence", "method")


def write_review_csv(path: pathlib.Path, rows: Iterable[tuple[str, str | None, MappingResult]]):
    """C-3.5: every accepted mapping, with its confidence and method. Company
    names, domains and ATS tokens are public data (SPEC §15)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(REVIEW_COLUMNS)
        for name, domain, result in rows:
            if result.accepted:
                writer.writerow(
                    (
                        name,
                        domain or "",
                        result.provider.value if result.provider else "",
                        result.token,
                        result.confidence.value if result.confidence else "",
                        result.method,
                    )
                )


def summarize(outcomes: Sequence[MappingOutcome]) -> str:
    """Counts only, never identities -- safe for a public Actions log."""
    total = len(outcomes)
    accepted = [o for o in outcomes if o.result.accepted]
    with_domain = [o for o in outcomes if o.evidence.careers_page is not CareersPage.NO_DOMAIN]
    valid = [o for o in outcomes if o.evidence.careers_page is not CareersPage.NOT_A_COMPANY]
    accepted_valid = sum(1 for o in valid if o.result.accepted)
    slug_hits = sum(o.slug_hit for o in outcomes)
    slug_accepted = sum(
        1 for o in accepted if o.result.method and o.result.method.startswith("slug_guess")
    )
    confidence = Counter(
        o.result.confidence.value if o.result.confidence else "none" for o in outcomes
    )
    reasons = Counter(o.result.failure_reason for o in outcomes if not o.result.accepted)
    providers = Counter(o.result.provider.value for o in accepted if o.result.provider)
    methods = Counter(o.result.method for o in accepted)

    def pct(n: int, d: int) -> str:
        return f"{n}/{d} ({100 * n / d:.1f}%)" if d else f"{n}/0"

    lines = [
        f"companies:            {total} ({len(with_domain)} with a domain)",
        f"cascade coverage:     {pct(len(accepted), total)} accepted (verified+probable); "
        f"{pct(accepted_valid, len(valid))} of valid inputs",
        f"slug hit rate:        {pct(slug_hits, total)} had a live stage-1 guess; "
        f"{slug_accepted} accepted via slug_guess*",
        "confidence:           " + ", ".join(f"{k}={v}" for k, v in sorted(confidence.items())),
        "accepted by provider: " + ", ".join(f"{k}={v}" for k, v in sorted(providers.items())),
        "accepted by method:   " + ", ".join(f"{k}={v}" for k, v in sorted(methods.items())),
        "failure reasons:      "
        + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])),
    ]
    return "\n".join(lines)


# -- ground-truth check (C-3.1) -------------------------------------------------

EXPECTED_PATH = pathlib.Path("config/watchlist_expected.yml")
DEFAULT_REVIEW_PATH = pathlib.Path("data/mapping_review.csv")


@dataclass(frozen=True, slots=True)
class Expected:
    provider: AtsProvider
    token: str
    zero_postings: bool = False


def load_expected(path: pathlib.Path = EXPECTED_PATH) -> dict[str, Expected]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(domain).lower(): Expected(
            provider=AtsProvider(entry["provider"]),
            token=normalize_token(AtsProvider(entry["provider"]), str(entry["token"])),
            zero_postings=bool(entry.get("zero_postings", False)),
        )
        for domain, entry in raw.items()
    }


def verdict(result: MappingResult, expected: Expected | None) -> str:
    """TP: accepted and correct. FP: accepted and wrong -- the one C-3.1 forbids.
    FN: correct answer known, not accepted (a coverage finding, not an error)."""
    if not result.accepted:
        return "FN" if expected else "TN"
    if expected and (result.provider, result.token) == (expected.provider, expected.token):
        return "TP"
    return "FP"


# -- CLI --------------------------------------------------------------------------


def _cli_client() -> FetchClient:
    # Shorter than the polling defaults: a careers page that takes 20s is
    # indistinguishable from one that isn't there, and the cascade can make
    # ~20 requests per company.
    return FetchClient(timeout=10.0, max_attempts=2)


def _map_all(
    client: FetchClient, companies: Sequence[tuple[str, str | None]]
) -> list[MappingOutcome]:
    outcomes = []
    for i, (name, domain) in enumerate(companies, 1):
        outcomes.append(map_company(client, name, domain))
        if i % 25 == 0:
            print(f"  ... {i}/{len(companies)}", flush=True)
    return outcomes


def _check_watchlist(review_path: pathlib.Path) -> int:
    from src.watchlist import canonicalize_domain, load_watchlist

    entries = load_watchlist()
    expected = load_expected()
    companies = [(e.name, canonicalize_domain(e.domain)) for e in entries]
    with _cli_client() as client:
        outcomes = _map_all(client, companies)

    counts: Counter[str] = Counter()
    print(f"{'company':28s} {'expected':42s} {'got':42s} {'confidence':10s} verdict  method")
    for (name, domain), outcome in zip(companies, outcomes, strict=True):
        exp = expected.get(domain or "")
        r = outcome.result
        v = verdict(r, exp)
        counts[v] += 1
        exp_s = f"{exp.provider.value}:{exp.token}" if exp else "-"
        got_s = f"{r.provider.value}:{r.token}" if r.provider and r.token else "-"
        conf = r.confidence.value if r.confidence else "-"
        detail = r.method if r.accepted else f"{r.method} [{r.failure_reason}]"
        print(f"{name[:28]:28s} {exp_s[:42]:42s} {got_s[:42]:42s} {conf:10s} {v:7s}  {detail}")

    write_review_csv(
        review_path, [(n, d, o.result) for (n, d), o in zip(companies, outcomes, strict=True)]
    )
    print()
    print(summarize(outcomes))
    print(
        f"verdicts:             TP={counts['TP']} FP={counts['FP']} FN={counts['FN']} "
        f"TN={counts['TN']}"
    )
    print(f"review csv:           {review_path}")
    return 1 if counts["FP"] else 0


def _read_domains_csv(path: pathlib.Path, limit: int | None, seed: int) -> list[tuple[str, str]]:
    """A dry-run sample from a spike CSV with a `company_domain` column. No
    name column exists there, so the domain label stands in for the name --
    which makes `probable` rarer than it would be with a real name."""
    import random

    from src.watchlist import canonicalize_domain

    watchlist = set(load_expected())  # measured separately by --check-watchlist
    with path.open(encoding="utf-8", newline="") as fh:
        domains = sorted(
            {d for row in csv.DictReader(fh) if (d := canonicalize_domain(row["company_domain"]))}
            - watchlist
        )
    random.Random(seed).shuffle(domains)
    if limit is not None:
        domains = domains[:limit]
    return [(domain_label(d), d) for d in domains]


def _dry_run(path: pathlib.Path, limit: int | None, seed: int, review_path: pathlib.Path) -> int:
    companies = _read_domains_csv(path, limit, seed)
    print(f"dry run: mapping {len(companies)} domains from {path} (seed {seed}); no DB writes")
    with _cli_client() as client:
        outcomes = _map_all(client, companies)
    write_review_csv(
        review_path, [(n, d, o.result) for (n, d), o in zip(companies, outcomes, strict=True)]
    )
    print(summarize(outcomes))
    print(f"review csv:           {review_path}")
    return 0


def _map_database(limit: int | None, review_path: pathlib.Path) -> int:
    from datetime import UTC, datetime

    from src.db import Database, DatabaseUnavailable

    try:
        db = Database.from_env()
        with db, _cli_client() as client:
            companies = order_for_mapping(db.companies_to_map(limit))
            outcomes = []
            for company in companies:
                outcome = map_company(client, company.name, company.canonical_domain)
                if company.id is not None:
                    db.record_mapping(company.id, outcome.result, datetime.now(UTC))
                outcomes.append(outcome)
            accepted = db.pollable_companies()
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1
    write_review_csv(
        review_path,
        [
            (
                c.name,
                c.canonical_domain,
                MappingResult(
                    provider=c.ats_provider,
                    token=c.ats_token,
                    confidence=c.mapping_confidence,
                    method=c.mapping_method,
                ),
            )
            for c in accepted
        ],
    )
    print(summarize(outcomes))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SPEC.md §8 ATS mapping cascade.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-watchlist",
        action="store_true",
        help="map config/watchlist.yml live and score it against config/watchlist_expected.yml",
    )
    mode.add_argument(
        "--domains-csv", type=pathlib.Path, help="dry run over a CSV's company_domain column"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--review-csv", type=pathlib.Path, default=DEFAULT_REVIEW_PATH)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    if args.check_watchlist:
        return _check_watchlist(args.review_csv)
    if args.domains_csv:
        return _dry_run(args.domains_csv, args.limit, args.seed, args.review_csv)
    return _map_database(args.limit, args.review_csv)


if __name__ == "__main__":
    sys.exit(main())
