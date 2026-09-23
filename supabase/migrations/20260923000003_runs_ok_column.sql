-- Found by live testing on 2026-09-23: `last_successful_run_at()` had no way to
-- tell a cleanly-finished run apart from one that finished but tripped an
-- anomaly (posting drop, HTTP error rate, RLS posture, DB hiccup). A forced
-- C-0.6 test run exited non-zero as designed, but its `runs` row still closed
-- normally -- so the very next run's export reported that failed run's
-- timestamp as `last_successful_run`, which would show a green marker on the
-- dashboard for a run that had just failed. That directly contradicts
-- SPEC.md §12.1's stale-banner rule: the banner must appear whenever the last
-- run failed OR is over 48h old, and only the age half was actually checkable.
--
-- `ok` is this run's own verdict at the moment it finished, written once and
-- never revised, so later queries don't need to recompute an anomaly history
-- to answer "was the last run clean."

ALTER TABLE runs ADD COLUMN ok BOOLEAN NOT NULL DEFAULT true;

-- No RLS change needed: `runs` already enabled it in the migration that
-- created the table, and RLS is a table-level property, not a per-column one.
