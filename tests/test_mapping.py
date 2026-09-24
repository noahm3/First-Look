"""Tests for src/mapping.py -- the SPEC.md §8.1 cascade, end to end, offline.

Each test serves a small fake website (homepage, careers page, redirects) and
fake ATS endpoints through the FetchClient's fake transport, then checks the
judged result. Anything a test doesn't route is a 404.
"""

import csv
from datetime import UTC, datetime

import pytest

import src.mapping as mapping
from src.mapping import (
    domain_label,
    map_company,
    order_for_mapping,
    slug_candidates,
    summarize,
    write_review_csv,
)
from src.models import AtsProvider, Company, MappingConfidence, MappingFailureReason, MappingResult
from tests.ats_fixtures import fake_client, refuse_connection, respond

P = AtsProvider


def site(routes):
    """routes: {url: response | callable(request) -> response}; else 404."""

    def handler(request):
        url = str(request.url)
        route = routes.get(url)
        if route is None:
            return respond(404, content=b"not found")
        return route(request) if callable(route) else route

    return handler


def page(body: str):
    return respond(200, content=body.encode())


def redirect(to: str):
    return respond(302, headers={"Location": to})


GH_BOARD = "https://boards-api.greenhouse.io/v1/boards/{}"
WORKABLE = "https://apply.workable.com/api/v1/widget/accounts/{}"
LEVER = "https://api.lever.co/v0/postings/{}?mode=json&limit=1"
LONG_TEXT = "We build widgets for everyone. " * 20


def run(routes, name="Acme Widgets", domain="acmewidgets.com"):
    with fake_client(site(routes), max_attempts=1) as client:
        return map_company(client, name, domain)


