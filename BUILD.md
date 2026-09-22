# First Look — Implementation Guide

Companion to `SPEC.md` (what and why), `CRITERIA.md` (what "done" means), and
`SECURITY.md` (threat model).

**This guide covers the pre-platform build only** — `SPEC.md` §1–§18, milestones `M-1`
through `M12`. `SPEC.md` §19 describes a platform era (accounts, real alerting, an
application tracker) that is explicitly deferred; when that work starts, its setup steps
live in `SETUP-PLATFORM.md`, not here.

---

## 0. Working setup

### 0.1 Files

```
SPEC.md              # current-state design — editable. §1-18 current build, §19 platform era (deferred)
CRITERIA.md          # acceptance criteria — append and strike only, never delete
SECURITY.md          # threat model and hardening requirements
BUILD.md             # this file
SETUP-PLATFORM.md    # platform-era account/infra setup — not needed until SPEC.md §19 starts
DEVLOG.md            # session history — editable
CLAUDE.md            # short pointer, read automatically every session
archive/             # superseded documents, kept verbatim for history — never edited
```

Separate documents because a single spec was doing two jobs and only one was getting
corrupted. `SPEC.md` answers "what is true now." `CRITERIA.md` holds success conditions
that must never quietly disappear. `DEVLOG.md` holds the narrative.

### 0.2 CLAUDE.md

```markdown
# Project: First Look

Read SPEC.md before making design decisions. SPEC.md §4 lists rejected
alternatives — do not re-propose them. SPEC.md §19 is a deferred platform
era; do not build it without being asked.
Read BUILD.md for the current milestone. Read CRITERIA.md for its criteria.
Read the last two DEVLOG.md entries at the start of every session.

## Session protocol — every time
1. Read the last two DEVLOG entries and state where we left off.
2. Check the current milestone header in BUILD.md. It specifies a recommended
   model and whether to use plan mode. **Tell me explicitly** whether to switch
   model or enter plan mode, and wait for me to confirm before starting.
3. Commit directly to main. Commit at each criterion, not once at the end.
4. Before committing any change to SPEC.md or CRITERIA.md, show me the diff.
5. At session end, append a DEVLOG entry using the BUILD.md §0.4 template.
6. End every milestone with the evidence report in BUILD.md §0.5. Show real
   terminal output, never a summary.

## THIS IS A PUBLIC REPOSITORY
Everything committed is world-readable, including Actions run logs.

NEVER commit, print, or log:
- Email addresses (notify profiles live in the NOTIFY_PROFILES secret)
- LinkedIn connection data of any kind, including aggregate counts
- Any third party's name, employer, or contact details
- API keys, tokens, or credentials

GitHub masks exact secret values in logs. NOTIFY_PROFILES is a JSON blob we
parse, so an email extracted from it is a DIFFERENT string and will NOT be
masked. Never log a parsed profile, and never include a recipient in an
error message.

Run summaries report counts, never identities. Company names, ATS tokens, and
job postings are public data and are fine. If unsure whether something is
personal data, ask before committing it.

## CRITERIA.md rules
- Never delete or reword an existing criterion. Strike it through with a date
  and reason if superseded. Append new ones.
- Check a box only when I have seen the actual output, not a summary.

## Non-negotiables
- Python 3.13, stdlib + httpx + pytest. Justify any other dependency.
- No user-specific job criteria in src/. Dashboard filters are client-side;
  notification criteria come from the NOTIFY_PROFILES secret.
- No headless browsers. No authenticated scraping. No OAuth, no backend,
  no user accounts. No LinkedIn API or scraping.
- Every per-company operation is wrapped so no exception escapes the loop.
- Every network call goes through src/http.py. Nothing calls httpx directly.
- Tests never hit the network. Use fixtures in tests/fixtures/.
- Read SECURITY.md before writing dashboard rendering code, workflow files,
  or anything touching NOTIFY_PROFILES.
- Never use innerHTML, outerHTML, insertAdjacentHTML, or document.write with
  data from a posting, company, or URL parameter. Use textContent.

## Current milestone
M-1. See BUILD.md.
```

### 0.3 Single track, direct to main, automated guards

**Build one milestone at a time, sequentially, committing directly to `main`.**

