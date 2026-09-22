# SPEC Revision 02 — Platform, accounts, and user state

**Applies to:** `SPEC.md`
**Companion to:** `SPEC-REVISION-01.md` (aggregators become company sources)
**Supersedes:** `PLATFORM-NOTES.md` — that file is now history; this one is authoritative.
**Setup:** `SETUP-PLATFORM.md`

**Convention:** as in `CRITERIA.md`, nothing is silently deleted. Every supersession names
the section it replaces and why.

**Build order note.** §R14 splits this into what to build before parental leave and what
waits. Do not build §5–§12 during the accelerated path.

---

## R0. Supersession map

Read this first. Everything else is detail.

| `SPEC.md` section | Status | Where |
|---|---|---|
| §3.9 no personal data anywhere | **EXTENDED** | §1 — personal data now exists, in one tiered place |
| §4 OAuth / accounts / backend rejection | **SUPERSEDED** | §2 |
| §4 Wellfound rejection | **STRUCK** | `SPEC-REVISION-01.md` §R2 |
| §6 committed SQLite | **SUPERSEDED** | §3 |
| §6 `postings` table | **AMENDED** | §3.3 hot/cold split |
| §6 `posting_comp_tiers` | **AMENDED** | §4 — add `observed_at` |
| §6 `notifications_sent` | **REPLACED** | §7.1 |
| §10 step 3 (`last_seen_at` each run) | **SUPERSEDED** | §3.2 — daily, not 4x |
| §10 step 5 (repost via 90-day hash) | **AMENDED** | §3.3 — `posting_hashes` |
| §11 compensation | **EXTENDED** | §4 — observed history |
| §12.2 filters | **EXTENDED** | §6.3 |
| §12.2 dismissal in `localStorage` | **SUPERSEDED** | §6.1 — server-side |
| §12.5 cards | **EXTENDED** | §6.1, §6.2 |
| §12.6 LinkedIn connections | **RETAINED, UX REVISED** | §11 |
| §12.8 payload sharding | **SUPERSEDED** | §2 — DB queries replace static JSON |
| §13.1 `NOTIFY_PROFILES` secret | **SUPERSEDED** | §7 |
| §13.2 request-an-alert form | **SUPERSEDED for alerts; PATTERN RETAINED for feedback** | §7, §10 |
| §14 reliability | **RETAINED** | §3.1 — DB outage is a *loud* failure |
| §15 hosting / public-repo posture | **SUPERSEDED in platform era** | §2 |
| §16 keepalive | **OBSOLETE in platform era** | §2 |

---

## 1. Privacy posture — supersedes the absolutism of §3.9

§3.9 says no personal data in the repository, in committed artifacts, or in run logs.
**That rule is retained verbatim for the repo.** What changes is that personal data now
exists somewhere: in Postgres, behind RLS.

The question is not whether PII can be secured. It is what each item costs to hold.

| Tier | Items | Handling |
|---|---|---|
| **Never server-side** | LinkedIn connection export; resume files | Client-side only, permanently (§11, §12) |
| **Transits, never rests** | Resume text sent for LLM tailoring | Zero-retention proxy or BYOK (§12) |
| **Normal table + retention** | Applications, saves, saved searches, contact channels | RLS default-deny; auto-age; export + delete |
| **Public** | Companies, postings, comp observations | Employer-published |

**The control that matters for application history is retention, not encryption.** The
damage from a leak here is not identity theft — it is that people get fired for job
hunting. Age applications out ~1 year after their last update.

**Realistic breach path is a table shipped with RLS off, or `service_role` reaching the
frontend.** Not disk theft. Spend effort accordingly:
- Every table starts with RLS enabled and default-deny. **CI check**, in the same spirit
  as §15's existing guards.
- The anon key is public by design. RLS is the *only* barrier between a stranger and
  users' addresses.
- `service_role` never leaves GitHub Actions and server-side routes.
- Application-layer encryption is **not** recommended — it breaks queryability and
  defends the wrong threat.

