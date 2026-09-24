# First Look — Specification

A personal job-search discovery and monitoring tool. Self-contained; assumes no prior
context.

**Read §4 before proposing any design change.** It lists alternatives considered and
deliberately rejected. Do not re-propose them.

**Acceptance criteria live in `CRITERIA.md`.** Lines there are never deleted — only
appended or struck through with a reason.

**Document history.** This file consolidates the original spec with `SPEC-REVISION-01`
(aggregators become company sources), `SPEC-REVISION-02` (platform, accounts, user
state), `first-look-sources-patch.md` (Greentown Labs, Y Combinator), and the SPEC-facing
parts of `first-look-security-patch.md`. All are merged in as of 2026-09-17. The
originals are preserved verbatim in `archive/` — nothing was deleted, only folded into
one current document. See `DEVLOG.md` for the session that did the merge, including one
resolved contradiction between `SPEC-REVISION-01` and `first-look-sources-patch.md` over
Y Combinator (noted at §7.8).

**Two build eras.** Sections 1–18 describe the system being built now — the accelerated,
unattended, pre-parental-leave build (`M-1` → `M12` in `BUILD.md`), running on GitHub
Actions with Postgres storage and a static dashboard. **§19 describes the platform era** —
accounts, alerting, an application tracker, and more — which is deliberately **not** built
yet. Per `SPEC-REVISION-02` §14, only two platform-era items are pulled forward into the
current build because they are unrecoverable or structural later: the Postgres migration
(§6) and the `observed_at` column (§11). Everything else in §19 waits for November, with
three months of live data in hand.

---

## 1. What this builds

1. **Discovers** companies from several sources into one deduped table.
2. **Maps** each to its Applicant Tracking System (ATS) and board token.
3. **Polls** each mapped company's public ATS board API ~4x daily, detecting new,
   changed, and closed postings.
4. **Publishes** to a static filterable dashboard, an RSS feed, and per-user email
   alerts.

All ATS endpoints are public and unauthenticated. No login, no authenticated scraping,
no headless browser.

---

## 2. Users and operating constraints

**Two users** with different criteria, potentially a few more later. No user's criteria
appear in pipeline *code*: dashboard filters are client-side, notification criteria live
in an Actions secret (§13).

**This runs from a public repository.** Everything committed is world-readable, and so
are Actions run logs. See §15 for what that permits and forbids.

**The primary user begins two months of parental leave in mid-September 2026.** Nobody
will monitor, debug, or notice failures during that window:

- A component that fails loudly beats one that degrades quietly.
- A fragile component on a recurring path is worse than one on a one-time path.
- "I ran and found nothing" must be unambiguously distinct from "I stopped running."

**The user checks daily or twice daily and intends to apply as soon as a role opens**,
to be early in the applicant pool. Latency matters; email alerts matter more than the
dashboard.

---

## 3. Design principles

1. **Collect broadly, filter at display time.** No user criterion in pipeline code.
2. **The database is the source of truth for novelty**, not any ATS's date field.
3. **Absence of output must be distinguishable from absence of jobs.**
4. **Fragile components belong on one-time or infrequent paths**, never the polling loop.
   "Fragile" means *fails silently when an upstream party changes something they never
   promised to keep stable* — not simply "external." (§3.10 makes this absolute, not
   approximate, for aggregator postings specifically.)
5. **Store raw, derive on read.**
6. **No classifiers, no taxonomies, no NLP.** Where grouping is needed, use a
   user-editable alias file (§12.4) or data a source already supplies.
7. **No exception escapes a per-company loop.**
8. **Wrong data is worse than missing data.** An unmapped company is a known gap; a
   wrongly-mapped one is invisible bad data nobody catches for two months.
9. **No personal data in the repository, in committed artifacts, or in run logs.**
   Email addresses, contact lists, and anything identifying a third party live in
   secrets or on the user's own machine. This applies to every milestone, not just the
   ones that obviously touch it. Third-party strings (job titles, company names,
   location strings, comp summaries) are untrusted *input* in the security sense too —
   see principle 10 and `SECURITY.md §S1`. **Extended for the platform era**, where
   personal data starts to exist server-side in one tiered, access-controlled place — see
   §19.1.
10. **Only mapped ATS endpoints are polled.** Discovery sources are read on the cold
    path (one-time or monthly) and never on the recurring path, regardless of how
    convenient their postings data looks. An aggregator's postings are someone else's
    product; a company's ATS board is the company's own publication. This is the line
    that keeps the system both unattended-safe and defensible. *(Added by
    `SPEC-REVISION-01` §R1. No existing principle was removed; §3.4 is now enforced
    absolutely rather than as a preference.)*

---

## 4. Rejected alternatives — do not propose these

| Rejected | Why |
|---|---|
| OAuth sign-in, user accounts, a server-side backend | Requires a database, sessions, and a non-Pages deploy target; unwinds every static-hosting decision at once and replaces a cron job with a service to maintain. Solves a problem that starts at ~20 users, not 2–5. **This rejection is stale, not wrong** (`SPEC-REVISION-02` §2.1): three problems in 2024, one managed service (Supabase) in 2026. Recorded here as superseded, not as an error — see §19.2. |
| A "mission-driven" classifier or scoring field | Irreducibly subjective; guesswork presented as data. The user reviews postings by eye. |
| A preference-tier system encoded as a stored field | Same reason, and incompatible with multiple users holding different preferences. |
| A weighted ranking score | Output is already filtered to "new." Sort by date. |
| Workday adapter | Real endpoint, worst effort-to-yield available: POST bodies, hard 20-item pagination silently returning empty above the cap, a second request per job for a date, Akamai bot management — aimed at enterprises, not growth-stage companies. Backlog only. |
| Workable, Recruitee, Personio adapters | SMB / agency / DACH-European skew. Personio is XML-only. Near-zero expected yield. Rejections stand, but their stakes have changed — see §8's mapping-coverage note. Revisit only against a measured `unsupported_ats:{name}` distribution, never on principle. **Measured 2026-09-22** (`spikes/ats_platform_census.py`, 1,668 careers pages across the VC-discovered portfolio — one discovery source, not yet the full §18 seed): Workable 42 companies, second-largest unpollable platform found after Rippling's 62; Recruitee 5; Personio 11. Workable's rejection rested specifically on "near-zero expected yield" — this measurement contradicts that premise. Recruitee and Personio are not disturbed by it; Personio's separate XML-only objection is untouched. Not re-proposed here — §4 is the do-not-re-propose list, and building an adapter remains the user's call — recorded because this row itself asks for exactly this distribution before revisiting. **Workable and Personio reopened 2026-09-24, user's explicit call, folded into M2.** Workable: this row's own "near-zero expected yield" premise is the part the 2026-09-22 measurement contradicts. Personio: a live spot-check of `nexwafe`'s documented `/xml` path returned a client-rendered shell, not XML (`spikes/ats_integration_backlog.md`) — the XML-only characterization is being re-verified against a fresh sample during M2, not assumed correct. **Recruitee is not reopened** — smallest measured count of the three (5), rejection stands as written above. |
| `jobs.climatebase.org` GraphQL reverse-engineering | ClimateBase supplies only a climate flag, available from the plain-HTML org directory. **Reasoning strengthened, not weakened** (`SPEC-REVISION-01` §R2): job detail pages on `jobs.climatebase.org` carry `meta-robots: noindex`, a deliberate do-not-aggregate signal. The org directory (§7.3) remains in scope and is unaffected. |
| ~~Wellfound automation~~ | ~~No public API; value behind a login wall; a warmed session is unacceptable maintenance.~~ **Struck 2026-09: factually wrong.** `wellfound.com/role/{role}`, `/role/r/{role}` (remote), and `/role/l/{role}/{city}` are public, server-rendered, `?page=N` paginated, no cookie, and carry salary range, equity range, remote policy, company size, stage, and stable numeric job URLs. What is behind the login is *arbitrary filtering and applying*, not the listings. The rejection generalised a property of the filter UI to the whole source. Replaced by acceptance as a company source — see §7.8. |
| A circuit breaker disabling a source for N days | One request per company per run. No hammering to prevent. |
| Normalizing the raw location string | `location_raw` is verbatim. A narrow derived classification is permitted (§12.3) but never overwrites it. |
| Scraping LinkedIn, or using any LinkedIn API for connection data | The connection graph isn't exposed by their APIs, and scraping is against their terms and actively defended. §12.6 achieves the goal without it. **Non-negotiable permanently, including in the platform era** (`SPEC-REVISION-01` §R2): this stays client-side forever, even once a database exists. |
| Storing notify profiles or connection data in the repo | Public repo. See §13.1 and §12.6. |
| Headless browsers anywhere | Every source in scope is reachable with plain HTTP. |
| Any aggregator's postings on the recurring polling loop | §3.10. Puts a fragile, undocumented, unilaterally-changeable parser on the recurring path, where a silent break is indistinguishable from a quiet week for two months. (`SPEC-REVISION-01` §R2) |
| Republishing aggregator-sourced postings in the dashboard, RSS, or email | Not our data. The ATS-sourced version of the same posting is available and is the employer's own publication. (`SPEC-REVISION-01` §R2) |
| Wellfound, YC, Built In, ClimateTechList, or Consider as *posting* sources | Same as above. All are accepted as **company** sources only (§7.4–§7.9). (`SPEC-REVISION-01` §R2) |
| Consider-powered job boards (e.g. `jobs.greentownlabs.com`) as a monitoring source | Client-rendered SPA requiring endpoint reverse-engineering, yielding thinner data than polling the same companies' ATSes directly — same reasoning that cut the ClimateBase jobs SPA. Consider is used for company discovery only (§7.6). (`first-look-sources-patch.md`) |
| Moving the LinkedIn connections feature (§12.6) server-side once a database exists | The export contains hundreds of other people's employment data. This stays client-side permanently, including in any future platform version. Non-negotiable. (`SPEC-REVISION-01` §R2) |

**Deferred pending measurement, not rejected:** SmartRecruiters. A plain documented
unauthenticated GET, roughly as simple as Greenhouse — the effort argument ruling out the
others doesn't apply. Included in **detection** from day one (§9); the polling adapter is
written only if the count justifies it (§18). **Measured 2026-09-22:** 1 company out of
1,668 careers pages in the VC-discovered portfolio (`spikes/ats_platform_census.py`) —
one discovery source, not the full §18 seed. The volume this deferral is waiting on has
not shown up yet; on this evidence alone the adapter stays unwritten.

**A note on Y Combinator, since two documents disagreed.** `first-look-sources-patch.md`
independently proposed rejecting `workatastartup.com` as account-gated, using the same
reasoning the original spec used to reject Wellfound — reasoning `SPEC-REVISION-01`
subsequently found factually wrong for Wellfound. Rather than assume it also holds for
YC, this spec follows `SPEC-REVISION-01` and accepts YC as a company source (§7.8),
pending a fresh look during discovery work. If YC turns out to actually be account-gated
on inspection, strike this row properly with the evidence, the way Wellfound's rejection
was struck above — don't just quietly drop it.

---

## 5. Architecture

```
DISCOVERY          one-time before leave; monthly after
  Manual watchlist · Getro VC boards · ClimateBase orgs · Built In
  ClimateTechList · Consider boards · Wellfound · YC · Greentown Labs
        │  dedupe on canonical_domain
        ▼
ATS MAPPING        one-time per company; retried monthly on failure
  slug guess → apply-redirect → careers-page regex → classified failure
        ▼
MONITORING         ~4x daily, GitHub Actions — ATS ONLY
  Greenhouse · Lever · Ashby  [· SmartRecruiters, pending §18]
        ▼
OUTPUT
  Dashboard + health page (Pages) · RSS · email alerts
```

**Getro is no longer on the monitoring side.** The original design polled Getro boards
directly as an independent postings path, needing no ATS mapping. `SPEC-REVISION-01` §R0
removed that: every aggregator, Getro included, is now a **company source only**.
Nothing but a mapped company's own ATS endpoint appears on the polling loop. This was not
a scope expansion — applied fully, it makes the system smaller and removes the one
fragile component that lived on the recurring path.

**What that decision buys:** no fragile component on the recurring path (§3.4 holds
absolutely); no republishing of another aggregator's listings — the data published is
what the employer's own ATS publishes, for the purpose the employer published it for; a
simpler posting lifecycle (§10) with one source path instead of two.

**What it costs, named explicitly because it is a real loss:** the Getro independent path
was a hedge covering companies whose ATS mapping failed. That hedge is gone. **An
unmapped company is now invisible, full stop.** Mapping coverage stops being an open
question and becomes the top-line product metric — see §8 and §18.

