# Iteration 16 spike notes: Getro's "Load more" — not found headlessly

Follow-up to SPEC.md §7.2's `/companies` domain-field finding (previous session). The
UI has a "Load more" button on `/companies` (and, it turns out, on `/jobs` too) — this
spike tried to find what it calls, without a browser.

## What's confirmed

- **The Next.js SSR data route ignores pagination.**
  `/_next/data/{buildId}/companies.json` always returns the same first 12 companies
  regardless of query string — tried `page`, `offset`, `skip`, `cursor`, `after`,
  `companiesPage`, `p`, all ignored. "Load more" is not server-side pagination via a
  query param on this route.
- **Static analysis of the JS actually loaded for `/companies` found no search/pagination
  fetch call.** Checked every chunk the Next.js build manifest lists for that route (main
  app bundle, page-specific chunk, every shared chunk) — ~14 files. No `fetch`/`.get`/
  `.post` call site building a companies-search request, no hardcoded API base URL beyond
  getro.com's own marketing pages. The feature is very likely behind the "Load more"
  button's own dynamic `import()`, which Next.js code-splits into a chunk that's never
  requested until the button is actually clicked — invisible to anything that doesn't
  click it in a real browser.
- **A real correction to already-shipped code, not just a `/companies` limitation:**
  `/jobs` has the exact same undercount, and `src/getro.py` (M6, `CRITERIA.md` C-6.1)
  already depends on it. Climate Draft's `/jobs` page reports `jobs.total = 11474` but
  `jobs.found` only ever has 20 entries; even Breakthrough Energy Ventures — the smallest,
  most-checked board in `config/getro_boards.yml` — has `total = 106` against the same
  `found = 20`. `extract_companies` in `src/getro.py` only reads `found`, so on every
  board it's ever run against, it's been seeing a slice of the real company list, not the
  whole thing. Not a correctness bug (every company it sees is real, C-6.1's own wording
  — "at least two Getro boards parse successfully" — still holds), but a completeness gap
  that predates this spike and was never measured until now.

## What this means for the `/companies`-as-domain-fix idea

Still promising in principle (real `domain` field, 12/12 populated) but now clearly
blocked on the same unsolved problem as the jobs undercount, not a separate one: finding
Getro's actual client-side search/pagination endpoint. That needs the same method that
found Consider's real endpoint (`spikes/iteration2_consider_spike.py`) — a real devtools
session against a live board, watching the network tab while clicking "Load more" —
not more URL guessing from the terminal. Recorded as the next step, not attempted here.

## Scope note

This spike deliberately did not attempt to fix `src/getro.py`'s jobs undercount. That's
real follow-up work (arguably higher priority than the `/companies` question, since it
affects an already-shipped, already-checked criterion), but it's a code change, not a
spike — flagged in DEVLOG for a future session to pick up deliberately, not slipped in
here.