Parallel tracks were considered and rejected. Several milestones are technically
independent — M6 and M9 in particular could run alongside the backend chain — but
parallelism only pays off when the human is the review bottleneck. Without line-by-line
review, two tracks mean twice as much unreviewed code landing simultaneously, which is
strictly worse.

Pull requests were also considered and rejected, for the same reason. They existed to
force a diff review; a PR approved without reading is theatre. **The two things PRs were
guarding are automated instead**, which is more reliable than a person scanning for them:

**Pre-commit hook — blocks personal data.** `.githooks/pre-commit`, enabled with
`git config core.hooksPath .githooks`:

```bash
#!/usr/bin/env bash
if git diff --cached -U0 | grep -qE '^\+.*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'; then
  echo "BLOCKED: email address in staged changes"; exit 1
fi
if git diff --cached --name-only | grep -qiE 'connections.*\.(csv|json)'; then
  echo "BLOCKED: connection data in staged changes"; exit 1
fi
```

**CI check — protects CRITERIA.md.** In `test.yml`: fail the build if any `C-` identifier
present in `main`'s copy is missing from the current one. Twenty lines of Python, and it
enforces the never-delete rule better than a tired person at 11pm.

Plus GitHub secret scanning and push protection, enabled in M-1.

### 0.4 DEVLOG.md

Editable, one entry per session, newest at the bottom:

```markdown
## 2026-09-15 — M2: ATS adapters
**Model:** Sonnet 5 · **Plan mode:** no

### Built
- greenhouse.py, lever.py, ashby.py + fixtures

### Decisions made this session
- Lever `categories.team` for department_raw, not `categories.department` —
  department is often null while team is populated. SPEC §9 updated.

### Deviations from SPEC
- None / [what changed, and whether SPEC.md was updated]

### Criteria checked
- C-2.1 through C-2.7

### Least confident about
- Ashby comp string parsing — only tested against 4 real examples

### Next session
- M3, mapping cascade. Opus + plan mode.
```

**Decisions that change what is true also go into SPEC.md.** The devlog is history; the
spec is current state. If only the devlog knows, the spec has rotted.

DEVLOG is committed to a public repo — keep personal detail out.

### 0.5 Closing a milestone — evidence, not code

You are not reviewing implementation. You are reviewing evidence that the criteria hold.
Whether `http.py` uses a token bucket or a semaphore is not a decision needing your
opinion.

End every milestone with:

```
Don't show me code. For each criterion in this milestone, show the command
you ran and its actual terminal output — not a summary, not "this passes."
Paste the real output.

Then tell me: what did you build that ISN'T in SPEC.md? What did you skip?
What are you least confident about?
```

That last question is the highest-value one in the process. It reliably points at the
thing worth looking at.

**Two places to look at output directly:**

- **M3** — open `data/mapping_review.csv`. Fifty rows of company, provider, token. Do the
  tokens look like the companies? That is the entire check, and it needs no code reading.
- **M10** — send one test email to yourself. Right posting? Arrived once?

### 0.6 Models and plan mode

Every milestone header carries **Model** and **Plan mode**; CLAUDE.md instructs Claude
Code to surface them and wait.

- `/model` switches mid-session with context preserved.
- `--model` at launch; `model` in `settings.json` persists it.
- Natural pattern: **plan in Opus, implement in Sonnet, same session.**
- Override: switch up to Opus after two consecutive attempts fail to progress.

---

## 1. M-1 — Accounts, git, GitHub

**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 1.5–2h · *Mostly you, not Claude.*
**Criteria:** C-1.1 – C-1.5, C-1.9, C-1.10

### 1.1 Plan and posture

GitHub Free, **public repository**. Pages serves from public repos on Free; Actions
minutes are unmetered on public repos, so run frequency costs nothing.

Building in public is accepted. The posture is **low-profile, not hidden**:

- **Neutral repository name.** Don't name it after your job search.
- No README tying the project to you. No personal name on the dashboard.
- Don't pin it on your profile.
- `config/watchlist.yml` is committed and readable — accepted.

