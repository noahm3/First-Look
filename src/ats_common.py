"""Shared plumbing for src/ats_*.py adapters.

Each adapter converts one provider's response into `src.models.Posting`
immediately, per that module's own docstring, so provider shapes never leak
past the adapter boundary (BUILD.md §3). This module holds the two things
every adapter needs and none should reimplement.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from src.models import Posting


@dataclass(frozen=True, slots=True)
class AdapterResult:
    """Outcome of one fetch-and-parse pass for one company.

    Mirrors src.http.FetchResult's "nothing raises" contract at the adapter
    layer (SPEC.md §3.7): a malformed response is a result to record, never
    an exception to propagate into the per-company polling loop.
    """

    ok: bool
    postings: tuple[Posting, ...] = ()
    error: str | None = None
    # A per-job sub-fetch failed (e.g. Rippling's detail call) but the
    # posting itself was still returned, degraded rather than dropped. Kept
    # separate from `error` because the overall fetch is still `ok`.
    degraded_count: int = 0


def as_dict(value: object) -> dict:
    """Return value if it's a dict, else an empty dict. Never raises.

    Every adapter reads at least one nested provider field (a location,
    department, or compensation object) with `.get()`. A provider whose
    shape drifts to a bare string or null there must degrade that field,
    not crash the whole company's fetch (BUILD.md §3: no exception escapes
    a per-company operation).
    """
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list:
    """Return value if it's a list, else an empty list. Never raises."""
    return value if isinstance(value, list) else []


def parse_iso_or_epoch_ms(value: object) -> datetime | None:
    """Provider date -> aware UTC datetime, or None. Never raises.

    Handles Lever's undocumented epoch-ms integers and every other
    provider's ISO-8601 (full timestamp or date-only) strings in one place,
    so a provider returning the wrong shape produces a null field
    (BUILD.md §6), not a crash.
    """
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None
