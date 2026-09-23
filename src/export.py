"""The `jobs-recent.json` export — the contract between pipeline and dashboard.

Settled at M0 with a committed fixture, per BUILD.md §3, because it is what lets
M9's dashboard be built and tested without a live database behind it.

Two shape decisions carry real weight:

*   **Every compensation tier ships, not just the collapsed values.** SPEC.md §11
    is explicit that the authoritative filter question is "does any *single* tier
    satisfy all active conditions", and §12.2 puts the filters client-side. So the
    tiers have to reach the browser, or C-5.2 — a multi-band posting where no one
    band satisfies a combined min+max filter — cannot be answered correctly. The
    collapsed `comp_best_annual_usd` fields ride along for sorting only.

*   **Each tier carries both what was published and a normalized annual USD
    figure.** §11: filters operate only on normalized values, because raw
    comparison means hourly postings silently never match. The raw values stay so
    a card can show what the employer actually wrote.

Only open postings and only fields the cards use (§12.8). Past ~3MB the file
shards by month, and §18's coverage sample decides whether that applies — nothing
here should build sharding before then.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.models import Company, CompPeriod, CompTier, Posting

# Bumped whenever the shape changes incompatibly, so a dashboard served from a
# stale cache can say so rather than rendering half a page.
EXPORT_SCHEMA_VERSION = 1

# SPEC.md §11's normalization. The currency table is deliberately hardcoded and
# refreshed approximately never: ±5% is irrelevant at a screening threshold, and
# only these four currencies matter.
PERIODS_PER_YEAR: dict[CompPeriod, int] = {
    CompPeriod.YEAR: 1,
    CompPeriod.MONTH: 12,
    CompPeriod.WEEK: 52,
    CompPeriod.HOUR: 2080,
}

USD_PER_UNIT: dict[str, float] = {
    "USD": 1.0,
    "CAD": 0.73,
    "EUR": 1.08,
    "GBP": 1.27,
}


def to_annual_usd(
    amount: Decimal | float | None, period: CompPeriod | None, currency: str | None
) -> int | None:
    """Normalize a published figure to whole USD per year, or None.

    Returns None rather than guessing when the period or currency is unknown — a
    wrong number here silently fails a filter for months, which is exactly the
    §3.8 case where missing beats wrong.
    """
    if amount is None or period is None:
        return None
    rate = USD_PER_UNIT.get((currency or "USD").upper())
    if rate is None:
        return None
    return int(round(float(amount) * PERIODS_PER_YEAR[period] * rate))


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def tier_to_row(tier: CompTier) -> dict[str, Any]:
    return {
        "label": tier.tier_label,
        # What the employer published, kept verbatim alongside the derived value.
        "min": float(tier.min_amount) if tier.min_amount is not None else None,
        "max": float(tier.max_amount) if tier.max_amount is not None else None,
        "currency": tier.currency,
        "period": tier.period.value if tier.period else None,
        # What the filters actually compare against (§11).
        "min_annual_usd": to_annual_usd(tier.min_amount, tier.period, tier.currency),
        "max_annual_usd": to_annual_usd(tier.max_amount, tier.period, tier.currency),
    }


def posting_to_row(posting: Posting, company: Company) -> dict[str, Any]:
    """One card's worth of data. Nothing here is personal data (§15)."""
    return {
        "id": posting.id,
        "company": company.name,
        "company_domain": company.canonical_domain,
        # First two are shown on the card; the rest feed the Industry filter.
        "industry_tags": list(company.industry_tags),
        "is_climate": company.is_climate,
        "title": posting.title_raw,
        # Rendered as an href. The dashboard validates the scheme before rendering
        # it and drops the link otherwise — a javascript: URL in a posting executes
        # on click (SECURITY.md §S1). Exported verbatim; sanitizing here would hide
        # the problem from the place that must handle it.
        "url": posting.url,
        "department": posting.department_raw,
        "location_raw": posting.location_raw,
        "location_class": posting.location_class.value,
        "city": posting.city_raw,
        # THE date. The card says "Found Nh ago", which is what it means (§6).
        "first_seen_at": _isoformat(posting.first_seen_at),
        "is_repost": posting.is_repost,
        "comp": {
            # Verbatim, regardless of parse success (C-5.6). Null means undisclosed,
            # which the card renders as "comp not disclosed" and never as blank.
            "summary": posting.comp_raw_summary,
            "quality": posting.comp_data_quality.value,
            "tier_count": posting.comp_tier_count,
            "best_annual_usd": posting.comp_best_annual_usd,
            "floor_annual_usd": posting.comp_floor_annual_usd,
            "tiers": [tier_to_row(t) for t in posting.tiers],
        },
    }


@dataclass(frozen=True, slots=True)
class ExportMeta:
    generated_at: datetime
    last_successful_run: datetime | None = None
    run_id: int | None = None
    stale: bool = False


def build_export(
    rows: Iterable[tuple[Posting, Company]],
    meta: ExportMeta,
) -> dict[str, Any]:
    """Assemble the payload. Only open postings belong here (§12.8)."""
    postings = [posting_to_row(posting, company) for posting, company in rows if posting.is_open]
    # Newest first, matching the dashboard's only sort order (§4: "Output is
    # already filtered to new. Sort by date.").
    postings.sort(key=lambda row: row["first_seen_at"] or "", reverse=True)

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": _isoformat(meta.generated_at),
        "last_successful_run": _isoformat(meta.last_successful_run),
        "run_id": meta.run_id,
        # Drives the stale banner on the main page. Without it a broken pipeline
        # looks identical to a quiet week (§12.1).
        "stale": meta.stale,
        "counts": {
            "postings": len(postings),
            "companies": len({row["company"] for row in postings}),
        },
        "postings": postings,
    }


def write_export(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write the export, creating parent directories as needed."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return destination


def is_stale(last_successful_run: datetime | None, now: datetime, *, hours: int = 48) -> bool:
    """SPEC.md §12.1: the banner shows when the last run failed or is over 48h old."""
    if last_successful_run is None:
        return True
    return (now - last_successful_run).total_seconds() > hours * 3600


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "ExportMeta",
    "build_export",
    "is_stale",
    "posting_to_row",
    "tier_to_row",
    "to_annual_usd",
    "write_export",
]
