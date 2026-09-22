# First Look — Specification

A personal job-search discovery and monitoring tool. Self-contained; assumes no prior
context.

**Read §4 before proposing any design change.** It lists alternatives considered and
deliberately rejected. Do not re-propose them.

**Acceptance criteria live in `CRITERIA.md`.** Lines there are never deleted — only
appended or struck through with a reason.

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
   promised to keep stable* — not simply "external."
5. **Store raw, derive on read.**
6. **No classifiers, no taxonomies, no NLP.** Where grouping is needed, use a
   user-editable alias file (§12.4) or data a source already supplies.
7. **No exception escapes a per-company loop.**
8. **Wrong data is worse than missing data.** An unmapped company is a known gap; a
   wrongly-mapped one is invisible bad data nobody catches for two months.
9. **No personal data in the repository, in committed artifacts, or in run logs.**
   Email addresses, contact lists, and anything identifying a third party live in
   secrets or on the user's own machine. This applies to every milestone, not just the
   ones that obviously touch it.

---

## 4. Rejected alternatives — do not propose these

| Rejected | Why |
|---|---|
| OAuth sign-in, user accounts, a server-side backend | Requires a database, sessions, and a non-Pages deploy target; unwinds every static-hosting decision at once and replaces a cron job with a service to maintain. Solves a problem that starts at ~20 users, not 2–5. |
| A "mission-driven" classifier or scoring field | Irreducibly subjective; guesswork presented as data. The user reviews postings by eye. |
| A preference-tier system encoded as a stored field | Same reason, and incompatible with multiple users holding different preferences. |
| A weighted ranking score | Output is already filtered to "new." Sort by date. |
| Workday adapter | Real endpoint, worst effort-to-yield available: POST bodies, hard 20-item pagination silently returning empty above the cap, a second request per job for a date, Akamai bot management — aimed at enterprises, not growth-stage companies. Backlog only. |
| Workable, Recruitee, Personio adapters | SMB / agency / DACH-European skew. Personio is XML-only. Near-zero expected yield. |
| `jobs.climatebase.org` GraphQL reverse-engineering | ClimateBase supplies only a climate flag, available from the plain-HTML org directory. |
| Wellfound automation | No public API; value behind a login wall; a warmed session is unacceptable maintenance. |
| A circuit breaker disabling a source for N days | One request per company per run. No hammering to prevent. |
| Normalizing the raw location string | `location_raw` is verbatim. A narrow derived classification is permitted (§12.3) but never overwrites it. |
| Scraping LinkedIn, or using any LinkedIn API for connection data | The connection graph isn't exposed by their APIs, and scraping is against their terms and actively defended. §12.6 achieves the goal without it. |
| Storing notify profiles or connection data in the repo | Public repo. See §13.1 and §12.6. |
| Headless browsers anywhere | Every source in scope is reachable with plain HTTP. |

**Deferred pending measurement, not rejected:** SmartRecruiters. A plain documented
unauthenticated GET, roughly as simple as Greenhouse — the effort argument ruling out the
others doesn't apply. Included in **detection** from day one (§8); the polling adapter is
written only if the count justifies it.

---

## 5. Architecture

```
DISCOVERY          one-time before leave; monthly after
  Manual watchlist · Getro VC boards · ClimateBase orgs · Built In Boston
        │  dedupe on canonical_domain
        ▼
ATS MAPPING        one-time per company; retried monthly on failure
  slug guess → apply-redirect → careers-page regex → classified failure
        ▼
MONITORING         ~4x daily, GitHub Actions
  Greenhouse · Lever · Ashby board APIs → diff → postings
  Getro boards (independent path — needs no mapping)
        ▼
OUTPUT
  Dashboard + health page (Pages) · RSS · email alerts
```

**Two independent workflows.** `monitor.yml` (~4x daily) and `discover.yml`
(manual/monthly). A crash in fragile discovery code must not take down monitoring. Both
carry `workflow_dispatch`.

Cron is UTC and has no DST handling — wall-clock times shift by an hour when DST ends
mid-leave. Expected, not a bug.

---

## 6. Data model

SQLite committed each run alongside JSON exports. Git provides versioned, revertible
state for free.

