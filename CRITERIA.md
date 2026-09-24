# First Look — Acceptance Criteria

**Rules for this file, which override any instruction to tidy it:**

1. **Lines are never deleted.** A criterion that no longer applies is struck through with
   a date and reason:
   `- [ ] ~~Old criterion~~ (superseded 2026-10-04: replaced by C-4.2)`
2. **New criteria are appended**, never inserted in a way that renumbers existing ones.
3. **Every edit to this file must be shown as a diff before it is committed.**
4. Claude may check boxes and append. Claude may not delete, renumber, or reword an
   existing criterion without being asked directly.

Check a box only when you have seen the actual output, not a summary of it.

**2026-09-17 consolidation note:** the Security block at the end of this file was merged
in from `SECURITY.md` (via `first-look-security-patch.md`), and C-8.5–C-8.8 were merged
into the M8 block from `first-look-sources-patch.md` (Greentown Labs). Both source
patches are preserved in `archive/`. Nothing above this note was reworded or renumbered.

---

## M-1 — Setup

- [ ] **C-1.1** `git push` to the public repo succeeds
- [ ] **C-1.2** `gh secret list` shows `HEALTHCHECK_URL`, `RESEND_API_KEY`,
      `KEEPALIVE_PAT`, and `NOTIFY_PROFILES`
- [ ] **C-1.3** Pages is enabled, serving `/docs` from `main`, and the URL loads
- [ ] **C-1.4** Actions workflow permissions are set to read-and-write
- [ ] **C-1.5** healthchecks.io check exists, period matches the run schedule, and the
      alert email is one reachable on a phone
- [ ] **C-1.9** `.gitignore` includes `Connections.csv`, `connections*.json`, and
      `config/notify/` **before the first commit**
- [ ] **C-1.10** Repository name does not identify the project as a personal job search,
      and no README ties it to the owner

## M0 — Skeleton and reliability plumbing

- [x] **C-0.1** The scheduled workflow runs unattended without manual triggering
      (2026-09-23: a `schedule`-triggered run fired at 15:22 UTC with no dispatch)
- [ ] ~~**C-0.2** A run commits `jobs.db` and the JSON exports back to the repo~~
      (superseded 2026-09-22: `jobs.db` is never committed — `SPEC.md` §6 moved state to
      Postgres and §15 says so explicitly, so this criterion can no longer pass as
      written. The JSON-exports half is live and is re-stated as C-0.9.)
- [x] **C-0.3** Commits are attributed to the user's account, not `github-actions[bot]`
      (2026-09-23: commit `d6b9878`, authored as `noahm3` via that account's own GitHub
      noreply identity, made by `monitor.yml` using `KEEPALIVE_PAT`)
- [x] **C-0.4** The dashboard loads on the Pages URL and shows a green
      `last_successful_run` (2026-09-23: `https://noahm3.github.io/First-Look/
      jobs-recent.json` served `stale: false` with a populated `last_successful_run`
      from a real run)
- [x] **C-0.5** **Breaking the healthcheck URL produces an email to the user's phone.**
      Do not proceed past M0 until that email has arrived.
      (2026-09-23: `HEALTHCHECK_URL` set to a bad value, healthchecks.io period/grace
      temporarily shortened to 2min/2min for a fast test. First attempt surfaced a real
      gap — no DOWN email arrived even though the dashboard showed downtime, only an
      UP/recovery email after a manual ping. Root cause: the check's "next expected
      ping" deadline was still computed from the old 6h/2h period active when the last
      real ping landed, so the first evaluation cycle ran on stale timing before
      catching up. Once that cycle passed, a genuine DOWN alert email reached the
      user's phone — confirmed by the user, separately from the dashboard state.
      Production settings restored (6h/2h) and the real ping URL restored; a
      subsequent real run logged "healthcheck ping accepted" and the dashboard
      confirmed UP.)
- [x] **C-0.6** A forced non-zero exit produces a GitHub workflow-failure email
      (2026-09-23: `--force-failure` dispatched twice, both exited 1 on a real
      `http_error_rate` anomaly; user confirmed a GitHub failure email arrived)
- [x] **C-0.7** Two overlapping runs cannot occur (concurrency group verified)
      (2026-09-23: two `monitor.yml` dispatches 5s apart — the second sat `queued`
      then `pending` until the first reached `completed`, never running concurrently)