The 60-day scheduled-workflow inactivity disable applies to public repos — almost exactly
the leave window. Mitigated in §1.5, caught by the dead-man's switch regardless. A second,
independent keepalive risk applies once Postgres is wired up in M0 — see `SPEC.md` §16.

### 1.2 Accounts

1. **GitHub CLI** — `brew install gh`, `gh auth login`.
2. **healthchecks.io** — free; create the check, period matching the run schedule,
   generous grace. Put the dashboard URL in the description so it appears in alerts.
   Confirm the alert address is one you read on your phone.
3. **Resend** — free account, verify a sender, create a send-only API key.
4. **Fine-grained PAT** — **scoped to this one repository, `Contents: read/write` only,
   no `workflow` scope. Set the expiry past the end of leave and record the date in
   DEVLOG** — a default 90-day token created now dies in November with nobody around to
   renew it (`SECURITY.md §S4`).
5. **A hosted form** (Tally / Google Forms / Formspree) for alert requests, SPEC §13.2.
6. **Enable secret scanning and push protection** — Settings → Code security. One toggle,
   and the only control that catches an accidental paste.
7. **Enable "Require approval for all external contributors"** — Settings → Actions →
   General.
8. `git config --global user.name` / `user.email` if unset.
9. **Supabase project**, per `SETUP-PLATFORM.md` §4. Storage moves to Postgres in this
   milestone's successor (M0) per `SPEC.md` §6 — start the account now so the DNS/OAuth
   waiting periods in `SETUP-PLATFORM.md` §0 don't block later.

### 1.3 Repo creation

```bash
mkdir <neutral-name> && cd <neutral-name>
git init
git config core.hooksPath .githooks     # §0.3 pre-commit hook
gh repo create <neutral-name> --public --source=. --remote=origin
gh secret set HEALTHCHECK_URL
gh secret set RESEND_API_KEY
gh secret set KEEPALIVE_PAT
gh secret set NOTIFY_PROFILES       # JSON array — SPEC §13.1
gh api -X PUT repos/:owner/:repo/pages -f "source[branch]=main" -f "source[path]=/docs"
```

**Write `.gitignore` before the first commit**, including entries for features that don't
exist yet:

```
.venv/
__pycache__/
*.pyc
.cache/
Connections.csv
connections*.json
config/notify/
*.local.yml
```

The LinkedIn entries go in now, ten milestones early, because `Connections.csv` in the
working directory is the single most likely accidental commit in this project — and the
window opens the moment you're curious enough to download the export.

**Do not gitignore `data/`** if you're keeping local JSON exports or fixtures — the
system's committed state of record is now Postgres (`SPEC.md` §6), not a SQLite file, but
exported JSON fixtures for the dashboard still belong in the repo.

Create `test.yml` alongside the other workflows. It runs lint, tests, and the CRITERIA
check on `pull_request` and `push`, and **must not reference any secret**. `monitor.yml`
and `discover.yml` trigger only on `schedule` and `workflow_dispatch` — never
`pull_request`, and under no circumstances `pull_request_target` (`SECURITY.md §S2`).

### 1.4 Workflow permissions

```yaml
permissions:
  contents: write
concurrency:
  group: monitor
  cancel-in-progress: false
```

Confirm **Settings → Actions → General → Workflow permissions** allows read-and-write. The
concurrency group costs nothing to keep even though the SQLite-corruption risk it
originally guarded against mostly evaporates once state lives in transactional Postgres
(`SPEC.md` §6, §15).

### 1.5 Keepalive

Check out and push with `KEEPALIVE_PAT` rather than `GITHUB_TOKEN`, so state commits are
attributed to your account. Bot commits are widely reported not to reset the inactivity
timer; user commits do. Community lore, not documented behaviour — a mitigation, not a
guarantee, which is why the dead-man's switch exists.

---

## 2. Environment

```
Python 3.13
httpx                # HTTP client
pytest               # tests
selectolax or lxml   # HTML parsing
PyYAML               # config files
psycopg or asyncpg   # Postgres client (SPEC.md §6)
```

Everything else is stdlib. No ORM, no web framework, no scheduler library.

Install from a **hash-pinned lockfile** (`uv.lock`, or `pip-compile --generate-hashes`)
with `--require-hashes`. Dependencies execute with repo write access and secrets in
scope, so the minimal dependency list is a security control as much as a simplicity one
(`SECURITY.md §S5`). Pin Action SHAs for the same reason.

