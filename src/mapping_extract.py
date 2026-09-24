"""Stage 3 evidence: which ATS boards and platforms does a careers page point at?

Pure string work on raw HTML -- no network. Two outputs:

* ``tokens`` -- (provider, token) pairs for the 8 supported providers, taken
  only from URL shapes that actually carry a board token. A provider's name
  appearing in the page is not evidence (CircleCI's only "greenhouse" was a
  cookie/CSP allowlist entry, DEVLOG M1), and neither is its asset or
  marketing host (`staticfe.bamboohr.com`, `www.workable.com`).
* ``unsupported`` -- names of unsupported ATS platforms whose hosts appear in
  a URL on the page, for SPEC.md §8.4's `unsupported_ats:{name}` distribution.

Found tokens are not trusted here; src/mapping_validate.py decides what they
are worth once each has been probed.
"""

import html
import re
from dataclasses import dataclass

from src.mapping_validate import is_valid_token
from src.models import AtsProvider

P = AtsProvider

# Not preceded by another host character: the captured label is the whole
# leftmost subdomain, not the tail of a longer one.
_HOST_START = r"(?<![a-z0-9.-])"

# Subdomains of tenant-per-subdomain providers that are the provider's own
# infrastructure or marketing, never a customer's board.
_NON_TENANT = {
    P.BAMBOOHR: frozenset(
        {"www", "staticfe", "static", "app", "api", "help", "partners", "marketplace"}
        | {"resources", "status", "go", "info", "marketing", "signup", "login", "careers"}
    ),
    P.WORKABLE: frozenset(
        {"www", "jobs", "apply", "resources", "help", "api", "app", "careers", "status"}
    ),
    P.BREEZY_HR: frozenset(
        {"www", "app", "api", "marketing", "help", "assets", "attachments", "developer", "blog"}
    ),
}
# apply.workable.com/j/{shortcode} is a single job, not an account.
_WORKABLE_NON_ACCOUNT_PATHS = frozenset({"j", "api", "careers", "jobs"})

_TOKEN_PATTERNS: tuple[tuple[AtsProvider, re.Pattern[str], frozenset[str]], ...] = tuple(
    (provider, re.compile(pattern, re.I), exclude)
    for provider, pattern, exclude in (
        (
            P.GREENHOUSE,
            r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/embed/job_board(?:/js)?"
            r"\?(?:[^\"'\s<>]*?&)?for=([a-z0-9_-]+)",
            frozenset(),
        ),
        (
            P.GREENHOUSE,
            r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/([a-z0-9_-]+)",
            frozenset(),
        ),
        (P.GREENHOUSE, r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)", frozenset()),
        (P.LEVER, r"jobs\.lever\.co/([a-z0-9_-]+)", frozenset()),
        (P.LEVER, r"api\.lever\.co/v0/postings/([a-z0-9_-]+)", frozenset()),
        (P.ASHBY, r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", frozenset()),
        (P.ASHBY, r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9_-]+)", frozenset()),
        # Rippling's shapes, from spikes/iteration11_rippling_spike.py (62/62
        # resolved): the API call in inline JS, the embed attribute, and the
        # hosted board with optional /embed/ and locale prefixes.
        (
            P.RIPPLING,
            r"api\.rippling\.com/platform/api/ats/v2/board/([a-z0-9][a-z0-9-]*)/jobs",
            frozenset(),
        ),
        (P.RIPPLING, r"data-job-board-id=[\"']*([a-z0-9][a-z0-9-]*)", frozenset()),
        (
            P.RIPPLING,
            r"ats\.rippling\.com/(?:embed/)?(?:[a-z]{2}(?:-[a-z]{2})?/)?([a-z0-9][a-z0-9-]{2,})"
            r"(?=[/?\"'\s<>]|$)",
            frozenset(),
        ),
        (P.BAMBOOHR, _HOST_START + r"([a-z0-9][a-z0-9-]*)\.bamboohr\.com", _NON_TENANT[P.BAMBOOHR]),
        (
            P.WORKABLE,
            r"apply\.workable\.com/(?:api/v\d+/(?:widget/)?accounts/)?([a-z0-9_-]+)",
            _WORKABLE_NON_ACCOUNT_PATHS,
        ),
        (P.WORKABLE, _HOST_START + r"([a-z0-9][a-z0-9-]*)\.workable\.com", _NON_TENANT[P.WORKABLE]),
        (
            P.PERSONIO,
            _HOST_START + r"([a-z0-9][a-z0-9-]*\.jobs\.personio\.(?:de|com))",
            frozenset(),
        ),
        (P.BREEZY_HR, _HOST_START + r"([a-z0-9][a-z0-9-]*)\.breezy\.hr", _NON_TENANT[P.BREEZY_HR]),
    )
)

