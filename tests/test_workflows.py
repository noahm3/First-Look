"""Static checks on the GitHub Actions workflows.

The repo is public, so anyone can open a pull request, and a workflow that runs
attacker-controlled code with secrets in scope is a full compromise: KEEPALIVE_PAT
has write access to a repo that auto-executes workflows (SECURITY.md §S2).

C-S.6, C-S.7 and C-S.8 are properties of these files, so they are checked here
rather than re-read by a person each milestone. Parsed as YAML rather than
grepped, so a comment explaining why a trigger is absent does not read as the
trigger being present.
"""

import pathlib
import re

import pytest
import yaml

WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOW_FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))

SECRETS_FREE_WORKFLOWS = {"test.yml"}
FORBIDDEN_TRIGGERS = {"pull_request", "pull_request_target"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

SECRET_REFERENCE = re.compile(r"\$\{\{\s*secrets\.", re.IGNORECASE)


def load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def on_section(workflow: dict):
    """The `on:` block.

    PyYAML resolves an unquoted `on:` key to the boolean True (the Norway
    problem's cousin), so reading workflow["on"] raises KeyError on a perfectly
    valid file. Accept both spellings rather than depending on either.
    """
    if "on" in workflow:
        return workflow["on"]
    return workflow.get(True)


def triggers(workflow: dict) -> set[str]:
    section = on_section(workflow)
    if isinstance(section, str):
        return {section}
    if isinstance(section, list):
        return set(section)
    if isinstance(section, dict):
        return set(section)
    return set()


def steps(workflow: dict) -> list[dict]:
    found: list[dict] = []
    for job in (workflow.get("jobs") or {}).values():
        found.extend(job.get("steps") or [])
    return found


def test_the_expected_workflows_exist():
    names = {p.name for p in WORKFLOW_FILES}
    assert names == {
        "test.yml",
        "monitor.yml",
        "discover.yml",
        "migrate.yml",
        "watchlist.yml",
    }, names


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
class TestTriggers:
    def test_no_workflow_triggers_on_a_pull_request(self, path):
        """C-S.6.

        pull_request_target is the dangerous one — it runs in the base repo's
        context with secrets available. plain pull_request is forbidden too,
        because BUILD.md §0.3 rejected PRs as a workflow, which makes the
        trigger dead configuration that only widens the surface.
        """
        assert not (triggers(load(path)) & FORBIDDEN_TRIGGERS)

    def test_every_workflow_can_be_run_by_hand(self, path):
        """SPEC.md §16's recovery action: one dispatch tap from the mobile app."""
        assert "workflow_dispatch" in triggers(load(path))

    def test_permissions_are_declared_explicitly(self, path):
        """SECURITY.md §S2: minimum necessary, never the default token scope."""
        assert "permissions" in load(path)


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
class TestActionPinning:
    def test_every_third_party_action_is_pinned_to_a_full_commit_sha(self, path):
        """C-S.8 — a mutable tag can be repointed at code that reads secrets."""
        for step in steps(load(path)):
            uses = step.get("uses")
            if not uses:
                continue
            assert "@" in uses, f"{path.name}: {uses} has no ref at all"
            _action, ref = uses.rsplit("@", 1)
            assert FULL_SHA.match(ref), f"{path.name}: {uses} is not a 40-char SHA"


class TestSecretBoundary:
    def test_the_test_workflow_has_no_secrets_in_scope(self):
        """C-S.7 — this is the boundary, not an organisational preference."""
        for name in SECRETS_FREE_WORKFLOWS:
            source = (WORKFLOWS_DIR / name).read_text(encoding="utf-8")
            # Strip comments: the file documents the rule it follows.
            code = "\n".join(
                line for line in source.splitlines() if not line.strip().startswith("#")
            )
            assert not SECRET_REFERENCE.search(code), f"{name} references a secret"

    def test_secret_carrying_workflows_never_run_on_a_schedule_they_should_not(self):
        # migrate.yml applies schema changes. A scheduled schema change landing
        # unattended during leave is the class of quiet risk SPEC.md §3.3 exists
        # to prevent, so it is dispatch-only.
        assert triggers(load(WORKFLOWS_DIR / "migrate.yml")) == {"workflow_dispatch"}

    def test_monitor_and_discover_are_scheduled_and_dispatchable_only(self):
        for name in ("monitor.yml", "discover.yml"):
            assert triggers(load(WORKFLOWS_DIR / name)) == {"schedule", "workflow_dispatch"}


class TestMonitorSpecifics:
    @property
    def monitor(self) -> dict:
        return load(WORKFLOWS_DIR / "monitor.yml")

    def test_it_runs_four_times_a_day(self):
        """SPEC.md §16: four attributed runs daily, and §1's ~4x polling."""
        crons = [entry["cron"] for entry in on_section(self.monitor)["schedule"]]
        hours = crons[0].split()[1].split(",")
        assert len(hours) == 4, crons

    def test_it_holds_a_concurrency_group_that_does_not_cancel(self):
        """C-0.7 — two overlapping runs cannot occur."""
        concurrency = self.monitor["concurrency"]
        assert concurrency["group"] == "monitor"
        assert concurrency["cancel-in-progress"] is False

    def test_the_checkout_uses_the_pat_not_the_default_token(self):
        """C-0.3 / SPEC.md §16 — bot commits are reported not to reset the
        60-day inactivity timer; user commits do."""
        checkout = next(s for s in steps(self.monitor) if "checkout" in (s.get("uses") or ""))
        assert "KEEPALIVE_PAT" in checkout["with"]["token"]

    def test_it_requests_write_access_only_for_contents(self):
        assert self.monitor["permissions"] == {"contents": "write"}

    def test_discover_is_a_separate_concurrency_group(self):
        # SPEC.md §5: a crash in fragile discovery code must not take down
        # monitoring — which includes not queueing behind it.
        assert load(WORKFLOWS_DIR / "discover.yml")["concurrency"]["group"] == "discover"


class TestNoPersonalData:
    """SPEC.md §15 / CLAUDE.md: never commit an email address, noreply included."""

    @pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
    def test_no_email_shaped_literal(self, path):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", source)

    @pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
    def test_nothing_echoes_an_environment_variable_wholesale(self, path):
        # SECURITY.md §S2: never echo, print or log an env var, and never add a
        # debug step that dumps env.
        source = path.read_text(encoding="utf-8")
        for banned in ("env | ", "printenv", "echo $SUPABASE", "echo $HEALTHCHECK"):
            assert banned not in source, f"{path.name} contains {banned!r}"
