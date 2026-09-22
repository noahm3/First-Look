# SPEC Revision 01 — Aggregators become company sources

**Status:** proposed, pending measurement gate (§R9)
**Applies to:** `SPEC.md` as written
**Convention:** follows `CRITERIA.md` — nothing is silently deleted. Every removal
below names what is removed and why. Apply in order; later items assume earlier ones.

---

## R0. The one change

Every aggregator in scope becomes a **company source only**. Nothing but a mapped
company's own ATS endpoint appears on the polling loop.

This is one decision with a lot of downstream consequences. It is not a scope
expansion — applied fully it makes `SPEC.md` *smaller*.

**What it buys:**
- No fragile component on the recurring path. §3.4 holds absolutely rather than
  approximately.
- No republishing of another aggregator's listings. The data published is what the
  employer's own ATS publishes, which is what the ATS publishes it for.
- A simpler posting lifecycle (§10) with one source path instead of two.

**What it costs — name this explicitly, it is a real loss:**
- The Getro independent path in §7.2 was a hedge covering companies whose ATS mapping
  failed. That hedge is gone. **An unmapped company is now invisible, full stop.**
- Therefore mapping coverage stops being an open question and becomes the top-line
  product metric. See §R6 and §R9.

---

## R1. §3 Design principles — APPEND

Append as §3.10:

> **10. Only mapped ATS endpoints are polled.** Discovery sources are read on the cold
> path (one-time or monthly) and never on the recurring path, regardless of how
> convenient their postings data looks. An aggregator's postings are someone else's
> product; a company's ATS board is the company's own publication. This is the line
> that keeps the system both unattended-safe and defensible.

No existing principle is removed. §3.4 is unchanged but is now enforced absolutely
rather than as a preference.

---

## R2. §4 Rejected alternatives — one STRIKE, several APPENDS

### STRIKE (with reason)

Strike this row, do not delete it:

> ~~| Wellfound automation | No public API; value behind a login wall; a warmed session
> is unacceptable maintenance. |~~
> **Struck 2026-09: factually wrong.** `wellfound.com/role/{role}`,
> `/role/r/{role}` (remote) and `/role/l/{role}/{city}` are public, server-rendered,
> `?page=N` paginated, no cookie, and carry salary range, equity range, remote policy,
> company size, stage and stable numeric job URLs. What is behind the login is
> *arbitrary filtering and applying*, not the listings. The rejection generalised a
> property of the filter UI to the whole source. Replaced by §7.8.

### APPEND new rows

| Rejected | Why |
|---|---|
| Any aggregator's postings on the polling loop | §3.10. Puts a fragile, undocumented, unilaterally-changeable parser on the recurring path, where a silent break is indistinguishable from a quiet week for two months. |
| Republishing aggregator-sourced postings in the dashboard, RSS or email | Not our data. The ATS-sourced version of the same posting is available and is the employer's own publication. |
| Wellfound, YC, Built In, ClimateTechList or Consider as *posting* sources | Same as above. All five are accepted as **company** sources (§7.6–§7.9). |
| Moving the LinkedIn connections feature (§12.6) server-side once a database exists | The export contains hundreds of other people's employment data. This stays client-side permanently, including in any future platform version. Non-negotiable. |

### STRENGTHEN (no change to the decision)

The `jobs.climatebase.org` GraphQL rejection stands and its reasoning is now stronger,
not weaker. Additional evidence: ClimateBase job detail pages carry
`meta-robots: noindex`, a deliberate do-not-aggregate signal. The org directory
(§7.3) remains in scope and is unaffected.

The Workday / Workable / Recruitee / Personio rejections stand, **but their stakes have
changed** — see §R6. Revisit only against measured `unsupported_ats:{name}`
distribution, never on principle.

---

## R3. §5 Architecture — REPLACE the diagram

Remove the existing diagram. Replace with:

```
DISCOVERY          one-time before leave; monthly after
  Manual watchlist · ClimateTechList · ClimateBase orgs · Built In
  Getro VC boards · Consider boards · Wellfound · YC
        │  dedupe on canonical_domain
        ▼
ATS MAPPING        one-time per company; retried monthly on failure
  slug guess → apply-redirect → careers-page regex → classified failure
        ▼
MONITORING         ~4x daily, GitHub Actions — ATS ONLY
  Greenhouse · Lever · Ashby  [· SmartRecruiters, pending §17.4]
        ▼
OUTPUT
  Dashboard + health page (Pages) · RSS · email alerts
```

**Removed from the diagram:** the `Getro boards (independent path — needs no mapping)`
line under MONITORING.

The two-workflow split (`monitor.yml` / `discover.yml`) is unchanged and matters more
now, since discovery has grown from four sources to eight.

---

## R4. §6 Data model — one REMOVE, one APPEND

### REMOVE

