"""
Scheduled trial-change sweep.

Re-queries ClinicalTrials.gov for every saved trial, records what changed,
and emails each affected user one digest.

Run manually:
    cd backend && python -m jobs.check_watchlist

Schedule daily at 7am:
    0 7 * * *  cd /path/to/backend && /path/to/python -m jobs.check_watchlist

Or, if the API is deployed, hit the endpoint instead:
    curl -X POST https://your-api/api/watchlist/check -H "X-Cron-Token: $CRON_TOKEN"

Uses the free ClinicalTrials.gov API, so it costs nothing to run.
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("check_watchlist")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check saved trials for changes")
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Detect and record changes without sending any email.",
    )
    args = parser.parse_args()

    from db.database import init_db, session_scope
    from services import alert_service

    init_db()
    logger.info("Starting trial change sweep (email=%s)", not args.no_email)

    with session_scope() as db:
        summary = alert_service.run_check(db, send_email=not args.no_email)

    logger.info(
        "Done. %d accounts, %d trials checked, %d changed, %d emails sent.",
        summary.accounts_checked,
        summary.trials_checked,
        summary.trials_changed,
        summary.emails_sent,
    )
    for line in summary.details:
        logger.info("  %s", line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