**Two independent workflows**, plus a third with no secrets, plus two more that only ever
run by hand. `migrate.yml` (added at M0) applies the §6 migrations and triggers on
`workflow_dispatch` **only** — it cannot live in secrets-free `test.yml`, and
auto-applying a schema change on every push to `main` during an unattended leave is
exactly the class of quiet risk §3.3 exists to prevent. `watchlist.yml` (added at M1)
ingests `config/watchlist.yml` into `companies` and carries the same posture: manual only,
so a person presses the button each time the watchlist gains new entries rather than a
seeding step running unattended. `monitor.yml` (~4x daily)
and `discover.yml` (manual/monthly) carry secrets and never trigger on `pull_request`. A
third workflow, `test.yml`, runs lint and tests **with no secrets in scope** — a security
boundary, not an organisational one (`SECURITY.md §S2`). **It triggers on `push` and
`workflow_dispatch`, not on `pull_request`** (settled at M0): `CRITERIA.md` C-S.6 forbids
*any* workflow from triggering on `pull_request`, and `BUILD.md` §0.3 rejected pull
requests outright in favour of committing straight to `main` — so a PR trigger would be
dead configuration that only widens the C-S.6 surface. The secrets-free property is what
matters and is unchanged. A crash in
fragile discovery code must not take down monitoring. All five carry `workflow_dispatch`
where relevant.

Cron is UTC and has no DST handling — wall-clock times shift by an hour when DST ends
mid-leave. Expected, not a bug.

**Compute is unchanged for the platform era.** GitHub Actions keeps polling and keeps
writing even after the Postgres migration (§6) and, later, after the read layer moves to
Next.js (§19.2). The pipeline does not change; only where it writes to does.

---

## 6. Data model

**Postgres from the start, not committed SQLite.** The original design committed a SQLite
file each run for versioned, revertible state "for free." `SPEC-REVISION-02` §3.1
supersedes that, and — unlike most of that revision — **this is a pre-leave build item**,
not a platform-era deferral: git does not delta-compress binaries, so a ~30MB DB committed
4x/day is roughly 120MB of repo growth daily, a gigabyte inside a month at 2,000
companies, during the exact unattended window nobody is watching disk usage. See
`SETUP-PLATFORM.md` for the Supabase setup steps and migration order.

**Why the network dependency is acceptable.** A DB outage fails the run, which exits
non-zero, which emails (§14). That is a *loud* failure — precisely what §3.3 asks for.
The criterion was never zero dependencies, it was no *silent* ones.

**The DDL below is Postgres-shaped as of M0.** Earlier drafts of this section carried
SQLite-flavoured types — `INTEGER PRIMARY KEY`, `TEXT` timestamps, `INTEGER` booleans —
left over from the committed-SQLite design this section supersedes. They are now written as
`BIGINT GENERATED ALWAYS AS IDENTITY`, `TIMESTAMPTZ`, `BOOLEAN`, and `JSONB`. This is not
cosmetic: archiving by `closed_at`, the 30-day hot/cold split, and §12.2's "Posted within N
days" filter are all interval arithmetic, which `TEXT` cannot do. `ON DELETE CASCADE` is
added on the child tables so `canonical_domain`'s manual merge hatch (below) doesn't leave
orphans — companies are still **never auto-removed** (§14); the cascade exists for
deliberate merges only. Timestamps are still stored as UTC.

**Accepted costs of the move:**
- Loss of `git checkout` on state. Managed backups only partly cover it; free-tier
  retention is short.
- **Migration discipline from M0.** "Delete the file and re-seed" stops being the answer.
  Expect several schema changes early — §12.3 and §12.4 are explicitly designed to be
  written after seeing real facet data. Pick a migration tool at M0, not M6
  (`SETUP-PLATFORM.md` §6).
- The concurrency group below still guards against overlapping runs; with transactions
  the corruption risk it originally guarded against mostly evaporates, but it costs
  nothing to keep.

**New unattended risk, replacing the old committed-SQLite risk:** Supabase pauses
Free-Plan projects after a period of low activity; paid projects are not paused. A 4x/day
poller keeps a project alive trivially, but the pause only bites if the monitor is
*already* dead for a week — exactly the parental-leave scenario. **Pay for Supabase Pro
across the leave months.** Verify current pause, backup, and Data API grant policies
directly before relying on this description; these terms change, and an explicit Postgres
grants requirement for the Data API is scheduled to roll out to existing projects from
2026-10-30.

```sql
CREATE TABLE companies (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  canonical_domain          TEXT UNIQUE,
  name                      TEXT NOT NULL,
  is_climate                BOOLEAN NOT NULL DEFAULT FALSE,
  industry_tags             JSONB,           -- raw array; a lookup, not a classifier (§3.6)
  has_open_roles_signal     BOOLEAN NOT NULL DEFAULT FALSE,
  ats_provider              TEXT,
  ats_token                 TEXT,
  ats_status                TEXT NOT NULL DEFAULT 'unmapped',  -- unmapped|ok|failing|unmappable
  mapping_confidence        TEXT,            -- verified|probable|weak
  mapping_method            TEXT,
  mapping_failure_reason    TEXT,            -- §8.4
  mapping_last_attempt_at   TIMESTAMPTZ,
  ats_last_success_at       TIMESTAMPTZ,
  ats_consecutive_failures  INTEGER NOT NULL DEFAULT 0,
  last_nonzero_postings_at  TIMESTAMPTZ,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE company_sources (
  company_id            BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  source                TEXT NOT NULL,
  -- builtin | climatebase | climatetechlist | getro | consider
  -- | wellfound | yc | greentown | manual
  source_id             TEXT,
  source_metadata_json  JSONB,
  PRIMARY KEY (company_id, source)
);
```

`companies.is_climate` is unchanged in shape but now has **more than one independent
source** (ClimateBase orgs, ClimateTechList, Greentown Labs membership). Multiple sources
agreeing is a stronger flag than one; appearing in only one is still a flag. This remains
a lookup, not a classifier — principle §3.6 holds.

```sql
CREATE TABLE postings (
  id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  company_id             BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  ats_job_id             TEXT NOT NULL,
  title_raw              TEXT NOT NULL,
  department_raw         TEXT,
  location_raw           TEXT,            -- verbatim, never overwritten
  workplace_type_raw     TEXT,            -- Ashby's structured field
  location_class         TEXT,            -- derived §12.3: remote|hybrid|onsite|unknown
  city_raw               TEXT,            -- first comma-token of location_raw
  url                    TEXT,
  first_seen_at          TIMESTAMPTZ NOT NULL,  -- THE date: sort key and "Posted" filter
  last_seen_at           TIMESTAMPTZ NOT NULL,
  closed_at              TIMESTAMPTZ,
  posted_at              TIMESTAMPTZ,     -- ATS date, informational only
  content_hash           TEXT,
  is_repost              BOOLEAN NOT NULL DEFAULT FALSE,
  comp_data_quality      TEXT NOT NULL DEFAULT 'none',
  comp_raw_summary       TEXT,
  comp_best_annual_usd   INTEGER,         -- normalized, whole USD per year
  comp_floor_annual_usd  INTEGER,
  comp_tier_count        INTEGER NOT NULL DEFAULT 0,
  UNIQUE (company_id, ats_job_id)
) WITH (fillfactor = 85);   -- keeps the daily last_seen_at update HOT, per below
```

**`source_path` (`'ats' | 'getro'`) has been removed from this table**
(`SPEC-REVISION-01` §R4). Every row is now ATS-sourced; a column with one possible value
is noise that invites someone to add a second value later. If you find this column in an
old draft or a stale fixture, it predates the R0 architecture change.

```sql
CREATE TABLE posting_comp_tiers (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  posting_id   BIGINT NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
  tier_label   TEXT,
  min_amount   NUMERIC,         -- as published; an hourly rate is not a whole number
  max_amount   NUMERIC,
  currency     TEXT,
  period       TEXT,            -- year|month|week|hour
  observed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
      -- added by SPEC-REVISION-02 §4, pre-leave item — see §11
);

CREATE TABLE runs (
  id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  started_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at          TIMESTAMPTZ,
  companies_polled     INTEGER NOT NULL DEFAULT 0,
  http_ok              INTEGER NOT NULL DEFAULT 0,
  http_err             INTEGER NOT NULL DEFAULT 0,
  total_live_postings  INTEGER NOT NULL DEFAULT 0,
  new_postings         INTEGER NOT NULL DEFAULT 0,
  ok                   BOOLEAN NOT NULL DEFAULT true  -- added M0, post-launch:
                       -- this run's own anomaly verdict at close time. Without
                       -- it, a run that finishes but trips an anomaly (§14) is
                       -- indistinguishable from a clean one to any later query,
                       -- which a live C-0.6 test on 2026-09-23 demonstrated
                       -- directly -- the dashboard's "last successful run"
                       -- read a run that had just failed as its most recent
                       -- success. §12.1's stale-banner rule ("last run failed
                       -- OR is over 48h old") needs this column to check the
                       -- first half at all.
);

CREATE TABLE notifications_sent (
  posting_id   BIGINT NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
  profile      TEXT NOT NULL,   -- profile NAME only, never an email address
  sent_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (posting_id, profile)
);
```

**`notifications_sent.profile` stores a short name, never an address.** This table lives
in a database that, per §15, is no longer git-committed to the public repo, but the rule
predates that change and stays: never store an address here regardless of where the table
lives.

**`canonical_domain`:** lowercase, strip protocol, `www.`, path, query params. Needs a
null-domain fallback (normalized name, flagged) and a manual merge hatch.

**Discovery sources vary widely in whether they hand back a usable domain at all.**
Consider does, directly, on every record (§7.6). Getro does not — only a slug plus a
job's external application URL, which is often a third-party ATS subdomain rather than
the company's own site (§7.2), same class of problem Wellfound already has a budgeted
resolution hop for (§7.7). Check this per source rather than assuming any of them behave
like the others.

**`first_seen_at` is the canonical date** for sorting and the "Posted" filter.
`posted_at` is unreliable — ~~Greenhouse's list endpoint exposes only `updated_at`, which
mutates on any edit~~ **(corrected 2026-09-22: the list endpoint carries `first_published`
too — see §9 — but `posted_at` stays informational regardless, because Lever's `createdAt`
runs years stale on live postings)**. The UI says **"Found 6h ago"**, which is what the
number means.

A live example of why this column exists, caught 2026-09-22 between two runs eight
minutes apart: a Greenhouse posting with `first_published` of 2026-09-10 appeared on its
board for the first time in the later run, `updated_at` two minutes earlier. Sorted by
`posted_at` it lands twelve days deep and is never seen; sorted by `first_seen_at` it is
correctly the newest thing on the board. The whole "be early in the applicant pool"
premise (§2) depends on this specific choice.

**Do not add a table for observed compensation history.** It is derivable from `postings`
and `posting_comp_tiers` by company (`SPEC-REVISION-01` §R4). Store raw, derive on read —
see §11.

**Write amplification and the hot/cold split** (both pre-leave items, `SPEC-REVISION-02`
§3.2–§3.3):

The original design updated `last_seen_at` on every still-present posting, every run. At
scale that is enormous write amplification for no benefit — closure detection needs
same-day accuracy, not six-hour precision.

1. **Update `last_seen_at` once per day**, not on all four runs. New postings still
   insert on every run — that is where latency matters and it is unaffected.
2. **Never index `last_seen_at`. Set `fillfactor` ~85** on `postings` so updates stay HOT.
3. If bloat persists, move the column to `posting_liveness(posting_id, last_seen_at)`.

**Budget: ~500k posting rows per 500MB.** ~450 bytes heap + ~300 index ≈ 800 bytes; round
to 1KB for bloat headroom. Rows scale with churn, not poll frequency — a still-present
posting is an update, not an insert.

- `postings` — open, plus closed <30 days. Fully indexed. Serves the dashboard.
- `postings_archive` — closed ≥30 days. Drop `url` (dead link) and `content_hash`. One
  index, `(company_id, department_raw)`. ~350 bytes/row.

**Archive by `closed_at`, never by `first_seen_at`.** A role open 60 days is still
applicable; archiving by posting date would hide live jobs. The 30-day rule aligns with
§12.2's "Posted" ceiling, so the hot table is close to exactly what the dashboard serves.

**Repost detection breaks silently against a 30-day archive window.** The original design
matched `content_hash` against postings closed within ~90 days; a 30-day archive move
would quietly stop that from working past 30 days. Add:

```sql
CREATE TABLE posting_hashes (
  content_hash  TEXT NOT NULL,
  company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  closed_at     TIMESTAMPTZ,
  PRIMARY KEY (content_hash, company_id)
);
```

This table outlives the archive move and is cheaper than indexing `content_hash` on the
archive directly.