```sql
CREATE TABLE companies (
  id                        INTEGER PRIMARY KEY,
  canonical_domain          TEXT UNIQUE,
  name                      TEXT NOT NULL,
  is_climate                INTEGER DEFAULT 0,
  industry_tags             TEXT,            -- JSON array, raw
  has_open_roles_signal     INTEGER DEFAULT 0,
  ats_provider              TEXT,
  ats_token                 TEXT,
  ats_status                TEXT DEFAULT 'unmapped',  -- unmapped|ok|failing|unmappable
  mapping_confidence        TEXT,            -- verified|probable|weak
  mapping_method            TEXT,
  mapping_failure_reason    TEXT,            -- §8.4
  mapping_last_attempt_at   TEXT,
  ats_last_success_at       TEXT,
  ats_consecutive_failures  INTEGER DEFAULT 0,
  last_nonzero_postings_at  TEXT,
  created_at                TEXT NOT NULL
);

CREATE TABLE company_sources (
  company_id            INTEGER NOT NULL REFERENCES companies(id),
  source                TEXT NOT NULL,   -- builtinboston|climatebase|getro|manual
  source_id             TEXT,
  source_metadata_json  TEXT,
  PRIMARY KEY (company_id, source)
);

CREATE TABLE postings (
  id                     INTEGER PRIMARY KEY,
  company_id             INTEGER NOT NULL REFERENCES companies(id),
  ats_job_id             TEXT NOT NULL,
  source_path            TEXT NOT NULL,   -- 'ats' | 'getro'
  title_raw              TEXT NOT NULL,
  department_raw         TEXT,
  location_raw           TEXT,            -- verbatim, never overwritten
  workplace_type_raw     TEXT,            -- Ashby's structured field
  location_class         TEXT,            -- derived §12.3: remote|hybrid|onsite|unknown
  city_raw               TEXT,            -- first comma-token of location_raw
  url                    TEXT,
  first_seen_at          TEXT NOT NULL,   -- THE date: sort key and "Posted" filter
  last_seen_at           TEXT NOT NULL,
  closed_at              TEXT,
  posted_at              TEXT,            -- ATS date, informational only
  content_hash           TEXT,
  is_repost              INTEGER DEFAULT 0,
  comp_data_quality      TEXT DEFAULT 'none',
  comp_raw_summary       TEXT,
  comp_best_annual_usd   INTEGER,
  comp_floor_annual_usd  INTEGER,
  comp_tier_count        INTEGER DEFAULT 0,
  UNIQUE (company_id, ats_job_id)
);

CREATE TABLE posting_comp_tiers (
  id, posting_id REFERENCES postings(id),
  tier_label, min_amount, max_amount, currency,
  period           -- year|month|week|hour
);

CREATE TABLE runs (
  id, started_at, finished_at,
  companies_polled, http_ok, http_err,
  total_live_postings, new_postings
);

CREATE TABLE notifications_sent (
  posting_id   INTEGER NOT NULL REFERENCES postings(id),
  profile      TEXT NOT NULL,   -- profile NAME only, never an email address
  sent_at      TEXT NOT NULL,
  PRIMARY KEY (posting_id, profile)
);
```

**`notifications_sent.profile` stores a short name, never an address.** This table is
committed to a public repo.

**`canonical_domain`:** lowercase, strip protocol, `www.`, path, query params. Needs a
null-domain fallback (normalized name, flagged) and a manual merge hatch.

**`first_seen_at` is the canonical date** for sorting and the "Posted" filter.
`posted_at` is unreliable — Greenhouse's list endpoint exposes only `updated_at`, which
mutates on any edit. The UI says **"Found 6h ago"**, which is what the number means.

---

## 7. Discovery sources

Each yields `(name, domain, source_id, raw_metadata)`. Dedupe on `canonical_domain`.
Appearing in multiple sources is a mild positive signal.

### 7.1 Manual watchlist
`config/watchlist.yml`, name + domain. Highest signal per unit of effort. Committed —
acceptable, it's a list of companies.

### 7.2 Getro / VC portfolio boards — discovery *and* monitoring
`config/getro_boards.yml`, ~10–15 climate and energy VC boards (Energy Impact Partners,
Congruent, Powerhouse, Breakthrough Energy Ventures, Elemental Excelerator).

Next.js apps: data lives in the `__NEXT_DATA__` JSON of the server response. Parse
directly. Shape is community-derived, not documented — verify against two or three
boards first.

**Two roles.** These boards already aggregate postings from portfolio companies' own
ATSes, so polling them yields *postings* **without requiring ATS mapping to have
succeeded** — an independent path covering the highest-value population regardless of
mapping coverage.

