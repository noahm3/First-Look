"""Tests for src/ats_greenhouse.py.

Fixtures recorded live 2026-09 against boards-api.greenhouse.io (SPEC.md §9,
C-2.7) — see tests/fixtures/ats/greenhouse/. No test here opens a socket
(tests/conftest.py blocks it); every response is replayed from a fixture file.
"""

from src.ats_greenhouse import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture, respond


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("greenhouse", "normal.json")

    def handler(request):
        assert "boards-api.greenhouse.io" in str(request.url)
        assert "content=true" in str(request.url)
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url
        assert posting.company_id == 1


def test_department_raw_populated_from_departments_field():
    body = read_fixture("greenhouse", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert any(p.department_raw for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("greenhouse", "empty.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("greenhouse", "malformed.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken-board")

    assert result.ok is False
    assert result.error


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("greenhouse", "not_found.json")
    attempts = []

    def handler(request):
        attempts.append(request)
        return respond(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-token")

    assert result.ok is False
    assert len(attempts) == 1  # BUILD.md §3: a 404 is an answer, never retried


def test_location_as_a_bare_string_does_not_crash_the_fetch():
    # Undocumented endpoint (SPEC.md §9 warns shapes drift). A `location`
    # field that isn't the usual {"name": ...} object must degrade that
    # posting's location_raw, never raise out of the per-company fetch.
    def handler(_request):
        return respond(
            200,
            json={"jobs": [{"id": 1, "title": "T", "location": "Remote"}]},
        )

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="drifted")

    assert result.ok
    assert result.postings[0].location_raw is None


def test_response_too_large_falls_back_to_the_plain_list_instead_of_losing_the_company():
    # A board with full descriptions can exceed the response size cap with
    # content=true (DEVLOG.md's iteration7 entry recorded a real 400+
    # posting board hitting this and recovered 618 postings via this exact
    # fallback). Losing department_raw for a company beats losing the
    # company outright.
    normal_body = read_fixture("greenhouse", "normal.json")
    plain_body = b'{"jobs":[{"id":1,"title":"T","absolute_url":"https://x/1"}]}'
    calls = []

    def handler(request):
        url = str(request.url)
        calls.append(url)
        if "content=true" in url:
            return respond(200, content=normal_body)
        return respond(200, content=plain_body)

    with fake_client(handler, max_response_bytes=len(normal_body) - 1) as client:
        result = fetch_postings(client, company_id=1, token="huge-board")

    assert result.ok
    assert len(result.postings) > 0
    assert len(calls) == 2  # the content=true attempt, then the plain-list fallback
    assert result.postings[0].department_raw is None  # lost with the fallback, not the company


def test_no_comp_data_observed_on_this_board_is_none_quality():
    # Confirmed live 2026-09-22 against 384 postings on 8 mapped boards:
    # pay_input_ranges appears on none of them (SPEC.md §9).
    body = read_fixture("greenhouse", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)
