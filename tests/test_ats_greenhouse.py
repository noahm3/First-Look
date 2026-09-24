"""Tests for src/ats_greenhouse.py.

Fixtures recorded live 2026-09 against boards-api.greenhouse.io (SPEC.md §9,
C-2.7) — see tests/fixtures/ats/greenhouse/. No test here opens a socket
(tests/conftest.py blocks it); every response is replayed from a fixture file.
"""

import httpx

from src.ats_greenhouse import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("greenhouse", "normal.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "boards-api.greenhouse.io" in str(request.url)
        assert "content=true" in str(request.url)
        return httpx.Response(200, content=body)

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

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert any(p.department_raw for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("greenhouse", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("greenhouse", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken-board")

    assert result.ok is False
    assert result.error


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("greenhouse", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-token")

    assert result.ok is False
    assert len(attempts) == 1  # BUILD.md §3: a 404 is an answer, never retried


def test_no_comp_data_observed_on_this_board_is_none_quality():
    # Confirmed live 2026-09-22 against 384 postings on 8 mapped boards:
    # pay_input_ranges appears on none of them (SPEC.md §9).
    body = read_fixture("greenhouse", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)