**Never archive a posting with a dependent user row** — a save or an application, once
those exist in the platform era (§19). A shortlist that degrades to a dead link and half a
card reads as a bug. `postings_archive` rows are never purged for any posting with a
dependent user row — write this down now, because otherwise someone later adds a cleanup
job and quietly breaks a user's history.

**`posting_comp_tiers` rows are never dropped or trimmed.** They are the asset (§11).

**Descriptions are available and deliberately discarded.** Greenhouse (`content=true`),
Lever (`description`), Ashby (`descriptionHtml`) all expose full descriptions. Keeping
them makes a row 5–8KB; at scale that is most of a free-tier budget spent on text nobody
may ever read. This is why cards link out (§12.5) instead of rendering descriptions
inline. Two distinct *future* features would want description text back, with opposite
retention rules — noted here so they aren't conflated later:

| | Purpose | Retention |
|---|---|---|
| **Display cache** | Expandable drawer on a card | Fetch on demand via a server proxy (CORS blocks direct browser calls); cache ~7 days; scales with *attention*, not corpus |
| **Sampled archive** | Requirement drift by title/location over time | A few hundred per title cluster per quarter, retained permanently; tens of MB/year |

Description text is the employer's copyrighted content. Fetching one on request for
display sits differently from building a searchable archive of everyone's job
descriptions — be deliberate about which of these two you're building, if either.

---

## 7. Discovery sources

Each yields `(name, domain, source_id, raw_metadata)`. Dedupe on `canonical_domain`.
Appearing in multiple sources is a mild positive signal.

**Source selection is not user filtering.** Choosing which companies to discover — Built
In's 11–1000 employee band, Greentown's current members, whether to crawl the full YC
directory — is a sourcing decision about where to spend crawl and mapping budget. It is
distinct from principle §3.1, which forbids *user criteria* (compensation, role,
location, seniority) from appearing in pipeline code. Those still live exclusively in the
dashboard and notification profiles.

### 7.1 Manual watchlist
`config/watchlist.yml`, name + domain. Highest signal per unit of effort. Committed —
acceptable, it's a list of companies.

### 7.2 Getro / VC portfolio boards — discovery only
`config/getro_boards.yml`, ~10–15 climate and energy VC boards (Energy Impact Partners,
Congruent, Powerhouse, Breakthrough Energy Ventures, Elemental Excelerator).

Next.js apps: data lives in the `__NEXT_DATA__` JSON of the server response. Parse
directly. Shape is community-derived, not documented — verify against two or three
boards first. **Confirmed live on one board** (`breakthroughenergy.getro.com/jobs`,
2026-09-20): classic Next.js Pages Router, `__NEXT_DATA__` present, job data at
`props.pageProps.initialState.jobs.found`, each entry carrying a nested
`organization` object (name, slug, id, `industryTags`, `headCount`, `stage`). **Shape
is not universal, though** — a second, unconfirmed candidate board
(`jobs.a16z.com`) turned out to run Next.js App Router with a streamed RSC payload
instead of a `__NEXT_DATA__` script tag, and wasn't even confirmed to actually be
Getro under the hood. Verify each real board in `config/getro_boards.yml`
individually rather than assuming one shape fits all.

**Company source only, not a monitoring path.** The original design gave Getro a second
role: polling its boards directly for postings, as a path independent of ATS mapping.
`SPEC-REVISION-01` §R0/§R5 removed that role entirely — see §5 for why. Getro's board
pages still yield company names via `__NEXT_DATA__`; nothing else about this source
changes. If you see references to a `getro` posting path or a `source_path` column
elsewhere, they are stale — see §6.

**Domain resolution gap, confirmed 2026-09-20, not yet solved.** Getro does *not*
expose a company's own domain directly — only a slug, plus each job's external
application URL, whose host is usually a *third-party ATS's* subdomain
(`renewco2.breezy.hr`, `rift.recruitee.com`, `carbonengineering.applytojob.com`), not
the company's own site. `canonical_domain` dedupe (§6) needs a real domain, and this
source can't reliably supply one on its own. This needs a resolution hop — same shape
as the one §7.7 already budgets for Wellfound (an extra request per new company,
cold-path, so the cost is acceptable), just not currently written into the pipeline for
Getro. Add it once this holds up across more than the one board sampled so far.
**Contrast with §7.6**: Consider doesn't have this problem at all.

### 7.3 ClimateBase organization directory
`climatebase.org/organizations`, ~7,250 orgs, server-rendered, one-time crawl. **Sole
purpose: `is_climate` and sector tags.** Do not touch `jobs.climatebase.org` — see §4 for
why, including the strengthened `noindex` evidence.

### 7.4 Built In Boston
`builtinboston.com/companies`, server-rendered, plain GET. ~4,106 companies; ~852
filtered to 11–1000 employees with open roles.

- **Crawl into our own DB**, store raw fields, re-filter locally.
- **Do not filter to `location/fully-remote` at the source.** Office type is a
  company-level label; remote-ness is job-level. A Boston-HQ'd "Hybrid" company still
  posts remote roles.
- Capture: name, slug, `companyId`, external website URL, industry tags, employee count,
  year founded, office type, hiring-now flag (→ `has_open_roles_signal`), blurb.

Largest crawl, most anti-bot exposure. Run once, attended, before leave. Smoke-test 20–50
requests. Checkpoint so a killed run resumes.

**National (`builtin.com`, ~100k companies) is deferred behind the §18 measurement
gate.** The crawl is tractable; whether the mapping cascade holds up at that volume is
not yet known. If cascade coverage is low, the correct response is better mapping, not a
bigger crawl. Boston first. Re-evaluate with a real coverage number in hand
(`SPEC-REVISION-01` §R5).

### 7.5 ClimateTechList
`climatetechlist.com`. ~400+ climate companies, aggregating 8,000+ postings daily from
individual company job boards. **Primary climate company seed.**

Its company list is already filtered to *climate companies that run a pollable board* —
the exact population this system wants, curated by someone maintaining it full-time.
Crawlable company directory indexes into per-company profile pages; take name, domain,
and sector, nothing else.

**Ask first.** They explicitly invite data partnership enquiries. A company-list request
costs one email and removes the entire question of whether this is acceptable use. Do
this before crawling, not after.

Note honestly: this is also the closest thing to a competitor. Both facts are true and
neither should be hidden from them. (`SPEC-REVISION-01` §R5)

### 7.6 Consider
`consider.com` — a board platform, not a single board. Confirmed in use at
`jobs.greentownlabs.com` (307 companies, 578 jobs).

**Endpoint confirmed 2026-09-20**, found via a real browser devtools session (guessing
REST paths from the terminal got nowhere, including one false lead — a `/graphql` path
that returned HTTP 200 but was just the SPA's client-side-router catch-all shell, not a
real API):

```
GET  https://jobs.{board}.com/jobs                 # any page on the board; embeds
                                                     # window.serverInitialData, which
                                                     # contains a session-scoped
                                                     # csrfToken and the board id
POST https://jobs.{board}.com/api-boards/search-jobs
     Cookie: <the session cookie set by the GET above>
     x-csrf-token: <csrfToken from serverInitialData>
     body: {"meta": {"size": N},
            "board": {"id": "<board-id>", "isParent": true},
            "query": {"promoteFeatured": true}}
```

Confirmed reproducible headlessly (no browser needed at request time) — GET once for a
session + token, then POST. **Company source only** — see §4 for why Consider is never
used for monitoring; the fields below are for discovery, not for storing as postings.

**Better than Getro for domain resolution.** Unlike Getro (§7.2), every job record
carries `companyDomain` directly (`energydome.com`, `lydianlabs.com`,
`americanbatterytechnology.com`, confirmed 5/5 on a live sample) — no resolution hop
needed at all. This makes Consider a stronger company-discovery source than "one parser
unlocks many boards" alone implied; worth weighing that when deciding which boards
beyond Greentown Labs are worth adding.

**Ignore Consider's own inferred fields.** The response also includes `scores` (a
proprietary relevance/match/age/richness score), `skills` / `requiredSkills` /
`preferredSkills` (resume-matching tags), `considerLevels` (inferred seniority ranges),
and `matchingTalent` — all Consider's own derived output, not anything the employer
wrote. **Never store or surface these.** They're exactly the scoring/classifier
category §4 already rejects building ourselves; the fact that a third party computed it
for free doesn't change that.

One parser unlocks many accelerator and VC boards, same leverage pattern as Getro.
Greentown Labs is the first board to add. (`SPEC-REVISION-01` §R5)

**Built 2026-09-24** (`src/consider.py`, `config/consider_boards.yml`, `CRITERIA.md`
C-6.4), ahead of §18's original sequencing — see BUILD.md's M6 section and §18 for why.
Pagination via `meta.sequence` confirmed working at the job level (zero duplicate
`jobId`s across pages); bounded by `MAX_PAGES` (`src/consider.py`), so a board larger
than `MAX_PAGES × PAGE_SIZE` jobs will not have every company discovered in one run —
recorded as a known limitation, not solved here. 4 boards confirmed live and committed to
`config/consider_boards.yml`: Greentown Labs, Congruent Ventures, Bessemer Venture
Partners, MCJ Collective.

### 7.7 Wellfound
`wellfound.com/role/{role}`, `/role/r/{role}`, `/role/l/{role}/{city}`. Public,
server-rendered, `?page=N`. Next.js — check for `__NEXT_DATA__` before parsing HTML.

**Take company name and Wellfound slug only.** Listings carry salary and equity; do not
store or display them. Under §3.10 that data comes from the company's own ATS, and
taking it here is exactly the republishing §4 rejects.

Known gap: listings expose a Wellfound company slug, not a domain. `canonical_domain`
dedupe requires a second hop to `wellfound.com/company/{slug}`. Budget one extra request
per new company; this is cold-path work, so cost is acceptable.

This source was originally rejected as unautomatable — struck in §4 once that turned out
to be wrong. (`SPEC-REVISION-01` §R5)

### 7.8 Y Combinator
`workatastartup.com/jobs` returns listing data to an anonymous fetch — verified.
React-rendered, so expect an embedded JSON blob rather than parseable markup. The YC
company directory is separately Algolia-backed.

Company source only. Lowest urgency of the sources in this section — YC skews
early-stage and engineering-heavy relative to the target profile. (`SPEC-REVISION-01`
§R5)

**See the note at the end of §4** — a second, independent patch (`first-look-sources-patch.md`)
proposed rejecting YC on grounds this spec's authors had already found unreliable for a
near-identical source (Wellfound). This spec follows `SPEC-REVISION-01` and keeps YC in
scope, but flags it for a fresh look during discovery work rather than treating either
document as automatically right.

### 7.9 Greentown Labs member directory
`greentownlabs.com/members/?hq=all&cat={category}&status=current` — roughly 307 member
companies, WordPress, server-rendered, plain GET. One-time crawl.

Categories, each crawled separately: `agtech-water`, `buildings`, `electricity`,
`manufacturing`, `resiliency-adaptation`, `transportation`.

**Discovery only.** Sets `is_climate = 1` — incubator membership is a lookup, not a
judgment, on the same basis as ClimateBase directory membership — and supplies the
category as `industry_tags`. These categories are cleaner and more specific than Built
In's generic industry tags.

Also capture `status` (current vs. alumni). Current members are more likely to be
actively hiring, which feeds `has_open_roles_signal` as a weak positive. Alumni are still
listed and still kept — a company leaving the incubator says nothing about whether it's
hiring — but alumni status does not itself set `has_open_roles_signal`.

**Density and overlap.** Heavy Somerville/Boston and Houston concentration, which maps
directly onto the climate-remote and climate-Boston cases. Expect meaningful overlap with
ClimateBase and Built In Boston; `canonical_domain` dedupe handles it, and multi-source
appearance is a mild positive signal per this section's intro.

**Note: the Greentown jobs board itself (`jobs.greentownlabs.com`) is not used.** It runs
on Consider, a client-rendered aggregator — see §7.6 and §4. (`first-look-sources-patch.md`)

### 7.10 Wellfound — historical note

The heading `7.10` is intentionally absent. The original spec had a "Wellfound — not
automated" section here describing it as manual-only; that section's content is now
folded into §7.7 above, and the rejection it was based on is struck in §4. Left as a note
rather than silently vanishing, per this project's convention of not deleting content
without saying so.

---

## 8. ATS mapping

### 8.1 Cascade
Four stages, first *validated* success wins. **Stage 3 is the workhorse, not stage 1.**
Slug guessing exists because it's free when it works; don't optimize it at stage 3's
expense.

1. **Slug guessing.** Candidates from company name (lowercase, strip punctuation and
   whitespace, strip trailing `Inc`/`Labs`/`Technologies`/`AI`) and from the
   second-level label of `canonical_domain` — the domain candidate hits noticeably more
   often. Try against Greenhouse, Lever, Ashby, SmartRecruiters.
