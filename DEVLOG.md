# First Look — Development Log

## 2026-09-17 — Document consolidation (pre-M-1)
**Model:** Sonnet 5 · **Plan mode:** no

### Built
No application code. Consolidated the project's design documents into one current
source of truth each, ahead of connecting the GitHub repo:

- `SPEC.md` — merged the original spec with `SPEC-REVISION-01.md` (aggregators become
  company sources), `SPEC-REVISION-02.md` (platform, accounts, user state), the
  SPEC-facing parts of `first-look-security-patch.md`, and `first-look-sources-patch.md`
  (Greentown Labs, Y Combinator). Added a new §18 (measurement gate) and a new §19
  (platform era, deferred) to hold content that didn't map onto the original 17
  sections.
- `SECURITY.md` — applied the patch's §5 refinements (scoped log-masking assertion,
  fetch-guard rejection logging).
- `BUILD.md` — applied the sources-patch's M8 additions (Greentown crawl, revised
  estimate, pagination/alumni notes) and fixed the M6 milestone description, which still
  described Getro's now-removed dual monitoring role.
- `CRITERIA.md` — appended the Security block from `SECURITY.md` and the M8 Greentown
  criteria (C-8.5–C-8.8) from the sources patch. Struck C-6.2 and C-6.3 with today's date
  and a reason: they describe Getro producing posting rows, which is no longer possible
  now that Getro is a company-source-only per `SPEC-REVISION-01`.
- `SETUP-PLATFORM.md` — fixed cross-references that pointed at `SPEC-REVISION-02.md`'s
  own section numbers (now folded into `SPEC.md` §19), and marked the Postgres/RLS-baseline
  steps as scheduled for M0 rather than the deferred platform era, since `SPEC.md` §6
  pulled that migration forward. **Nothing has actually been built** — this was a
  reclassification of which milestone the work belongs to, not a status update. An early
  draft of this file wrongly said "already done in M0" in several places; caught and fixed
  after the user asked for clarification.
- `GETTING-STARTED.md` — trimmed Phase 0 and Phase 5, which assumed the patch files still
  needed applying; fixed Phase 3's `.gitignore` guidance, which told the user to strip
  `*.db`/`*.sqlite` ignore rules under the old committed-SQLite design — now backwards,
  since storage is Postgres from the start.
- `DEVLOG.md` — this file, created now per the user's request, ahead of Phase 5 rather
  than during it.

### Decisions made this session
- **Y Combinator conflict, resolved in favor of `SPEC-REVISION-01`.** That revision
  accepted Wellfound and YC as company sources after finding the original Wellfound
  rejection factually wrong. `first-look-sources-patch.md` independently proposed
  rejecting YC, reusing the same (already-debunked) reasoning. User's call: follow
  `SPEC-REVISION-01`, keep YC in scope (`SPEC.md` §7.8), and flag it in `SPEC.md` §4/§7.8
  for a fresh look during actual discovery work rather than trusting either document
  blindly.
- **Archive, don't delete, superseded documents.** All originals — `SPEC.md`,
  `SPEC-REVISION-01.md`, `SPEC-REVISION-02.md`, `BUILD.md`, `CRITERIA.md`, `SECURITY.md`,
  `first-look-security-patch.md`, `first-look-sources-patch.md`, `GETTING-STARTED.md`,
  `SETUP-PLATFORM.md` — moved to `archive/` verbatim before any new content was written,
  per the user's explicit instruction to generate new files rather than edit in place.
- **Postgres migration and `observed_at` stay pulled forward into the pre-leave build**,
  per `SPEC-REVISION-02` §14's own carve-out — these were the two platform-era items
  that revision said were unrecoverable or structural if deferred. Reflected directly in
  `SPEC.md` §6 and §11.1 rather than left in the deferred §19.

### Deviations from SPEC
None — this session only reorganized existing content. No new product decisions were
made beyond the YC resolution above, which was the user's call, not an autonomous one.

### Criteria checked
None. No code exists yet.

### Least confident about
- Whether folding `SPEC-REVISION-02` almost entirely into a new `SPEC.md` §19 (rather
  than interleaving every sentence into the sections it nominally supersedes) will read
  as「the current source of truth」cleanly enough in six months, or whether it'll feel
  like two documents stapled together. Flagging this now in case a future session wants
  to restructure further once §19 actually starts getting built.
- Whether YC turns out to actually be account-gated on real inspection — see the note in
  `SPEC.md` §7.8. Nobody has actually re-verified it since the conflict was found; the
  resolution was "trust the more careful research," not "confirmed independently."

### Next session
- Connect the personal GitHub account and sync this folder with the repo GitHub already
  created (`GETTING-STARTED.md` Phases 1–4). Several steps there require the user's own
  browser/terminal actions.

---

## 2026-09-20 — Iteration 1 & 2 spikes: source shapes, no repo yet
**Model:** Sonnet 5 · **Plan mode:** no

### Built
Throwaway scripts in a new `spikes/` folder (not `src/` — no milestone framework, no
tests, no fixtures directory yet, just direct exploration), per the user's request to
work in small, concrete, reorderable iterations rather than plan the whole thing up
front:

- `spikes/iteration1_ats_spike.py` — one real, live company each from Greenhouse
  (robinhood), Lever (ro), and Ashby (ramp): fetch, parse into the fields `SPEC.md` §6/§9
  say we'd store, print to terminal. All three worked on the first real try.
- `spikes/iteration2_getro_spike.py` — one real, live Getro board
  (`breakthroughenergy.getro.com/jobs`), parsed for company-discovery fields (name, slug,
  industry tags, headcount, stage), since `SPEC.md` §7.2 makes Getro a company source
  only, not a postings source.
- `spikes/iteration2_consider_notes.md` — write-up of the first attempt, which failed:
  confirmed Consider's branding and board-id shape on `jobs.greentownlabs.com`, but
  guessed REST paths 404'd and `/graphql` returning 200 was a false lead (the SPA's
  catch-all shell, not a real endpoint).
- `spikes/iteration2_consider_spike.py` — **completed**, same session. The user opened
  their own browser devtools on `jobs.greentownlabs.com`, found the real request
  (`POST /api-boards/search-jobs`, cookie + `x-csrf-token` header) and pasted the real
  request body and a response sample directly — no more guessing needed. This script
  confirms the whole flow is reproducible headlessly: GET the `/jobs` page for a fresh
  session cookie + CSRF token (both embedded in `window.serverInitialData`), then POST
  the search request with them. Works. Real output from a live 5-job pull is in the
  script's own run history, not duplicated here.

### Decisions made this session
- Reframed the earlier "in scope / out of scope" language the user was given as wrong:
  everything in `SPEC.md` (current build and §19 platform era alike) is in scope: some
  of it is just a later iteration, and iteration order is meant to be reshuffled, not
  fixed by the milestone numbers in `BUILD.md`. No document changes yet, just a
  correction going forward in how this gets talked about.
- Started iteration work directly against public APIs from this local folder, without
  waiting for `GETTING-STARTED.md`'s GitHub-connection phases. Nothing here needed a
  repo, and this kind of spike is exactly the "fetch real data, write fixtures from
  live responses" work `BUILD.md` M2 already says should happen against real docs and
  real responses, not memory — just done earlier and smaller than a whole milestone.

### Deviations from SPEC
- **Getro's `__NEXT_DATA__` shape is confirmed for at least one real board, but not
  universal.** A second candidate board (`jobs.a16z.com`, tried before finding a
  confirmed Getro board) turned out to run Next.js App Router with a streamed RSC
  payload instead of a `__NEXT_DATA__` script tag — and it's not even confirmed to
  actually be Getro-branded. `SPEC.md` §7.2 already warns the shape is
  community-derived and needs per-board verification; this is a concrete instance of
  that warning being right. Not a SPEC change, just first-hand evidence for something
  SPEC already flagged as a risk.
- **Getro doesn't expose a company's own domain directly** — only a slug and, per job,
  an external application URL that's usually a *third-party ATS's* subdomain
  (`renewco2.breezy.hr`, `rift.recruitee.com`, `carbonengineering.applytojob.com`), not
  the company's own domain. **Now in `SPEC.md` §7.2 and §6**, dated and flagged as
  confirmed on one board only, with a new open question in §17 (#6) about whether it
  holds up across more boards and whether it's even solvable in general.
- **Consider does NOT have this gap — it hands back `companyDomain` directly** in every
  job record (`energydome.com`, `lydianlabs.com`, `americanbatterytechnology.com`,
  confirmed on 5/5 real results). No resolution hop needed at all, unlike Getro and
  unlike Wellfound. **Now in `SPEC.md` §7.6**, along with the confirmed endpoint/auth
  flow (see below) — §17's old open question #10 about Consider's endpoint is struck
  and marked resolved.
- **Consider's response also includes fields that are its own inferred output, not the
  employer's raw posting**: `scores` (a proprietary relevance/match/age/richness
  score), `skills`/`requiredSkills`/`preferredSkills` (resume-matching tags),
  `considerLevels` (inferred seniority ranges), `matchingTalent`. These are exactly the
  kind of scoring/classifier output `SPEC.md` §4 already rejects building ourselves —
  noted explicitly in `spikes/iteration2_consider_spike.py` as fields to never store or
  surface, even though the API hands them to us for free.

### Criteria checked
None — these are pre-M2 spikes, not milestone work, and `CRITERIA.md` has no criteria
for exploratory scripts by design.

### Least confident about
- Whether the one Getro board tested (`breakthroughenergy.getro.com`) is representative,
  or whether it happened to be one of the "still using classic Next.js" boards while
  newer Getro deployments (like whatever `jobs.a16z.com` actually is) have moved on.
  Five real boards would tell us a lot more than one.
- Resolved: Consider's real endpoint, found via the user's own devtools session rather
  than more guessing from the terminal — see the Consider bullets above.
- Whether the `search-jobs` request needs anything beyond the cookie + CSRF token pair
  to keep working over time (e.g. does the CSRF token expire independent of the
  session cookie?), and whether hammering this endpoint on a schedule risks the same
  kind of bot defenses Built In Boston's crawl already has to smoke-test around
  (`SPEC.md` §7.4, §8.1). Only tried this a handful of times manually so far.

### Next session
- User's call: keep working through sources one at a time (Wellfound, YC, ClimateTechList,
  Consider's real endpoint), or shift to connecting the GitHub repo, or something else
  entirely. Nothing here is blocking on the other.

---

## 2026-09-21 — Consider's real endpoint found; Kardow parked; VC-portfolio-board
## discovery via Sightline's public investor list (new source idea, in progress)
**Model:** Sonnet 5 · **Plan mode:** no

### Built
- **Consider's endpoint, fully resolved** — the user opened real devtools on
  `jobs.greentownlabs.com`, found `POST /api-boards/search-jobs` (session cookie +
  `x-csrf-token` from `window.serverInitialData`, body
  `{"meta":{"size":N},"board":{"id":"<slug>","isParent":true},"query":{...}}`), and pasted
  the real request + a response sample. `spikes/iteration2_consider_spike.py` replays the
  whole flow headlessly (GET for session+token, then POST) — confirmed working. Findings
  folded into `SPEC.md` §7.6, §7.2, §6, §17 in the previous session's edits (see above).
- **`spikes/sightline_investors_raw.json`** — all 393 climate investor records from
  `api.sightlineclimate.com/v1/gold/public/investors` (public, unauthenticated, paginated,
  `count`/`next`/`results` shape). Each record: `name`, `website` (real domain),
  `overview`, `investor_types`, `city_display_name`.
- **`spikes/iteration3_vc_board_discovery.py`** — for a given VC name + website, fetch the
  homepage, find a jobs/careers link (or fall back to guessing
  `jobs.{domain}` / `careers.{domain}` / `{domain}/jobs` / `{domain}/careers` / etc.), then
  fingerprint the resulting page as Getro / Consider / Kardow / WordPress (WP Job Manager)
  / direct ATS / unknown. Tested and fixed twice on the same batch of 20 real investors
  (see Deviations below for the two real bugs found and fixed).
- **Final clean result on batch of 20:** 2150 → Getro, 360 Capital → Consider, AENU →
  Getro, AgFunder → **WordPress / WP Job Manager (new pattern, not previously in SPEC.md)**,
  Airbus Ventures → Consider, 4impact Capital → found a page but unfingerprinted
  ("unknown"), 13 others → no jobs page found via this heuristic, 2 homepage fetches
  failed outright (403/404).

### Decisions made this session
- **Kardow (`ctvc.kardow.com`) parked, not pursued further.** Confirmed it's Next.js App
  Router with data fetched client-side (same category as Consider was), but the user
  judged it not worth the devtools time right now — "doesn't seem as straightforward as
  Consider... we'll get really sidetracked." Correct call; revisit only if Kardow turns
  out to power many boards, the way Getro/Consider do.
- **Sightline Climate's public investor API: fine to use, reversing my initial caution.**
  I'd flagged this as the same "ask first" category as ClimateTechList (`SPEC.md` §7.5).
  User's counter, which stands: this specific list is Sightline's own marketing
  lead-magnet for their paid platform (a "Request Demo" CTA sits right on the page), not
  the proprietary product itself — and more importantly, **what we actually want isn't on
  Sightline's site at all.** We're using their investor directory as a one-time seed list
  to go find each VC's *own* public jobs page, which is a step removed from anything
  Sightline curates or sells. Decision: proceed, no outreach needed. This is a narrower
  fact pattern than ClimateTechList (§7.5 still stands as-is for climate *companies*,
  where the curated list itself is exactly what we'd be reusing) — don't over-generalize
  this decision to other "public but clearly curated" data without re-checking which
  category it falls in.
- **New source pattern to add to `SPEC.md` eventually: VC-portfolio-board discovery,
  Getro-slug-guessing style, one level up from ATS mapping.** Same cascade shape as
  `SPEC.md` §8.1 (slug guess → validate), applied to "VC name → Getro/Consider/etc.
  board" instead of "company name → ATS board." Not yet written into SPEC.md — see Next
  session.

### Deviations from SPEC
- **Naive Getro-slug-guessing has a real, confirmed false-positive rate — don't skip
  validation.** Tried `{name}.getro.com/jobs` for ~25 VC name guesses. 3 returned HTTP 200
  with a real Getro `__NEXT_DATA__` payload; only 1 (`lowercarbon` → Lowercarbon Capital)
  was actually the intended fund. The other two were unrelated companies that happened to
  register the same intuitive slug: `prelude.getro.com` is "Prelude Management"
  (`prelude.xyz`, unrelated), `closedloop.getro.com` is a healthcare AI company, not
  ClosedLoop Partners. **A 200 + valid Getro payload is not enough** — must check the
  returned `network.domain` / `network.description` / `network.legal.name` against the
  VC we were actually looking for before accepting a match. This is the exact same
  discipline `SPEC.md` §8.2 already requires for ATS token guessing (verified/probable/
  weak), just not yet written down for this VC-board-discovery use case specifically.
  **Not yet added to SPEC.md** — should be, alongside whatever this new discovery source
  ends up being called.
- **Two real bugs found and fixed in `iteration3_vc_board_discovery.py` while building
  it, both worth remembering if this logic ever moves into `src/`:**
  1. A homepage-link regex that matched "job"/"career" as a bare substring anywhere in an
     `href` grabbed `.../wp-job-manager/assets/dist/css/job-listings.css` (a CSS file) as
     AgFunder's "jobs page." Fixed by requiring the keyword to be a whole path segment
     and excluding common asset extensions.
  2. Tightening that regex correctly stopped it from matching subdomain-style links
     (`jobs.360cap.vc`) as if they were paths — but that silently broke detection for two
     already-confirmed Consider boards (360 Capital, Airbus Ventures), because the
     fallback guesser tried the same-domain `/jobs` path *before* the `jobs.{domain}`
     subdomain guess, and the same-domain path turned out to be a client-side-JS redirect
     stub that a plain HTTP fetch doesn't follow — so it read as "unknown" instead of
     following through to the real Consider board. Fixed by trying subdomain guesses
     first. **General lesson, not just for this script:** when guessing multiple
     candidate URLs, order matters, and "got a 200" is not the same as "got the real
     page" — same shape as the Getro slug-collision finding above, different mechanism.

### Criteria checked
None — still pre-M2 spike work.

### Least confident about
- Whether AgFunder's WordPress/WP Job Manager pattern is common enough among these VCs to
  be worth a dedicated adapter, or a one-off. Only seen once so far.
- Whether the ~20-25% clean-hit rate on the batch of 20 (5 confirmed platforms + 1
  found-but-unfingerprinted out of 20) holds up across the full 393, or whether the first
  20 (alphabetically first) happen to be unrepresentative.
- `4impact Capital`'s `jobs.4impact.vc` returned something, but nothing matched any known
  fingerprint. Didn't look closer — could be a fifth platform, could be a placeholder/
  parked page.

### Next session
1. **Decide whether to scale `iteration3_vc_board_discovery.py` to the full 393** in
   `spikes/sightline_investors_raw.json`, or refine further first (e.g. investigate the
   `4impact` "unknown" case, check whether WP Job Manager shows up again).
2. **Write the VC-slug-collision validation rule into `SPEC.md`** once the discovery
   approach is scaled up and stable — same shape as §8.2, applied to VC-board discovery.
   Also add WordPress/WP Job Manager as a recognized pattern once confirmed on more than
   one board.
3. **Once a real list of confirmed VC boards exists** (Getro/Consider/WP-Job-Manager,
   validated), fold the new ones into `config/getro_boards.yml`-equivalent config and
   update `SPEC.md` §7.2's "~10-15 climate and energy VC boards" count, which this work is
   likely to grow substantially.
4. Still separately outstanding from prior sessions: Wellfound, YC, and ClimateTechList
   spikes were never done (only Getro/Consider/the three ATS providers were). Connecting
   the GitHub repo (`GETTING-STARTED.md` Phases 1–4) is also still untouched.

---

## 2026-09-22 — M-1: GitHub repo setup
**Model:** Sonnet 5 · **Plan mode:** no

### Built
Worked through `GETTING-STARTED.md` Phases 0–7 with the user driving the browser/account
steps and Claude running the git/gh commands:

- `git init`, `main` branch, per-repo commit identity set to a GitHub noreply address
  (not global config, so no work identity is at risk).
- Remote connected to `noahm3/First-Look` (personal account, confirmed via `gh auth
  status` before doing anything — the account list also showed a second, work account,
  correctly inactive).
- `git pull origin main` brought down GitHub's own initial commit (`README.md`,
  `.gitignore`, `LICENSE`) as a fast-forward — local `main` had no commits yet, so no
  `--allow-unrelated-histories` was needed.
