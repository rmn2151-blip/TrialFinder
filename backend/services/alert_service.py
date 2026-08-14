"""
Trial change detection and alerting.

Flow:
  1. For each watched trial, fetch its current state from ClinicalTrials.gov.
  2. Diff against the snapshot we stored last time.
  3. Record each change as a TrialAlert (deduplicated, so a change is only
     ever recorded once per trial).
  4. Email each account a single digest of everything new, if they have email
     alerts enabled.
  5. Update the stored snapshot so the same change is not re-detected.

Alerts persist independently of email, so a user who unsubscribed still sees
their updates in the app.
"""

import hashlib
import logging
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Account, PatientProfile, TrialAlert, WatchedTrial
from models.watchlist import CheckSummary
from services import ctgov_service, email_service

logger = logging.getLogger(__name__)

# Fields we diff, with a human label and whether a change is high priority.
_FIELDS = {
    "status": ("Status", True),
    "phase": ("Phase", False),
    "completion_date": ("Completion date", False),
    "site_count": ("Number of sites", False),
}

# Status transitions that materially change what a patient can do.
_CLOSING_STATUSES = {
    "active, not recruiting",
    "completed",
    "terminated",
    "suspended",
    "withdrawn",
}


def _hash_change(change_type: str, old, new) -> str:
    raw = f"{change_type}|{old}|{new}"
    return hashlib.sha256(raw.encode()).hexdigest()


def ensure_unsubscribe_token(db: Session, account: Account) -> str:
    """Lazily create a token so old accounts get one on first use."""
    if not account.unsubscribe_token:
        account.unsubscribe_token = secrets.token_urlsafe(32)
        db.flush()
    return account.unsubscribe_token


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------


def diff_snapshots(old: dict, new: dict) -> list[dict]:
    """
    Compare stored state to freshly fetched state.

    Returns a list of structured change dicts. Pure function, no I/O, so the
    detection logic is cheap to test.
    """
    changes: list[dict] = []

    for field, (label, is_high) in _FIELDS.items():
        old_val = old.get(field)
        new_val = new.get(field)

        if new_val is None or new_val == old_val:
            continue

        if field == "site_count":
            if old_val is None:
                continue
            if new_val > old_val:
                desc = f"{label}: {old_val} to {new_val} (new sites added)"
            else:
                desc = f"{label}: {old_val} to {new_val} (sites removed)"
            severity = "normal"
        elif old_val is None:
            desc = f"{label}: now {new_val}"
            severity = "normal"
        else:
            desc = f"{label}: {old_val} to {new_val}"
            # Recruitment closing is the one change a patient must act on.
            severity = (
                "high"
                if field == "status" and str(new_val).lower() in _CLOSING_STATUSES
                else ("high" if is_high else "normal")
            )

        changes.append(
            {
                "change_type": field,
                "description": desc,
                "old_value": None if old_val is None else str(old_val),
                "new_value": str(new_val),
                "severity": severity,
            }
        )

    return changes


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


