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

from src.ats_rippling import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture, respond


def _handler(list_body: bytes, detail_body: bytes | None, detail_status: int = 200):
    def handler(request):
        url = str(request.url)
        if "/jobs/" in url.rsplit("/board/", 1)[-1]:
            if detail_body is None:
                return respond(404, content=b'{"error": "not found"}')
            return respond(detail_status, content=detail_body)
        return respond(200, content=list_body)

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
    # (mirrors Greenhouse's degrade-don't-drop precedent, SPEC.md §9) --
    # and it must be visible via degraded_count, not silent.
    assert result.ok
    assert len(result.postings) > 0
    assert all(p.posted_at is None for p in result.postings)
    assert result.degraded_count == len(result.postings)


def test_department_as_a_bare_string_does_not_crash_the_fetch():
    # Undocumented v2 endpoint (SPEC.md §9) -- a `department` field that
    # isn't the usual {"name": ...} object must degrade, never raise.
    list_body = (
        b'{"items":[{"id":"1","name":"T","department":"Eng"}],'
        b'"page":0,"pageSize":20,"totalItems":1,"totalPages":1}'
    )
    detail_body = read_fixture("rippling", "detail_normal.json")

    with fake_client(_handler(list_body, detail_body)) as client:
        result = fetch_postings(client, company_id=1, token="drifted")

    assert result.ok
    assert result.postings[0].department_raw is None


def test_multi_page_board_fetches_every_page_not_just_the_first():
    # Confirmed live 2026-09-24: real boards do exceed the 20-item pageSize
    # (spikes/iteration11_rippling_full_results.json has boards with 33-112
    # postings). A board that silently truncated to page 0 would report
    # ok=True with a wrong-but-plausible low count -- exactly the "degrades
    # quietly" failure this project's own principles reject.
    page0 = {
        "items": [{"id": str(i), "name": f"Job {i}"} for i in range(20)],
        "page": 0,
        "pageSize": 20,
        "totalItems": 25,
        "totalPages": 2,
    }
    page1 = {
        "items": [{"id": str(i), "name": f"Job {i}"} for i in range(20, 25)],
        "page": 1,
        "pageSize": 20,
        "totalItems": 25,
        "totalPages": 2,
    }
    detail = {"createdOn": None, "payRangeDetails": []}

    def handler(request):
        url = str(request.url)
        if "/jobs/" in url.rsplit("/board/", 1)[-1]:
            return respond(200, json=detail)
        if "page=1" in url:
            return respond(200, json=page1)
        return respond(200, json=page0)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="big-board")

    assert result.ok
    assert len(result.postings) == 25
    assert {p.ats_job_id for p in result.postings} == {str(i) for i in range(25)}


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("rippling", "list_empty.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("rippling", "malformed.json")

    def handler(_request):
        return respond(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("rippling", "not_found.json")
    attempts = []

    def handler(request):
        attempts.append(request)
        return respond(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-board")

    assert result.ok is False
    assert len(attempts) == 1


# ---------------------------------------------------------------------------
# `detail_job_ids` -- M4 kickoff decision (DEVLOG): the poller passes only the
# job ids that actually need a detail call (new + backfill-eligible), instead
# of this adapter re-fetching detail for every posting on every poll.
# ---------------------------------------------------------------------------


def test_detail_job_ids_none_still_fetches_every_job_detail():
    list_body = read_fixture("rippling", "list_normal.json")
    detail_body = read_fixture("rippling", "detail_normal.json")
    detail_requests = []

    def handler(request):
        url = str(request.url)
        if "/jobs/" in url.rsplit("/board/", 1)[-1]:
            detail_requests.append(request)
            return respond(200, content=detail_body)
        return respond(200, content=list_body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="adiabatic")

    assert result.ok
    assert len(detail_requests) == len(result.postings)


def test_detail_job_ids_restricts_detail_calls_to_the_given_set():
    list_body = read_fixture("rippling", "list_normal.json")
    detail_body = read_fixture("rippling", "detail_normal.json")
    detail_requests = []

    def handler(request):
        url = str(request.url)
        if "/jobs/" in url.rsplit("/board/", 1)[-1]:
            detail_requests.append(url)
            return respond(200, content=detail_body)
        return respond(200, content=list_body)

    with fake_client(handler) as client:
        all_result = fetch_postings(client, company_id=1, token="adiabatic")
        job_ids = [p.ats_job_id for p in all_result.postings]

    with fake_client(handler) as client:
        result = fetch_postings(
            client, company_id=1, token="adiabatic", detail_job_ids={job_ids[0]}
        )

    assert result.ok
    assert len(result.postings) == len(job_ids)
    kept = [p for p in result.postings if p.ats_job_id == job_ids[0]]
    skipped = [p for p in result.postings if p.ats_job_id != job_ids[0]]
    assert kept[0].posted_at is not None
    assert all(p.posted_at is None for p in skipped)
    assert all(p.comp_data_quality == CompDataQuality.NONE for p in skipped)


def test_skipped_detail_calls_do_not_count_as_degraded():
    list_body = read_fixture("rippling", "list_normal.json")
    detail_body = read_fixture("rippling", "detail_normal.json")

    with fake_client(_handler(list_body, detail_body)) as client:
        result = fetch_postings(client, company_id=1, token="adiabatic", detail_job_ids=set())

    # Every job was skipped on purpose -- that is not a failed detail call,
    # so degraded_count (SPEC.md §3.8's "visible, not silent" signal) must
    # stay at zero rather than flagging every posting as degraded.
    assert result.ok
    assert result.degraded_count == 0
    assert all(p.posted_at is None for p in result.postings)
