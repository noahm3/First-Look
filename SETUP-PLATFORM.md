# First Look — Platform Setup Guide

**Companion to:** `SPEC.md` §6 (Data model — specified as a pre-leave build item, not yet
built) and `SPEC.md` §19 (Platform era — deferred to November+, not yet built).

**Nothing described in this file has been built.** As of this writing the project is
still at the document-consolidation stage — no repository setup, no code, no Supabase
project, nothing. Every step below is a plan, not a status report.

**Relationship to `GETTING-STARTED.md` and `BUILD.md`.** The Postgres/Supabase storage
move described in `SPEC.md` §6 is **not** platform-era work — it's a pre-leave build item
that belongs in milestone M0, unlike everything else in this file which waits for
November. `GETTING-STARTED.md` (account creation) and `BUILD.md` §3/§4 (schema, RLS
baseline for the public tables) are where that part gets built, when M0 happens. **This
guide covers everything else in `SPEC.md` §19** — auth, the Next.js read layer, real
alerting, accounts. Sections below are marked **[Scheduled for M0]** where they belong to
the pre-leave build rather than the deferred platform era, so this file can serve as the
platform-era reference without implying that part is somehow already finished — none of
it is.

**Read this before writing code.** Several steps have waiting periods (DNS propagation,
Google OAuth consent review) that will block you if discovered late.

**A note on specifics.** Dashboard menu paths, free-tier limits and provider requirements
change. Every screen name below is a description, not a promise. Where this guide says
*verify*, verify — do not trust the number written here.

---

## 0. Order of operations

Sequenced by blocking time, not by importance.

| # | Step | Blocks on | When |
|---|---|---|---|
| 1 | Domain + DNS records for email | DNS propagation, hours | When alerting migrates (§19.7) — platform era |
| 2 | Resend account + domain verification | Step 1 | Pipeline alerting will use Resend (`SPEC.md` §13, built in M10); this second key is for auth mail, platform era |
| 3 | Google Cloud OAuth client | Consent screen review if publishing | When auth starts (§19.5) — platform era |
| 4 | Supabase project | — | **[Scheduled for M0]** — will be created per `BUILD.md` §1.2, §3 |
| 5 | Migration tooling | Step 4 | **[Scheduled for M0]** — chosen per `BUILD.md` §3 |
| 6 | RLS baseline + CI check | Step 5 | **[Scheduled for M0]** for public tables (companies/postings); the user-data policies below wait for accounts to exist, platform era |
| 7 | Actions secrets + pipeline cutover | Steps 4–5 | **[Scheduled for M0]** — see §8 below; there will be no legacy SQLite to migrate, since Postgres is used from the start |
| 8 | Vercel project | Step 4 | When the read layer starts (§19.2) — platform era |
| 9 | Auth wiring | Steps 2, 3, 4 | When accounts start (§19.5) — platform era |
| 10 | Verification checklist (§10) | All | Before any real user |

---

## 1. Domain and DNS

You need a domain you control for auth and alert email. Sending from a shared or unverified
domain lands you in spam immediately, and reputation damage is slow to undo.

Add, per Resend's instructions for your domain:
- **SPF** — TXT record authorising Resend to send.
- **DKIM** — CNAME or TXT records Resend generates.
- **DMARC** — start at `p=none` with a reporting address, then tighten once you see clean
  reports for a couple of weeks. Do not start at `p=reject`; you will silently drop your
  own mail.

Use a **subdomain for transactional mail** (`mail.` or `send.`). It isolates sending
reputation from your main domain, so a bad week does not affect anything else you run.

**This step gates everything email.** Start it first, when you start it; DNS propagation
is the one delay you cannot compress. The pipeline's alert mail (`SPEC.md` §13, built in
M10) is planned to run on Resend without a custom domain — this step is about the
platform era's auth mail and any domain upgrade you might want for alerting too.

---

## 2. Resend

One provider is meant to serve both jobs — alert email (`SPEC.md` §13, built in M10) and,
once auth exists, Supabase Auth's outbound mail. One domain, one reputation, one place to
look when mail is not arriving.