def _record_alert(
    db: Session,
    *,
    account: Account,
    watch: WatchedTrial,
    profile: PatientProfile,
    change: dict,
) -> Optional[TrialAlert]:
    """
    Insert an alert unless this exact change is already recorded.
    Returns the new alert, or None if it was a duplicate.
    """
    change_hash = _hash_change(
        change["change_type"], change["old_value"], change["new_value"]
    )

    existing = db.execute(
        select(TrialAlert).where(
            TrialAlert.watched_trial_id == watch.id,
            TrialAlert.change_hash == change_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    alert = TrialAlert(
        watched_trial_id=watch.id,
        account_id=account.id,
        nct_id=watch.nct_id,
        trial_title=watch.title,
        profile_label=profile.label,
        source_url=watch.source_url
        or f"https://clinicaltrials.gov/study/{watch.nct_id}",
        change_type=change["change_type"],
        description=change["description"],
        old_value=change["old_value"],
        new_value=change["new_value"],
        severity=change["severity"],
        change_hash=change_hash,
    )
    db.add(alert)
    db.flush()
    return alert


def run_check(db: Session, *, send_email: bool = True) -> CheckSummary:
    """Sweep every watched trial, record alerts, and email digests."""
    accounts = db.execute(select(Account)).scalars().all()
    now = datetime.utcnow()

    trials_checked = 0
    trials_changed = 0
    emails_sent = 0
    details: list[str] = []

    for account in accounts:
        new_alerts: list[TrialAlert] = []

        for profile in account.profiles:
            for watch in profile.watched_trials:
                trials_checked += 1

                fresh = ctgov_service.fetch_study(watch.nct_id)
                watch.last_checked_at = now
                if fresh is None:
                    logger.info(
                        "alert.fetch_failed nct_id=%s (skipping)", watch.nct_id
                    )
                    continue

                changes = diff_snapshots(watch.snapshot(), fresh)

                if changes:
                    trials_changed += 1
                    watch.last_change_at = now
                    for change in changes:
                        alert = _record_alert(
                            db,
                            account=account,
                            watch=watch,
                            profile=profile,
                            change=change,
                        )
                        if alert is not None:
                            new_alerts.append(alert)
                            details.append(
                                f"{account.email} | {profile.label} | "
                                f"{watch.nct_id}: {change['description']}"
                            )

                # If the trial just completed, try to pull published results.
                new_status = (fresh.get("status") or "").lower()
                if "complet" in new_status and not watch.results_summary:
                    _attach_results(db, account, profile, watch, now, new_alerts)

                # Always refresh the snapshot so we do not re-detect.
                watch.last_status = fresh.get("status")
                watch.last_phase = fresh.get("phase")
                watch.last_completion_date = fresh.get("completion_date")
                watch.last_site_count = fresh.get("site_count")

        if new_alerts and send_email and account.email_alerts_enabled:
            token = ensure_unsubscribe_token(db, account)
            ok = email_service.send_watchlist_digest(
                account.email,
                _group_for_email(new_alerts),
                unsubscribe_token=token,
            )
            if ok:
                emails_sent += 1
                for alert in new_alerts:
                    alert.emailed_at = now
        elif new_alerts and not account.email_alerts_enabled:
            logger.info(
                "alert.email_skipped account_id=%s reason=unsubscribed alerts=%d",
                account.id,
                len(new_alerts),
            )

    db.commit()

    summary = CheckSummary(
        accounts_checked=len(accounts),
        trials_checked=trials_checked,
        trials_changed=trials_changed,
        emails_sent=emails_sent,
        details=details,
    )
    logger.info(
        "alert.sweep_complete accounts=%d trials=%d changed=%d emails=%d",
        summary.accounts_checked,
        summary.trials_checked,
        summary.trials_changed,
        summary.emails_sent,
    )
    return summary


def _attach_results(db, account, profile, watch, now, new_alerts) -> None:
    """Fetch published results for a completed trial and alert on them."""
    import asyncio

    from services import results_service

    try:
        results = asyncio.run(
            results_service.fetch_results_summary(watch.nct_id, watch.title)
        )
    except Exception as exc:
        logger.warning("alert.results_fetch_failed nct_id=%s: %s", watch.nct_id, exc)
        return

    if not results or not results.summary:
        return

    watch.results_headline = results.headline
    watch.results_summary = results.summary
    watch.results_journal_url = results.journal_url
    watch.results_fetched_at = now

    alert = _record_alert(
        db,
        account=account,
        watch=watch,
        profile=profile,
        change={
            "change_type": "results",
            "description": results.headline
            or "Results have been published for this trial.",
            "old_value": None,
            "new_value": (results.summary or "")[:500],
            "severity": "high",
        },
    )
    if alert is not None:
        new_alerts.append(alert)


def _group_for_email(alerts: list[TrialAlert]) -> list[dict]:
    """Collapse alerts into one entry per trial for the digest email."""
    by_trial: dict[str, dict] = {}
    for a in alerts:
        entry = by_trial.setdefault(
            a.nct_id,
            {
                "nct_id": a.nct_id,
                "title": a.trial_title,
                "profile_label": a.profile_label,
                "source_url": a.source_url,
                "changes": [],
                "severity": "normal",
            },
        )
        entry["changes"].append(a.description)
        if a.severity == "high":
            entry["severity"] = "high"
    # High-priority trials first.
    return sorted(by_trial.values(), key=lambda e: e["severity"] != "high")


# ---------------------------------------------------------------------------
# Reading alerts
# ---------------------------------------------------------------------------


def list_alerts(
    db: Session, account_id: int, *, unread_only: bool = False, limit: int = 50
) -> list[TrialAlert]:
    stmt = select(TrialAlert).where(TrialAlert.account_id == account_id)
    if unread_only:
        stmt = stmt.where(TrialAlert.read_at.is_(None))
    stmt = stmt.order_by(TrialAlert.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def count_unread(db: Session, account_id: int) -> int:
    return len(list_alerts(db, account_id, unread_only=True, limit=1000))


def mark_read(db: Session, account_id: int, alert_id: int) -> bool:
    """Mark one alert read. Scoped by account so users cannot touch others'."""
    alert = db.get(TrialAlert, alert_id)
    if alert is None or alert.account_id != account_id:
        return False
    if alert.read_at is None:
        alert.read_at = datetime.utcnow()
        db.flush()
    return True


def mark_all_read(db: Session, account_id: int) -> int:
    alerts = list_alerts(db, account_id, unread_only=True, limit=1000)
    now = datetime.utcnow()
    for a in alerts:
        a.read_at = now
    db.flush()
    return len(alerts)


def unsubscribe_by_token(db: Session, token: str) -> Optional[Account]:
    """Turn off email alerts using the token from an email link."""
    if not token:
        return None
    account = db.execute(
        select(Account).where(Account.unsubscribe_token == token)
    ).scalar_one_or_none()
    if account is None:
        return None
    account.email_alerts_enabled = 0
    db.flush()
    logger.info("alert.unsubscribed account_id=%s", account.id)
    return account
