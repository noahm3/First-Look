"""Tests for src/consider.py (SPEC.md §7.6, CRITERIA.md C-6.4).

Fixtures under tests/fixtures/consider/ are trimmed real responses recorded
live 2026-09-24 against two confirmed real boards (jobs.greentownlabs.com,
jobs.congruentvc.com) -- config/consider_boards.yml's header has the full
provenance. Page fixtures use a real board id but a placeholder csrfToken
(no real session artifact committed to a public repo). No test here opens a
socket (tests/conftest.py blocks it); every response is replayed from a
fixture.
"""

import pathlib

import pytest
import yaml

from src.consider import (
    CONSIDER_DERIVED_FIELDS_TO_IGNORE,
    ConsiderBoard,
    ConsiderParseError,
    DiscoverySummary,
    discover_boards,
    extract_companies,
    fetch_board_companies,
    load_boards,
    parse_session,
)
from src.db import Database
from tests.ats_fixtures import fake_client, respond

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "consider"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestLoadBoards:
    def test_the_real_committed_board_list_parses(self):
        boards = load_boards(pathlib.Path("config/consider_boards.yml"))
        assert len(boards) >= 2
        assert all(b.name and b.url for b in boards)

    def test_an_entry_missing_a_url_is_rejected(self, tmp_path: pathlib.Path):
        path = tmp_path / "boards.yml"
        path.write_text(yaml.safe_dump([{"name": "Some VC"}]), encoding="utf-8")
        with pytest.raises(ValueError):
            load_boards(path)


class TestParseSession:
    def test_c_6_4_a_real_confirmed_board_parses(self):
        csrf_token, board_id = parse_session(read_fixture("greentown_page.html"))
        assert csrf_token
        assert board_id == "greentown-labs"

    def test_c_6_4_a_second_real_confirmed_board_parses(self):
        csrf_token, board_id = parse_session(read_fixture("congruent_page.html"))
        assert csrf_token
        assert board_id == "congruent-ventures"

    def test_a_board_with_no_server_initial_data_raises_a_classified_error(self):
        # SPEC.md §7.6: a fingerprint-flagged candidate is not a confirmed
        # board -- SOSV 404s outright (spikes/iteration15_consider_notes.md).
        # This fixture models the case where the page loads but the shape
        # isn't there at all.
        with pytest.raises(ConsiderParseError):
            parse_session(read_fixture("no_server_initial_data.html"))

    def test_truncated_json_raises_a_classified_error(self):
        with pytest.raises(ConsiderParseError):
            parse_session(read_fixture("malformed_page.html"))


class TestExtractCompanies:
    def test_companies_are_extracted_with_their_real_domain(self):
        import json

        body = json.loads(read_fixture("greentown_page1.json"))
        companies = extract_companies(body["jobs"])
        assert len(companies) == 2
        by_name = {c.name: c for c in companies}
        assert by_name["Upstream Tech"].domain == "upstream.tech"
        assert by_name["Upstream Tech"].slug == "upstream-tech"

    def test_a_job_missing_company_fields_is_skipped_not_fatal(self):
        jobs = [
            {"companyName": None, "companySlug": None},
            {"companyName": "Real Co", "companySlug": "real-co"},
        ]
        companies = extract_companies(jobs)
        assert len(companies) == 1
        assert companies[0].name == "Real Co"
        assert companies[0].domain is None

    def test_consider_derived_fields_are_never_read_off_the_returned_company(self):
        # The fixtures deliberately carry 'scores' and 'skills' (Consider's own
        # inferred output, SPEC.md §3.6/§4) to prove the adapter never surfaces
        # them -- ConsiderCompany has no field for either.
        import dataclasses
        import json

        body = json.loads(read_fixture("greentown_page1.json"))
        assert "scores" in body["jobs"][0]  # the fixture really carries it
        companies = extract_companies(body["jobs"])
        stored_fields = {f.name for f in dataclasses.fields(companies[0])}
        assert stored_fields.isdisjoint(CONSIDER_DERIVED_FIELDS_TO_IGNORE)


