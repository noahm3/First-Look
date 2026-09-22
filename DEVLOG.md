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