2. **Apply-redirect.** Built In postings link to
   `builtinboston.com/job/{slug}/{id}?handler=ApplyRedirect`. Follow redirects; parse the
   resolved domain.
3. **Careers-page regex.** Fetch the careers page; match raw HTML for `greenhouse.io`,
   `lever.co`, `ashbyhq.com`, `smartrecruiters.com`. Also capture *any other*
   recognizable ATS domain, including unsupported ones — §8.4.
4. **Classified failure**, never a silent drop.

### 8.2 Validation — three confidence levels

HTTP 200 is not evidence. A common-word slug can return a different company's board, and
an unvalidated false positive means silently monitoring the wrong company for months.

| Level | Test |
|---|---|
| `verified` | The company's own careers page references the **same token**. Two independent sources agreeing. |
| `probable` | The ATS response names the company and it fuzzy-matches (Greenhouse `/v1/boards/{token}` returns `name`; Ashby carries the org name). Lever is weak here. |
| `weak` | 200, nothing corroborates. |

**Only `verified` and `probable` enter the polling loop.** `weak` is a mapping failure.
Per §3.8, a known gap beats invisible bad data.

**Negative guard:** candidates under six characters or listed in
`config/collision_words.yml` (`atlas`, `square`, `ramp`, `notion`, `arc`, `level`,
`front`, `scale`) require `verified` and may never be accepted at `probable`.

Log every accepted `(company, provider, token, confidence, method)` to
`data/mapping_review.csv` for a one-time eyeball before the system is left unattended.
A backstop, not the primary control.

### 8.3 Priority
Map `has_open_roles_signal = 1` first. A miss on a company with no open roles costs
nothing, so degradation lands where it matters least.

### 8.4 Failure classification — never a single bucket

| Reason | Meaning | Remedy |
|---|---|---|
| `unsupported_ats:{name}` | Careers page shows an unsupported ATS. Record the name. | Adapter decision — *not* a mapping problem |
| `js_rendered` | No useful raw HTML | Mapping |
| `no_careers_page` | No careers URL resolvable | Data quality |
| `weak_only` | Token found, failed validation | Validation signals |
| `unknown` | Nothing diagnostic | Manual sample |

The distribution *is* the answer to "should we build more adapters." Surfaced on the
health page.

**A fetch guard that silently drops a legitimate request corrupts this measurement.**
`src/http.py`'s SSRF/redirect guards (`SECURITY.md §S6`) must log every rejection with the
requested URL and the resolved address — a rejected-but-legitimate fetch is otherwise
indistinguishable from a company having no careers page, and lands here as `unknown`,
poisoning the one distribution the whole coverage decision rests on.

### 8.5 Retry
Failed mappings retry monthly on the cold path. Failure is not permanent.

### 8.6 Mapping coverage is now the product

Under the original design, a failed mapping was partially covered by the Getro
independent path (§7.2, before `SPEC-REVISION-01` removed it). That path is gone. **An
unmapped company is invisible, full stop.** Consequences:

- Cascade coverage and the failure-reason distribution are promoted from open questions
  to **blocking measurements** — see §18.
- `mapping_review.csv` review before unattended operation is no longer a backstop. It is
  the only control on a silent population gap.
- The adapter question changes character. `unsupported_ats:{name}` no longer reads
  "should we build more adapters" but "what fraction of the climate population am I
  structurally unable to see." SmartRecruiters in particular is now the most likely
  adapter to be justified.

(`SPEC-REVISION-01` §R6)

---

## 9. ATS adapters

Public, unauthenticated. 2–5 req/sec per provider; providers run as parallel jobs.

**Fetch the linked documentation during implementation rather than building from
memory.** Shapes drift, and two sources have no authoritative docs at all — which is why
fixtures recorded from live responses are the real contract.

### Greenhouse — [docs.greenhouse.io/job-board.html](https://docs.greenhouse.io/job-board.html)
```
GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
GET boards-api.greenhouse.io/v1/boards/{token}/jobs/{id}    # detail
GET boards-api.greenhouse.io/v1/boards/{token}               # name, for validation
```
~~List returns only `updated_at`, which mutates on any edit. True `first_published` and
`payInputRanges` come only from the detail endpoint.~~ Department via `departments`.
**Corrected 2026-09-22 against 384 live postings on 8 mapped boards**
(`spikes/iteration7_live_postings_spike.py`):

- `first_published` **is** on the list endpoint, with or without `content=true`.
  `updated_at` is there too and still mutates on any edit, so §6's choice of
  `first_seen_at` as the canonical date is unaffected.
- `departments` is present **only** when `content=true` is passed. The plain list has no
  department field at all, so `content=true` is mandatory rather than optional — which
  also means the description body is fetched on every poll and must be discarded in
  memory (§6).
- **The detail endpoint returned a byte-identical object to the `content=true` list
  entry** — same key set, same values, on 6/6 jobs across two boards. See §10.
- `pay_input_ranges` appeared on **none** of those 384 postings, on either endpoint.
  See §11.

### Lever — [hire.lever.co/developer/documentation](https://hire.lever.co/developer/documentation)
```
GET api.lever.co/v0/postings/{site}?mode=json
```
Full board in one call. **The linked docs cover the authenticated v1 Data API; the public
v0 Postings API used here is not officially documented.** Undocumented `createdAt` (epoch
ms), ~~reliable in practice~~ **not a publication date — corrected 2026-09-22**: 9 of 28
live postings sampled carried a `createdAt` over a year old, the oldest 7.7 years. Still
worth storing in `posted_at`, which §6 already treats as informational only.
`salaryRange` when disclosed. Department via `categories.team`. **Lever also exposes a
structured `workplaceType`** (`onsite` / `hybrid` / `remote`), populated on 363/363 live
postings — store it in `workplace_type_raw` and see §12.3. v1's rate limits don't apply.

### Ashby — [developers.ashbyhq.com/docs/public-job-posting-api](https://developers.ashbyhq.com/docs/public-job-posting-api)
```
GET api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true
```
Full board, no pagination. `publishedAt` directly. ~~**The only provider exposing a
structured `workplaceType`**~~ — store in `workplace_type_raw`. *(Struck 2026-09-22: Lever
exposes one too, see above. Ashby's values are capitalised — `OnSite` / `Hybrid` /
`Remote` — against Lever's lowercase, and were populated on 1,416 of 1,817 live
postings.)* Compensation returns `compensationTiers` with a human-readable summary string
rather than separated numerics. **The `compensation` object is truthy even when nothing is
disclosed** (`compensationTiers: []`, summary `null`), so disclosure must be judged on the
tiers or the summary and never on the object itself;
`shouldDisplayCompensationOnJobPostings` is the provider's own flag and tracks it
exactly.

### SmartRecruiters — [developers.smartrecruiters.com/docs/endpoints](https://developers.smartrecruiters.com/docs/endpoints)
```
GET api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings
```
Documented, public, no auth. **Detection from day one**, so companies land in the
measurement rather than the failure bucket. **Polling adapter only if the count justifies
it** (§18).

### Rippling — [developer.rippling.com/documentation/job-board-api](https://developer.rippling.com/documentation/job-board-api) (a different endpoint than the one below)
```
GET api.rippling.com/platform/api/ats/v2/board/{token}/jobs[?page=N]
GET api.rippling.com/platform/api/ats/v2/board/{token}/jobs/{id}    # detail
```
**The linked docs describe `v1`, which requires a paid Recruiting Pro subscription and an
API key. The public, unauthenticated `v2` endpoint used here is undocumented** — it is
the same endpoint Rippling's own embed widget and hosted careers page call, same
public-widget-vs-authenticated-admin-API split as Greenhouse's boards-api vs. Harvest.
Token resolution needs a careers-page fetch first: the token appears as a literal API
call in inline JS, an embed's `data-job-board-id` attribute, or in the hosted page URL
(three sub-shapes: bare, `/embed/{token}/jobs`, locale-prefixed `/en-GB/{token}/jobs`) —
unescape HTML entities before matching, not after. List endpoint has no date or comp;
unlike Greenhouse, **the per-job detail call is not redundant** — `createdOn` (a real
posted date) and structured `payRangeDetails` (location/currency/frequency/range) exist
only there. `locations[].workplaceType` is structured, like Ashby. Confirmed live
2026-09-22 on 62 companies, 61 ok, 716 postings (`spikes/iteration11_rippling_spike.py`).

### BambooHR
No authoritative documentation of any kind (same bucket as Lever v0/Getro).
```
GET {company}.bamboohr.com/careers/list
```
Undocumented internal endpoint powering BambooHR's own careers-page widget; shape and
host reported to change between BambooHR releases without notice — needs the same
fixture-from-live-response discipline as Lever v0/Getro, and revalidation if a board
suddenly 404s. No organization-name field confirmed yet, so the same live-corroboration
requirement §8.2 already applies to careers-page-derived Greenhouse/Lever/Ashby tokens
applies here too before trusting a `verified` mapping. Confirmed live on at least one
board 2026-09-22 (`spikes/ats_integration_backlog.md`).

