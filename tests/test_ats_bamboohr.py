"""Tests for src/ats_bamboohr.py.

BambooHR has no authoritative documentation (SPEC.md §9, same bucket as Lever
v0/Getro) and its list endpoint exposes neither a per-job URL nor a date
field (confirmed live 2026-09-24 against ph7.bamboohr.com/careers/list, full
body inspected). The URL is constructed from the known
{token}.bamboohr.com/careers/{id} pattern, confirmed live (200); posted_at
stays None rather than being invented.

An invalid subdomain does NOT 404 (confirmed live 2026-09-24): BambooHR
302-redirects it to the https://www.bamboohr.com marketing homepage, which
itself returns 200 HTML — src.http.FetchClient follows the redirect, so the
adapter sees a 200 response with an HTML body, not a 404 status. That is
exactly the "unexpected shape" failure path, not a distinct 404 path — there
is no 404 case to test for this provider.
"""

from src.ats_bamboohr import fetch_postings
from tests.ats_fixtures import fake_client, read_fixture, respond


def test_normal_board_returns_parsed_postings_with_titles_and_constructed_urls():
    body = read_fixture("bamboohr", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ph7")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url == f"https://ph7.bamboohr.com/careers/{posting.ats_job_id}"


def test_posted_at_stays_none_no_date_field_exists():
    body = read_fixture("bamboohr", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ph7")

    assert all(p.posted_at is None for p in result.postings)


def test_department_raw_populated_from_department_label():
    body = read_fixture("bamboohr", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ph7")

    assert any(p.department_raw for p in result.postings)


def test_location_as_a_bare_string_does_not_crash_the_fetch():
    # No authoritative docs (SPEC.md §9) -- a `location` field that isn't
    # the usual {"city", "state"} object must degrade, never raise.
    def handler(_request):
        return respond(
            200,
            content=b'{"meta":{"totalCount":1},"result":[{"id":"1","jobOpeningName":"T","location":"Remote"}]}',
        )

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="drifted")

    assert result.ok
    assert result.postings[0].location_raw is None


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("bamboohr", "empty.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("bamboohr", "malformed.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_invalid_subdomain_redirect_to_marketing_html_is_a_classified_failure():
    body = read_fixture("bamboohr", "not_found.html")

    def handler(_request):
        # Real behavior confirmed live: this is what the adapter sees after
        # src.http.FetchClient follows BambooHR's 302 to www.bamboohr.com.
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-company")

    assert result.ok is False
    assert result.error
