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
LEVER = "https://api.lever.co/v0/postings/{}?mode=json"
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
