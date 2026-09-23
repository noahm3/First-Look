"""The monitoring run. Entry point for monitor.yml.

At M0 this does what BUILD.md §4 asks and no more: open a run, do nothing, close
it, write the export, ping healthchecks, exit 0. The polling loop arrives with M4,
the adapters with M2, the mapping cascade with M3.

That "do nothing" is not a placeholder to be embarrassed about — it is the point
of the milestone. Everything around the empty middle is the part that is painful
to retrofit: the run row, the anomaly rules, the dead-man's switch, the exit code,
the committed export. Proving that shell works while there is nothing inside it is
much easier than debugging it later with four crawlers attached.

Usage:
    python -m src.monitor [--seed] [--export docs/jobs-recent.json]
                          [--force-failure]
"""

import argparse
import logging
import os
import sys
from datetime import UTC, datetime

from src.db import Database, DatabaseUnavailable
from src.export import ExportMeta, build_export, is_stale, write_export
from src.health import RunRecorder
from src.http import FetchClient

log = logging.getLogger(__name__)

DEFAULT_EXPORT_PATH = "docs/jobs-recent.json"
HEALTHCHECK_ENV_VAR = "HEALTHCHECK_URL"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        action="store_true",
        help=(
            "populate without producing new-posting output or sending email "
            "(SPEC.md §10). Accepted now so the flag exists before M4 needs it; "
            "there is nothing to seed yet."
        ),
    )
    parser.add_argument("--export", default=DEFAULT_EXPORT_PATH)
    parser.add_argument(
        "--force-failure",
        action="store_true",
        help=(
            "exit non-zero on purpose. This is how C-0.6 is demonstrated: a forced "
            "failure must produce a GitHub workflow-failure email. Untested "
            "alerting is not alerting (SPEC.md §14)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    now = datetime.now(UTC)

    try:
        db = Database.from_env()
    except DatabaseUnavailable as exc:
        # No run row is possible, so there is no summary to print from one. Say
        # so loudly on stdout and exit non-zero: silence here would be the exact
        # failure §3.3 forbids.
        print(f"=== run [FAILED] ===\n{exc}\nexiting non-zero")
        return 1

    fetcher = FetchClient()
    try:
        recorder = RunRecorder(
            db,
            healthcheck_url=os.environ.get(HEALTHCHECK_ENV_VAR) or None,
            fetcher=fetcher,
        )
        with recorder:
            if args.force_failure:
                recorder.record_failing_company("--force-failure", "requested on the command line")
                recorder.bump("http_err", 100)

            # ---- M2/M3/M4 fill this in. Nothing polls yet (SPEC.md §3.10:
            # ---- only mapped ATS endpoints are ever polled, and there are none).
            rows = _export_rows(db, recorder)

            recorder.set_count("total_live_postings", len(rows))

            last_success = _last_success(db, recorder)
            payload = build_export(
                rows,
                ExportMeta(
                    generated_at=now,
                    last_successful_run=last_success,
                    run_id=recorder.run_id,
                    stale=is_stale(last_success, now),
                ),
            )
            written = write_export(args.export, payload)
            log.info("wrote %s (%d postings)", written, len(payload["postings"]))

        return recorder.exit_code
    finally:
        fetcher.close()
        db.close()


def _export_rows(db: Database, recorder: RunRecorder) -> list:
    """Open postings for the export, or an empty list if the database is unreachable."""
    try:
        return db.open_postings_for_export()
    except DatabaseUnavailable as exc:
        recorder.record_failing_company("export", f"could not read postings: {exc}")
        return []


def _last_success(db: Database, recorder: RunRecorder) -> datetime | None:
    try:
        return db.last_successful_run_at()
    except DatabaseUnavailable:
        recorder.record_failing_company("export", "could not read the last successful run")
        return None


if __name__ == "__main__":
    sys.exit(main())
