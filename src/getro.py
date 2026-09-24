"""Getro / VC portfolio board discovery (SPEC.md §7.2, BUILD.md M6).

Company source only, not a posting source -- `SPEC-REVISION-01` §R0/§R5 removed
Getro's original second role (polling boards directly as an independent postings
path). This module does exactly one thing: parse `__NEXT_DATA__` out of a Getro
board's HTML, extract the distinct companies it names, and feed them into the
same company-ingest path M1's watchlist uses (`Database.ingest_manual_company`),
tagged `source='getro'` rather than `'manual'` so `company_sources` keeps an
honest record of which source actually found each company.

Shape is community-derived, not documented, and confirmed to drift between
boards (SPEC.md §7.2) -- verify each real board individually rather than
assuming one shape fits all; `config/getro_boards.yml`'s header records which
boards were actually confirmed live and when.

No domain resolution is attempted here. Getro does not expose a company's own
domain -- only a slug, plus each job's *external application* URL, whose host is
usually a third-party ATS subdomain (`renewco2.breezy.hr`, `jobs.lever.co`), not
the company's own site. That resolution hop is a known, explicitly unsolved gap
(SPEC.md §7.2) -- companies land with `canonical_domain=None`, the same no-domain
case M1's watchlist already handles (C-1.8).

Usage:
    python -m src.getro [--boards config/getro_boards.yml]
"""

import argparse
import json
import logging
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any

import yaml

from src.db import Database, DatabaseUnavailable
from src.http import FetchClient

log = logging.getLogger(__name__)

DEFAULT_BOARDS_PATH = pathlib.Path("config/getro_boards.yml")

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


@dataclass(frozen=True, slots=True)
class GetroBoard:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class GetroCompany:
    name: str
    slug: str


class GetroParseError(ValueError):
    """A board's HTML didn't yield the expected __NEXT_DATA__ shape."""


def load_boards(path: pathlib.Path = DEFAULT_BOARDS_PATH) -> list[GetroBoard]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    boards = []
    for item in raw:
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        if not name or not url:
            raise ValueError(f"getro board entry missing name/url: {item!r}")
        boards.append(GetroBoard(name=name, url=url))
    return boards


def parse_next_data(html: str) -> dict[str, Any]:
    """Extract and decode the `__NEXT_DATA__` JSON payload from a board's HTML.

    Raises GetroParseError rather than a bare exception type, so callers can
    tell "this board's shape drifted" (SPEC.md §7.2) apart from any other bug.
    """
    match = _NEXT_DATA_RE.search(html)
    if match is None:
        raise GetroParseError(
            "no __NEXT_DATA__ script tag found -- this board may use a different "
            "Next.js rendering mode (e.g. App Router streaming); shape needs "
            "re-verifying per-board, per SPEC.md §7.2"
        )
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise GetroParseError(f"__NEXT_DATA__ present but not valid JSON: {exc}") from exc


def extract_companies(data: dict[str, Any]) -> list[GetroCompany]:
    """Distinct companies named in a parsed `__NEXT_DATA__` payload.

    Only name + slug are trusted (see module docstring on the domain gap).
    A job whose organization is missing an id, name, or slug is skipped rather
    than raising -- a board with one malformed entry among twenty real ones is
    a partial result worth keeping, not a reason to discard the whole board.
    """
    try:
        jobs = data["props"]["pageProps"]["initialState"]["jobs"]["found"]
    except (KeyError, TypeError) as exc:
        raise GetroParseError(f"__NEXT_DATA__ present but shape mismatch: {exc}") from exc
    if not isinstance(jobs, list):
        raise GetroParseError("__NEXT_DATA__ jobs.found is not a list")

    seen_ids: set[str] = set()
    companies = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        org = job.get("organization")
        if not isinstance(org, dict):
            continue
        org_id, name, slug = org.get("id"), org.get("name"), org.get("slug")
        if not org_id or not name or not slug or org_id in seen_ids:
            continue
        seen_ids.add(org_id)
        companies.append(GetroCompany(name=name, slug=slug))
    return companies


def fetch_board_companies(client: FetchClient, board: GetroBoard) -> list[GetroCompany]:
    result = client.get(board.url)
    if not result.ok:
        raise GetroParseError(
            f"fetch failed: {result.error if result.error else f'HTTP {result.status}'}"
        )
    return extract_companies(parse_next_data(result.text))


@dataclass(frozen=True, slots=True)
class DiscoverySummary:
    boards_parsed: int = 0
    boards_failed: int = 0
    companies_created: int = 0
    companies_already_present: int = 0


def discover_boards(
    db: Database, client: FetchClient, boards: list[GetroBoard]
) -> DiscoverySummary:
    """Parse each board and ingest the companies it names. One bad board never
    stops the rest (BUILD.md non-negotiable: no exception escapes the loop)."""
    boards_parsed = boards_failed = created = already_present = 0
    for board in boards:
        try:
            companies = fetch_board_companies(client, board)
        except GetroParseError as exc:
            log.warning("getro board %r failed to parse: %s", board.name, exc)
            boards_failed += 1
            continue
        boards_parsed += 1
        for company in companies:
            _company_id, was_created = db.ingest_manual_company(
                name=company.name,
                canonical_domain=None,
                source_id=company.slug,
                source="getro",
            )
            if was_created:
                created += 1
            else:
                already_present += 1
    return DiscoverySummary(
        boards_parsed=boards_parsed,
        boards_failed=boards_failed,
        companies_created=created,
        companies_already_present=already_present,
    )


def dry_run_boards(client: FetchClient, boards: list[GetroBoard]) -> DiscoverySummary:
    """Crawl and parse every board, report counts, touch no database at all --
    discover.yml's `dry_run` input (default true on a manual dispatch)."""
    boards_parsed = boards_failed = companies_found = 0
    for board in boards:
        try:
            companies = fetch_board_companies(client, board)
        except GetroParseError as exc:
            log.warning("getro board %r failed to parse: %s", board.name, exc)
            boards_failed += 1
            continue
        boards_parsed += 1
        companies_found += len(companies)
    return DiscoverySummary(
        boards_parsed=boards_parsed, boards_failed=boards_failed, companies_created=companies_found
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boards", default=str(DEFAULT_BOARDS_PATH))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="crawl and report without writing to the database (no SUPABASE_DB_URL needed)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    boards = load_boards(pathlib.Path(args.boards))

    if args.dry_run:
        client = FetchClient()
        try:
            summary = dry_run_boards(client, boards)
        finally:
            client.close()
        print(
            f"getro (dry run): {summary.boards_parsed}/{len(boards)} boards parsed "
            f"({summary.boards_failed} failed) -> {summary.companies_created} companies found, "
            f"nothing written"
        )
        return 0

    try:
        db = Database.from_env()
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1

    client = FetchClient()
    try:
        with db:
            summary = discover_boards(db, client, boards)
    except DatabaseUnavailable as exc:
        print(f"BLOCKED: {exc}")
        return 1
    finally:
        client.close()

    print(
        f"getro: {summary.boards_parsed}/{len(boards)} boards parsed "
        f"({summary.boards_failed} failed) -> {summary.companies_created} companies "
        f"created, {summary.companies_already_present} already present"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
