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