### Workable — [developer.workable.com](https://developer.workable.com) documents the authenticated admin API, not the endpoint below
```
GET apply.workable.com/api/v1/widget/accounts/{company}
```
The documented API (`spi/v3/jobs`, bearer token with `r_jobs` scope, 10 req/10sec limit)
is Workable's authenticated admin surface. The endpoint above is a separate, undocumented,
public, unauthenticated board endpoint that powers customers' own careers pages — same
split as Rippling and Breezy HR below. Returns `name`/`description` at minimum (a
validation signal, like Greenhouse's `/v1/boards/{token}`); full job-list field shape not
yet inspected live for this project — confirm during implementation, not from memory.
Rejection reopened 2026-09-24 — see §4.

### Personio — [support.personio.de: Overview of the Personio Recruiting API](https://support.personio.de/hc/en-us/articles/360000314338-Overview-of-the-Personio-Recruiting-API)
```
GET {company}.jobs.personio.de/xml?language=en
```
The public XML job feed is an officially documented, sanctioned feature for job
aggregators — not a reverse-engineered endpoint, unlike every other new provider here.
Public, unauthenticated. Returns XML, not JSON — needs a parser, not a JSON decode.
**Open, unresolved as of 2026-09-24:** a live spot-check of `nexwafe` returned a
client-rendered Next.js page at this path instead of XML (`spikes/ats_integration_backlog.md`)
— re-verify against a fresh sample during implementation before trusting either the
XML-only framing or that one negative result. Some tenants use `.com` instead of `.de` —
check the live hostname per company rather than hardcoding the TLD. Rejection reopened
2026-09-24 — see §4.

### Breezy HR — [developer.breezy.hr](https://developer.breezy.hr) documents the authenticated admin API, not the endpoint below
```
GET {company}.breezy.hr/json
```
The documented API (`api.breezy.hr/v3`, `GET v3/company/{company_id}/positions`, requires
an auth token) is Breezy's authenticated admin surface. The endpoint above is a separate,
undocumented, public, unauthenticated board endpoint — same public-widget-vs-authenticated
split as Workable and Rippling. Confirmed live 2026-09-22: structured `location.is_remote`
and a `salary` field, comparable richness to Ashby (`spikes/ats_integration_backlog.md`).
A `?verbose=true` query param reportedly returns full descriptions in one request —
confirm live before relying on it, not from this note alone.

### Getro
No documentation of any kind. `__NEXT_DATA__` shape is community-derived. Company source
only — see §7.2.

### Webhooks are unavailable
All ATS webhook systems live on the authenticated recruiting API, provisionable only by
the hiring company. Polling is the only option; structural.

---

## 10. Posting lifecycle

Per company, per run:

1. Fetch the live board.
2. **New** `ats_job_id` → insert, set `first_seen_at` / `last_seen_at`; ~~Greenhouse detail
   call *only here*~~. **No Greenhouse detail call appears to be needed at all
   (2026-09-22): the detail endpoint returned a byte-identical object to the
   `content=true` list entry on every job tested, so one list request per company covers
   it — see §9. Confirm against a board that actually publishes `pay_input_ranges` before
   deleting the detail path outright; none has been found yet.**
3. **Still present** → update `last_seen_at` **once per day**, not on every run (§6). New
   postings still insert on every run.
4. **Absent but previously present** → set `closed_at`.
5. **Reappearing** → `content_hash` matching a `posting_hashes` row for the same company
   sets `is_repost` (§6 — this table replaces the original ~90-day lookup against
   `postings` directly, which would have broken silently once closed postings started
   moving to `postings_archive` at 30 days). Surface it; a reopened role is signal.

**There is no Getro-sourced posting path anymore.** The original lifecycle described
Getro postings following the same steps with `source_path = 'getro'`, deduped against ATS
rows. That entire branch is gone along with the `source_path` column (§6) — every posting
row is ATS-sourced.

**`ats_job_id` stability is the assumption everything above rests on, and it now has a
measurement behind it.** Across two runs (`spikes/iteration7_run_diff.py`), 8,542 of
8,545 postings on the same companies kept their id, and **not one** of the compared
fields drifted on any of them — title, department, location, workplace type, url,
`posted_at`, or compensation. The three that vanished were confirmed as real closures by
re-fetching that board three more times rather than assumed to be. Worth re-running
whenever a provider changes shape: if ids churn, step 2 inserts postings that are not
new and step 4 closes postings that never closed, both silently and both at once.

**Seed mode:** an explicit flag populates without producing new-posting output or sending
any email. Without it, the first run emails thousands of postings.

**Comp backfill:** companies add ranges *after* publishing. Each run, re-fetch details
where `comp_data_quality = 'none' AND closed_at IS NULL AND age < 30 days`. Scoping by
comp status rather than date keeps this cheap — it's the only set a refresh can change.
Treat a backfill as **appending an observation** to `posting_comp_tiers`, never
overwriting an existing tier row — see §11.

---

## 11. Compensation

**Never collapse ranges for filter evaluation.** A posting often carries separate bands
per level or location: `max(all maxes)` comes from a band the user wouldn't be hired
into, `min(all mins)` from a different band, and a combined min+max filter over collapsed
values can pass a posting where no single band satisfies both.

Store every range in `posting_comp_tiers`. Collapsed fields exist for index speed only.
**The authoritative rule: does any single tier satisfy all active conditions?** Display
which tier matched; badge `comp_tier_count > 1`.

**Normalization:** `hour × 2080`, `week × 52`, `month × 12`; currency via a hardcoded rate
table refreshed approximately never (±5% is irrelevant at a screening threshold; only USD,
CAD, EUR, GBP matter). **Filters operate only on normalized values** — raw comparison
means hourly postings silently never match.

**By provider:** Greenhouse `payInputRanges` (detail) → `structured`; Lever `salaryRange`
→ `structured`; Ashby `compensationTiers` parsed with the original kept verbatim →
`structured` or `parsed`; nothing disclosed → `none`.

**Measured 2026-09-22 on 8,760 live postings across 255 mapped companies**
(`spikes/iteration7_live_postings_spike.py`), and it changes what "disclosed" means:

| Where the number was published | Postings | Share |
|---|---|---|
| Provider's structured field | 1,583 | 18.1% |
| Description body only | 3,020 | 34.5% |
| **Either** | **4,603** | **52.5%** |

*(An earlier revision of this section reported 14.2% / 38.3% from a 5,893-posting run.
Those figures were an undercount — the extraction was splitting Greenhouse's pay-range
block away from its own label and then discarding it. Corrected after a hand-labelled
sample; see below. Recorded rather than silently overwritten, since the first pair of
numbers was committed to this file.)*

**Greenhouse disclosed nothing structurally at all** — 0 of 5,243 postings carried
`pay_input_ranges` — while roughly a quarter of its postings published a range in the
description body. Lever and Ashby carry most of the structured disclosure.

**The structured fields therefore see about a third of the compensation actually
published.** An adapter reading only `payInputRanges` / `salaryRange` /
`compensationTiers` reports 18.1% where the real figure is 52.5%, and reports *zero* for
Greenhouse, the largest provider in the mapped set. Reading the description costs no
extra requests — all three providers return it in a response the poller already makes.

**How good the description extraction is, measured rather than asserted.** A
reproducible hand-labelled sample (seed 20260922) of 60 counted snippets found 59 to be
genuine role compensation; the single miss was a `$300 per month` commuter benefit.
Residual false negatives run at roughly 17% of a small reject pool, about 1% of all
postings — mostly pay bands embedded in requirements lists, of the form
`Level II ($101,000-$146,500): Bachelor's degree...`. **Proximity must be judged against
a bounded window of surrounding text, not the line the amount sits on**: Greenhouse
renders the amount on its own line, with the "Salary Range" label on the preceding one.
The correctly-rejected cases are consistently funding rounds, valuations, revenue and
market-size claims — "raised $42M", "valued at $15 billion", "$900 billion U.S. trucking
industry".

**This is not licence to parse prose into a number.** Keeping the matched line verbatim
in `comp_raw_summary` is cheap and safe; deriving integers from it is the part that needs
care, because the observed text carries real employer errors — `$200,00 USD - $280,000
USD` with a dropped digit, and an Ashby tier published as
`{"minValue": 20, "maxValue": 20, "interval": "1 YEAR"}`, a twenty-dollar *annual* salary
that is obviously an hourly rate. §3.8 applies: a confidently wrong number is worse than
a missing one. Treat any description-derived value as lower confidence than a structured
tier, and never let one satisfy a numeric filter silently.

**Never drop a row for missing comp.** Undisclosed is a first-class state.

Bonus and equity are not modeled — free text in every ATS studied. Keep whatever appears
in `comp_raw_summary` and display it.

### 11.1 `observed_at` and observed compensation history

**`posting_comp_tiers.observed_at` is a pre-leave build item, not a platform-era one**
(`SPEC-REVISION-02` §4, §14) — add the column before any data is collected; it is
unrecoverable later. Treat comp backfill (§10) as *appending* an observation, not
overwriting. A mid-posting range edit is signal; overwriting destroys it silently.

**The feature this enables — displaying observed history on undisclosed postings — is
platform-era work** (§19) and produces nothing useful for the first several weeks in any
case, since it needs history to accumulate. The schema groundwork goes in now; the
display goes in later. Concept, for when it's built:

Transparency laws mean many companies disclose on *some* postings and not others — the
CO/NY/MA req carries a band, the "Remote, US" one does not. A system polling the same
companies daily for months accumulates real observed comp per company and per rough
level, with a time dimension — you can see whether a band *moved*. No aggregator can
replicate this without polling at the source over time. Treat it as the differentiator.

Guardrails, load-bearing when it's built:
- This is **collected data, not inference**. Display the observations and their count.
  Never emit a single estimated number, a midpoint, or a predicted band for the posting
  in hand — that is the §4 scoring rejection in a new costume.
- **Observed history never satisfies a numeric filter.** A posting matching on a
  neighbour's salary is wrong data; §3.8 applies.
- Derived on read from `postings` + `posting_comp_tiers`. No stored estimate field (§6).
- Card treatment, when built: where comp is undisclosed and the company has ≥3 prior
  observed ranges in the same job function, show the observed history beneath the muted
  "comp not disclosed" line, labelled as history and never as an estimate for this role.
  No filter changes — the comp filters in §12.2 continue to operate only on the
  posting's own disclosed values.

(`SPEC-REVISION-01` §R7, `SPEC-REVISION-02` §4)

---

## 12. Interface

Static site on GitHub Pages, regenerated and committed each run. Public, with **no
personal name, no author attribution, and no identifying detail** — see §15.

**Before writing any rendering code, read `SECURITY.md §S1`.** Every field on a card
originates from a third party, and the page shares an origin with uploaded LinkedIn data
in `localStorage`. Rendering rules are a correctness requirement, not a hardening pass to
apply later.

### 12.1 Layout

```
┌──────────────────────────────────────────┐
│  ☰   First Look                           │   nav: Jobs · Health
├──────────────────────────────────────────┤
│  ⚠ Data may be stale — last updated 3d    │   only when stale/failed
├──────────────────────────────────────────┤
│  [ sticky filter bar ]                    │
├──────────────────────────────────────────┤
│  47 jobs match    [get alerts] [clear]    │
├──────────────────────────────────────────┤
│  cards, newest first, no pagination       │
└──────────────────────────────────────────┘
```

Health lives behind the hamburger on `/health` — the second user has no reason to see it.
**The exception is the stale banner**, shown on the main page whenever the last run failed
or is over 48 hours old. Without it, a broken pipeline looks identical to a quiet week,
recreating silent failure in the UI.

### 12.2 Filters (sticky, in this order)

| Filter | Type | Notes |
|---|---|---|
| Posted | Single select | 24h / 3d / 7d / 14d / 30d. Operates on `first_seen_at`. |
| Location | Multi | Remote / Hybrid / In-office / Unknown — §12.3 |
| City | Multi | "Remote" plus cities from postings, alias-grouped (§12.4) |
| Industry | Multi | From `industry_tags`; "Climate" appears here |
| Company | Type-to-search, multi | |
| Job Function | Multi | From `department_raw`, alias-grouped (§12.4) |
| Title | Free text | **Case-insensitive** |
| Above Salary Range Min | Number | Input ×1000 (`200` → `$200,000`); >1000 treated as literal dollars |
| Above Salary Range Max | Number | Same |
| Undisclosed Salary | Toggle | |

**The undisclosed toggle must short-circuit both numeric filters.** When comp is null
neither comparison is meaningful, so null rows pass whenever the toggle is on regardless
of the numeric inputs. The obvious bug is letting a numeric filter drop the row first,
making the toggle appear broken.

**Filter state is encoded in URL query params** — bookmarkable and shareable, no accounts.
**Dismissal state in `localStorage`**, dimmed with a "show dismissed" toggle rather than
hidden, plus an export button. Per-browser conveniently means per-user. **Platform-era
note:** once accounts exist, dismissal moves server-side and gains three more states — see
§19.3.

### 12.3 Location classification — derivation deferred by design

`location_raw` is verbatim and never overwritten. `location_class` is narrow and derived:

- **Ashby and Lever** → from structured `workplace_type_raw`. *(Lever added 2026-09-22 —
  see §9. Ashby's values are capitalised and Lever's lowercase, so normalise case when
  deriving; never overwrite the raw value.)*
- ~~**Greenhouse / Lever**~~ **Greenhouse** → narrow keyword match on the raw string for
  remote and hybrid. It exposes no structured field at all (0 of 3,713 live postings).
- **Everything else** → `unknown`, never guessed as onsite.

`unknown` is a **visible filter option**. It will be a large bucket, and hiding it would
silently lose postings from a filter the user believes is exhaustive.

**Exact rules are written after inspecting real values.** A `--dump-facets` command prints
distinct `location_raw`, `workplace_type_raw`, `city_raw`, and `department_raw` values
with counts. Write the rules from what's actually there.

### 12.4 Alias grouping — user-editable, not a classifier

```yaml
# config/function_aliases.yml
Product: [Product, Product Management, "Product & Design", PM]

# config/city_aliases.yml
San Francisco: ["San Francisco, CA", "SF Bay Area", "Bay Area"]
```

Both start empty, grown by hand from `--dump-facets` output. Unaliased values appear as
themselves — optional improvements, never required for correctness. A lookup table the
user owns, not a classifier.

`city_raw` is the first comma-token of `location_raw` — a crude split that will sometimes
be wrong; aliases absorb the damage.

### 12.5 Cards

```
Acme Energy · Climate, Energy                    Found 6h ago
Senior Product Manager, Grid Platform
Product · Remote (US)
$190K – $255K   ⚠ multiple ranges
🔗 3 connections at Acme Energy                            [×]
```

- Company name, then actual industry tags (first two).
- **Age from `first_seen_at`: hours under 24h, days above.** Labelled "Found," which is
  what the number means.
- Title links to the posting.
- Job function and location.
- Comp shows `comp_raw_summary` verbatim; multi-range badge when `comp_tier_count > 1`;
  "comp not disclosed" muted otherwise — **never blank**, or missing is
  indistinguishable from broken.
- **Once observed comp history exists** (§11.1, platform era): where comp is undisclosed
  and the company has ≥3 prior observed ranges in the same job function, show the
  observed history beneath the muted line, labelled as history, never as an estimate.
- Connection count (§12.6) when connection data has been loaded, otherwise absent.
- Repost badge where applicable. `×` dismisses.

**Rendering rules (`SECURITY.md §S1`):** every field above is set with `textContent`,
never `innerHTML`. The title's `href` is rendered only when the URL scheme is `http:` or
`https:` — a `javascript:` URL in a posting executes on click. Outbound links carry
`rel="noopener noreferrer"`.

### 12.6 LinkedIn connections — entirely client-side

Shows how many first-degree connections the viewer has at each posting's company. This is
the only feature touching conversion rather than discovery.

**No LinkedIn API and no scraping** — the connection graph isn't exposed by their APIs,
and scraping is against their terms and actively defended.

**The data never touches the repo or the network:**

1. The user exports `Connections.csv` from LinkedIn (includes each connection's current
   company) and keeps it local.
2. A local-only script reduces it to `{company_name: count}` — **counts only, no names,
   no titles, no emails**.
3. The dashboard has a file-upload control that loads that JSON into `localStorage`.
4. Cards render the count, matched on company name.
5. **The upload is validated as an object of string keys to integer values and rejected
   otherwise** — it is untrusted input like any other field on the page
   (`SECURITY.md §S1`). Because this data shares an origin with the dashboard, an XSS on
   that page is an exfiltration path for it, which is why §S1's rendering rules are
   load-bearing here rather than merely tidy.

Nothing is committed, nothing is transmitted, and it is per-user by construction — each
person uploads their own and sees their own numbers. This is not merely the user's own
privacy: the export contains hundreds of other people's employment data, which is not the
user's to publish.

`Connections.csv` and `connections*.json` are gitignored **from day one, before the
feature exists.**

Matching is fuzzy company-name-to-company-name and will be imperfect; a small
`config/company_aliases.yml` absorbs the common cases, same pattern as §12.4.

**Planned UX improvement, platform era (§19.6):** the download → local script → upload
flow is three steps and a terminal, which means almost nobody does it. A revised flow
parses the CSV in the browser directly (no script), stores the reduced JSON in IndexedDB
instead of `localStorage`, and offers a File System Access API handle for one-click
refresh. The client-side-only rule stays permanent through that revision and every future
one — this is non-negotiable, not merely current-state (§4).

### 12.7 Empty states — three distinct messages

- "No jobs match these filters" + clear-all → filters too tight
- "No jobs in the database" → seeding never ran
- "Last run failed — see Health" → don't trust what you're seeing

Conflating these recreates silent failure in the UI.

### 12.8 Payload size

Client-side *filtering* is fast at any realistic scale; **transfer and parse are the
constraint.**

```
docs/jobs-recent.json    open postings, last 30 days — loads immediately
docs/jobs-archive.json   everything else — fetched only when a filter needs it
```

Ship only `closed_at IS NULL` and only fields the cards use. Past ~3MB on
`jobs-recent.json`, shard by month. Don't build sharding before §7's coverage sample (§18)
says which regime applies.

**Superseded once the platform-era read layer exists** (§19.2): a server-rendered Next.js
app queries Postgres directly, and the sharded-JSON approach goes away entirely. Retain
this section only while Pages is the live interface.

### 12.9 Health page

Behind the hamburger. Run history, `last_successful_run`, companies polled, live postings,
failing companies by name and reason, mapping coverage by `ats_status` /
`mapping_confidence` / `mapping_failure_reason`, recent run summaries. **No email
addresses, no profile contents** — see §15. Once instrumentation exists (§19.13), this is
also where the median discovery-to-view/apply latency number belongs.

---

## 13. Notification

Three channels with distinct jobs. Neither GitHub's nor healthchecks' email content is
customizable, which is why §14 requires a readable run summary.

| Need | Mechanism |
|---|---|
| **New matching postings** | Per-profile email, Resend free tier |
| "It ran but something is wrong" | Workflow exits non-zero → GitHub failure email to repo watchers |
| "It stopped running entirely" | healthchecks.io dead-man's switch |
| Browsing | Dashboard + RSS (`feed.xml`) |

### 13.1 Notification profiles live in a secret, not the repo

Because the repo is public, profiles are stored as a single Actions secret,
`NOTIFY_PROFILES`, holding a JSON array:

```json
[
  {"name": "primary", "email": "...", "filters": {"comp_max_above": 200,
   "job_function": ["Product"], "location": ["remote"], "posted_within_days": 1}}
]
```

The workflow reads it from env. Secrets remain private on public repos, so no address
ever lands in git history. Code stays user-agnostic — it reads whatever profiles exist
and applies them generically, exactly as it would from files.

- Sent **only when there are new matches** — liveness is covered by the other two
  channels, so an empty email at 4x/day would be noise.
- Each posting is emailed at most once per profile (`notifications_sent`, storing profile
  *name* only).
- Seed mode sends nothing.
- Adding a profile requires no code change.

**Log-masking caveat (`SECURITY.md §S3`).** GitHub masks *exact* secret values in logs,
but `NOTIFY_PROFILES` is parsed — an address extracted from it is a different string and
will **not** be masked. Profiles are referred to by `name` everywhere outside the send
call itself; a parse failure raises a message containing no parsed content; the send
call's error path never includes the recipient.

**Platform era:** this whole mechanism is superseded by `saved_searches` +
`alert_subscriptions` tables once accounts exist — see §19.7. The secret and the
generic-reader pattern stay exactly as described here until that migration happens.

### 13.2 Alert requests — self-serve without a backend

The dashboard's "Get email alerts for this view" button opens a hosted form (Tally,
Google Forms, Formspree — all free) pre-filled with the current filter query string. The
submission goes to the maintainer's inbox, who pastes an updated JSON into the secret.