class TestFetchBoardCompanies:
    def test_c_6_4_two_pages_are_walked_via_the_sequence_cursor_and_deduped(self):
        board = ConsiderBoard(name="Greentown Labs", url="https://jobs.greentownlabs.com/jobs")
        calls = {"n": 0}

        def handler(request):
            if request.method == "GET":
                return respond(200, content=read_fixture("greentown_page.html").encode())
            calls["n"] += 1
            body = read_fixture(f"greentown_page{calls['n']}.json").encode()
            return respond(200, content=body)

        with fake_client(handler) as client:
            companies = fetch_board_companies(client, board, page_size=2, max_pages=2)

        assert len(companies) == 4  # 2 distinct companies per fixture page, no overlap
        assert calls["n"] == 2

    def test_the_same_company_across_two_pages_is_deduped(self):
        board = ConsiderBoard(name="Dup Board", url="https://dup.example.com/jobs")
        calls = {"n": 0}

        def handler(request):
            if request.method == "GET":
                return respond(200, content=read_fixture("greentown_page.html").encode())
            calls["n"] += 1
            body = read_fixture(f"dup_page{calls['n']}.json").encode()
            return respond(200, content=body)

        with fake_client(handler) as client:
            companies = fetch_board_companies(client, board, page_size=1, max_pages=5)

        assert len(companies) == 1
        assert companies[0].name == "Delos"

    def test_a_real_zero_jobs_board_yields_zero_companies_not_an_error(self):
        board = ConsiderBoard(name="Empty Board", url="https://empty.example.com/jobs")

        def handler(request):
            if request.method == "GET":
                return respond(200, content=read_fixture("greentown_page.html").encode())
            return respond(200, content=read_fixture("empty_page1.json").encode())

        with fake_client(handler) as client:
            companies = fetch_board_companies(client, board)

        assert companies == []

    def test_the_max_pages_cap_stops_pagination_even_if_more_sequence_tokens_remain(self):
        board = ConsiderBoard(name="Greentown Labs", url="https://jobs.greentownlabs.com/jobs")
        calls = {"n": 0}

        def handler(request):
            if request.method == "GET":
                return respond(200, content=read_fixture("greentown_page.html").encode())
            calls["n"] += 1
            # page1 has a real sequence token -- pagination *could* continue,
            # but max_pages=1 must stop it here regardless.
            return respond(200, content=read_fixture("greentown_page1.json").encode())

        with fake_client(handler) as client:
            companies = fetch_board_companies(client, board, page_size=2, max_pages=1)

        assert calls["n"] == 1
        assert len(companies) == 2

    def test_a_session_fetch_404_raises_a_classified_error_not_a_crash(self):
        board = ConsiderBoard(name="Dead Board", url="https://dead.example.com/jobs")

        def handler(_request):
            return respond(404, content=b"not found")

        with fake_client(handler) as client, pytest.raises(ConsiderParseError):
            fetch_board_companies(client, board)


class FakeCompaniesDb:
    """A minimal in-memory stand-in for `companies` + `company_sources`, scoped
    to this file (same pattern as tests/test_getro.py)."""

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
    def test_c_6_4_two_real_boards_are_ingested_as_consider_sourced_with_real_domains(self):
        db, backend = make_db()

        def handler(request):
            if request.method == "GET":
                if "greentownlabs" in str(request.url):
                    return respond(200, content=read_fixture("greentown_page.html").encode())
                return respond(200, content=read_fixture("congruent_page.html").encode())
            if "greentownlabs" in str(request.url):
                return respond(200, content=read_fixture("empty_page1.json").encode())
            return respond(200, content=read_fixture("congruent_page1.json").encode())

        boards = [
            ConsiderBoard(name="Greentown Labs", url="https://jobs.greentownlabs.com/jobs"),
            ConsiderBoard(name="Congruent Ventures", url="https://jobs.congruentvc.com/jobs"),
        ]

        with fake_client(handler) as client:
            summary = discover_boards(db, client, boards)

        assert summary.boards_parsed == 2
        assert summary.boards_failed == 0
        assert summary.companies_created == 1  # congruent_page1.json has 1 company
        assert all(source == "consider" for (_cid, source) in backend.sources)
        # Unlike Getro, Consider companies land WITH a real domain.
        assert all(domain is not None for (_name, domain) in backend.companies.values())

    def test_one_bad_board_does_not_stop_the_others(self):
        db, backend = make_db()

        def handler(request):
            if "greentownlabs" in str(request.url):
                if request.method == "GET":
                    return respond(200, content=read_fixture("greentown_page.html").encode())
                return respond(200, content=read_fixture("greentown_page1.json").encode())
            return respond(404, content=b"not found")

        boards = [
            ConsiderBoard(name="Greentown Labs", url="https://jobs.greentownlabs.com/jobs"),
            ConsiderBoard(name="Dead Board", url="https://dead.example.com/jobs"),
        ]

        with fake_client(handler) as client:
            summary = discover_boards(db, client, boards)

        assert summary.boards_parsed == 1
        assert summary.boards_failed == 1
        assert summary.companies_created == 2
        assert len(backend.companies) == 2

    def test_re_running_discovery_creates_zero_duplicate_companies(self):
        db, backend = make_db()

        def handler(request):
            if request.method == "GET":
                return respond(200, content=read_fixture("greentown_page.html").encode())
            return respond(200, content=read_fixture("greentown_page1.json").encode())

        boards = [ConsiderBoard(name="Greentown Labs", url="https://jobs.greentownlabs.com/jobs")]

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