- [x] **C-0.8** The run summary prints counts only and contains no `@` character
      (2026-09-23: real run log showed the full summary format with zero `@`
      characters even while reporting a failing-company reason; also unit-tested)
- [x] **C-0.9** A run commits the JSON exports under `docs/` back to the repo. This is the
      only state the repo still holds (`SPEC.md` §6) and it doubles as the
      PAT-attributed keepalive commit (§16). Replaces the struck C-0.2.
      (2026-09-23: commit `d6b9878` and subsequent runs, each committing a real
      `docs/jobs-recent.json` diff)

## M1 — Watchlist ingest and dedupe

- [x] **C-1.6** Ingesting the watchlist twice creates zero duplicate companies on the
      second run. (2026-09-24, against the final 17-entry, real-API-verified,
      hand-confirmed-by-the-user file: run `35948412764`: "17 entries -> 0 created, 17
      already present, 0 with no domain" — all 17 were already rows in the database from
      earlier dispatches this session, so this run was itself a genuine re-ingest and
      correctly created zero duplicates; run `35948465336` immediately after: identical
      output, "17 entries -> 0 created, 17 already present, 0 with no domain". Earlier in
      the session, a fresh subset of these same rows was also observed going from
      `N created, 0 already present` to `0 created, N already present` on a second
      dispatch — e.g. run `35936442516` -> `35936489777` for the file's prior 13-entry
      revision — so both the create and the re-ingest halves of this criterion have live
      evidence, just not in the same pair of runs against the final file content)
- [x] **C-1.7** `https://www.X.com/careers?utm=1` and `x.com` resolve to one company row.
      (2026-09-23: `tests/test_watchlist.py::TestIngestWatchlist::
      test_c_1_7_a_url_variant_and_a_bare_host_resolve_to_one_company`, passing against the
      real `ingest_manual_company`/`canonicalize_domain` code. Not exercised live against
      Supabase — `config/watchlist.yml`'s real entries don't currently contain a
      duplicate-under-a-URL-variant pair to force the case)
- [x] **C-1.8** A company with no resolvable domain is ingested and flagged rather than
      dropped or crashed on. (2026-09-23: `tests/test_watchlist.py::TestIngestWatchlist::
      test_c_1_8_a_company_with_no_resolvable_domain_is_ingested_and_flagged` and
      `test_c_1_8_re_ingesting_a_no_domain_company_does_not_duplicate_it`, passing against
      the real code path. Not exercised live — the production watchlist has no no-domain
      entry yet)

## M2 — ATS adapters

- [x] **C-2.1** Greenhouse, Lever, and Ashby each return parsed postings for 5 known
      tokens, with non-empty titles and URLs. (2026-09-24: live run against real M1
      watchlist companies with a real `FetchClient`, no fixtures — Greenhouse 5/5 ok
      (owllabs 2, markforged 3, brandwatch 10, vestmark 10, 3playmedia 3 postings);
      Lever 4/5 ok (logrocket 7, cfsenergy 105, palantir 318, ro 52 postings), 1 correctly
      `FAILED http_error: HTTP 404` on `appcues` — its board is genuinely gone as of
      today, see the M2 DEVLOG entry, not an adapter bug. **Ashby only 3/3, not 5**: the
      M1 watchlist has just 3 Ashby entries (crusoe 350, helpscout 10, wistia 2 postings)
      — a gap in M1's watchlist composition, not this adapter; all 3 known tokens work.)
      **Correction, same day, after the final-review pass flagged this note as checked
      without literally meeting "5 known tokens" for two providers:** re-ran against 2
      more real, live-verified tokens per gap — Lever `joltcharge` (6 postings, replacing
      `appcues`, real 5/5) and Ashby `cambium` (5 postings) + `stillbright` (6 postings)
      (real 5/5, alongside the original crusoe/helpscout/wistia). All 8 real tokens
      (`spikes/ats_platform_detections.csv`) confirmed live via the actual adapters, not
      fixtures. Greenhouse and Lever now both genuinely 5/5; Ashby now genuinely 5/5.
- [x] **C-2.2** `department_raw` is populated from each provider's own field. (2026-09-24:
      `tests/test_ats_greenhouse.py::test_department_raw_populated_from_departments_field`,
      `tests/test_ats_lever.py::test_department_raw_populated_from_categories_team`,
      `tests/test_ats_ashby.py::test_department_raw_populated`, all passing against real
      recorded fixtures.)
