"""Tests for src/mapping_validate.py -- SPEC.md §8.2's confidence rules.

Written before the cascade (BUILD.md M3: "Write validation first, then the
cascade that feeds it"). Every case here is built from evidence, never from a
status code: an HTTP 200 alone must never produce an accepted mapping.

Several cases are regressions for real false positives already found live in
earlier spikes -- each names the company it came from.
"""

import pytest

from src.mapping_validate import (
    BoardProbe,
    CareersPage,
    Evidence,
    ProbeOutcome,
    decide,
    fuzzy_name_match,
    guard_requires_verified,
    is_valid_token,
    load_collision_words,
)
from src.models import AtsProvider, MappingConfidence, MappingFailureReason

GH = AtsProvider.GREENHOUSE
LEVER = AtsProvider.LEVER
ASHBY = AtsProvider.ASHBY
WORKABLE = AtsProvider.WORKABLE
PERSONIO = AtsProvider.PERSONIO

CLOSED_REASONS = {r.value for r in MappingFailureReason}


def live(provider, token, name=None, count=3):
    return BoardProbe(provider, token, ProbeOutcome.LIVE, org_name=name, posting_count=count)


def dead(provider, token):
    return BoardProbe(provider, token, ProbeOutcome.NOT_FOUND)


def flaky(provider, token):
    return BoardProbe(provider, token, ProbeOutcome.INCONCLUSIVE, detail="timeout")


def evidence(name="Acme Widgets", **kw):
    kw.setdefault("careers_page", CareersPage.FOUND)
    return Evidence(company_name=name, **kw)


def assert_failure(result, reason):
    assert not result.accepted
    assert result.failure_reason == reason
    assert result.failure_reason is not None


# -- the negative guard (C-3.3) ----------------------------------------------


class TestGuard:
    @pytest.mark.parametrize("token", ["ro", "abc", "stem5", "owl"])
    def test_short_tokens_require_verified(self, token):
        assert guard_requires_verified(token)

    @pytest.mark.parametrize(
        "token", ["atlas", "square", "ramp", "notion", "arc", "level", "front", "scale"]
    )
    def test_every_spec_collision_word_requires_verified(self, token):
        assert guard_requires_verified(token)

    def test_collision_words_are_loaded_from_config(self):
        assert load_collision_words() == {
            "atlas",
            "square",
            "ramp",
            "notion",
            "arc",
            "level",
            "front",
            "scale",
        }

    def test_collision_match_is_case_insensitive(self):
        assert guard_requires_verified("NOTION")

    def test_a_long_uncommon_token_passes_the_guard(self):
        assert not guard_requires_verified("markforged")

    def test_c_3_3_a_short_slug_is_never_accepted_at_probable(self):
        """Name matches, board is live -- but `ramp` is short and a collision word."""
        result = decide(evidence(name="Ramp", slug_probes=(live(GH, "ramp", name="Ramp"),)))
        assert result.confidence is not MappingConfidence.PROBABLE
        assert_failure(result, MappingFailureReason.WEAK_ONLY)

    def test_c_3_3_a_collision_word_of_six_plus_chars_is_never_probable(self):
        result = decide(
            evidence(name="Notion", slug_probes=(live(WORKABLE, "notion", name="Notion"),))
        )
        assert result.confidence is not MappingConfidence.PROBABLE
        assert not result.accepted

    def test_c_3_3_the_same_short_slug_is_accepted_when_verified(self):
        """The guard caps `probable`, it does not forbid the token: the company's
        own careers page naming it is the independent second source."""
        result = decide(
            evidence(
                name="Ro",
                page_tokens=((LEVER, "ro"),),
                page_probes=(live(LEVER, "ro"),),
                slug_probes=(live(LEVER, "ro"),),
            )
        )
        assert result.accepted
        assert result.confidence is MappingConfidence.VERIFIED


# -- fuzzy name matching ------------------------------------------------------


class TestFuzzyNameMatch:
    @pytest.mark.parametrize(
        ("company", "returned"),
        [
            ("Mark Forged", "Markforged"),
            ("Owl Labs", "Owl Labs"),
            ("3Play Media", "3Play Media, Inc."),
            ("Aerones", "Aerones"),
            ("Brandwatch", "Brandwatch Ltd"),
            ("Terabase Energy", "Terabase Energy Inc"),
        ],
    )
    def test_same_company_matches(self, company, returned):
        assert fuzzy_name_match(company, returned)

    @pytest.mark.parametrize(
        ("company", "returned"),
        [
            ("Arc", "Arcadia"),  # substring of a different word is not a match
            ("OhmConnect", "Renew Home"),
            ("Acme", None),
            ("Acme", ""),
            ("Stem", "Stem Cell Labs"),  # a short prefix word is not enough
        ],
    )
    def test_different_or_missing_names_do_not_match(self, company, returned):
        assert not fuzzy_name_match(company, returned)