This is **request-an-alert, not true self-serve.** True self-serve requires a server able
to write on a stranger's behalf, which is the rejected OAuth path in §4 (stale, not wrong
— see §19.2 for when it stops being rejected). This gets most of the UX at none of the
infrastructure cost and scales to a handful of people.

**Do not use a pre-filled GitHub issue for this.** It requires a GitHub account and would
publish the requester's email address on a public repository.

**Platform era:** superseded for alerts by real saved searches (§19.7); the pattern
(hosted form pre-filled with query string, no pre-filled GitHub issue) is retained
permanently for the feedback button (§19.10).

---

## 14. Reliability

**Absence of output must be distinguishable from absence of jobs.** Nobody is watching for
two months.

**Dead-man's switch — build first.** healthchecks.io: the workflow pings on success; the
service emails when a ping doesn't arrive. The only mechanism catching "Actions stopped
running at all" — no internal heartbeat can report a job that never started. Period
matches the run schedule with generous grace.

**Per-company failure detection, split by permanence:**

| Condition | Meaning | Action |
|---|---|---|
| Timeout, 5xx, connection reset | Transient | Backoff within run; flag after 3+ consecutive failed runs |
| 404, invalid token | Permanent — token changed or company left | Flag for remapping after 1–2 failures |
| 200 with zero postings | Ambiguous | Suspicious only if `last_nonzero_postings_at` is set |

Failing companies are flagged, excluded from health counts, **never auto-removed**, named
on the health page.

**Aggregate anomaly → non-zero exit.** Total live postings dropping >25% run-over-run, or
HTTP error rate >10%, fails the workflow — catching systemic breakage that per-company
checks would report as hundreds of individual failures nobody reads, and converting it
into an email for free. **A database connection failure is now part of this same rule**
(`SETUP-PLATFORM.md` §8): with Postgres in place (§6), a DB outage must exit non-zero,
not retry silently forever — this is what makes it a loud failure per §3.3 rather than a
new silent one.

**The run-over-run comparison must hold the company set fixed.** Measured 2026-09-22 on
two runs eight minutes apart (`spikes/iteration7_run_diff.py`): comparing run totals
reported **+681 postings**, while the real movement across the companies present in both
runs was **2 opened and 3 closed**. Every one of the 681 was a newly-*mapped company*,
not a newly-*opened posting*. Mapping runs monthly on the cold path (§8.5) and discovery
adds companies in batches, so the totals this rule watches move for reasons that have
nothing to do with any board. Compute the ±25% against the intersection of companies
polled successfully in both runs, and report companies added or dropped as a separate
number. Otherwise the check fires on a discovery batch, or — worse, and the reason this
is here rather than in `BUILD.md` — a genuine 25% collapse hides behind a pool that grew
by 30% the same week, during the exact unattended window this section exists for.

**Readable run summary as the final output of every run.** GitHub's failure email is a
fixed template linking to the run log, so the last twenty lines must answer "what's
wrong": companies polled, new postings, failing companies by name and reason, anomaly
status.

**The run summary must never print personal data.** Workflow logs are world-readable on
public repos. Report "2 profiles matched, 5 alerts sent" — never an address, never which
profile received what. **Write the summary emitter to take counts only, never objects**
(`SECURITY.md §S3`) — a function that accepts a profile and formats it is one refactor
away from printing an address into a world-readable log. This is an interface decision,
made once, not an ongoing discipline. Assert this by test on the **run summary string**
specifically, which is deterministic; a blanket "no `@` in stdout" grep will eventually
false-positive on a company name or posting URL and should be advisory only, never
failing.

**No exception escapes the per-company loop.** The most important line of code in the
system and the easiest to omit — everything works until one company returns malformed JSON
and the result is zero postings for a month.

**Checkpoint discovery crawls. Pin everything** — Python version, lockfile, Action SHAs.

**Burn-in before leave:** two weeks of scheduled runs, breaking things deliberately and
confirming each alert arrives. Untested alerting is not alerting.

---

## 15. Hosting and public-repo posture

**GitHub Free, public repository, GitHub Pages, for the pipeline and the dashboard.**
Pages serves from public repos on Free, and Actions minutes are unmetered on public
repos, so run frequency costs nothing.

**Building in public is an accepted, deliberate choice.** The posture is low-profile
rather than hidden: discovery is fine, advertisement is not.

- Neutral repository name. No README tying the project to a person. No personal name on
  the dashboard or in commits beyond the git identity. Not pinned on the owner's profile.
- `config/watchlist.yml` is committed and readable. Accepted.
- `mapping_review.csv` and `jobs-*.json` contain public company and posting data. Fine.
- **`jobs.db` is no longer committed** (§6) — state now lives in Postgres, not in git.
  Everything in this section about what *is* committed refers only to what's still
  actually in the repo after that move.

**What may never be committed or logged**, because it is other people's data rather than
the owner's to accept risk on:

| Item | Handling |
|---|---|
| Notification emails and filters | `NOTIFY_PROFILES` secret (§13.1) |
| LinkedIn connection data | Local only; localStorage; gitignored (§12.6) |
| Anything in Actions run logs | Counts, never identities (§14) |
| `DEVLOG.md` | Reviewed periodically for incidental personal detail |
| `SUPABASE_SERVICE_ROLE_KEY` | GitHub Actions secrets and server-side env only, never `NEXT_PUBLIC_*` (`SETUP-PLATFORM.md` §7) |

```yaml
permissions: { contents: write }
concurrency: { group: monitor, cancel-in-progress: false }
```

The concurrency group prevents overlapping runs conflicting on writes; it cost nothing to
keep even after the SQLite-corruption risk it was originally written for mostly evaporated
with the move to a transactional Postgres store (§6).

### 15.1 Security posture

A public repository running Actions with secrets has a real attack surface even though
the application itself has almost none. `SECURITY.md` is the full audit; three structural
requirements constrain design rather than implementation:

- **Workflows carrying secrets never trigger on a pull request.** A separate,
  secrets-free `test.yml` runs tests on PRs (§5, `SECURITY.md §S2`).
- **Every third-party Action is pinned to a full commit SHA.** A mutable tag can be
  repointed at code that reads secrets (`SECURITY.md §S2`).
- **`KEEPALIVE_PAT` is fine-grained, single-repo, contents-only, and expires after leave
  ends.** It carries write access to a repo that executes workflows, which makes it the
  highest-value secret in the project (`SECURITY.md §S4`).

**Platform era:** this section's reasoning is superseded, not by getting weaker, but by
splitting — the web app is a separate deploy (§19.2) whose user data lives in Postgres
behind RLS, not in a world-readable git history. The pipeline repo's public posture
described above is unaffected and continues exactly as written.

---

## 16. Keepalive

The 60-day scheduled-workflow inactivity disable applies to public repos — almost exactly
the leave window. Layered mitigation, ordered by effort required:

1. **PAT-attributed state commits (zero effort).** Push with a fine-grained PAT so commits
   are attributed to the user's account rather than `github-actions[bot]`. Bot commits are
   widely reported not to reset the inactivity timer; user commits do. Community lore
   rather than documented behaviour — a mitigation, not a guarantee.
2. **Four runs daily (zero effort).** More attributed activity.
3. **Dead-man's switch (zero effort).** Everything above is best-effort; this makes
   failure *detected*. Which is why it's built first.
4. **One `workflow_dispatch` tap per month from the GitHub mobile app (~10 seconds).** The
   recovery action, and the only item needing the user.

**A second, independent keepalive risk now exists on the database side** (§6): Supabase
pauses Free-Plan projects after a period of low activity. A 4x/day poller keeps it alive
trivially on its own, but the mitigation that actually matters is paying for Pro across
the leave months, since the pause only bites once the monitor is *already* dead for a
week — and at that point the dead-man's switch has already fired regardless.

---

## 17. Open questions

1. **Cascade coverage** — what fraction reach `verified` or `probable`. The single number
   determining whether the system is worth its crawl; also sets §12.8's payload regime.
   Promoted to a blocking measurement — see §18.
2. **Failure-reason distribution** — `unsupported_ats` (build adapters) vs.
   `js_rendered` / `weak_only` (improve mapping). Promoted to a blocking measurement —
   see §18.
