"""Tests for src/ats_common.py — the plumbing every src/ats_*.py adapter shares.

parse_iso_or_epoch_ms is tested directly because every provider disagrees on date
shape: Lever is undocumented epoch milliseconds, everyone else is an ISO-8601
string, and Workable's published_on is date-only (no time component). A bug here
silently breaks posted_at across every adapter at once.
"""

from datetime import UTC, datetime

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.models import Posting


def test_adapter_result_defaults_to_empty_postings_on_failure():
    result = AdapterResult(ok=False, error="HTTP 404")
    assert result.postings == ()
    assert result.error == "HTTP 404"


def test_adapter_result_carries_postings_on_success():
    posting = Posting(company_id=1, ats_job_id="1", title_raw="Engineer")
    result = AdapterResult(ok=True, postings=(posting,))
    assert result.ok
    assert result.postings == (posting,)


def test_parse_iso_or_epoch_ms_handles_lever_epoch_milliseconds():
    # Real value shape from Lever's undocumented createdAt (SPEC.md §9).
    # 1758585600000 ms == 1758585600 s == 2025-09-23T00:00:00Z.
    assert parse_iso_or_epoch_ms(1758585600000) == datetime(
        2025, 9, 23, 0, 0, tzinfo=UTC
    )


def test_parse_iso_or_epoch_ms_handles_iso_string_with_z_suffix():
    assert parse_iso_or_epoch_ms("2026-09-11T15:05:27.198Z") == datetime(
        2026, 9, 11, 15, 5, 27, 198000, tzinfo=UTC
    )


def test_parse_iso_or_epoch_ms_handles_date_only_string():
    # Workable's published_on: "2026-09-21", no time component.
    assert parse_iso_or_epoch_ms("2026-09-21") == datetime(2026, 9, 21, tzinfo=UTC)


def test_parse_iso_or_epoch_ms_returns_none_for_junk():
    assert parse_iso_or_epoch_ms(None) is None
    assert parse_iso_or_epoch_ms("") is None
    assert parse_iso_or_epoch_ms("not a date") is None
    assert parse_iso_or_epoch_ms(object()) is None