**The dashboard is a single static HTML file** with vanilla JS fetching
`jobs-recent.json`. No build step, no bundler, no framework — a build step is one more
thing that breaks unattended. (This changes in the platform era per `SPEC.md` §19.2, not
before.)

---

## 3. Foundations — built in M0, painful to retrofit

**`src/http.py`** — single chokepoint; nothing else imports `httpx`. Exponential backoff
on timeout/5xx/connection error; **no retry on 4xx** (a 404 is an answer). Realistic
`User-Agent`. Per-host token bucket, 2–5 req/sec. Returns a result object rather than
raising, so callers never need `try/except` to satisfy principle §3.7. Optional disk cache
for development.

⚠ **Add the fetch guards now, not later** (`SECURITY.md §S6`): cap redirect depth at 5–8,
reject non-`http`/`https` schemes, reject resolved addresses in private, loopback, and
link-local ranges including `169.254.169.254`, enforce a response size cap. **Log every
rejection with the requested URL and resolved address** — a guard that silently drops a
legitimate fetch is indistinguishable from a company having no careers page, and would
corrupt the §8.4 measurement the whole coverage decision rests on.

**`src/db.py`** — schema from `SPEC.md §6`, typed helpers, no ORM, foreign keys on,
**against Postgres, not SQLite** — this is now a pre-leave build item, not a platform-era
one (`SPEC.md` §6, `SETUP-PLATFORM.md` §6). Migrations as an ordered set applied by a real
migration tool (Supabase CLI migrations are the path of least resistance — pick one at M0,
not M6). The schema *will* change mid-build and you do not want to lose a crawl.

**`src/health.py`** — `RunRecorder`: opens a `runs` row, accumulates counters, closes it,
pings healthchecks on success, computes anomalies, exposes `should_fail_run()`, prints the
run summary as final output. A DB connection failure must be one of the conditions that
triggers a non-zero exit (`SPEC.md` §14) — a network dependency is acceptable exactly
because it fails loudly, never silently.

⚠ **Write the summary emitter to take counts only, never objects** (`SECURITY.md §S3`). A
summary function that accepts a profile and formats it is one refactor away from printing
an address into a world-readable log. This is an interface decision, not a check.

**`src/models.py`** — dataclasses for `Company`, `Posting`, `CompTier`, `MappingResult`.
Adapters convert provider JSON into these immediately so provider shapes never leak past
the adapter boundary.

**Also settle in M0: the `jobs-recent.json` export schema**, with a committed fixture.
Even on a single track, it's what lets the dashboard be built and tested without a live
database behind it.

---

## 4. Milestones

Sequential. Estimates are active development time including debugging and review cycles,
excluding all waiting.

### M0 — Skeleton and reliability plumbing
**Model:** Opus 5 · **Plan mode:** yes · **Est:** 5–7h · **Criteria:** C-0.1 – C-0.8

Repo layout, four foundation modules, the JSON export schema and fixture, three workflows
with SHA-pinned actions and the trigger/secret split, PAT-attributed commits, anomaly
check wired to `sys.exit(1)`, dashboard scaffold publishing to Pages, pre-commit hook and
CRITERIA CI check active. **Also this milestone: the Postgres migration and RLS baseline**
(`SPEC.md` §6, `SETUP-PLATFORM.md` §6–§7) — pulled forward from the platform era because
delaying it means retrofitting a schema change onto a committed-SQLite design that's
already in flight. Estimate bumped from the original 4–6h to reflect that.

The monitor workflow should open a run, do nothing, close it, commit state, ping
healthchecks, exit 0.

**Security work here:** trigger split, SHA pinning, explicit `permissions`, fetch guards,
counts-only summary. Criteria C-S.6 – C-S.9, C-S.13, C-S.14.

**C-0.5 is a hard gate. Do not proceed until the dead-man's-switch email arrives.**

---

### M1 — Watchlist ingest and dedupe
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 1–1.5h · **Criteria:** C-1.6 – C-1.8

`config/watchlist.yml` with 20–30 companies whose ATS you already know — this becomes M3's
ground truth, so choose deliberately.