3. **Slug-guess false-positive rate** against watchlist ground truth. If the negative
   guard is insufficient, tighten to `verified`-only.
4. **SmartRecruiters volume** — decides whether the adapter is written.
5. **Real `location_raw` and `department_raw` distributions** — determines §12.3 rules and
   seeds §12.4 aliases. Feeds measurement #4 in §18.
6. **Getro `__NEXT_DATA__` shape** — confirmed on one real board (§7.2); still needs
   checking against the rest of `config/getro_boards.yml`, since one candidate already
   turned out to look structurally different. **New sub-question, not yet answered:**
   does the domain-resolution gap noted in §7.2 hold up across more boards, and if so,
   what does the resolution hop look like — is it even solvable in general, given the
   external URL is often a third-party ATS rather than the company's own site?
7. **Built In Boston anti-bot posture** at crawl volume — 20–50 requests first.
8. **Real comp disclosure rate.** Pay transparency laws in Massachusetts, Colorado, New
   York, California and Washington suggest most remote US postings disclose, but the
   actual rate determines the comp filter's usefulness. Promoted to §18's measurement 3 —
   note it is a fact about the world, not an engineering problem, unlike #5/#4 above.
9. **LinkedIn company-name match rate** — how often an export's employer string matches a
   `companies` row, and how much `company_aliases.yml` is needed.
10. ~~Consider's client-side fetch — what endpoint, what shape~~ **Resolved
    2026-09-20** — see §7.6 for the confirmed endpoint, auth flow, and request shape.
11. **ClimateTechList partnership response** — did they say yes (§7.5).
12. **Wellfound company-slug → domain resolution hit rate** (§7.7).
13. **Greentown overlap rate** — what fraction of Greentown members are already captured
    by ClimateBase, Getro, or Built In. Measured after the Greentown crawl. If overlap is
    near total, note it; if Greentown surfaces a meaningful number of companies no other
    source has, that is evidence for adding similar incubator directories (Elemental,
    Third Derivative, New Energy Nexus) as a cheap backlog item.
14. **Whether a filtered YC climate slice would add anything** beyond the full YC source
    already in scope (§7.8) — answerable only once #13 shows how much the existing
    climate sources already cover. Do not build it speculatively.
15. **Whether Wellfound offers native saved-search email alerts**, as a manual
    supplement — moot for automation either way, since Wellfound is a company source now
    (§7.7).

**Still open, platform era** (`SPEC-REVISION-02` §15 — none of these block the current
build):

16. Resume editor — build at all? See §19.12's unresolved tension.
17. Whether "apply fast" and "tailor carefully" can coexist as one product claim.
18. Everything gated on the §18 measurement gate below.
19. Whether the platform happens at all.

---

## 18. Measurement gate

**Run after M4, before any further source work.** Nothing below the gate is built before
the gate is passed. Seed a few hundred companies through the full cascade and measure four
numbers from `--dump-facets` and the mapping table:

| # | Measurement | Decides |
|---|---|---|
| 1 | Cascade coverage: % reaching `verified` or `probable` | Whether company-first discovery works at all, and therefore whether Built In national (§7.4) is a 10x win or 90k unmappable rows |
| 2 | `mapping_failure_reason` distribution | Which adapter, if any, to build next |
| 3 | Comp disclosure rate on live postings | The ceiling on the whole time-saving claim. ~~Not engineerable — if the employer published no number, no parser recovers it~~ **Partly engineerable after all (2026-09-22): most published comp sits in the description body rather than the structured field — 18.1% structured against 52.5% including description text, measured on 8,760 live postings. See §11.** What stays un-engineerable is only the remainder where no number was published anywhere |
| 4 | `location_class = 'unknown'` share | Whether remote filtering is usable. Unlike #3 this *is* engineerable: the information is present in `location_raw` and the rules grow from real facet output |

**#3 is a fact about the world; #4 is a parsing problem.** Do not conflate them when
reading the results. **Qualified 2026-09-22:** #3 turned out to be part parsing problem
too — the employer frequently *had* published a number, just not where the API exposes
it. The distinction still holds for postings carrying no number anywhere, which is the
real ceiling.

**Gate outcomes:**
- Coverage high, disclosure high → proceed to Built In national and the platform
  question.
- Coverage high, disclosure low → the product is novelty-and-alerting, not
  comp-filtering. Reprioritise §11.1's observed-history feature hard; it becomes the main
  feature rather than a bonus.
- Coverage low → stop adding sources. Fix mapping. The seed list is not the constraint.

**Sequencing across the gate** (`SPEC-REVISION-01` §R12):

1. M-1 → M4 as specced. Seed from watchlist + ClimateTechList + ClimateBase orgs.
2. **This measurement gate.**
3. M10, M8 — unattended monitor emailing new postings.
4. ~~Consider parser (§7.6)~~, Wellfound company source (§7.7) — cheap, cold-path.
   **Consider built 2026-09-24 (`src/consider.py`, `CRITERIA.md` C-6.4), ahead of this
   gate, by explicit user decision after a de-risking spike
   (`spikes/iteration15_consider_notes.md`) — not a gate-driven promotion. Wellfound
   remains gated here as originally sequenced.**
5. Run live against real criteria for three months even if not actively applying. This
   is the only honest way to answer coverage, and the only way to learn whether the
   interesting product is this or something adjacent.
6. YC (§7.8), Built In national (§7.4), observed comp history (§11.1) — gated on step 2.
7. Platform question (§19) — November, with data.

**Effort note:** the original 45–75 hour estimate assumed functioning evenings. Against a
newborn, plan for roughly a third of the available time and treat anything more as
upside.

---

## 19. Platform era — deferred, decide in November

Everything in this section is `SPEC-REVISION-02` in full, describing a possible future
build: accounts, real alerting, an application tracker, and more. **None of it is built
now.** Per §14 of that revision, the only two items pulled forward into the current build
are the Postgres migration (§6 above) and the `observed_at` column (§11.1 above) — both
because they are unrecoverable or structural if deferred. Read this section to understand
where the project could go, not as a build list for the next milestone.

### 19.1 Privacy posture

Principle §3.9 (no personal data in the repository, in committed artifacts, or in run
logs) is retained verbatim for the repo. What changes in the platform era is that
personal data starts to exist *somewhere* — in Postgres, behind RLS. The question stops
being whether PII can be secured and becomes what each item costs to hold.

| Tier | Items | Handling |
|---|---|---|
| **Never server-side** | LinkedIn connection export; resume files | Client-side only, permanently (§12.6, §19.6, §19.12) |
| **Transits, never rests** | Resume text sent for LLM tailoring | Zero-retention proxy or BYOK (§19.12) |
| **Normal table + retention** | Applications, saves, saved searches, contact channels | RLS default-deny; auto-age; export + delete |
| **Public** | Companies, postings, comp observations | Employer-published |

**The control that matters for application history is retention, not encryption.** The
damage from a leak here is not identity theft — it is that people get fired for job
hunting. Age applications out ~1 year after their last update.

**Realistic breach path is a table shipped with RLS off, or `service_role` reaching the
frontend** — not disk theft. Spend effort accordingly:
- Every table starts with RLS enabled and default-deny, checked in CI (`SETUP-PLATFORM.md`
  §7).
- The anon key is public by design. RLS is the *only* barrier between a stranger and
  users' addresses.
- `service_role` never leaves GitHub Actions and server-side routes.
- Application-layer encryption is **not** recommended — it breaks queryability and
  defends the wrong threat.

**Export and delete are features, not compliance theater** (§19.8).

### 19.2 Platform architecture

**The §4 OAuth/backend rejection is stale, not wrong.** Three problems in 2024; one
managed service in 2026. Supabase Auth collapses database, sessions, and deploy target
into the Postgres instance already required by §6. Record as superseded when this is
built, not as an error.

**Stack, when built:**

| Layer | Choice | Note |
|---|---|---|
| Compute | GitHub Actions, unchanged | The pipeline does not change |
| Storage | Supabase Postgres | Already true — see §6 |
| Read layer | Next.js on Vercel, server components | No API layer to write |
| Auth | Supabase Auth — Google + magic link | §19.5 |
| Email | Resend — alerts *and* auth SMTP | One domain reputation |

Supabase is not an OAuth provider alongside Google — it is the layer that runs providers.
The choice is which methods to enable inside it.

**What this obsoletes, when built:**
- **§12.8 payload sharding** — server components query Postgres directly, no more static
  JSON shards.
- **§15 public-repo posture, for the web app specifically** — the web app is a separate
  deploy; the pipeline repo's posture is unaffected.
- **§16 keepalive, the scheduled-workflow-disable concern** — superseded by the Supabase
  pause concern already described in §16.

**Migration order:**
1. Storage first (§6) — built in M0, not yet done as of this writing. Pages keeps
   running off exported JSON until then; nothing user-visible changes when it happens.
2. Next.js read layer alongside Pages until parity, then cut over.
3. Auth + per-user state (§19.5). Saves and dismissals leave `localStorage`.
4. Alerts from `saved_searches` (§19.7), retiring `NOTIFY_PROFILES`.
5. Applications (§19.9), instrumentation (§19.13), feedback (§19.10).

See `SETUP-PLATFORM.md` for the concrete account setup, DNS, and RLS steps for all of the
above.

### 19.3 Card state and filters

**Card states, four plus a badge.** Every state needs a non-color signal — a label or
icon; four greys plus a green wash fails for colorblind users and collapses in dark mode.

| State | Trigger | Treatment |
|---|---|---|
| **Viewed** | Clicked through | Marker, **not** a downgrade — left border or "viewed" tag, unchanged text weight |
| **Not interested** | Button | Dimmed, strongest grey. This is §12.2's dismissal, moved server-side |
| **Applied** | Button | Dimmed, green tint, label |
| **Saved** | Button | **Accent, never dimmed** — highest-intent state in the system |

**Do not reuse dim for "opened."** Dimming on click-through conflates "I looked at this"
with "I'm done with this" — opposite meanings. Someone fires off five tabs, works through
them, returns, and the two worth applying to look identical to the three rejected.

**Click behavior:** open in a background tab so the filtered list survives, mark viewed,
apply the viewed treatment. The multi-tab scan is the power-user pattern and most of the
felt speed.

**Applied needs an honest bridge.** Clicking through is not applying. Once a card has been
opened and left unmarked for a while, show a quiet affordance — "opened 2h ago · applied?"
— one click to resolve. Do not prompt on return; that is nagging.

**Save is a shortlist**: jobs the user wants to apply to but has no time for now. Fully
orthogonal to the others — someone can save *and* apply. Give it a nav destination, not
just a filter; it is somewhere you go.

**The New badge, and two visit timestamps.** Store two columns, not one:
`previous_visit_at` and `current_visit_at`. Render badges against `previous_visit_at`;
write `current_visit_at` on session start. With a single column updated on load, badges
vanish on arrival or the list shifts mid-scroll.

Badge = `first_seen_at > previous_visit_at` AND not clicked. Time-windowed so it means
"new"; click-clearing so it behaves as described. Next visit rolls the window.