# -- token sanity -------------------------------------------------------------


class TestTokenSanity:
    @pytest.mark.parametrize(
        "token", ["markforged", "cfsenergy", "3playmedia", "a_b-c", "JourneyClinical"]
    )
    def test_plain_tokens_are_valid(self, token):
        assert is_valid_token(GH, token)

    @pytest.mark.parametrize(
        "token",
        ["", "embed", "api", "jobs", "../x", "a b", "x?y", "a" * 65, "-lead", "Acme\n"],
    )
    def test_malformed_or_path_word_tokens_are_invalid(self, token):
        assert not is_valid_token(GH, token)

    def test_reserved_path_words_are_invalid_in_any_case(self):
        assert not is_valid_token(GH, "Embed")

    def test_case_sensitivity_per_provider(self):
        from src.mapping_validate import normalize_token

        assert normalize_token(LEVER, "JourneyClinical") == "JourneyClinical"
        assert normalize_token(AtsProvider.RIPPLING, "Stem-Inc") == "Stem-Inc"
        assert normalize_token(WORKABLE, "AcmeCo") == "AcmeCo"
        assert normalize_token(GH, "OwlLabs") == "owllabs"
        assert normalize_token(ASHBY, "Crusoe") == "crusoe"
        assert normalize_token(PERSONIO, "Strohm.Jobs.Personio.com") == "strohm.jobs.personio.com"

    def test_personio_token_must_be_a_personio_tenant_host(self):
        assert is_valid_token(PERSONIO, "strohm.jobs.personio.com")
        assert is_valid_token(PERSONIO, "planetafoods.jobs.personio.de")
        assert not is_valid_token(PERSONIO, "www.personio.com")
        assert not is_valid_token(PERSONIO, "evil.example.com")
        assert not is_valid_token(PERSONIO, "strohm")

    def test_an_invalid_token_is_never_accepted_even_if_live(self):
        result = decide(evidence(page_tokens=((GH, "embed"),), page_probes=(live(GH, "embed"),)))
        assert not result.accepted


# -- verified -----------------------------------------------------------------


