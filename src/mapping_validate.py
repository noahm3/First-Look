"""SPEC.md §8.2: turn collected mapping evidence into a confidence level.

This module is pure -- no network, no database. The cascade (src/mapping.py)
gathers evidence; `decide()` alone judges it. Keeping the judgement separate
is BUILD.md M3's "write validation first": nothing here can see an HTTP status
code, so an HTTP 200 on its own can never become an accepted mapping.

The rules, in order of strength:

* ``verified`` -- a token taken from the company's *own* careers page (or the
  ATS URL that page redirected to) whose board probes live. Two independent
  sources agreeing. A name mismatch does not disqualify it: rebrands and
  acquisitions keep old tokens (Volta -> `joltcharge`, OhmConnect ->
  `renewhome`).
* ``probable`` -- a stage-1 slug guess whose live board *names* the company
  (Greenhouse board name, Workable account name), and whose token passes the
  negative guard. Lever and Ashby return no name, so a guess there can only
  ever be ``verified`` or ``weak``.
* ``weak`` -- live, but nothing corroborates. Always a mapping failure
  (``weak_only``) and never pollable -- per §3.8 a known gap beats invisible
  bad data.

A probe that failed transiently (timeout, 5xx, 429) is ``inconclusive`` and is
never treated as evidence that a board is dead: DEVLOG iteration 7 retired a
live 336-posting board on exactly that mistake.
"""

import pathlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from typing import Any

import yaml

from src.models import (
    AtsProvider,
    MappingConfidence,
    MappingFailureReason,
    MappingResult,
    unsupported_ats,
)

COLLISION_WORDS_PATH = pathlib.Path("config/collision_words.yml")
MIN_TOKEN_LEN = 6

# Providers whose board endpoint returns an organisation name we can compare
# against the company's -- the only basis for `probable`.
NAME_BEARING_PROVIDERS = frozenset({AtsProvider.GREENHOUSE, AtsProvider.WORKABLE})

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
# Confirmed live 2026-09-24: these providers' tokens are case-sensitive (Lever
# `JourneyClinical` 200, `journeyclinical` 404; Rippling `Shippo` and Workable
# `Aerones` 404). Greenhouse, Ashby, and the hostname-based providers are not,
# and are normalised to lowercase.
CASE_SENSITIVE_PROVIDERS = frozenset(
    {AtsProvider.LEVER, AtsProvider.RIPPLING, AtsProvider.WORKABLE}
)
_PERSONIO_HOST_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}\.jobs\.personio\.(?:de|com)$")
# Path words that a loose URL regex can capture as a "token" -- e.g. the
# Greenhouse `embed/job_board/js?for=` shape the iteration 6 spike misread.
_RESERVED_TOKENS = frozenset(
    {"embed", "api", "v0", "v1", "v2", "jobs", "job", "careers", "boards", "board", "js", "en"}
)

# Legal-form and filler words dropped before comparing names. SPEC §8.1 names
# Inc/Labs/Technologies/AI for slug candidates; the rest are the forms that
# actually show up in provider-returned names.
_NAME_NOISE = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "ag",
        "bv",
        "sa",
        "plc",
        "labs",
        "technologies",
        "technology",
        "ai",
        "the",
    }
)
_WORD_RE = re.compile(r"[a-z0-9]+")


class ProbeOutcome(StrEnum):
    LIVE = "live"
    NOT_FOUND = "not_found"
    NOT_A_BOARD = "not_a_board"  # 200 but not a board: BambooHR's marketing-page 302
    INCONCLUSIVE = "inconclusive"  # transient -- never evidence either way


class CareersPage(StrEnum):
    FOUND = "found"
    NONE = "none"
    NO_DOMAIN = "no_domain"
    JS_RENDERED = "js_rendered"
    PARKED = "parked"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"  # homepage answered 401/403/429
    NOT_A_COMPANY = "not_a_company"  # input rejected before any request


