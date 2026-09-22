# Project: First Look

Read SPEC.md before making design decisions. SPEC.md §4 lists rejected
alternatives — do not re-propose them. SPEC.md §19 is a deferred platform
era; do not build it without being asked.
Read BUILD.md for the current milestone. Read CRITERIA.md for its criteria.
Read the last two DEVLOG.md entries at the start of every session.

## Session protocol — every time
1. Read the last two DEVLOG entries and state where we left off.
2. Check the current milestone header in BUILD.md. It specifies a recommended
   model and whether to use plan mode. **Tell me explicitly** whether to switch
   model or enter plan mode, and wait for me to confirm before starting.
3. Commit directly to main. Commit at each criterion, not once at the end.
4. Before committing any change to SPEC.md or CRITERIA.md, show me the diff.
5. At session end, append a DEVLOG entry using the BUILD.md §0.4 template.
6. End every milestone with the evidence report in BUILD.md §0.5. Show real
   terminal output, never a summary.

## THIS IS A PUBLIC REPOSITORY
Everything committed is world-readable, including Actions run logs.

NEVER commit, print, or log:
- Email addresses (notify profiles live in the NOTIFY_PROFILES secret)
- LinkedIn connection data of any kind, including aggregate counts
- Any third party's name, employer, or contact details
- API keys, tokens, or credentials

GitHub masks exact secret values in logs. NOTIFY_PROFILES is a JSON blob we
parse, so an email extracted from it is a DIFFERENT string and will NOT be
masked. Never log a parsed profile, and never include a recipient in an
error message.

Run summaries report counts, never identities. Company names, ATS tokens, and
job postings are public data and are fine. If unsure whether something is
personal data, ask before committing it.

## CRITERIA.md rules
- Never delete or reword an existing criterion. Strike it through with a date
  and reason if superseded. Append new ones.
- Check a box only when I have seen the actual output, not a summary.

## Non-negotiables
- Python 3.12, stdlib + httpx + pytest. Justify any other dependency.
- No user-specific job criteria in src/. Dashboard filters are client-side;
  notification criteria come from the NOTIFY_PROFILES secret.
- No headless browsers. No authenticated scraping. No OAuth, no backend,
  no user accounts. No LinkedIn API or scraping.
- Every per-company operation is wrapped so no exception escapes the loop.
- Every network call goes through src/http.py. Nothing calls httpx directly.
- Tests never hit the network. Use fixtures in tests/fixtures/.
- Read SECURITY.md before writing dashboard rendering code, workflow files,
  or anything touching NOTIFY_PROFILES.
- Never use innerHTML, outerHTML, insertAdjacentHTML, or document.write with
  data from a posting, company, or URL parameter. Use textContent.

## Current milestone
M0. See BUILD.md.