---

### M2 — ATS adapters
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 3–4h · **Criteria:** C-2.1 – C-2.7

**Fetch the API docs linked in `SPEC.md §9` during this milestone.** Do not build from
memory: shapes drift, and Lever's v0 and Getro have no authoritative documentation — which
is why fixtures recorded from live responses are the real contract.

---

### M3 — Mapping cascade and validation
**Model:** Opus 5 · **Plan mode:** yes · **Est:** 6–9h · **Criteria:** C-3.1 – C-3.6
*Highest-risk correctness work. A bug here produces confidently wrong data nobody catches
for two months. Mapping coverage is now the top-line product metric — see `SPEC.md` §8.6.*

**Write validation first, then the cascade that feeds it.** Building the cascade first
tempts you into accepting HTTP 200 as success.

C-3.1 — zero false positives against ground truth — is the real test of the project's core
assumption. Poor coverage on known-good companies is a finding: stop and reassess.

**Open `mapping_review.csv` yourself at the end of this one.** It's the highest-value five
minutes in the build.

---

### M4 — Monitoring loop and seed mode
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 4–5h · **Criteria:** C-4.1 – C-4.8

**End of this milestone is the first genuinely useful state** — a working monitor over
your watchlist. Right after this milestone comes `SPEC.md` §18's measurement gate — seed
a few hundred companies (watchlist + ClimateTechList + ClimateBase orgs) through the full
cascade before doing any further source work.

---

### M5 — Compensation
**Model:** Opus 5 · **Plan mode:** yes · **Est:** 4–5h · **Criteria:** C-5.1 – C-5.8
*Subtle. Wrong code here returns plausible-looking wrong answers for months.*

The filter predicate is the deliverable: *does any single tier satisfy all active
conditions?* One function, used identically by the dashboard. C-5.2 is the test that
matters. Add `observed_at` to `posting_comp_tiers` here if it isn't already in the M0
schema (`SPEC.md` §11.1) — before any comp data is collected, since it's unrecoverable
later.

---

### M6 — Getro (company source, discovery only)
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 2–3h · **Criteria:** C-6.1
*(C-6.2 and C-6.3 are struck in `CRITERIA.md` — Getro no longer has a monitoring role.)*

**One role only: discovery.** The original design gave Getro boards a second job, polling
them directly for postings as a path independent of ATS mapping. `SPEC-REVISION-01`
removed that (`SPEC.md` §5, §7.2) — every posting now comes from a mapped company's own
ATS. This milestone is just: parse `__NEXT_DATA__` from two or three Getro boards, extract
company name and domain, feed them into the same discovery pipeline as the other sources
in `SPEC.md` §7. No posting rows, no `source_path`, no independent monitoring path.

---

### M7 — Coverage sample (decision point)
**Model:** — · **Plan mode:** no · **Est:** 1–2h · **Criteria:** C-7.1 – C-7.4
**Your decision, not Claude's.**

100 Built In Boston companies through the full cascade. Record coverage and failure-reason
distribution, then decide:

- Acceptable → full crawl.
- Mostly `unsupported_ats:{X}` → the fix is an adapter, not better mapping. Check whether
  SmartRecruiters volume justifies its adapter.
- Mostly `js_rendered` / `weak_only` → the fix is mapping.

**Do not skip and do not delegate the interpretation.** 100 requests, and the last cheap
moment to change course before spending the anti-bot budget on 4,000 pages. Also sets the
`SPEC.md` §12.8 payload regime, and doubles as the `SPEC.md` §18 measurement gate if it
wasn't already run after M4.

---

### M8 — Full discovery crawls
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 4–5h · **Criteria:** C-8.1 – C-8.8
**Run attended, before leave begins.**

**Three crawls in this milestone**, in ascending order of risk:

1. **Greentown member directory** (~307 companies, 6 category URLs, `SPEC.md` §7.9).
   Smallest and safest — do it first as a warm-up that validates the crawler shape before
   the larger jobs.
2. **ClimateBase organization directory** (~7,250 orgs, `SPEC.md` §7.3).
3. **Built In Boston** (~852 filtered companies, `SPEC.md` §7.4) — largest and highest
   anti-bot exposure, smoke-tested with 20–50 requests first.