```sql
source_path  TEXT NOT NULL,   -- 'ats' | 'getro'
```

Remove the column from `postings`. Every row is now ATS-sourced; a column with one
possible value is noise that invites someone to add a second value later.

### APPEND

Extend the `company_sources.source` comment to enumerate the new sources:

```sql
source  TEXT NOT NULL,
-- builtin | climatebase | climatetechlist | getro | consider
-- | wellfound | yc | manual
```

`companies.is_climate` is unchanged in shape but now has **two independent sources**
(ClimateBase orgs + ClimateTechList). Two sources agreeing is a stronger flag than one;
appearing in only one is still a flag. This remains a lookup, not a classifier — §3.6
holds.

### DO NOT ADD

No table for observed compensation history (§R7). It is derivable from `postings` and
`posting_comp_tiers` by company. §3.5: store raw, derive on read.

---

## R5. §7 Discovery sources — one REMOVE, one STRIKE, four APPENDS

### §7.2 Getro — REMOVE the dual role

Remove the entire **Two roles** subsection and its three bullets. Getro is a company
source. Its board pages still yield company names and domains via `__NEXT_DATA__`;
nothing else about §7.2 changes.

### §7.5 Wellfound — STRIKE the section

> ~~### 7.5 Wellfound — not automated~~
> **Struck 2026-09.** See §R2 and §7.8.

### §7.4 Built In — APPEND a deferral

Append to §7.4:

> **National (`builtin.com`, ~100k companies) is deferred behind the §R9 measurement
> gate.** The crawl is tractable; the mapping cascade at that volume is not yet known to
> be. If cascade coverage is low, the correct response is better mapping, not a bigger
> crawl. Boston first. Re-evaluate with a real coverage number in hand.

### APPEND §7.6 — ClimateTechList

> `climatetechlist.com`. ~400+ climate companies, aggregating 8,000+ postings daily from
> individual company job boards. **Primary climate company seed.**
>
> Its company list is already filtered to *climate companies that run a pollable board* —
> the exact population this system wants, curated by someone maintaining it full-time.
> Crawlable company directory indexes into per-company profile pages; take name, domain
> and sector, nothing else.
>
> **Ask first.** They explicitly invite data partnership enquiries. A company-list
> request costs one email and removes the entire question of whether this is acceptable
> use. Do this before crawling, not after.
>
> Note honestly: this is also the closest thing to a competitor. Both facts are true and
> neither should be hidden from them.

### APPEND §7.7 — Consider

> `consider.com` — a board platform, not a single board. Confirmed in use at
> `jobs.greentownlabs.com` (307 companies, 578 jobs). Job rows are not in the server
> HTML; there is a client-side fetch behind the page which needs identifying once.
>
> One parser unlocks many accelerator and VC boards, same leverage pattern as Getro.
> Greentown Labs is the first board to add. **Company source only.**

### APPEND §7.8 — Wellfound (company source)

> `wellfound.com/role/{role}`, `/role/r/{role}`, `/role/l/{role}/{city}`. Public,
> server-rendered, `?page=N`. Next.js — check for `__NEXT_DATA__` before parsing HTML.
>
> **Take company name and Wellfound slug only.** Listings carry salary and equity; do
> not store or display them. Under §R0 that data comes from the company's own ATS, and
> taking it here is exactly the republishing §R2 rejects.
>
> Known gap: listings expose a Wellfound company slug, not a domain. `canonical_domain`
> dedupe requires a second hop to `wellfound.com/company/{slug}`. Budget one extra
> request per new company; this is cold-path work, so cost is acceptable.

### APPEND §7.9 — Y Combinator

> `workatastartup.com/jobs` returns listing data to an anonymous fetch — verified. React-
> rendered, so expect an embedded JSON blob rather than parseable markup. The YC company
> directory is separately Algolia-backed.
>
> Company source only. Lowest urgency of the four — YC skews early-stage and
> engineering-heavy relative to the target profile.

---

## R6. §8 ATS mapping — APPEND, raise stakes

No mechanical change to the cascade. Append to §8:

> **Mapping coverage is now the product.** Under the previous design a failed mapping
> was partially covered by the Getro independent path. That path is gone (§R0). An
> unmapped company is invisible.
>
> Consequences:
> - §17.1 (cascade coverage) and §17.2 (failure-reason distribution) are promoted from
>   open questions to **blocking measurements** (§R9).
> - `mapping_review.csv` review before unattended operation is no longer a backstop.
>   It is the only control on a silent population gap.
> - The adapter question changes character. `unsupported_ats:{name}` no longer reads
>   "should we build more adapters" but "what fraction of the climate population am I
>   structurally unable to see." SmartRecruiters in particular (§17.4) is now the most
>   likely adapter to be justified.

---

## R7. §11 Compensation — APPEND observed history

Append to §11:

> **Observed compensation history per company.** Transparency laws mean many companies
> disclose on *some* postings and not others — the CO/NY/MA req carries a band, the
> "Remote, US" one does not. A system polling the same companies daily for months
> accumulates real observed comp per company and per rough level.
>
> An undisclosed posting can therefore be annotated with what was actually collected:
> *"This company's last 4 Product roles: $195K – $265K."*
>
> Rules:
> - This is **collected data, not inference**. Display the observations and their count.
>   Never emit a single estimated number, a midpoint, or a predicted band for the
>   posting in hand — that is the §4 scoring rejection in a new costume.
> - Derived on read from `postings` + `posting_comp_tiers`. No stored estimate field.
> - Requires history, so it produces nothing useful for the first several weeks. Build
>   after the dashboard, not with it.
>
> This is the one capability no aggregator can copy without polling at the source over
> time. Treat it as the differentiator.

---

## R8. §12 Interface — APPEND to §12.5 cards

Append one line to the card spec:

> - Where comp is undisclosed and the company has ≥3 prior observed ranges in the same
>   job function, show the observed history beneath the muted "comp not disclosed" line,
>   labelled as history and never as an estimate for this role.

No filter changes. The comp filters in §12.2 continue to operate only on the posting's
own disclosed values — **observed history never satisfies a numeric filter.** A posting
matching on a neighbour's salary is wrong data, and §3.8 applies.

---

## R9. Measurement gate — NEW SECTION

Insert as a new §18. Nothing below the gate is built before the gate is passed.

**Run after M4, before any further source work.** Seed a few hundred companies through
the full cascade and measure four numbers from `--dump-facets` and the mapping table:

| # | Measurement | Decides |
|---|---|---|
| 1 | Cascade coverage: % reaching `verified` or `probable` | Whether company-first discovery works at all, and therefore whether Built In national (§7.4) is a 10x win or 90k unmappable rows |
| 2 | `mapping_failure_reason` distribution | Which adapter, if any, to build next |
| 3 | Comp disclosure rate on live postings | The ceiling on the whole time-saving claim. Not engineerable — if the employer published no number, no parser recovers it |
| 4 | `location_class = 'unknown'` share | Whether remote filtering is usable. Unlike #3 this *is* engineerable: the information is present in `location_raw` and the rules grow from real facet output |

**#3 is a fact about the world; #4 is a parsing problem.** Do not conflate them when
reading the results.

Gate outcomes:
- Coverage high, disclosure high → proceed to Built In national and the platform
  question.
- Coverage high, disclosure low → the product is novelty-and-alerting, not
  comp-filtering. Reprioritise §R7 hard; it becomes the main feature rather than a bonus.
- Coverage low → stop adding sources. Fix mapping. The seed list is not the constraint.

---

## R10. §17 Open questions — edits

- **#6 (Getro `__NEXT_DATA__` shape)** — REWORD: still required, but for company
  extraction only, not postings.
- **#8 (comp disclosure rate)** — PROMOTE to §R9 gate, measurement 3.
- **#10 (Wellfound native email alerts)** — REMOVE. Obsolete; Wellfound is a company
  source now and its alerting is irrelevant.
- **APPEND #11:** Consider's client-side fetch — what endpoint, what shape.
- **APPEND #12:** ClimateTechList partnership response — did they say yes.
- **APPEND #13:** Wellfound company-slug → domain resolution hit rate.

---

## R11. What does not change

Stated so a future session does not relitigate it:

- The static GitHub Pages / committed-SQLite / Actions architecture. Unchanged for this
  revision. The platform question is separate and deferred.
- §13.1 `NOTIFY_PROFILES` in a secret; §13.2 request-an-alert rather than self-serve.
- §14 reliability in full — dead-man's switch first, per-company failure classification,
  aggregate anomaly exit, counts-never-identities in logs.
- §15 public-repo posture, including no personal attribution.
- §12.6 LinkedIn connections, client-side, permanently.
- §16 keepalive.
- The accelerated build path: M-1→M4, M10, M8.

## R12. Sequencing

1. M-1 → M4 as specced. Seed from watchlist + ClimateTechList + ClimateBase orgs.
2. **§R9 measurement gate.**
3. M10, M8 — unattended monitor emailing new postings.
4. Consider parser (§7.7), Wellfound company source (§7.8) — cheap, cold-path.
5. Run live against real criteria for three months even if not actively applying. This
   is the only honest way to answer coverage, and the only way to learn whether the
   interesting product is this or something adjacent.
6. YC (§7.9), Built In national (§7.4), observed comp history (§R7) — gated on step 2.
7. Platform question — November, with data.

**Effort note:** the original 45–75 hour estimate assumed functioning evenings. Against
a newborn, plan for roughly a third of the available time and treat anything more as
upside. This revision does not add hours; applied fully it removes some.
