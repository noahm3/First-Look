# Iteration 15 spike notes: what a real Consider adapter would take

Not a decision to build it — SPEC.md §18 item #4 and BUILD.md §5 gate Consider behind
the M7 measurement gate, which hasn't run. This is exploration to inform that decision
later, same spirit as `spikes/iteration2_consider_spike.py` but broader.

Re-verified live 2026-09-24 with `spikes/iteration15_consider_spike.py`, against 4 real
boards beyond the one (`jobs.greentownlabs.com`) SPEC.md §7.6 already had confirmed.

## Newly confirmed

- **The flow generalizes.** Greentown Labs, Congruent Ventures, Bessemer Venture
  Partners, and MCJ Collective all worked: real session cookie + CSRF token from
  `window.serverInitialData`, then a working `POST /api-boards/search-jobs`.
  `companyDomain` was populated 10/10 in every sample across all 4 — matches SPEC.md
  §7.6's claim that Consider doesn't have Getro's domain-resolution gap.
- **A fingerprint-flagged candidate is not a confirmed board.** SOSV
  (`techjobs.sosv.com/jobs`), flagged `consider` by `spikes/iteration3_vc_board_discovery.py`'s
  heuristic, 404s outright. Same caveat SPEC.md already gives Getro's "getro (likely)"
  column — a real live check per board is still required before trusting any of these
  lists, this platform included.
- **Board sizes vary far more than the one known example suggested.** Total jobs per
  board sampled: Greentown Labs 580, Congruent Ventures 456, MCJ Collective 1,147,
  Bessemer Venture Partners **7,318**. A real adapter's pagination/crawl-budget
  assumptions can't be sized off Greentown Labs alone.
- **Pagination via `meta.sequence` works correctly at the job level.** Confirmed zero
  duplicate `jobId`s across 3 pages of 50 against Greentown Labs. (An earlier draft of
  the probe script flagged company-slug *reappearance* across pages as "overlap" — that
  was the script's own instrumentation conflating "same job twice" with "same company,
  different job," not a real platform bug. A company with several open roles correctly
  has them spread across the ranked result set. Fixed before committing the script —
  worth remembering as a lesson about testing pagination the same way `SPEC.md` already
  warns about "a 200 is not evidence of a real endpoint": a duplicate-looking metric is
  not automatically a duplicate-data bug either.)
- **Full field inventory** (see the spike script's docstring) confirms
  `spikes/iteration2_consider_spike.py`'s derived-fields-to-ignore list is still current
  (`scores`, `skills`, `requiredSkills`, `preferredSkills`, `considerLevels`,
  `matchingTalent`), and surfaces two more worth naming explicitly: `salary` (real
  min/max/currency comp data — out of scope regardless, Consider is company-source only,
  same rule as everything else in SPEC.md §7) and `atsJobs` (empty on every one of the
  ~30 job records sampled today — unconfirmed whether it's ever populated).

## What a real adapter would need, versus Getro (`src/getro.py`, M6)

| | Getro | Consider |
|---|---|---|
| Requests per board | 1 (GET) | 2+ (GET for session/CSRF, then POST per page) |
| Session handling | None | Needed, but free: `src/http.py`'s `FetchClient` wraps a single `httpx.Client` per instance, which already persists cookies across calls — `client.get()` then `client.post_json()` on the same client needs no `src/http.py` change |
| Pagination | None (one response has everything) | Required for full coverage — confirmed-working `meta.sequence` cursor |
| Domain resolution | Unsolved gap (SPEC.md §7.2) — lands `canonical_domain=None` | **Solved for free** — `companyDomain` present on every sampled record |
| Board list curation | Same problem either way — a fingerprint heuristic over-suggests candidates (SOSV here, `jobs.a16z.com` for Getro); each board needs live confirmation before being trusted |

**Net assessment:** more request-flow complexity (stateful session + pagination loop)
than Getro, but the domain-resolution win is real and immediate — this doesn't
contradict SPEC.md §7.6's framing of Consider as the stronger company-discovery source
of the two. If this is ever prioritized: a `src/consider.py` shaped like `src/getro.py`
(parse → extract distinct companies → `ingest_manual_company(source='consider')`), plus
a paginate-until-`total` loop, plus its own `config/consider_boards.yml` built the same
way `config/getro_boards.yml` was — confirm each candidate live, don't trust the
fingerprint column alone.

## Not addressed here

- **Rate/politeness budget for a large board.** Bessemer's 7,318 jobs at `size=50` is
  ~150 requests to fully paginate. Whether that's acceptable under SPEC.md §9's 2-5
  req/sec-per-host budget wasn't stress-tested — just noted as a real cost a production
  crawl would need to account for, unlike Getro's single request per board.
- **Whether `atsJobs` is ever populated on any board.** If it is, on some board not
  sampled here, it would be an even better resolution path than `companyDomain` (a
  mapped ATS token handed to us directly). Empty on every record seen today — not
  enough evidence either way.
- **No `config/consider_boards.yml` was built.** This is a spike, not a milestone.
