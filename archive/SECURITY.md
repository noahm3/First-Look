# First Look — Security

The architecture is inherently low-risk: no backend, no server-side user input, no
authentication, no database service, no secrets in the browser. Most of the classic
web-application attack surface doesn't exist here.

What remains comes from three facts:

1. **The repository is public**, and it runs GitHub Actions with secrets.
2. **The dashboard renders third-party data** — job titles, company names, and comp
   strings written by strangers.
3. **Other people's personal data** (LinkedIn connections, a second user's email) is in
   scope, so a compromise isn't only the owner's problem.

Findings are ordered by expected cost, not by how exotic they are.

---

## S1 — Stored XSS in the dashboard (highest likelihood)

**Risk.** `title_raw`, `name`, `department_raw`, `location_raw`, `comp_raw_summary`, and
`industry_tags` all originate from third parties. Rendering any of them with `innerHTML`
produces stored XSS on a public page. Filter state also round-trips through URL query
params, so reflecting those into the DOM unescaped adds reflected XSS.

**Why it matters more than usual here.** Uploaded LinkedIn connection data lives in
`localStorage` on the same origin. An XSS is therefore an exfiltration path for hundreds
of other people's employment data — not just a defacement.

**Requirements.**

- **Never use `innerHTML`, `outerHTML`, `insertAdjacentHTML`, or `document.write` with
  any value derived from a posting, company, filter, or URL parameter.** Use
  `textContent` and `createElement`.
- The `url` field is rendered as an `href`. **Validate the scheme is `http:` or `https:`
  before rendering**, and drop the link otherwise. A `javascript:` URL in a posting
  executes on click.
- Add `rel="noopener noreferrer"` to outbound links.
- Serve a Content-Security-Policy meta tag as defence in depth:
  `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'`
  Inline event handlers and inline `<script>` must go for this to hold — which is a good
  constraint anyway.
- Treat the uploaded connections JSON as untrusted input: validate it is an object of
  string keys to integer values, reject anything else, and never eval or spread it into
  the DOM.

**Test.** Insert a fixture posting titled
`<img src=x onerror="document.title='XSS'">` with `url` of `javascript:alert(1)`, render
the dashboard, and confirm the title displays as literal text and the link is dropped.

---

## S2 — Secret exposure through GitHub Actions (highest severity)

The repo is public, so anyone can open a pull request. Workflow runs are where secrets
live, and a workflow that runs attacker-controlled code with secrets in scope is a full
compromise: `KEEPALIVE_PAT` has write access, which on a repo that auto-executes
workflows means arbitrary code execution with every other secret.

**Requirements.**

- **The monitoring workflow triggers only on `schedule` and `workflow_dispatch`.** Never
  `pull_request`, and under no circumstances `pull_request_target`, which runs in the
  context of the base repo with secrets available.
- **Two workflows, split by secret access.** A `test.yml` running lint and tests on PRs
  with **no secrets at all**, and `monitor.yml` / `discover.yml` carrying secrets but
  never triggered by a PR.
- **Pin every third-party Action to a full commit SHA**, not a tag. The spec already
  requires this for stability; the security reason is stronger — a mutable tag can be
  repointed at code that reads your secrets.
- **Confirm fork-PR workflow approval is enabled.** Settings → Actions → General →
  "Require approval for all external contributors."
- Set `permissions` explicitly at the top of every workflow, minimum necessary. Only the
  state-committing job needs `contents: write`.
- Never `echo`, `print`, or log an environment variable, and never run a debug step that
  dumps `env`.

---

## S3 — `NOTIFY_PROFILES` defeats GitHub's log masking

**Risk.** GitHub masks *exact* secret values in logs. `NOTIFY_PROFILES` is a JSON blob
that gets parsed, so an individual email address extracted from it is a different string
than the registered secret — **it will not be masked.** Any log line, stack trace, or
exception message containing a parsed profile leaks an address into a world-readable log.

