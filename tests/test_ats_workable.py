"""Tests for src/ats_workable.py.

The endpoint here (apply.workable.com/api/v1/widget/accounts/{company}) is
public and unauthenticated — a separate surface from Workable's documented,
authenticated admin API (spi/v3/jobs). Confirmed live 2026-09-24: no
compensation field exists on this endpoint, so comp_data_quality is always
NONE here, unlike the admin API's documented salary object.
"""

import httpx

from src.ats_workable import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_account_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    assert any(p.department_raw for p in result.postings)


def test_telecommuting_flag_maps_to_workplace_type_raw():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    remote = [p for p in result.postings if p.workplace_type_raw == "remote"]
    onsite = [p for p in result.postings if p.workplace_type_raw is None]
    assert remote  # the fixture's first job has telecommuting: true
    assert onsite  # the others have telecommuting: false


def test_no_compensation_field_on_this_endpoint_is_none_quality():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)


def test_empty_account_is_ok_with_zero_postings():
    body = read_fixture("workable", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="empty-co")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("workable", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("workable", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-account")

    assert result.ok is False
    assert len(attempts) == 1
