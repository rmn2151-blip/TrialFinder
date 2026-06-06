"""
Watchlist business logic: saving trials to a patient profile, listing them,
and the nightly change-detection sweep that re-queries ClinicalTrials.gov and
emails the account when a watched trial changes.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

import asyncio

from db.models import Account, PatientProfile, WatchedTrial
from models.watchlist import CheckSummary
from services import ctgov_service, email_service, results_service

logger = logging.getLogger(__name__)

# Human-readable labels for the snapshot fields we diff.
_FIELD_LABELS = {
    "status": "Status",
    "phase": "Phase",
    "completion_date": "Completion date",
    "site_count": "Number of sites",
}


# ---------------------------------------------------------------------------
# Watchlist CRUD (scoped to a profile)
# ---------------------------------------------------------------------------


def add_watch(
    db: Session,
    *,
    profile_id: int,
    nct_id: str,
    title: str,
    source_url: Optional[str] = None,
) -> WatchedTrial:
    """Add a trial to a profile's watchlist (idempotent per profile+trial)."""
    existing = db.execute(
        select(WatchedTrial).where(
            WatchedTrial.profile_id == profile_id,
            WatchedTrial.nct_id == nct_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    # Seed the snapshot now so the first nightly run compares against reality,
    # not against an empty baseline (which would false-positive on everything).
    snapshot = ctgov_service.fetch_study(nct_id) or {}

    watch = WatchedTrial(
        profile_id=profile_id,
        nct_id=nct_id,
        title=title,
        source_url=source_url or snapshot.get("source_url"),
        last_status=snapshot.get("status"),
        last_phase=snapshot.get("phase"),
        last_completion_date=snapshot.get("completion_date"),
        last_site_count=snapshot.get("site_count"),
        last_checked_at=datetime.utcnow() if snapshot else None,
    )
    db.add(watch)
    db.flush()
    return watch


def list_watches(db: Session, profile_id: int) -> list[WatchedTrial]:
    return list(
        db.execute(
            select(WatchedTrial).where(WatchedTrial.profile_id == profile_id)
        ).scalars()
    )


def get_owned_watch(
    db: Session, account_id: int, watch_id: int
) -> Optional[WatchedTrial]:
    """Return a watch only if it belongs (via its profile) to this account."""
    watch = db.get(WatchedTrial, watch_id)
    if watch is None:
        return None
    profile = db.get(PatientProfile, watch.profile_id)
    if profile is None or profile.account_id != account_id:
        return None
    return watch


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def diff_snapshots(old: dict, new: dict) -> list[str]:
    """
    Compare a stored snapshot to a freshly fetched one and return a list of
    human-readable change descriptions. Pure function — no I/O — so it's
    cheap to unit test.
    """
    changes: list[str] = []
    for field, label in _FIELD_LABELS.items():
        old_val = old.get(field)
        new_val = new.get(field)
        if new_val is None or new_val == old_val:
            continue

        if field == "site_count":
            if old_val is None:
                continue
            if new_val > old_val:
                changes.append(f"{label}: {old_val} → {new_val} (new sites added)")
            elif new_val < old_val:
                changes.append(f"{label}: {old_val} → {new_val} (sites removed)")
            continue

        if old_val is None:
            changes.append(f"{label}: now {new_val}")
        else:
            changes.append(f"{label}: {old_val} → {new_val}")
    return changes


def run_check(db: Session, *, send_email: bool = True) -> CheckSummary:
    """
    Sweep every watched trial across all accounts/profiles, re-fetch current
    state from CT.gov, record changes, and email each affected account a
    digest grouped by patient profile. Returns a summary.
    """
    accounts = db.execute(select(Account)).scalars().all()
    trials_checked = 0
    trials_changed = 0
    emails_sent = 0
    details: list[str] = []
    now = datetime.utcnow()

    for account in accounts:
        account_changes: list[dict] = []

        for profile in account.profiles:
            for watch in profile.watched_trials:
                trials_checked += 1
                fresh = ctgov_service.fetch_study(watch.nct_id)
                watch.last_checked_at = now
                if fresh is None:
                    continue

                changes = diff_snapshots(watch.snapshot(), fresh)
                if changes:
                    trials_changed += 1
                    watch.last_change_at = now
                    account_changes.append(
                        {
                            "profile_label": profile.label,
                            "nct_id": watch.nct_id,
                            "title": watch.title,
                            "source_url": watch.source_url or fresh.get("source_url"),
                            "changes": changes,
                        }
                    )
                    details.append(
                        f"{account.email} · {profile.label} · {watch.nct_id}: {'; '.join(changes)}"
                    )

                # If this trial just became Completed and we haven't fetched
                # results yet, pull a plain-English results summary now.
                new_status = (fresh.get("status") or "").lower()
                if (
                    "complet" in new_status
                    and not watch.results_summary
                ):
                    try:
                        results = asyncio.run(
                            results_service.fetch_results_summary(
                                watch.nct_id, watch.title
                            )
                        )
                        watch.results_headline = results.headline
                        watch.results_summary = results.summary
                        watch.results_journal_url = results.journal_url
                        watch.results_fetched_at = now
                    except Exception as exc:
                        logger.warning(
                            "Results fetch failed for %s: %s", watch.nct_id, exc
                        )

                # Update the stored snapshot regardless, so we don't re-alert.
                watch.last_status = fresh.get("status")
                watch.last_phase = fresh.get("phase")
                watch.last_completion_date = fresh.get("completion_date")
                watch.last_site_count = fresh.get("site_count")

        if account_changes and send_email:
            ok = email_service.send_watchlist_digest(account.email, account_changes)
            if ok:
                emails_sent += 1

    db.commit()
    summary = CheckSummary(
        accounts_checked=len(accounts),
        trials_checked=trials_checked,
        trials_changed=trials_changed,
        emails_sent=emails_sent,
        details=details,
    )
    logger.info(
        "Watchlist check complete — %d accounts, %d trials, %d changed, %d emails",
        summary.accounts_checked,
        summary.trials_checked,
        summary.trials_changed,
        summary.emails_sent,
    )
    return summary
