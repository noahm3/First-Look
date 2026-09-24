"""Tests for src/ats_breezy.py.

The endpoint here ({company}.breezy.hr/json) is public and unauthenticated —
a separate surface from Breezy's documented, authenticated admin API
(api.breezy.hr/v3). salary is a free-text string (confirmed live 2026-09-24,
e.g. "$110,000 - $140,000 / year"), not a structured object — classified
PARSED, not STRUCTURED. The fixture carries two real companies' jobs: one
with a populated department and an empty salary string, one with a null
department and a real salary string.
"""

from src.ats_breezy import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture, respond


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("breezy", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated_where_present():
    body = read_fixture("breezy", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    assert any(p.department_raw for p in result.postings)
    assert any(p.department_raw is None for p in result.postings)


def test_free_text_salary_string_is_parsed_not_structured():
    body = read_fixture("breezy", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    salaried = [p for p in result.postings if p.comp_raw_summary]
    assert salaried
    assert all(p.comp_data_quality == CompDataQuality.PARSED for p in salaried)
    # An empty salary string must not count as disclosed.
    empty_salary = [p for p in result.postings if not p.comp_raw_summary]
    assert all(p.comp_data_quality == CompDataQuality.NONE for p in empty_salary)


def test_is_remote_false_never_mapped_to_remote():
    body = read_fixture("breezy", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    # Both live jobs in the fixture have is_remote: false.
    assert all(p.workplace_type_raw != "remote" for p in result.postings)


def test_location_as_a_bare_string_does_not_crash_the_fetch():
    # Undocumented public board endpoint -- a `location` field that isn't
    # the usual {"name", "is_remote"} object must degrade, never raise.
    def handler(_request):
        return respond(200, content=b'[{"id": "1", "name": "T", "location": "Remote"}]')

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="drifted")

    assert result.ok
    assert result.postings[0].location_raw is None
    assert result.postings[0].workplace_type_raw is None


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("breezy", "empty.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="empty-co")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("breezy", "malformed.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("breezy", "not_found.json")
    attempts = []

    def handler(request):
        attempts.append(request)
        return respond(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-company")

    assert result.ok is False
    assert len(attempts) == 1
