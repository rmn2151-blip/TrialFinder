"""
Nightly watchlist change-detection job.

Re-queries ClinicalTrials.gov for every watched trial, records status/phase/
site/completion-date changes, and emails affected users a digest.

Run manually:
    cd backend && python -m jobs.check_watchlist

Schedule (cron, daily 7am):
    0 7 * * *  cd /path/to/backend && /path/to/python -m jobs.check_watchlist

Or, if the API is deployed, hit the endpoint instead (e.g. Railway cron):
    curl -X POST https://your-api/api/watchlist/check -H "X-Cron-Token: $CRON_TOKEN"

Uses the free CT.gov API, so it does NOT spend any Linkup budget.
"""

import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("check_watchlist")


def main() -> int:
    from db.database import init_db, session_scope
    from services import watchlist_service

    init_db()
    logger.info("Starting watchlist change-detection sweep…")

    with session_scope() as db:
        summary = watchlist_service.run_check(db, send_email=True)

    logger.info(
        "Done — %d trials checked, %d changed, %d emails sent.",
        summary.trials_checked,
        summary.trials_changed,
        summary.emails_sent,
    )
    for line in summary.details:
        logger.info("  changed: %s", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
