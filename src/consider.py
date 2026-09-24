"""Consider board-platform discovery (SPEC.md §7.6, CRITERIA.md C-6.4).

Company source only, same rule as Getro (`src/getro.py`, M6) and every other
source in SPEC.md §7: Consider is never a posting/monitoring path (§4, §7.6) --
monitoring stays on the employer's own ATS. This module parses a Consider
board's confirmed request flow (`spikes/iteration2_consider_spike.py`,
`spikes/iteration15_consider_spike.py`) and feeds the distinct companies it
names into the same `Database.ingest_manual_company` path Getro uses, tagged
`source='consider'`.

Pulled forward ahead of SPEC.md §18's stated sequencing (Consider was item #4,
gated behind the M7 measurement gate) by explicit user decision on 2026-09-24 --
see DEVLOG and CRITERIA.md C-6.4's note.

Confirmed flow, live against 4 real boards (spikes/iteration15_consider_notes.md):
1. GET the board's `/jobs` page. It embeds `window.serverInitialData`, a JSON
   blob carrying a session-scoped `csrfToken` and the board's own `id`.
2. POST `/api-boards/search-jobs` with the cookie the GET set (handled for
   free -- `FetchClient` wraps one `httpx.Client` per instance, which already
   persists cookies across calls) and the token as `x-csrf-token`. Paginate
   with `meta.sequence`, the cursor the previous response returns.

Unlike Getro, Consider exposes a company's own domain directly
(`companyDomain`) -- no resolution-hop gap here (SPEC.md §7.6, §7.2 contrast).

Known limitation, honestly recorded rather than hidden: `MAX_PAGES` bounds how
far a single board's pagination goes. spikes/iteration15_consider_notes.md
found board sizes ranging from 456 to 7,318 total jobs -- fully paginating the
largest at `PAGE_SIZE` would be ~150 requests per crawl, untested against
SPEC.md §9's per-host rate budget. A board larger than `MAX_PAGES *
PAGE_SIZE` jobs will not have every company discovered in one run; repeated
runs may still surface more of it if ranking shifts, but that isn't guaranteed.

Usage:
    python -m src.consider [--boards config/consider_boards.yml]
"""

import argparse
import json
import logging
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import yaml

from src.db import Database, DatabaseUnavailable
from src.http import FetchClient

log = logging.getLogger(__name__)

DEFAULT_BOARDS_PATH = pathlib.Path("config/consider_boards.yml")

PAGE_SIZE = 50
MAX_PAGES = 20  # see module docstring's "Known limitation"

_SERVER_INITIAL_DATA_RE = re.compile(r"window\.serverInitialData\s*=\s*(\{.*?\})\s*;", re.S)

# Consider's own derived/inferred output, never the employer's raw posting --
# never store or surface these (SPEC.md §3.6: no classifiers; §4: no scoring
# field). Confirmed still present on every job record sampled live 2026-09-24
# (spikes/iteration15_consider_notes.md). Listed here, same as the spike, so
# nobody copies one into a stored row without noticing what it is.
CONSIDER_DERIVED_FIELDS_TO_IGNORE = frozenset(
    {"scores", "skills", "requiredSkills", "preferredSkills", "considerLevels", "matchingTalent"}
)


@dataclass(frozen=True, slots=True)
class ConsiderBoard:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class ConsiderCompany:
    name: str
    slug: str
    domain: str | None


class ConsiderParseError(ValueError):
    """A board's response didn't yield the expected shape."""


def load_boards(path: pathlib.Path = DEFAULT_BOARDS_PATH) -> list[ConsiderBoard]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    boards = []
    for item in raw:
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        if not name or not url:
            raise ValueError(f"consider board entry missing name/url: {item!r}")
        boards.append(ConsiderBoard(name=name, url=url))
    return boards


def parse_session(html: str) -> tuple[str, str]:
    """Extract (csrf_token, board_id) from a board page's `serverInitialData`."""
    match = _SERVER_INITIAL_DATA_RE.search(html)
    if match is None:
        raise ConsiderParseError(
            "no window.serverInitialData found -- either not actually "
            "Consider-powered, or the shape drifted (SPEC.md §7.6 warns a "
            "fingerprint guess is not a confirmed board)"
        )
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ConsiderParseError(f"serverInitialData present but not valid JSON: {exc}") from exc
    try:
        csrf_token = data["csrfToken"]
        board_id = data["board"]["id"]
    except (KeyError, TypeError) as exc:
        raise ConsiderParseError(f"serverInitialData present but shape mismatch: {exc}") from exc
    if not csrf_token or not board_id:
        raise ConsiderParseError("serverInitialData present but csrfToken or board.id is empty")
    return csrf_token, board_id


