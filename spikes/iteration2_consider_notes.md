# Iteration 2 spike, part B: Consider — notes, not a working parser

Target: `jobs.greentownlabs.com`, per `SPEC.md` §7.6.

## What's confirmed live

- The page is genuinely Consider-powered — the HTML contains
  `job-boards-footer-powered-by-consider`, `product.consider.com`, and a
  `window.serverInitialData` blob (Consider's equivalent of Getro's
  `__NEXT_DATA__`).
- `window.serverInitialData.board` = `{"id": "greentown-labs", "isParent": true}`
  — a real board identifier exists to query against.
- `window.serverInitialData` itself does **not** contain the job listings —
  only page config (board id, feature flags, a CSRF token, staff-count filter
  options). This matches `SPEC.md` §7.6's existing note: "job rows are not in
  the server HTML."

## What's still unconfirmed

- Guessed several REST-shaped endpoints (`/api/v1/boards/{id}/jobs`,
  `/api/boards/{id}/jobs`, `/jobs.json`, `/api/v1/jobs`) — all 404.
- `/graphql` returned HTTP 200, but the body is the same SPA HTML shell as
  every other path. This site's client-side router evidently catches
  unmatched paths and serves the shell rather than 404ing — so **a 200 here
  is not evidence of a real GraphQL endpoint**, and the earlier guess that it
  might be one was wrong. Worth remembering as a general trap: for an SPA,
  `curl`'s status code alone doesn't tell you whether a path is a real route.
- The actual data-fetching call happens client-side, presumably against
  `product.consider.com` or a per-tenant subdomain, using the CSRF token and
  board id from `serverInitialData`. Finding the real request needs a real
  browser's network tab (or a headless-browser trace, which `SPEC.md` §4
  rejects as infrastructure for the *pipeline* — doing it once, by hand, to
  learn the shape, is a different thing from running one in production).

## Where this leaves `SPEC.md` §17's open question #10

"Consider's client-side fetch — what endpoint, what shape" is **partially
answered**: it's not a simple guessable REST path, and the `/graphql`-looks-200
result is a false lead. Still open: the real endpoint and query shape, which
needs a one-time browser devtools session against a live Consider board
(Greentown Labs or another), not more URL guessing from the terminal.