"Seen" means clicked, never rendered — viewport tracking would generate an event per card
per scroll (§19.13's volume problem).

**First-session suppression.** When `previous_visit_at IS NULL`, suppress badges entirely
and set the column when that first session ends. Otherwise every card in the database is
technically new on the one occasion the badge is most likely to be dismissed as noise.
Same reasoning as §10's seed mode. **Cap the window at ~14 days** regardless of actual
last visit — past a couple of weeks "what changed since I looked" has stopped being a
useful question.

**Filters — tri-state controls, not five checkboxes.** Only-applied and exclude-applied
are mutually exclusive; as checkboxes a user can tick both and get zero results with no
indication why — the same failure §12.2 already calls out for the undisclosed-salary
toggle.

| Control | Positions |
|---|---|
| Applied | show all / **hide applied (default)** / only applied |
| Not interested | show all / **hide (default)** / only |
| Unopened | off / **only unopened** |

Defaulting both to hide is the point: the list you land on is everything you have not
dealt with. "Only applied" doubles as the application tracker view for free. Unopened is
click-based and persistent — the backlog view, everything never got to, regardless of
when it landed. Distinct from the badge, which is time-windowed; do not merge them.
Consider making unopened-plus-recent the default landing view.

**Save expiry — no episodes table.** A shortlist should not persist across job searches,
but a `searches` episode table with start/end and an "I got a job" flow is overengineering.
Instead: one nullable `saves.expires_at`, set 90 days out on save, pushed forward on any
interaction with that row.

- **Expiry hides, never deletes.** This rule will be wrong for some users; a hidden save
  is recoverable, a deleted one is not.
- **Gap prompt, independent of the rule.** Returning after months: "you have 23 saved
  jobs from your last search — keep or clear?" One question, no inference.
- **Saved + closed** shows as closed rather than disappearing: struck title, "closed 12
  days ago," link disabled, plus a nudge — "2 of your saved jobs closed this week" —
  which is direct evidence for the speed thesis.

### 19.4 Storage details specific to the platform era

The core storage move (Postgres, write amplification, hot/cold split, `posting_hashes`)
is already current — see §6. The only additional platform-era storage concern is the
schema for accounts and their data, covered in §19.7's table list.

### 19.5 Auth

**Passwordless only. Nobody remembers a password.**

- **Google** — primary in the UI, instant.
- **Magic link** — beneath it, for people without a Google account. Doubles as email
  verification for alerts (§19.7).
- No GitHub. It skews technical; the target user is a climate PM.

**Anonymous-first.** Do not gate the first click.

1. Anonymous saves and dismissals write to `localStorage`, keyed by the same `anon_id`
   used for events (§19.13).
2. Prompt at a natural threshold — three saves, or on return — not on first action.
3. On signup, **migrate the accumulated state**. The pitch is "keep your 5 saved jobs,"
   which converts far better than an empty modal.

**Never gated:** filtering, browsing, clicking through to apply. Gating apply clicks would
sabotage the thing the product is for. **Genuinely gated:** alerts — there is nowhere to
send them otherwise.

**Preserve the action through auth.** The universal failure is: click Save → sign up →
land on an empty dashboard with the job gone. Stash the intended action, complete it after
callback, return to the filtered list. §12.2 already encodes filter state in the URL, so
carrying that through the redirect restores the list for free.

**Modal, not a route.** A full-page redirect loses scroll position and the context of the
list.

**Configuration that must be deliberate** (details in `SETUP-PLATFORM.md` §5):
- **Identity linking.** Same email via magic link and Google must resolve to one account.
  The failure mode is two accounts, one holding all their saves — experienced as you
  losing their data.
- **Magic-link rate limits and short expiry.** Otherwise the endpoint is a way to send
  mail from your domain to arbitrary addresses.
- **Custom SMTP → Resend.** Supabase's built-in mailer is development-grade.

**The anonymous → authenticated migration is the highest-risk small feature here.** It
runs once per user, silently, and if it drops rows nobody reports it because they do not
know what they lost. Test deliberately.

### 19.6 LinkedIn connections — UX revision

The rule is unchanged and permanent: never server-side, in any version (§4, §12.6). The
export contains hundreds of other people's employment data. Do not move it into the
database merely because a database now exists.

The revised UX, described briefly at §12.6, in full:
- **Parse the CSV in the browser.** File input, reduce to `{company: count}` in JS. The
  script disappears, and it is *more* private than the original design: the reduced JSON
  no longer exists as a file on disk that could be committed or synced by accident. Names
  live in a variable that is garbage-collected on reload.
- **IndexedDB, not `localStorage`** — 5MB and string-only is the wrong tool.
- **`navigator.storage.persist()`** on first save, so the browser does not evict silently.
- **File System Access API** to store a handle to their `Connections.csv`, making refresh
  one click. Chrome/Edge only; keep file input as fallback.
- **Surface staleness** — "connections loaded 47 days ago." A stale count is worse than
  none.

Accepted limitation: per-browser, per-device. That is the price of not holding it.

### 19.7 Alerting

**Schema:**

```
profiles            (id → auth.users, timezone, previous_visit_at,
                     current_visit_at, created_at)
contact_channels    (id, user_id, kind, address, verified_at, is_active)
saved_searches      (id, user_id, name, filters jsonb, created_at)
alert_subscriptions (id, saved_search_id, channel_id, cadence, quiet_hours, is_active)
notifications_sent  (posting_id, subscription_id, sent_at)   -- replaces §6's table
saves               (user_id, posting_id, saved_at, expires_at)
dismissals          (user_id, posting_id, dismissed_at)
applications        (id, user_id, posting_id, status, applied_at, notes, updated_at)
```

**Searches and subscriptions are separate tables.** A saved search is useful alone — the
"click it and see results" case. A subscription turns one into notifications. Splitting
them lets one search fire to email *and* push without duplicating filters.

`filters` as `jsonb` preserves §3.1: no user criterion in pipeline code; the matcher reads
whatever is there generically. Same principle as `NOTIFY_PROFILES`, in a table.

`notifications_sent` in the current build stores a profile *name* to keep addresses out
of a public repo. That constraint is gone once this table exists in Postgres behind RLS;
key on `subscription_id` instead.

**Three things that bite if skipped:**
- **Channel verification is not optional.** An unverified row means anyone can subscribe
  anyone else's address, and your domain reputation pays. Double opt-in before
  `verified_at`. Magic-link signup already verifies the auth address; separate channels
  need their own confirmation.
- **Match in SQL, not in the app.** 1,000 users × 5 searches = 5,000 filter evaluations
  per batch, 4x/day. Iterating in Python pulls the whole batch per search. Compile each
  `filters` jsonb to a predicate; one pass in Postgres.
- **SMS is a bigger step than it looks.** US A2P requires 10DLC brand and campaign
  registration — fees, carrier review, weeks not hours. **Order: email → web push → SMS.**
  Web push is free, instant, needs no registration, and is the best fit for the speed
  thesis. SMS probably belongs behind a paid tier.

**Unsubscribe and "I got a job."** Unsubscribe must work without a login — a signed token
in the URL, resolves in one click, no session. Someone who clicks unsubscribe on their
phone and hits a sign-in wall marks you as spam instead. "I got a job!! — end future
alerts" as a second door alongside pause/unsubscribe, in every alert email, rides the
same signed-link mechanism — it turns the highest-signal churn event into outcome data
that is otherwise structurally unavailable.

**§13.2 disposition:** the hosted-form alert request is superseded by real saved
searches. The pattern is retained for feedback (§19.10), including its rejection of
pre-filled GitHub issues.

### 19.8 Account settings

Sections: profile, email, alerts, data, danger zone.

**Email is two fields.** With magic-link auth, `auth.users.email` *is* the credential;
alerts go to `contact_channels`. Changing where alerts land must not change how you log
in. Default the notification channel to the auth email at signup; label them distinctly.
Changing the login email requires confirmation at **both** old and new addresses — enable
Supabase's secure-email-change setting, or a hijacked session locks the owner out
permanently.

**Pause is more important than delete.** Most people who want alerts to stop want a
break, not erasure. A global pause with optional auto-resume absorbs most delete intent
and keeps saves intact for the next search.

**Delete needs a server route.** The client cannot delete a user; that is `service_role`,
so an Edge Function or server route handler.
- `ON DELETE CASCADE` on every user-referencing table so nothing dangles.
- **`events`: null the `user_id`, keep the row.** Deleting rewrites your aggregates
  silently every time someone leaves.
- **7-day grace window** with a cancel link emailed. Accidental deletion is unrecoverable
  and people do it while annoyed.

**Export is easy — build it with delete.** Same tables, one reasoning pass. It is a
feature, not compliance theater: someone tracking 80 applications wants them out when
they land a job.

### 19.9 Application tracker

**Build the tracker; do not build self-report prompts.** Survey prompts produce
unreliable data. A tracker people maintain for their own sake does not — instrumentation
and user benefit become the same object.

**The tracker does not require resume storage.** Application state (posting, applied
date, stage, notes) is low-density PII keyed to `user_id` — arguably less sensitive than
`saved_searches`, which reveals the same "this person is job hunting" fact. The two
questions are fully separable.

**Scope discipline.** Huntr, Teal, and Simplify all do this, and users will expect
reminders, follow-up nudges, and interview scheduling. Build the thinnest version —
status on a card you already render — and let demand pull it further.

**Retention:** age out ~1 year after last update (§19.1).

### 19.10 Feedback button

Persistent control on every page, retaining §13.2's request-an-alert pattern.

**Capture automatically, do not ask:** `page_url` **including the filter query string**
(the highest-value field in the table; it turns "search is broken" into a reproducible
report), `user_agent`, viewport, timestamp, `user_id` if present.

**Ask only for:** free-text body, plus an optional email if anonymous, with a plain
statement of why. **No category dropdown** — it depresses submission rates and 50 items
can be categorised by hand faster than users will do it correctly.

**Anti-abuse:** rate limit per `anon_id` and IP, honeypot, length cap. No CAPTCHA until
spam actually appears; it costs real submissions.

**Routing, no admin UI:** Supabase Database Webhook on insert → Resend → inbox, with body
and full URL. Triage in the email client until volume makes that painful.

**Close the loop.** `status` field, and email the submitter when their suggestion ships.
A write-only feedback button is used once per user. One that visibly produces changes
keeps being used by the people who care most.

**Pre-platform version, i.e. now:** §13.2's hosted form (Tally, Formspree) pre-filled
with the current query string. Zero code, same context capture, migrates cleanly into the
table below when built.

```
feedback (id, user_id?, anon_id, body, page_url, filters_state,
          user_agent, status, admin_notes, created_at)
```

### 19.11 Compensation — see §11.1

Observed compensation history is described fully at §11.1, including which part
(`observed_at`) is already a current build item and which part (display) waits for this
section's era.

### 19.12 Resume — deferred, with the storage/processing split settled

**Storage stays client-side.** Versions, tailored variants, edit history → IndexedDB, or
Origin Private File System for actual blobs. Nothing held server-side. Same category as
§12.6/§19.6.

**Processing transits, never rests.** LLM tailoring means sending resume text somewhere:
- **BYOK** — user's key in IndexedDB, browser calls the provider directly. Zero
  infrastructure, zero cost, excludes non-technical users.
- **Zero-retention proxy** — works for everyone, costs per call, requires real discipline
  because every logging library captures payloads by default.

**Unresolved tension — do not build until settled.** Tailoring makes each application
*slower*. The core thesis is being early in the pile. Both goals are legitimate; they are
not the same product claim and will pull the roadmap apart. A resume editor also does not
compound with the moat the way connections do, and drags in document parsing, ATS-safe
formatting, and PDF/DOCX export.

**Recommendation:** build the client-side storage layer once, use it for connections at
launch, leave it ready. Build the editor only if users say the bottleneck is the resume
rather than the finding.

### 19.13 Instrumentation

**Most of it is already in the schema, once §19.7 exists.** Saved searches show intent.
Dismissals are explicit negative labels. `notifications_sent` shows what was pushed.
Authenticated request frequency gives daily-vs-weekly with zero tracking. Only three
things are genuinely missing: app opens, email-vs-direct arrival, and the outbound apply
click.

**Own the redirect.** Route every posting link — dashboard, email, RSS — through
`/r/{token}`, which logs and 302s. One code path, works in email where JS does not, and
the token encodes surface so email-vs-direct falls out free. Keep it fast; log
asynchronously. This sits on the critical path of the thing the product claims to be good
at, and covers per-card click tracking without per-card instrumentation.

**Skip email open tracking.** Apple Mail Privacy Protection pre-fetches images; opens are
meaningless. Clicks are the only honest email signal.

**Events in Postgres, not a third party.** Shipping GA into this architecture would be
incoherent and drags in cookie consent. `anon_id` in `localStorage`, reconciled to
`user_id` on signup. **RLS insert-only** — users write, only `service_role` reads.

```
events (id, user_id?, anon_id, name, posting_id?, saved_search_id?,
        surface, occurred_at, props jsonb)
```

**Events eat the database faster than postings do.** 1,000 users × 50 events/day ≈
17MB/day at ~350 bytes with index. **Partition by month, roll up to daily aggregates,
drop raw events after 90 days.**

**The metric only this system can compute: median lag from `first_seen_at` to first view,
and to apply click.** No aggregator can compute it — they know when they scraped, not
when the posting went live at the source.

- ~4 hours, against LinkedIn syndication running a day or two behind → the thesis is
  quantified rather than narrated.
- 3 days because people check on weekends → the problem is not discovery latency, it is
  alerting. Better learned before building anything else.

Put this number on the health page (§12.9) once it exists.

### 19.14 Build order, platform era

**Before leave — unchanged from the current build (§1–§18):** M-1 → M4, M10, M8.

**Two things belong in that pre-leave window regardless** (already reflected in §6 and
§11.1, repeated here for the supersession record): `observed_at` on
`posting_comp_tiers`, and Postgres instead of committed SQLite, with the daily
`last_seen_at` rule and a migration tool chosen at M0.

Everything else in this section (§19.1–§19.13) waits. Decide in November, with three
months of live data.

**Effort note:** the 45–75 hour estimate assumed functioning evenings. Against a newborn,
plan for roughly a third and treat more as upside.

### 19.15 Still open — see §17

Rolled into the main open-questions list at §17, items 16–19, to keep one place to look.

---
