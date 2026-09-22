# GETTING-STARTED.md

**Read this first, Claude.** This document walks the user through setting up the First
Look project from a folder of design documents to a working repository ready for the M0
milestone. It implements `BUILD.md` §1 (milestone M-1) plus document normalization.

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

🤖 List the folder contents and confirm you can see these five files:

```
SPEC.md
BUILD.md
CRITERIA.md
SECURITY.md
first-look-security-patch.md
```

Read all five in full before doing anything else.

🤖 Check whether the GitHub-created files are also present (`README.md`, `.gitignore`,
`LICENSE`). They may not be yet — Phase 2 brings them down.

**Verify:** report which files you found. If any of the five design documents is missing,
stop and tell the user.

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

**Verify:** `README.md`, `.gitignore`, and `LICENSE` now exist locally alongside the five
design documents.

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
project.

**Second — and this one is critical — remove any line matching `*.db`, `*.sqlite`, or
`*.sqlite3`.** GitHub's Python template usually includes them. This project **commits its
SQLite database as state by design**, and excluding it would silently break the entire
persistence model.

🤖 Show the user the final `.gitignore` and explicitly confirm no database pattern
remains.

**Verify:** `git check-ignore -v data/jobs.db` should return **nothing**. If it returns a
matching rule, the offending line is still there.

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

## Phase 5 — Document normalization

Now the actual setup work.

🤖 **Step 1.** Create `CLAUDE.md` from the template in `BUILD.md` §0.2, exactly as
written.

🤖 **Step 2.** Create `DEVLOG.md` containing only a title heading:

```markdown
# First Look — Development Log
```

🤖 **Step 3.** Apply **only sections 2, 4, and 5** of `first-look-security-patch.md` — to
`SPEC.md`, `CRITERIA.md`, and `SECURITY.md` respectively.

**Sections 1 and 3 are already incorporated into `BUILD.md` and `CLAUDE.md`. Skip them
entirely — applying them would duplicate content.**

Every item in those sections is an insertion or an append. **Nothing may be deleted or
reworded.** The Security criteria block goes at the **end** of `CRITERIA.md`, after all
existing criteria, with existing numbering untouched.

🤖 **Step 4.** Delete `first-look-security-patch.md` once fully applied.

🤖 **Step 5.** Create `.githooks/pre-commit` from `BUILD.md` §0.3. Include the
`#!/usr/bin/env bash` shebang — Git for Windows runs hooks through its bundled bash, so
the script works despite `chmod` being meaningless on Windows.

Do **not** run `git config core.hooksPath` — the user does that in Phase 6.

**Verify — report all of this before committing:**

- `git diff` for every changed file.
- An explicit confirmation that no existing line was deleted or reworded.
- An explicit confirmation that `CRITERIA.md`'s original criterion numbering is unchanged
  and every original `C-` identifier is still present.

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
git commit -m "Setup: CLAUDE.md, DEVLOG, security patch applied, pre-commit hook"
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

**A hosted form** (Tally, Google Forms, or Formspree) for alert requests — see `SPEC.md`
§13.2. This can wait until M10 if they'd rather move on.

---

## Phase 9 — Close out

🤖 Append the first `DEVLOG.md` entry using the template in `BUILD.md` §0.4. Record:

- Setup completed, date
- Which email identity was chosen for commits
- The PAT expiry date
- Which accounts were created
- Any contradiction, ambiguity, or gap you noticed while reading SPEC, BUILD, CRITERIA,
  and SECURITY — places where documents disagree, or where something is referenced but
  never defined

🤖 **Report that list of contradictions to the user directly as well. Do not fix any of
them.** Five documents written across a long design conversation will have seams, and
this is the cheapest moment to resolve them — but the decisions are the user's.

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
- No deleting or rewording anything in `CRITERIA.md`.
- No applying sections 1 or 3 of the security patch.
- No committing before the hook is verified working.
- No proceeding past a failed verification step.