- `.gitignore` extended with the project-specific block from `BUILD.md` §1.3 (`.cache/`,
  `Connections.csv`, `connections*.json`, `config/notify/`, `*.local.yml`). The template's
  existing `db.sqlite3` lines were left alone — harmless, and correct-by-accident now that
  storage is Postgres.
- Two commits pushed to `main`: "Initial design documents" (all design docs, `archive/`,
  and the `spikes/` folder as it stood at the time) and "Setup: CLAUDE.md, pre-commit
  hook".
- `CLAUDE.md` created verbatim from `BUILD.md` §0.2.
- `.githooks/pre-commit` created verbatim from `BUILD.md` §0.3, `core.hooksPath` enabled,
  and live-tested: a commit containing a fabricated email-shaped string was correctly
  blocked with `BLOCKED: email address in staged changes`, then cleaned up. (This same
  DEVLOG entry tripped the hook a second time on its own draft — see Least confident
  about, below.)
- Repo settings confirmed enabled: Secret Protection, push protection, workflow
  permissions set to read-and-write, "Require approval for all external contributors."

### Decisions made this session
- **Commit email: the account's GitHub noreply address** (set per-repo, not global), name
  `noahm3` — user's choice, matches `GETTING-STARTED.md`'s recommendation and the
  project's low-profile posture. (Deliberately not spelled out here — see Least confident
  about, below.)
- **Resend API key and the fine-grained PAT deliberately not created yet.** User's
  reasoning: no point minting a live credential before there's a secret store
  (`gh secret set`) ready to receive it — that happens as part of M0, not M-1. Sound
  practice, just noting it as a sequencing choice since `GETTING-STARTED.md` Phase 8
  assumes these get created in this same setup pass.
- **Supabase: staying on the free tier for now, project creation deferred to when M0
  actually needs it.** Diverges from `SPEC.md` §6's explicit "pay for Supabase Pro across
  the leave months" recommendation and `GETTING-STARTED.md` Phase 8's "decide on Pro now"
  framing. Flagging as genuinely open, not resolved — `SPEC.md` §2 states the parental
  leave began mid-September 2026, so the free-tier pause risk this recommendation exists
  to avoid may already be live.
- **Hosted form for alert requests deferred to M10** — `GETTING-STARTED.md` itself offers
  this as an acceptable deferral.
- **healthchecks.io account created, but no check configured with a real ping yet** —
  correctly, since nothing exists to ping it. Will be wired up in M0.

### Deviations from SPEC
None to `SPEC.md` itself. One stale pointer in `GETTING-STARTED.md`: it directs the user
to "Settings → Code security" for secret scanning/push protection, but GitHub has since
renamed and relocated this to "Settings → Advanced Security" under "Secret Protection."
Confirmed both toggles were enabled there instead.

### Criteria checked
- **C-1.1** — `git push` to the public repo succeeds (two pushed commits, both visible on
  github.com under the correct personal account)
- **C-1.4** — Workflow permissions set to read-and-write (user confirmed in Settings →
  Actions → General)
- **C-1.9** — `.gitignore` includes the required entries, added before the first commit
- **C-1.10** — Repo name (`First-Look`) doesn't identify the project as a personal job
  search; README stays neutral and technical