- [x] **C-2.3** Ashby's `workplace_type_raw` is captured where present. (2026-09-24:
      `tests/test_ats_ashby.py::test_workplace_type_raw_captured_where_present`, passing.)
- [x] **C-2.4** Unit tests pass with the network disabled. (2026-09-24: `pytest -v`, full
      suite, `342 passed in 1.02s`, `tests/conftest.py`'s socket-blocking fixture active
      throughout.) **Updated same day, after the final-review fix pass added 13 more
      tests** (Rippling pagination, 6 nested-type-drift crash tests, a Personio encoding
      test, a Greenhouse size-cap-fallback test): `pytest -v` → `356 passed in 1.03s`.
- [x] **C-2.5** Fixtures exist per provider for: normal board, empty board, malformed
      JSON, 404. (2026-09-24: `tests/fixtures/ats/{greenhouse,lever,ashby}/` each carry
      `normal.json`, `empty.json`, `malformed.json`, `not_found.json`, all recorded from
      real live responses except the hand-constructed malformed cases.)
      **Correction, same day:** Lever's `empty.json` is also hand-constructed (`[]`), not
      live-recorded — Appcues, the real zero-postings board this fixture was meant to
      capture, went from "mapped, zero postings" to a genuine 404 within one day (see the
      M2 DEVLOG entry), so no live zero-postings Lever board was available when this
      fixture was built.
- [x] **C-2.6** A missing Lever `createdAt` produces a null, not an exception. (2026-09-24:
      `tests/test_ats_lever.py::test_missing_created_at_produces_null_not_exception`,
      passing.)
- [x] **C-2.7** Implementation was written against the live API docs fetched during this
      milestone, not from memory. (2026-09-24: fetched
      docs.greenhouse.io/job-board.html, hire.lever.co/developer/documentation, and
      developers.ashbyhq.com/docs/public-job-posting-api during this session; also fetched
      live fixtures for all three providers same-day rather than reusing September spike
      output.)
- [x] **C-2.8** Rippling, BambooHR, Workable, Personio, and Breezy HR each return parsed
      postings for a known real company, with non-empty titles and URLs (scope added
      2026-09-24 — Workday deferred, see SPEC.md §4). (2026-09-24: live run against real
      M1 watchlist companies for Rippling — shippo 5, stem-inc 14, algorand-foundation 3,
      gotenna-inc 7 postings, all ok; BambooHR/Workable/Personio/Breezy HR have no M1
      watchlist entries yet, so verified against real companies found via
      `spikes/ats_platform_detections.csv` instead — `ph7.bamboohr.com` (4 postings),
      `apply.workable.com/.../aerones` (34 postings), `strohm.jobs.personio.com`
      (11 postings), `elysium-health.breezy.hr` (1 posting) — all confirmed live and
      captured as fixtures, `tests/test_ats_{bamboohr,workable,personio,breezy}.py` all
      passing.)
- [x] **C-2.9** `department_raw` is populated from each of the 5 new providers' own field,
      where the provider exposes one. (2026-09-24:
      `test_department_raw_populated_from_department_label` (BambooHR),
      `test_department_raw_populated` (Workable), `test_department_raw_populated`
      (Personio), `test_department_raw_populated_where_present` (Breezy HR) — all passing.
      Rippling's equivalent field exists in the adapter but wasn't separately unit-tested;
      the live watchlist run above exercises it implicitly, not explicitly asserted.)
- [x] **C-2.10** Fixtures exist per new provider for: normal board, empty board, malformed
      response, 404. (2026-09-24: `tests/fixtures/ats/{rippling,bamboohr,workable,
      personio,breezy}/`. Two real deviations from a literal 404, both ledgered and
      documented in the adapters' own docstrings: BambooHR doesn't 404 on an invalid
      subdomain, it 302-redirects to a 200 HTML marketing page — `not_found.html` captures
      that instead; Personio doesn't 404 uniformly either — `not_found.txt` is the real
      empty 404 body from `be-levels.jobs.personio.com`, and a second fixture
      (`not_xml.html`) covers the distinct "200 + non-XML body" failure mode this provider
      also exhibits.)
