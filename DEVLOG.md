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
  ~4,074 kicked off in the background, **still running as this entry is written** (274 of
  4,284 checked at time of writing; see the tally below, to be updated once complete).

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

### Unsupported-ATS tally (partial — background run still in progress, 274/4,284 checked)
| Provider | Count |
|---|---|
| BambooHR | 5 |
| Polymer | 4 |
| Breezy HR | 4 |
| WordPress + WP Job Manager | 3 |
| Workday | 2 |
| careers-page.com | 2 |
| Workable | 2 |
| Recruitee | 2 |
| PyjamaHR | 1 |
| Personio | 1 |
| ApplyToJob | 1 |

Confidence so far: 20 `verified`, 8 `probable` (~10% of checked). Other failure buckets:
116 `no_careers_page`, 79 `unknown`, 20 `weak_only`, 4 `js_rendered`. **This table will need
updating once the full run completes** — flagging now per the user's explicit ask to track
this, since it's the input to a "build another adapter" decision (`SPEC.md` §8.6, §18
measurement #2), not because the count is final.

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
- Full run completes in the background; report the final distribution and unsupported-ATS
  tally, then game-plan reducing `no_careers_page`/`unknown` (most likely: junk-domain
  filtering upstream in `discovered_companies.csv`, not more cascade logic).
- A new spike session was requested in parallel: fetching live postings from the
  `verified`/`probable`-mapped companies' actual ATS APIs (Greenhouse, Lever, Ashby to
  start) — separate from this mapping work, prompt handed to the user directly rather than
  recorded here.

---

## 2026-09-22 — Iteration 7: live postings from mapped companies' ATS APIs
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

### Deviations from SPEC
Nine corrections committed to `SPEC.md` this session (§6, §9 ×3, §10, §11, §12.3, §18 ×2),
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
- **§11 / §18 #3** — the disclosure measurement above.

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
- The mapped pool grew from 35 to 157 *during* this session because iteration 6's run was
  still going; it was at ~750 of 4,284 rows checked at session end. Re-run this spike when
  that finishes — the command is `--all`, it takes ~90 seconds, and the pool could be
  several hundred companies.
- ~~Recommended follow-up spikes, in the order they de-risk the most: comp-snippet
  precision sampling, then a repeat-run diff, then the `careers_page_regex` precision
  fix.~~ **Precision sampling was done this session** (above). Remaining, in order: a
  repeat-run diff 24h apart to measure real posting churn and confirm `ats_job_id` is
  stable across runs — which §10's whole lifecycle assumes and nothing has verified — then
  the `careers_page_regex` precision fix, then a measurement-only pass on how many
  description snippets yield a clean min/max/interval, so M5 starts with a known hit rate.
- Concurrency note: a separate M0 session was committing to `main` throughout this one
  (`src/http.py`, `src/models.py`, the Postgres schema, `src/health.py`). Commits
  interleaved cleanly because the two sessions touched disjoint paths, but both edited
  documentation — worth checking `SPEC.md` has not drifted before the next doc change.