- **Not yet checked:** C-1.2 (`NOTIFY_PROFILES`/`HEALTHCHECK_URL`/`RESEND_API_KEY`/
  `KEEPALIVE_PAT` secrets — none set yet, no PAT or API key exists to set them with),
  C-1.3 (Pages — that's M0's job via `gh`), C-1.5 (healthchecks period/grace/alert-address
  — account exists but the check isn't wired to a real ping yet)

### Least confident about
- **The pre-commit hook's blunt email regex applies to prose in this very file, not just
  code.** This entry originally spelled out the noreply address and a fabricated test
  address; both tripped `BLOCKED: email address in staged changes` on the first commit
  attempt. Rewrote both to describe rather than quote the address. Worth remembering for
  future DEVLOG entries: don't write any email-shaped string literally, even a
  known-safe or fabricated one, when documenting work in this repo.
- Whether deferring PAT/Resend-key creation cleanly folds into M0's own setup steps, or
  whether M0 will assume they already exist. No functional risk either way, just a
  sequencing question for whoever picks up M0.
- Whether the Supabase free-vs-Pro decision needs resolving before M0's Postgres migration
  work starts, given `SPEC.md` §6 treats Pro as a leave-window requirement, not an
  optional upgrade, and leave has reportedly already begun.

### Next session
- **M0** — skeleton and reliability plumbing. `BUILD.md` recommends **Opus 5 with plan
  mode**; start a **fresh Claude Code session** for it. Before M0's workflows can be built
  end-to-end, the deferred accounts (Resend key, correctly-scoped fine-grained PAT with a
  leave-safe expiry, Supabase project/plan) need resolving, since M0 wires secrets into
  GitHub Actions.
- **Separately, flagging for the user's attention, not touched this session:** while this
  setup work was underway, a background process completed a full run of
  `iteration3_vc_board_discovery.py` and `iteration4_vc_portfolio_discovery.py` against
  all 393 Sightline investors (`spikes/investor_sources.csv` now has 393 rows;
  `spikes/discovered_companies.csv` has grown to ~4,260 rows). This appears to go beyond
  the 20-investor test batch the 2026-09-21 entry describes, and beyond what that entry's
  "Next session" list asked to confirm before scaling. Nothing from this output was
  reviewed, folded into `SPEC.md`, or committed as part of this session — that decision
  and review are still the user's, per the prior entry's explicit ask.

  **Correction, added by the session that actually did this work (see the entry directly
  below): this was not an unsupervised background process.** It was a separate, concurrent
  Claude Code session in the same working directory, driven by the user step by step in
  real time — small batches, review, bug fixes, explicit confirmation before scaling, at
  each stage. The M-1 session above had no visibility into that conversation and drew a
  reasonable but incorrect conclusion from the file changes alone. Left both notes here
  rather than editing the original away, per this project's convention of correcting the
  record rather than silently rewriting it.

---

## 2026-09-22 — Iteration 3/4/5: VC-based company discovery scaled to all 393 investors
**Model:** Sonnet 5 · **Plan mode:** no

### Built
Continuing directly from the 2026-09-21 entry's VC-board-discovery spike, in a session
running concurrently with the M-1 GitHub-setup session recorded above (see the correction
note there):

- Scaled `iteration3_vc_board_discovery.py` (VC-hosted jobs-board fingerprinting:
  Getro/Consider/direct Greenhouse/Lever/Ashby/WordPress) across all 393 investors.
- Built and scaled `iteration4_vc_portfolio_discovery.py`, a second, complementary
  discovery approach: instead of looking for a shared jobs-board platform, find each VC's
  marketing "portfolio" page and extract outbound links to each portfolio company's own
  domain. Structurally the same as the manual watchlist (`SPEC.md` §7.1) — a name+domain
  list — just VC-sourced instead of hand-curated, and it doesn't require the VC to run any
  job-board infrastructure at all, unlike the iteration-3 approach.
- Built `iteration5_second_hop_detail_pages.py`: for the ~42 investors where iteration 4
  found a portfolio page but extracted zero domains, most turned out not to be
  client-rendered at all — the index page links to per-company detail pages on the VC's
  own domain, and the real external link is one hop deeper (confirmed by hand on
  Lowercarbon Capital: `lowercarbon.com/company/antora/` → `antora.com`). Recovered real
  companies for 13 of those 42 investors this way.
- Built `tracking_store.py` + `spikes/investor_sources.csv` + `spikes/discovered_companies.csv`:
  persistent, upsert-keyed CSV storage (chosen over SQLite for this stage, on the user's
  call — plain-text, diffable, hand-editable) so a monthly re-crawl can build on prior
  state instead of re-discovering everything from scratch. `discovered_companies.csv`
  already carries empty `careers_page_url` / `ats_provider` / `ats_token` columns, staged
  for the next spike, same shape as `SPEC.md` §11.1's `observed_at` — schema in now, the
  crawl that fills it comes later.

**End state:** `investor_sources.csv` — 393 rows (jobs-board result, portfolio-page result,
or both, per investor). `discovered_companies.csv` — 4,284 unique candidate company
domains.

### Decisions made this session
- **VC portfolio-page extraction is a broader, complementary discovery mechanism to
  jobs-board fingerprinting, not a replacement.** Hand-checking iteration 3's early misses
  showed several VCs (Aligned Climate Capital, American Century Investments) have no
  shared jobs board at all, but do have a portfolio page. Both approaches now run across
  the full list.
- **Treated "portfolio page found, zero domains extracted" as a classified, revisitable
  bucket** (same shape as `SPEC.md` §8.4's `mapping_failure_reason`) rather than a dead
  end — this paid off directly: most of that bucket was a recoverable two-hop link
  structure, not genuine client-side rendering.
- **Did not add headless-browser rendering** to recover the remainder that are genuinely
  client-rendered SPA shells — consistent with `SPEC.md` §4's existing project-wide
  rejection of headless browsers. Where a real per-VC API might exist (the Consider
  precedent), that would need the same hand-devtools approach used for Consider, not a
  generic renderer.
- **This session's raw discovery output is explicitly left unvalidated.** No
  confidence-level system (verified/probable/weak, per `SPEC.md` §8.2) exists yet for
  either VC-discovery approach, and it was a deliberate choice not to build one here.
  Reasoning: a junk domain (an ESG-certification body, a fund-admin SaaS tool, a
  press-mention link) will simply fail to map to a real Greenhouse/Lever/Ashby board when
  it goes through the actual ATS mapping cascade later — costs a wasted request, not
  invisible bad data, per `SPEC.md` §3.8. Validation effort was spent instead on the
  extraction mechanics themselves (see bugs below).
- **This whole mechanism (both discovery approaches, the two-CSV schema) is deliberately
  not yet folded into `SPEC.md` §6/§7.** Still spike-only, same discipline already applied
  to the original Getro/Consider work — prove it out further before formalizing.

### Deviations from SPEC
None yet — nothing here has been written into `SPEC.md`. See "Next session" for what
formalizing this would need to answer first.

### Real bugs found and fixed this session (worth remembering if any of this logic moves
into `src/`)
1. An href regex matched *any* `href="..."` attribute, not just `<a>` tags — a
   `<link rel="preconnect">` performance hint pointed at analytics domains was being
   counted as an "outbound company" (found on Verve Ventures).
2. A handful of sites leak un-rendered JS template code as a raw href value (client-side
   string concatenation, e.g. `.../portfolio/' + text + '`) — confirms genuine client-side
   rendering with nothing to recover, not a bug in the extractor.
3. **A one-character-too-short junk-domain entry (`"ft.com"` for Financial Times) matched
   as a substring and silently deleted real companies** whose domain happened to end in
   "...ft.com" — `microsoft.com`, `shift.com`, `lyft.com`, `treeswift.com`,
   `salesloft.com`, `triplelift.com`, and others. Caught by verifying the cleanup's effect
   before trusting it, not after; all wrongly-removed rows were restored and the entry
   replaced with the exact Financial Times subdomain.
4. Company detail pages routinely link to press-mention logos ("as seen in TechCrunch/
   CNBC/Reuters") and government/regulator citations (`sec.gov`, `bafin.de`) — a junk
   category that turned out to be scattered across the *original* full-393 portfolio-page
   run too, not just the second-hop bucket, since some VCs' index pages carry the same
   press logos. A global sweep against the corrected junk list removed 35 genuine junk
   rows once the substring bug above was fixed.

### Criteria checked
None — pre-M2 spike work, no `CRITERIA.md` items apply yet.

### Least confident about
- **Overall precision of the 4,284 discovered companies is still unmeasured.** Real bugs
  were found and fixed iteratively, but there's no guarantee the junk-domain blocklist is
  now exhaustive — the true signal-to-noise ratio won't be known until these companies go
  through real ATS mapping.
- **The ~76 raw "confirmed platform" jobs-board hits (Getro/Consider/Greenhouse/Lever/
  Ashby/WordPress) have not been validated against the VC they're attributed to.** The
  2026-09-21 entry already confirmed naive Getro slug-guessing has a real false-positive
  rate (3 guesses, only 1 correct); this session's jobs-board fingerprinting works
  differently (checks the VC's own found careers/jobs page, not a raw slug guess) but has
  had no equivalent validation pass.
- **Cerulean Ventures' 7 recovered domains** came from blog-post-shaped URLs
  (`/portfolio/cerulean-ventures-blog/financing-coffee-farms...`) rather than clean
  per-company detail pages — less certain than the rest of the second-hop recoveries,
  worth a manual glance before relying on them.
- Whether the CSV-based `investor_sources`/`discovered_companies` schema, upsert-keyed and
  hand-editable, will still be the right shape once this needs to run unattended on a
  schedule rather than interactively — it was chosen explicitly for this exploratory
  stage, not evaluated against the concurrency/write-amplification concerns `SPEC.md` §6
  already works through for the real system.

### Next session
- **Crawl the ~4,284 discovered companies for their own careers page, and detect which ATS
  (if any) each is running** — the natural next layer, using the same cascade shape
  `SPEC.md` §8 already designs for the real system (slug guess → careers-page regex →
  classified failure), reusing the working fetch/parse logic already proven in
  `spikes/iteration1_ats_spike.py` for Greenhouse/Lever/Ashby. Write results into
  `discovered_companies.csv`'s already-staged `careers_page_url`/`ats_provider`/
  `ats_token` columns.
- **Uncommitted at end of session:** `spikes/discovered_companies.csv`,
  `spikes/investor_sources.csv`, and `spikes/iteration4_vc_portfolio_discovery.py` are
  modified; several `iteration3_batch_*`/`iteration4_batch_*` JSON files and
  `iteration5_second_hop_detail_pages.py` are untracked. Not committed this session —
  that's the user's call, same as the M-1 session's note above about this same directory.
- Still separately outstanding from prior sessions: Wellfound, YC, and ClimateTechList
  spikes were never done. `SPEC.md`/`CRITERIA.md` formalization of the VC-discovery
  mechanism (validation confidence levels, new `company_sources.source` value, the
  `investor_sources` table) waits until the careers-page/ATS crawl above shows whether
  this discovery approach is worth keeping at all.

---

## 2026-09-22 — M-1 follow-up: Resend, PAT, and Supabase accounts resolved
**Model:** Sonnet 5 · **Plan mode:** no

### Built
Resolved the three accounts the M-1 close-out entry (above) left deferred, ahead of
starting M0 for real:

- **Resend** — account verified, send-only API key created, set via
  `gh secret set RESEND_API_KEY` (value entered at the interactive prompt, never pasted
  into any chat).
- **Fine-grained PAT** — created scoped to this one repository only, permission
  `Contents: read/write`, no `workflow` scope, **expiry 2026-12-21** — comfortably past
  the roughly mid-November 2026 end of the two-month leave `SPEC.md` §2 describes. Set
  via `gh secret set KEEPALIVE_PAT`, same never-in-chat pattern.
- **Supabase project created.** Settings chosen at creation: region Americas; Data API
  left enabled (unused pre-platform per `SETUP-PLATFORM.md` §8 — the pipeline uses the
  direct connection string, not the Data API); "Automatically expose new tables"
  disabled; "Enable automatic RLS" enabled — the last two match `SETUP-PLATFORM.md`
  §6/§7's instruction to start default-deny from the very first migration rather than
  retrofit RLS later.

### Decisions made this session
- **Supabase: Free tier, not Pro — user's explicit, informed call, made twice after the
  tradeoff was flagged both times.** Diverges from `SETUP-PLATFORM.md` §4's "Pro plan,
  not Free" and `SPEC.md` §6/§16's stated reasoning (a free-tier pause after low activity
  lands hardest during the exact unattended leave window this project exists for).
  Recorded as a real, deliberate deviation, not an oversight. Worth noting for whoever
  revisits this: the risk is partly bounded by controls that already exist for other
  reasons — a 4x/day poller keeps a free project alive trivially, and the pause scenario
  converges with "the monitor has already been dead for a week," which the
  healthchecks.io dead-man's switch (`SPEC.md` §14) is already designed to catch
  regardless of Supabase's plan.
- **New Supabase credentials (project URL, anon key, service_role key, direct DB
  connection string) were not pasted into any chat.** They'll become
  `SUPABASE_DB_URL` / `SUPABASE_SERVICE_ROLE_KEY` GitHub secrets once M0 actually wires
  the pipeline to Postgres.

### Deviations from SPEC
- Supabase Free tier vs. `SPEC.md` §6/§16's Pro recommendation — see above. The only
  deviation this session.

### Criteria checked
- **C-S.12** — PAT is fine-grained, single-repo, `Contents`-only, expires after leave
  ends (2026-12-21, recorded here as required)
- **C-1.2, partially** — `RESEND_API_KEY` and `KEEPALIVE_PAT` secrets now set.
  `HEALTHCHECK_URL` and `NOTIFY_PROFILES` remain unset: the healthchecks.io account
  exists (per the M-1 entry) but isn't wired to a ping URL yet, and `NOTIFY_PROFILES`
  isn't due until closer to M10.

### Least confident about
- Whether the Free-tier decision holds up once the M0 Postgres migration is actually
  running unattended for real — nothing to verify yet, since no schema exists.

### Next session
- Hand off to the M0/Opus planning session with all three previously-deferred accounts
  now resolved. Two secrets remain genuinely unset for later:
  `HEALTHCHECK_URL` (needs the existing healthchecks.io check's actual ping URL) and
  `NOTIFY_PROFILES` (not due until M10).

---

## 2026-09-22 — Iteration 6: ATS mapping cascade for discovered companies
**Model:** Opus 5 (plan mode for cascade design) → same session for implementation

### Built
Continuing directly from the previous Iteration 3/4/5 entry's "Next session" ask —
mapping the ~4,284 VC-discovered company domains to their own ATS, in `spikes/`, still
pre-M2:

- `spikes/iteration6_ats_mapping_spike.py` — implements `SPEC.md` §8.1's cascade (slug
  guess against Greenhouse/Lever/Ashby → careers-page regex → classified failure; stage 2
  apply-redirect is N/A here, these aren't Built In postings) and §8.2's three confidence
  levels plus the negative guard for short/collision-word slugs. Reuses the fetch pattern
  from `iteration1_ats_spike.py` and the careers-page-finding logic (href regex +
  subdomain-first fallback) from `iteration3_vc_board_discovery.py`, applied to a plain
  company domain instead of a VC site.
- Extended `spikes/tracking_store.py`: added `mapping_confidence`/`mapping_method`/
  `mapping_failure_reason` columns to `discovered_companies.csv` (mirroring the real
  `companies` table's fields, `SPEC.md` §6) and an `update_company_mapping()` helper.
- Worked in small batches throughout, per the user's explicit process ask, reviewing real
  output and fixing bugs before scaling: 15 → 15 (recheck) → 15 → 15 → 150 → the remaining
  ~4,074 run in the background (restarted once partway through — see bug 6 below). **Full
  run completed this session: all 4,284 companies checked.**

### Real bugs found and fixed this session
1. `careers_page_url` was silently dropped whenever a careers page was found but showed no
   recognizable ATS — lost real signal (e.g. `ifvi.org`). Fixed.
2. **`jetzero.au`** — fuzzy-matched a real Greenhouse board ("JetZero") at `probable`
   confidence, but the domain is a dead, suspended-hosting parked page with no connection
   to the real company (`jetzero.com`). The fuzzy-name check only compared strings, never
   checked whether the discovered domain was live. Added a parked/dead-domain guard
   (same escalation-to-`verified` treatment as the existing collision-word guard) and
   corrected the already-written CSV row. This is the C-3.1-shaped finding this milestone's
   own `BUILD.md` warns about: a real false `probable`, caught by review, not hypothetical.
3. **`loamist.com`** (found via the user's manual spot-check, see below) — its "Careers"
   button resolved to a page byte-identical to the homepage, a same-page anchor/placeholder
   link. Added a same-content check so this no longer counts as a found careers page.
4. Forgot to port the WordPress/WP Job Manager fingerprint (`job_listing`,
   `wp-job-manager`, `feed=job_feed`) from `iteration3_vc_board_discovery.py` into this
   script — found again via `genh2hydrogen.com`'s RSS feed. Restored.
5. New `unsupported_ats` platforms found via the user's manual spot-check and added to
   detection (measurement only, no adapter): Polymer (`addisenergy.com`), PyjamaHR
   (`unifyndlabs.com`), careers-page.com (`mati.earth`), Phenom People (found one hop deep
   on `nature.org`'s third-party `careers.tnc.org`, itself layered on Workday — a domain
   -resolution-gap shape the mapping cascade doesn't chase, same class of gap `SPEC.md`
   §7.2/§7.7 already flag for Getro/Wellfound).
6. **The 12s per-request timeout wasn't actually bounding total time per company.**
   `find_careers_page` can attempt up to ~5 URLs per company (homepage + linked page + up
   to 4 fallback paths); when a domain is dead/blocked, several of those can each eat the
   full timeout independently, compounding to 30-70+ seconds for a single company even
   though the timeout parameter itself was working correctly on each individual request
   (confirmed live: `autodesk.com.cn` took 29.8s total; a 20-domain random sample showed
   19/20 finishing in under 1s and one hitting the timeout ceiling cleanly at 12.35s — so
   it's a small tail of slow/blocked domains dragging the average, not throttling or a
   broken timeout). Lowered the default from 12s to 6s and restarted the background run —
   safe to restart, since already-checked rows are skipped, so none of the first 591
   companies' work was lost. Throughput went from 5.3/min to ~17.7/min (~3x) after the
   restart.

### Decisions made this session
- **`.org` domains are now skipped in future batches without spending a request** — the
  user's call after reviewing the first 45 results, most of which were industry
  associations/advocacy groups, not real hiring companies. **Known counterexample, not
  retroactively touched:** `rmi.org`, checked before this rule existed, is a real nonprofit
  that hires and mapped cleanly to `unsupported_ats:workday`. `SPEC.md` §7's "source
  selection is a sourcing decision, not user criteria" framing covers this kind of scoping
  choice.
- **A careers page directly naming its own ATS token counts as `verified` on its own**,
  with no separate corroborating slug guess required — the company's own domain asserting
  the token is treated as the independent-source bar `SPEC.md` §8.2 sets, even though only
  one source (the page itself) is literally consulted. This is an interpretation worth
  flagging, not obviously the only valid one: `voltacharging.com` verified this way with
  Lever token `joltcharge` (a mismatched brand name, evidently a rebrand that kept the old
  slug) — correct, but a real edge case for this reading of "verified."
- **Confirmed live, contradicts `SPEC.md` §8.2:** Ashby's public job-board API returns only
  `{jobs, apiVersion}` — no organization-name field. §8.2's claim that "Ashby carries the
  org name" is wrong as written. Ashby (like Lever) caps at `weak` from the API alone;
  `verified` requires the careers page to independently name the token.
- User's review technique, worth remembering for future ATS-detection work: click "Apply"
  and see where it lands, and check the page's raw HTML (before and/or after) for the
  script/origin revealing the real ATS — same two signals the script's `careers_page_regex`
  stage automates, but a useful manual fallback for anything the script calls `unknown`.

### Final results — all 4,284 companies checked
56 companies excluded outright as `.org` domains (no request spent). Of the remaining
4,228:

| Outcome | Count | % of 4,228 |
|---|---|---|
| Mapped (`verified` + `probable`) | 584 | 13.8% |
| `no_careers_page` | 1,783 | 42.2% |
| `unknown` | 1,176 | 27.8% |
| `weak_only` | 343 | 8.1% |
| `unsupported_ats:*` (known other ATS) | 297 | 7.0% |
| `js_rendered` | 45 | 1.1% |

Mapped, by provider: **Greenhouse 287, Ashby 220, Lever 77** (435 `verified` / 149
`probable`).

### Unsupported-ATS tally (final, input to SPEC.md §8.6 / §18 measurement #2's "build
another adapter" question)
| Provider | Count |
|---|---|
| BambooHR | 57 |
| Workable | 55 |
| Personio | 42 |
| Breezy HR | 34 |
| Workday | 30 |
| ApplyToJob | 22 |
| WordPress + WP Job Manager | 20 |
| Polymer | 12 |
| Recruitee | 11 |
| Phenom People | 7 |
| careers-page.com | 3 |
| SmartRecruiters | 3 |
| PyjamaHR | 1 |

**No single unsupported provider comes close to Greenhouse/Ashby/Lever's volume** — even
BambooHR (the largest) is 57 companies against 584 mapped. Not an obvious case for a new
adapter yet on this data alone; `no_careers_page` (1,783) and `unknown` (1,176) together
dwarf every `unsupported_ats` bucket combined (297) and are the real opportunity — see
"Next session."

### Deviations from SPEC
- The Ashby org-name finding above (§8.2 correction).
- Everything in "Decisions made this session" above.

### Criteria checked
None — pre-M2 spike work, no `CRITERIA.md` items apply yet.

### Least confident about
- **Junk-domain rate in `discovered_companies.csv` is still substantial** and is inflating
  both `no_careers_page` and `unknown` — VC-internal tooling subdomains
  (`atoneventures.arkpes.com`), CDN/asset hosts (`siteassets.parastorage.com`), and
  auth-portal subdomains with a coincidental `/careers` path (`auth.fundrbird.com`) all
  showed up in just the first 45. Fixing this upstream (before mapping, in the discovery
  CSV itself) is likely cheaper than making the cascade smarter, but hasn't been
  attempted — flagged to the user as the open "game plan" question once the full run
  completes.
- Whether the `.org` exclusion rule is too blunt (see `rmi.org` above) — kept as-is per the
  user's explicit choice, but worth revisiting once the failure-reason distribution is
  complete.
- The `verified`-from-careers-page-alone interpretation above — not SPEC-blocking, but
  worth a second look before this logic (if any) moves toward `src/`.

### Next session
- Full run is done; game-planning reducing `no_careers_page`/`unknown` (most likely:
  junk-domain filtering upstream in `discovered_companies.csv`, not more cascade logic) is
  the live open thread as of this entry.
- A new spike session was requested in parallel: fetching live postings from the
  `verified`/`probable`-mapped companies' actual ATS APIs (Greenhouse, Lever, Ashby to
  start) — separate from this mapping work, prompt handed to the user directly rather than
  recorded here.

---

## 2026-09-22 — Iteration 7: live postings from mapped ATS APIs, and the stage-3 mapping fix
**Model:** Opus 5 (1M context) · **Plan mode:** no

### Built
`spikes/iteration7_live_postings_spike.py` — generalizes the one-hardcoded-example-per-
provider fetch logic from `iteration1_ats_spike.py` across every company that iteration 6
mapped to `verified`/`probable`, parsing into `SPEC.md` §6's `postings` field names and
§9's per-provider notes. Reads `discovered_companies.csv`; never writes to it, since
iteration 6's background mapping run was still rewriting that file whole throughout this
session.

Carried over from `SPEC.md` even at spike scale: a per-provider-host rate limiter (§9's
2–5 req/sec, default 3, verified engaging — 70 waits totalling 13.1s on the full run), and
§3.7's no-exception-escapes wrapper around every company plus a fetch helper that returns
a result object instead of raising.

Ran small-batch first per the usual process: 3-company probe (one per provider, with a raw
JSON key inventory) → 12 companies round-robin across providers → full mapped set, twice,
the second time after a bug fix. Final run: **157 mapped companies, 147 ok, 5,893 live
postings, 158 requests, ~90 seconds.** Field coverage was 5,893/5,893 on `title_raw`,
`location_raw`, `url`, `posted_at` and 5,890 on `department_raw`.

Out of scope by design and not built: lifecycle (§10 — no `first_seen_at`/`closed_at`/
`is_repost`/`content_hash`), comp normalization (§11 — no annualization, no currency
conversion, no collapsed fields, no filter predicate), classification (no `location_class`,
no `city_raw`), any database, any email or dashboard.

### The finding that matters
**Compensation disclosure read from the providers' structured fields is 18.1%. Read
including the description body it is 52.5%.**

| Where the number was published | Postings | Share |
|---|---|---|
| Provider's structured field | 1,583 | 18.1% |
| Description body only | 3,020 | 34.5% |
| **Either** | **4,603** | **52.5%** |

Greenhouse carried `pay_input_ranges` on **0 of 5,243** postings while publishing a range
in the description body on roughly a quarter of them; Lever and Ashby hold nearly all of
the structured disclosure.

**These figures replace an earlier 14.2% / 38.3% pair that was committed to both this
entry and `SPEC.md` before a precision sample was run.** That pair was an undercount —
see bug 3 below. Recorded rather than quietly swapped, because it was already published
to the repo. The sample attributes essentially all of the gap to the bug rather than to
the mapped pool growing from 157 to 255 companies mid-session: the rejected population
under the old rule was 1,355 postings at ~57.5% genuine, worth ~13 points, and
38.3 + 13 ≈ 51.5.

Found because the user spotted a Crusoe posting whose page showed a salary while our
output said none: its `compensation` object is empty and
`shouldDisplayCompensationOnJobPostings` is `false`, while the description reads
"Compensation will be paid in the range of $170,000 to $205,000 + Bonus."

This costs no extra requests. Ashby and Lever return `descriptionPlain` in the board
response, and Greenhouse's `content=true` must be passed anyway because `departments` is
absent without it. The text was already arriving and being discarded.

It lands on `SPEC.md` §18's measurement gate, which has not been run yet. Measurement #3
was framed as "not engineerable — if the employer published no number, no parser recovers
it." The employer usually *had* published one, just not where the API exposes it. At 18%
the gate's own rule says "disclosure low → the product is novelty-and-alerting, reprioritise
comp hard." At 52% it does not say that.

### Decisions made this session
- **Extract comp from the description; do not store the description.** Only the matched
  line is kept, windowed on the money match and capped at 300 characters, at most 3 per
  posting. §6's "descriptions are deliberately discarded" is preserved — no body is
  written. Kept in separate fields (`comp_in_description`, `comp_description_snippets`)
  rather than folded into `comp_data_quality`, so structured and prose-derived comp stay
  distinguishable rather than being silently merged.
- **Do not parse the snippets into numbers.** That is §11/M5, and the live text argues for
  caution — see "least confident" below.
- **Greenhouse detail calls default to 0** after measuring them redundant, rather than the
  cap of 3 the user selected at the start of the session. The choice was made on the
  assumption detail calls were needed for `posted_at` and comp; both assumptions turned
  out false. Flag retained to re-verify on a new board.
- **A board exceeding the response size cap falls back to the plain list** and flags the
  degradation per posting, rather than losing the company. Recovered 618 postings on the
  one board that hit it. Losing `department_raw` for a company beats losing the company.
- **Did not touch `CRITERIA.md`.** C-4.7 ("seed mode makes no Greenhouse detail calls")
  becomes trivially true rather than wrong, so it needs no strike.

### Precision sample on the description extraction
Run at the user's request, after the numbers above were already committed. A reproducible
hand-labelled sample (seed 20260922) drawn from the committed run, in two populations,
because precision alone would have missed the actual problem:

- **Counted as disclosure: 100/100 genuine role compensation.** No false positives.
- **Rejected by the keyword test: 23/40 were genuine compensation too** — bare ranges
  like `$120,000 – $170,000 USD`. The other 17 were correctly rejected and are
  consistently funding rounds, valuations, revenue and market-size claims.

So the rule was precise and badly under-recalling. After the fix (bug 3 below),
re-sampled: **59/60 precision** — the one miss is `$300 per month` commuter benefit,
a benefit rather than a salary — with residual false negatives at ~17% of a much smaller
reject pool, about 1% of all postings. Those are mostly pay bands embedded in
requirements lists, of the form `Level II ($101,000-$146,500): Bachelor's degree...`.

Worth recording because it is counterintuitive: of the two rules added, the bounded
±220-character context window does essentially all the work (1,989 keyword-only, 1,025
both), and the standalone-money-line rule added alongside it contributes **6**. It stays
as a cheap backstop but it is not what fixed this.

### Real bugs found and fixed this session
1. **Greenhouse `content` arrives HTML-escaped**, so unescaping *after* tag-stripping left
   every tag intact and the body unsplittable — which meant the stored "snippet" was the
   first 300 characters of the job description, exactly what this spike must not store. It
   also inflated the headline number (1,847 → 1,476 confident matches) because `salary`
   appearing anywhere in an undivided blob counted as keyword proximity. Fixed by
   unescaping first, converting block tags to newlines, and windowing on the money match
   instead of taking the head. **The known-wrong run's output was deleted rather than
   committed.** Caught by reading the actual snippets in review, not by a test.
2. The `--limit` batch selector originally drew in file order, which would have given a
   single-provider batch; changed to round-robin across providers so a small batch always
   covers all three.
3. **The fix for bug 1 caused a second, larger bug, and only the precision sample caught
   it.** Splitting on block tags — added to stop the description body leaking into
   snippets — also split Greenhouse's pay-range amount away from its "Salary Range"
   label, which sits on the *preceding* line. A line-local keyword test then discarded
   real ranges, undercounting disclosure by ~13 points. Proximity is now judged against a
   bounded ±220-character window of surrounding text. **The general lesson: a
   text-extraction fix that changes how text is segmented can silently break a heuristic
   that depends on adjacency, and neither the run summary nor the field-coverage counts
   showed anything wrong — only reading the actual snippets did.**

### Repeat-run diff — `ats_job_id` stability
Also run at the user's request. `spikes/iteration7_run_diff.py` compares two result
files, restricted to the (provider, token) pairs ok in **both** runs — the pool was
growing throughout the session, so an unrestricted diff counts newly-*mapped companies*
as newly-*opened postings*.

Two runs eight minutes apart, 239 shared companies:

```
  id present in both runs : 8542
  id only in after (new)  : 2
  id only in before (gone): 3
  field drift on stable ids: none - every compared field identical
```

**The assumption `SPEC.md` §10's lifecycle rests on holds**, and nothing had previously
verified it. Zero drift across title, department, location, workplace type, url,
`posted_at` and compensation. The three disappearances were checked rather than assumed —
three further fetches of that board never returned them, so real closures, not board
non-determinism. That mattered to check: spurious omissions would make §10 step 4 set
`closed_at` on live roles.

**A naive whole-run diff would have reported +681 postings against real movement of 2
opened and 3 closed** — a hundredfold overstatement, entirely from newly-mapped
companies. This is an M4 trap and a `SPEC.md` §14 correction, now written into §14.

**One posting argued §6's case better than §6 does.** A Greenhouse role with
`first_published` of 2026-09-10 appeared on its board for the first time between the two
runs, `updated_at` two minutes prior. Sorted by `posted_at` it lands twelve days deep and
the user never sees it; sorted by `first_seen_at` it is correctly the newest thing there.
The "be early in the applicant pool" premise depends on that column.

Eight minutes measures id stability well and daily churn not at all. The 0.06% figure
says nothing about a 24-hour rate; that needs a real overnight gap, and the diff tool
takes any two result files.

### Full mapped population — the numbers restated on all 584 companies
Iteration 6's cascade finished mid-session (4,284/4,284 rows checked, **584 mapped** —
435 `verified`, 149 `probable`; 287 Greenhouse, 220 Ashby, 77 Lever). Re-ran `--all`
against the complete population: **554 companies ok, 17,499 live postings, 588 requests,
~6 minutes.** Everything above was measured on samples of 12 → 157 → 255 companies; this
is the population.

**The disclosure measurement held at three times the scale it was taken on** — 54.2%
against 52.5%:

| | Structured | Description-only | Total | Combined |
|---|---|---|---|---|
| Greenhouse | 0 (0.0%) | 5,238 (48.5%) | 10,802 | **48.5%** |
| Lever | 598 (40.4%) | 410 (27.7%) | 1,481 | **68.1%** |
| Ashby | 2,398 (46.0%) | 847 (16.2%) | 5,216 | **62.2%** |
| **All** | **2,996 (17.1%)** | **6,495 (37.1%)** | **17,499** | **54.2%** |

`SPEC.md` §11 was deliberately left at the 255-company figures: a 1.7-point move changes
no decision, and re-editing that section a third time is churn rather than accuracy.

**Greenhouse carried `pay_input_ranges` on 0 of 10,802 postings.** At 62% of all
postings in the mapped set that is no longer a small-sample artifact — the field is not
in use across this population at all, and nearly half of the largest provider's
published compensation is invisible to the adapter §9 describes.

**All 30 dead tokens are `verified` via `careers_page_regex`. Zero** from
`slug_guess+careers_page_corroboration`, across 584 companies. At 12 of 157 this was a
hint; at 30 of 584 with a perfectly clean split it is a verdict on one cascade stage, and
it is ~5% of the mapped set silently contributing nothing. 40 further companies returned
200 with zero postings (§14's ambiguous case).

**`workplace_type_raw` covers 34.6% overall** — Lever 100%, Ashby 87.6%, Greenhouse 0% —
so **65.4% of postings would start as `location_class = unknown`** before any keyword
rules are written. That is §18's measurement #4 with a real starting point, and it is
almost entirely a Greenhouse problem. Unlike measurement #3 this one is squarely a
parsing problem, as §18 already says: the information is in `location_raw`.

### Iteration 8: fixing the cascade stage that produced every dead token
Iteration 7's full-population run found 30 dead tokens, **all 30 from
`careers_page_regex` and none from `slug_guess+careers_page_corroboration`**. Reading
iteration 6's `classify_and_map` explains the clean split exactly: stage 1 calls
`PROVIDER_CHECKS` to validate a guessed slug, and **stage 3 never called the provider at
all** — a token scraped off the company's own careers page was accepted as `verified` on
the page's word alone. About 5% of the mapped set pointed at boards that did not exist,
at the highest confidence level the system has.

Two changes, both committed:

1. **`spikes/iteration6_ats_mapping_spike.py`** — stage 3 now validates the scraped token
   against the provider before accepting it. A board that does not resolve becomes
   `weak_only`, which returns the company to the monthly retry set (`SPEC.md` §8.5)
   rather than leaving it `verified` and silently contributing nothing (§3.8). Where
   Greenhouse returns a name that does not fuzzy-match the domain label, that is recorded
   in `notes` but is **not** disqualifying — a rebrand that kept an old slug is real and
   correct, which `voltacharging.com` → lever `joltcharge` already demonstrated.
2. **`spikes/iteration8_revalidate_mappings.py`** — a one-off pass repairing the rows the
   unvalidated version already wrote. Report-only by default, `--apply` to write.

**The 30 were confirmed unrecoverable before being demoted**, because several looked like
regex capture bugs rather than dead boards (`American`, `Benchmark`, `dClimate`,
`Commure-Athelas` — mixed case, some apparently truncated). Neither lowercasing the token
nor substituting the full domain label resolves a single one: **0 of 30 recoverable**. So
they are genuinely dead boards and the mixed case was a red herring. Discovery
provenance, timestamps and `careers_page_url` are all preserved — the careers page is
still the right place for a monthly retry to look.

**Mapped set: 584 → 554** (405 `verified`, 149 `probable`). A clean re-run of the
validator afterwards reports **554 live, 0 dead, 0 inconclusive**.

**Independently corroborated.** A third concurrent session built a duplicate job-fetching
spike against the same mapped output before the collision was noticed (see the addendum
entry below, and the user's call to keep this one). Its run reported **550 companies ok
and 17,371 postings against this spike's 554 and 17,499**, with 34 failures described as
404s and connection errors — consistent with the 30 dead boards found here plus a few
transients, which is exactly the distinction the validator bug below turned on. Two
implementations written independently landing within 1% is better evidence for these
numbers than either run alone.

### A bug I wrote, caught by one anomalous number
The first `--apply` wrote **31** corrections rather than 30, and the extra one was
attributed to stage 1 — contradicting the finding it was meant to act on. That was the
only signal, and it was worth chasing:

```
flyzipline.com | slug_guess+name_match | token 'flyzipline' returned HTTP 0
```

**HTTP 0 is a connection failure, not a 404.** The script read "I could not reach it" as
"it does not exist" and retired a live Greenhouse board carrying **336 open postings** —
in a script whose own docstring cites §3.8 about wrong data being worse than missing
data. `SPEC.md` §14 already separates transient failures (timeout, 5xx, connection reset)
from permanent ones (404, invalid token) for precisely this reason, and I had not applied
its own rule inside the validator. Only a definitive 4xx demotes now; timeouts, 5xx and
429 retry three times and are reported as `inconclusive` and left untouched. Zipline is
restored.

Worth writing down because the near-miss is instructive: had the transient failure landed
on a stage-3 row instead of a stage-1 one, the count would have been a plausible 31/31
from `careers_page_regex` and I would have shipped a silently wrong demotion. The tell
was a number that did not match a prediction, not anything the tooling flagged.

### Iteration 9: what the failure buckets actually are
Iteration 6 guessed `no_careers_page` (1,783) and `unknown` (1,176) were inflated by junk
rows. **Measured, that is wrong.** Only 2.3% of those rows are structurally junk — infra
hosts, subdomains of other rows — against a 0.9% false-positive rate on mapped rows as a
control. They are mostly real companies.

What they are, from diagnostics already recorded in the CSV:

| Share | Cause |
|---|---|
| 44.5% | homepage OK, no careers link found |
| 39.7% | `unknown` — and **100% of those have a `careers_page_url`**, so this means the page was fetched and no ATS fingerprint matched, not that no page was found |
| 9.3% | HTTP 0 or 429 — transient failures recorded as permanent outcomes |
| 4.0% | HTTP 403 |

**The 403 cause generalises past this spike, and the first hypothesis was wrong.** The UA
was already a realistic Chrome string, so "bot-shaped UA" was not it — the *version* is.
Four domains returned 403 to `Chrome/120` and 200 to `Chrome/140` in the same minute with
identical headers (`dataminr.com`, `lunewave.com`, `yieldmo.com`, `quinoenergy.com`). WAFs
block outdated browser versions, so **a hardcoded UA silently rots into a wall of 403s
that this cascade records as `no_careers_page`** — indistinguishable from a company that
genuinely has none. Noted in the file for whatever becomes `src/http.py`; an aged-out UA
during an unattended leave is exactly the silent failure §3.3 exists to prevent.

Fixes applied to the cascade: current UA, Greenhouse's `boards-api` host, a broader
Rippling pattern, and ten more unsupported-ATS fingerprints seen on real careers pages.
Stage 3 also now validates (see the iteration 8 section above).

**Result of a 150-row re-crawl with those fixes, which is worse than a smaller probe had
suggested: 0 newly mapped, 9 reclassified** into named `unsupported_ats` buckets. An
18-row probe had implied 44% were recoverable; that probe's ATS regex was looser than the
real fingerprints and overstated it badly. The 150-row re-crawl is the number to trust.
**The failure buckets are not a cheap win** — the lever for more mapped companies is a
better-curated company list, not more cascade logic.

### Iteration 10: census of the `unknown` bucket — which ATSes are actually out there
The user's ask, and the right one: `unknown` and `unsupported_ats:*` are **disjoint**.
Both mean the careers page was fetched; `unsupported_ats` means a known fingerprint
matched, `unknown` means nothing did. So `unknown` is the unexplored four-fifths and is
precisely the input §8.4 wants — "the distribution IS the answer to 'should we build more
adapters'."

**Method deliberately inverted.** Every earlier pass matched a hand-written platform list,
which can only find platforms someone already thought of — and did overstate things once.
This extracts *every* third-party host each careers page references, drops obvious
analytics/CDN/CMS noise, and ranks what survives by distinct companies. Platforms surface
by frequency, and an unrecognised one ranks itself.

250 careers pages, all fetched. Distinct companies per platform, projected across the
1,176-row bucket:

| Platform | Companies | % | Projected |
|---|---|---|---|
| **rippling** | 16 | 6.4% | **~75** |
| teamtailor | 4 | 1.6% | ~18 |
| adp | 4 | 1.6% | ~18 |
| consider | 4 | 1.6% | ~18 |
| greenhouse *(supported, still missed)* | 3 | 1.2% | ~14 |
| gem | 2 | 0.8% | ~9 |
| ukg | 2 | 0.8% | ~9 |
| **any platform** | 41 | 16.4% | **~192** |
| **none detectable** | 209 | 83.6% | **~983** |

**Rippling is the single largest unsupported platform in the dataset** at ~75 companies,
ahead of BambooHR's 57 — and it is adapter-able: its board URL carries the token
(`api.rippling.com/platform/api/ats/v2/board/{token}/jobs`, seen on `goshippo.com`).
Teamtailor and ADP follow at ~18 each. **SmartRecruiters, which §4 defers pending volume,
stays at 3** — this population says do not build it.

`consider.com` on 4 companies is worth noting separately: §7.6 already knows Consider as a
*discovery* source, and §4 rules it out as a posting source.

**The honest other half: 83.6% of the bucket has no detectable ATS on its careers page at
all.** Better fingerprinting does not recover those.

### Iteration 11: the standing ATS platform census, run over the whole portfolio
The user's ask, and the right shape for it: stop doing one-off probes, and build the
thing we will re-run after every future source (ClimateBase, Built In Boston, Greentown,
Wellfound, YC) so the picture accumulates instead of being recomputed and lost.

`spikes/ats_platform_census.py`, plus three data files:

| File | Role |
|---|---|
| `ats_platform_hosts.csv` | host regex → platform name. **Hand-editable.** Same user-owned-lookup pattern as §12.4's alias files, explicitly not a classifier (§3.6) — find a new platform, add a row, re-run, no code change |
| `ats_platform_detections.csv` | one row per (company, platform), upserted, so re-running a source updates rather than duplicates. The raw record |
| `ats_platform_tally.csv` | regenerated from detections every run (§3.5, store raw derive on read). Never hand-edited |

**Method inverted on purpose.** Every earlier pass matched a hand-written platform list,
which can only find platforms someone already thought of — and one such probe overstated
a share by 4x (iteration 9). This mines *every* third-party host each careers page
references, drops hosts that are clearly not recruiting infrastructure, names what it can
from the mapping file, and reports what it **could not** name, ranked by company count. An
unrecognised platform surfaces near the top instead of being invisible. That the current
unnamed list is entirely analytics and CMS noise (`js.hsforms.net`, `wordpress.org`,
`visualwebsiteoptimizer`) is the signal the naming map is complete for this population.

**Full run: 1,668 careers pages, 1,663 fetched OK, ~20 minutes.**

| Platform | Total | Mapped | Referenced only | Status |
|---|---|---|---|---|
| greenhouse | 345 | 272 | 73 | supported |
| ashby | 248 | 209 | 39 | supported |
| lever | 99 | 73 | 26 | supported |
| **rippling** | **62** | 0 | 62 | candidate |
| **workable** | **42** | 0 | 42 | rejected by §4 |
| wordpress plugin | 24 | 0 | 24 | unbuilt |
| adp | 21 | 0 | 21 | unbuilt |
| bamboohr | 19 | 0 | 19 | unbuilt |
| teamtailor | 17 | 0 | 17 | candidate |
| workday / gem / breezy | 12 each | 0 | 12 | — |
| smartrecruiters | 1 | 0 | 1 | deferred by §4 |

**Mapped and referenced-only are split deliberately.** "Referenced" means the careers page
names the platform but no usable mapping came out of the cascade. Conflating them would
overstate real coverage, which is the §3.8 failure mode. 138 companies sit on a
*supported* ATS without being mapped — but **116 of those are `weak_only`**, meaning the
cascade found a token and validation rejected it. That is §8.2 working as designed, not a
miss: `perchenergy.com` is in that set and its board genuinely 404s. Whether validation is
too strict for the other 22 is unanswered.

Discount three rows as noise: `glassdoor` 22, `indeed` 15, `consider` 11 are careers pages
linking to their own profile on those sites, not platforms they run on. Tagged
`not-an-ats` in the mapping file.

### The measurement §4 asked for has arrived, and it disagrees with §4
`SPEC.md` §4 rejects Workable, Recruitee and Personio adapters on the stated grounds of
"SMB / agency / DACH-European skew ... **near-zero expected yield**", and then names
exactly one condition for reopening them: "**Revisit only against a measured
`unsupported_ats:{name}` distribution, never on principle.**"

That distribution now exists, and **Workable measures 42 companies — the second-largest
unpollable platform in the dataset**, ahead of ADP (21) and BambooHR (19). Near-zero is
not what 42 looks like. Recruitee (5) and Personio (11) are much weaker and their
rejections look undisturbed; Personio's XML-only objection is a separate technical point
this measurement says nothing about.

**Not re-proposed here, and no `SPEC.md` edit made** — §4 is the do-not-re-propose list
and this is the user's call. Recorded because §4 itself asked for the number, and the
number is in. The same applies in reverse to SmartRecruiters: §4 defers its adapter
pending volume, and volume came back as **1**, which argues for leaving it deferred
indefinitely.

**Rippling is the strongest unbuilt candidate on the evidence**: 62 companies, ~3x
BambooHR, never evaluated in `SPEC.md` at all, and adapter-able — its board URL carries
the token (`api.rippling.com/platform/api/ats/v2/board/{token}/jobs`, seen on
`goshippo.com`). Gated behind coverage per §8.6 regardless.

**Misdated at first pass — moved.** This session's SPEC §4 update, the real 24h churn diff, and the repo-weight decision were originally appended here mid-edit, but they happened the following day. Moved to their own dated entry below (`## 2026-09-23 — SPEC §4 measurements, the real churn diff, and the repo-weight decision`).

### Deviations from SPEC
~~Nine corrections~~ **Fourteen corrections and additions** committed to `SPEC.md` this session (§6, §9 ×3, §10, §11, §12.3, §18 ×2),
all struck-through rather than deleted, each carrying the date and the measurement:
- **§9 Greenhouse** — `first_published` **is** on the list endpoint; `departments` is
  present **only** with `content=true`; the detail endpoint returned a byte-identical
  object to the `content=true` list entry on 6/6 jobs across 2 boards; `pay_input_ranges`
  appeared on **none** of 384 postings across 8 boards, on either endpoint.
- **§9/§12.3 Lever** — exposes a structured `workplaceType` (363/363 postings), so Ashby is
  not "the only provider" with one and Lever does not need §12.3's keyword fallback. Ashby's
  values are capitalised, Lever's lowercase.
- **§9 Lever** — `createdAt` is not a publication date: 9 of 28 sampled postings over a
  year old, oldest 7.7 years. Supports §6's existing choice of `first_seen_at`.
- **§9 Ashby** — the `compensation` object is truthy even when nothing is disclosed.
- **§6** — the "list endpoint exposes only `updated_at`" claim.
- **§10** — the Greenhouse detail call on the new-posting path.
- **§11 / §18 #3** — the disclosure measurement above, corrected once after the
  precision sample (14.2% / 38.3% → 18.1% / 52.5%), with the superseded pair recorded in
  place because it had already been committed.
- **§14** — the ">25% run-over-run drop" anomaly check must be computed against the
  intersection of companies polled ok in both runs, not against run totals. Added, not
  struck — the existing rule is not wrong, it is under-specified in a way that fails
  silently.
- **§10** — `ats_job_id` stability recorded as measured rather than assumed.
- **§6** — a live example for why `first_seen_at` rather than `posted_at` is the sort key.

### Criteria checked
None — pre-M2 spike work, no `CRITERIA.md` items apply yet.

### Least confident about
- ~~The 38.3% figure is a floor for "published somewhere" and a ceiling for "cleanly
  parseable." `near_comp_keyword` is a proximity heuristic with no systematic precision
  check.~~ **Answered this session by the precision sample above — 59/60, with the
  residual error characterised.** What remains unmeasured is how the heuristic behaves on
  boards outside this mapped set; every sample so far comes from the same 255 companies.
- **Turning snippets into numbers will be harder than the snippets suggest.** Two real
  employer errors already in the sample: `$200,00 USD - $280,000 USD` (dropped digit), and
  an Ashby tier published as `{"minValue": 20, "maxValue": 20, "interval": "1 YEAR"}` — a
  twenty-dollar *annual* salary that is plainly an hourly rate. §3.8 applies.
- **The "detail endpoint is redundant" claim rests on 6 jobs across 2 boards**, neither of
  which publishes `pay_input_ranges` — and no board that does has been found. Worth
  confirming before the detail path is deleted outright.
- Whether committing an 8.5 MB results JSON per run is the right shape. Fine once; it
  should not be re-committed on every future run.

### Mapping-precision signal for iteration 6 (not this spike's to fix)
**9 of 157 mapped tokens returned 404, and every one came from `careers_page_regex`** —
zero from `slug_guess+careers_page_corroboration`. That is a direct precision signal about
the "a careers page naming its own token counts as `verified` on its own" interpretation
the iteration 6 entry flagged: it is the stage producing all the bad tokens. One of them,
`app.grammarly.com`, also looks like a junk-domain row rather than a mapping error.
Separately, 10 boards returned 200-with-zero-postings; the two checked by hand (`funga`,
`carbonfuture`) resolve to real board names via `/v1/boards/{token}` — correct mappings,
genuinely empty boards, `SPEC.md` §14's ambiguous case. That endpoint returning `name` is a
cheap corroboration signal the cascade could use.

### Next session
- ~~The mapped pool grew from 35 to 157 during this session because iteration 6's run was
  still going. Re-run this spike when that finishes.~~ **Done — iteration 6 completed
  mid-session and `--all` was re-run against all 584 mapped companies (above).**
- ~~Re-run iteration 6's cascade over the failure buckets.~~ **Done and measured
  (iteration 9 above): the junk-domain hypothesis is wrong, and re-crawling recovers
  almost nothing. Closed as a line of work.**
- **The §18 gate is not the live question yet — the user's call, 2026-09-22: "we're
  still early, still collecting sources."** The numbers below stand as a baseline to
  re-run once ClimateBase, Built In Boston and Greentown are in, rather than as a
  decision now due.
- **The `SPEC.md` §18 gate has been computed but not decided.** `BUILD.md` M7 and
  `CRITERIA.md` C-7.3 both require the go/no-go call be the user's, so
  `spikes/iteration9_measurement_gate.py` prints the four numbers and deliberately stops.
  Coverage is 13.1% of attempted domains — but over a VC-scrape population containing
  initiatives, funds and trade associations, not the watchlist/ClimateTechList/ClimateBase
  seed §18 assumes. That denominator is the crux of the decision and is the reason it is
  a judgment rather than arithmetic.
- **A Rippling adapter is the best-evidenced next integration** — 62 companies measured
  over the full portfolio (iteration 11 supersedes iteration 10's ~75 projection from a
  250-row sample). Token-in-URL, so it is adapter-able.
- **Two `SPEC.md` §4 decisions now have the measurement §4 itself asked for**: Workable at
  42 against a "near-zero expected yield" rejection, and SmartRecruiters at 1 against a
  deferral pending volume. Both are the user's call; neither was edited.
- **Run the census after every future source** — `python spikes/ats_platform_census.py
  --source <name>` — so the tally accumulates. The `by_source` column will show whether
  ClimateBase and Built In Boston skew toward different platforms than the VC portfolio,
  which is the thing that would change an adapter decision.
- **Coordination note:** this session edited `spikes/iteration6_ats_mapping_spike.py`,
  which the concurrent M0 session had committed shortly before. The edit is confined to
  `classify_and_map`'s stage-3 branch. Worth a glance from whoever owns that file next.
- ~~Repo weight is now a real question, not a nit.~~ **Decided (iteration 12): stop
  committing the full results JSON at all.** See that section above.
- ~~Recommended follow-up spikes: comp-snippet precision sampling, then a repeat-run
  diff, then the `careers_page_regex` precision fix.~~ **All done.** Precision sampling
  (this session's earlier entries), the 8-minute id-stability diff (this session), the
  real ~18.5h churn diff (iteration 12), and the `careers_page_regex` fix (iteration 8)
  are all complete. Remaining: a measurement-only pass on how many description snippets
  yield a clean min/max/interval, so M5 starts with a known hit rate.
- Concurrency note: a separate M0 session was committing to `main` throughout this one
  (`src/http.py`, `src/models.py`, the Postgres schema, `src/health.py`). Commits
  interleaved cleanly because the two sessions touched disjoint paths, but both edited
  documentation — worth checking `SPEC.md` has not drifted before the next doc change.

---

## 2026-09-22 — Addendum: a third concurrent session also built (and dropped) its own iteration 7
**Model:** Sonnet 5 · **Plan mode:** yes (design phase), no (rest)

A third session, running the iteration 6 mapping cascade recorded earlier today (see the
"Iteration 6: ATS mapping cascade for discovered companies" entry above — that work is
this session's), also independently built a job-fetching spike against the mapped output,
under the same "iteration 7" name as the session recorded immediately above. Discovered via
`git log` after the fact, not before building it — this session's `discovered_companies.csv`
and `tracking_store.py` edits were never committed, so there was no earlier signal to catch.

**Resolution, the user's explicit call:** the other session's `spikes/iteration7_live_postings_spike.py`
is already committed, more thorough (comp-in-description extraction, precision-sampled,
`SPEC.md`-corrected — see that entry). This session's simpler duplicate
(`spikes/iteration7_ats_job_fetch_spike.py` and its batch/log output) was deleted rather
than committed or reconciled. It did validate two things worth keeping, informally, since
they're consistent with the kept entry's own findings rather than contradicting them:
a 94.2% fetch-success rate across all 584 companies iteration 6 mapped (550 ok, 17,371
postings, 34 failures — all clean 404s/connection errors, the same "mapping went stale
between the mapping run and the fetch" pattern, not script bugs), and two real bugs in its
own reporting path (a Unicode character in a job title crashing print() outside the
per-company try/except, and no incremental write meaning that crash lost an entire batch)
that have no bearing on the kept spike, which didn't share that code.

**Iteration 6 itself is unaffected and stands as this session's real contribution** — it
was the input the other session's iteration 7 was reading from `discovered_companies.csv`
on disk while both sessions were live simultaneously.

### Next session
- Before doing further spike work in `spikes/`, check `git log` first — this collision
  would have been caught immediately rather than after building a full duplicate.
- Iteration 6's output (`discovered_companies.csv`, `tracking_store.py`) is still
  uncommitted as of this entry. Whether to commit it, and how it reconciles with whatever
  state the other iteration-7 session left those same files in, is still open.

---

## 2026-09-22 — Iteration 6 committed; unsupported-ATS backlog and feasibility spot-checks
**Model:** Sonnet 5 · **Plan mode:** no

### Built
- **Committed iteration 6** (`spikes/iteration6_ats_mapping_spike.py`,
  `spikes/tracking_store.py`'s extension, and the populated `discovered_companies.csv`) —
  confirmed via `git log` that only two commits had ever touched these files and neither
  came from a concurrent session, and that the working-tree CSV was a strict same-row,
  same-order superset (mapping columns filled in, nothing added/removed/reordered) of the
  last commit — safe to commit directly with no merge risk. Left the large batch/log
  scratch artifacts (`iteration6_batch_*`, `iteration6_full_run_log*.txt`,
  `sample_for_review.csv`) uncommitted, consistent with this project's existing precedent
  of not committing bulky derived-and-redundant spike output.
- `spikes/unsupported_ats_tally.py` + `spikes/unsupported_ats_tally.csv` — a re-runnable
  view over `discovered_companies.csv`'s `mapping_failure_reason` column, per `SPEC.md`
  §3.5 ("store raw, derive on read"): the raw per-company data is the source of truth, this
  is just a summary that can never drift stale, unlike a hand-maintained count would.
- `spikes/ats_integration_backlog.md` — qualitative backlog reference for a **later
  phase**, per the user's explicit framing (not built now). Ranks unsupported-ATS
  candidates by measured volume × confirmed API cleanliness, with live-confirmed endpoint
  shapes for the top five.

### Real findings from live feasibility spot-checks (top 5 by count)
- **BambooHR (57 companies) — confirmed clean, public, unauthenticated:**
  `GET {company}.bamboohr.com/careers/list` → structured JSON (title, department, city/state,
  employment type, remote flag). Not in `SPEC.md` at all yet.
- **Workable (55) — confirmed clean:** `GET apply.workable.com/api/v1/widget/accounts/{company}`
  → JSON including the company name for free, a validation signal Lever/Ashby lack.
  **`SPEC.md` §4 already rejects Workable but explicitly invites revisiting "against a
  measured `unsupported_ats:{name}` distribution, never on principle" — this count is that
  measurement**, not a new proposal.
- **Personio (42) — weaker than the count suggests.** SPEC's "XML-only" characterization
  looks stale: the documented `/xml` path returned a client-rendered Next.js HTML shell on
  one live company and a 404 on another. Flagged rather than trusted either way — needs a
  fresh sample before anyone builds against it.
- **Breezy HR (34) — confirmed clean and rich:** `GET {company}.breezy.hr/json` → JSON with
  structured `location.is_remote` and a `salary` field, comparable richness to Ashby.
- **Workday (30) — confirmed the CxS API works structurally as `SPEC.md` §4 already
  describes.** `POST {tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` returned
  clean JSON on one live tenant (`rmi.org`'s `rockymountain`), no bot challenge encountered
  this time — `postedOn` is a relative string only, confirming §4's "needs a second request
  per job for a date" concern. One clean test doesn't override §4's existing "Backlog
  only" verdict, which is about reliability at polling scale, not endpoint existence.

### Decisions made this session
- Held off on building any adapter — this is explicitly backlog/reference work for a later
  phase per the user's framing, not implementation.
- Did not touch or attempt to commit `iteration6_ats_mapping_spike.py` mid-session when it
  showed as locally modified — a concurrent session was actively editing it live (a
  User-Agent fix: `Chrome/120` was drawing false 403s from WAFs on some domains, silently
  indistinguishable from `no_careers_page`, ~4% of all failures). Waited for it to settle
  and confirmed via `git log`/`git diff` that it had been committed elsewhere before
  touching anything in that file's vicinity again.

### A second concurrent-session discovery, mid-session
- **A real bug in iteration 6's own cascade got found and fixed by the other concurrent
  session** (`93feb78`, co-authored by Opus 5/1M context), before this session touched the
  file further: `classify_and_map` accepted a careers-page-scraped token as `verified`
  without ever calling the provider API to confirm the board actually resolves — exactly
  the "verified-from-careers-page-alone... worth a second look" item this session's own
  earlier entry flagged as unresolved. Found by iteration 7 fetching all 584 mapped boards
  live: 30 dead tokens, **100% from stage 3 (careers-page regex), 0% from stage 1** (which
  already called the provider API). Fixed by adding that same live-resolution check to
  stage 3, demoting unresolvable tokens to `weak_only` rather than leaving them silently
  `verified`. Correctly kept the `voltacharging.com` → Lever `joltcharge` rebrand case as
  legitimate (name mismatch recorded, not disqualifying) rather than over-correcting.
  **Mapped count: 584 → 554 (405 verified, 149 probable).** The `unsupported_ats` tally
  above is unaffected — the fix only touched the confidence bucket.
- **A broader ATS catalog appeared, also mid-session:** `spikes/ats_platform_hosts.csv`, a
  host-pattern registry covering far more platforms than this session measured (Teamtailor,
  Gem, JazzHR, ADP, UKG, Dayforce, iCIMS, Jobvite, Taleo, SuccessFactors, Paylocity,
  Pinpoint, Homerun, Join, Softgarden, HeyJobs, Factorial, HiBob, and more), each tagged
  `supported`/`candidate`/`rejected`/`deferred`/`unbuilt`/`not-an-ats` with a `SPEC.md`
  cross-reference. **Complementary to this session's backlog doc, not a duplicate** — it
  has breadth (many more platforms, no counts, most unresearched), this session's has depth
  (real measured counts and confirmed live endpoint shapes, but only for platforms
  `iteration6_ats_mapping_spike.py`'s detection regex already looks for).

### Deviations from SPEC
None committed this session — the Personio/Workday/Workable findings are recorded as
backlog input, not as `SPEC.md` edits, per the user's explicit "later phase" framing.

### Criteria checked
None — pre-M2 spike/backlog work, no `CRITERIA.md` items apply yet.

### Least confident about
- **This session's `unsupported_ats_tally.csv` is an undercount relative to the broader
  `ats_platform_hosts.csv` catalog** — it only reflects platforms `iteration6`'s detection
  regex already checks for (13 of them), not the ~20 additional ones the other session's
  catalog now names. A truly comprehensive tally needs detection expanded to match that
  broader list before the counts mean "this is everything," not just "this is what we
  happened to look for."
- Personio's live-checked sample was 2 companies. Not enough to overturn or confirm
  SPEC's existing XML-only characterization either way.
- Whether `ats_platform_hosts.csv` and `ats_integration_backlog.md` should eventually merge
  into one artifact, or stay separate (catalog vs. measured-and-verified backlog) — not
  decided, flagging for whoever next touches either file.

### Next session
- Regenerate `unsupported_ats_tally.csv` after any further iteration 6 re-runs (the
  cascade fix above may shift companies between buckets beyond just the confidence field).
- Consider expanding `iteration6_ats_mapping_spike.py`'s `OTHER_ATS_DOMAINS` detection to
  match `ats_platform_hosts.csv`'s broader catalog, so the measured tally actually covers
  what the catalog claims to track.
- Personio needs a fresh, larger live sample before its backlog entry can be trusted either
  direction.


---

## 2026-09-23 — M0: skeleton and reliability plumbing built through package 7
**Model:** Opus 5 (1M context), then Sonnet 5 mid-session · **Plan mode:** yes (per BUILD.md's M0 header)

### Built
Full M0 plan executed through package 7 of 11 (see the approved plan for the package
breakdown). In commit order:

- **Doc amendments** — Python pin 3.12 -> 3.13 (CLAUDE.md, BUILD.md), SPEC.md §6 DDL
  rewritten in Postgres types (was SQLite-shaped: `INTEGER PRIMARY KEY`, `TEXT`
  timestamps), `migrate.yml` added as a fourth workflow to SPEC.md §5 and SECURITY.md §S2,
  CRITERIA.md's C-0.2 struck and replaced by C-0.9 (JSON export only — `jobs.db` is never
  committed under the Postgres design).
- **Repo skeleton** — `pyproject.toml`, `uv.lock` (hash-pinned), `.python-version`,
  `test.yml` (push + workflow_dispatch, zero secrets, SHA-pinned actions), and two CI
  guards: `tools/check_criteria.py` (fails the build if a criterion identifier disappears)
  and `tools/check_rls.py` (fails if a migration creates a table without enabling RLS).
- **`src/models.py`, `src/http.py`** — the network chokepoint, guards written before the
  happy path per SECURITY.md's ordering. Redirect cap, scheme allowlist, private/loopback/
  link-local address rejection (169.254.169.254 explicit), response size cap, exponential
  backoff with no retry on 4xx, per-host token bucket, optional dev disk cache. Every
  rejection logs the requested URL and resolved address.
- **Postgres schema + RLS baseline + migration runner** — `supabase/migrations/`, two
  files: RLS baseline (default-deny before any table exists) then the SPEC.md §6 core
  tables, each enabling RLS in the same migration. Supabase CLI dropped in favor of a
  ~130-line psycopg-based runner (`src/migrate.py`) — decided with the user mid-session
  once it became clear the CLI has no winget package and buys nothing over hand-authored
  SQL. `src/check_schema.py` is the live half of the RLS check (queries `pg_tables`/
  `pg_policies` directly; the static half runs in `test.yml` with no DB credential).
- **`src/health.py`** — `RunRecorder`, anomaly detection (posting drop >25%, HTTP error
  rate >10%, DB unavailable, RLS posture wrong), and the counts-only run summary
  (`format_run_summary`). The counts-only shape is enforced by the function signature, not
  by discipline, per SECURITY.md §S3. A `scrub()` helper neutralizes `@` in any third-party
  string (company name, failure reason) so C-0.8's literal "no @ character" rule holds even
  though a company name can legitimately contain one. The summary is pure ASCII — an em
  dash rendered as `?` on a cp1252 Windows console during testing, so the header is now
  plain characters only.
- **`src/export.py`** + `tests/fixtures/jobs-recent.json` — the export schema settled with
  a seven-row fixture, each row pinning a specific case (multi-band C-5.2 trap, undisclosed
  comp, hourly normalization, CAD conversion, SECURITY.md §S1's exact XSS row, a repost). A
  test asserts every fixture row matches the real row shape, so fixture and code cannot
  drift apart silently.
- **Dashboard scaffold** — `docs/index.html`, `app.js`, `health.html`, `health.js`,
  `style.css`, with the CSP meta tag and the `textContent`-only rendering rules present from
  this first commit rather than retrofitted at M9, per SECURITY.md's explicit ordering
  requirement. `tests/test_dashboard.py` makes C-S.2/C-S.3/C-S.4 build failures; verified
  against a deliberately bad probe file that it actually catches all six violation types.
- **`src/monitor.py`, `monitor.yml`, `discover.yml`** — the real entry point (open a run, do
  nothing yet, close it, write the export, ping healthchecks, exit) and the two remaining
  workflows. `tests/test_workflows.py` parses the YAML (not grep) to enforce C-S.6/7/8 as
  tests rather than manual review — this caught a real bug on the first pass, where a naive
  grep for `pull_request` "matched" every workflow because each one documents in a comment
  why the trigger is absent.
- **A real bug found and fixed mid-build**: `monitor.yml`'s commit step originally
  hardcoded the account's noreply email address as a literal string. CLAUDE.md forbids
  committing any email address and does not carve out a known-safe noreply one. Rewrote to
  assemble the identity from `github.repository_owner_id` + `github.repository_owner` at
  runtime instead, with a test now asserting no email-shaped literal exists in any workflow
  file.
- **A second real bug, found by the first live migration run**: `redact_dsn()` returned a
  bare `"<unparseable dsn>"` when `urlsplit` raised — which is exactly what happens on
  Supabase's Connect-modal URI, since it ships with a literal `[YOUR-PASSWORD]` placeholder
  that reads as an unmatched IPv6 bracket. The diagnostic was least useful in the single
  most likely failure. Added `describe_dsn_problem()`, which runs before psycopg is ever
  dialled and names the actual problem (unreplaced placeholder, wrong scheme, whitespace,
  missing host/password) without ever including the DSN itself, plus `redact_secrets()` to
  scrub psycopg's own error text before logging it (GitHub only masks the *exact* secret
  value; a substring like the bare password is a different string and slips through).

### Decisions made this session
- **Python 3.13, not 3.12** — CLAUDE.md's non-negotiable was the pin, not the number; 3.13
  was already the only interpreter on the machine. Documents amended, diff shown before
  commit per the session protocol.
- **C-0.2 struck, replaced by C-0.9** — `jobs.db` can never be committed under the Postgres
  design; the JSON-export half of the original criterion is live and carries forward.
- **Migration runner: hand-rolled psycopg, not the Supabase CLI** — the CLI has no winget
  package and its main draw (`db diff`) is moot against hand-authored migrations. Decided
  with the user via AskUserQuestion mid-session, not unilaterally.
- **Supabase connection: Session pooler (port 5432), not Direct** — flagged as a probable
  deviation from SETUP-PLATFORM.md §4 before it was confirmed: GitHub-hosted runners are
  IPv4-only, and Supabase's Direct connection is IPv6-only on Free-tier projects without the
  paid IPv4 add-on. Confirmed empirically once the secret was set correctly — the pooler
  connected on the first successful attempt. **SETUP-PLATFORM.md §4 needs a correction
  noting this**, not yet made.
- **`npx skills add supabase/agent-skills` declined for now** — the project's Supabase
  surface is a bare connection string and hand-written SQL; nearly everything the skill
  covers (RLS policy authoring, auth, storage) is §19 platform-era work. Revisit then. Saved
  to persistent memory so future sessions don't need to re-litigate it.

### Deviations from SPEC
- SPEC.md §6's DDL was SQLite-shaped and is now Postgres-shaped (diff shown, committed).
- SPEC.md §5 gained a fourth workflow, `migrate.yml` (diff shown, committed).
- SETUP-PLATFORM.md §4 still says "Direct connection" for the pipeline; empirically the
  Session pooler is what actually works from GitHub Actions on this project's Free tier.
  Not yet corrected in the document — flagged for next session.

### Criteria checked
- **C-S.13** — `uv sync --locked` from a clean state; hash-pinned lockfile confirmed.
- **C-S.14** — fetch guards, verified by 67 tests including the literal 169.254.169.254
  case, a mid-redirect block, and an oversized-body rejection.
- **C-S.6, C-S.7, C-S.8** — enforced as tests (`tests/test_workflows.py`), passing.
- **C-0.8** — the run summary contains no `@` character; verified against a company name
  and failure reason that both legitimately contain one.
- **Not yet checked (need a live push to succeed first):** C-0.1, C-0.2/C-0.9, C-0.3, C-0.4,
  C-0.5 (hard gate — needs the healthcheck grace period to elapse), C-0.6, C-0.7, C-1.2
  (partially — SUPABASE_DB_URL and HEALTHCHECK_URL now set; all four M0-relevant secrets
  exist), C-1.3 (Pages enabled and live at the predicted URL, not yet verified against a
  real committed export since the commit step is blocked).

### Real infrastructure stood up this session, with live evidence
- **Migrations applied for real** against the actual Supabase project. `check_schema.py`
  ran against the live database afterward and reported: "every public table has RLS
  enabled, and every deny-all table is on the allowlist (9 inspected)." Not a mock — a real
  query against `pg_tables`/`pg_policies`.
- **GitHub Pages enabled**, live at `https://noahm3.github.io/First-Look/`, predicted
  correctly from the owner+repo name before Pages existed.
- **The monitor ran for real**: connected to Postgres, wrote a real (empty, correctly-so)
  export, computed a summary. The pipeline itself works end to end.

### Blocked, needs the user
**`KEEPALIVE_PAT` push failed with `403: Permission ... denied to noahm3`** on the first
live monitor run's commit step. Checkout succeeded with the token (basic-auth header set
correctly), branch protection is off, and the account has full admin on the repo via a
separate `gh` session — so the problem is specific to the fine-grained PAT itself: most
likely its Contents permission is read-only rather than read/write, its repository access
doesn't actually include `First-Look`, or it needs regenerating. Cannot be diagnosed further
from this side since the token's contents aren't inspectable. **User needs to check the
token's settings on GitHub and re-set the secret if wrong; nothing else in M0 that depends
on a real commit (C-0.2/C-0.9, C-0.3, C-0.4 with real data) can be verified until this is
fixed.**

### Least confident about
- Whether the Session-pooler-over-Direct-connection finding generalizes, or is specific to
  this project's Free-tier + IPv4-only-runner combination. Worth re-verifying if Supabase's
  networking options change.
- Whether `describe_dsn_problem()`'s placeholder-detection regex is specific enough to
  Supabase's current UI, versus a more general "brackets in the authority" heuristic that
  happens to work today. Low risk either way — worst case it just doesn't fire and the
  generic unparseable-DSN message takes over.
- The two untracked spike files from the concurrent session
  (`iteration6_batch_0_150_results.json`, `iteration6_batch150_log.txt`) were left
  completely untouched throughout, per the session's standing rule of only ever staging
  explicit paths.

### Next session
**Fresh session, same milestone (M0), Opus + plan mode per BUILD.md's header — no need to
re-plan, the approved plan file covers packages 8-11 exhaustively.** Prompt to paste:

> Read CLAUDE.md, then the last two DEVLOG entries. We're continuing M0 (BUILD.md), plan
> mode already approved in the prior session — the plan file is still at
> `C:\Users\o439n\.claude\plans\valiant-dreaming-crab.md` if you need to re-read it. First,
> confirm the KEEPALIVE_PAT push issue from the last session is now fixed by re-dispatching
> `monitor.yml` and checking the commit lands. Then work through the M0 evidence sweep
> (BUILD.md §0.5): C-0.5 is the hard gate — point HEALTHCHECK_URL at a wrong URL, wait out
> the grace period, confirm the email reaches my phone, then restore it — and C-0.6 (forced
> failure -> GitHub email). Check off every M0 criterion you have real terminal output for,
> not a summary. Also: correct SETUP-PLATFORM.md §4 to say Session pooler (port 5432)
> instead of Direct connection, since Direct is IPv6-only and GitHub Actions runners are
> IPv4-only — show me that diff before committing. When M0's criteria all check out, give
> me the BUILD.md §0.5 evidence report and we'll move to M1.

---

## 2026-09-23 — SPEC §4 measurements, the real churn diff, and the repo-weight decision
**Model:** Sonnet 5 · **Plan mode:** no

### Built
Three follow-ups from the previous session's close, all requested directly by the user
in this session.

**SPEC.md 4 updated with the measurements it asked for.** Workable's rejection cites
"near-zero expected yield" and says to revisit "only against a measured
`unsupported_ats:{name}` distribution, never on principle." That distribution now exists
(iteration 11): Workable 42 companies, second only to Rippling among unpollable
platforms. Recorded as contradicting the stated premise, **not as a reversal** - the
rejection stands until the user decides to build the adapter, and §4 is the
do-not-re-propose list regardless. Recruitee (5) and Personio (11) are undisturbed;
Personio's separate XML-only objection is untouched. SmartRecruiters measured at 1,
which argues for leaving that deferral in place. Both numbers are from one discovery
source (the VC portfolio), noted as such in the addition.

**The real overnight churn number, ~18.5h apart** (`spikes/iteration7_live_postings_spike.py --all`,
labelled `mapped7`, diffed against yesterday's `mapped6` with `iteration7_run_diff.py`).
Cleaner than the earlier 8-minute diff in one respect: the mapped pool was frozen at
554/554 for the whole gap (no mapping run since the stage-3 fix), so there is no
pool-growth confound to filter out this time - every company present in `mapped6` is
still present in `mapped7`.

```
postings on shared companies: 16884 before, 16957 after
  id present in both runs : 16731
  id only in after (new)  :   226
  id only in before (gone):   153
  churn as % of before    : 2.24%
```

**Unlike the 8-minute diff, this one shows real field drift under a stable `ats_job_id`**
- 32 title changes, 24 location, 24 department, 10 `posted_at`, 5 comp, 4 workplace
type, out of 16,731 stable ids. `ats_job_id` stability (confirmed again) is about
identity, not content: the same posting can be edited in place, and `SPEC.md` §10's
lifecycle currently only touches `last_seen_at` on "still present," never the content
fields - **so an employer's edit to a live posting's title, location, department, or
comp band would go unrecorded under the current design.** Not fixed here; flagged for
the user, since it is a real design gap this measurement surfaces rather than a bug in
this spike.

**One drift worth its own line:** `basecamp-research`'s "Bioinformatics Scientist" and
`crusoe`'s "Senior Staff Data Center Operation..." both jumped `posted_at` forward by
months under the *same* `ats_job_id` (`2026-07-13` -> `2026-09-23`; `2026-05-15` ->
`2026-09-23`) - a live repost/refresh, not a new posting. Direct, first-hand evidence
for `SPEC.md` §6's "`posted_at` is unreliable" and for why `first_seen_at` must be the
system's own clock: this is not `updated_at`-style drift on every edit, it is a multi-
month jump on the field §9 currently treats as the trustworthy one.

**Comp bands moved on live postings**, not just appeared - `Antares` $150K-$210K ->
$160K-$235K, `handshake` $108K-$150K -> $108K-$160K. `SPEC.md` §11.1 describes exactly
this ("you can see whether a band moved") as a platform-era feature waiting on months
of accumulated history; this is the first real instance of it showing up in a single
overnight gap.

**~2.24% churn over ~18.5h extrapolates to roughly 2.9%/day** - a single sample, not a
stabilised rate, but a first real number for what "4x daily" polling would actually be
catching.

### Repo-weight decision, made rather than left open
The 2026-09-22 entry flagged this without deciding. Deciding now: **stop committing the
full per-run results JSON at all.** Growth so far - 8MB, 13MB, 14MB, 26MB across four
commits as the mapped pool grew from 157 to 554 - already sits at **59MB in git history
from four superseded snapshots alone**, and git keeps every committed version forever;
deleting the working-tree copy after each run stopped the tree from bloating but did
nothing for `.git`. ClimateBase and Built In Boston will grow the mapped pool by
roughly an order of magnitude, which would take this from a minor inefficiency to a
real problem - the same class of issue `SPEC.md` §6 already reasons through for
`jobs.db`, just at spike scale.

`spikes/iteration7_live_postings_mapped6_results.json` (already committed) untracked
and deleted from the tree - its numbers are already in earlier DEVLOG entries and are
not lost. `spikes/iteration7_live_postings_*_results.json` added to `.gitignore` so
future runs (`mapped7` and on) are never committed at all. What gets committed instead:
the printed run summary, a small derived text/CSV report when one is worth keeping
(`spikes/iteration7_run_diff_24h_report.txt`, a few KB), and the real numbers written
into DEVLOG - which is where the analysis lives regardless of whether the raw JSON is
kept.


### Decisions made this session
- Workable's rejection in `SPEC.md` §4 is left standing even though the measurement
  contradicts its stated premise — building the adapter is the user's call, and §4 is
  the do-not-re-propose list either way.
- Stop committing the full per-run `iteration7_live_postings_*_results.json` at all;
  keep it local, commit a small text/CSV report and the DEVLOG numbers instead.

### Deviations from SPEC
None new this session — the `SPEC.md` §4 additions are corrections to a rejected-alternatives
table (recording measurements it explicitly asked for), not a deviation from a design
decision.

### Criteria checked
None — pre-M2 spike work, no `CRITERIA.md` items apply yet.

### Least confident about
- The ~18.5h churn sample is one data point. 2.24% churn / ~2.9%-per-day extrapolation
  should not be treated as a stable rate until it's been measured across more than one
  overnight gap.
- The §10 content-drift gap (title/location/department/comp changing under a stable
  `ats_job_id`, with only `last_seen_at` currently updated on "still present") is
  flagged, not sized — no measurement yet of how often it would actually matter for a
  user re-viewing a posting they've already seen.

### Next session
- Decide whether `SPEC.md` §10's "still present" step should also refresh drifted
  content fields, or whether that is explicitly out of scope for the pre-platform build.
- Continuing discovery: run `spikes/ats_platform_census.py --source <name>` after each
  new source (ClimateBase, Built In Boston, Greentown) lands, so the platform tally
  accumulates rather than resetting.
- Also outstanding from the prior entry: a measurement-only pass on how many description
  comp snippets yield a clean min/max/interval, so M5 starts with a known hit rate.



---

## 2026-09-23 — M0 closed: KEEPALIVE_PAT fixed, a real last-successful-run bug found and
## fixed, C-0.5 verified end to end, all criteria checked
**Model:** Sonnet 5 · **Plan mode:** yes (carried over from the M0 planning session)

### Built
Continuing directly from the earlier same-day M0 session (packages 1-7 built, blocked on
a KEEPALIVE_PAT 403). This session unblocked it and closed the milestone for real, against
the live database and the live workflows — not fixtures.

- **KEEPALIVE_PAT fixed by the user** (permissions corrected in the token's own GitHub
  settings). Re-dispatched `monitor.yml`; the commit landed as `d6b9878`, attributed to
  `noahm3`, not `github-actions[bot]` — C-0.3's real evidence.
- **Migrations applied for real**, twice: the original two files from the earlier session,
  then a third (`20260923000003_runs_ok_column.sql`, see the bug below). `check_schema.py`
  confirmed against the live `pg_tables`/`pg_policies` both times.
- **GitHub Pages confirmed live** at `https://noahm3.github.io/First-Look/`, serving the
  real committed export.
- **A real bug found by live testing, not by unit tests**: after a C-0.6 forced-failure
  run (100% HTTP error rate, exit 1), the *next* run's export reported that failed run's
  finish time as `last_successful_run`, with `stale: false` — a green marker for a run
  that had just failed. Root cause: `runs` had no column recording a run's own anomaly
  verdict, so `last_successful_run_at()` could not distinguish a cleanly-finished run from
  one that finished but tripped an anomaly. Confirmed with a two-step live test: dispatched
  a force-failure run (run 6, finished ~16:48:44), then a clean run (run 7, ~16:49) —
  run 7's export correctly reported run 5's earlier timestamp (16:41:12), *skipping over*
  run 6 despite it finishing more recently. Fixed by adding `runs.ok BOOLEAN NOT NULL
  DEFAULT true`, written once at close time from `should_fail_run()`, filtered on by
  `last_successful_run_at()`. Deliberately *not* applied to `previous_finished_run()` —
  the run-over-run anomaly baseline needs the true prior state regardless of that run's own
  outcome, or a real posting-count drop would compare against stale data. SPEC.md §6's
  `runs` table definition updated to match, diff shown and approved before commit.
- **SETUP-PLATFORM.md §4 and §8 corrected.** Both said the pipeline uses Supabase's Direct
  connection string. Empirically wrong: GitHub-hosted Actions runners are IPv4-only, and
  Supabase's Direct connection is IPv6-only on Free-tier projects without the paid IPv4
  add-on — the first live `migrate.yml` run couldn't connect at all until the secret was
  switched to the Session pooler (port 5432), which worked immediately. Also recorded why
  the *Transaction* pooler (6543) is wrong too: no prepared-statement support, which
  psycopg needs. Reserved for the future Next.js read layer instead.
- **C-0.5 — the hard gate — run for real, end to end, and it found a genuine gap on the
  first attempt.** User shortened the healthchecks.io check's period/grace to 2min/2min
  for a fast test, then set `HEALTHCHECK_URL` to a bad value and a run was dispatched so
  the real check stopped receiving valid pings. The dashboard correctly showed ~27 minutes
  of downtime, but **no DOWN alert email arrived** — only a recovery (UP) email after the
  user manually re-pinged it. This is exactly the failure mode a dead-man's switch exists
  to catch, so it was treated as a real finding, not dismissed. Diagnosed live with the
  user (checked the Integrations tab — channel present, active, configured for both UP
  and DOWN — ruling out the obvious "no channel attached" cause). Root cause: healthchecks.io
  was still evaluating the check's "next expected ping" deadline against the *old* 6h/2h
  period active when the last real ping had landed, so the first post-change evaluation
  cycle ran on stale timing. Once that cycle passed, a genuine DOWN email reached the
  user's phone, confirmed directly and separately from the dashboard's own status.
  Settings and the real ping URL were restored to production values (6h/2h); a subsequent
  real run logged `healthcheck ping accepted` and the user confirmed the dashboard showed
  UP.
- **CRITERIA.md closed out.** All eight non-superseded M0 criteria (C-0.1, C-0.3–C-0.9)
  checked with dated evidence notes — real commit hashes, real log excerpts, real curl
  output against the live Pages URL, and explicit user confirmations for the two criteria
  (C-0.5, C-0.6) that depend on an email actually arriving, which only the user can see.
  C-0.2 stays struck (superseded, from the earlier session).

### Decisions made this session
- **The `runs.ok` column is a decision that changed SPEC.md §6** — diff shown, approved,
  committed, per session protocol.
- **C-0.5's fast-test methodology (temporarily shrinking period/grace) was the user's own
  call**, offered as the recommended option among three paced differently. It was the right
  call: it surfaced a real, subtle bug (the stale-evaluation-cycle delay) that a full
  8-hour real-timing wait would also have hit, just slower and with much less clarity about
  *why* the first email didn't arrive on schedule.
- **Git push races with the concurrent session's own direct pushes to `main` happened
  repeatedly** during live testing (multiple `git stash push -u` / rebase / `stash pop`
  cycles to preserve that session's uncommitted spike work without ever touching it). No
  conflict was ever force-resolved in either direction; every rebase was clean.

### Deviations from SPEC
- SPEC.md §6: `runs` gained the `ok` column, documented above and in the file itself.
- SETUP-PLATFORM.md §4/§8: Direct connection corrected to Session pooler, documented above
  and in the file itself.

### Real infrastructure now running, with live evidence for each claim
- Live Postgres database, migrated, RLS-verified against the actual schema (not a mock).
- Live GitHub Pages dashboard serving a real, continuously-updating export.
- Live scheduled workflow (`0 11,15,19,23 * * *` UTC) confirmed to have fired
  unattended at least once (2026-09-23T15:22:10Z) before this session began fixing
  anything — the automation itself was never in question, only the two credentials
  wired into it.
- Live dead-man's switch, proven with a real induced outage and a real recovered alert.

### Least confident about
- **Whether the C-0.5 stale-evaluation-cycle explanation is exactly right** or merely
  the most plausible account consistent with what was observed. Not verified against
  healthchecks.io's own source or documentation. Low practical risk either way — if wrong,
  the failure mode is "alert arrives a bit late," not "alert never arrives," which is a
  much smaller problem for a system with 6h/2h production settings than it would be for
  a testing setup with 2min/2min.
- **The git-push race with the concurrent session is not defended against by monitor.yml's
  retry logic**, which does one `git pull --rebase --autostash` and gives up on conflict.
  During the actual unattended leave window there is no second writer, so this is not a
  real production risk today — but it's worth remembering if that assumption ever changes.
- Same open items carried from the earlier same-day entry: the Session-pooler finding's
  generality across Supabase plan tiers, and the placeholder-detection regex's specificity
  to Supabase's current UI.

### Criteria checked
C-0.1, C-0.3, C-0.4, C-0.5, C-0.6, C-0.7, C-0.8, C-0.9 — every non-superseded M0 criterion
that doesn't require a later milestone's code. **M0 is closed.**

### Next session
**M1 — Watchlist ingest and dedupe. BUILD.md recommends Sonnet 5, no plan mode** (M1 is
small and mechanical: build `config/watchlist.yml` with 20-30 companies, and the
ingest/dedupe logic against it — C-1.6 through C-1.8). Prompt to paste:

> Read CLAUDE.md, then the last two DEVLOG entries. We just closed M0 — confirm the
> milestone header says M1 and tell me the recommended model and plan-mode setting from
> BUILD.md, then wait for me to confirm before starting. M1 is watchlist ingest and
> dedupe (C-1.6 - C-1.8): `config/watchlist.yml` with 20-30 companies whose ATS I already
> know (this becomes M3's ground truth, so we should choose deliberately), plus the
> ingest logic that dedupes on `canonical_domain` and never drops a company with no
> resolvable domain. Commit at each criterion, not once at the end.

---

## 2026-09-23 — Iteration 12: the Rippling parser, built and validated
**Model:** Sonnet 5 · **Plan mode:** no

### Built
Following the user's direct steer after a checkpoint question ("is there anything you
would do in this spike") - the census (iteration 11's earlier entry) found Rippling as
the largest unbuilt integration (62 companies); this builds and validates it.

`spikes/iteration11_rippling_spike.py`, reusing `iteration7_live_postings_spike.py`'s
proven infra (rate limiter, `blank_posting` shape, comp-in-description extraction,
redaction) via import rather than duplicating it.

**Two steps, small-batch first throughout**, because the census only recorded which
*host* each company referenced, never the board token itself:

1. **Token resolution.** A 6-company hand sample suggested two patterns (a hosted page
   `ats.rippling.com/{token}/jobs` and an embed's `data-job-board-id`). The full
   62-company run found five real shapes: hosted-bare, hosted `/embed/{token}/jobs`,
   hosted locale-prefixed `/en-GB/{token}/jobs`, the embed attribute, and the literal API
   call embedded directly in inline JS. **One company's embed snippet was
   HTML-entity-double-escaped** (`data-job-board-id=&quot;gradientcomfort&quot;`) —
   unescape-before-matching, the exact ordering bug already found once this session on
   Greenhouse's `content` field. All three token sources resolve against the same API.
   **62/62 resolved.**
2. **Fetch.** `api.rippling.com/platform/api/ats/v2/board/{token}/jobs` is paginated
   (`items`/`page`/`pageSize`/`totalItems`/`totalPages`) and, **unlike Greenhouse, its
   detail call is not redundant** — `createdOn` (a real posted date) and
   `payRangeDetails` (structured comp: location/currency/frequency/rangeStart/rangeEnd,
   cleaner than any of the three existing providers) exist only on the per-job detail
   endpoint.

**Full run: 61/62 companies ok, 716 postings.** 100% field coverage on
title/department/location/workplace_type/url/posted_at. Comp: 68 structured + 275
description-confident = **47.9% combined**, consistent with the 45-62% range already
measured on Greenhouse/Lever/Ashby. The reused comp-in-description extractor
**generalized to a 4th provider with zero new bugs** — correctly separated a "raised
$161M" funding mention from a genuine "$100-110K base salary" line inside the same
posting's description.

### Real findings caught by reading actual output, not asserted from counts
- **`door.com` and `latch.com`** — discovered via different VC investors (Techstars,
  Tekfen Ventures) — resolve to the **same** Rippling token and produce identical
  postings. A real company found under two different domains, which `canonical_domain`
  dedup cannot catch since the domains themselves are genuinely different strings, not a
  normalization artifact of the same one. Worth remembering for M1's dedup logic:
  domain-based dedup has a structural blind spot for rebrands/multi-domain companies that
  no amount of URL normalization fixes.
- **`cleartrace.io`** was the one 404. Checked before writing it off as a resolver bug:
  the exact token is still live in a job-detail link on the company's own careers page
  right now, so resolution was correct — the board itself has simply gone stale since.
  Same transient/dead-board pattern already seen in iterations 6 and 8.

### Decisions made this session
- Built the parser as its own script importing iteration7's helpers, rather than adding
  Rippling as a fifth provider inside iteration7 directly — the token-resolution step has
  no equivalent for the other three providers and would have been an awkward fit in that
  file's existing CLI shape.

### Deviations from SPEC
None — this is new-adapter exploration, still `spikes/`, not a deviation from any
existing design decision.

### Criteria checked
None — pre-M2 spike work, no `CRITERIA.md` items apply yet.

### Least confident about
- Whether the 5 token-resolution patterns found here are exhaustive. They cover 62/62 of
  this population, but a different discovery source (ClimateBase, Built In Boston) could
  surface a sixth shape the same way this one kept surfacing new ones past the first
  6-company sample.
- No systematic precision check on the comp-in-description extraction for this provider
  specifically, beyond the one hand-verified example above — it reuses code already
  precision-sampled on Greenhouse/Lever/Ashby, but Rippling's description HTML structure
  hasn't been checked as closely.

### Next session
- If a Rippling adapter is ever built for real in `src/`, the token-resolution step
  (five URL/attribute patterns, unescape-before-matching) is the part that took the most
  iteration here and is worth porting deliberately rather than re-discovering.
- Continue applying `spikes/ats_platform_census.py` after each future discovery source
  lands, per the standing methodology (iteration 11, the platform census, from the previous session).

---

## 2026-09-23 — M1 closed: watchlist ingest and dedupe, ground truth built by hand
**Model:** Sonnet 5 · **Plan mode:** no

### Built
- `src/watchlist.py` — loads `config/watchlist.yml`, canonicalizes a domain (bare host or
  full URL, `www.` stripped, port stripped) down to one comparable form, and ingests each
  entry idempotently.
- `Database.ingest_manual_company` (`src/db.py`) — keys on `company_sources.source_id`
  (the canonical domain, or a name-derived slug when there is none) rather than on
  `canonical_domain` alone, because a nullable-and-`UNIQUE` column can't dedupe two
  no-domain entries against each other (NULL never equals NULL). A domain match against a
  company already known via another source attaches the `manual` source instead of
  creating a duplicate row.
- `.github/workflows/watchlist.yml` — a fifth workflow, `workflow_dispatch` only, modeled
  directly on `migrate.yml`'s already-audited posture (secret scoped to one step, pinned
  SHAs). Needed because `SUPABASE_DB_URL` only ever decrypts inside a running Action —
  there is no local `.env`, and GitHub secrets cannot be read back by any CLI, a real
  platform limitation rather than a project choice. SPEC.md §5 updated to document it.
- `tests/test_watchlist.py` (20 tests) — a small in-memory fake of the `companies` +
  `company_sources` tables (not a mock of `ingest_manual_company` itself) so C-1.6, C-1.7,
  and C-1.8 are exercised against the real dedupe logic, including cross-call idempotency.
- `config/watchlist.yml` — 17 companies, the actual deliverable of this milestone.

### Decisions made this session
- **The watchlist has exactly one job: be an independent answer key for M3, not a bigger
  production company list.** Surfaced when the user asked "what is the watchlist actually
  for" and I'd initially seeded it from the discovery spikes' own `verified`-confidence
  tier. That was circular: M3 will grade a cascade built from the same kind of logic that
  produced that tier, so grading it against that tier's own output can't catch the cascade
  being confidently wrong, only catch it disagreeing with an earlier version of itself. The
  user's own multi-year, hand-compiled company list (kept outside the repo — Downloads,
  never committed as-is) is the real independent source; broader production coverage from
  the discovery spikes (the 584 `verified`/`probable`-mapped companies from iteration 6)
  is a separate, still-open task via a different `company_sources.source`, not this file.
- **String-matching an ATS's name in page HTML is not verification.** The first pass
  (`spikes/iteration13_personal_list_verify.py`) fingerprinted by searching fetched HTML
  for `greenhouse.io`/`lever.co`/etc. The user manually clicked "Apply" on Machine Metrics
  and landed on Indeed, not Greenhouse — real signal that something was wrong. Investigating
  found the string match was real but stale (a leftover embed script pointing at a token
  that 404s on Greenhouse's own API) and, separately, that CircleCI's only "greenhouse"
  mention was a cookie-consent/CSP allowlist entry with zero connection to any real job
  data. Rewrote the check (`spikes/iteration14_api_verify.py`) to hit each ATS's real
  public jobs API for the extracted token and require a real, parseable response —
  Pixability also dropped this way (403s a plain fetch, unconfirmable either way).
- **A mapped board with zero current postings is still a valid ground-truth entry.**
  Appcues' Lever token is live and correct but returns 0 jobs right now — kept rather than
  swapped out, since the cascade should report "mapped, zero jobs," not "unmapped" or
  "weak," and that is itself worth being able to check.
- **Every entry in the final 17 was independently hand-clicked and confirmed live by the
  user**, not just API-checked by Claude — the user's own words: "I clicked through and
  confirmed all of these links and ATS are accurate as of right now."
- Spiro Technologies (from the personal list) was excluded rather than silently swapped: its
  careers link now redirects to a Greenhouse board under the token `cordance`, not `spiro` —
  looks like an acquisition or rebrand, left for the user to confirm on their own time
  rather than guessed at.

### Deviations from SPEC
- SPEC.md §5 gained a fifth workflow, `watchlist.yml` (diff shown, approved, committed) —
  same manual-only posture as `migrate.yml`, for the reason above.

### A live, unrelated finding worth recording
- The user's personal company-tracking CSV (outside the repo, in Downloads) carries a
  `Contact / Connection` column of real people's names and a plaintext password reused
  across several numbered Gmail accounts used for a monitoring tool. Only `Name` and
  `Careers Page`/`Home Page` were ever read out of it into this session; nothing from those
  other columns touched the repo or got printed more than once. Flagged to the user
  directly as worth rotating — not otherwise acted on, since it's outside this project's
  scope.

### Criteria checked
- **C-1.6** — two live `watchlist.yml` GitHub Actions dispatches against the real
  database, back to back, both reporting zero newly-created duplicates (real run IDs and
  output quoted in `CRITERIA.md`).
- **C-1.7** — `tests/test_watchlist.py::TestIngestWatchlist::
  test_c_1_7_a_url_variant_and_a_bare_host_resolve_to_one_company`, against the real code.
- **C-1.8** — the two `test_c_1_8_*` tests in the same file, against the real code.
  C-1.7 and C-1.8 are unit-test evidence, not a live Supabase dispatch: the committed
  watchlist has no URL-variant-duplicate or no-domain entry to force either case for real,
  and manufacturing one just to exercise it live was judged not worth polluting the
  production ground-truth set.

### Least confident about
- Whether 17 companies (5 Greenhouse, 5 Lever, 3 Ashby, 4 Rippling) is enough diversity for
  M3's false-positive check, or whether it's worth growing further before M3 actually
  starts — nothing forces the number, and the user can add more at any time.
- C-1.7 and C-1.8 resting on unit-test evidence alone. The logic under test is the same
  `ingest_manual_company`/`canonicalize_domain` code the live-verified C-1.6 runs exercise,
  just not the exact input shapes those two criteria describe, so this is a real gap in
  live coverage, not just a formality — flagged to the user before checking either box.
- Whether the API-based verification method (`iteration14`) itself has a blind spot
  symmetric to the one it just fixed — it trusts a 200 + non-empty JSON response from the
  provider's real API, which is a much stronger signal than a string match, but still
  assumes the token-extraction regex found the *company's own* board rather than an
  unrelated one that happens to share a guessable token. Not hit in practice this session,
  but not proven impossible either.

### Next session
**M2 — ATS adapters. BUILD.md recommends Sonnet 5, no plan mode.** Fetch the real API docs
linked in `SPEC.md` §9 during this milestone rather than building from memory — Lever's v0
and Getro have no authoritative documentation, which is why recorded fixtures are the real
contract. Prompt to paste:

> Read CLAUDE.md, then the last two DEVLOG entries. We just closed M1 — confirm the
> milestone header says M2 and tell me the recommended model and plan-mode setting from
> BUILD.md, then wait for me to confirm before starting. M2 is ATS adapters (C-2.1 –
> C-2.7): Greenhouse, Lever, and Ashby adapters that fetch and parse real postings,
> reusing `spikes/iteration1_ats_spike.py` and `spikes/iteration7_live_postings_spike.py`'s
> already-proven fetch/parse logic rather than rebuilding it from scratch, plus fixtures
> recorded from live responses in `tests/fixtures/`. Fetch the real API docs linked in
> SPEC.md §9 first rather than building from memory. Commit at each criterion, not once at
> the end.

---

## 2026-09-24 — M2 closed: 8 ATS adapters, scope expanded mid-session
**Model:** Sonnet 5 · **Plan mode:** yes, for the implementation plan; execution inline

### Built
Scope grew from the original 3-provider M2 ask to 8 during the session-start
conversation, per the user's explicit direction ("let's ALSO fold in BambooHR, Workable,
Personio, Breezy HR, and Workday... the more ATS integrations the merrier"). Workday was
deferred after flagging its distinct risk profile (hard pagination cap, Akamai bot
management, no "revisit on measurement" escape hatch in `SPEC.md` §4 the way
Workable/Personio have) — the user chose to do the other 5 now and leave Workday for
later. `SPEC.md` §4 (Workable/Personio rejections reopened, Recruitee/Workday untouched)
and §9 (5 new provider sections) updated and shown as a diff before committing, per
protocol.

An implementation plan was written (`docs/superpowers/plans/2026-09-24-m2-ats-adapters.md`,
12 tasks) and executed inline, strict TDD throughout (RED confirmed before every
implementation, GREEN confirmed after):

- `src/ats_common.py` — shared `AdapterResult` envelope and `parse_iso_or_epoch_ms`
  (handles Lever's epoch-ms, everyone else's ISO-8601, Workable's date-only strings).
- `src/ats_greenhouse.py`, `src/ats_lever.py`, `src/ats_ashby.py` — the original 3,
  rebuilt against fresh live fixtures and the official docs fetched this session, not
  reused verbatim from the September spikes.
- `src/ats_rippling.py`, `src/ats_bamboohr.py`, `src/ats_workable.py`,
  `src/ats_personio.py`, `src/ats_breezy.py` — the 5 new providers.
- 342 tests total (up from ~305 before this session), all passing with the network
  disabled; fixtures under `tests/fixtures/ats/<provider>/` recorded from real live
  responses on 2026-09-24, not carried over from the September spikes.
- `CRITERIA.md` C-2.1 – C-2.12 checked, each with the real command/output that satisfies
  it, including a live run of every adapter against a real `FetchClient` (no fixtures)
  against the M1 watchlist's real companies plus a few more real companies for the 4
  providers the watchlist doesn't cover yet.

### Real findings from re-verifying live rather than trusting September's notes or memory
- **Appcues' Lever board (M1's "mapped, zero postings" ground-truth entry, written
  2026-09-23) is now a genuine 404** — the board was removed entirely within one day of
  that DEVLOG entry, not just emptied. Confirmed twice (building the Lever fixtures, and
  again in the live watchlist run). **M1's watchlist needs Appcues re-verified or
  swapped before M3 uses it as ground truth.**
- **BambooHR does not 404 on an invalid subdomain** — it 302-redirects to
  `www.bamboohr.com`'s marketing homepage, itself a 200 HTML response. `src/http.py`'s
  `FetchClient` follows the redirect, so the adapter never sees a 404; the
  unexpected-shape branch is what actually catches a bad token. Documented in the
  adapter's docstring and the test fixture is a 200 HTML body, not a 404 status.
- **BambooHR's list endpoint has no per-job URL and no date field at all** (confirmed by
  reading the full live response, not a truncated sample). The adapter constructs the URL
  from the known `{token}.bamboohr.com/careers/{id}` pattern (confirmed live, 200);
  `posted_at` stays `None` — there is nothing to read it from.
- **Workable's public widget endpoint has no compensation field**, unlike the documented,
  authenticated admin API's `salary` object — confirmed by reading the full live response.
- **Personio is genuinely inconsistent across tenants, confirmed live in real time**: one
  tenant 200s with real XML, one 404s, one rate-limits (429), and the original
  spot-check's "client-rendered shell" tenant (`nexwafe`) now 307-redirects to
  `personio.com` — a *third* distinct failure shape for that one tenant since the earlier
  spot-check, re-checked live while building this task rather than assumed stable.
- **Personio has real structured per-position compensation** (`<salaryInformation>`:
  min/max/currencyCode/type) on tenants where the feed works — richer than any of the
  other 4 new providers, and worth noting since `SPEC.md` §4's original Workable/
  Personio rejection was framed around "near-zero expected yield," not data richness.
- **Rippling's `payRangeDetails` is a list of range objects, not a single dict** — the
  plan's draft code treated it as a dict (`.get(key)` on the object directly), which
  would have silently left every real disclosed-comp posting classified `NONE`. Caught
  before shipping by testing against real fixture data (a real posting on `adiabatic`'s
  board) instead of the plan's constructed example, which happened to be a job with
  `payRangeDetails: []` and wouldn't have caught the bug.
- **A pre-commit hook block during this session caught a real recruiting-team email
  address embedded in a live Lever fixture's description fields**, and a
  separate manual read (not caught by the hook, which only pattern-matches emails) found
  a real recruiter's name and WhatsApp number in a live Personio fixture's description.
  Neither adapter reads description fields at all; both fixtures were trimmed to only the
  fields each adapter actually parses before committing. Worth generalizing: **any fixture
  recorded from a live ATS response should be trimmed to adapter-relevant fields before
  committing, not just scanned for the hook's narrow email regex** — job descriptions
  routinely name real recruiters.

### Decisions made this session
- **Comp handling for all 8 adapters is deliberately shallow**: `comp_data_quality`
  (structured/parsed/none) and, where available, a human-readable `comp_raw_summary`
  string. No `CompTier` rows are constructed (no Decimal parsing, no period-enum mapping,
  no annualization) — that is explicitly `SPEC.md` §11 / M5's job per `BUILD.md`, and
  `CRITERIA.md`'s M2 block doesn't test compensation at all. Chosen for uniformity across
  9 providers in one milestone rather than partially building comp for some and not
  others.
- **Token resolution (finding which token a company's careers page actually uses) stays
  out of every adapter** — Rippling's multi-shape token resolution and any future
  discovery-side work belongs to M3's mapping cascade. Every adapter here takes an
  already-known token (or, for Personio, a full known-working hostname — see below).
- **Personio's adapter takes a full `host`, not a bare `token`**, unlike the other 7 —
  the TLD genuinely varies per tenant (`.com` and `.de` both confirmed live), so the
  caller (eventually M3) is the one that resolves which TLD actually works, rather than
  this adapter guessing.
- **Fixtures were live-refetched this session rather than reused from the September
  spikes**, even where a spike had already captured similar data, per `SPEC.md` §9's own
  instruction and `C-2.7`/`C-2.12`'s explicit ask. This is what caught the Rippling
  `payRangeDetails` shape bug and the Appcues/Personio/BambooHR behavior changes above.

### Deviations from SPEC
- `SPEC.md` §4: Workable and Personio rejections reopened (diff shown, approved,
  committed). Recruitee and Workday untouched.
- `SPEC.md` §9: 5 new provider sections added (diff shown, approved, committed).
- None beyond what's recorded in SPEC.md itself — every adapter behavior described above
  as a "finding" is now also documented in that provider's own module docstring.

### Criteria checked
C-2.1 through C-2.12, each with real command output pasted into `CRITERIA.md` itself
rather than summarized. Two honest gaps flagged inline rather than glossed over:
Ashby's watchlist coverage is 3 real tokens, not 5 (a gap in M1's watchlist, not this
adapter), and Rippling's `department_raw` has an adapter but no dedicated unit test
(exercised only implicitly by the live watchlist run).

### Least confident about
- **Whether the 8-adapter scope jump in one milestone was the right call versus
  splitting it** — nothing broke, but M2's original 3-4h estimate was sized for 3
  providers, not 8, and the next milestone (M3, mapping cascade) now needs to validate
  against 8 providers' worth of real-world quirks instead of 3.
- **Lever's `salaryRange` sub-field names** (`min`/`max`/`currency`/`interval`) are
  carried over from `SPEC.md` §9's existing text, not independently re-verified live this
  session — none of the fixtures captured happened to have a disclosed `salaryRange`.
  Low risk given comp isn't normalized this milestone anyway, but worth a fresh check
  before M5 builds real `CompTier` rows against it.
- **Whether trimming fixtures to "only what the adapter reads" is sufficient hygiene
  long-term**, or whether recording live fixtures at all is inherently risky enough that
  this project wants a stronger rule (e.g., always run a human-name/phone-number check,
  not just the pre-commit hook's email regex) before the next provider gets added.

### Next session
**Before M3: reconcile with `origin/main`.** This session's local `main` (4 commits: the
final-review fix pass) and `origin/main` (3 commits: M6, pushed by a concurrent session)
have diverged but merge cleanly (`git merge-tree` shows zero conflicts) — neither was
merged or pushed this session; that's the user's call, not this session's to make
unilaterally.

**M3 — Mapping cascade and validation. BUILD.md recommends Opus 5, plan mode.**
Highest-risk correctness work per `BUILD.md`'s own framing, now scoped against 8
providers instead of 3. Before starting: re-verify or swap Appcues in
`config/watchlist.yml` (see the finding above), and decide whether the watchlist needs
more Ashby/BambooHR/Workable/Personio/Breezy-HR entries added so C-3.1's "zero false
positives" check has real ground truth for all 8 providers, not just the original 4.

**Also before M4 builds the polling loop:** decide how Rippling's per-job detail call
should be scoped during a real recurring poll (once per new posting? backfill window
only?) rather than the current fetch-once-per-company shape's implicit "detail call every
posting, every run" — flagged but deliberately not solved in this session, see the final
review's Rippling ruling above.

### A concurrent-session note, same shape as the 2026-09-22 M-1 entry's correction
While Task 11 was running (between this session's own `fc372ef` and `aa6faf9` commits,
23:52–23:56 local time), a commit not made by this session landed directly on `main`:
`1e64063`, "BUILD.md: supersede the parallel-tracks rejection in §0.3, add §0.3a policy"
— it strikes §0.3's single-track rationale and adds a new §0.3a permitting parallel
git-worktree tracks under specific conditions. Same commit-identity convention as every
commit in this repo, so it isn't distinguishable in `git log` from this session's own
work, but the content (a reasoned policy change, `Co-Authored-By: Claude Sonnet 5`) reads
like another concurrent Claude Code session, not a manual edit — the same situation the
2026-09-22 M-1 entry already documented once. This session's own ledger had already ruled
to skip git-worktree isolation for M2, reasoning from §0.3's *pre-strike* text; that
ruling stands (no file conflicts occurred — the concurrent commit touched only
`BUILD.md`), but is now reasoning from a policy that changed under it mid-session. Flagged
here rather than silently reconciled, per this project's own convention for exactly this
situation.

**Confirmed after this session finished its own work**: that concurrent session went on
to build and push an entire milestone — `origin/main` carries 3 commits this session's
local checkout never pulled: `03518c5` "M6: Getro discovery", `da11f1d` "CRITERIA: check
C-6.1", `7ca804c` "DEVLOG: M6 closed, Getro discovery". `git merge-tree` shows a clean,
conflict-free merge between this session's local `main` (4 commits ahead, the final-review
fix pass) and `origin/main` (3 commits ahead, M6). Neither branch was merged or pushed by
this session — left for the user to decide how to reconcile, since a push to the public
remote is exactly the kind of shared-state action this project's own instructions say to
confirm first, not decide unilaterally.

### Final review (fresh Opus reviewer, dispatched after Task 11)
Reviewed the full branch (`78d5754..2d1d83f`, excluding the concurrent session's
`1e64063`) against the plan, `SPEC.md`, `CRITERIA.md`, and this session's own ledger.
**One Critical, confirmed independently before fixing:** `src/ats_rippling.py` only
fetched page 0 of a paginated board, silently capping any board over 20 postings at 20
while still reporting `ok=True` — 9 of the 62 companies in `spikes/
iteration11_rippling_full_results.json` exceed that. Fixed: loops `totalPages` with a
defensive cap.

**Five Important findings, all confirmed independently and fixed in one pass:**
- 7 of 8 adapters (all but Workable) could raise `AttributeError`/`LookupError` if a
  provider's nested field (location, categories, compensation, department) drifted to a
  bare string — a real risk given none of these 8 endpoints are documented. Fixed with
  new `as_dict()`/`as_list()` helpers in `src/ats_common.py`; Personio's XML parsing now
  also catches `LookupError`/`ValueError` (an unrecognized `<?xml encoding?>` raises
  `LookupError`, not `ParseError` — confirmed live).
- All 8 `tests/test_ats_*.py` files imported `httpx` directly, which `pyproject.toml`'s
  `TID251` rule bans outside `src/http.py` — this would have failed CI's `ruff check .`
  on push. Fixed with a shared `respond()` helper in `tests/ats_fixtures.py` and a
  matching per-file-ignore; also fixed a pre-existing `test_watchlist.py` format issue
  and excluded `docs/superpowers/plans/` from ruff's scope (it formats markdown code
  fences, and a point-in-time plan isn't source to keep in sync with the formatter).
- Greenhouse never implemented the `content=true` size-cap fallback this project already
  decided on in September (DEVLOG's iteration7 entry: "Recovered 618 postings on the one
  board that hit it"). Fixed: retry without `content=true` on `RESPONSE_TOO_LARGE`.
- `C-2.1` was checked without literally meeting "5 known tokens" for Lever (4/5 —
  Appcues' 404) and Ashby (3/5 — the watchlist only has 3 Ashby entries). Fixed by finding
  and live-verifying 2 more real tokens per gap (Lever `joltcharge`, Ashby `cambium` +
  `stillbright`) via the actual adapters. `CRITERIA.md` corrected, appended not reworded.
- Rippling's per-job detail-call failures were silent and uncounted. Fixed:
  `AdapterResult.degraded_count`.

**One Important finding, ruled rather than fixed:** Rippling's per-poll detail-call
volume (~778 requests across a full mapped set, 4x/day) is a real cost, but it's an M4
polling-loop design question — how often to re-fetch detail for an already-seen posting —
not an M2 adapter defect, since M2 fetches once, it doesn't poll repeatedly. Deferred to
M4; see Next session.

**9 Minor findings, deferred per this project's own review-process rule** (never enter
the fix pass): token/host string-injection validation in 3 adapters (low risk today —
`src/http.py` already blocks private-address SSRF — real risk is data-integrity once M3
feeds in scraped tokens, not a security hole); Workable's `ats_job_id` missing an explicit
`str()`; Ashby's `comp_raw_summary` falling back to a Python `repr()` of a list; an
empty-but-technically-`STRUCTURED` comp edge case in Rippling/Lever; BambooHR's
`isRemote`/`locationType` fields being effectively always-null in the one real board
sampled; a few test-assertion-specificity gaps; two now-stale docstring citations.

Full test suite after the fix pass: **356 passed** (up from 342 before final review).
`ruff check .` and `ruff format --check .` both clean, repo-wide.
