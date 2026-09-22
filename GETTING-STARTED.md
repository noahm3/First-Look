# GETTING-STARTED.md

**Read this first, Claude.** This document walks the user through setting up the First
Look project from a folder of design documents to a working repository ready for the M0
milestone. It implements `BUILD.md` §1 (milestone M-1).

**2026-09-17 update:** the document-normalization work this file originally did in
Phase 5 (merging `SPEC-REVISION-01.md`, `SPEC-REVISION-02.md`,
`first-look-security-patch.md`, and `first-look-sources-patch.md` into `SPEC.md`,
`BUILD.md`, `CRITERIA.md`, and `SECURITY.md`) has already happened, in a session before
any git history existed. The originals are preserved verbatim in `archive/`. Phase 0 and
Phase 5 below have been trimmed to match — don't go looking for those patch files, they
won't be at the top level.

## How to use this document

Work through the phases **in order**, one at a time. After each phase, run its
verification step and report the result before moving on.

Three kinds of step appear:

- 🤖 **You run it.** Execute the command and show the user the output.
- 🛑 **User must do it.** Stop completely, tell them exactly what to do, and wait for
  them to confirm before continuing. These are browser tasks and interactive logins you
  cannot perform.
- ⚠️ **Decision point.** Ask the user, wait for an answer, do not assume a default.

Do not batch phases together. Do not skip verification. If a verification fails, stop
and fix it before continuing — a bad setup is much cheaper to fix now than after thirty
commits.

**The user is on Windows.** Prefer Git Bash over PowerShell for anything shell-shaped.
If they're on macOS or Linux, the commands are the same except for tool installation.

**Do not write any application code in this session.** Setup only.

---

## Phase 0 — Orient

🤖 List the folder contents and confirm you can see these files:

```
SPEC.md
BUILD.md
CRITERIA.md
SECURITY.md
SETUP-PLATFORM.md
DEVLOG.md
archive/   (contains the pre-merge originals — SPEC.md, SPEC-REVISION-01.md,
            SPEC-REVISION-02.md, BUILD.md, CRITERIA.md, SECURITY.md,
            first-look-security-patch.md, first-look-sources-patch.md,
            GETTING-STARTED.md — all as first written, for history only)
```

Read `SPEC.md`, `BUILD.md`, `CRITERIA.md`, and `SECURITY.md` in full before doing
anything else. Do not read `archive/` unless you need historical context — it's there
for the human, not because it's still authoritative.

🤖 Check whether the GitHub-created files are also present (`README.md`, `.gitignore`,
`LICENSE`). They may not be yet — Phase 2 brings them down.

**Verify:** report which files you found. If any of the four current design documents is
missing, stop and tell the user.

---

## Phase 1 — Tools

🛑 **User installs these if not already present.** Ask them to confirm each.

**Git for Windows** — from git-scm.com. This also provides Git Bash, which is needed
because the pre-commit hook is a bash script.

**GitHub CLI** — in PowerShell:

```powershell
winget install --id GitHub.cli
```

Or the installer from cli.github.com. **They must close and reopen the terminal
afterward** so `gh` lands on the PATH.

🤖 Verify both:

```bash
git --version
gh --version
```

**Verify:** both commands return a version. If `gh` isn't found, the terminal wasn't
restarted.

---

## Phase 2 — Identity and remote

This phase matters more than it looks. Two separate things determine where work lands,
and getting either wrong is silent.

### 2.1 — Which GitHub account

⚠️ **The user has both a work and a personal GitHub account.** This project belongs to
the **personal** one.

🛑 Ask the user to run this themselves and complete the browser flow:

```bash
gh auth login
```

**Before they do:** tell them to check that their browser's active GitHub session is the
personal account, not work. A private/incognito window is the safest way.

🤖 Then verify:

```bash
gh auth status
```

**Verify:** the reported username is the personal account. If `gh` reports multiple
accounts, use `gh auth switch` to select the personal one. Do not continue until this is
correct.

### 2.2 — Commit identity

**This is the step most likely to go wrong silently.** GitHub login and commit identity
are independent. If global git config holds a work email, every commit is attributed to
the work account's profile and contribution graph — even in a personal repo.

🤖 Check what's currently set:

```bash
git config --global user.email
git config --global user.name
```

⚠️ **Ask the user which email to use for this project.** Two options:

- Their personal email, as registered on the personal GitHub account.
- GitHub's noreply address, found at personal account → Settings → Emails → "Keep my
  email addresses private." It looks like `12345678+username@users.noreply.github.com`.

**Recommend the noreply address.** The user has said they want a low profile on this
project, and it keeps a real address out of a public repository's commit history
permanently.

🤖 Set it **per-repository**, which overrides global config for this folder only:

```bash
git init
git branch -M main
git config user.email "<their choice>"
git config user.name "<their name>"
```

🤖 Verify the local setting took:

```bash
git config user.email
```

**Verify:** returns the personal/noreply address, not the global one.

### 2.3 — Connect the remote

⚠️ Ask the user for the **full URL of the GitHub repository they created**. It looks like
`https://github.com/username/reponame.git`.

🤖 Add it and confirm:

```bash
git remote add origin <URL>
git remote -v
```

**Verify:** both lines show the personal account's repository. If wrong, fix with
`git remote set-url origin <correct URL>`.

### 2.4 — Pull GitHub's files

The repository was created with a README, .gitignore, and license, so it has commits the
local folder doesn't.

🤖

```bash
git pull origin main
```

If this fails with unrelated-histories, use `git pull origin main --allow-unrelated-histories`.

**Verify:** `README.md`, `.gitignore`, and `LICENSE` now exist locally alongside the
project documents and the `archive/` folder.

---

## Phase 3 — .gitignore

🤖 Open `.gitignore` and make two changes.

**First, append the project-specific entries** (from `BUILD.md` §1.3):

```
.cache/
Connections.csv
connections*.json
config/notify/
*.local.yml
```

The `Connections.csv` entry exists ten milestones before the feature that uses it,
because that file in the working directory is the most likely accidental commit in this
project — and the window opens the moment you're curious enough to download the export.

**Second — check for any line matching `*.db`, `*.sqlite`, or `*.sqlite3`.** GitHub's
Python template usually includes them. **Unlike the original design, this project does
*not* commit a SQLite database as state** — `SPEC.md` §6 moved storage to Postgres
(Supabase) before any code was written, specifically to avoid the repo-bloat problem a
committed binary database would cause. So: if GitHub's template already ignores `*.db` /
`*.sqlite*`, **leave those lines in** — they're correct now, where they would have been
wrong under the original design. Do not remove them.

🤖 Show the user the final `.gitignore`.

---

## Phase 4 — First commit

🤖

```bash
git add -A
git commit -m "Initial design documents"
git push -u origin main
```

🛑 **Windows credential trap.** If the push fails with a permissions error, Git Credential
Manager has the work account cached. Tell the user to open **Windows Credential Manager →
Windows Credentials**, find and remove any `git:https://github.com` entry, then retry —
it will re-prompt for the correct account.

🛑 **Attribution check — do not skip this.** Ask the user to open the repository on
github.com, click the commit, and confirm it shows their **personal** username and
avatar.

If it shows the work account, `user.email` was wrong. Fix it and future commits will be
correct; this early, one misattributed commit is not worth rewriting history over — but
catching it now rather than at commit thirty is the point.

**Verify:** user confirms correct attribution.

---

## Phase 5 — CLAUDE.md and the pre-commit hook

Document normalization already happened before Phase 0 of this session. What's left:

🤖 **Step 1.** Create `CLAUDE.md` from the template in `BUILD.md` §0.2, exactly as
written.

🤖 **Step 2.** Confirm `DEVLOG.md` exists with at least one entry (it should, from the
consolidation session — see its first entry for what was merged and what was flagged).
If it's missing for some reason, create it with just a title heading:

```markdown
# First Look — Development Log
```

🤖 **Step 3.** Create `.githooks/pre-commit` from `BUILD.md` §0.3. Include the
`#!/usr/bin/env bash` shebang — Git for Windows runs hooks through its bundled bash, so
the script works despite `chmod` being meaningless on Windows.

Do **not** run `git config core.hooksPath` — the user does that in Phase 6.

**Verify — report before committing:**

- `git diff` for `CLAUDE.md` and any other changed file.
- Confirmation that `CRITERIA.md`'s criterion numbering is unchanged from what's already
  in the working tree (it was already reconciled in the consolidation session, including
  two criteria struck in the M6 block — see `CRITERIA.md`'s consolidation note at the
  top and `DEVLOG.md`).

---

## Phase 6 — Enable the hook

🤖