- Poll alongside ATS adapters; write with `source_path = 'getro'`.
- Where a company is also ATS-mapped, the ATS row is authoritative. Dedupe on
  `content_hash`, prefer `'ats'`.
- Getro data is thinner: refresh lag, weaker comp, unreliable dates. Safety net, not
  replacement.

### 7.3 ClimateBase organization directory
`climatebase.org/organizations`, ~7,250 orgs, server-rendered, one-time crawl. **Sole
purpose: `is_climate` and sector tags.** Do not touch `jobs.climatebase.org`.

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

### 7.5 Wellfound — not automated
No public API; value behind login; a warmed session is unacceptable maintenance. Manual
saved search. Worth checking whether native email alerts exist.

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

### 8.5 Retry
Failed mappings retry monthly on the cold path. Failure is not permanent.

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
List returns only `updated_at`, which mutates on any edit. True `first_published` and
`payInputRanges` come only from the detail endpoint. Department via `departments`.

### Lever — [hire.lever.co/developer/documentation](https://hire.lever.co/developer/documentation)
```
GET api.lever.co/v0/postings/{site}?mode=json
```
Full board in one call. **The linked docs cover the authenticated v1 Data API; the public
v0 Postings API used here is not officially documented.** Undocumented `createdAt` (epoch
ms), reliable in practice. `salaryRange` when disclosed. Department via `categories.team`.
v1's rate limits don't apply.

### Ashby — [developers.ashbyhq.com/docs/public-job-posting-api](https://developers.ashbyhq.com/docs/public-job-posting-api)
```
GET api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true
```
Full board, no pagination. `publishedAt` directly. **The only provider exposing a
structured `workplaceType`** — store in `workplace_type_raw`. Compensation returns
`compensationTiers` with a human-readable summary string rather than separated numerics.

### SmartRecruiters — [developers.smartrecruiters.com/docs/endpoints](https://developers.smartrecruiters.com/docs/endpoints)
```
GET api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings
```
Documented, public, no auth. **Detection from day one**, so companies land in the
measurement rather than the failure bucket. **Polling adapter only if the count justifies
it** (§17.4).

### Getro
No documentation of any kind. `__NEXT_DATA__` shape is community-derived.

### Webhooks are unavailable
All ATS webhook systems live on the authenticated recruiting API, provisionable only by
the hiring company. Polling is the only option; structural.

---

## 10. Posting lifecycle

Per company, per run:

1. Fetch the live board.
2. **New** `ats_job_id` → insert, set `first_seen_at` / `last_seen_at`; Greenhouse detail
   call *only here*.
3. **Still present** → update `last_seen_at`.
4. **Absent but previously present** → set `closed_at`.
5. **Reappearing** → `content_hash` matching a posting closed within ~90 days sets
   `is_repost`. Surface it; a reopened role is signal.

Getro postings follow the same lifecycle with `source_path = 'getro'`, deduped against
ATS rows by `content_hash` with ATS preferred.

**Seed mode:** an explicit flag populates without producing new-posting output or sending
any email. Without it, the first run emails thousands of postings.

**Comp backfill:** companies add ranges *after* publishing. Each run, re-fetch details
where `comp_data_quality = 'none' AND closed_at IS NULL AND age < 30 days`. Scoping by
comp status rather than date keeps this cheap — it's the only set a refresh can change.

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

**Never drop a row for missing comp.** Undisclosed is a first-class state.

Bonus and equity are not modeled — free text in every ATS studied. Keep whatever appears
in `comp_raw_summary` and display it.

---

## 12. Interface

Static site on GitHub Pages, regenerated and committed each run. Public, with **no
personal name, no author attribution, and no identifying detail** — see §15.

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
hidden, plus an export button. Per-browser conveniently means per-user.

### 12.3 Location classification — derivation deferred by design

`location_raw` is verbatim and never overwritten. `location_class` is narrow and derived:

- **Ashby** → from structured `workplace_type_raw`.
- **Greenhouse / Lever** → narrow keyword match on the raw string for remote and hybrid.
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
- Connection count (§12.6) when connection data has been loaded, otherwise absent.
- Repost badge where applicable. `×` dismisses.

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

Nothing is committed, nothing is transmitted, and it is per-user by construction — each
person uploads their own and sees their own numbers. This is not merely the user's own
privacy: the export contains hundreds of other people's employment data, which is not the
user's to publish.

`Connections.csv` and `connections*.json` are gitignored **from day one, before the
feature exists.**

