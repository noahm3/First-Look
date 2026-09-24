# M2 — ATS Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This project's own convention overrides the usual subagent-driven default: single track, direct commits to `main`, no branches, no PRs (BUILD.md §0.3).** See "Execution approach" at the end of this document — Native (this session implements every task) is the recommended and only conforming approach here.

**Goal:** Build 8 ATS adapters (Greenhouse, Lever, Ashby, Rippling, BambooHR, Workable,
Personio, Breezy HR) that fetch a known company's postings from the provider's public,
unauthenticated API/feed and parse them into `src.models.Posting`, satisfying
`CRITERIA.md` C-2.1–C-2.12.

**Architecture:** One adapter module per provider (`src/ats_<provider>.py`), each
exposing a single `fetch_postings(client, company_id, token) -> AdapterResult` function.
A shared `src/ats_common.py` holds the result envelope and date-parsing helper that
every adapter needs. Every adapter calls `src.http.FetchClient` — nothing imports
`httpx` directly (Non-negotiable, enforced by ruff's banned-api per `src/http.py`'s own
docstring). No adapter raises; every failure mode becomes `AdapterResult(ok=False, ...)`.

**Tech stack:** Python 3.13 stdlib + the project's existing `src/http.py` (httpx
chokepoint) + `src/models.py` dataclasses + pytest. Personio's feed is XML — parsed with
the stdlib `xml.etree.ElementTree`, not a new dependency.

**Spec:** `SPEC.md` §9 (ATS adapters — all 8 provider entries, updated 2026-09-24),
`SPEC.md` §4 (Workable/Personio rejections reopened 2026-09-24; Workday and Recruitee
remain rejected/deferred), `CRITERIA.md` M2 block (C-2.1–C-2.12), `BUILD.md` §4 M2
section.

## Global Constraints

- Python 3.13, stdlib + httpx + pytest only. No new dependency for XML — stdlib
  `xml.etree.ElementTree` covers Personio.
- Every network call goes through `src/http.py`'s `FetchClient`. Nothing else imports
  `httpx`.
- Tests never hit the network — `tests/conftest.py`'s `_no_network` fixture blocks
  sockets in every test not marked `allow_network`. Fixtures live under
  `tests/fixtures/ats/<provider>/`.
- Every per-company operation is wrapped so no exception escapes the loop — at the
  adapter layer this means: `fetch_postings` never raises; every failure returns
  `AdapterResult(ok=False, error=...)`.
- `Posting.location_raw` is stored verbatim, never normalized (SPEC.md §4 rejects
  normalizing it) — a light join of a provider's own city/state sub-fields into one
  string is not the location-classification logic §4 rejects; that stays this way in
  every adapter below.
- Comp handling is intentionally shallow this milestone: `comp_data_quality`
  (structured/parsed/none) and, where available, a human-readable `comp_raw_summary`
  string. Building real `CompTier` rows (parsed numerics, currency, period, annualized
  best/floor) is `SPEC.md` §11 / **M5's job** (BUILD.md §4) — not attempted here, so this
  plan is not guessing at unverified sub-field mappings under M2's own criteria, which
  do not test compensation at all (C-2.1–C-2.12).
- Commit at each criterion, not once at the end (CLAUDE.md session protocol) — each task
  below ends with a commit that closes out the specific `C-2.x` boxes it satisfies.

## Review Focus

- **Malformed/unexpected shape on a 200 response** (HTML error page where JSON/XML was
  expected, JSON missing the expected top-level key) must degrade to
  `AdapterResult(ok=False, error=...)`, never raise and never silently return an empty
  `postings` tuple mislabeled as success. Every provider's test file exercises this.
- **A real company with zero open postings** (e.g. Appcues on Lever, confirmed in the
  M1 watchlist) must return `AdapterResult(ok=True, postings=())` — a company having no
  jobs right now is not a fetch failure. Lever's test file exercises this explicitly.
- **Personio's per-tenant inconsistency**, confirmed live 2026-09-24 in the same session
  that wrote this plan: one real tenant (`strohm.jobs.personio.com`) returns 200 + valid
  XML; another (`be-levels.jobs.personio.com`) 404s; another (`www.personio.com`, a
  marketing host mistakenly recorded as a tenant) 429s; another
  (`deepdrive.jobs.personio.com`) 307-redirects. The Personio adapter's tests cover the
  200+XML case, a 404, and a non-XML 200 body (the shape the earlier spike found on
  `nexwafe`) — three distinguishable outcomes, not one collapsed "Personio failed."
- **BambooHR's list endpoint has no per-job URL or date field at all** (confirmed live
  2026-09-24 against `ph7.bamboohr.com/careers/list` — see Task 6). The adapter
  constructs the URL from the known `{token}.bamboohr.com/careers/{id}` pattern
  (confirmed live, 200) rather than crashing on a missing key, and `posted_at` stays
  `None` rather than being invented from an unrelated field.
- **A 404 or other 4xx must never be retried** (already enforced in `src/http.py`,
  BUILD.md §3: "a 404 is an answer") **and must produce a clean `AdapterResult(ok=False)`
  at the adapter layer**, not an unhandled exception from calling `.json()` on an HTML or
  plain-text error body. Every provider's test file includes a 404 case.

---

## Task 0: Register the five new ATS providers

**Files:**
- Modify: `src/models.py:20-26` (`AtsProvider` enum)
- Test: `tests/test_models.py` (new file)

**Interfaces:**
- Produces: `AtsProvider.RIPPLING`, `AtsProvider.BAMBOOHR`, `AtsProvider.WORKABLE`,
  `AtsProvider.PERSONIO`, `AtsProvider.BREEZY_HR` — string values `"rippling"`,
  `"bamboohr"`, `"workable"`, `"personio"`, `"breezy_hr"`. Every later task's `Company`/
  test fixtures reference these.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
"""Tests for src/models.py's closed value sets.

New providers land here first: a typo in an enum value silently breaks every
adapter and the mapping cascade's `unsupported_ats:{name}` distribution alike,
so the value strings are pinned by name, not just existence.
"""

from src.models import AtsProvider