@dataclass(frozen=True, slots=True)
class BoardProbe:
    provider: AtsProvider
    token: str
    outcome: ProbeOutcome
    org_name: str | None = None
    posting_count: int | None = None
    detail: str | None = None

    @property
    def live(self) -> bool:
        return self.outcome is ProbeOutcome.LIVE


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything the cascade learned about one company. No judgement yet."""

    company_name: str
    careers_page: CareersPage = CareersPage.NONE
    # (provider, token) pairs extracted from the company's own careers page.
    page_tokens: tuple[tuple[AtsProvider, str], ...] = ()
    page_probes: tuple[BoardProbe, ...] = ()
    # Every stage-1 slug-guess probe, live or not.
    slug_probes: tuple[BoardProbe, ...] = ()
    # Unsupported ATS platforms seen on the careers page (SPEC §8.4).
    unsupported: tuple[str, ...] = field(default=())
    # Slug-guess boards whose own posting text contains the company's exact
    # domain -- the board declaring whose it is (iteration 16).
    domain_mentions: tuple[tuple[AtsProvider, str], ...] = ()


@cache
def load_collision_words(path: pathlib.Path = COLLISION_WORDS_PATH) -> frozenset[str]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return frozenset(str(word).strip().lower() for word in raw if str(word).strip())


def guard_requires_verified(token: str) -> bool:
    """SPEC §8.2's negative guard: short or collision-listed tokens may only
    ever be accepted at `verified`, never at `probable`. C-3.3."""
    t = token.strip().lower()
    return len(t) < MIN_TOKEN_LEN or t in load_collision_words()


def normalize_token(provider: AtsProvider, token: str) -> str:
    token = token.strip()
    return token if provider in CASE_SENSITIVE_PROVIDERS else token.lower()


def is_valid_token(provider: AtsProvider, token: str) -> bool:
    """A token is interpolated into a provider URL and stored publicly, so it
    must be a plain slug -- or, for Personio, a tenant host."""
    if provider is AtsProvider.PERSONIO:
        return bool(_PERSONIO_HOST_RE.fullmatch(token))
    return bool(_TOKEN_RE.fullmatch(token)) and token.lower() not in _RESERVED_TOKENS


def mentions_domain(text: str, domain: str) -> bool:
    """Does `text` contain `domain` as a whole host (`https://www.bolster.ai`,
    a mailto address at the domain), not as part of a longer one (`notbolster.ai`,
    `bolster.airline.com`)?"""
    if not text or not domain:
        return False
    pattern = rf"(?<![a-z0-9-])(?:www\.)?{re.escape(domain.lower())}(?![a-z0-9-]|\.[a-z])"
    return re.search(pattern, text.lower()) is not None


def _name_words(name: str) -> list[str]:
    return [w for w in _WORD_RE.findall(name.lower()) if w not in _NAME_NOISE]


def _is_spelled_out(words: list[str]) -> bool:
    return len(words) >= 2 and all(len(w) == 1 for w in words)


def fuzzy_name_match(company_name: str, returned_name: str | None) -> bool:
    """Do these two strings name the same organisation?

    Deliberately word-based, not substring-based: the iteration 6 spike's
    two-way substring test would call "Arc" a match for "Arcadia". Matches when
    the names are equal once legal-form words and spacing are dropped
    ("Mark Forged" / "Markforged, Inc."), or when one is a contiguous run of
    whole words inside the other and that run is itself long enough not to be
    a coincidence.
    """
    if not returned_name:
        return False
    a, b = _name_words(company_name), _name_words(returned_name)
    if not a or not b:
        return False
    # A name spelled as single letters ("S.H.I.E.L.D.") only matches another
    # spelled the same way: squashed, it would equal an ordinary word -- the
    # 300-domain re-run matched shield.ai to Greenhouse's "S.H.I.E.L.D." demo board.
    if _is_spelled_out(a) != _is_spelled_out(b):
        return False
    if "".join(a) == "".join(b):
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len("".join(short)) < MIN_TOKEN_LEN:
        return False
    n = len(short)
    return any(long_[i : i + n] == short for i in range(len(long_) - n + 1))


def _distinct(pairs: Iterable[tuple[AtsProvider, str]]) -> list[tuple[AtsProvider, str]]:
    seen: dict[tuple[AtsProvider, str], None] = {}
    for pair in pairs:
        seen.setdefault(pair, None)
    return list(seen)


def _failure(reason: str, method: str, weak: BoardProbe | None = None) -> MappingResult:
    if weak is not None:
        return MappingResult(
            provider=weak.provider,
            token=weak.token,
            confidence=MappingConfidence.WEAK,
            method=method,
            failure_reason=reason,
        )
    return MappingResult(method=method, failure_reason=reason)


def decide(ev: Evidence) -> MappingResult:
    """Judge one company's evidence. Never returns a failure without a reason."""
    page_probes = {
        (p.provider, p.token): p for p in ev.page_probes if is_valid_token(p.provider, p.token)
    }
    slug_probes = [p for p in ev.slug_probes if is_valid_token(p.provider, p.token)]
    live_slugs = [p for p in slug_probes if p.live]
    live_slug_pairs = {(p.provider, p.token) for p in live_slugs}

    page_pairs = [pair for pair in _distinct(ev.page_tokens) if is_valid_token(*pair)]
    live_page = [pair for pair in page_pairs if pair in page_probes and page_probes[pair].live]

    # A page token we couldn't judge -- probe inconclusive, or never probed --
    # might be the company's real board. It can't be ignored just because the
    # probe failed: shield.ai's real Lever board was too big to download, and
    # dropping it left an acquired subsidiary's live board looking unambiguous.
    unresolved = [
        pair
        for pair in page_pairs
        if pair not in page_probes or page_probes[pair].outcome is ProbeOutcome.INCONCLUSIVE
    ]

    # -- verified: the company's own careers page names a live board ----------
    if ev.careers_page is CareersPage.FOUND and live_page:
        if len(live_page) + len(unresolved) == 1:
            chosen = live_page[0]
        else:
            corroborated = [pair for pair in live_page if pair in live_slug_pairs]
            if len(corroborated) != 1:
                if unresolved:
                    return _failure(
                        MappingFailureReason.UNKNOWN.value, "careers_page_probe_inconclusive"
                    )
                return _failure(
                    MappingFailureReason.WEAK_ONLY.value,
                    f"careers_page_ambiguous:{len(live_page)}",
                )
            chosen = corroborated[0]
        method = "slug_guess+careers_page" if chosen in live_slug_pairs else "careers_page"
        return MappingResult(
            provider=chosen[0],
            token=chosen[1],
            confidence=MappingConfidence.VERIFIED,
            method=method,
        )

    # -- probable: a guessed board that names the company ----------------------
    if ev.careers_page is not CareersPage.PARKED:
        # The board's own postings containing the company's exact domain is
        # the board saying whose it is -- stronger than a name match, and
        # (user's call, 2026-09-24) strong enough to override the short-slug
        # guard: the guard exists because a short slug may be someone else's
        # board, and someone else's board doesn't carry this domain.
        mentioned = set(ev.domain_mentions)
        by_domain = [
            (p.provider, p.token) for p in live_slugs if (p.provider, p.token) in mentioned
        ]
        by_name = [
            (p.provider, p.token)
            for p in live_slugs
            if p.provider in NAME_BEARING_PROVIDERS
            and fuzzy_name_match(ev.company_name, p.org_name)
            and not guard_requires_verified(p.token)
        ]
        probable = _distinct(by_domain + by_name)
        if len(probable) == 1:
            provider, token = probable[0]
            how = "domain_in_postings" if probable[0] in by_domain else "name_match"
            return MappingResult(
                provider=provider,
                token=token,
                confidence=MappingConfidence.PROBABLE,
                method=f"slug_guess+{how}",
            )
        if len(probable) > 1:
            return _failure(
                MappingFailureReason.WEAK_ONLY.value, f"slug_guess_ambiguous:{len(probable)}"
            )

    # -- failures, most diagnostic first --------------------------------------
    if ev.careers_page is CareersPage.NOT_A_COMPANY:
        return _failure(MappingFailureReason.NOT_A_COMPANY_DOMAIN.value, "input_rejected")
    if ev.careers_page is CareersPage.BLOCKED:
        # Any guess stayed uncorroborated *because* the site refused us.
        return _failure(
            MappingFailureReason.BLOCKED.value,
            "homepage_blocked",
            weak=live_slugs[0] if live_slugs else None,
        )

    inconclusive_page = [
        pair
        for pair in page_pairs
        if pair in page_probes and page_probes[pair].outcome is ProbeOutcome.INCONCLUSIVE
    ]
    if inconclusive_page:
        return _failure(MappingFailureReason.UNKNOWN.value, "careers_page_probe_inconclusive")

    if ev.unsupported:
        return _failure(unsupported_ats(ev.unsupported[0]), "careers_page_unsupported_ats")

    if live_slugs:
        method = {
            CareersPage.PARKED: "parked_domain",
        }.get(ev.careers_page, "slug_guess")
        return _failure(
            MappingFailureReason.WEAK_ONLY.value, f"{method}_uncorroborated", weak=live_slugs[0]
        )

    if page_pairs:
        return _failure(MappingFailureReason.WEAK_ONLY.value, "careers_page_token_dead")

    match ev.careers_page:
        case CareersPage.JS_RENDERED:
            return _failure(MappingFailureReason.JS_RENDERED.value, "careers_page_js_rendered")
        case CareersPage.NONE | CareersPage.NO_DOMAIN | CareersPage.PARKED:
            return _failure(
                MappingFailureReason.NO_CAREERS_PAGE.value, f"careers_page_{ev.careers_page}"
            )
        case CareersPage.INCONCLUSIVE:
            return _failure(MappingFailureReason.UNKNOWN.value, "careers_page_inconclusive")
    if any(p.outcome is ProbeOutcome.INCONCLUSIVE for p in slug_probes):
        return _failure(MappingFailureReason.UNKNOWN.value, "slug_probe_inconclusive")
    return _failure(MappingFailureReason.UNKNOWN.value, "no_ats_evidence")
