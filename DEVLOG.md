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