- [x] **C-2.11** Unit tests for all 8 providers (Greenhouse, Lever, Ashby, Rippling,
      BambooHR, Workable, Personio, Breezy HR) pass with the network disabled. (2026-09-24:
      `pytest -v`, full suite including all 8 `tests/test_ats_*.py` files,
      `342 passed in 1.02s`.) **Updated same day: `356 passed in 1.03s`** after the
      final-review fix pass (see C-2.4's correction).
- [x] **C-2.12** Personio's XML feed shape was freshly re-verified against a live request
      during this milestone, not assumed from the September spike/backlog notes — the
      earlier spot-check found one company serving a client-rendered shell instead of XML.
      (2026-09-24: `strohm.jobs.personio.com/xml?language=en` confirmed live 200 + real
      XML, `be-levels.jobs.personio.com` confirmed live 404, and the tenant from the
      original spot-check (`nexwafe`) re-checked live and found to now 307-redirect to
      `personio.com` — a third distinct behavior, documented in
      `tests/test_ats_personio.py` and the adapter's own docstring rather than silently
      updated over the original finding.)

## M3 — Mapping cascade and validation

- [x] **C-3.1** **Zero false positives** against the watchlist, where the correct answer
      is already known. One false positive means tightening the guard before proceeding.
      (2026-09-24: `python -m src.mapping --check-watchlist`, live, against
      `config/watchlist_expected.yml` -- 31 companies across all 8 providers:
      "verdicts: TP=31 FP=0 FN=0 TN=0", exit 0. One real false positive was found
      *outside* the watchlist while reviewing the 300-domain sample -- shield.ai mapped to
      an acquired subsidiary's board because its real board probed inconclusive -- and
      fixed with regression tests before this run.)
- [x] **C-3.2** A `weak`-confidence result is recorded as a mapping failure and does not
      enter the polling loop (2026-09-24:
      `tests/test_db_mapping.py::TestC32WeakNeverEntersThePollingLoop` (4 tests, incl.
      a loosened-SQL case) and
      `tests/test_mapping_validate.py::TestFailures::test_c_3_2_weak_is_recorded_as_a_failure_not_accepted`,
      passing.)
- [x] **C-3.3** A short or collision-listed slug cannot be accepted at `probable`
      (2026-09-24: `tests/test_mapping_validate.py::TestGuard::test_c_3_3_*` (3 tests),
      passing; removing the guard makes 2 of them fail.)
- [x] **C-3.4** Every failure carries a `mapping_failure_reason`; none are null
      (2026-09-24: `test_c_3_4_every_failure_in_the_matrix_carries_a_closed_set_reason`
      and `tests/test_db_mapping.py::TestRecordMapping::test_c_3_4_a_failure_without_a_reason_is_refused`,
      passing. The 300-domain run's 242 failures all carry a reason.)
- [x] **C-3.5** `data/mapping_review.csv` contains every accepted mapping with its
      confidence and method (2026-09-24: 58 rows from the 300-domain dry run, commit
      `988065f`, opened and read row by row. shield.ai's wrong row from an earlier run is
      fixed and absent; capsule8 -> Lever `sophos` is present by the user's acquisition
      decision, labelled `careers_page+redirected_domain`.)
- [x] **C-3.6** Slug hit rate, cascade coverage, confidence distribution, and
      failure-reason distribution recorded in DEVLOG (2026-09-24: DEVLOG "M3: mapping
      cascade and validation" entry and its addendum.)

## M4 — Monitoring loop and seed mode

- [ ] **C-4.1** A second consecutive run reports zero new postings and updates
      `last_seen_at` on all of them
- [ ] **C-4.2** Deleting three posting rows causes the next run to report exactly three new
- [ ] **C-4.3** A company pointed at a garbage token is flagged while the run completes and
      every other company is still polled
- [ ] **C-4.4** A posting removed from a board gets `closed_at` set
- [ ] **C-4.5** A posting reappearing within 90 days with a matching `content_hash` is
      marked `is_repost`
- [ ] **C-4.6** Seed mode populates without producing new-posting output or sending email
- [ ] **C-4.7** Seed mode makes no Greenhouse detail calls
- [ ] **C-4.8** A 200-with-zero-postings response is treated as suspicious only when
      `last_nonzero_postings_at` is set

## M5 — Compensation

- [ ] **C-5.1** A single-range posting filters correctly against both min and max inputs
- [ ] **C-5.2** **A multi-band posting where no single band satisfies a combined min+max
      filter returns false**, even though the collapsed values would satisfy it
- [ ] **C-5.3** An hourly posting matches a $200k annual filter after normalization
- [ ] **C-5.4** A CAD posting is converted before comparison
- [ ] **C-5.5** A null-comp posting is excluded with the toggle off and included with it
      on, **while both numeric inputs have values**
- [ ] **C-5.6** `comp_raw_summary` is preserved verbatim regardless of parse success
- [ ] **C-5.7** Unparseable comp degrades to `parsed` or `none` rather than raising
- [ ] **C-5.8** Comp backfill updates a posting that gains a range after first being seen

## M6 — Getro

- [x] **C-6.1** At least two Getro boards parse successfully from `__NEXT_DATA__` --
      3/3 confirmed live 2026-09-24 (Breakthrough Energy Ventures, Blue Bear Capital,
      Convective Capital), both via `python -m src.getro --dry-run` and via a real
      `workflow_dispatch` of `discover.yml` against production
      (github.com/noahm3/First-Look/actions/runs/35954998865): "getro: 3/3 boards
      parsed (0 failed) -> 26 companies created, 1 already present"
- [ ] ~~C-6.2 A company present in both Getro and an ATS board produces one posting row,
      sourced `'ats'`~~ (superseded 2026-09-17: Getro no longer produces posting rows at
      all — `SPEC-REVISION-01` §R0 made it a company source only. See `SPEC.md` §7.2.)
- [ ] ~~C-6.3 Getro postings appear for companies that failed ATS mapping~~ (superseded
      2026-09-17: same reason as C-6.2 — there is no Getro-sourced posting path to appear
      on. An unmapped company is now invisible; see `SPEC.md` §5, §8.6.)

## M7 — Coverage sample (decision point)

- [ ] **C-7.1** 100 Built In Boston companies run through the full cascade
- [ ] **C-7.2** Cascade coverage and failure-reason distribution recorded in DEVLOG
- [ ] **C-7.3** A go/no-go decision on the full crawl recorded in DEVLOG, **made by the
      user, not by Claude**
- [ ] **C-7.4** The payload regime for §12.8 is determined from the projected posting count

## M8 — Full discovery crawls

- [ ] **C-8.1** A 20–50 request smoke test completes without blocks before the full crawl
- [ ] **C-8.2** A deliberately killed crawl resumes from its checkpoint without duplicating
      rows
- [ ] **C-8.3** Both crawls completed while attended, before leave begins
- [ ] **C-8.4** `--dump-facets` output reviewed and alias files seeded
- [ ] **C-8.5** The Greentown crawl returns roughly 300 companies across all six
      categories, each with `is_climate = 1` and a category in `industry_tags`
- [ ] **C-8.6** Greentown pagination is handled — the crawl does not stop at page 1
- [ ] **C-8.7** A company appearing in both Greentown and ClimateBase produces one
      `companies` row with two `company_sources` rows
- [ ] **C-8.8** The overlap matrix across all four discovery sources is recorded in
      DEVLOG

## M9 — Dashboard, filters, RSS

- [ ] **C-9.1** Filter state round-trips through the URL: set filters, copy URL, open in a
      fresh browser, same view
- [ ] **C-9.2** **The undisclosed-salary toggle works correctly while both numeric inputs
      have values**
- [ ] **C-9.3** Title search is case-insensitive
- [ ] **C-9.4** Salary inputs multiply by 1000; a value over 1000 is treated as literal
      dollars
- [ ] **C-9.5** Dismissed postings dim rather than vanish, and "show dismissed" restores
      them
- [ ] **C-9.6** Dismissals survive a page reload
- [ ] **C-9.7** All three empty states render distinctly
- [ ] **C-9.8** The stale banner appears on the main page when the last run is over 48h old
      or failed
- [ ] **C-9.9** Health information is reachable only via the hamburger, not on the jobs page
- [ ] **C-9.10** Cards show "Found Nh ago" under 24 hours and "Found N days ago" above
- [ ] **C-9.11** A posting with no comp shows "comp not disclosed", never a blank field
- [ ] **C-9.12** `location_class = unknown` is a selectable filter option
- [ ] **C-9.13** `feed.xml` validates and renders in a reader
- [ ] **C-9.14** The page loads acceptably on a phone over cellular
- [ ] **C-9.15** Neither the dashboard nor `/health` displays any email address, personal
      name, or profile contents

## M10 — Notifications

- [ ] **C-10.1** A new matching posting produces an email to the profile's address
- [ ] **C-10.2** The same posting is never emailed twice to the same profile
- [ ] **C-10.3** A run with no new matches sends no email
- [ ] **C-10.4** A second profile with different filters receives a different set
- [ ] **C-10.5** Adding a profile requires no code change
- [ ] **C-10.6** A Resend failure does not fail the run or lose the posting — it retries
      next run
- [ ] **C-10.7** **No email address appears in any committed file or run log.**
      `notifications_sent` stores profile names only.
- [ ] **C-10.8** The "Get email alerts" button opens the hosted form pre-filled with the
      current filter query string

## M11 — LinkedIn connections

- [ ] **C-11.1** The local script reduces `Connections.csv` to `{company: count}` with no
      names, titles, or emails in the output
- [ ] **C-11.2** The dashboard upload control loads the JSON and persists it in
      `localStorage`
- [ ] **C-11.3** Cards show a connection count for matched companies and nothing for
      unmatched ones
- [ ] **C-11.4** Connection data survives a page reload and is absent in a different browser
- [ ] **C-11.5** **`git status` shows no connection file at any point**, and
      `git log --all -- Connections.csv` returns nothing
- [ ] **C-11.6** `company_aliases.yml` improves match rate on at least a few real misses

## M12 — Privacy audit and burn-in

- [ ] **C-12.1** `git log -p` across all history contains no email address
- [ ] **C-12.2** A full Actions run log, read as an anonymous visitor, contains no personal
      data
- [ ] **C-12.3** No connection file exists in the working tree or git history
- [ ] **C-12.4** The published dashboard and `/health` page, viewed logged out, expose
      nothing personal
- [ ] **C-12.5** DEVLOG contains no incidental personal detail
- [ ] **C-12.6** Renaming a board token flags that company; the run completes and it appears
      on the health page
- [ ] **C-12.7** Pointing a discovery source at a dead domain fails the discovery workflow
      without affecting monitoring
- [ ] **C-12.8** A forced >25% posting drop exits non-zero and produces a GitHub email
- [ ] **C-12.9** Disabling the schedule for two days produces a healthchecks email
- [ ] **C-12.10** Fourteen consecutive days of scheduled runs completed before leave begins,
      and the run log's final twenty lines answer "what's wrong" without a stack trace

## Security (verify in M9, M10, M11, and again in M12)

- [ ] **C-S.1** A fixture posting with `<img src=x onerror=...>` in its title renders as
      literal text; no script executes
- [ ] **C-S.2** A posting with a `javascript:` URL has its link dropped, not rendered
- [ ] **C-S.3** No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, or `document.write`
      appears anywhere in the dashboard source
- [ ] **C-S.4** A CSP meta tag is present and the page functions with no inline scripts or
      event handlers
- [ ] **C-S.5** A malformed connections upload is rejected with a message, not applied
- [ ] **C-S.6** No workflow triggers on `pull_request` or `pull_request_target`
- [ ] **C-S.7** The PR test workflow has no secrets in scope
- [ ] **C-S.8** Every third-party Action is pinned to a full commit SHA
- [ ] **C-S.9** "Require approval for all external contributors" is enabled
- [ ] **C-S.10** A deliberately malformed `NOTIFY_PROFILES` produces an error message
      containing no parsed content
- [ ] **C-S.11** The integration test asserts captured stdout contains no `@` character
- [ ] **C-S.12** `KEEPALIVE_PAT` is fine-grained, single-repo, contents-only, and expires
      after leave ends — expiry date recorded in DEVLOG
- [ ] **C-S.13** Dependencies install from a hash-pinned lockfile
- [ ] **C-S.14** `src/http.py` caps redirect depth, rejects non-http(s) schemes, and
      rejects private/loopback/link-local addresses
- [ ] **C-S.15** Secret scanning and push protection are enabled on the repository
- [ ] **C-S.16** The repository has no collaborators