1. Create the account; add and verify the sending domain from §1.
2. Create **two API keys**: one for the pipeline (Actions — used by M10, per
   `SPEC.md` §13), one for the web app. Separate keys mean you can rotate one without
   downtime on the other, and logs tell you which system sent what.
3. Configure a **sending identity** — `alerts@`, `login@` — and a real reply-to that
   reaches you. A no-reply address on a product asking for feedback is a bad signal.
4. Set up the **unsubscribe header** (`List-Unsubscribe` and
   `List-Unsubscribe-Post`) on alert mail. `SPEC.md` §19.7 requires one-click unsubscribe
   that works without a login; this is the header half of it.

*Verify current free-tier send limits. Plan on paying once alerts go to real users.*

---

## 3. Google OAuth client

In Google Cloud Console: create a project, configure the OAuth consent screen, create an
**OAuth 2.0 Client ID** of type Web application.

- **Authorised redirect URI** is Supabase's callback, not your app's. It looks like
  `https://<project-ref>.supabase.co/auth/v1/callback`. Copy it from the Supabase
  dashboard rather than constructing it.
- Add your Vercel preview and production origins as authorised JavaScript origins.
- **The consent screen is the delay.** While in testing mode only listed test users can
  sign in. Publishing may require review depending on scopes. You only need basic profile
  and email, which is the lightest path — but start it early.

Save the client ID and secret for §5.

---

## 4. Supabase project — [Scheduled for M0]

This happens during `BUILD.md` M0, since `SPEC.md` §6 pulled the Postgres migration
forward into the pre-leave build rather than leaving it for the platform era. Nothing
here is done yet as of this writing. Repeated in this file for the platform-era
reference, and because a couple of its decisions are worth re-checking once M0 actually
happens, before real users show up:

1. Project created, region chosen near users, not near you.
2. **Pro plan, not Free**, per `SPEC.md` §16 — Free-plan projects pause after a period of
   low activity, which bites hardest during the exact unattended window this project
   exists for. Decide this at M0 and don't default to Free.
3. Recorded from the API settings:
   - Project URL
   - **anon key** — public by design, safe in the browser, useless without correct RLS
   - **service_role key** — never leaves Actions and server-side routes
   - **Session pooler connection string, port 5432** — not Direct. See point 4.
4. **The pipeline uses the Session pooler (port 5432), not the Direct connection** —
   corrected at M0, 2026-09-23, after the first live migration run failed to connect at
   all. GitHub-hosted Actions runners are IPv4-only, and Supabase's Direct connection is
   IPv6-only on Free-tier projects without the paid IPv4 add-on — an original draft of
   this guide assumed Direct would work for the pipeline and reserved pooling for the
   future web app, which turned out not to hold from Actions specifically. The
   **Transaction pooler (port 6543) is still wrong for the pipeline**: it doesn't support
   prepared statements, which psycopg relies on. Reserve the Transaction pooler for the
   Next.js read layer once it exists (§19.2) — that workload is many short-lived
   serverless connections, which is what the Transaction pooler is actually for; the
   pipeline holds one persistent connection per run and has no need of it.

*An explicit Postgres grants requirement for the Data API rolls out to existing projects
from 2026-10-30. Check whether it affects your project before then.*

---

## 5. Auth configuration

Providers: **Google** (from §3) and **magic link**. No passwords. No GitHub.

Configure deliberately:

- **Custom SMTP → Resend.** Supabase's built-in mailer is development-grade and heavily
  rate-limited. Point Auth at Resend using the web-app API key from §2.
- **Identity linking.** Same email arriving via magic link and Google must resolve to one
  account. Behaviour depends on project settings and on whether the provider reports the
  email as verified. **Configure it, then test it** — the failure mode is a user with two
  accounts, one holding all their saves, experienced as you losing their data.
- **Secure email change.** Require confirmation at **both** old and new addresses.
  Without it, a hijacked session locks the real owner out permanently.
- **Magic-link expiry and rate limits.** Short expiry; per-address and per-IP limits.
  Without them the endpoint is a way to send mail from your domain to arbitrary
  addresses.
