"""Tests for src/ats_ashby.py.

workplaceType is Ashby's structured field (OnSite/Hybrid/Remote, capitalised —
SPEC.md §9 corrected 2026-09-22: Lever exposes one too, not just Ashby).
compensation is a truthy object even when nothing is disclosed
(compensationTiers: [], summary null) — disclosure must be judged on the
tiers/summary, never on the object's own truthiness.
"""

from src.ats_ashby import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture, respond


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("ashby", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated():
    body = read_fixture("ashby", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert any(p.department_raw for p in result.postings)


def test_workplace_type_raw_captured_where_present():
    body = read_fixture("ashby", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert any(p.workplace_type_raw for p in result.postings)


def test_structured_compensation_tiers_are_structured_quality():
    body = read_fixture("ashby", "normal.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert any(p.comp_data_quality == CompDataQuality.STRUCTURED for p in result.postings)


def test_truthy_but_empty_compensation_object_is_none_quality():
    import json

    body = read_fixture("ashby", "normal.json")
    jobs = json.loads(body)
    for job in jobs.get("jobs", []):
        job["compensation"] = {"compensationTiers": [], "compensationTierSummary": None}
    patched_body = json.dumps(jobs).encode()

    def handler(_request):
        return respond(200, content=patched_body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)


def test_compensation_as_a_bare_string_does_not_crash_the_fetch():
    # Undocumented sub-field drift (SPEC.md §9 corrects a factual claim
    # about this same field already) -- must degrade to NONE, never raise.
    def handler(_request):
        return respond(
            200,
            json={"jobs": [{"id": "1", "title": "T", "compensation": "n/a"}]},
        )

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="drifted")

    assert result.ok
    assert result.postings[0].comp_data_quality == CompDataQuality.NONE


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("ashby", "empty.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("ashby", "malformed.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("ashby", "not_found.json")
    attempts = []

    def handler(request):
        attempts.append(request)
        return respond(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-board")

    assert result.ok is False
    assert len(attempts) == 1
