# Security cross-references — patch list

Exact insertions to add `SECURITY.md` references at the points where the relevant code
gets written. Apply in order. Nothing below deletes or rewords existing content — every
item is an insertion or an append.

**Sequencing note:** three of these controls must land *before* the code they govern, not
after. They are marked ⚠ and explained in §6.

---

## 1. CLAUDE.md

**Append to the `## Non-negotiables` block:**

```
- Read SECURITY.md before writing dashboard rendering code, workflow files,
  or anything that touches NOTIFY_PROFILES.
- Never use innerHTML, outerHTML, insertAdjacentHTML, or document.write with
  data from a posting, company, or URL parameter. Use textContent.
```

**Append to the `## THIS IS A PUBLIC REPOSITORY` block:**

```
GitHub masks exact secret values in logs. NOTIFY_PROFILES is a JSON blob we
parse, so an email extracted from it is a DIFFERENT string and will NOT be
masked. Never log a parsed profile, and never include a recipient in an
error message.
```

**Add to the file list in §0.1:**

```
SECURITY.md   # threat model and hardening requirements
```

---

## 2. SPEC.md

### 2.1 — after principle §3.9, append a tenth principle

```markdown
10. **Third-party strings are untrusted input.** Job titles, company names, location
    strings, and comp summaries are written by strangers and rendered into a public
    page. They are escaped, never interpolated as markup. See `SECURITY.md §S1`.
```

### 2.2 — in §12 Interface, immediately under the heading

```markdown
> **Before writing any rendering code, read `SECURITY.md §S1`.** Every field on a card
> originates from a third party, and the page shares an origin with uploaded LinkedIn
> data in `localStorage`. Rendering rules are a correctness requirement, not a
> hardening pass to apply later.
```

### 2.3 — in §12.5 Cards, append after the bullet list

```markdown
**Rendering rules (`SECURITY.md §S1`):** every field above is set with `textContent`,
never `innerHTML`. The title's `href` is rendered only when the URL scheme is `http:` or
`https:` — a `javascript:` URL in a posting executes on click. Outbound links carry
`rel="noopener noreferrer"`.
```

### 2.4 — in §12.6 LinkedIn connections, append to the numbered list

```markdown
5. The upload is validated as an object of string keys to integer values and rejected
   otherwise. It is untrusted input like any other (`SECURITY.md §S1`).

Because this data shares an origin with the dashboard, an XSS on that page is an
exfiltration path for it. That is why §S1's rendering rules are load-bearing here rather
than merely tidy.
```

### 2.5 — in §13.1, append after the bullet list

```markdown
**Log-masking caveat (`SECURITY.md §S3`).** GitHub masks exact secret values, but
`NOTIFY_PROFILES` is parsed — an extracted address is a different string and will not be
masked. Profiles are referred to by `name` everywhere outside the send call itself; a
parse failure raises a message containing no parsed content; the send error path never
includes the recipient.
```

### 2.6 — in §14, immediately after the "run summary must never print personal data"
paragraph

```markdown
This is enforced by test, not by discipline: the integration suite asserts the run
summary contains no `@` character (`SECURITY.md §S3`).
```

### 2.7 — in §15, append a new subsection

```markdown
### 15.1 Security posture

A public repository running Actions with secrets has a real attack surface even though
the application itself has almost none. `SECURITY.md` is the full audit; the three
structural requirements that constrain design rather than implementation:

- **Workflows carrying secrets never trigger on a pull request.** A separate
  secrets-free workflow runs tests on PRs. (`§S2`)
- **Every third-party Action is pinned to a full commit SHA.** A mutable tag can be
  repointed at code that reads secrets. (`§S2`)
- **`KEEPALIVE_PAT` is fine-grained, single-repo, contents-only, and expires after leave
  ends.** It carries write access to a repo that executes workflows, which makes it the
  highest-value secret in the project. (`§S4`)
```

### 2.8 — in §5 Architecture, append under the two-workflows paragraph

```markdown
A third workflow, `test.yml`, runs lint and tests on pull requests **with no secrets in
scope**. The split is a security boundary, not an organisational one (`SECURITY.md §S2`).
```

---

## 3. BUILD.md

### 3.1 — §1.2 Accounts, append items

```markdown
7. **Enable secret scanning and push protection** — Settings → Code security. Free on
   public repos, one toggle, and the only control that catches an accidental paste.
8. **Enable "Require approval for all external contributors"** — Settings → Actions →
   General.
```

### 3.2 — §1.2 item 4, replace the PAT line's parenthetical by appending

```markdown
   **Fine-grained, scoped to this one repository, `Contents: read/write` only, no
   `workflow` scope. Set the expiry past the end of leave and record the date in
   DEVLOG** — a default 90-day token created now dies in November with nobody around to
   renew it (`SECURITY.md §S4`).
```

### 3.3 — §1.3, append after the `gh` commands

```markdown
Create `test.yml` at the same time as the other two workflows. It runs lint and tests on
`pull_request` and **must not reference any secret**. `monitor.yml` and `discover.yml`
trigger only on `schedule` and `workflow_dispatch` — never `pull_request`, and under no
circumstances `pull_request_target` (`SECURITY.md §S2`).
```

