"""Watchlist ingest and dedupe (SPEC.md §7.1, BUILD.md M1).

`config/watchlist.yml` is name + domain, committed and readable (BUILD.md §1.3).
Every entry becomes exactly one `companies` row no matter how many times this
runs (C-1.6), whether the domain is written as a bare host or a full URL with
a path and query string (C-1.7), and even when no domain exists at all
(C-1.8) -- Getro and Wellfound already prove real sources hit that case
(SPEC.md §7.2, §7.7), so this path has to handle it too rather than assume
every entry names a company with a resolvable site.

Usage:
    python -m src.watchlist [--watchlist config/watchlist.yml]
"""

import argparse
import logging
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import yaml

from src.db import Database, DatabaseUnavailable

log = logging.getLogger(__name__)

DEFAULT_WATCHLIST_PATH = pathlib.Path("config/watchlist.yml")

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    name: str
    domain: str | None = None


def load_watchlist(path: pathlib.Path = DEFAULT_WATCHLIST_PATH) -> list[WatchlistEntry]:
    """Parse config/watchlist.yml. A blank or missing `domain` is valid (C-1.8)."""
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    entries = []
    for item in raw:
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError(f"watchlist entry missing a name: {item!r}")
        domain = str(item.get("domain") or "").strip() or None
        entries.append(WatchlistEntry(name=name, domain=domain))
    return entries


def canonicalize_domain(raw: str | None) -> str | None:
    """Lowercase host only -- no scheme, no `www.`, no path, no query, no port.

    C-1.7: `https://www.x.com/careers?utm=1` and `x.com` must resolve to the
    same value. Accepts a bare host as well as a full URL, since watchlist
    entries and other sources both write domains either way.
    """
    if not raw or not raw.strip():
        return None
    candidate = raw.strip()
    if "//" not in candidate:
        candidate = f"//{candidate}"
    host = urlsplit(candidate).netloc.lower()
    host = host.rpartition("@")[2]  # strip any userinfo, defensively
    host = host.partition(":")[0]  # strip a port
    if host.startswith("www."):
        host = host[4:]
    return host or None


def slugify(name: str) -> str:
    """A stable identity key for companies with no domain.

    Used as `company_sources.source_id` so re-ingesting the same no-domain
    entry finds the row it already created instead of inserting a duplicate
    (C-1.6) -- `canonical_domain` can't serve as that key here because it's
    NULL, and NULLs never collide under a UNIQUE constraint.
    """
    slug = _SLUG_NON_ALNUM.sub("-", name.strip().lower()).strip("-")
    return slug or "unnamed"


def source_identity(entry: WatchlistEntry) -> tuple[str | None, str]:
    """(canonical_domain, source_id) for one entry -- the pair ingest keys on."""
    domain = canonicalize_domain(entry.domain)
    return domain, domain or f"name:{slugify(entry.name)}"


@dataclass(frozen=True, slots=True)
class IngestSummary:
    created: int = 0
    already_present: int = 0
    no_domain: int = 0

    @property
    def total(self) -> int:
        return self.created + self.already_present


def ingest_watchlist(db: Database, entries: list[WatchlistEntry]) -> IngestSummary:
    created = already_present = no_domain = 0
    for entry in entries:
        domain, source_id = source_identity(entry)
        if domain is None:
            no_domain += 1
        _company_id, was_created = db.ingest_manual_company(
            name=entry.name, canonical_domain=domain, source_id=source_id
        )
        if was_created:
            created += 1
        else:
            already_present += 1
    return IngestSummary(created=created, already_present=already_present, no_domain=no_domain)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watchlist", default=str(DEFAULT_WATCHLIST_PATH))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    entries = load_watchlist(pathlib.Path(args.watchlist))

    try:
        db = Database.from_env()
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    try:
        with db:
            summary = ingest_watchlist(db, entries)
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    print(
        f"watchlist: {len(entries)} entries -> {summary.created} created, "
        f"{summary.already_present} already present, {summary.no_domain} with no domain"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
