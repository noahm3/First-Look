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

- [ ] **C-0.1** The scheduled workflow runs unattended without manual triggering
- [ ] **C-0.2** A run commits `jobs.db` and the JSON exports back to the repo
- [ ] **C-0.3** Commits are attributed to the user's account, not `github-actions[bot]`
- [ ] **C-0.4** The dashboard loads on the Pages URL and shows a green
      `last_successful_run`
- [ ] **C-0.5** **Breaking the healthcheck URL produces an email to the user's phone.**
      Do not proceed past M0 until that email has arrived.
- [ ] **C-0.6** A forced non-zero exit produces a GitHub workflow-failure email
- [ ] **C-0.7** Two overlapping runs cannot occur (concurrency group verified)
- [ ] **C-0.8** The run summary prints counts only and contains no `@` character

## M1 — Watchlist ingest and dedupe

- [ ] **C-1.6** Ingesting the watchlist twice creates zero duplicate companies on the
      second run
- [ ] **C-1.7** `https://www.X.com/careers?utm=1` and `x.com` resolve to one company row
- [ ] **C-1.8** A company with no resolvable domain is ingested and flagged rather than
      dropped or crashed on

## M2 — ATS adapters

- [ ] **C-2.1** Greenhouse, Lever, and Ashby each return parsed postings for 5 known
      tokens, with non-empty titles and URLs
- [ ] **C-2.2** `department_raw` is populated from each provider's own field
- [ ] **C-2.3** Ashby's `workplace_type_raw` is captured where present
- [ ] **C-2.4** Unit tests pass with the network disabled
- [ ] **C-2.5** Fixtures exist per provider for: normal board, empty board, malformed
      JSON, 404
- [ ] **C-2.6** A missing Lever `createdAt` produces a null, not an exception
- [ ] **C-2.7** Implementation was written against the live API docs fetched during this
      milestone, not from memory

## M3 — Mapping cascade and validation

- [ ] **C-3.1** **Zero false positives** against the watchlist, where the correct answer
      is already known. One false positive means tightening the guard before proceeding.
- [ ] **C-3.2** A `weak`-confidence result is recorded as a mapping failure and does not
      enter the polling loop
- [ ] **C-3.3** A short or collision-listed slug cannot be accepted at `probable`
- [ ] **C-3.4** Every failure carries a `mapping_failure_reason`; none are null
- [ ] **C-3.5** `data/mapping_review.csv` contains every accepted mapping with its
      confidence and method
- [ ] **C-3.6** Slug hit rate, cascade coverage, confidence distribution, and
      failure-reason distribution recorded in DEVLOG

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

- [ ] **C-6.1** At least two Getro boards parse successfully from `__NEXT_DATA__`
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