class TestVerified:
    def test_careers_link_with_greenhouse_embed_is_verified(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(f'<a href="/careers">Careers</a>{LONG_TEXT}'),
                "https://acmewidgets.com/careers": page(
                    '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acmeco">'
                    + LONG_TEXT
                ),
                GH_BOARD.format("acmeco"): respond(200, json={"name": "Acme Widgets"}),
            }
        )
        assert outcome.result.accepted
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert (outcome.result.provider, outcome.result.token) == (P.GREENHOUSE, "acmeco")
        assert outcome.careers_urls == ("https://acmewidgets.com/careers",)

    def test_careers_redirect_to_an_ats_board_is_verified(self):
        """ohmconnect.com's careers page redirects to apply.workable.com/renewhome."""
        outcome = run(
            {
                "https://ohmconnect.com/": page(f'<a href="/careers">Join us</a>{LONG_TEXT}'),
                "https://ohmconnect.com/careers": redirect("https://apply.workable.com/renewhome/"),
                "https://apply.workable.com/renewhome/": page("<div id=app></div>"),
                WORKABLE.format("renewhome"): respond(200, json={"name": "Renew Home", "jobs": []}),
            },
            name="OhmConnect",
            domain="ohmconnect.com",
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert (outcome.result.provider, outcome.result.token) == (P.WORKABLE, "renewhome")

    def test_board_linked_straight_from_the_homepage_is_verified(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(
                    f'<a href="https://jobs.lever.co/joltcharge">Jobs</a>{LONG_TEXT}'
                ),
                LEVER.format("joltcharge"): respond(200, json=[]),
            }
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.token == "joltcharge"

    def test_fallback_path_is_tried_when_the_homepage_has_no_careers_link(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(LONG_TEXT),
                "https://acmewidgets.com/jobs": page(
                    '<a href="https://forge-nano.breezy.hr/">Open roles</a>' + LONG_TEXT
                ),
                "https://forge-nano.breezy.hr/json": respond(200, json=[]),
            }
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert (outcome.result.provider, outcome.result.token) == (P.BREEZY_HR, "forge-nano")

    def test_bare_domain_failure_falls_back_to_www(self):
        outcome = run(
            {
                "https://acmewidgets.com/": refuse_connection,
                "https://www.acmewidgets.com/": page(
                    f'<a href="https://jobs.lever.co/acmeco">x</a>{LONG_TEXT}'
                ),
                LEVER.format("acmeco"): respond(200, json=[]),
            }
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED


class TestProbable:
    def test_slug_guess_with_matching_greenhouse_name_is_probable(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(LONG_TEXT),
                GH_BOARD.format("acmewidgets"): respond(200, json={"name": "Acme Widgets"}),
            }
        )
        assert outcome.result.confidence is MappingConfidence.PROBABLE
        assert outcome.slug_hit


class TestNotAccepted:
    def test_a_page_on_an_unrelated_domain_is_not_the_companys_own(self):
        """/careers redirecting to some other company's site: its board is not
        evidence about this company."""
        outcome = run(
            {
                "https://acmewidgets.com/": page(LONG_TEXT),
                "https://acmewidgets.com/careers": redirect("https://parentco.example/careers"),
                "https://parentco.example/careers": page(
                    '<a href="https://jobs.lever.co/parentco">x</a>' + LONG_TEXT
                ),
                LEVER.format("parentco"): respond(200, json=[]),
            }
        )
        assert not outcome.result.accepted

    def test_homepage_redirect_to_an_acquirer_is_followed_and_labelled(self):
        """capsule8.com -> sophos.com (acquired). User's call 2026-09-24: an
        acquisition is let in -- the acquirer's board is where that company's
        roles now live -- but the method says so, so it's visible in review."""
        outcome = run(
            {
                "https://capsule8.com/": redirect("https://www.sophos.com/en-us"),
                "https://www.sophos.com/en-us": page(
                    '<a href="https://jobs.lever.co/sophos">Careers</a>' + LONG_TEXT
                ),
                LEVER.format("sophos"): respond(200, json=[{"id": "1"}]),
            },
            name="capsule8",
            domain="capsule8.com",
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.token == "sophos"
        assert outcome.result.method == "careers_page+redirected_domain"

    def test_rebrand_redirect_is_followed_too(self):
        """voltacharging.com -> joltcharge.com: the watchlist's Volta case."""
        outcome = run(
            {
                "https://voltacharging.com/": redirect("https://joltcharge.com/us/"),
                "https://joltcharge.com/us/": page(f'<a href="/careers">Careers</a>{LONG_TEXT}'),
                "https://joltcharge.com/careers": page(
                    '<a href="https://jobs.lever.co/joltcharge">x</a>' + LONG_TEXT
                ),
                LEVER.format("joltcharge"): respond(200, json=[]),
            },
            name="Volta",
            domain="voltacharging.com",
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.token == "joltcharge"
        assert outcome.result.method == "careers_page+redirected_domain"

    def test_same_brand_redirect_keeps_the_plain_method(self):
        outcome = run(
            {
                "https://galileohealth.com/": redirect("https://galileo.io/"),
                "https://galileo.io/": page(
                    f'<a href="https://boards.greenhouse.io/galileo">x</a>{LONG_TEXT}'
                ),
                GH_BOARD.format("galileo"): respond(200, json={"name": "Galileo"}),
            },
            name="galileohealth",
            domain="galileohealth.com",
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.method == "careers_page"

    def test_homepage_redirect_to_the_same_brand_on_another_tld_is_still_own(self):
        """algorand.com -> algorand.co: same brand, and its careers page is the
        watchlist's ground truth (Rippling `algorand-foundation`)."""
        outcome = run(
            {
                "https://algorand.com/": redirect("https://algorand.co/"),
                "https://algorand.co/": page(f'<a href="/careers">Careers</a>{LONG_TEXT}'),
                "https://algorand.co/careers": page(
                    '<a href="https://ats.rippling.com/algorand-foundation/jobs">x</a>' + LONG_TEXT
                ),
                "https://api.rippling.com/platform/api/ats/v2/board/algorand-foundation/jobs": (
                    respond(200, json={"items": [], "totalItems": 0})
                ),
            },
            name="Algorand",
            domain="algorand.com",
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.token == "algorand-foundation"

    @pytest.mark.parametrize(
        ("a", "b", "same"),
        [
            ("algorand.com", "algorand.co", True),
            ("galileohealth.com", "galileo.io", True),
            ("loyalfordogs.com", "loyal.com", True),
            ("capsule8.com", "sophos.com", False),
            ("voltacharging.com", "joltcharge.com", False),
            ("gobrightside.com", "go.com", False),  # too short to be a brand prefix
        ],
    )
    def test_same_brand(self, a, b, same):
        assert mapping._same_brand(a, b) is same

    def test_shield_ai_huge_real_board_plus_subsidiary_board_is_not_accepted(self):
        """The page links the real (huge) board and an acquired subsidiary's
        board; if the real one can't be probed, nothing is accepted."""
        outcome = run(
            {
                "https://shield.ai/": page(f'<a href="/careers/">Careers</a>{LONG_TEXT}'),
                "https://shield.ai/careers/": page(
                    '<a href="https://jobs.lever.co/shieldai">a</a>'
                    '<a href="https://job-boards.greenhouse.io/aechelontechnology">b</a>'
                    + LONG_TEXT
                ),
                LEVER.format("shieldai"): respond(503),
                GH_BOARD.format("aechelontechnology"): respond(200, json={"name": "Aechelon"}),
            },
            name="shield",
            domain="shield.ai",
        )
        assert not outcome.result.accepted
        assert outcome.result.failure_reason == MappingFailureReason.UNKNOWN

    def test_a_careers_link_serving_the_homepage_is_ignored(self):
        """loamist.com: the careers link returned a byte-identical homepage."""
        home = f'<a href="/careers">Careers</a>{LONG_TEXT}'
        outcome = run(
            {
                "https://acmewidgets.com/": page(home),
                "https://acmewidgets.com/careers": page(home),
            }
        )
        assert outcome.careers_urls == ()
        assert outcome.result.failure_reason == MappingFailureReason.NO_CAREERS_PAGE

    def test_parked_domain_is_never_accepted_on_a_name_match(self):
        """jetzero.au (DEVLOG iteration 6)."""
        outcome = run(
            {
                "https://jetzero.au/": page("<h1>Account Suspended</h1>" + LONG_TEXT),
                GH_BOARD.format("jetzero"): respond(200, json={"name": "JetZero"}),
            },
            name="JetZero",
            domain="jetzero.au",
        )
        assert not outcome.result.accepted

    def test_dead_embed_is_weak_only(self):
        """Machine Metrics: a leftover embed pointing at a 404 token."""
        outcome = run(
            {
                "https://acmewidgets.com/": page(f'<a href="/careers">x</a>{LONG_TEXT}'),
                "https://acmewidgets.com/careers": page(
                    '<a href="https://boards.greenhouse.io/deadtoken">x</a>' + LONG_TEXT
                ),
            }
        )
        assert outcome.result.failure_reason == MappingFailureReason.WEAK_ONLY
        assert not outcome.result.accepted

    def test_unsupported_ats_is_named(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(f'<a href="/careers">x</a>{LONG_TEXT}'),
                "https://acmewidgets.com/careers": page(
                    '<a href="https://careers-acme.icims.com/jobs">x</a>' + LONG_TEXT
                ),
            }
        )
        assert outcome.result.failure_reason == "unsupported_ats:icims"

    def test_js_rendered_homepage(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(
                    '<div id="root"></div><script src="/app.js"></script>'
                )
            }
        )
        assert outcome.result.failure_reason == MappingFailureReason.JS_RENDERED

    def test_unreachable_site_is_unknown_not_no_careers_page(self):
        outcome = run({"https://acmewidgets.com/": refuse_connection})
        assert outcome.result.failure_reason == MappingFailureReason.UNKNOWN

    def test_no_domain_runs_only_stage_1(self):
        seen = []

        def record(request):
            seen.append(request.url.host)
            return respond(404)

        with fake_client(record, max_attempts=1) as client:
            outcome = map_company(client, "Acme Widgets", None)
        assert outcome.result.failure_reason == MappingFailureReason.NO_CAREERS_PAGE
        assert set(seen) <= {
            "boards-api.greenhouse.io",
            "api.lever.co",
            "api.ashbyhq.com",
            "apply.workable.com",
        }

    def test_an_exception_inside_the_cascade_never_escapes(self, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError("parser exploded")

        monkeypatch.setattr(mapping, "extract", boom)
        outcome = run({"https://acmewidgets.com/": page(LONG_TEXT)})
        assert outcome.result.failure_reason == MappingFailureReason.UNKNOWN
        assert outcome.result.method == "cascade_error:RuntimeError"


class TestSlugGuessProviders:
    def test_workable_is_never_guessed(self):
        """Guessing tripped a sustained 429 on apply.workable.com in the first
        dry run, which then blocked probing real careers-page tokens."""
        seen = []

        def record(request):
            seen.append(request.url.host)
            return respond(404)

        with fake_client(record, max_attempts=1) as client:
            map_company(client, "Acme Widgets", None)
        assert "apply.workable.com" not in seen
        assert {"boards-api.greenhouse.io", "api.lever.co", "api.ashbyhq.com"} <= set(seen)


class TestSlugCandidates:
    @pytest.mark.parametrize(
        ("domain", "label"),
        [
            ("cfs.energy", "cfs"),
            ("acme.co.uk", "acme"),
            ("careers.acme.com", "acme"),
            ("virtual-peaker.com", "virtual-peaker"),
        ],
    )
    def test_domain_label(self, domain, label):
        assert domain_label(domain) == label

    def test_domain_label_first_then_name_with_suffixes_stripped(self):
        assert slug_candidates("PH7 Technologies", "ph7technologies.com") == [
            "ph7technologies",
            "ph7",
        ]

    def test_hyphenated_domain_yields_both_forms(self):
        assert slug_candidates("Virtual Peaker", "virtual-peaker.com")[:2] == [
            "virtual-peaker",
            "virtualpeaker",
        ]

    def test_capped(self):
        assert len(slug_candidates("Some Long Company Name Inc", "some-long.io")) <= 3


class TestOrdering:
    def test_open_roles_first_then_never_attempted_then_oldest(self):
        old = datetime(2026, 1, 1, tzinfo=UTC)
        new = datetime(2026, 9, 1, tzinfo=UTC)
        companies = [
            Company(name="a", mapping_last_attempt_at=new),
            Company(name="b", has_open_roles_signal=True, mapping_last_attempt_at=old),
            Company(name="c"),
            Company(name="d", mapping_last_attempt_at=old),
            Company(name="e", has_open_roles_signal=True),
        ]
        assert [c.name for c in order_for_mapping(companies)] == ["e", "b", "c", "d", "a"]


class TestReporting:
    def _outcomes(self):
        accepted = run(
            {
                "https://acmewidgets.com/": page(
                    f'<a href="https://jobs.lever.co/acmeco">x</a>{LONG_TEXT}'
                ),
                LEVER.format("acmeco"): respond(200, json=[]),
            }
        )
        failed = run({"https://acmewidgets.com/": page(LONG_TEXT)}, name="Zeta Corp")
        return accepted, failed

    def test_c_3_5_review_csv_holds_every_accepted_mapping_and_nothing_else(self, tmp_path):
        accepted, failed = self._outcomes()
        path = tmp_path / "data" / "mapping_review.csv"
        write_review_csv(
            path,
            [
                ("Acme Widgets", "acmewidgets.com", accepted.result),
                ("Zeta Corp", "zeta.example", failed.result),
                (
                    "Weak Co",
                    "weak.example",
                    MappingResult(
                        provider=P.LEVER,
                        token="weakco",
                        confidence=MappingConfidence.WEAK,
                        method="slug_guess_uncorroborated",
                        failure_reason="weak_only",
                    ),
                ),
            ],
        )
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        assert rows == [
            {
                "company": "Acme Widgets",
                "domain": "acmewidgets.com",
                "provider": "lever",
                "token": "acmeco",
                "confidence": "verified",
                "method": "careers_page",
            }
        ]

    def test_summary_reports_counts_never_company_names(self):
        accepted, failed = self._outcomes()
        text = summarize([accepted, failed])
        assert "cascade coverage:     1/2 (50.0%)" in text
        assert "Acme" not in text and "Zeta" not in text and "acmeco" not in text


class TestGroundTruth:
    def test_every_watchlist_domain_has_an_expected_mapping_and_nothing_else(self):
        from src.watchlist import canonicalize_domain, load_watchlist

        expected = mapping.load_expected()
        domains = {canonicalize_domain(e.domain) for e in load_watchlist()}
        assert domains == set(expected)

    def test_ground_truth_covers_all_eight_providers(self):
        providers = {e.provider for e in mapping.load_expected().values()}
        # SmartRecruiters is detection-only (SPEC §4): no adapter, nothing to map to.
        assert providers == set(AtsProvider) - {AtsProvider.SMARTRECRUITERS}

    def test_ground_truth_tokens_are_valid(self):
        from src.mapping_validate import is_valid_token

        for exp in mapping.load_expected().values():
            assert is_valid_token(exp.provider, exp.token), exp

    def test_verdicts(self):
        exp = mapping.Expected(AtsProvider.LEVER, "joltcharge")
        right = MappingResult(
            provider=AtsProvider.LEVER,
            token="joltcharge",
            confidence=MappingConfidence.VERIFIED,
            method="careers_page",
        )
        wrong = MappingResult(
            provider=AtsProvider.LEVER,
            token="volta",
            confidence=MappingConfidence.PROBABLE,
            method="slug_guess+name_match",
        )
        weak = MappingResult(
            provider=AtsProvider.LEVER,
            token="joltcharge",
            confidence=MappingConfidence.WEAK,
            failure_reason="weak_only",
        )
        assert mapping.verdict(right, exp) == "TP"
        assert mapping.verdict(wrong, exp) == "FP"
        assert mapping.verdict(weak, exp) == "FN"
        assert mapping.verdict(right, None) == "FP"

    def test_verdict_respects_case_sensitivity(self):
        lever = mapping.Expected(AtsProvider.LEVER, "JourneyClinical")
        got = MappingResult(
            provider=AtsProvider.LEVER,
            token="journeyclinical",
            confidence=MappingConfidence.VERIFIED,
            method="careers_page",
        )
        assert mapping.verdict(got, lever) == "FP"  # a different, dead Lever board
        gh = mapping.Expected(AtsProvider.GREENHOUSE, "owllabs")
        got_gh = MappingResult(
            provider=AtsProvider.GREENHOUSE,
            token="owllabs",
            confidence=MappingConfidence.VERIFIED,
            method="careers_page",
        )
        assert mapping.verdict(got_gh, gh) == "TP"


# -- M3 follow-up (iteration 16 findings) ----------------------------------------


class TestIteration16Fixes:
    @pytest.mark.parametrize("status", [401, 403, 429])
    def test_blocked_homepage_is_reason_blocked(self, status):
        outcome = run({"https://acmewidgets.com/": respond(status)})
        assert outcome.result.failure_reason == MappingFailureReason.BLOCKED

    @pytest.mark.parametrize(
        ("label", "href"),
        [
            ("Join The Team", "/join-the-team/"),  # fluorok.com
            ("Work with us", "/?page_id=3772"),  # plotlogic.com
            ("Careers", "/company#careers"),  # currents.market
            ("Hiring and Recruitment", "/hiring-and-recruitment.html"),
        ],
    )
    def test_careers_link_found_by_its_text(self, label, href):
        from urllib.parse import urljoin

        target = urljoin("https://acmewidgets.com/", href).split("#")[0]
        outcome = run(
            {
                "https://acmewidgets.com/": page(
                    f'<a href="{href}"><span>{label}</span></a>' + LONG_TEXT
                ),
                target: page('<a href="https://jobs.lever.co/acmeco">x</a>' + LONG_TEXT),
                LEVER.format("acmeco"): respond(200, json=[]),
            }
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.method == "careers_page"

    def test_offsite_careers_link_is_followed_and_labelled(self):
        """taxscouts.com: its Jobs link goes to taxfix.com (its acquirer)."""
        outcome = run(
            {
                "https://acmewidgets.com/": page(
                    '<a href="https://parentco.example/en/careers/">Jobs</a>' + LONG_TEXT
                ),
                "https://parentco.example/en/careers/": page(
                    '<a href="https://jobs.lever.co/parentco">x</a>' + LONG_TEXT
                ),
                LEVER.format("parentco"): respond(200, json=[]),
            }
        )
        assert outcome.result.confidence is MappingConfidence.VERIFIED
        assert outcome.result.token == "parentco"
        assert outcome.result.method == "careers_page+offsite_careers_link"

    @pytest.mark.parametrize(
        "href",
        [
            "https://www.linkedin.com/company/acme/",
            "https://wellfound.com/company/acme",
            "https://www.glassdoor.com/acme",
        ],
    )
    def test_profile_sites_are_not_followed_as_careers_pages(self, href):
        seen = []

        def handler(request):
            seen.append(request.url.host)
            if str(request.url) == "https://acmewidgets.com/":
                return page(f'<a href="{href}">Careers</a>' + LONG_TEXT)
            return respond(404)

        with fake_client(handler, max_attempts=1) as client:
            map_company(client, "Acme Widgets", "acmewidgets.com")
        profile_hosts = ("linkedin.com", "wellfound.com", "glassdoor.com")
        assert not any(h.endswith(profile_hosts) for h in seen)

    def test_own_careers_link_is_preferred_over_an_offsite_one(self):
        outcome = run(
            {
                "https://acmewidgets.com/": page(
                    '<a href="https://parentco.example/careers">Careers</a>'
                    '<a href="/careers">Careers</a>' + LONG_TEXT
                ),
                "https://acmewidgets.com/careers": page(
                    '<a href="https://jobs.lever.co/acmeco">x</a>' + LONG_TEXT
                ),
                LEVER.format("acmeco"): respond(200, json=[]),
            }
        )
        assert outcome.result.token == "acmeco"
        assert outcome.result.method == "careers_page"

    @pytest.mark.parametrize(
        "domain", ["app.usercentrics.eu", "api.intellimize.co", "careers.acme.co.uk"]
    )
    def test_subdomain_inputs_are_not_a_company_domain_and_cost_no_requests(self, domain):
        seen = []

        def handler(request):
            seen.append(request)
            return respond(404)

        with fake_client(handler, max_attempts=1) as client:
            outcome = map_company(client, "x", domain)
        assert outcome.result.failure_reason == MappingFailureReason.NOT_A_COMPANY_DOMAIN
        assert seen == []

    def test_listed_non_company_domain(self):
        outcome = run({}, name="therobotreport", domain="therobotreport.com")
        assert outcome.result.failure_reason == MappingFailureReason.NOT_A_COMPANY_DOMAIN

    @pytest.mark.parametrize("domain", ["acme.co.uk", "cfs.energy", "acme.com"])
    def test_registrable_domains_pass_the_input_check(self, domain):
        from src.domain_quality import classify_input_domain

        assert classify_input_domain(domain) is None

    def test_lever_guess_with_domain_in_postings_is_probable_end_to_end(self):
        outcome = run(
            {
                "https://bolster.ai/": page(LONG_TEXT),
                "https://api.lever.co/v0/postings/bolster?mode=json&limit=1": respond(
                    200, json=[{"id": "1"}]
                ),
                "https://api.lever.co/v0/postings/bolster?mode=json&limit=5": respond(
                    200,
                    json=[{"id": "1", "descriptionPlain": "About us: see https://bolster.ai"}],
                ),
            },
            name="bolster",
            domain="bolster.ai",
        )
        assert outcome.result.confidence is MappingConfidence.PROBABLE
        assert outcome.result.method == "slug_guess+domain_in_postings"

    def test_summary_reports_coverage_over_valid_inputs_too(self):
        good = run(
            {
                "https://acmewidgets.com/": page(
                    f'<a href="https://jobs.lever.co/acmeco">x</a>{LONG_TEXT}'
                ),
                LEVER.format("acmeco"): respond(200, json=[]),
            }
        )
        bad = run({}, name="x", domain="app.usercentrics.eu")
        text = summarize([good, bad])
        assert "cascade coverage:     1/2 (50.0%)" in text
        assert "1/1 (100.0%) of valid inputs" in text