- **Redirect allow-list.** Add production and Vercel preview URLs. `SPEC.md` §19.5
  requires returning the user to the filtered list they came from, so the return URL
  carries a query string — confirm your allow-list patterns do not break on it.
- **Email templates.** Replace the defaults. They are the first thing a user sees from
  you and they currently say "Supabase."

---

## 6. Migrations — [Scheduled for M0]

A migration tool needs to be chosen at M0, per `BUILD.md` §3 — "delete the file and
re-seed" is not available once Postgres is the store of record from the start, and
`SPEC.md` §12.3/§12.4 are designed to be written after seeing real facet data, so expect
several schema changes early regardless.

Whatever gets chosen:

- Migrations live in the repo and are applied by CI, never by hand in the SQL editor.
- Every migration is forward-only with an explicit `down` where reversal is plausible.
- Seeding is a separate, idempotent script — not a migration.

**The RLS baseline (§7) should be the first migration**, before the postings tables. It
is much easier to start default-deny than to retrofit it. Confirm this order when M0
actually runs, before any user-data tables (§19.7's schema) get added later.

---

## 7. RLS baseline and the CI check

This is the single highest-value security step. The realistic breach path is a table
shipped with RLS off, or `service_role` reaching the frontend — not disk theft.

**Baseline for every table:**

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
-- no policies = deny all. Add policies deliberately.
```

**The three shapes you need — the first is needed from M0, the other two arrive with §19.7:**

| Table group | Policy | Status |
|---|---|---|
| `companies`, `postings`, `postings_archive`, `posting_comp_tiers` | Public `SELECT`; writes `service_role` only | **Needed at M0** — these tables are created then |
| `profiles`, `saves`, `dismissals`, `saved_searches`, `alert_subscriptions`, `applications`, `contact_channels` | `auth.uid() = user_id`, both directions | Needed once §19.5/§19.7 tables are built |
| `events`, `feedback` | **Insert-only.** Anyone may insert; only `service_role` may read | Needed once §19.10/§19.13 tables are built |

`events` insert-only is easy to get wrong and is a data leak if you do, when that table
is built.

**CI check — do not skip this; it's needed from M0.** A test that fails the build if any
table in the public schema has RLS disabled, or has RLS enabled with zero policies and is
not on an explicit allow-list. `SPEC.md` §15 already establishes the precedent of CI
guarding a data-posture rule; this is the same pattern.

**Key hygiene:**
- `service_role` in GitHub Actions secrets and Vercel server-side env vars only.
- Never in a `NEXT_PUBLIC_` variable. Add a CI grep for that specific mistake.
- Rotate on any suspicion; it is a single dashboard action.

---

## 8. Pipeline — planned as a direct Postgres build, no migration step needed later

An earlier draft of this section described migrating a running pipeline from committed
SQLite to Postgres partway through the project. That plan is superseded: per `SPEC.md`
§6, the pipeline is designed to write to Postgres from M0 onward, so **there will be no
legacy SQLite data to migrate** once M0 is actually built — don't go looking for one.
What's left from the original cutover plan, as things to set up at M0, not before:

**GitHub Actions secrets, to be created at M0:**

| Secret | Use |
|---|---|
| `SUPABASE_DB_URL` | Session pooler connection (port 5432) for the pipeline — see §4 |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin operations |
| `RESEND_API_KEY` | Alert sending (`SPEC.md` §13) |
| `HEALTHCHECK_URL` | Dead-man's switch (`SPEC.md` §14) |

**Remove when alerting migrates to `saved_searches` (§19.7), not before:**
`NOTIFY_PROFILES` (also not yet created — see `BUILD.md` §1.3).

**Specified in `SPEC.md`, to be verified once built, not yet true of anything:**
- The concurrency group (`SPEC.md` §15) — costs nothing, keep it once M0 sets it up.
- The dead-man's switch — will be the only mechanism catching "stopped running entirely,"
  once it exists.
- The DB-connection-failure-exits-non-zero rule (`SPEC.md` §14) — this is what will make
  a Postgres outage a *loud* failure rather than a new silent one, once implemented.
- The write-amplification rules (`SPEC.md` §6): `last_seen_at` updated once per day, not
  four times; no index on `last_seen_at`; `fillfactor` ~85 on `postings`.

---

## 9. Vercel

Not needed until the Next.js read layer starts (§19.2).

1. Connect the repo (or a separate web repo — the pipeline repo's public posture from
   `SPEC.md` §15 does not need to extend to the app).
2. Environment variables, scoped correctly:
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — public, fine
   - `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY_WEB` — **server-side only**
3. Point the web app at the **pooler** connection, not the direct one.
4. Add production and preview URLs to Supabase's redirect allow-list (§5) and Google's
   authorised origins (§3).
5. Custom domain, then re-check the auth redirect allow-list — changing the domain breaks
   OAuth callbacks in a way that only shows up at sign-in.

---

## 10. Verification checklist

Run before a single real user touches the platform-era features. `SPEC.md` §14 already
establishes the principle in writing: untested alerting is not alerting. The same applies
to auth and to RLS. **The Pipeline group below duplicates checks that already appear as
line items in `CRITERIA.md`'s M0/M12 criteria** — listed here for completeness, not as new
work, and not implying either group has actually been run yet.

**Security**
- [ ] Every public-schema table has RLS enabled; CI check fails the build if not
- [ ] `events` and `feedback` are insert-only — attempt a read with the anon key and
      confirm it fails
- [ ] Attempt to read another user's `saves` with a valid session; confirm it fails
- [ ] No `service_role` key in any `NEXT_PUBLIC_` variable; CI grep in place

**Auth**
- [ ] Google sign-in works on production *and* on a preview URL
- [ ] Magic link arrives, from your domain, in under 30 seconds
- [ ] **Same email via both methods resolves to one account** — the linking test
- [ ] Login-email change requires confirmation at both addresses
- [ ] Sign up mid-action: click Save while anonymous → auth → **the job is saved and the
      filtered list is restored**
- [ ] Anonymous `localStorage` saves migrate on signup, with nothing dropped

**Email**
- [ ] SPF, DKIM, DMARC all pass — check a received message's headers, not the dashboard
- [ ] Alert mail lands in inbox, not spam, at Gmail and at one other provider
- [ ] One-click unsubscribe works **without a session**, from a phone
- [ ] "I got a job" link resolves and stops future alerts

**Pipeline** *(duplicates `CRITERIA.md` C-0.x / C-12.x — check once, don't re-verify twice)*
- [ ] A forced DB connection failure exits non-zero and produces a GitHub failure email
- [ ] Dead-man's switch fires when the workflow is disabled
- [ ] `last_seen_at` updates once per day, not four times — check `pg_stat_user_tables`
      for dead tuple growth after 48 hours

**Data**
- [ ] Export returns everything for a test user
- [ ] Delete cascades cleanly; `events` rows survive with `user_id` nulled
- [ ] Delete has a 7-day grace window with a working cancel link

---

## 11. Running costs

| Item | Free | Realistic |
|---|---|---|
| GitHub Actions | Unmetered on public repos | $0, or a paid tier if the repo goes private |
| Supabase | 500MB DB, pauses when idle | **$25/mo Pro — plan to take it for the leave months**, per the M0 decision in `SPEC.md` §16 |
| Vercel | Generous hobby tier | $0 until real traffic |
| Resend | Limited monthly sends | ~$20/mo once alerts go to real users |
| Domain | — | ~$15/yr |

**Supabase Pro becomes a running cost starting at M0**, not a platform-era addition, once
M0 is actually built. Roughly
$25–50/month more once the rest of the platform reaches meaningful scale. The polling
stays free either way, which is the point of keeping Actions.

---

## 12. What this guide does not cover

- Web push (`SPEC.md` §19.7) — VAPID keys and service worker registration, when you get
  there
- SMS — requires US A2P 10DLC brand and campaign registration, weeks of lead time. Do not
  start until email and push are working
- The LLM proxy for resume tailoring (`SPEC.md` §19.12) — deferred, and possibly never