After all three, report the **overlap matrix**: how many companies each source
contributed uniquely versus in common with the others. This answers `SPEC.md` §17's
Greentown-overlap question and tells you whether more incubator directories are worth
adding.

End with `--dump-facets` and seed `config/city_aliases.yml` and
`config/function_aliases.yml` from real values. Both start empty; unaliased values appear
as themselves, so this is an improvement pass rather than a blocker.

---

### M9 — Dashboard, filters, RSS
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 8–12h · **Criteria:** C-9.1 – C-9.15

⚠ **Read `SECURITY.md §S1` before the first line of rendering code, and add the CSP meta
tag at the start of this milestone, not the end.** Retrofitting CSP onto a working
dashboard means debugging a blank page with no console error; writing against it from the
outset costs nothing. Criteria C-S.1 – C-S.5.

Write the `location_class` derivation rules **here**, from the M8 facet dump — not earlier
from guesses. `unknown` stays a visible option.

C-9.2 is the specific bug this ordering is designed to catch.

---

### M10 — Notifications
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 3–4h · **Criteria:** C-10.1 – C-10.8

Profiles read from the `NOTIFY_PROFILES` secret and applied generically.
`notifications_sent` guarantees at-most-once per profile, storing profile *name* only. A
Resend failure must not fail the run or lose a posting — it retries next run. Includes the
alert-request button linking to the hosted form.

**Security work:** parsing that never echoes parsed content, name-only references outside
the send call, the no-`@` assertion on the run summary. Criteria C-S.10, C-S.11.

**Test with a throwaway address first.** If seed mode is buggy, this milestone emails
thousands of postings.

---

### M11 — LinkedIn connections
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 2–3h · **Criteria:** C-11.1 – C-11.6

Local-only script reducing `Connections.csv` to `{company: count}`, dashboard upload
control, `localStorage` persistence, card rendering, `company_aliases.yml` for misses.

**Nothing here is ever committed.** The export contains hundreds of other people's
employment data. Gitignore entries are already in place from M-1; verify they work before
running the script. (The browser-side, IndexedDB-backed version of this flow in
`SPEC.md` §19.6 is a platform-era improvement, not part of this milestone.)

---

### M12 — Privacy and security audit, plus breakage tests
**Model:** Sonnet 5 · **Plan mode:** no · **Est:** 4–5h · **Criteria:** C-12.1 – C-12.10

**Audit (~3h):**

1. `git log -p` across all history — any email address anywhere.
2. Read a full Actions run log as an anonymous visitor would.
3. Confirm no connection file in the working tree or history.
4. Read the published dashboard and `/health` logged out.
5. Skim DEVLOG for incidental personal detail.
6. Work through every criterion in the Security block of CRITERIA.md. The M9–M11 checks
   were verified against the code as written then; this verifies them against what
   shipped.

**Breakage tests (~2h) — the part that does not happen naturally:**

1. Rename a board token → company flagged, run continues, appears on health page.
2. Point a discovery source at a dead domain → discovery fails, monitoring unaffected.
3. Force a >25% posting drop → non-zero exit → GitHub email arrives.
4. Disable the schedule for two days → healthchecks email arrives.
5. Force a DB connection failure → non-zero exit → GitHub email arrives (`SPEC.md` §14).

Passive running only proves the system works when nothing goes wrong. It cannot tell you
whether the alert fires when something does — a broken notification path looks identical
to a quiet week, forever. **Do these on any spare evening in the first weeks; don't wait
for a clean two-week window.**

---

## 5. Timeline

**Total: ~45–75 hours, centered near 55.** M3 and M9 are a third of it and carry most of
the variance.

**Wall-clock floors independent of effort:** crawls take 20–40 minutes per pass; the
dead-man's-switch verification needs a grace period to elapse.

**Value accrues as you go — this is not a system that only works when finished.**
M-1 → M4 is roughly 20 hours and produces a working monitor over your watchlist. M10 puts
it in your inbox. M8 widens the company set. Everything after improves something already
running.

**If time is short, the order that ships value fastest is:**