**Export and delete are features, not compliance theater** (§9.4).

---

## 2. Platform architecture — supersedes §4 OAuth rejection, §12.8, §15, §16

### 2.1 The §4 rejection is stale, not wrong

> Rejected: *OAuth sign-in, user accounts, a server-side backend. Requires a database,
> sessions, and a non-Pages deploy target…*

Three problems in 2024; one managed service in 2026. Supabase Auth collapses database,
sessions and deploy target into the Postgres instance already required by §3. Record as
superseded in `CRITERIA.md`, not as an error.

### 2.2 Stack

| Layer | Choice | Note |
|---|---|---|
| Compute | GitHub Actions, **unchanged** | The pipeline does not change |
| Storage | Supabase Postgres | §3 |
| Read layer | Next.js on Vercel, server components | No API layer to write |
| Auth | Supabase Auth — Google + magic link | §8 |
| Email | Resend — alerts *and* auth SMTP | One domain reputation |

**Supabase is not an OAuth provider alongside Google.** It is the layer that runs
providers. The choice is which methods to enable inside it.

### 2.3 What this obsoletes

- **§12.8 payload sharding.** `jobs-recent.json` / `jobs-archive.json` and the 3MB
  sharding rule exist because a static site can't query. Server components query
  Postgres directly. Retain §12.8 only while Pages is live.
- **§15 public-repo posture.** Retained for the *pipeline* repo. The web app is a
  separate deploy; the reasoning about world-readable artifacts no longer covers user
  data, which is in Postgres.
- **§16 keepalive.** The 60-day workflow-inactivity concern belongs to the Pages era.
  Note the *new* equivalent in §3.1.

### 2.4 Migration order

Storage first. This is an **M4-era problem, not a 10k-company one**: git does not
delta-compress binaries, so a ~30MB DB committed 4x/day is ~120MB of repo growth daily —
a gigabyte inside a month at 2,000 companies, during the unattended window.

1. SQLite → Postgres. Pages keeps running off exported JSON. Nothing user-visible.
2. Next.js read layer alongside Pages until parity, then cut over.
3. Auth + per-user state (§6). Saves and dismissals leave `localStorage`.
4. Alerts from `saved_searches` (§7), retiring `NOTIFY_PROFILES`.
5. Applications (§9), instrumentation (§13), feedback (§10).

---

## 3. Storage — supersedes §6 committed SQLite and §10 step 3

### 3.1 Postgres from the start

**Why the network dependency is acceptable.** A DB outage fails the run, which exits
non-zero, which emails (§14). That is a *loud* failure — precisely what §3.3 asks for.
The criterion was never zero dependencies, it was no *silent* ones.

**Accepted costs:**
- Loss of `git checkout` on state. Managed backups only partly cover it; free-tier
  retention is short.
- **Migration discipline from M0.** "Delete the file and re-seed" stops being the answer.
  Expect several schema changes early — §12.3 and §12.4 are explicitly designed to be
  written after seeing real facet data. Pick a migration tool at M0, not M6.

**Bonus:** §15's concurrency group exists to stop overlapping runs corrupting a binary
SQLite file. With transactions that concern largely evaporates. Keep the group anyway;
it costs nothing.

**New unattended risk, replacing §16's:** Supabase pauses Free Plan projects after ~7 days
of low activity; paid projects are not paused. Detection looks at real queries and writes,
so a 4x/day poller keeps it alive trivially. The pause only bites if the monitor is
*already* dead for a week. **Pay for Pro during the leave months** — it removes a
compounding failure in the window where the operator is least reachable.

*Verify current pause, backup and Data API grant policies directly; these terms change.
An explicit Postgres grants requirement for the Data API rolls out to existing projects
from 2026-10-30.*

### 3.2 Write amplification — supersedes §10 step 3

§10 step 3 updates `last_seen_at` on every still-present posting every run. At 80k live
postings × 4 runs that is 320k dead tuples per day on a shared-CPU instance. **You would
hit the storage cap on garbage, not data.**