```bash
git config core.hooksPath .githooks
```

🤖 Test that it actually blocks. Create a throwaway file containing a fake email address,
stage it, and attempt a commit. The hook should refuse.

```bash
echo "test@example.com" > hooktest.txt
git add hooktest.txt
git commit -m "should fail"
```

Then clean up:

```bash
git reset hooktest.txt
rm hooktest.txt
```

**Verify:** the commit was blocked with the hook's message. **If the commit succeeded,
the hook is not running** — check `core.hooksPath`, the file location, and the shebang.
This hook is one of two automated guards replacing manual PR review, so it has to work.

🤖 Commit the setup work:

```bash
git add -A
git commit -m "Setup: CLAUDE.md, pre-commit hook"
git push
```

---

## Phase 7 — Repository settings

🛑 **User does these in the browser.** List them, wait for confirmation of each.

**Settings → Code security:**
- Enable **secret scanning**
- Enable **push protection**

**Settings → Actions → General:**
- Workflow permissions → **Read and write permissions**
- Enable **"Require approval for all external contributors"**

**Settings → Pages:** leave alone for now — M0 configures it via `gh`.

🛑 **README caution.** If the user wants to fill in the README, it should stay neutral and
technical — something like *"Monitors public ATS job boards and publishes new postings to
a static dashboard."* Nothing identifying whose job search this is, per the low-profile
posture in `SPEC.md` §15. Leaving it near-empty is also fine.

**Verify:** user confirms all four toggles.

---

## Phase 8 — Accounts for M0

These are needed by the first real milestone. 🛑 **User creates each**, then reports back.
Do not ask for the secret values in chat — they go straight into GitHub via `gh secret
set`, which prompts privately.

**healthchecks.io** — free account. Create a check named `first-look-monitor`, period
matching the run schedule (start with 1 day, generous grace). Put the eventual dashboard
URL in the description so it appears in alert emails. **Confirm the alert address is one
they actually read on their phone.**

**Resend** — free account, verify a sender, create a **send-only** API key.

**Fine-grained PAT** — personal account → Settings → Developer settings → Fine-grained
tokens:
- Scoped to **this one repository** only
- Permission: **Contents: read/write** only. No `workflow` scope, no org access.
- ⚠️ **Expiry set past the end of parental leave.** A default 90-day token created now
  dies in November with nobody available to renew it. **Record the expiry date in
  DEVLOG.md.**

**Supabase project** — per `SETUP-PLATFORM.md` §4. `SPEC.md` §6 moved storage to Postgres
as a pre-leave build item, not a platform-era one, so this account is needed for M0, not
deferred. Decide on the Pro plan now per `SETUP-PLATFORM.md` §4.2 — free-tier projects
pause after low activity, which bites hardest during exactly the unattended window this
project is built for.

**A hosted form** (Tally, Google Forms, or Formspree) for alert requests — see `SPEC.md`
§13.2. This can wait until M10 if they'd rather move on.

---

## Phase 9 — Close out

🤖 Append a `DEVLOG.md` entry using the template in `BUILD.md` §0.4. Record:

- Setup completed, date
- Which email identity was chosen for commits
- The PAT expiry date
- Which accounts were created, including the Supabase project
- Any *new* contradiction, ambiguity, or gap you noticed while reading `SPEC.md`,
  `BUILD.md`, `CRITERIA.md`, and `SECURITY.md` in this session — the consolidation
  session already surfaced and resolved one (Y Combinator's status, see `SPEC.md` §4 and
  §7.8) and struck two stale Getro criteria, both logged in `DEVLOG.md`'s first entry.
  This step is about anything *new*, not re-litigating that one.

🤖 **Report that list to the user directly as well. Do not fix any of them** unless
they're trivial and you say so explicitly — the decisions are the user's.

🤖 Update the "Current milestone" line in `CLAUDE.md` to `M0`.

🤖 Commit and push.

🤖 Finally, tell the user:

- That setup is complete and what the next milestone is
- That `BUILD.md` recommends **Opus 5 with plan mode** for M0
- That they should start a **fresh Claude Code session** for it, switching model with
  `/model` before beginning

Then stop.

---

## What must not happen in this session

- No application code, no `src/` files, no workflows — those are M0.
- No deleting or rewording anything in `CRITERIA.md` beyond what's already reconciled.
- No committing before the hook is verified working.
- No proceeding past a failed verification step.
