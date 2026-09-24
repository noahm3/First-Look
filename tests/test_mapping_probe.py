"""Tests for src/mapping_probe.py -- does (provider, token) name a real board?

Reuses the M2 adapter fixtures (tests/fixtures/ats/*), which were trimmed from
live responses. The point of every test here is the same: a 200 is only
`live` when the body is actually that provider's board shape, and a transient
failure is `inconclusive`, never `not_found`.
"""

import pytest

from src.mapping_probe import probe, probe_url
from src.mapping_validate import ProbeOutcome
from src.models import AtsProvider
from tests.ats_fixtures import fake_client, read_fixture, refuse_connection, respond

P = AtsProvider


def run(provider, token, handler, **kw):
    with fake_client(handler, max_attempts=1, **kw) as client:
        return probe(client, provider, token)


def always(status, *, content=None, json=None, headers=None):
    def handler(_request):
        return respond(status, content=content, json=json, headers=headers)

    return handler


class TestLive:
    def test_greenhouse_board_endpoint_returns_the_board_name(self):
        result = run(P.GREENHOUSE, "markforged", always(200, json={"name": "Markforged"}))
        assert result.outcome is ProbeOutcome.LIVE
        assert result.org_name == "Markforged"

    def test_greenhouse_probe_hits_the_board_endpoint_not_jobs(self):
        seen = []

        def handler(request):
            seen.append(str(request.url))
            return respond(200, json={"name": "Markforged"})

        run(P.GREENHOUSE, "markforged", handler)
        assert seen == ["https://boards-api.greenhouse.io/v1/boards/markforged"]

    def test_workable_account_name_is_captured(self):
        body = read_fixture("workable", "normal.json")
        result = run(P.WORKABLE, "aerones", always(200, content=body))
        assert result.outcome is ProbeOutcome.LIVE
        assert result.org_name == "Aerones"
        assert result.posting_count and result.posting_count > 0

    @pytest.mark.parametrize(
        ("provider", "provider_dir", "fixture"),
        [
            (P.LEVER, "lever", "normal.json"),
            (P.ASHBY, "ashby", "normal.json"),
            (P.RIPPLING, "rippling", "list_normal.json"),
            (P.BAMBOOHR, "bamboohr", "normal.json"),
            (P.BREEZY_HR, "breezy", "normal.json"),
        ],
    )
    def test_nameless_providers_are_live_with_no_name(self, provider, provider_dir, fixture):
        body = read_fixture(provider_dir, fixture)
        result = run(provider, "acmewidgets", always(200, content=body))
        assert result.outcome is ProbeOutcome.LIVE
        assert result.org_name is None

    def test_personio_xml_is_live(self):
        body = read_fixture("personio", "normal.xml")
        result = run(P.PERSONIO, "strohm.jobs.personio.com", always(200, content=body))
        assert result.outcome is ProbeOutcome.LIVE
        assert result.posting_count and result.posting_count > 0

    @pytest.mark.parametrize(
        ("provider", "provider_dir", "fixture"),
        [
            (P.LEVER, "lever", "empty.json"),
            (P.ASHBY, "ashby", "empty.json"),
            (P.BAMBOOHR, "bamboohr", "empty.json"),
            (P.WORKABLE, "workable", "empty.json"),
            (P.BREEZY_HR, "breezy", "empty.json"),
            (P.RIPPLING, "rippling", "list_empty.json"),
        ],
    )
    def test_an_empty_board_is_live_with_zero_postings(self, provider, provider_dir, fixture):
        body = read_fixture(provider_dir, fixture)
        result = run(provider, "acmewidgets", always(200, content=body))
        assert result.outcome is ProbeOutcome.LIVE
        assert result.posting_count == 0


class TestNotFound:
    @pytest.mark.parametrize(
        ("provider", "provider_dir", "fixture"),
        [
            (P.GREENHOUSE, "greenhouse", "not_found.json"),
            (P.LEVER, "lever", "not_found.json"),
            (P.ASHBY, "ashby", "not_found.json"),
            (P.RIPPLING, "rippling", "not_found.json"),
            (P.WORKABLE, "workable", "not_found.json"),
            (P.BREEZY_HR, "breezy", "not_found.json"),
        ],
    )
    def test_404_is_not_found(self, provider, provider_dir, fixture):
        body = read_fixture(provider_dir, fixture)
        result = run(provider, "acmewidgets", always(404, content=body))
        assert result.outcome is ProbeOutcome.NOT_FOUND

    def test_personio_404_is_not_found(self):
        body = read_fixture("personio", "not_found.txt")
        result = run(P.PERSONIO, "be-levels.jobs.personio.com", always(404, content=body))
        assert result.outcome is ProbeOutcome.NOT_FOUND