class TestVerified:
    def test_careers_page_token_with_live_board_is_verified(self):
        result = decide(
            evidence(page_tokens=((GH, "acmewidgets"),), page_probes=(live(GH, "acmewidgets"),))
        )
        assert result.accepted
        assert result.confidence is MappingConfidence.VERIFIED
        assert (result.provider, result.token) == (GH, "acmewidgets")
        assert result.method == "careers_page"
        assert result.failure_reason is None

    def test_slug_guess_corroborated_by_careers_page_is_verified(self):
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"),),
                page_probes=(live(GH, "acmewidgets"),),
                slug_probes=(live(GH, "acmewidgets", name="Acme Widgets"),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED
        assert result.method == "slug_guess+careers_page"

    def test_rebrand_token_mismatch_is_still_verified(self):
        """voltacharging.com -> Lever `joltcharge`: a rebrand that kept the old
        slug is real and correct (DEVLOG iteration 6). The company's own page is
        the evidence; the token not resembling the name is not a disqualifier."""
        result = decide(
            evidence(
                name="Volta",
                page_tokens=((LEVER, "joltcharge"),),
                page_probes=(live(LEVER, "joltcharge"),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED
        assert result.token == "joltcharge"

    def test_acquisition_name_mismatch_is_still_verified(self):
        """ohmconnect.com's careers page redirects to Workable `renewhome`, whose
        widget names "Renew Home" -- a mismatch, but the page is the company's own."""
        result = decide(
            evidence(
                name="OhmConnect",
                page_tokens=((WORKABLE, "renewhome"),),
                page_probes=(live(WORKABLE, "renewhome", name="Renew Home"),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED

    def test_live_board_with_zero_postings_is_still_verified(self):
        """Cofactor Genomics' case: mapped, zero jobs -- not unmapped, not weak."""
        result = decide(
            evidence(
                page_tokens=((AtsProvider.BREEZY_HR, "acme-widgets"),),
                page_probes=(live(AtsProvider.BREEZY_HR, "acme-widgets", count=0),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED

    def test_two_distinct_live_page_tokens_are_ambiguous_not_verified(self):
        """A careers page linking two live boards (a parent company, a portfolio
        page) is not evidence of which one is this company's."""
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"), (LEVER, "otherco")),
                page_probes=(live(GH, "acmewidgets"), live(LEVER, "otherco")),
            )
        )
        assert_failure(result, MappingFailureReason.WEAK_ONLY)
        assert result.method.startswith("careers_page_ambiguous")

    def test_ambiguity_is_resolved_by_exactly_one_matching_slug_hit(self):
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"), (LEVER, "otherco")),
                page_probes=(live(GH, "acmewidgets"), live(LEVER, "otherco")),
                slug_probes=(live(GH, "acmewidgets", name="Acme Widgets"),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED
        assert result.token == "acmewidgets"

    def test_the_same_token_repeated_on_a_page_is_not_ambiguity(self):
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"), (GH, "acmewidgets")),
                page_probes=(live(GH, "acmewidgets"),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED

    def test_shield_ai_an_inconclusive_second_token_still_makes_it_ambiguous(self):
        """shield.ai, 300-domain dry run: the page linked Lever `shieldai` (its
        real board, too big to download -> inconclusive) and Greenhouse
        `aechelontechnology` (an acquired subsidiary's board, live). Ignoring the
        inconclusive token "verified" the wrong company."""
        result = decide(
            evidence(
                name="shield",
                page_tokens=((LEVER, "shieldai"), (GH, "aechelontechnology")),
                page_probes=(flaky(LEVER, "shieldai"), live(GH, "aechelontechnology")),
            )
        )
        assert not result.accepted
        assert result.failure_reason == MappingFailureReason.UNKNOWN

    def test_an_unprobed_page_token_also_counts_toward_ambiguity(self):
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"), (LEVER, "neverprobed")),
                page_probes=(live(GH, "acmewidgets"),),
            )
        )
        assert not result.accepted

    def test_a_slug_corroborated_token_still_wins_over_an_inconclusive_one(self):
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"), (LEVER, "otherco")),
                page_probes=(live(GH, "acmewidgets"), flaky(LEVER, "otherco")),
                slug_probes=(live(GH, "acmewidgets", name="Acme Widgets"),),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED
        assert result.token == "acmewidgets"

    def test_a_dead_second_token_does_not_make_the_live_one_ambiguous(self):
        result = decide(
            evidence(
                page_tokens=((GH, "acmewidgets"), (GH, "oldacme")),
                page_probes=(live(GH, "acmewidgets"), dead(GH, "oldacme")),
            )
        )
        assert result.confidence is MappingConfidence.VERIFIED
        assert result.token == "acmewidgets"


# -- probable -----------------------------------------------------------------


class TestProbable:
    def test_greenhouse_slug_hit_with_matching_board_name_is_probable(self):
        result = decide(
            evidence(
                name="Mark Forged",
                slug_probes=(live(GH, "markforged", name="Markforged"),),
            )
        )
        assert result.accepted
        assert result.confidence is MappingConfidence.PROBABLE
        assert result.method == "slug_guess+name_match"

    def test_workable_slug_hit_with_matching_account_name_is_probable(self):
        result = decide(
            evidence(name="Aerones", slug_probes=(live(WORKABLE, "aerones", name="Aerones"),))
        )
        assert result.confidence is MappingConfidence.PROBABLE

    def test_slug_hit_with_a_different_company_name_is_weak(self):
        """HTTP 200 on a guessed slug, but the board belongs to someone else."""
        result = decide(
            evidence(name="Acme Widgets", slug_probes=(live(GH, "acmewidgets", name="Zeta"),))
        )
        assert result.confidence is MappingConfidence.WEAK
        assert_failure(result, MappingFailureReason.WEAK_ONLY)

    @pytest.mark.parametrize("provider", [LEVER, ASHBY])
    def test_uncorroborated_slug_hit_on_a_nameless_provider_is_weak(self, provider):
        """Lever and Ashby return no org name, so a bare 200 is all there is."""
        result = decide(evidence(slug_probes=(live(provider, "acmewidgets"),)))
        assert result.confidence is MappingConfidence.WEAK
        assert_failure(result, MappingFailureReason.WEAK_ONLY)

    def test_two_different_probable_slug_hits_are_ambiguous(self):
        result = decide(
            evidence(
                slug_probes=(
                    live(GH, "acmewidgets", name="Acme Widgets"),
                    live(WORKABLE, "acmewidgets", name="Acme Widgets"),
                ),
            )
        )
        assert not result.accepted
        assert result.failure_reason == MappingFailureReason.WEAK_ONLY

    def test_parked_domain_blocks_probable(self):
        """jetzero.au (DEVLOG iteration 6): a suspended-hosting parked domain
        fuzzy-matched a real Greenhouse board at `probable`. A parked domain is
        not evidence the company is this one."""
        result = decide(
            evidence(
                name="JetZero",
                careers_page=CareersPage.PARKED,
                slug_probes=(live(GH, "jetzero", name="JetZero"),),
            )
        )
        assert not result.accepted


# -- failures (C-3.2, C-3.4) ---------------------------------------------------


class TestFailures:
    def test_c_3_2_weak_is_recorded_as_a_failure_not_accepted(self):
        result = decide(evidence(slug_probes=(live(LEVER, "acmewidgets"),)))
        assert result.confidence is MappingConfidence.WEAK
        assert not result.accepted
        assert result.failure_reason == MappingFailureReason.WEAK_ONLY

    def test_machine_metrics_dead_embed_is_weak_only_not_verified(self):
        """Machine Metrics had a leftover Greenhouse embed pointing at a token
        that 404s (DEVLOG M1). A dead token on the page is a failure."""
        result = decide(
            evidence(
                name="Machine Metrics",
                page_tokens=((GH, "machinemetrics"),),
                page_probes=(dead(GH, "machinemetrics"),),
            )
        )
        assert_failure(result, MappingFailureReason.WEAK_ONLY)
        assert result.confidence is None

    def test_circleci_cookie_allowlist_mention_yields_no_mapping(self):
        """CircleCI's only 'greenhouse' mention was a cookie-consent allowlist
        entry -- extraction finds no token, so there is nothing to accept."""
        result = decide(evidence(name="CircleCI"))
        assert_failure(result, MappingFailureReason.UNKNOWN)

    def test_inconclusive_probe_is_unknown_not_demoted_to_dead(self):
        """Zipline's live 336-posting board was retired on an HTTP 0 (DEVLOG
        iteration 7). A transient failure is not evidence the board is gone."""
        result = decide(
            evidence(page_tokens=((GH, "acmewidgets"),), page_probes=(flaky(GH, "acmewidgets"),))
        )
        assert_failure(result, MappingFailureReason.UNKNOWN)
        assert "inconclusive" in result.method

    def test_unsupported_ats_records_the_platform_name(self):
        result = decide(evidence(unsupported=("icims",)))
        assert_failure(result, "unsupported_ats:icims")

    def test_unsupported_ats_outranks_an_uncorroborated_slug_hit(self):
        result = decide(evidence(unsupported=("icims",), slug_probes=(live(LEVER, "acmewidgets"),)))
        assert_failure(result, "unsupported_ats:icims")

    def test_js_rendered_page(self):
        result = decide(evidence(careers_page=CareersPage.JS_RENDERED))
        assert_failure(result, MappingFailureReason.JS_RENDERED)

    def test_no_careers_page(self):
        result = decide(evidence(careers_page=CareersPage.NONE))
        assert_failure(result, MappingFailureReason.NO_CAREERS_PAGE)

    def test_no_domain_at_all(self):
        result = decide(evidence(careers_page=CareersPage.NO_DOMAIN))
        assert_failure(result, MappingFailureReason.NO_CAREERS_PAGE)

    def test_careers_page_fetch_inconclusive_is_unknown(self):
        result = decide(evidence(careers_page=CareersPage.INCONCLUSIVE))
        assert_failure(result, MappingFailureReason.UNKNOWN)

    def test_c_3_4_every_failure_in_the_matrix_carries_a_closed_set_reason(self):
        matrix = [
            evidence(careers_page=page, slug_probes=slugs, page_tokens=pt, page_probes=pp, **extra)
            for page in CareersPage
            for slugs in ((), (live(LEVER, "acmewidgets"),), (flaky(GH, "acmewidgets"),))
            for pt, pp in (
                ((), ()),
                (((GH, "acmewidgets"),), (dead(GH, "acmewidgets"),)),
                (((GH, "acmewidgets"),), (flaky(GH, "acmewidgets"),)),
            )
            for extra in ({}, {"unsupported": ("teamtailor",)})
        ]
        failures = [r for r in map(decide, matrix) if not r.accepted]
        assert failures
        for result in failures:
            assert result.failure_reason is not None
            assert result.failure_reason in CLOSED_REASONS or result.failure_reason.startswith(
                "unsupported_ats:"
            ), result
