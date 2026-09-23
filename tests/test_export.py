"""Tests for src/export.py and the committed jobs-recent.json fixture.

The fixture is a contract, not a sample: M9's dashboard is built against it with
no database behind it (BUILD.md §3), so the assertions here are what stop the two
drifting apart.
"""

import json
import pathlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.export import (
    EXPORT_SCHEMA_VERSION,
    ExportMeta,
    build_export,
    is_stale,
    posting_to_row,
    to_annual_usd,
)
from src.models import Company, CompDataQuality, CompPeriod, CompTier, LocationClass, Posting

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "jobs-recent.json"
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def a_company(**overrides) -> Company:
    base = {"name": "Acme Grid Energy", "canonical_domain": "acmegrid.example"}
    return Company(**{**base, **overrides})


def a_posting(**overrides) -> Posting:
    base = {
        "company_id": 1,
        "ats_job_id": "1001",
        "title_raw": "Senior Product Manager",
        "id": 1001,
        "first_seen_at": NOW,
    }
    return Posting(**{**base, **overrides})


# ---------------------------------------------------------------------------
# Normalization — SPEC.md §11
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_an_annual_usd_figure_passes_through(self):
        assert to_annual_usd(Decimal("190000"), CompPeriod.YEAR, "USD") == 190000

    def test_an_hourly_rate_becomes_annual(self):
        # §11: hour x 2080. Without this an hourly posting silently never matches
        # a $200k filter.
        assert to_annual_usd(Decimal("52.00"), CompPeriod.HOUR, "USD") == 108160

    def test_monthly_and_weekly_convert(self):
        assert to_annual_usd(Decimal("10000"), CompPeriod.MONTH, "USD") == 120000
        assert to_annual_usd(Decimal("2000"), CompPeriod.WEEK, "USD") == 104000

    def test_a_foreign_currency_is_converted_before_comparison(self):
        assert to_annual_usd(Decimal("165000"), CompPeriod.YEAR, "CAD") == 120450

    def test_currency_matching_is_case_insensitive(self):
        assert to_annual_usd(Decimal("100"), CompPeriod.YEAR, "usd") == 100

    def test_a_missing_currency_is_assumed_usd(self):
        assert to_annual_usd(Decimal("100"), CompPeriod.YEAR, None) == 100

    def test_an_unknown_currency_returns_none_rather_than_a_guess(self):
        # §3.8: a wrong number here fails a filter silently for months.
        assert to_annual_usd(Decimal("100"), CompPeriod.YEAR, "JPY") is None

    def test_an_unknown_period_returns_none(self):
        assert to_annual_usd(Decimal("100"), None, "USD") is None

    def test_a_missing_amount_returns_none(self):
        assert to_annual_usd(None, CompPeriod.YEAR, "USD") is None


# ---------------------------------------------------------------------------
# Row shape
# ---------------------------------------------------------------------------


class TestRowShape:
    def test_every_tier_is_exported_not_just_the_collapsed_values(self):
        # The reason C-5.2 is answerable client-side at all.
        posting = a_posting(
            comp_tier_count=2,
            comp_floor_annual_usd=150000,
            comp_best_annual_usd=260000,
            tiers=(
                CompTier(
                    tier_label="Zone A",
                    min_amount=Decimal("150000"),
                    max_amount=Decimal("180000"),
                    currency="USD",
                    period=CompPeriod.YEAR,
                ),
                CompTier(
                    tier_label="Zone B",
                    min_amount=Decimal("210000"),
                    max_amount=Decimal("260000"),
                    currency="USD",
                    period=CompPeriod.YEAR,
                ),
            ),
        )
        row = posting_to_row(posting, a_company())
        assert len(row["comp"]["tiers"]) == 2
        assert [t["label"] for t in row["comp"]["tiers"]] == ["Zone A", "Zone B"]

    def test_a_tier_carries_both_published_and_normalized_values(self):
        posting = a_posting(
            tiers=(
                CompTier(
                    min_amount=Decimal("52.00"),
                    max_amount=Decimal("61.50"),
                    currency="USD",
                    period=CompPeriod.HOUR,
                ),
            )
        )
        tier = posting_to_row(posting, a_company())["comp"]["tiers"][0]
        assert tier["min"] == 52.0 and tier["period"] == "hour"
        assert tier["min_annual_usd"] == 108160

    def test_an_undisclosed_posting_exports_a_null_summary_not_an_empty_string(self):
        # C-9.11 renders "comp not disclosed" off this. An empty string would read
        # as a blank field, which is exactly what §12.5 forbids.
        row = posting_to_row(a_posting(), a_company())
        assert row["comp"]["summary"] is None
        assert row["comp"]["quality"] == CompDataQuality.NONE.value

    def test_a_hostile_url_is_exported_verbatim_for_the_dashboard_to_reject(self):
        # Sanitizing here would hide the problem from the layer that must handle
        # it, and the dashboard is the only place that knows it is rendering an
        # href (SECURITY.md §S1).
        row = posting_to_row(a_posting(url="javascript:alert(1)"), a_company())
        assert row["url"] == "javascript:alert(1)"

    def test_unknown_location_class_survives_as_a_real_value(self):
        row = posting_to_row(a_posting(location_class=LocationClass.UNKNOWN), a_company())
        assert row["location_class"] == "unknown"