**Supersede with:**
1. **Update `last_seen_at` once per day**, not on all four runs. Closure detection needs
   same-day accuracy, not six-hour precision. New postings still insert on every run —
   that is where latency matters and it is unaffected.
2. **Never index `last_seen_at`. Set `fillfactor` ~85** on `postings` so updates stay HOT.
3. If bloat persists, move the column to `posting_liveness(posting_id, last_seen_at)`.

### 3.3 Hot / cold split, and the repost catch

**Budget: ~500k posting rows per 500MB.** ~450 bytes heap + ~300 index ≈ 800 bytes; round
to 1KB for bloat headroom. **Rows scale with churn, not poll frequency** — a still-present
posting is an update, not an insert.

- `postings` — open, plus closed <30 days. Fully indexed. Serves the dashboard.
- `postings_archive` — closed ≥30 days. Drop `url` (dead link) and `content_hash`. One
  index, `(company_id, department_raw)`. ~350 bytes/row.

**Archive by `closed_at`, never by `first_seen_at`.** A role open 60 days is still
applicable; archiving by posting date would hide live jobs. The 30-day rule aligns with
§12.2's "Posted" ceiling, so the hot table is close to exactly what the dashboard serves.

**Catch — supersedes §10 step 5.** Repost detection matches `content_hash` against
postings closed within ~90 days. A 30-day archive breaks that **silently**. Add:

```sql
CREATE TABLE posting_hashes (
  content_hash  TEXT NOT NULL,
  company_id    INTEGER NOT NULL REFERENCES companies(id),
  closed_at     TEXT,
  PRIMARY KEY (content_hash, company_id)
);
```

Outlives the archive move; cheaper than indexing `content_hash` on the archive.

**Never archive a posting with a dependent user row** — any save or application. A
shortlist that degrades to a dead link and half a card reads as a bug. See §6.4.

**`postings_archive` rows are never purged** for any posting with a dependent user row.
Write this down: otherwise someone later adds a cleanup job and quietly breaks the
tracker's history.

**`posting_comp_tiers` rows are never dropped or trimmed.** They are the asset (§4).

### 3.4 Descriptions — not stored now, sampled later

Descriptions are available (Greenhouse `content=true`, Lever `description`, Ashby
`descriptionHtml`) and deliberately discarded. Keeping them makes a row 5–8KB; 80k live
postings would be 400MB+ — the whole free tier, in text nobody may read. **This is why
cards link out** (§6.1).

Two distinct future features with **opposite retention rules** — do not conflate:

| | Purpose | Retention |
|---|---|---|
| **Display cache** | Expandable drawer on a card | Fetch on demand via server proxy (CORS blocks direct browser calls); cache ~7 days; scales with *attention*, not corpus |
| **Sampled archive** | Requirement drift by title/location over time | A few hundred per title cluster per quarter, retained permanently. Tens of MB/year |

Note lightly: description text is the employer's copyrighted content. Fetching on request
for display sits differently from building a searchable archive of everyone's job
descriptions. Be deliberate rather than drifting.

---

## 4. Compensation — extends §11

**Add `observed_at` to `posting_comp_tiers`.** Treat §10's comp backfill as *appending an
observation*, not overwriting. A mid-posting range edit is signal; overwriting destroys it
silently. **Make this change before any data is collected — it is unrecoverable later.**

**Observed comp history.** Transparency laws mean companies disclose on some reqs and not
others. Polling the same companies daily accumulates real observed comp per company and
function, with a time dimension — you can see whether a band *moved*. No aggregator can
replicate this without polling at the source over time. Treat it as the differentiator.

**Guardrails:**
- Display observations and their count. **Never** emit an estimate, midpoint or predicted
  band — that is §4's scoring rejection in a new costume.
- **Observed history never satisfies a numeric filter.** A posting matching on a
  neighbour's salary is wrong data; §3.8 applies.
