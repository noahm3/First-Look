"""Tests for src/getro.py (SPEC.md §7.2, BUILD.md M6, C-6.1).

Fixtures under tests/fixtures/getro/ are trimmed __NEXT_DATA__ payloads recorded
live 2026-09-24 against two confirmed real boards (breakthroughenergy.getro.com,
jobs.bluebearcap.com) plus a third confirmed board (jobs.convectivecapital.com) --
config/getro_boards.yml's header has the full provenance. No test here opens a
socket (tests/conftest.py blocks it); every response is replayed from a fixture.
"""

import pathlib

import pytest
import yaml

from src.db import Database
from src.getro import (
    DiscoverySummary,
    GetroBoard,
    GetroParseError,
    discover_boards,
    extract_companies,
    fetch_board_companies,
    load_boards,
    parse_next_data,
)
from tests.ats_fixtures import fake_client, respond

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "getro"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestLoadBoards:
    def test_the_real_committed_board_list_parses(self):
        boards = load_boards(pathlib.Path("config/getro_boards.yml"))
        assert len(boards) >= 2
        assert all(b.name and b.url for b in boards)

    def test_an_entry_missing_a_url_is_rejected(self, tmp_path: pathlib.Path):
        path = tmp_path / "boards.yml"
        path.write_text(yaml.safe_dump([{"name": "Some VC"}]), encoding="utf-8")
        with pytest.raises(ValueError):
            load_boards(path)


class TestParseNextData:
    def test_c_6_1_a_real_confirmed_board_parses(self):
        data = parse_next_data(read_fixture("breakthrough.html"))
        jobs = data["props"]["pageProps"]["initialState"]["jobs"]["found"]
        assert len(jobs) > 0

    def test_c_6_1_a_second_real_confirmed_board_with_a_different_org_set_parses(self):
        data = parse_next_data(read_fixture("bluebear.html"))
        jobs = data["props"]["pageProps"]["initialState"]["jobs"]["found"]
        assert len(jobs) > 0

    def test_a_board_with_no_next_data_script_tag_raises_a_classified_error(self):
        # SPEC.md §7.2: jobs.a16z.com turned out to be Next.js App Router with a
        # streamed RSC payload instead -- shape drift, not a bug in this parser.
        with pytest.raises(GetroParseError):
            parse_next_data(read_fixture("no_next_data.html"))

    def test_truncated_json_inside_the_script_tag_raises_a_classified_error(self):
        with pytest.raises(GetroParseError):
            parse_next_data(read_fixture("malformed.html"))


class TestExtractCompanies:
    def test_distinct_organizations_are_each_returned_once(self):
        data = parse_next_data(read_fixture("breakthrough.html"))
        companies = extract_companies(data)
        assert len(companies) == 2
        assert {c.name for c in companies} == {"RenewCO2", "RIFT"}

    def test_the_same_organization_across_two_job_postings_is_deduped(self):
        data = parse_next_data(read_fixture("duplicate_org.html"))
        companies = extract_companies(data)
        assert len(companies) == 1
        assert companies[0].name == "Delos"

    def test_a_real_zero_jobs_board_yields_zero_companies_not_an_error(self):
        # Confirmed live: some VC boards on this platform currently have zero
        # open roles. That is a valid outcome, not a parse failure.
        data = parse_next_data(read_fixture("empty.html"))
        assert extract_companies(data) == []

    def test_a_missing_organization_on_one_job_is_skipped_not_fatal(self):
        data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "jobs": {
                            "found": [
                                {"id": 1, "organization": None},
                                {
                                    "id": 2,
                                    "organization": {
                                        "id": "x1",
                                        "name": "Real Co",
                                        "slug": "real-co",
                                    },
                                },
                            ]
                        }
                    }
                }
            }
        }
        companies = extract_companies(data)
        assert len(companies) == 1
        assert companies[0].name == "Real Co"

    def test_wrong_shape_raises_a_classified_error_not_a_crash(self):
        with pytest.raises(GetroParseError):
            extract_companies({"props": {}})


class TestFetchBoardCompanies:
    def test_a_successful_fetch_returns_parsed_companies(self):
        body = read_fixture("breakthrough.html").encode("utf-8")

        def handler(request):
            assert "breakthroughenergy.getro.com" in str(request.url)
            return respond(200, content=body)

        board = GetroBoard(
            name="Breakthrough Energy Ventures", url="https://breakthroughenergy.getro.com/jobs"
        )
        with fake_client(handler) as client:
            companies = fetch_board_companies(client, board)

        assert len(companies) == 2

    def test_a_404_raises_a_classified_error_not_a_crash(self):
        def handler(_request):
            return respond(404, content=b"not found")

        board = GetroBoard(name="Dead Board", url="https://dead.getro.com/jobs")
        with fake_client(handler) as client, pytest.raises(GetroParseError):
            fetch_board_companies(client, board)