def test_all_eight_m2_providers_are_registered():
    values = {p.value for p in AtsProvider}
    assert values == {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "rippling",
        "bamboohr",
        "workable",
        "personio",
        "breezy_hr",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `AssertionError` (only 4 values exist yet).

- [ ] **Step 3: Write minimal implementation**

```python
# src/models.py — replace the AtsProvider class
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "models: register the 5 new M2 ATS providers"
```

---

## Task 1: Shared adapter plumbing

**Files:**
- Create: `src/ats_common.py`
- Test: `tests/test_ats_common.py`

**Interfaces:**
- Consumes: `src.models.Posting` (Task 0's file, unchanged shape).
- Produces: `AdapterResult(ok: bool, postings: tuple[Posting, ...] = (), error: str | None
  = None)`; `parse_iso_or_epoch_ms(value: object) -> datetime | None`. Every later task
  imports both from `src.ats_common`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ats_common.py
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
    assert parse_iso_or_epoch_ms(1758585600000) == datetime(
        2025, 9, 22, 22, 40, tzinfo=UTC
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ats_common.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ats_common'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ats_common.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ats_common.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ats_common.py tests/test_ats_common.py
git commit -m "ats: add shared AdapterResult and date-parsing helper"
```

---

## Task 2: Test support helper for faking `FetchClient`

**Files:**
- Create: `tests/ats_fixtures.py`

**Interfaces:**
- Produces: `fake_client(handler, *, resolves_to="93.184.216.34") -> FetchClient` — every
  `tests/test_ats_*.py` file imports this instead of reimplementing
  `tests/test_http.py`'s `client()` helper.

- [ ] **Step 1: Write the helper directly (support code, not itself under test — it is
  exercised indirectly by every adapter test that follows)**

```python
# tests/ats_fixtures.py
"""Shared FetchClient-faking helper for tests/test_ats_*.py.

Copies tests/test_http.py's transport-fake pattern rather than importing from
a test module, so the 8 adapter test files share one helper instead of
duplicating this boilerplate 8 times.
"""

from pathlib import Path

import httpx

from src.http import FetchClient

PUBLIC_IP = "93.184.216.34"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ats"


def read_fixture(provider: str, name: str) -> bytes:
    return (FIXTURES_DIR / provider / name).read_bytes()


def fake_client(handler, *, resolves_to: str = PUBLIC_IP, **kwargs) -> FetchClient:
    """Build a FetchClient wired to a fake transport. `handler(request) ->
    httpx.Response`."""

    def resolver(_host: str) -> list[str]:
        return [resolves_to]

    kwargs.setdefault("rate_per_second", 1000.0)
    return FetchClient(
        resolver=resolver,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )
```

- [ ] **Step 2: Commit**

```bash
git add tests/ats_fixtures.py
git commit -m "test: add shared FetchClient fake for ats adapter tests"
```

---

## Task 3: Greenhouse adapter

**Files:**
- Create: `src/ats_greenhouse.py`
- Create: `tests/fixtures/ats/greenhouse/normal.json`
- Create: `tests/fixtures/ats/greenhouse/empty.json`
- Create: `tests/fixtures/ats/greenhouse/malformed.json`
- Create: `tests/fixtures/ats/greenhouse/not_found.json`
- Test: `tests/test_ats_greenhouse.py`

**Interfaces:**
- Consumes: `src.ats_common.AdapterResult`, `parse_iso_or_epoch_ms`; `src.http.FetchClient`;
  `src.models.Posting`, `CompDataQuality`.
- Produces: `fetch_postings(client: FetchClient, company_id: int, token: str) ->
  AdapterResult`.

- [ ] **Step 1: Fetch the live docs and a real fixture during implementation**

Read [docs.greenhouse.io/job-board.html](https://docs.greenhouse.io/job-board.html)
(C-2.7). Then record fixtures from a real board:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/robinhood/jobs?content=true" \
  -o tests/fixtures/ats/greenhouse/normal.json
```

For the empty-board fixture, use a real board known to have zero postings right now
(check the current watchlist / re-verify live before committing — boards open and close
roostings over time, so confirm this one is still empty at implementation time rather
than trusting this plan's word for it) or, if none is confirmed empty live, use the real
shape with `"jobs": []` constructed from the schema above — write:

```json
{"jobs": [], "meta": {"total": 0}}
```
to `tests/fixtures/ats/greenhouse/empty.json`.

Malformed fixture — deliberately truncated JSON, not fetched (there is no live source
for "malformed"; this is a constructed edge case):

```json
{"jobs": [{"id": 1, "title": "Truncated
```
to `tests/fixtures/ats/greenhouse/malformed.json`.

404 fixture — Greenhouse's real invalid-token response, confirmed shape:

```json
{"error":"Board is not associated with any live jobs. Please check your credentials."}
```
to `tests/fixtures/ats/greenhouse/not_found.json`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_greenhouse.py
"""Tests for src/ats_greenhouse.py.

Fixtures recorded live 2026-09 against boards-api.greenhouse.io (SPEC.md §9,
C-2.7) — see tests/fixtures/ats/greenhouse/. No test here opens a socket
(tests/conftest.py blocks it); every response is replayed from a fixture file.
"""

import httpx
import pytest

from src.ats_common import AdapterResult
from src.ats_greenhouse import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("greenhouse", "normal.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "boards-api.greenhouse.io" in str(request.url)
        assert "content=true" in str(request.url)
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url
        assert posting.company_id == 1


def test_department_raw_populated_from_departments_field():
    body = read_fixture("greenhouse", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert any(p.department_raw for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("greenhouse", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("greenhouse", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken-board")

    assert result.ok is False
    assert result.error


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("greenhouse", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-token")

    assert result.ok is False
    assert len(attempts) == 1  # BUILD.md §3: a 404 is an answer, never retried


def test_no_comp_data_observed_on_this_board_is_none_quality():
    # Confirmed live 2026-09-22 against 384 postings on 8 mapped boards:
    # pay_input_ranges appears on none of them (SPEC.md §9).
    body = read_fixture("greenhouse", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="robinhood")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_greenhouse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ats_greenhouse'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_greenhouse.py
"""Greenhouse adapter. SPEC.md §9:
docs.greenhouse.io/job-board.html

content=true is mandatory, not optional — `departments` is absent without it
(confirmed live 2026-09-22 against 8 mapped boards). The per-job detail
endpoint is never called: it returned a byte-identical object to the
content=true list entry on 6/6 jobs across two boards, so it buys nothing
(SPEC.md §9). `pay_input_ranges` appeared on none of 384 live postings
measured — comp is classified NONE unconditionally here; if a future board
ever populates it, that is a real finding worth a fresh look, not something
to guess a mapping for now.
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'jobs' array")

    postings = []
    for job in body["jobs"]:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        departments = [
            d.get("name")
            for d in (job.get("departments") or [])
            if isinstance(d, dict) and d.get("name")
        ]
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("title") or "",
                department_raw=", ".join(departments) or None,
                location_raw=(job.get("location") or {}).get("name"),
                url=job.get("absolute_url"),
                posted_at=parse_iso_or_epoch_ms(job.get("first_published")),
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_greenhouse.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit and check off criteria**

```bash
git add src/ats_greenhouse.py tests/fixtures/ats/greenhouse tests/test_ats_greenhouse.py
git commit -m "ats: add Greenhouse adapter (C-2.1, C-2.2, C-2.5, C-2.7 partial)"
```

Then in `CRITERIA.md`, check C-2.1/C-2.2/C-2.5/C-2.7 only once Lever and Ashby (Tasks 4–5)
also pass, since those criteria name all three providers together.

---

## Task 4: Lever adapter

**Files:**
- Create: `src/ats_lever.py`
- Create: `tests/fixtures/ats/lever/normal.json`
- Create: `tests/fixtures/ats/lever/empty.json`
- Create: `tests/fixtures/ats/lever/malformed.json`
- Create: `tests/fixtures/ats/lever/not_found.json`
- Test: `tests/test_ats_lever.py`

**Interfaces:**
- Same shape as Task 3: `fetch_postings(client, company_id, token) -> AdapterResult`.

- [ ] **Step 1: Fetch the live docs and real fixtures**

Read [hire.lever.co/developer/documentation](https://hire.lever.co/developer/documentation)
— note in a code comment that this documents the authenticated v1 Data API, not the
public v0 endpoint used here (SPEC.md §9 already records this).

```bash
curl -s "https://api.lever.co/v0/postings/ro?mode=json" \
  -o tests/fixtures/ats/lever/normal.json
curl -s "https://api.lever.co/v0/postings/appcues?mode=json" \
  -o tests/fixtures/ats/lever/empty.json   # confirmed 0 open postings, M1 DEVLOG 2026-09-23
```

Verify `empty.json` really is `[]` before committing it — Appcues' board could have new
postings by the time this task runs; if it does, pick another watchlist company or
construct `[]` directly.

Malformed (constructed): `tests/fixtures/ats/lever/malformed.json` containing
`[{"id": "abc", "text": "Truncated`.

404 (Lever returns a plain string body for an unknown site — confirm live and record the
real body): capture via
```bash
curl -s "https://api.lever.co/v0/postings/this-site-does-not-exist-first-look-check?mode=json" \
  -o tests/fixtures/ats/lever/not_found.json
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_lever.py
"""Tests for src/ats_lever.py.

createdAt is Lever's undocumented epoch-ms field (SPEC.md §9) — a missing one
must produce posted_at=None, never an exception (C-2.6). Appcues' real board
(0 open postings as of the 2026-09-23 M1 watchlist entry) is the empty-board
fixture, not a constructed one.
"""

import httpx

from src.ats_lever import fetch_postings
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("lever", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated_from_categories_team():
    body = read_fixture("lever", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert any(p.department_raw for p in result.postings)


def test_appcues_real_empty_board_is_ok_with_zero_postings():
    body = read_fixture("lever", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="appcues")

    assert result.ok
    assert result.postings == ()


def test_missing_created_at_produces_null_not_exception():
    import json

    jobs = json.loads(read_fixture("lever", "normal.json"))
    jobs[0].pop("createdAt", None)
    body = json.dumps(jobs).encode()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ro")

    assert result.ok
    assert result.postings[0].posted_at is None


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("lever", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_unexpected_top_level_shape_is_a_classified_failure():
    # Lever's board is a bare JSON array; an object at the top level is invalid.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"not": "an array"}')

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("lever", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-site")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_lever.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_lever.py
"""Lever adapter. SPEC.md §9:
hire.lever.co/developer/documentation documents the authenticated v1 Data API.
The public v0 Postings API used here is not officially documented.

createdAt is undocumented epoch ms and is not a reliable publication date —
9 of 28 sampled live postings carried a createdAt over a year old (SPEC.md
§9) — but it is still the best available signal, stored as-is via
parse_iso_or_epoch_ms, which returns None rather than raising when the field
is absent (C-2.6). workplaceType is a structured onsite/hybrid/remote field,
populated on 363/363 live postings measured (SPEC.md §9).

Comp: salaryRange, when present, is structured but its sub-field shape has
not been independently re-verified this milestone (open item — see the M2
DEVLOG entry). Classified STRUCTURED with a best-effort rendered summary
rather than parsed into CompTier rows, per this plan's Global Constraints
(CompTier construction is M5's job).
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, list):
        return AdapterResult(ok=False, error="unexpected shape: expected a JSON array")

    postings = []
    for job in body:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        cats = job.get("categories") or {}
        comp_quality, comp_summary = _comp(job)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("text") or "",
                department_raw=cats.get("team") or cats.get("department"),
                location_raw=cats.get("location"),
                workplace_type_raw=job.get("workplaceType"),
                url=job.get("hostedUrl"),
                posted_at=parse_iso_or_epoch_ms(job.get("createdAt")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _comp(job: dict) -> tuple[CompDataQuality, str | None]:
    salary_range = job.get("salaryRange")
    if isinstance(salary_range, dict) and salary_range:
        parts = [
            str(salary_range.get(key))
            for key in ("min", "max", "currency", "interval")
            if salary_range.get(key) is not None
        ]
        return CompDataQuality.STRUCTURED, " ".join(parts) or None
    summary = job.get("salaryDescriptionPlain")
    if summary:
        return CompDataQuality.PARSED, summary
    return CompDataQuality.NONE, None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_lever.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add src/ats_lever.py tests/fixtures/ats/lever tests/test_ats_lever.py
git commit -m "ats: add Lever adapter (C-2.6)"
```

---

## Task 5: Ashby adapter

**Files:**
- Create: `src/ats_ashby.py`
- Create: `tests/fixtures/ats/ashby/normal.json`
- Create: `tests/fixtures/ats/ashby/empty.json`
- Create: `tests/fixtures/ats/ashby/malformed.json`
- Create: `tests/fixtures/ats/ashby/not_found.json`
- Test: `tests/test_ats_ashby.py`

**Interfaces:** Same shape as Task 3.

- [ ] **Step 1: Fetch the live docs and real fixtures**

Read
[developers.ashbyhq.com/docs/public-job-posting-api](https://developers.ashbyhq.com/docs/public-job-posting-api).

```bash
curl -s "https://api.ashbyhq.com/posting-api/job-board/ramp?includeCompensation=true" \
  -o tests/fixtures/ats/ashby/normal.json
```

For empty/malformed/404, same approach as Tasks 3–4: an empty board confirmed live at
implementation time (or construct `{"jobs": [], "apiVersion": "1"}`), a hand-truncated
malformed fixture, and a real 404 body captured against an unknown board name.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_ashby.py
"""Tests for src/ats_ashby.py.

workplaceType is Ashby's structured field (OnSite/Hybrid/Remote, capitalised —
SPEC.md §9 corrected 2026-09-22: Lever exposes one too, not just Ashby).
compensation is a truthy object even when nothing is disclosed
(compensationTiers: [], summary null) — disclosure must be judged on the
tiers/summary, never on the object's own truthiness.
"""

import httpx

from src.ats_ashby import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("ashby", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated():
    body = read_fixture("ashby", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert any(p.department_raw for p in result.postings)


def test_workplace_type_raw_captured_where_present():
    body = read_fixture("ashby", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert any(p.workplace_type_raw for p in result.postings)


def test_truthy_but_empty_compensation_object_is_none_quality():
    import json

    jobs = json.loads(read_fixture("ashby", "normal.json"))
    for job in jobs.get("jobs", []):
        job["compensation"] = {"compensationTiers": [], "compensationTierSummary": None}
    body = json.dumps(jobs).encode()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ramp")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("ashby", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("ashby", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("ashby", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-board")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_ashby.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_ashby.py
"""Ashby adapter. SPEC.md §9:
developers.ashbyhq.com/docs/public-job-posting-api

publishedAt is a direct field. workplaceType is structured (capitalised:
OnSite/Hybrid/Remote) and populated on the large majority of live postings
measured (SPEC.md §9). The compensation object is truthy even when nothing
is disclosed (compensationTiers: [], summary null) — disclosure is judged on
the tiers/summary, never on the object itself; shouldDisplayCompensationOnJobPostings
is the provider's own flag and tracks this exactly, but is not stored here
(M5's normalization territory).
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'jobs' array")

    postings = []
    for job in body["jobs"]:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        comp_quality, comp_summary = _comp(job)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("title") or "",
                department_raw=job.get("department") or job.get("team"),
                location_raw=job.get("location"),
                workplace_type_raw=job.get("workplaceType"),
                url=job.get("jobUrl"),
                posted_at=parse_iso_or_epoch_ms(job.get("publishedAt")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _comp(job: dict) -> tuple[CompDataQuality, str | None]:
    comp = job.get("compensation") or {}
    tiers = comp.get("compensationTiers")
    summary = comp.get("compensationTierSummary")
    if tiers:
        return CompDataQuality.STRUCTURED, summary or str(tiers)
    if summary:
        return CompDataQuality.PARSED, summary
    return CompDataQuality.NONE, None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_ashby.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit and check off C-2.1/C-2.2/C-2.3/C-2.5/C-2.7**

```bash
git add src/ats_ashby.py tests/fixtures/ats/ashby tests/test_ats_ashby.py
git commit -m "ats: add Ashby adapter (C-2.1, C-2.2, C-2.3, C-2.5, C-2.7)"
```

At this point Greenhouse, Lever, and Ashby are all done — check C-2.1, C-2.2, C-2.3,
C-2.5, C-2.6, C-2.7 in `CRITERIA.md` (each only after re-running that provider's real
test output and looking at it, per CLAUDE.md: "Check a box only when I have seen the
actual output, not a summary").

---

## Task 6: BambooHR adapter

**Files:**
- Create: `src/ats_bamboohr.py`
- Create: `tests/fixtures/ats/bamboohr/normal.json`
- Create: `tests/fixtures/ats/bamboohr/empty.json`
- Create: `tests/fixtures/ats/bamboohr/malformed.json`
- Create: `tests/fixtures/ats/bamboohr/not_found.json`
- Test: `tests/test_ats_bamboohr.py`

**Interfaces:** Same shape as Task 3.

- [ ] **Step 1: Record the real fixture (no authoritative docs exist — SPEC.md §9)**

Confirmed live 2026-09-24 against a real board (`ph7.bamboohr.com`, "PH7
Technologies"):

```bash
curl -s "https://ph7.bamboohr.com/careers/list" \
  -o tests/fixtures/ats/bamboohr/normal.json
```

This is the real captured shape as of 2026-09-24 (re-verify at implementation time —
BambooHR is explicitly documented in SPEC.md §9 as changing without notice):

```json
{"meta":{"totalCount":4},"result":[{"id":"41","jobOpeningName":"Process Operator","departmentId":"18673","departmentLabel":"PGM-Ops","employmentStatusLabel":"Full-Time","employmentType":null,"location":{"city":"Burnaby","state":"British Columbia"},"atsLocation":{"country":null,"state":null,"province":null,"city":null},"isRemote":null,"locationType":"0"}]}
```

**No `url` field and no date field exist anywhere in this response** — confirmed by
reading the full body, not just a truncated sample. The real posting URL was confirmed
live by requesting it directly: `https://ph7.bamboohr.com/careers/41` → `200`. The
adapter constructs this URL from `token` + `id`; it does not come from the response.

Empty/malformed/404 fixtures: same approach as prior tasks — a real zero-postings
board if one can be confirmed live, else `{"meta":{"totalCount":0},"result":[]}`; a
hand-truncated malformed fixture; a real captured 404 body against an invalid subdomain.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_bamboohr.py
"""Tests for src/ats_bamboohr.py.

BambooHR has no authoritative documentation (SPEC.md §9, same bucket as Lever
v0/Getro) and its list endpoint exposes neither a per-job URL nor a date
field (confirmed live 2026-09-24 against ph7.bamboohr.com/careers/list, full
body inspected). The URL is constructed from the known
{token}.bamboohr.com/careers/{id} pattern, confirmed live (200); posted_at
stays None rather than being invented.
"""

import httpx

from src.ats_bamboohr import fetch_postings
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_constructed_urls():
    body = read_fixture("bamboohr", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ph7")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url == f"https://ph7.bamboohr.com/careers/{posting.ats_job_id}"


def test_posted_at_stays_none_no_date_field_exists():
    body = read_fixture("bamboohr", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ph7")

    assert all(p.posted_at is None for p in result.postings)


def test_department_raw_populated_from_department_label():
    body = read_fixture("bamboohr", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="ph7")

    assert any(p.department_raw for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("bamboohr", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("bamboohr", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("bamboohr", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-company")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_bamboohr.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_bamboohr.py
"""BambooHR adapter. SPEC.md §9: no authoritative documentation of any kind
(same bucket as Lever v0/Getro) — this is an internal endpoint powering
BambooHR's own careers-page widget, shape reported to change between
BambooHR releases without notice.

Confirmed live 2026-09-24: the list endpoint has no per-job URL and no date
field at all. The URL is constructed from the known
{token}.bamboohr.com/careers/{id} pattern (confirmed live, 200). posted_at
is always None — there is no field to read it from, and no comp field was
observed either, so comp_data_quality is always NONE.
"""

from src.ats_common import AdapterResult
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://{token}.bamboohr.com/careers/list"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("result"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'result' array")

    postings = []
    for job in body["result"]:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        job_id = str(job["id"])
        location = job.get("location") or {}
        location_parts = [location.get("city"), location.get("state")]
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=job.get("jobOpeningName") or "",
                department_raw=job.get("departmentLabel"),
                location_raw=", ".join(p for p in location_parts if p) or None,
                workplace_type_raw="remote" if job.get("isRemote") is True else None,
                url=f"https://{token}.bamboohr.com/careers/{job_id}",
                posted_at=None,
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_bamboohr.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add src/ats_bamboohr.py tests/fixtures/ats/bamboohr tests/test_ats_bamboohr.py
git commit -m "ats: add BambooHR adapter (C-2.8, C-2.9, C-2.10 partial)"
```

---

## Task 7: Workable adapter

**Files:**
- Create: `src/ats_workable.py`
- Create: `tests/fixtures/ats/workable/normal.json`
- Create: `tests/fixtures/ats/workable/empty.json`
- Create: `tests/fixtures/ats/workable/malformed.json`
- Create: `tests/fixtures/ats/workable/not_found.json`
- Test: `tests/test_ats_workable.py`

**Interfaces:** Same shape as Task 3.

- [ ] **Step 1: Fetch the real fixture, confirm which API is public**

The documented API at
[developer.workable.com](https://developer.workable.com) (`spi/v3/jobs`, bearer token,
`r_jobs` scope, 10 req/10s) is Workable's authenticated admin surface — **not** what
this adapter calls. The public, unauthenticated board endpoint, confirmed live
2026-09-24:

```bash
curl -s "https://apply.workable.com/api/v1/widget/accounts/aerones" \
  -o tests/fixtures/ats/workable/normal.json
```

Real confirmed job fields (from the live body): `title`, `shortcode`, `code`,
`employment_type`, `telecommuting`, `department`, `url`, `shortlink`,
`application_url`, `published_on`, `created_at`, `country`, `city`, `state`,
`locations[]`. **No compensation field of any kind was present** — the documented
admin API's `salary` object does not appear on this public endpoint.

Empty/malformed/404: same pattern as prior tasks (confirm a real zero-postings account
live, or construct `{"name": "Empty Co", "jobs": []}`; hand-truncated malformed;
real captured 404 — confirmed live 2026-09-24 that a bad account slug returns a plain
`Not Found` body).

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_workable.py
"""Tests for src/ats_workable.py.

The endpoint here (apply.workable.com/api/v1/widget/accounts/{company}) is
public and unauthenticated — a separate surface from Workable's documented,
authenticated admin API (spi/v3/jobs). Confirmed live 2026-09-24: no
compensation field exists on this endpoint, so comp_data_quality is always
NONE here, unlike the admin API's documented salary object.
"""

import httpx

from src.ats_workable import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_account_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_department_raw_populated():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    assert any(p.department_raw for p in result.postings)


def test_no_compensation_field_on_this_endpoint_is_none_quality():
    body = read_fixture("workable", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="aerones")

    assert all(p.comp_data_quality == CompDataQuality.NONE for p in result.postings)


def test_empty_account_is_ok_with_zero_postings():
    body = read_fixture("workable", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="empty-co")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("workable", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("workable", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-account")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_workable.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_workable.py
"""Workable adapter. SPEC.md §9: developer.workable.com documents the
authenticated admin API (spi/v3/jobs, bearer token, r_jobs scope,
10 req/10sec limit) — not the endpoint used here.

apply.workable.com/api/v1/widget/accounts/{company} is a separate,
undocumented, public, unauthenticated board endpoint that powers customers'
own careers pages, confirmed live 2026-09-24. No compensation field exists
on this endpoint (the documented admin API's salary object does not appear
here) — comp_data_quality is always NONE.
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'jobs' array")

    postings = []
    for job in body["jobs"]:
        if not isinstance(job, dict) or not job.get("shortcode"):
            continue
        location_parts = [job.get("city"), job.get("state"), job.get("country")]
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job["shortcode"],
                title_raw=job.get("title") or "",
                department_raw=job.get("department"),
                location_raw=", ".join(p for p in location_parts if p) or None,
                workplace_type_raw="remote" if job.get("telecommuting") is True else None,
                url=job.get("url") or job.get("application_url"),
                posted_at=parse_iso_or_epoch_ms(job.get("published_on")),
                comp_data_quality=CompDataQuality.NONE,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_workable.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add src/ats_workable.py tests/fixtures/ats/workable tests/test_ats_workable.py
git commit -m "ats: add Workable adapter (SPEC.md §4 rejection reopened)"
```

---

## Task 8: Personio adapter

**Files:**
- Create: `src/ats_personio.py`
- Create: `tests/fixtures/ats/personio/normal.xml`
- Create: `tests/fixtures/ats/personio/empty.xml`
- Create: `tests/fixtures/ats/personio/malformed.xml`
- Create: `tests/fixtures/ats/personio/not_xml.html`
- Create: `tests/fixtures/ats/personio/not_found.txt`
- Test: `tests/test_ats_personio.py`

**Interfaces:**
- Produces: `fetch_postings(client: FetchClient, company_id: int, host: str) ->
  AdapterResult`. **Deliberately `host`, not `token`, unlike every other adapter** — the
  TLD varies per tenant (`.de` vs `.com`, confirmed live 2026-09-24), so the caller
  passes the full working hostname once the mapping cascade (M3) has resolved which one
  works, rather than this adapter guessing a TLD.

- [ ] **Step 1: Fetch the real fixtures — confirm the XML-only framing directly (C-2.12)**

Live-checked 2026-09-24, in this same session, against real tenants found in
`spikes/ats_platform_detections.csv`:

```bash
curl -s "https://strohm.jobs.personio.com/xml?language=en" \
  -o tests/fixtures/ats/personio/normal.xml       # 200, real XML, confirmed
curl -s "https://be-levels.jobs.personio.com/xml?language=en" \
  -o tests/fixtures/ats/personio/not_found.txt    # 404, confirmed
```

The root element is `<workzag-jobs>` — Personio's product was formerly "Workzag"; the
XML schema kept the old name. **Personio does carry structured compensation** on the
per-position `<salaryInformation>` block (`<min>`, `<max>`, `<currencySymbol>`,
`<currencyCode>`, `<type>`) — confirmed live on `strohm.jobs.personio.com`, contradicting
nothing in SPEC.md (comp richness was never part of the XML-only rejection reasoning)
but worth flagging in the M2 DEVLOG entry as a real finding.

For the "non-XML 200" case that the earlier spike found on `nexwafe`'s tenant — construct
`not_xml.html` as a minimal HTML shell (a live re-check of that exact host is not
guaranteed to reproduce the same failure by implementation time, so this fixture is
reconstructed from the spike's own description rather than re-fetched):

```html
<!DOCTYPE html><html><head><title>Loading...</title></head><body><div id="root"></div></body></html>
```

`empty.xml`: `<?xml version="1.0" encoding="UTF-8"?><workzag-jobs></workzag-jobs>`
(confirm against a real tenant with zero open positions if one turns up live, otherwise
this constructed shape is the documented empty case).

`malformed.xml`: hand-truncated —
`<?xml version="1.0"?><workzag-jobs><position><id>1</id><name>Truncated`

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_personio.py
"""Tests for src/ats_personio.py.

Personio's public XML feed is confirmed real and officially documented as a
feature (support.personio.de), unlike the other 4 new providers — but
confirmed live 2026-09-24 to be inconsistent across tenants: some 200+XML,
some 404, some redirect, some rate-limit. This adapter must turn each of
those into a distinguishable, correctly-classified AdapterResult, never a
crash from feeding non-XML content to the XML parser.
"""

import httpx

from src.ats_personio import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_tenant_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("personio", "normal.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="strohm.jobs.personio.com")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url.startswith("https://strohm.jobs.personio.com/job/")


def test_structured_salary_information_is_structured_quality():
    body = read_fixture("personio", "normal.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="strohm.jobs.personio.com")

    assert any(p.comp_data_quality == CompDataQuality.STRUCTURED for p in result.postings)


def test_department_raw_populated():
    body = read_fixture("personio", "normal.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="strohm.jobs.personio.com")

    assert any(p.department_raw for p in result.postings)


def test_empty_tenant_is_ok_with_zero_postings():
    body = read_fixture("personio", "empty.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="empty.jobs.personio.com")

    assert result.ok
    assert result.postings == ()


def test_malformed_xml_is_a_classified_failure_not_a_crash():
    body = read_fixture("personio", "malformed.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="broken.jobs.personio.com")

    assert result.ok is False


def test_client_rendered_html_instead_of_xml_is_a_classified_failure():
    # The real shape the earlier spike found on nexwafe's tenant.
    body = read_fixture("personio", "not_xml.html")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="nexwafe.jobs.personio.com")

    assert result.ok is False
    assert result.error


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("personio", "not_found.txt")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, host="be-levels.jobs.personio.com")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_personio.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_personio.py
"""Personio adapter. SPEC.md §9:
support.personio.de "Overview of the Personio Recruiting API" documents this
public XML feed as an officially sanctioned feature — unlike every other new
M2 provider, this is not a reverse-engineered endpoint.

Confirmed live 2026-09-24 to be genuinely inconsistent across tenants: some
200+XML, some 404, some redirect, some rate-limit. The TLD varies per tenant
(.com and .de both seen live) — this adapter takes the full working `host`,
not a bare token, so the caller (M3's mapping cascade) is the one that
resolved which TLD works.

The XML root element is <workzag-jobs> (Personio's product was formerly
"Workzag"). Per-position <salaryInformation> (min/max/currencyCode/type) is
real structured comp, confirmed live — richer than any of the other 4 new
providers. Uses the stdlib xml.etree.ElementTree; a malformed or non-XML body
is caught by ParseError and returned as a classified failure, never raised.
"""

import xml.etree.ElementTree as ET

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, host: str) -> AdapterResult:
    url = f"https://{host}/xml?language=en"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    try:
        root = ET.fromstring(result.body)
    except ET.ParseError as exc:
        return AdapterResult(ok=False, error=f"not valid XML: {exc}")

    if root.tag != "workzag-jobs":
        return AdapterResult(
            ok=False, error=f"unexpected root element {root.tag!r}, expected workzag-jobs"
        )

    postings = []
    for position in root.findall("position"):
        job_id = _text(position, "id")
        title = _text(position, "name")
        if not job_id or not title:
            continue
        office_parts = [_text(position, "office")]
        comp_quality, comp_summary = _comp(position)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=title,
                department_raw=_text(position, "department"),
                location_raw=", ".join(p for p in office_parts if p) or None,
                url=f"https://{host}/job/{job_id}",
                posted_at=parse_iso_or_epoch_ms(_text(position, "createdAt")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _text(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _comp(position: ET.Element) -> tuple[CompDataQuality, str | None]:
    salary = position.find("salaryInformation")
    if salary is None:
        return CompDataQuality.NONE, None
    parts = [
        _text(salary, key)
        for key in ("min", "max", "currencyCode", "type")
        if _text(salary, key)
    ]
    if parts:
        return CompDataQuality.STRUCTURED, " ".join(parts)
    return CompDataQuality.NONE, None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_personio.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit and check off C-2.12**

```bash
git add src/ats_personio.py tests/fixtures/ats/personio tests/test_ats_personio.py
git commit -m "ats: add Personio adapter, re-verify XML shape live (C-2.12)"
```

---

## Task 9: Breezy HR adapter

**Files:**
- Create: `src/ats_breezy.py`
- Create: `tests/fixtures/ats/breezy/normal.json`
- Create: `tests/fixtures/ats/breezy/empty.json`
- Create: `tests/fixtures/ats/breezy/malformed.json`
- Create: `tests/fixtures/ats/breezy/not_found.json`
- Test: `tests/test_ats_breezy.py`

**Interfaces:** Same shape as Task 3.

- [ ] **Step 1: Fetch the real fixture**

The documented API at [developer.breezy.hr](https://developer.breezy.hr)
(`api.breezy.hr/v3`, `GET v3/company/{company_id}/positions`, auth token required) is
Breezy's admin surface — **not** what this adapter calls. Confirmed live 2026-09-24:

```bash
curl -s "https://elysium-health.breezy.hr/json" \
  -o tests/fixtures/ats/breezy/normal.json
```

Real confirmed shape: `id`, `friendly_id`, `name`, `url`, `published_date`,
`type.name`, `location.name` / `location.is_remote`, `department` (was `null` in the
live sample — confirm a populated example if one turns up), `salary` (a free-text
string, e.g. `"$110,000 – $140,000 / year"` — **not structured**, contrary to an
earlier assumption in `spikes/ats_integration_backlog.md`; correct that note during
this task), `company.name`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_breezy.py
"""Tests for src/ats_breezy.py.

The endpoint here ({company}.breezy.hr/json) is public and unauthenticated —
a separate surface from Breezy's documented, authenticated admin API
(api.breezy.hr/v3). salary is a free-text string (confirmed live 2026-09-24,
e.g. "$110,000 - $140,000 / year"), not a structured object — classified
PARSED, not STRUCTURED.
"""

import httpx

from src.ats_breezy import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    body = read_fixture("breezy", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    assert result.ok
    assert len(result.postings) > 0
    for posting in result.postings:
        assert posting.title_raw
        assert posting.url


def test_free_text_salary_string_is_parsed_not_structured():
    body = read_fixture("breezy", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    salaried = [p for p in result.postings if p.comp_raw_summary]
    assert salaried
    assert all(p.comp_data_quality == CompDataQuality.PARSED for p in salaried)


def test_is_remote_flag_maps_to_workplace_type_raw():
    body = read_fixture("breezy", "normal.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="elysium-health")

    # The live sample has is_remote: false, so this must not be mislabeled remote.
    assert all(p.workplace_type_raw != "remote" for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("breezy", "empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="empty-co")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("breezy", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("breezy", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-company")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_breezy.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_breezy.py
"""Breezy HR adapter. SPEC.md §9: developer.breezy.hr documents the
authenticated admin API (api.breezy.hr/v3, GET v3/company/{company_id}/
positions, requires an auth token) — not the endpoint used here.

{company}.breezy.hr/json is a separate, undocumented, public, unauthenticated
board endpoint, confirmed live 2026-09-24. salary is a free-text string
(e.g. "$110,000 - $140,000 / year"), not structured — classified PARSED.
location.is_remote is a boolean, not a 3-way onsite/hybrid/remote enum like
Lever/Ashby; only the True case is mapped, so an unremarked absence is never
guessed as "remote" (mirrors SPEC.md §12.3's "UNKNOWN stays visible" caution).
"""

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    url = f"https://{token}.breezy.hr/json"
    result = client.get(url)
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, list):
        return AdapterResult(ok=False, error="unexpected shape: expected a JSON array")

    postings = []
    for job in body:
        if not isinstance(job, dict) or not job.get("id"):
            continue
        location = job.get("location") or {}
        comp_quality, comp_summary = _comp(job)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=str(job["id"]),
                title_raw=job.get("name") or "",
                department_raw=job.get("department"),
                location_raw=location.get("name"),
                workplace_type_raw="remote" if location.get("is_remote") is True else None,
                url=job.get("url"),
                posted_at=parse_iso_or_epoch_ms(job.get("published_date")),
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _comp(job: dict) -> tuple[CompDataQuality, str | None]:
    salary = job.get("salary")
    if isinstance(salary, str) and salary.strip():
        return CompDataQuality.PARSED, salary.strip()
    return CompDataQuality.NONE, None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_breezy.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add src/ats_breezy.py tests/fixtures/ats/breezy tests/test_ats_breezy.py
git commit -m "ats: add Breezy HR adapter"
```

---

## Task 10: Rippling adapter

**Files:**
- Create: `src/ats_rippling.py`
- Create: `tests/fixtures/ats/rippling/list_normal.json`
- Create: `tests/fixtures/ats/rippling/detail_normal.json`
- Create: `tests/fixtures/ats/rippling/list_empty.json`
- Create: `tests/fixtures/ats/rippling/malformed.json`
- Create: `tests/fixtures/ats/rippling/not_found.json`
- Test: `tests/test_ats_rippling.py`

**Interfaces:** Same shape as Task 3 — token resolution (deciding which board a company
uses) is `spikes/iteration11_rippling_spike.py`'s job and belongs to M3's mapping
cascade, not this adapter. This adapter takes an already-known token, matching how
C-2.1/C-2.8 describe every other adapter ("known tokens").

- [ ] **Step 1: Fetch the live docs, note the version split, record real fixtures**

`developer.rippling.com/documentation/job-board-api` documents `v1`, which requires a
paid Recruiting Pro subscription and an API key. The `v2` endpoint below is
undocumented, public, and unauthenticated — confirmed live in `spikes/
iteration11_rippling_spike.py` (61/62 companies, 716 postings).

```bash
curl -s "https://api.rippling.com/platform/api/ats/v2/board/formant-careers/jobs" \
  -o tests/fixtures/ats/rippling/list_normal.json
```

Then, using one real job id from that list response, record a detail fixture (the
detail call is **not** redundant here, unlike Greenhouse — `createdOn` and
`payRangeDetails` exist only on this endpoint):

```bash
curl -s "https://api.rippling.com/platform/api/ats/v2/board/formant-careers/jobs/<real-id-from-list>" \
  -o tests/fixtures/ats/rippling/detail_normal.json
```

Empty/malformed/404: same pattern as prior tasks.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ats_rippling.py
"""Tests for src/ats_rippling.py.

Unlike Greenhouse, the per-job detail call here is NOT redundant: createdOn
(a real posted date) and payRangeDetails (structured comp) exist only on the
detail endpoint (SPEC.md §9, confirmed in spikes/iteration11_rippling_spike.py).
Token resolution (finding which token a company's careers page uses) is M3's
job, not this adapter's — this adapter takes an already-known token.
"""

import json

import httpx

from src.ats_rippling import fetch_postings
from src.models import CompDataQuality
from tests.ats_fixtures import fake_client, read_fixture


def _handler(list_body: bytes, detail_body: bytes | None, detail_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/jobs/" in url.rsplit("/board/", 1)[-1]:
            if detail_body is None:
                return httpx.Response(404, content=b'{"error": "not found"}')
            return httpx.Response(detail_status, content=detail_body)
        return httpx.Response(200, content=list_body)

    return handler


def test_normal_board_returns_parsed_postings_with_titles_and_urls():
    list_body = read_fixture("rippling", "list_normal.json")
    detail_body = read_fixture("rippling", "detail_normal.json")

    with fake_client(_handler(list_body, detail_body)) as client:
        result = fetch_postings(client, company_id=1, token="formant-careers")

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
        result = fetch_postings(client, company_id=1, token="formant-careers")

    assert any(p.posted_at is not None for p in result.postings)
    assert any(p.comp_data_quality == CompDataQuality.STRUCTURED for p in result.postings)


def test_failed_detail_call_still_returns_the_posting_degraded():
    list_body = read_fixture("rippling", "list_normal.json")

    with fake_client(_handler(list_body, detail_body=None)) as client:
        result = fetch_postings(client, company_id=1, token="formant-careers")

    # Losing the detail call loses posted_at/comp, not the whole company
    # (mirrors Greenhouse's degrade-don't-drop precedent, SPEC.md §9).
    assert result.ok
    assert len(result.postings) > 0
    assert all(p.posted_at is None for p in result.postings)


def test_empty_board_is_ok_with_zero_postings():
    body = read_fixture("rippling", "list_empty.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="some-empty-board")

    assert result.ok
    assert result.postings == ()


def test_malformed_json_is_a_classified_failure_not_a_crash():
    body = read_fixture("rippling", "malformed.json")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="broken")

    assert result.ok is False


def test_404_is_a_classified_failure_never_retried():
    body = read_fixture("rippling", "not_found.json")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(404, content=body)

    with fake_client(handler) as client:
        result = fetch_postings(client, company_id=1, token="no-such-board")

    assert result.ok is False
    assert len(attempts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ats_rippling.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/ats_rippling.py
"""Rippling adapter. SPEC.md §9:
developer.rippling.com/documentation/job-board-api documents `v1`, which
requires a paid Recruiting Pro subscription and an API key. The `v2`
endpoint used here is undocumented, public, and unauthenticated — the same
endpoint Rippling's own embed widget and hosted careers page call, confirmed
live against 62 companies (spikes/iteration11_rippling_spike.py).

Unlike Greenhouse, the per-job detail call is NOT redundant: createdOn and
structured payRangeDetails exist only there. A failed detail call degrades
that one posting (posted_at/comp stay None/NONE) rather than dropping the
whole company, mirroring Greenhouse's size-cap degrade precedent (SPEC.md
§9). Token resolution from a careers page is M3's mapping-cascade job, not
this adapter's — this takes an already-known token.
"""

from datetime import datetime

from src.ats_common import AdapterResult, parse_iso_or_epoch_ms
from src.http import FetchClient
from src.models import CompDataQuality, Posting

API_BASE = "https://api.rippling.com/platform/api/ats/v2/board"


def fetch_postings(client: FetchClient, company_id: int, token: str) -> AdapterResult:
    result = client.get(f"{API_BASE}/{token}/jobs")
    if not result.ok:
        return AdapterResult(
            ok=False, error=str(result.error) if result.error else f"HTTP {result.status}"
        )

    body = result.json()
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        return AdapterResult(ok=False, error="unexpected shape: no 'items' array")

    postings = []
    for job in body["items"]:
        if not isinstance(job, dict) or job.get("id") is None:
            continue
        job_id = str(job["id"])
        locations = job.get("locations") or []
        location_names = [
            loc.get("name") for loc in locations if isinstance(loc, dict) and loc.get("name")
        ]
        workplace_types = sorted(
            {
                loc.get("workplaceType")
                for loc in locations
                if isinstance(loc, dict) and loc.get("workplaceType")
            }
        )
        posted_at, comp_quality, comp_summary = _fetch_detail(client, token, job_id)
        postings.append(
            Posting(
                company_id=company_id,
                ats_job_id=job_id,
                title_raw=job.get("name") or "",
                department_raw=(job.get("department") or {}).get("name"),
                location_raw=", ".join(location_names) or None,
                workplace_type_raw=(
                    workplace_types[0] if len(workplace_types) == 1 else None
                ),
                url=job.get("url"),
                posted_at=posted_at,
                comp_data_quality=comp_quality,
                comp_raw_summary=comp_summary,
            )
        )
    return AdapterResult(ok=True, postings=tuple(postings))


def _fetch_detail(
    client: FetchClient, token: str, job_id: str
) -> tuple[datetime | None, CompDataQuality, str | None]:
    detail_result = client.get(f"{API_BASE}/{token}/jobs/{job_id}")
    if not detail_result.ok:
        return None, CompDataQuality.NONE, None
    detail = detail_result.json()
    if not isinstance(detail, dict):
        return None, CompDataQuality.NONE, None
    posted_at = parse_iso_or_epoch_ms(detail.get("createdOn"))
    range_details = detail.get("payRangeDetails")
    if isinstance(range_details, dict) and range_details:
        parts = [
            str(range_details.get(key))
            for key in ("rangeStart", "rangeEnd", "currency", "frequency")
            if range_details.get(key) is not None
        ]
        return posted_at, CompDataQuality.STRUCTURED, " ".join(parts) or None
    return posted_at, CompDataQuality.NONE, None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ats_rippling.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit and check off C-2.8, C-2.9, C-2.10**

```bash
git add src/ats_rippling.py tests/fixtures/ats/rippling tests/test_ats_rippling.py
git commit -m "ats: add Rippling adapter (C-2.8, C-2.9, C-2.10)"
```

---

## Task 11: Full-suite network-disabled check and CRITERIA close-out

**Files:** none created — verification only.

- [ ] **Step 1: Run the entire test suite with the network guard active**

Run: `pytest -v`
Expected: PASS, including every `tests/test_ats_*.py` file above — this is the concrete
evidence for C-2.4 (original 3) and C-2.11 (all 8).

- [ ] **Step 2: Confirm no adapter imports httpx directly**

Run: `grep -rn "^import httpx\|^from httpx" src/ats_*.py`
Expected: no output. (`src/ats_common.py` and every `src/ats_*.py` file must be empty of
this pattern — only `src/http.py` imports httpx, per the Non-negotiables.)

- [ ] **Step 3: Live-run each adapter against the real M1 watchlist tokens (C-2.1, C-2.8)**

C-2.1 asks for 5 known tokens per provider; `config/watchlist.yml` (M1) has 5
Greenhouse, 5 Lever, only 3 Ashby, and 4 Rippling entries — note this gap explicitly
rather than silently treating 3 as 5 when checking the Ashby box. Write a short one-off
script (not committed to `src/`, this is a verification action, not shipped code) that
builds a real `FetchClient()` (no fake transport) and calls each adapter's
`fetch_postings` against every company in `config/watchlist.yml` for the matching
provider, printing `token -> ok/error, posting count` per row. Run it and paste the real
output — this is the actual evidence BUILD.md §0.5 asks for, not the unit-test pass/fail
count alone.

- [ ] **Step 4: Show the real output to the user and check CRITERIA.md boxes**

Per CLAUDE.md: "Check a box only when I have seen the actual output, not a summary."
Paste both the real `pytest -v` output and the real live-run output from Step 3 before
checking C-2.1 through C-2.12.

- [ ] **Step 5: Append the M2 DEVLOG entry**

Using the `BUILD.md` §0.4 template. Include, at minimum, the real findings from this
session that are new information, not just a restatement of this plan: Personio's
per-tenant inconsistency (confirmed live, not hypothetical), Personio's real structured
`salaryInformation` (richer comp than any other new provider, worth a note since SPEC's
framing of Personio was "near-zero yield"), BambooHR's missing url/date fields, and
Workable's public endpoint having no comp field despite the documented admin API
having one.

---

## Execution approach

This project's `BUILD.md` §0.3 explicitly rejects parallel tracks and PRs — everything
lands as a sequence of direct commits to `main`, one milestone at a time, because a
human reviews every commit and parallel unreviewed work is strictly worse for a
single-reviewer project. `subagent-driven-development`'s per-task branch-and-review
model doesn't fit that. **Recommended: Native** — I implement every task above myself in
this session, in order, committing after each one closes its criteria, exactly as
CLAUDE.md's session protocol already asks for.

**REQUIRED SUB-SKILL: superpowers:executing-plans**

Does this plan capture what you want? Any adjustments before I start Task 0?
