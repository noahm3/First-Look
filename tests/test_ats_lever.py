"""Tests for src/ats_lever.py.

createdAt is Lever's undocumented epoch-ms field (SPEC.md §9) — a missing one
must produce posted_at=None, never an exception (C-2.6). The "empty board"
fixture is constructed (`[]`), not live-captured: Appcues, the M1 watchlist's
real zero-postings example, was re-checked 2026-09-24 while building this
fixture and now 404s outright (board removed since the 2026-09-23 watchlist
entry was written) — a real, fast-moving finding worth a DEVLOG note, not a
bug in this test.
"""

import httpx

from src.ats_lever import fetch_postings
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("lever", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated_from_categories_team():
    body = read_fixture("lever", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert any(p.department_raw for p in result.postings)


def test_workplace_type_raw_captured():
    body = read_fixture("lever", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert any(p.workplace_type_raw for p in result.postings)


def test_constructed_empty_board_is_ok_with_zero_postings():
    body = read_fixture("lever", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_missing_created_at_produces_null_not_exception():
    import json

    jobs = json.loads(read_fixture("lever", "normal.json"))
    jobs[0].pop("createdAt", None)
    body = json.dumps(jobs).encode()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert result.ok
    assert result.postings[0].posted_at is None


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("lever", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_unexpected_top_level_shape_is_a_classified_failure():
    # Lever's board is a bare JSON array; an object at the top level is invalid.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"not": "an array"}')

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("lever", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-site")

    assert result.ok is False
    assert len(attempts) == 1