- Card treatment: where comp is undisclosed and the company has ≥3 prior observations in
  the same function, show the history beneath the muted "comp not disclosed" line,
  labelled as history.

---

## 5. Auth — new

**Passwordless only. Nobody remembers a password.**

- **Google** — primary in the UI, instant.
- **Magic link** — beneath it, for people without a Google account. Doubles as email
  verification for alerts (§7.2).
- No GitHub. It skews technical; the target user is a climate PM.

**Anonymous-first.** Do not gate the first click.

1. Anonymous saves and dismissals write to `localStorage`, keyed by the same `anon_id`
   used for events (§13).
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

**Configuration that must be deliberate** (details in `SETUP-PLATFORM.md`):
- **Identity linking.** Same email via magic link and Google must resolve to one account.
  The failure mode is two accounts, one holding all their saves — experienced as you
  losing their data.
- **Magic-link rate limits and short expiry.** Otherwise the endpoint is a way to send
  mail from your domain to arbitrary addresses.
- **Custom SMTP → Resend.** Supabase's built-in mailer is development-grade.

**The anonymous → authenticated migration is the highest-risk small feature here.** It
runs once per user, silently, and if it drops rows nobody reports it because they do not
know what they lost. Test deliberately.

---

## 6. Card state and filters — extends §12.2 and §12.5

### 6.1 Card states

Four states plus a badge. **Every state needs a non-color signal** — a label or icon.
Four greys plus a green wash fails for colorblind users and collapses in dark mode.

| State | Trigger | Treatment |
|---|---|---|
| **Viewed** | Clicked through | Marker, **not** a downgrade — left border or "viewed" tag, unchanged text weight |
| **Not interested** | Button | Dimmed, strongest grey. *This is §12.2's dismissal, moved server-side* |
| **Applied** | Button | Dimmed, green tint, label |
| **Saved** | Button | **Accent, never dimmed** — highest-intent state in the system |

**Do not reuse dim for "opened."** Dimming on click-through conflates "I looked at this"
with "I'm done with this" — opposite meanings. Someone fires off five tabs, works through
them, returns, and the two worth applying to look identical to the three rejected.

**Click behavior:** open in a **background tab** so the filtered list survives, mark
viewed, apply the viewed treatment. The multi-tab scan is the power-user pattern and most
of the felt speed.

**Applied needs an honest bridge.** Clicking through is not applying. Once a card has been
opened and left unmarked for a while, show a quiet affordance — "opened 2h ago · applied?"
— one click to resolve. Do not prompt on return; that is nagging.

**Save is a shortlist**: jobs the user wants to apply to but has no time for now. Fully
orthogonal to the others — someone can save *and* apply. Give it a nav destination, not
just a filter; it is somewhere you go.

### 6.2 The New badge, and two visit timestamps

**Store two columns, not one:** `previous_visit_at` and `current_visit_at`. Render badges
against `previous_visit_at`; write `current_visit_at` on session start. With a single
column updated on load, badges vanish on arrival or the list shifts mid-scroll.

**Badge** = `first_seen_at > previous_visit_at` AND not clicked. Time-windowed so it means
"new"; click-clearing so it behaves as described. Next visit rolls the window.

**"Seen" means clicked, never rendered.** Viewport tracking would generate an event per
card per scroll — the volume problem in §13.

**First-session suppression.** When `previous_visit_at IS NULL`, suppress badges entirely
and set the column when that first session ends. Otherwise every card in the database is
technically new on the one occasion the badge is most likely to be dismissed as noise.
Same reasoning as §10's seed mode.

**Cap the window at ~14 days** regardless of actual last visit. Someone returning after
two months should not see a badge on everything; past a couple of weeks "what changed
since I looked" has stopped being a useful question.

### 6.3 Filters — extends §12.2

**Tri-state controls, not five checkboxes.** Only-applied and exclude-applied are mutually
exclusive; as checkboxes a user can tick both and get zero results with no indication why
— the same failure §12.2 already calls out for the undisclosed-salary toggle.

