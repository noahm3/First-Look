# First Look — Platform Setup Guide

**Companion to:** `SPEC.md`, `SPEC-REVISION-01.md`, `SPEC-REVISION-02.md`
**Supersedes for platform work:** `GETTING-STARTED.md`, which covers the SQLite + Pages
setup. Keep it; it remains correct for the pre-platform build.

**Read this before writing code.** Several steps have waiting periods (DNS propagation,
Google OAuth consent review) that will block you if discovered late.

**A note on specifics.** Dashboard menu paths, free-tier limits and provider requirements
change. Every screen name below is a description, not a promise. Where this guide says
*verify*, verify — do not trust the number written here.

---

## 0. Order of operations

Sequenced by blocking time, not by importance.

| # | Step | Blocks on | Do early? |
|---|---|---|---|
| 1 | Domain + DNS records for email | DNS propagation, hours | **Yes** |
| 2 | Resend account + domain verification | Step 1 | **Yes** |
| 3 | Google Cloud OAuth client | Consent screen review if publishing | **Yes** |
| 4 | Supabase project | — | Anytime |
| 5 | Migration tooling | Step 4 | Before any schema |
| 6 | RLS baseline + CI check | Step 5 | Before any user table |
| 7 | Actions secrets + pipeline cutover | Steps 4–5 | M0 |
| 8 | Vercel project | Step 4 | When read layer starts |
| 9 | Auth wiring | Steps 2, 3, 4 | When accounts start |
| 10 | Verification checklist (§9) | All | Before any real user |

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

**This step gates everything email.** Start it first; DNS propagation is the one delay you
cannot compress.

---

## 2. Resend

One provider serves both jobs — alert email (`SPEC.md` §13) and Supabase Auth's outbound
mail (§5 below). One domain, one reputation, one place to look when mail is not arriving.

1. Create the account; add and verify the sending domain from §1.
2. Create **two API keys**: one for the pipeline (Actions), one for the web app. Separate
   keys mean you can rotate one without downtime on the other, and logs tell you which
   system sent what.
3. Configure a **sending identity** — `alerts@`, `login@` — and a real reply-to that
   reaches you. A no-reply address on a product asking for feedback is a bad signal.
4. Set up the **unsubscribe header** (`List-Unsubscribe` and
   `List-Unsubscribe-Post`) on alert mail. `SPEC-REVISION-02.md` §7.3 requires one-click
   unsubscribe that works without a login; this is the header half of it.

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

## 4. Supabase project

1. Create the project. Choose a region near your users, not near you.
2. **Decide on Pro now, not later.** Free-plan projects pause after a period of low
   activity; paid projects are not paused. Per `SPEC-REVISION-02.md` §3.1 this only bites
   when the monitor is *already* dead for a week — which is exactly the parental-leave
   scenario. **Pay for Pro across the leave months.** *Verify the current pause window and
   backup retention directly.*
3. Record from the API settings:
   - Project URL
   - **anon key** — public by design, safe in the browser, useless without correct RLS
   - **service_role key** — never leaves Actions and server-side routes
   - Direct database connection string (for migrations and the pipeline)
4. Use the **connection pooler** endpoint for the web app; the direct connection for
   migrations. Serverless functions open many short-lived connections and will exhaust a
   direct Postgres connection limit.

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
- **Redirect allow-list.** Add production and Vercel preview URLs. `SPEC-REVISION-02.md`
  §5 requires returning the user to the filtered list they came from, so the return URL
  carries a query string — confirm your allow-list patterns do not break on it.
- **Email templates.** Replace the defaults. They are the first thing a user sees from
  you and they currently say "Supabase."

---

## 6. Migrations

**Pick a tool at M0, before the first table.** `SPEC-REVISION-02.md` §3.1 flags this:
"delete the file and re-seed" stops being available, and §12.3/§12.4 of `SPEC.md` are
*designed* to be written after seeing real facet data — so expect several schema changes
early.

Supabase CLI migrations are the path of least resistance and keep local, preview and
production in step. Whatever you choose:

- Migrations live in the repo and are applied by CI, never by hand in the SQL editor.
- Every migration is forward-only with an explicit `down` where reversal is plausible.
- Seeding is a separate, idempotent script — not a migration.