class TestNotABoard:
    def test_bamboohr_invalid_subdomain_redirect_to_marketing_page(self):
        """Confirmed live in M2: BambooHR 302s an unknown tenant to its own
        marketing homepage, which is a 200. That 200 is not a board."""
        marketing = read_fixture("bamboohr", "not_found.html")

        def handler(request):
            if request.url.host == "no-such-co.bamboohr.com":
                return respond(302, headers={"Location": "https://www.bamboohr.com/"})
            return respond(200, content=marketing)

        result = run(P.BAMBOOHR, "no-such-co", handler)
        assert result.outcome is ProbeOutcome.NOT_A_BOARD

    def test_a_redirect_off_the_expected_host_is_not_a_board_even_with_board_json(self):
        body = read_fixture("lever", "normal.json")

        def handler(request):
            if request.url.host == "api.lever.co":
                return respond(302, headers={"Location": "https://elsewhere.example/x"})
            return respond(200, content=body)

        result = run(P.LEVER, "acmewidgets", handler)
        assert result.outcome is ProbeOutcome.NOT_A_BOARD

    def test_personio_js_shell_is_not_a_board(self):
        body = read_fixture("personio", "not_xml.html")
        result = run(P.PERSONIO, "nexwafe.jobs.personio.de", always(200, content=body))
        assert result.outcome is ProbeOutcome.NOT_A_BOARD

    @pytest.mark.parametrize("provider", [P.GREENHOUSE, P.LEVER, P.WORKABLE, P.BREEZY_HR])
    def test_a_200_with_the_wrong_shape_is_not_a_board(self, provider):
        result = run(provider, "acmewidgets", always(200, content=b"<html>hello</html>"))
        assert result.outcome is ProbeOutcome.NOT_A_BOARD


class TestInconclusive:
    @pytest.mark.parametrize("status", [429, 500, 502, 503, 403])
    def test_throttling_server_errors_and_bot_blocks_are_inconclusive(self, status):
        result = run(P.GREENHOUSE, "acmewidgets", always(status))
        assert result.outcome is ProbeOutcome.INCONCLUSIVE

    def test_a_connection_failure_is_inconclusive_not_dead(self):
        """Zipline's live board was retired on an HTTP 0 (DEVLOG iteration 7)."""
        result = run(P.LEVER, "acmewidgets", refuse_connection)
        assert result.outcome is ProbeOutcome.INCONCLUSIVE


class TestSafety:
    def test_an_invalid_token_is_never_fetched(self):
        calls = []

        def handler(request):
            calls.append(request)
            return respond(200, json={"name": "x"})

        result = run(P.GREENHOUSE, "../../admin", handler)
        assert result.outcome is ProbeOutcome.NOT_FOUND
        assert calls == []

    def test_a_non_string_board_name_is_dropped_not_crashed_on(self):
        result = run(P.GREENHOUSE, "acmewidgets", always(200, json={"name": {"en": "Acme"}}))
        assert result.outcome is ProbeOutcome.LIVE
        assert result.org_name is None

    def test_probe_never_raises_on_a_broken_body(self):
        result = run(P.WORKABLE, "acmewidgets", always(200, content=b"\xff\xfe{not json"))
        assert result.outcome is ProbeOutcome.NOT_A_BOARD

    @pytest.mark.parametrize(
        ("provider", "token", "url"),
        [
            (P.GREENHOUSE, "t", "https://boards-api.greenhouse.io/v1/boards/t"),
            (P.LEVER, "t", "https://api.lever.co/v0/postings/t?mode=json&limit=1"),
            (P.ASHBY, "t", "https://api.ashbyhq.com/posting-api/job-board/t"),
            (P.RIPPLING, "t", "https://api.rippling.com/platform/api/ats/v2/board/t/jobs"),
            (P.BAMBOOHR, "t", "https://t.bamboohr.com/careers/list"),
            (P.WORKABLE, "t", "https://apply.workable.com/api/v1/widget/accounts/t"),
            (P.PERSONIO, "t.jobs.personio.de", "https://t.jobs.personio.de/xml?language=en"),
            (P.BREEZY_HR, "t", "https://t.breezy.hr/json"),
        ],
    )
    def test_probe_urls_match_the_m2_adapters(self, provider, token, url):
        assert probe_url(provider, token) == url