| Control | Positions |
|---|---|
| Applied | show all / **hide applied (default)** / only applied |
| Not interested | show all / **hide (default)** / only |
| Unopened | off / **only unopened** |

Defaulting both to hide is the point: the list you land on is everything you have not dealt
with. "Only applied" doubles as the application tracker view for free.

**Unopened is click-based and persistent** — the backlog view, everything never got to,
regardless of when it landed. Distinct from the badge, which is time-windowed. Do not
merge them.

Consider making unopened-plus-recent the **default landing view**.

### 6.4 Save expiry — no episodes table

A shortlist should not persist across job searches. Rejected as overengineering: a
`searches` episode table with start/end and an "I got a job" flow.

**Implemented instead:** one nullable `saves.expires_at`, set 90 days out on save, pushed
forward on any interaction with that row.

- **Expiry hides, never deletes.** This rule will be wrong for some users; a hidden save
  is recoverable, a deleted one is not. Same storage either way.
- **Gap prompt, independent of the rule.** Returning after months: "you have 23 saved jobs
  from your last search — keep or clear?" One question, no inference, covers the cases the
  timer guesses wrong.
- **Saved + closed** shows as closed rather than disappearing: struck title, "closed 12
  days ago," link disabled. A saved job that closes is also worth a nudge — "2 of your
  saved jobs closed this week" — which is honest, actionable, and direct evidence for the
  speed thesis.

---

## 7. Alerting — supersedes §13.1 and §13.2

### 7.1 Schema

```
profiles            (id → auth.users, timezone, previous_visit_at,
                     current_visit_at, created_at)
contact_channels    (id, user_id, kind, address, verified_at, is_active)
saved_searches      (id, user_id, name, filters jsonb, created_at)
alert_subscriptions (id, saved_search_id, channel_id, cadence, quiet_hours, is_active)
notifications_sent  (posting_id, subscription_id, sent_at)   -- replaces §6 table
saves               (user_id, posting_id, saved_at, expires_at)
dismissals          (user_id, posting_id, dismissed_at)
applications        (id, user_id, posting_id, status, applied_at, notes, updated_at)
```

**Searches and subscriptions are separate tables.** A saved search is useful alone — the
"click it and see results" case. A subscription turns one into notifications. Splitting
them lets one search fire to email *and* push without duplicating filters.

`filters` as `jsonb` **preserves §3.1**: no user criterion in pipeline code; the matcher
reads whatever is there generically. Same principle as `NOTIFY_PROFILES`, in a table.

§6's `notifications_sent` stored a profile *name* to keep addresses out of a public repo.
That constraint is gone; key on `subscription_id`.

### 7.2 Three things that bite if skipped

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

### 7.3 Unsubscribe and "I got a job"

**Unsubscribe must work without a login.** Signed token in the URL, resolves in one click,
no session. Someone who clicks unsubscribe on their phone and hits a sign-in wall marks
you as spam instead. Major providers now require one-click unsubscribe for bulk senders;
implement it well below that threshold.

**"I got a job!! — end future alerts"** as a second door alongside pause/unsubscribe, in
every alert email. It arrives at the moment the user is actually thinking it, rather than
asking them to visit a site they have stopped visiting. Costs one button; turns the
highest-signal churn event into the outcome data that is otherwise structurally
unavailable. Rides the same signed-link mechanism.

### 7.4 §13.2 disposition

The hosted-form alert request is **superseded** by real saved searches. **The pattern is
retained for feedback** (§10), including its rejection of pre-filled GitHub issues.

---

## 8. Account settings — new

Sections: profile, email, alerts, data, danger zone. Four non-obvious things:

**Email is two fields.** With magic-link auth, `auth.users.email` *is* the credential;
alerts go to `contact_channels`. Changing where alerts land must not change how you log
in. Default the notification channel to the auth email at signup; label them distinctly.
Changing the login email requires confirmation at **both** old and new addresses — enable
Supabase's secure-email-change setting, or a hijacked session locks the owner out
permanently.