Every privacy mitigation in the build depends on this not happening.

**Requirements.**

- Wrap profile parsing so a malformed value raises a message containing **no parsed
  content** — "failed to parse NOTIFY_PROFILES" and nothing else.
- Refer to profiles by `name` everywhere outside the send call itself. The address exists
  only as a local variable passed to the mail client.
- The send call's error path must not include the recipient in the logged message.
- **Automated check:** a test asserting the full run summary matches no `@` character, and
  a CI grep over captured stdout in the integration test.

---

## S4 — Credential scope and lifetime

**`KEEPALIVE_PAT` is the highest-value secret** — repo write on a repo that executes
workflows.

- Fine-grained PAT, **scoped to this single repository**, permission `Contents:
  read/write` only. No `workflow` scope, no org access, no other repos.
- **Set the expiry past the end of leave.** A default 90-day token created now expires
  mid-leave, silently breaking keepalive with nobody around to renew it. Record the
  expiry date somewhere you'll see it.

**`RESEND_API_KEY`** — sending permission only, no domain or account management. A leak
means someone sends mail as your sender.

**`HEALTHCHECK_URL`** — worth naming because it's counterintuitive: a leaked ping URL lets
someone *suppress* your dead-man's-switch alert by pinging it themselves. It's a
confidentiality issue for your alerting, not just a nuisance.

Rotate all four if any is ever printed, pasted, or committed — including into a chat
window.

---

## S5 — Supply chain

Dependencies execute inside a context with repo write access and secrets. This is the
quiet one.

- **Lockfile with hashes** (`uv.lock` or `pip-compile --generate-hashes`), installed with
  `--require-hashes`.
- Keep the dependency list minimal — the spec's stdlib-first stance is a security control
  as much as a simplicity one.
- If Dependabot is enabled, **review updates manually**; never auto-merge.
- No `curl | bash`, no installing from a Git URL or an unpinned branch.

---

## S6 — Fetching attacker-influenced URLs

The crawlers follow URLs supplied by third parties: Built In's "View Website" link,
apply-redirect chains, careers pages. A hostile or compromised source could point at
something unintended.

The runner has little internal network to reach, so real SSRF impact is low — but the
controls are nearly free:

- Cap redirect depth (5 is plenty) in `src/http.py`.
- Refuse non-`http`/`https` schemes.
- Refuse resolved addresses in private, loopback, and link-local ranges — notably
  `169.254.169.254`, the cloud metadata address.
- Enforce a response size cap so one hostile response can't exhaust the runner.
- Never write a fetched filename to disk from a remote-controlled value.

---

## S7 — Repository access

Anyone with write access can execute code with all secrets, because workflows run on push.

- No collaborators unless you'd hand them the PAT directly. Your friend consumes the
  dashboard and receives email — he needs no repo access at all.
- Enable branch protection on `main` if you add anyone, and require PR review.
- Enable secret scanning and push protection (free on public repos). This is the
  single highest-value free setting, and it catches the accidental-paste case.

---

## S8 — Accepted, not mitigated

Deliberate decisions rather than oversights:

- **The repository, dashboard, run logs, and all committed data are public.** ATS tokens
  are public by design; company and posting data is public information.
- **`config/watchlist.yml` reveals target companies.** Accepted (SPEC §15).
- **The dashboard is unauthenticated.** Anyone with the URL can view it. It contains no
  personal data by construction.
- **The alert-request form is a third-party service** holding submitted email addresses.
  Choose one whose privacy terms you're comfortable with, and don't collect more than an
  address and a filter string.

---

## Criteria to append to CRITERIA.md

```markdown
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
```

## Line to add to CLAUDE.md non-negotiables

```
- Read SECURITY.md before writing dashboard rendering code, workflow files,
  or anything that touches NOTIFY_PROFILES. Never use innerHTML with data
  from a posting, company, or URL parameter.
```