def extract_companies(jobs: list[Any]) -> list[ConsiderCompany]:
    """Companies named in one page of job results. A job missing the fields
    this needs is skipped rather than raising -- a partial page is a partial
    result worth keeping, same principle as src/getro.py's extract_companies."""
    companies = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        name, slug = job.get("companyName"), job.get("companySlug")
        if not name or not slug:
            continue
        domain = job.get("companyDomain") or None
        companies.append(ConsiderCompany(name=name, slug=slug, domain=domain))
    return companies


def fetch_board_companies(
    client: FetchClient,
    board: ConsiderBoard,
    *,
    page_size: int = PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> list[ConsiderCompany]:
    """Fetch the session, then paginate via `meta.sequence` collecting every
    distinct company (deduped by slug) up to `max_pages` pages or until the
    board runs out of jobs, whichever comes first."""
    session_result = client.get(board.url)
    if not session_result.ok:
        detail = session_result.error if session_result.error else f"HTTP {session_result.status}"
        raise ConsiderParseError(f"session fetch failed: {detail}")
    csrf_token, board_id = parse_session(session_result.text)

    origin = _origin(board.url)
    seen_slugs: set[str] = set()
    companies: list[ConsiderCompany] = []
    sequence: str | None = None

    for _page in range(max_pages):
        meta: dict[str, Any] = {"size": page_size}
        if sequence:
            meta["sequence"] = sequence
        payload = {
            "meta": meta,
            "board": {"id": board_id, "isParent": True},
            "query": {"promoteFeatured": True},
        }
        result = client.post_json(
            f"{origin}/api-boards/search-jobs",
            payload,
            headers={"x-csrf-token": csrf_token, "Origin": origin, "Referer": board.url},
        )
        if not result.ok:
            detail = result.error if result.error else f"HTTP {result.status}"
            raise ConsiderParseError(f"search-jobs fetch failed: {detail}")
        body = result.json()
        if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
            raise ConsiderParseError("search-jobs response missing a 'jobs' array")

        jobs = body["jobs"]
        if not jobs:
            break
        for company in extract_companies(jobs):
            if company.slug not in seen_slugs:
                seen_slugs.add(company.slug)
                companies.append(company)

        sequence = (body.get("meta") or {}).get("sequence")
        if not sequence:
            break

    return companies


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


@dataclass(frozen=True, slots=True)
class DiscoverySummary:
    boards_parsed: int = 0
    boards_failed: int = 0
    companies_created: int = 0
    companies_already_present: int = 0


def discover_boards(
    db: Database, client: FetchClient, boards: list[ConsiderBoard]
) -> DiscoverySummary:
    """Parse each board and ingest the companies it names. One bad board never
    stops the rest (BUILD.md non-negotiable: no exception escapes the loop)."""
    boards_parsed = boards_failed = created = already_present = 0
    for board in boards:
        try:
            companies = fetch_board_companies(client, board)
        except ConsiderParseError as exc:
            log.warning("consider board %r failed to parse: %s", board.name, exc)
            boards_failed += 1
            continue
        boards_parsed += 1
        for company in companies:
            _company_id, was_created = db.ingest_manual_company(
                name=company.name,
                canonical_domain=company.domain,
                source_id=company.slug,
                source="consider",
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


def dry_run_boards(client: FetchClient, boards: list[ConsiderBoard]) -> DiscoverySummary:
    """Crawl and parse every board, report counts, touch no database at all."""
    boards_parsed = boards_failed = companies_found = 0
    for board in boards:
        try:
            companies = fetch_board_companies(client, board)
        except ConsiderParseError as exc:
            log.warning("consider board %r failed to parse: %s", board.name, exc)
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
            f"consider (dry run): {summary.boards_parsed}/{len(boards)} boards parsed "
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
        f"consider: {summary.boards_parsed}/{len(boards)} boards parsed "
        f"({summary.boards_failed} failed) -> {summary.companies_created} companies "
        f"created, {summary.companies_already_present} already present"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