class FakeCompaniesDb:
    """A minimal in-memory stand-in for `companies` + `company_sources`, scoped
    to this file so getro's tests don't depend on watchlist's test internals."""

    def __init__(self):
        self.companies: dict[int, tuple[str, str | None]] = {}
        self.sources: dict[tuple[int, str], str] = {}
        self._next_id = 1

    def router(self, sql: str, params: tuple):
        if sql.startswith("SELECT company_id FROM company_sources"):
            source, source_id = params
            for (company_id, src), sid in self.sources.items():
                if src == source and sid == source_id:
                    return [(company_id,)]
            return []
        if sql.startswith("SELECT id FROM companies WHERE canonical_domain"):
            (domain,) = params
            for company_id, (_name, dom) in self.companies.items():
                if dom == domain:
                    return [(company_id,)]
            return []
        if sql.startswith("INSERT INTO companies"):
            name, domain = params
            company_id = self._next_id
            self._next_id += 1
            self.companies[company_id] = (name, domain)
            return [(company_id,)]
        if sql.startswith("INSERT INTO company_sources"):
            company_id, source, source_id = params
            self.sources.setdefault((company_id, source), source_id)
            return []
        raise AssertionError(f"unexpected SQL in fake router: {sql}")


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self._conn._result = self._conn.router(" ".join(sql.split()), params or ())

    def fetchone(self):
        rows = self._conn._result or []
        return rows[0] if rows else None

    def fetchall(self):
        return list(self._conn._result or [])


class FakeConnection:
    def __init__(self, backend: FakeCompaniesDb):
        self._backend = backend
        self._result: list[tuple] | None = None

    def router(self, sql, params):
        return self._backend.router(sql, params)

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def make_db() -> tuple[Database, FakeCompaniesDb]:
    backend = FakeCompaniesDb()
    conn = FakeConnection(backend)
    db = Database("postgresql://user:pw@localhost/db", connect_fn=lambda *_a, **_k: conn)
    db.connect()
    return db, backend


class TestDiscoverBoards:
    def test_c_6_1_two_real_boards_parse_and_their_companies_are_ingested_as_getro_sourced(self):
        db, backend = make_db()

        def handler(request):
            if "breakthroughenergy" in str(request.url):
                return respond(200, content=read_fixture("breakthrough.html").encode())
            if "bluebearcap" in str(request.url):
                return respond(200, content=read_fixture("bluebear.html").encode())
            raise AssertionError(f"unexpected URL in test: {request.url}")

        boards = [
            GetroBoard(
                name="Breakthrough Energy Ventures", url="https://breakthroughenergy.getro.com/jobs"
            ),
            GetroBoard(name="Blue Bear Capital", url="https://jobs.bluebearcap.com/jobs"),
        ]

        with fake_client(handler) as client:
            summary = discover_boards(db, client, boards)

        assert summary.boards_parsed == 2
        assert summary.boards_failed == 0
        assert summary.companies_created == 4  # 2 orgs per fixture board
        assert all(source == "getro" for (_cid, source) in backend.sources)
        assert all(domain is None for (_name, domain) in backend.companies.values())

    def test_one_bad_board_does_not_stop_the_others_from_being_ingested(self):
        db, backend = make_db()

        def handler(request):
            if "breakthroughenergy" in str(request.url):
                return respond(200, content=read_fixture("breakthrough.html").encode())
            return respond(200, content=read_fixture("no_next_data.html").encode())

        boards = [
            GetroBoard(
                name="Breakthrough Energy Ventures", url="https://breakthroughenergy.getro.com/jobs"
            ),
            GetroBoard(name="Drifted-Shape VC", url="https://drifted.getro.com/jobs"),
        ]

        with fake_client(handler) as client:
            summary = discover_boards(db, client, boards)

        assert summary.boards_parsed == 1
        assert summary.boards_failed == 1
        assert summary.companies_created == 2
        assert len(backend.companies) == 2

    def test_re_running_discovery_creates_zero_duplicate_companies(self):
        db, backend = make_db()

        def handler(_request):
            return respond(200, content=read_fixture("breakthrough.html").encode())

        boards = [
            GetroBoard(
                name="Breakthrough Energy Ventures", url="https://breakthroughenergy.getro.com/jobs"
            )
        ]

        with fake_client(handler) as client:
            first = discover_boards(db, client, boards)
        with fake_client(handler) as client:
            second = discover_boards(db, client, boards)

        assert first == DiscoverySummary(
            boards_parsed=1, boards_failed=0, companies_created=2, companies_already_present=0
        )
        assert second == DiscoverySummary(
            boards_parsed=1, boards_failed=0, companies_created=0, companies_already_present=2
        )
        assert len(backend.companies) == 2

    def test_a_no_domain_company_already_known_via_another_source_is_not_merged(self):
        db, backend = make_db()
        # A no-domain company already known via another source (e.g. the
        # watchlist, itself no-domain per C-1.8) does NOT get merged with the
        # same company discovered via Getro -- this is SPEC.md §7.2's domain
        # gap, honestly reflected rather than papered over: with no
        # canonical_domain on either side, ingest_manual_company has no way to
        # know these are the same company, so a second row is created.
        backend.companies[99] = ("RenewCO2", None)
        backend.sources[(99, "manual")] = "name:renewco2"

        def handler(_request):
            return respond(200, content=read_fixture("breakthrough.html").encode())

        boards = [
            GetroBoard(
                name="Breakthrough Energy Ventures", url="https://breakthroughenergy.getro.com/jobs"
            )
        ]
        with fake_client(handler) as client:
            summary = discover_boards(db, client, boards)

        assert summary.companies_created == 2
        assert len(backend.companies) == 3
        assert (99, "getro") not in backend.sources
