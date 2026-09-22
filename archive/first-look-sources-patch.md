# Sources patch — Greentown Labs and Y Combinator

Insertions to `SPEC.md`, `BUILD.md`, and `CRITERIA.md`. Apply alongside the security
patch in the setup session. Every item is an insertion or an append — **nothing is
deleted or reworded.**

---

## 1. SPEC.md

### 1.1 — §6, extend the `company_sources.source` comment

Change:

```
  source                TEXT NOT NULL,   -- builtinboston|climatebase|getro|manual
```

to:

```
  source                TEXT NOT NULL,   -- builtinboston|climatebase|getro|greentown|manual
```

*(This is the one edit in this patch that modifies an existing line rather than adding
one. It extends an enum comment; no meaning is removed.)*

### 1.2 — §7, append a new subsection after §7.5

```markdown
### 7.6 Greentown Labs member directory

`greentownlabs.com/members/?hq=all&cat={category}&status=current` — roughly 307 member
companies, WordPress, server-rendered, plain GET. One-time crawl.

Categories, each crawled separately: `agtech-water`, `buildings`, `electricity`,
`manufacturing`, `resiliency-adaptation`, `transportation`.

**Discovery only.** Sets `is_climate = 1` — incubator membership is a lookup, not a
judgment, on the same basis as ClimateBase directory membership — and supplies the
category as `industry_tags`. These categories are cleaner and more specific than Built
In's generic industry tags.

Also capture `status` (current vs. alumni). Current members are more likely to be
actively hiring, which feeds `has_open_roles_signal` as a weak positive.

**Density and overlap.** Heavy Somerville/Boston and Houston concentration, which maps
directly onto the climate-remote and climate-Boston cases. Expect meaningful overlap
with ClimateBase and Built In Boston; `canonical_domain` dedupe handles it, and
multi-source appearance is a mild positive signal per §7.

**Not used: the Greentown jobs board.** `jobs.greentownlabs.com` runs on Consider, a
client-rendered aggregator — see §4.

### 7.7 Y Combinator — not used

Evaluated and excluded in all three of its forms:

- **`workatastartup.com/jobs`** — client-rendered, and full listings appear to be gated
  behind a YC account. Rejected on the same grounds as Wellfound (§7.5). Observed
  listings also skew almost entirely to engineering roles at San Francisco seed-stage
  companies.
- **The full YC company directory** (~5,000 companies) — would multiply mapping workload
  and dashboard payload for a population that is mostly seed to Series A, San
  Francisco-concentrated, and rarely hiring product roles at this compensation level.
  Rejected on yield, not difficulty.
- **YC's public directory filtered to climate** — plausibly worth 100–200 companies and
  publicly accessible, but expected to overlap heavily with ClimateBase and the climate
  VC portfolios already crawled. **Backlog, contingent on measurement** — see §17.11.
```

### 1.3 — §4, append two rows to the rejected table

```markdown
| Consider-powered job boards (`jobs.greentownlabs.com`) as a monitoring source | Client-rendered SPA requiring endpoint reverse-engineering, yielding thinner data than polling the same companies' ATSes directly. Same reasoning that cut the ClimateBase jobs SPA. Greentown is used for discovery via its member directory instead (§7.6). |
| `workatastartup.com` (Y Combinator) | Client-rendered and apparently account-gated, like Wellfound. Observed listings skew almost entirely to engineering roles at SF seed-stage companies. See §7.7. |
```

### 1.4 — §7, append after the intro paragraph

```markdown
**Source selection is not user filtering.** Choosing which companies to discover — Built
In's 11–1000 employee band, Greentown's current members, the exclusion of the full YC
directory — is a sourcing decision about where to spend crawl and mapping budget. It is
distinct from principle §3.1, which forbids *user criteria* (compensation, role,
location, seniority) from appearing in pipeline code. Those still live exclusively in
the dashboard and notification profiles.
```

### 1.5 — §17, append

```markdown
11. **Greentown overlap rate** — what fraction of Greentown members are already captured
    by ClimateBase, Getro, or Built In. Measured after the M8 crawl. If overlap is near
    total, note it; if Greentown surfaces a meaningful number of companies no other
    source has, that is evidence for adding similar incubator directories (Elemental,
    Third Derivative, New Energy Nexus) as a cheap backlog item.
12. **Whether a filtered YC climate slice would add anything** — answerable only once
    §17.11 shows how much the existing climate sources already cover. Do not build it
    speculatively.
```

---

## 2. BUILD.md

### 2.1 — M8 milestone, append

```markdown
**Three crawls in this milestone**, in ascending order of risk:

1. **Greentown member directory** (~307 companies, 6 category URLs). Smallest and
   safest — do it first as a warm-up that validates the crawler shape before the larger
   jobs.
2. **ClimateBase organization directory** (~7,250 orgs).
3. **Built In Boston** (~852 filtered companies) — largest and highest anti-bot
   exposure, smoke-tested with 20–50 requests first.

After all three, report the **overlap matrix**: how many companies each source
contributed uniquely versus in common with the others. This answers SPEC §17.11 and
tells you whether more incubator directories are worth adding.
```

### 2.2 — M8 estimate

Change the M8 estimate line from `**Est:** 3–4h` to `**Est:** 4–5h`. Three crawls
rather than two.

### 2.3 — §6 Things that will go wrong, append

```markdown
- **Greentown's member pages are paginated** (`/members/page/N/?...`). The category
  filter and pagination combine in the URL; confirm the last page rather than assuming
  a single response contains everything.
- **Greentown alumni companies are still listed.** Capture `status` and keep alumni —
  a company leaving the incubator says nothing about whether it's hiring — but don't
  treat alumni as a `has_open_roles_signal`.
```

---

## 3. CRITERIA.md

Append to the M8 block:

```markdown
- [ ] **C-8.5** The Greentown crawl returns roughly 300 companies across all six
      categories, each with `is_climate = 1` and a category in `industry_tags`
- [ ] **C-8.6** Greentown pagination is handled — the crawl does not stop at page 1
- [ ] **C-8.7** A company appearing in both Greentown and ClimateBase produces one
      `companies` row with two `company_sources` rows
- [ ] **C-8.8** The overlap matrix across all four discovery sources is recorded in
      DEVLOG
```

---

## 4. GETTING-STARTED.md

In Phase 5, Step 3, after applying the security patch, add:

```markdown
🤖 **Step 3b.** Apply `first-look-sources-patch.md` in full — all sections — to
`SPEC.md`, `BUILD.md`, and `CRITERIA.md`. Note that §1.1 modifies one existing comment
line to extend an enum; every other item is an insertion or append.

🤖 Delete `first-look-sources-patch.md` once applied.
```