### 3.4 — §2 Environment, append

```markdown
Install from a hash-pinned lockfile (`uv.lock`, or `pip-compile --generate-hashes`) with
`--require-hashes`. Dependencies execute with repo write access and secrets in scope, so
the minimal dependency list is a security control as much as a simplicity one
(`SECURITY.md §S5`).
```

### 3.5 — §3 Foundations, append to the `src/http.py` paragraph

```markdown
⚠ **Add the fetch guards now, in M0, not later** (`SECURITY.md §S6`): cap redirect depth
at 5–8, reject non-`http`/`https` schemes, reject resolved addresses in private,
loopback, and link-local ranges including `169.254.169.254`, and enforce a response size
cap. These are trivial to add before any crawler exists and awkward to retrofit once
several are depending on current behaviour.
```

### 3.6 — §3 Foundations, append to the `src/health.py` paragraph

```markdown
⚠ **Write the summary emitter to take counts only, never objects** (`SECURITY.md §S3`).
A summary function that accepts a profile and formats it is one refactor away from
printing an address into a world-readable log.
```

### 3.7 — M0 milestone, append

```markdown
**Security work in this milestone:** workflow trigger split, SHA-pinned Actions, explicit
`permissions` blocks, `src/http.py` fetch guards, and the counts-only run summary.
Criteria C-S.6 through C-S.9, C-S.13, C-S.14.
```

### 3.8 — M9 milestone, append

```markdown
⚠ **Read `SECURITY.md §S1` before writing the first line of rendering code, and add the
CSP meta tag at the start of this milestone rather than the end.** Retrofitting CSP onto
a working dashboard means debugging a blank page; writing against it from the outset
costs nothing. Criteria C-S.1 through C-S.5.
```

### 3.9 — M10 milestone, append

```markdown
**Security work:** profile parsing that never echoes parsed content, profile-name-only
references outside the send call, and the no-`@` assertion. Criteria C-S.10, C-S.11.
```

### 3.10 — M12 milestone, insert into the privacy audit list

```markdown
6. Work through every criterion in the Security block of CRITERIA.md. The M9–M11 checks
   were verified against the code as written then; this pass verifies them against what
   actually shipped.
```

### 3.11 — §5 Things that will go wrong, append

```markdown
- **CSP added late breaks the dashboard silently.** Inline handlers and inline `<script>`
  stop executing with no console error in some browsers. Add it first (§3.8).
- **A blanket "no `@` in stdout" grep is brittle** — a company name or a posting URL can
  legitimately contain one. Assert on the **run summary** specifically, which is
  deterministic; treat any wider grep as advisory only.
- **Private-IP blocking can reject legitimate fetches** if a CDN resolves oddly or a
  company site sits behind an unusual proxy. Log the rejection with the URL and the
  resolved address so it's diagnosable rather than a silent miss.
```

### 3.12 — §7 Session prompts, append

```markdown
**Before writing rendering or workflow code:**
> Read SECURITY.md §S1 and §S2 first. Tell me which of its requirements apply to what
> we're about to write, then start.
```

---

## 4. CRITERIA.md

Append the Security block from `SECURITY.md`, verbatim, at the end of the file. Per the
file's own rules it is appended, never interleaved, and existing numbering is untouched.

---

## 5. SECURITY.md — two refinements

### 5.1 — §S3, replace the automated-check bullet by appending

```markdown
Scope the assertion to the **run summary string**, which is deterministic and fully under
our control. A grep over all captured stdout will eventually false-positive on a company
name or a posting URL containing `@`; keep that as an advisory check rather than a
failing one.
```

### 5.2 — §S6, append

```markdown
Log every rejection with both the requested URL and the resolved address. A guard that
silently drops a legitimate fetch is indistinguishable from a company having no careers
page, and would land in the `mapping_failure_reason` bucket as `unknown` — corrupting the
§8.4 measurement that the whole coverage decision rests on.
```

---

## 6. The three that must land before the code they govern

Everything else can be verified after the fact. These three cannot:

**⚠ CSP and the rendering rules (M9, §3.8).** A dashboard written with `innerHTML` and
inline handlers works fine until CSP arrives, at which point it fails quietly — some
browsers block inline execution with nothing in the console. Writing against the
constraint from the first line costs nothing; retrofitting means rewriting the render
path and debugging a blank page.

**⚠ Fetch guards in `src/http.py` (M0, §3.5).** Once four crawlers and three adapters
depend on current redirect behaviour, tightening it means re-testing all seven. Twenty
lines on day one.

**⚠ The counts-only shape of the run summary (M0, §3.6).** This is an interface decision,
not a check. A summary function taking counts cannot leak an address; one taking objects
is always one refactor away from doing so. Fix the signature before anything calls it.

The rest — SHA pinning, PAT scope, secret scanning, lockfile hashes — are settings and
one-line changes that can be applied at any point without touching working code.
