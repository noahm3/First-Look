# ATS integration backlog — candidates beyond Greenhouse/Lever/Ashby

Not spike work in progress — a reference doc for a **later phase**, per the user's
explicit framing. Nothing here is built. Counts are the `unsupported_ats:*` distribution
from `discovered_companies.csv`, re-derivable any time via `unsupported_ats_tally.py`
(run it rather than trusting the numbers below once more companies have been discovered
or checked). Feasibility notes are hand-maintained from live spot-checks and don't
auto-update.

**Do not build any of these without re-reading `SPEC.md` §4 first** — three of the entries
below already have SPEC-level rejection or deferral reasoning that any implementation work
needs to engage with, not re-litigate from scratch.

## Top candidates, ranked by (measured volume × confirmed API cleanliness)

### BambooHR — 57 companies
- **Confirmed live, clean, public, unauthenticated:** `GET https://{company}.bamboohr.com/careers/list`
  → JSON: `{"meta": {"totalCount": N}, "result": [{"id", "jobOpeningName", "departmentId",
  "departmentLabel", "employmentStatusLabel", "location": {"city", "state"}, "isRemote", ...}]}`.
- Not in SPEC.md at all yet. Highest count of any unsupported provider, cleanest data of
  the three not already SPEC-addressed.
- No name/org-identity field spotted in this response shape yet — would need the same
  live-corroboration discipline `93feb78`'s fix now requires for careers-page-derived
  Greenhouse/Lever/Ashby tokens.

### Workable — 55 companies
- **Confirmed live:** `GET https://apply.workable.com/api/v1/widget/accounts/{company}`
  → JSON `{"name": "...", "description": "..."}` at minimum (job list fields not yet
  inspected). **Includes the company name for free** — the same kind of validation signal
  Greenhouse's `/v1/boards/{token}` gives, which Lever and Ashby lack.
- **`SPEC.md` §4 already rejects Workable** ("SMB / agency skew... near-zero expected
  yield"), but the same row explicitly says: "Revisit only against a measured
  `unsupported_ats:{name}` distribution, never on principle." **This count is that
  measurement.** Whoever revisits §4 should read that row's exact wording before deciding,
  not skip straight to building.

### Personio — 42 companies
- **Weaker than the count suggests.** SPEC.md §4 documents it as XML-only. Live-checked two
  companies 2026-09-22: one (`nexwafe`) returned HTTP 200 but a client-rendered Next.js
  HTML shell at the documented `/xml` path, not XML; the other (`archlet`) 404'd outright.
  Looks like Personio may have migrated its public career-site tech since SPEC's XML
  characterization was written — **re-verify on a fresh sample before trusting either the
  old "XML-only" framing or this backlog entry**, don't build against either blind.
- Also SPEC §4-rejected, same "revisit against measurement" clause as Workable.

### Breezy HR — 34 companies
- **Confirmed live, clean, public, unauthenticated, rich:**
  `GET https://{company}.breezy.hr/json` → JSON array of
  `{"id", "friendly_id", "name", "url", "published_date", "type": {"name"},
  "location": {"country", "is_remote", "name"}, "department", "salary",
  "company": {"name", "friendly_id"}}`.
- **Structured `location.is_remote` and a `salary` field** — comparable richness to Ashby.
  Not in SPEC.md yet. Second-cleanest confirmed shape after BambooHR/Workable.

### Workday — 30 companies
- **Confirmed live 2026-09-22:** the CxS API works as SPEC.md §4 describes structurally —
  `POST https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` with body
  `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}` → JSON
  `{"total", "jobPostings": [{"title", "externalPath", "locationsText", "postedOn",
  "bulletFields"}]}`. Worked cleanly on `rmi.org`'s tenant (`rockymountain`), no bot
  challenge encountered.
- **`postedOn` is a relative string** ("Posted Yesterday"), confirming SPEC §4's "needs a
  second request per job for a date" concern.
- **SPEC.md §4 already calls this "Backlog only"** — hard 20-item pagination cap, Akamai
  bot management at scale, aimed at enterprises. One clean test on one tenant doesn't
  contradict that; SPEC's concern was about polling reliability at volume, not whether the
  endpoint shape exists. Treat this count as informational, not a case to reopen §4's
  verdict without new evidence at scale.

## Smaller / lower-priority candidates

| Provider | Count | Notes |
|---|---|---|
| ApplyToJob (JazzHR) | 22 | Not live-verified yet. |
| WordPress + WP Job Manager | 20 | Not one platform — self-hosted per site; only the RSS feed shape is standard. Lower leverage per engineering hour than a single centralized API despite the count. |
| Polymer | 12 | Boutique platform, unresearched. |
| Recruitee | 11 | **Confirmed live, clean:** `GET https://{company}.recruitee.com/api/offers/` → JSON `{"offers": [{"title", "position", "salary": {"min","max","period","currency"}, "requirements" (HTML), ...}]}`. Structured salary is a real asset. SPEC §4-rejected ("SMB/agency skew"), same revisit-on-measurement clause as Workable/Personio. Smallest count of the three SPEC-rejected candidates but cleanest data. |
| Phenom People | 7 | Enterprise CMS layered on top of another ATS (found wrapping Workday for `nature.org`'s `careers.tnc.org`). Not a real standalone integration target — skip. |
| SmartRecruiters | 3 | Already tracked in SPEC.md §17 as "deferred pending measurement" — this is that measurement. Too low on this data to justify the adapter per §17's own stated criterion. |
| careers-page.com | 3 | India-focused. User already called this out as fine to deprioritize. |
| PyjamaHR | 1 | India-focused HR tool, negligible count. |

## Not adapter candidates regardless of count

- **LinkedIn Jobs** — `linkedin.com/company/{x}/jobs` found as a company's *only* listed
  careers link (`xplorobot.com`). **SPEC.md §4: "Non-negotiable permanently... this stays
  client-side forever."** Detection stays measurement-only (`unsupported_ats:linkedin-jobs`
  in `iteration6_ats_mapping_spike.py`); do not build against it under any circumstance.
- **Rippling** — found once (`getdelos.com` → `ats.rippling.com`). Not yet measured at
  scale; detection added to `iteration6_ats_mapping_spike.py` after the full run, so its
  real count needs a re-scan of the `no_careers_page`/`unknown` buckets specifically.

## Combined case for revisiting SPEC.md §4

BambooHR + Workable + Personio + Recruitee = **165 companies** (as of the last full tally —
regenerate before citing this number again), against 554 currently mapped via
Greenhouse/Lever/Ashby. Personio's live feasibility looks weaker than its count suggests;
BambooHR/Workable/Breezy/Recruitee all have confirmed clean public JSON matching the same
bar SPEC already applies to the supported three. This is the measurement SPEC.md §4 itself
asks for before revisiting Workable/Personio/Recruitee's rejections — presenting it here as
input to that discussion, not as a decision made on this document's authority.