Matching is fuzzy company-name-to-company-name and will be imperfect; a small
`config/company_aliases.yml` absorbs the common cases, same pattern as §12.4.

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
`jobs-recent.json`, shard by month. Don't build sharding before §17.1 says which regime
applies.

### 12.9 Health page
Behind the hamburger. Run history, `last_successful_run`, companies polled, live postings,
failing companies by name and reason, mapping coverage by `ats_status` /
`mapping_confidence` / `mapping_failure_reason`, recent run summaries. **No email
addresses, no profile contents** — see §15.

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

### 13.2 Alert requests — self-serve without a backend

The dashboard's "Get email alerts for this view" button opens a hosted form (Tally,
Google Forms, Formspree — all free) pre-filled with the current filter query string. The
submission goes to the maintainer's inbox, who pastes an updated JSON into the secret.

This is **request-an-alert, not true self-serve.** True self-serve requires a server able
to write on a stranger's behalf, which is the rejected OAuth path in §4. This gets most of
the UX at none of the infrastructure cost and scales to a handful of people.

**Do not use a pre-filled GitHub issue for this.** It requires a GitHub account and would
publish the requester's email address on a public repository.

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
into an email for free.

**Readable run summary as the final output of every run.** GitHub's failure email is a
fixed template linking to the run log, so the last twenty lines must answer "what's
wrong": companies polled, new postings, failing companies by name and reason, anomaly
status.

**The run summary must never print personal data.** Workflow logs are world-readable on
public repos. Report "2 profiles matched, 5 alerts sent" — never an address, never which
profile received what.

**No exception escapes the per-company loop.** The most important line of code in the
system and the easiest to omit — everything works until one company returns malformed JSON
and the result is zero postings for a month.

**Checkpoint discovery crawls. Pin everything** — Python version, lockfile, Action SHAs.

**Burn-in before leave:** two weeks of scheduled runs, breaking things deliberately and
confirming each alert arrives. Untested alerting is not alerting.

---

## 15. Hosting and public-repo posture

**GitHub Free, public repository, GitHub Pages.** Pages serves from public repos on Free,
and Actions minutes are unmetered on public repos, so run frequency costs nothing.

**Building in public is an accepted, deliberate choice.** The posture is low-profile
rather than hidden: discovery is fine, advertisement is not.

- Neutral repository name. No README tying the project to a person. No personal name on
  the dashboard or in commits beyond the git identity. Not pinned on the owner's profile.
- `config/watchlist.yml` is committed and readable. Accepted.
- `mapping_review.csv`, `jobs-*.json`, and `jobs.db` contain public company and posting
  data. Fine.

**What may never be committed or logged**, because it is other people's data rather than
the owner's to accept risk on:

| Item | Handling |
|---|---|
| Notification emails and filters | `NOTIFY_PROFILES` secret (§13.1) |
| LinkedIn connection data | Local only; localStorage; gitignored (§12.6) |
| Anything in Actions run logs | Counts, never identities (§14) |
| `DEVLOG.md` | Reviewed periodically for incidental personal detail |

```
permissions: { contents: write }
concurrency: { group: monitor, cancel-in-progress: false }
```

The concurrency group prevents overlapping runs conflicting on a binary SQLite file.

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

---

## 17. Open questions

1. **Cascade coverage** — what fraction reach `verified` or `probable`. The single number
   determining whether the system is worth its crawl; also sets §12.8's payload regime.
2. **Failure-reason distribution** — `unsupported_ats` (build adapters) vs.
   `js_rendered` / `weak_only` (improve mapping).
3. **Slug-guess false-positive rate** against watchlist ground truth. If the negative
   guard is insufficient, tighten to `verified`-only.
4. **SmartRecruiters volume** — decides whether the adapter is written.
5. **Real `location_raw` and `department_raw` distributions** — determines §12.3 rules and
   seeds §12.4 aliases.
6. **Getro `__NEXT_DATA__` shape** — verify against two or three boards.
7. **Built In Boston anti-bot posture** at crawl volume — 20–50 requests first.
8. **Real comp disclosure rate.** Pay transparency laws in Massachusetts, Colorado, New
   York, California and Washington suggest most remote US postings disclose, but the
   actual rate determines the comp filter's usefulness.
9. **LinkedIn company-name match rate** — how often an export's employer string matches a
   `companies` row, and how much `company_aliases.yml` is needed.
10. Whether Wellfound offers native saved-search email alerts.