class TestBuildExport:
    def test_closed_postings_are_excluded(self):
        rows = [
            (a_posting(id=1), a_company()),
            (a_posting(id=2, closed_at=NOW), a_company()),
        ]
        payload = build_export(rows, ExportMeta(generated_at=NOW))
        assert [p["id"] for p in payload["postings"]] == [1]

    def test_postings_are_sorted_newest_first(self):
        rows = [
            (a_posting(id=1, first_seen_at=NOW - timedelta(days=2)), a_company()),
            (a_posting(id=2, first_seen_at=NOW), a_company()),
            (a_posting(id=3, first_seen_at=NOW - timedelta(days=1)), a_company()),
        ]
        payload = build_export(rows, ExportMeta(generated_at=NOW))
        assert [p["id"] for p in payload["postings"]] == [2, 3, 1]

    def test_counts_reflect_what_shipped_not_what_was_offered(self):
        rows = [
            (a_posting(id=1), a_company(name="A")),
            (a_posting(id=2), a_company(name="A")),
            (a_posting(id=3, closed_at=NOW), a_company(name="B")),
        ]
        payload = build_export(rows, ExportMeta(generated_at=NOW))
        assert payload["counts"] == {"postings": 2, "companies": 1}

    def test_an_empty_export_is_valid_not_an_error(self):
        # M0's monitor does nothing and still has to write a usable file (C-0.9),
        # and the dashboard has to tell "no jobs in the database" apart from
        # "last run failed" (§12.7).
        payload = build_export([], ExportMeta(generated_at=NOW))
        assert payload["postings"] == []
        assert payload["counts"]["postings"] == 0
        assert payload["schema_version"] == EXPORT_SCHEMA_VERSION


class TestStaleness:
    def test_a_recent_run_is_not_stale(self):
        assert not is_stale(NOW - timedelta(hours=6), NOW)

    def test_over_48_hours_is_stale(self):
        assert is_stale(NOW - timedelta(hours=49), NOW)

    def test_never_having_run_is_stale(self):
        assert is_stale(None, NOW)


# ---------------------------------------------------------------------------
# The committed fixture
# ---------------------------------------------------------------------------


class TestFixtureContract:
    def test_it_is_valid_json_at_the_current_schema_version(self, payload):
        assert payload["schema_version"] == EXPORT_SCHEMA_VERSION

    def test_it_declares_the_keys_the_dashboard_reads(self, payload):
        assert set(payload) >= {
            "schema_version",
            "generated_at",
            "last_successful_run",
            "run_id",
            "stale",
            "counts",
            "postings",
        }

    def test_its_counts_match_its_contents(self, payload):
        assert payload["counts"]["postings"] == len(payload["postings"])

    def test_every_row_has_the_shape_posting_to_row_produces(self, payload):
        reference = set(posting_to_row(a_posting(), a_company()))
        for row in payload["postings"]:
            assert set(row) == reference, f"row {row['id']} has drifted from the real shape"

    def test_it_carries_the_multi_band_case_c_5_2_turns_on(self, payload):
        row = next(r for r in payload["postings"] if r["comp"]["tier_count"] == 2)
        tiers = row["comp"]["tiers"]

        # The collapsed pair looks like it satisfies "min >= 200k and max <= 240k"...
        assert row["comp"]["floor_annual_usd"] <= 200000
        assert row["comp"]["best_annual_usd"] >= 240000
        # ...but no single band does, which is the whole point of C-5.2.
        assert not any(
            t["min_annual_usd"] >= 200000 and t["max_annual_usd"] <= 240000 for t in tiers
        )

    def test_it_carries_an_undisclosed_comp_row(self, payload):
        assert any(r["comp"]["summary"] is None for r in payload["postings"])

    def test_it_carries_an_hourly_row_normalized_to_annual(self, payload):
        tier = next(
            t for r in payload["postings"] for t in r["comp"]["tiers"] if t["period"] == "hour"
        )
        assert tier["min_annual_usd"] == int(round(tier["min"] * 2080))

    def test_it_carries_a_non_usd_row_converted(self, payload):
        tier = next(
            t for r in payload["postings"] for t in r["comp"]["tiers"] if t["currency"] == "CAD"
        )
        assert tier["min_annual_usd"] != int(tier["min"])

    def test_it_carries_an_unknown_location_class(self, payload):
        # C-9.12 needs something to select.
        assert any(r["location_class"] == "unknown" for r in payload["postings"])

    def test_it_carries_securitys_exact_xss_row(self, payload):
        # SECURITY.md §S1's stated test, present from M0 so M9's render path is
        # written against it rather than audited afterwards.
        hostile = next(r for r in payload["postings"] if r["url"].startswith("javascript:"))
        assert "onerror" in hostile["title"]
        assert "<script>" in hostile["comp"]["summary"]

    def test_it_carries_a_repost(self, payload):
        assert any(r["is_repost"] for r in payload["postings"])