**Pause is more important than delete.** Most people who want alerts to stop want a break,
not erasure. A global pause with optional auto-resume absorbs most delete intent and keeps
saves intact for the next search.

**Delete needs a server route.** The client cannot delete a user; that is `service_role`,
so an Edge Function or server route handler.
- `ON DELETE CASCADE` on every user-referencing table so nothing dangles.
- **`events`: null the `user_id`, keep the row.** Deleting rewrites your aggregates
  silently every time someone leaves.
- **7-day grace window** with a cancel link emailed. Accidental deletion is unrecoverable
  and people do it while annoyed.

**Export is easy — build it with delete.** Same tables, one reasoning pass. It is a
feature, not compliance theater: someone tracking 80 applications wants them out when they
land a job.

---

## 9. Application tracker — new

**Build the tracker; do not build self-report prompts.** Survey prompts produce unreliable
data. A tracker people maintain for their own sake does not — instrumentation and user
benefit become the same object.

**The tracker does not require resume storage.** Application state (posting, applied date,
stage, notes) is low-density PII keyed to `user_id` — arguably less sensitive than
`saved_searches`, which reveals the same "this person is job hunting" fact. The two
questions are fully separable.

**Scope discipline.** Huntr, Teal and Simplify all do this, and users will expect
reminders, follow-up nudges and interview scheduling. Build the thinnest version — status
on a card you already render — and let demand pull it further.

**Retention:** age out ~1 year after last update (§1).

---

## 10. Feedback button — new, retains §13.2's pattern

Persistent control on every page.

**Capture automatically, do not ask:** `page_url` **including the filter query string**
(§12.2 already encodes filter state — this is the highest-value field in the table; it
turns "search is broken" into a reproducible report), `user_agent`, viewport, timestamp,
`user_id` if present.

**Ask only for:** free-text body, plus an optional email if anonymous, with a plain
statement of why. **No category dropdown** — it depresses submission rates and you can
categorise 50 items by hand faster than users will do it correctly.

**Anti-abuse:** rate limit per `anon_id` and IP, honeypot, length cap. No CAPTCHA until
spam actually appears; it costs real submissions.

**Routing, no admin UI:** Supabase Database Webhook on insert → Resend → inbox, with body
and full URL. Triage in the email client until volume makes that painful.

**Close the loop.** `status` field, and email the submitter when their suggestion ships. A
write-only feedback button is used once per user. One that visibly produces changes keeps
being used by the people who care most.

**Pre-platform version:** §13.2's hosted form (Tally, Formspree) pre-filled with the
current query string. Zero code, same context capture, migrates cleanly into the table.
**Do not use a pre-filled GitHub issue** — §13.2 already rejects this; same reasoning.

```
feedback (id, user_id?, anon_id, body, page_url, filters_state,
          user_agent, status, admin_notes, created_at)
```

---

## 11. LinkedIn connections — §12.6 retained, UX revised

**The rule is unchanged and permanent: never server-side, in any version.** The export
contains hundreds of other people's employment data. Do not move it into the database
merely because a database now exists.

**The §12.6 flow is revised** — download CSV → local Python script → upload JSON is three
steps and a terminal, which means almost nobody does it.

- **Parse the CSV in the browser.** File input, reduce to `{company: count}` in JS. The
  script disappears, and it is *more* private than specced: the reduced JSON no longer
  exists as a file on disk that could be committed or synced by accident. Names live in a
  variable that is garbage-collected on reload.
- **IndexedDB, not `localStorage`** — 5MB and string-only is the wrong tool.
- **`navigator.storage.persist()`** on first save, so the browser does not evict silently.
- **File System Access API** to store a handle to their `Connections.csv`, making refresh
  one click. Chrome/Edge only; keep file input as fallback.
- **Surface staleness** — "connections loaded 47 days ago." A stale count is worse than
  none.

Accepted limitation: per-browser, per-device. That is the price of not holding it.

---