# Hosts of the supported providers -- never reported as "unsupported".
_SUPPORTED_HOST = re.compile(
    r"(?:^|\.)(?:greenhouse\.io|lever\.co|ashbyhq\.com|rippling\.com|ripplingcdn\.com|"
    r"bamboohr\.com|workable\.com|personio\.(?:de|com)|breezy\.hr)$"
)

# Unsupported platforms, matched against URL *hosts* only (not prose), from
# spikes/ats_platform_hosts.csv and the iteration 6 unknown-bucket sampling.
_UNSUPPORTED_HOSTS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(r"(?:^|\.)(?:" + pattern + r")$"))
    for name, pattern in (
        ("smartrecruiters", r"smartrecruiters\.com"),
        ("workday", r"myworkdayjobs\.com|myworkdaysite\.com|myworkday\.com"),
        ("icims", r"icims\.com"),
        ("teamtailor", r"teamtailor\.com|teamtailor-cdn\.com"),
        ("recruitee", r"recruitee\.com"),
        ("jazzhr", r"applytojob\.com|jazzhr\.com"),
        ("jobvite", r"jobvite\.com"),
        ("gem", r"jobs\.gem\.com"),
        ("adp", r"workforcenow\.adp\.com|myjobs\.adp\.com"),
        ("ukg", r"ukg\.com|ultipro\.com|ukg\.net"),
        ("dayforce", r"dayforcehcm\.com"),
        ("taleo", r"taleo\.net"),
        ("successfactors", r"successfactors\.com|successfactors\.eu|sapsf\.com"),
        ("paylocity", r"paylocity\.com"),
        ("paycor", r"recruitingbypaycor\.com"),
        ("pinpoint", r"pinpointhq\.com"),
        ("polymer", r"polymer\.co"),
        ("pyjamahr", r"pyjamahr\.com"),
        ("careers-page", r"careers-page\.com"),
        ("phenompeople", r"phenompeople\.com"),
        ("homerun", r"homerun\.co"),
        ("join", r"join\.com"),
        ("softgarden", r"softgarden\.io|softgarden\.de"),
        ("factorial", r"factorialhr\.com"),
        ("hibob", r"hibob\.com"),
        ("jobscore", r"jobscore\.com"),
        ("comeet", r"comeet\.com|comeet\.co"),
        ("trakstar", r"trakstar\.com|recruiterbox\.com"),
        ("zohorecruit", r"zohorecruit\.com|zohorecruit\.eu"),
        ("freshteam", r"freshteam\.com"),
    )
)
_URL_HOST = re.compile(r"(?:https?:)?//([a-z0-9][a-z0-9.-]*\.[a-z]{2,})", re.I)
_WORDPRESS_JOB_PLUGIN = re.compile(r"wp-job-manager|job_listing|wpjobboard", re.I)


@dataclass(frozen=True, slots=True)
class Extracted:
    tokens: tuple[tuple[AtsProvider, str], ...] = ()
    unsupported: tuple[str, ...] = ()


def normalize(raw: str) -> str:
    """Undo the escaping that hides URLs: HTML entities (twice -- Rippling
    embeds were seen double-escaped as `&amp;quot;`) and JSON's `\\/`."""
    text = html.unescape(html.unescape(raw))
    return text.replace("\\/", "/")


def extract(raw_html: str) -> Extracted:
    text = normalize(raw_html)

    found: dict[tuple[AtsProvider, str], None] = {}
    for provider, pattern, exclude in _TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(1).lower()
            if token in exclude or not is_valid_token(provider, token):
                continue
            found.setdefault((provider, token), None)

    unsupported: dict[str, None] = {}
    for match in _URL_HOST.finditer(text):
        host = match.group(1).lower().rstrip(".")
        if _SUPPORTED_HOST.search(host):
            continue
        for name, pattern in _UNSUPPORTED_HOSTS:
            if pattern.search(host):
                unsupported.setdefault(name, None)
                break
    if _WORDPRESS_JOB_PLUGIN.search(text):
        unsupported.setdefault("wordpress-job-plugin", None)

    return Extracted(tokens=tuple(found), unsupported=tuple(unsupported))
