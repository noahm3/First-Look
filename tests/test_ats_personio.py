"""Tests for src/ats_personio.py.

Personio's public XML feed is confirmed real and officially documented as a
feature (support.personio.de), unlike the other 4 new providers — but
confirmed live 2026-09-24 to be inconsistent across tenants: some 200+XML
(strohm.jobs.personio.com), some 404 (be-levels.jobs.personio.com), and an
earlier spike found a client-rendered HTML shell on a third tenant
(nexwafe) — re-checked live while writing this test and that specific
tenant now 307-redirects to personio.com instead, a fourth behavior. The
non-XML-200 fixture below is a defensive regression case for a shape this
project has genuinely observed at least once, not a claim that any specific
tenant reproduces it right now. This adapter must turn each of those into a
distinguishable, correctly-classified AdapterResult, never a crash from
feeding non-XML content to the XML parser.
"""

import httpx

from src.ats_personio import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_tenant_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("personio", "normal.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="strohm.jobs.personio.com")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url.startswith("https://strohm.jobs.personio.com/job/")


def test_structured_salary_information_is_structured_quality():
    body = read_fixture("personio", "normal.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="strohm.jobs.personio.com")

    assert any(p.comp_data_quality == CompDataQuality.STRUCTURED for p in result.postings)


def test_department_raw_populated():
    body = read_fixture("personio", "normal.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="strohm.jobs.personio.com")

    assert any(p.department_raw for p in result.postings)


def test_empty_tenant_is_ok_with_zero_postings():
    body = read_fixture("personio", "empty.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="empty.jobs.personio.com")

    assert result.ok
    assert result.postings == ()


def test_malformed_xml_is_a_classified_failure_not_a_crash():
    body = read_fixture("personio", "malformed.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="broken.jobs.personio.com")

    assert result.ok is False


def test_client_rendered_html_instead_of_xml_is_a_classified_failure():
    # A shape this project has genuinely observed once (an earlier spike on
    # a different tenant) — a defensive regression case, not a currently
    # reproducible live example.
    body = read_fixture("personio", "not_xml.html")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="nexwafe.jobs.personio.com")

    assert result.ok is False
    assert result.error


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("personio", "not_found.txt")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="be-levels.jobs.personio.com")

    assert result.ok is False
    assert len(attempts) == 1