## 12. Resume — deferred, with the storage/processing split settled

**Storage stays client-side.** Versions, tailored variants, edit history → IndexedDB, or
Origin Private File System for actual blobs. Nothing held server-side. This is the same
category as §12.6.

**Processing transits, never rests.** LLM tailoring means sending resume text somewhere:
- **BYOK** — user's key in IndexedDB, browser calls the provider directly. Zero
  infrastructure, zero cost, excludes non-technical users.
- **Zero-retention proxy** — works for everyone, costs per call, requires real discipline
  because every logging library captures payloads by default.

**Unresolved tension — do not build until settled.** Tailoring makes each application
*slower*. The core thesis is being early in the pile. Both goals are legitimate; they are
not the same product claim and will pull the roadmap apart. A resume editor also does not
compound with the moat the way connections do, and drags in document parsing, ATS-safe
formatting and PDF/DOCX export.

**Recommendation:** build the client-side storage layer once, use it for connections at
launch, leave it ready. Build the editor only if users say the bottleneck is the resume
rather than the finding.

---

## 13. Instrumentation — new

**Most of it is already in the schema.** Saved searches show intent. Dismissals are
explicit negative labels. `notifications_sent` shows what was pushed. Authenticated
request frequency gives daily-vs-weekly with zero tracking. Only three things are genuinely
missing: app opens, email-vs-direct arrival, and the outbound apply click.

**Own the redirect.** Route every posting link — dashboard, email, RSS — through
`/r/{token}`, which logs and 302s. One code path, works in email where JS does not, and
the token encodes surface so email-vs-direct falls out free. Keep it fast; log
asynchronously. This sits on the critical path of the thing the product claims to be good
at. It also covers the per-card click tracking without per-card instrumentation.

**Skip email open tracking.** Apple Mail Privacy Protection pre-fetches images; opens are
meaningless. Clicks are the only honest email signal.

**Events in Postgres, not a third party.** Shipping GA into this architecture would be
incoherent and drags in cookie consent. `anon_id` in `localStorage`, reconciled to
`user_id` on signup. **RLS insert-only** — users write, only `service_role` reads.

```
events (id, user_id?, anon_id, name, posting_id?, saved_search_id?,
        surface, occurred_at, props jsonb)
```

**Events eat the database faster than postings do.** 1,000 users × 50 events/day ≈ 17MB/day
at ~350 bytes with index. **Partition by month, roll up to daily aggregates, drop raw
events after 90 days.**

### The metric only this system can compute

**Median lag from `first_seen_at` to first view, and to apply click.** No aggregator can
compute it — they know when they scraped, not when the posting went live at the source.

- ~4 hours, against LinkedIn syndication running a day or two behind → the thesis is
  quantified rather than narrated.
- 3 days because people check on weekends → the problem is not discovery latency, it is
  alerting. Better learned before building anything else.

**Put this number on the health page (§12.9).**

---

## 14. Build order

**Before leave — unchanged from `SPEC.md` plus `SPEC-REVISION-01.md`:**
M-1 → M4, M10, M8. The accelerated unattended monitor.

**Two things from this document belong in that window**, because both are unrecoverable
or structural later:
1. **`observed_at` on `posting_comp_tiers`** (§4).
2. **Postgres instead of committed SQLite** (§3), with the daily `last_seen_at` rule
   (§3.2) and a migration tool chosen at M0.

Everything else in §5–§13 waits. Decide in November, with three months of live data.

**Effort note:** the 45–75 hour estimate assumed functioning evenings. Against a newborn,
plan for roughly a third and treat more as upside.

---

## 15. Still open

1. Resume editor — build at all? (§12 tension unresolved)
2. Whether "apply fast" and "tailor carefully" can coexist as one product claim
3. ClimateTechList partnership response
4. Consider's client-side fetch — endpoint and shape
5. Wellfound company-slug → domain resolution hit rate
6. Everything gated on `SPEC-REVISION-01.md` §R9 measurement
7. Whether the platform happens at all