```
M-1 → M0 → M1 → M2 → M3 → M4 → [§18 measurement gate] → M10 → M8      (~27–35h)
```

An unattended monitor emailing new postings across a broad company set. Filtering starts
as title and company only; comp filtering arrives with M5. Then M5, M9, M6, M11 later.
After that, per `SPEC.md` §18's sequencing: the Consider parser and Wellfound company
source (cheap, cold-path), then a three-month live run against real criteria, then YC,
Built In national, and observed comp history — all gated on the measurement gate's
outcome. The platform question (`SPEC.md` §19) waits for November, with data in hand.

Even a partial build running is worth far more than a complete build unstarted.

---

## 6. Things that will go wrong

- **Greenhouse detail-call volume on first real run.** Seed mode must skip detail calls
  entirely.
- **Lever `createdAt` is undocumented.** Missing field → null, never a crash.
- **Ashby compensation is a summary string.** Parse defensively; keep the original;
  degrade rather than raise.
- **Postgres + concurrent runs.** The concurrency group from §1.4 prevents overlapping
  runs from racing each other even though transactions remove most of the corruption risk
  that used to apply to a committed SQLite file.
- **`jobs-recent.json` will grow.** Past ~3MB, shard by month. Not before M7 says so.
- **Timezones.** Store UTC ISO-8601 everywhere.
- **`content_hash` normalization must be stable** or every posting looks like a repost.
  Lowercase, collapse whitespace, strip punctuation, exclude anything that mutates.
- **Cron is UTC with no DST handling.** Times shift when DST ends mid-leave.
- **The first notification run.** Throwaway address first.
- **`Connections.csv` in the working directory** — the most likely accidental commit in
  the project, which is why it's gitignored ten milestones early.
- **CSP added late breaks the dashboard silently.** Inline handlers stop executing with no
  console error in some browsers. Add it first.
- **A blanket "no `@` in stdout" grep is brittle** — a company name or posting URL can
  legitimately contain one. Assert on the **run summary** specifically, which is
  deterministic; treat any wider grep as advisory.
- **Private-IP blocking can reject legitimate fetches** if a CDN resolves oddly. Log the
  URL and resolved address so it's diagnosable rather than a silent miss.
- **Greentown's member pages are paginated** (`/members/page/N/?...`). The category
  filter and pagination combine in the URL; confirm the last page rather than assuming a
  single response contains everything.
- **Greentown alumni companies are still listed.** Capture `status` and keep alumni — a
  company leaving the incubator says nothing about whether it's hiring — but don't treat
  alumni as a `has_open_roles_signal`.

---

## 7. Testing

- **Fixtures, never live calls.** One per provider per scenario.
- **Table-driven tests for comp normalization and the filter predicate** — the only logic
  where a silent bug produces plausible wrong output for months.
- **One integration test** running the pipeline against fixtures into a temp database.
- **A test asserting the run summary contains no `@` character.**
- **The CRITERIA line-preservation check** in `test.yml`.
- Skip crawler tests. They're coupled to markup that will change. The health page covers
  that.

---

## 8. Session prompts

**Starting:**
> Read CLAUDE.md, then the last two DEVLOG entries. Tell me the current milestone, its
> criteria from CRITERIA.md, the recommended model and plan-mode setting, and where we
> left off. Wait for me to confirm.

**When it proposes something rejected:**
> Check SPEC.md §4 before proposing that.

**Before rendering or workflow code:**
> Read SECURITY.md §S1 and §S2 first. Tell me which requirements apply to what we're
> about to write, then start.

**Closing a milestone:**
> Don't show me code. For each criterion, show the command you ran and its actual terminal
> output — not a summary, not "this passes." Paste the real output.
>
> Then tell me: what did you build that ISN'T in SPEC.md? What did you skip? What are you
> least confident about?

**Mid-session decisions:**
> That's a decision that isn't in SPEC.md. Note it for DEVLOG, and tell me whether it also
> changes something SPEC.md currently asserts.

**Reliability check:**
> If this fails at 3am during a scheduled run with nobody watching, what does the user
> see? If the answer is "nothing," that's the bug — fix that first.

**Ending:**
> Append a DEVLOG entry using the BUILD.md §0.4 template and check off the criteria we
> verified.
