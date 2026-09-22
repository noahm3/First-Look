"""Tests for the two CI guards in tools/.

These guards are the automation BUILD.md §0.3 and SETUP-PLATFORM.md §7 substitute
for human review, so a guard that silently stops working is worse than no guard at
all — it reads as a passing build.
"""

import pathlib
import sys

import pytest

import tools.check_criteria as check_criteria
import tools.check_rls as check_rls
from tools.check_criteria import identifiers
from tools.check_rls import CREATE_TABLE, ENABLE_RLS, unquote

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestCriteriaIdentifiers:
    def test_finds_plain_and_security_identifiers(self):
        text = "- [ ] **C-0.1** thing\n- [ ] **C-1.10** other\n- [ ] **C-S.14** guard\n"
        assert identifiers(text) == {"C-0.1", "C-1.10", "C-S.14"}

    def test_a_struck_criterion_still_counts_as_present(self):
        # This is the whole point: striking is allowed, deleting is not.
        struck = "- [ ] ~~**C-6.2** old criterion~~ (superseded 2026-09-17: reason)"
        assert "C-6.2" in identifiers(struck)

    def test_ignores_prose_that_merely_looks_similar(self):
        assert identifiers("see C-onsider and CS-1 and C-9 alone") == set()


class TestRlsMigrationParsing:
    def test_detects_a_plain_create_table(self):
        sql = "CREATE TABLE runs (id INT);"
        assert [unquote(m.group("name")) for m in CREATE_TABLE.finditer(sql)] == ["runs"]

    def test_detects_schema_qualified_and_guarded_forms(self):
        sql = 'CREATE TABLE IF NOT EXISTS public."Postings" (id INT);'
        match = CREATE_TABLE.search(sql)
        assert unquote(match.group("schema")) == "public"
        assert unquote(match.group("name")) == "postings"

    def test_detects_enable_rls(self):
        sql = "ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;"
        assert [unquote(m.group("name")) for m in ENABLE_RLS.finditer(sql)] == ["companies"]

    def test_enable_rls_tolerates_odd_whitespace(self):
        sql = "ALTER  TABLE\n  postings\n  ENABLE  ROW  LEVEL  SECURITY ;"
        assert [unquote(m.group("name")) for m in ENABLE_RLS.finditer(sql)] == ["postings"]

    def test_disabling_rls_is_not_mistaken_for_enabling_it(self):
        sql = "ALTER TABLE postings DISABLE ROW LEVEL SECURITY;"
        assert list(ENABLE_RLS.finditer(sql)) == []


class TestGuardsActuallyFail:
    """Exercise the non-zero exit paths. A guard that only ever passes is decoration."""

    def _run(self, module, argv, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)
        monkeypatch.setattr(sys, "argv", argv)
        return module.main()

    def test_criteria_guard_blocks_a_deleted_identifier(self, tmp_path, monkeypatch):
        committed = (REPO_ROOT / "CRITERIA.md").read_text(encoding="utf-8")
        tampered = "\n".join(line for line in committed.splitlines() if "**C-0.5**" not in line)
        candidate = tmp_path / "CRITERIA_tampered.md"
        candidate.write_text(tampered, encoding="utf-8")

        exit_code = self._run(
            check_criteria,
            [
                "check_criteria.py",
                "--base",
                "HEAD",
                "--base-file",
                "CRITERIA.md",
                "--file",
                str(candidate),
            ],
            monkeypatch,
        )
        assert exit_code == 1

    def test_criteria_guard_passes_when_nothing_was_removed(self, monkeypatch):
        exit_code = self._run(
            check_criteria,
            ["check_criteria.py", "--base", "HEAD", "--file", "CRITERIA.md"],
            monkeypatch,
        )
        assert exit_code == 0

    def test_rls_guard_blocks_a_table_created_without_rls(self, tmp_path, monkeypatch):
        (tmp_path / "0001_tables.sql").write_text(
            "CREATE TABLE public.companies (id BIGINT);\n"
            "ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;\n"
            "CREATE TABLE public.postings (id BIGINT);\n",
            encoding="utf-8",
        )
        exit_code = self._run(check_rls, ["check_rls.py", "--dir", str(tmp_path)], monkeypatch)
        assert exit_code == 1

    def test_rls_guard_passes_when_every_table_enables_rls(self, tmp_path, monkeypatch):
        (tmp_path / "0001_tables.sql").write_text(
            "CREATE TABLE public.companies (id BIGINT);\n"
            "ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;\n",
            encoding="utf-8",
        )
        exit_code = self._run(check_rls, ["check_rls.py", "--dir", str(tmp_path)], monkeypatch)
        assert exit_code == 0

    @pytest.mark.parametrize("missing_dir", ["does_not_exist", "also_missing"])
    def test_rls_guard_is_quiet_when_there_are_no_migrations_yet(
        self, tmp_path, monkeypatch, missing_dir
    ):
        exit_code = self._run(
            check_rls,
            ["check_rls.py", "--dir", str(tmp_path / missing_dir)],
            monkeypatch,
        )
        assert exit_code == 0