**First migration should create the RLS baseline (§7), not the postings tables.** It is
much easier to start default-deny than to retrofit it.

---

## 7. RLS baseline and the CI check

This is the single highest-value security step. The realistic breach path is a table
shipped with RLS off, or `service_role` reaching the frontend — not disk theft.

**Baseline for every table:**

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
-- no policies = deny all. Add policies deliberately.
```

**The three shapes you need:**

| Table group | Policy |
|---|---|
| `companies`, `postings`, `postings_archive`, `posting_comp_tiers` | Public `SELECT`; writes `service_role` only |
| `profiles`, `saves`, `dismissals`, `saved_searches`, `alert_subscriptions`, `applications`, `contact_channels` | `auth.uid() = user_id`, both directions |
| `events`, `feedback` | **Insert-only.** Anyone may insert; only `service_role` may read |

`events` insert-only is easy to get wrong and is a data leak if you do.

**CI check — do not skip this.** A test that fails the build if any table in the public
schema has RLS disabled, or has RLS enabled with zero policies and is not on an explicit
allow-list. `SPEC.md` §15 already establishes the precedent of CI guarding a data-posture
rule; this is the same pattern.

**Key hygiene:**
- `service_role` in GitHub Actions secrets and Vercel server-side env vars only.
- Never in a `NEXT_PUBLIC_` variable. Add a CI grep for that specific mistake.
- Rotate on any suspicion; it is a single dashboard action.

---

## 8. Pipeline cutover

The pipeline itself does not change — Actions keeps polling and keeps writing. Only the
target moves.

**GitHub Actions secrets to add:**

| Secret | Use |
|---|---|
| `SUPABASE_DB_URL` | Direct connection for the pipeline |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin operations |
| `RESEND_API_KEY_PIPELINE` | Alert sending |
| `HEALTHCHECKS_URL` | Existing, unchanged (`SPEC.md` §14) |

**Remove after cutover:** `NOTIFY_PROFILES` (superseded by `saved_searches`), and any step
committing `jobs.db`.

**Keep:**
- The concurrency group. It costs nothing and still prevents surprises.
- The dead-man's switch. It is now doing *more* work, since a DB outage is a new failure
  mode and this is what makes it loud.
- The non-zero-exit anomaly rules in §14. Add one: **a database connection failure must
  exit non-zero**, not retry silently forever.

**Two rules from `SPEC-REVISION-02.md` §3.2 that must land with the cutover**, or the
database fills with garbage rather than data:
- `last_seen_at` updated **once per day**, not on all four runs.
- `fillfactor` ~85 on `postings`; no index on `last_seen_at`.

**Migrate, do not re-seed.** Export the existing SQLite and load it, so `first_seen_at`
history survives. That column is the canonical date for the entire product; re-seeding
would reset every posting's age to the cutover date and destroy the one measurement
(§13's latency metric) that justifies the project.

---

## 9. Vercel

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

Run before a single real user touches it. `SPEC.md` §14 already establishes the principle:
untested alerting is not alerting. The same applies to auth and to RLS.

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

**Pipeline**
- [ ] A forced DB connection failure exits non-zero and produces a GitHub failure email
- [ ] Dead-man's switch fires when the workflow is disabled
- [ ] `first_seen_at` values survived the migration — spot-check against the old SQLite
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
| Supabase | 500MB DB, pauses when idle | **$25/mo Pro — take it for the leave months** |
| Vercel | Generous hobby tier | $0 until real traffic |
| Resend | Limited monthly sends | ~$20/mo once alerts go to real users |
| Domain | — | ~$15/yr |

**$0 to start. Roughly $25–50/month at meaningful scale.** The polling stays free, which
is the point of keeping Actions.

---

## 12. What this guide does not cover

- Web push (`SPEC-REVISION-02.md` §7.2) — VAPID keys and service worker registration, when
  you get there
- SMS — requires US A2P 10DLC brand and campaign registration, weeks of lead time. Do not
  start until email and push are working
- The LLM proxy for resume tailoring (§12) — deferred, and possibly never
