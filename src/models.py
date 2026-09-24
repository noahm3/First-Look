"""Domain dataclasses mirroring the SPEC.md §6 schema.

Adapters convert provider JSON into these immediately, so no provider's response
shape leaks past the adapter boundary (BUILD.md §3). Field names match the database
columns deliberately: one vocabulary across SQL, Python, and the JSON export beats
three that need translating.

Closed value sets are enums. `mapping_failure_reason` is deliberately *not* an enum
— SPEC.md §8.4's `unsupported_ats:{name}` carries the ATS's name in the value, and
that distribution is the measurement the adapter decision rests on (§8.6), so the
name has to survive.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class AtsProvider(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    # Detection from day one; the polling adapter waits on §18's measurement (SPEC §9).
    SMARTRECRUITERS = "smartrecruiters"
    # Added 2026-09-24, M2 scope expansion (SPEC.md §4/§9). Workday deliberately
    # excluded — deferred, see SPEC.md §4's Workday row.
    RIPPLING = "rippling"
    BAMBOOHR = "bamboohr"
    WORKABLE = "workable"
    PERSONIO = "personio"
    BREEZY_HR = "breezy_hr"


class AtsStatus(StrEnum):
    UNMAPPED = "unmapped"
    OK = "ok"
    FAILING = "failing"
    UNMAPPABLE = "unmappable"


class MappingConfidence(StrEnum):
    """SPEC.md §8.2. Only VERIFIED and PROBABLE ever enter the polling loop."""

    VERIFIED = "verified"
    PROBABLE = "probable"
    WEAK = "weak"


class CompDataQuality(StrEnum):
    STRUCTURED = "structured"
    PARSED = "parsed"
    NONE = "none"


class LocationClass(StrEnum):
    """SPEC.md §12.3. UNKNOWN is a visible filter option, never a guess at ONSITE."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class CompPeriod(StrEnum):
    YEAR = "year"
    MONTH = "month"
    WEEK = "week"
    HOUR = "hour"


class MappingFailureReason(StrEnum):
    """The closed members of SPEC.md §8.4's table.

    `unsupported_ats:{name}` is not here on purpose — build it with
    :func:`unsupported_ats`, which keeps the ATS name in the stored value.
    """

    JS_RENDERED = "js_rendered"
    NO_CAREERS_PAGE = "no_careers_page"
    WEAK_ONLY = "weak_only"
    UNKNOWN = "unknown"


UNSUPPORTED_ATS_PREFIX = "unsupported_ats:"


def unsupported_ats(name: str) -> str:
    """Build an `unsupported_ats:{name}` reason, preserving the ATS's name.

    SPEC.md §8.4: "Careers page shows an unsupported ATS. Record the name." The
    distribution of these names is what answers "which adapter, if any, next"
    (§8.6, §18 measurement 2), so collapsing them all into one bucket would throw
    away the measurement.
    """
    slug = name.strip().lower()
    if not slug:
        return MappingFailureReason.UNKNOWN.value
    return f"{UNSUPPORTED_ATS_PREFIX}{slug}"


@dataclass(frozen=True, slots=True)
class MappingResult:
    """Outcome of one pass of the SPEC.md §8.1 cascade for one company."""

    provider: AtsProvider | None = None
    token: str | None = None
    confidence: MappingConfidence | None = None
    method: str | None = None
    failure_reason: str | None = None

    @property
    def accepted(self) -> bool:
        """True only at `verified` or `probable` — SPEC.md §8.2.

        A `weak` result is a mapping failure and must not enter the polling loop:
        per §3.8 a known gap beats invisible bad data.
        """
        return self.confidence in (
            MappingConfidence.VERIFIED,
            MappingConfidence.PROBABLE,
        ) and bool(self.token)


@dataclass(frozen=True, slots=True)
class Company:
    name: str
    canonical_domain: str | None = None
    id: int | None = None
    is_climate: bool = False
    industry_tags: tuple[str, ...] = ()
    has_open_roles_signal: bool = False
    ats_provider: AtsProvider | None = None
    ats_token: str | None = None
    ats_status: AtsStatus = AtsStatus.UNMAPPED
    mapping_confidence: MappingConfidence | None = None
    mapping_method: str | None = None
    mapping_failure_reason: str | None = None
    mapping_last_attempt_at: datetime | None = None
    ats_last_success_at: datetime | None = None
    ats_consecutive_failures: int = 0
    last_nonzero_postings_at: datetime | None = None
    created_at: datetime | None = None

    @property
    def is_pollable(self) -> bool:
        """Whether the monitoring loop should poll this company at all.

        SPEC.md §3.10: only mapped ATS endpoints are polled. An unmapped company is
        invisible — that is the accepted cost of removing the Getro posting path
        (§5), and the reason mapping coverage is the top-line metric (§8.6).
        """
        return (
            self.ats_provider is not None
            and bool(self.ats_token)
            and self.ats_status in (AtsStatus.OK, AtsStatus.UNMAPPED)
            and self.mapping_confidence in (MappingConfidence.VERIFIED, MappingConfidence.PROBABLE)
        )


@dataclass(frozen=True, slots=True)
class CompTier:
    """One published compensation band.

    SPEC.md §11: never collapse these for filter evaluation. The authoritative
    question is whether any *single* tier satisfies all active conditions.
    `observed_at` makes a backfill an appended observation rather than an
    overwrite (§11.1) — a mid-posting range edit is signal, and overwriting
    destroys it silently.
    """

    tier_label: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    currency: str | None = None
    period: CompPeriod | None = None
    observed_at: datetime | None = None
    id: int | None = None
    posting_id: int | None = None


@dataclass(frozen=True, slots=True)
class Posting:
    company_id: int
    ats_job_id: str
    title_raw: str
    id: int | None = None
    department_raw: str | None = None
    # Verbatim, never overwritten (SPEC.md §4 rejects normalising it).
    location_raw: str | None = None
    # Ashby is the only provider exposing this as a structured field (§9).
    workplace_type_raw: str | None = None
    location_class: LocationClass = LocationClass.UNKNOWN
    city_raw: str | None = None
    url: str | None = None
    # THE date: sort key and the "Posted" filter. The UI says "Found Nh ago",
    # which is what it means. `posted_at` is informational only — Greenhouse's
    # list endpoint exposes only `updated_at`, which mutates on any edit (§6).
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    closed_at: datetime | None = None
    posted_at: datetime | None = None
    content_hash: str | None = None
    is_repost: bool = False
    comp_data_quality: CompDataQuality = CompDataQuality.NONE
    comp_raw_summary: str | None = None
    comp_best_annual_usd: int | None = None
    comp_floor_annual_usd: int | None = None
    comp_tier_count: int = 0
    tiers: tuple[CompTier, ...] = field(default_factory=tuple)

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def has_disclosed_comp(self) -> bool:
        """Undisclosed is a first-class state — never a reason to drop a row (§11)."""
        return self.comp_data_quality is not CompDataQuality.NONE
