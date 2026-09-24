"""Tests for src/ats_rippling.py.

Unlike Greenhouse, the per-job detail call here is NOT redundant: createdOn
(a real posted date) and payRangeDetails (structured comp) exist only on the
detail endpoint (SPEC.md §9, confirmed in spikes/iteration11_rippling_spike.py).
Fixtures are real: adiabatic's "Senior Organic Chemist" posting, live-checked
2026-09-24, one of the few Rippling postings found with a populated
payRangeDetails block. Token resolution (finding which token a company's
careers page uses) is M3's job, not this adapter's — this adapter takes an
already-known token.
"""

import json

import httpx

from src.ats_rippling import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def _handler(list_body: bytes, detail_body: bytes | None, detail_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/jobs/" in url.rsplit("/board/", 1)[-1]:
            if detail_body is None:
                return httpx.Response(404, content=b'{"error": "not found"}')
            return httpx.Response(detail_status, content=detail_body)
        return httpx.Response(200, content=list_body)

    return handler


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    list_body = read_fixture("rippling", "list_normal.json")
    detail_body = read_fixture("rippling", "detail_normal.json")

    with fake_client(_handler(list_body, detail_body)) as client:
        result = fetch_postings(client, company_id=1, token="adiabatic")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_detail_call_supplies_posted_at_and_structured_comp():
    list_body = read_fixture("rippling", "list_normal.json")
    detail_body = read_fixture("rippling", "detail_normal.json")
    detail = json.loads(detail_body)
    assert detail.get("payRangeDetails"), (
        "fixture must include a real payRangeDetails block to exercise this test"
    )

    with fake_client(_handler(list_body, detail_body)) as client:
        result = fetch_postings(client, company_id=1, token="adiabatic")

    assert any(p.posted_at is not None for p in result.postings)
    assert any(p.comp_data_quality == CompDataQuality.STRUCTURED for p in result.postings)


def test_failed_detail_call_still_returns_the_posting_degraded():
    list_body = read_fixture("rippling", "list_normal.json")

    with fake_client(_handler(list_body, detail_body=None)) as client:
        result = fetch_postings(client, company_id=1, token="adiabatic")

    # Losing the detail call loses posted_at/comp, not the whole company
    # (mirrors Greenhouse's degrade-don't-drop precedent, SPEC.md §9).
    assert result.ok
    assert len(result.postings) > 0
    assert all(p.posted_at is None for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("rippling", "list_empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("rippling", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("rippling", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-board")

    assert result.ok is False
    assert len(attempts) == 1
