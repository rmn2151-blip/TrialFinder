"""
Trial alert pipeline tests.

Covers change detection, alert persistence, deduplication, email delivery,
preferences, unsubscribe, and cross-account isolation.

Run: pytest tests/test_alerts.py -v
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault(
    "JWT_SECRET", "test-secret-long-enough-for-hs256-rfc7518-compliance"
)

from db.database import Base  # noqa: E402
from db.models import PatientProfile, TrialAlert, WatchedTrial  # noqa: E402
from services import alert_service  # noqa: E402
from services import auth_service  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def watched(db):
    """A verified account with one profile watching one recruiting trial."""
    account, _ = auth_service.register(db, "user@example.com", "hunter2pass")
    account.email_verified = 1
    profile = PatientProfile(
        account_id=account.id,
        label="Myself",
        condition="breast cancer",
        location="Wilmington, DE",
        treatment_history="none",
        medications=["none"],
    )
    db.add(profile)
    db.flush()
    watch = WatchedTrial(
        profile_id=profile.id,
        nct_id="NCT05879926",
        title="A Study of Adjuvant Chemotherapy",
        source_url="https://clinicaltrials.gov/study/NCT05879926",
        last_status="Recruiting",
        last_phase="Phase III",
        last_completion_date="2027-06",
        last_site_count=12,
    )
    db.add(watch)
    db.commit()
    return {"account": account, "profile": profile, "watch": watch}


def _snapshot(**overrides):
    base = {
        "status": "Recruiting",
        "phase": "Phase III",
        "completion_date": "2027-06",
        "site_count": 12,
        "source_url": "https://clinicaltrials.gov/study/NCT05879926",
    }
    base.update(overrides)
    return base


def _patch_ctgov(monkeypatch, snapshot):
    monkeypatch.setattr(
        alert_service.ctgov_service, "fetch_study", lambda nct_id: snapshot
    )


def _capture_email(monkeypatch):
    sent = []

    def fake_send(to_email, changes, unsubscribe_token=None):
        sent.append(
            {"to": to_email, "changes": changes, "token": unsubscribe_token}
        )
        return True

    monkeypatch.setattr(alert_service.email_service, "send_watchlist_digest", fake_send)
    return sent


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def test_no_change_produces_no_alert(db, watched, monkeypatch):
    _patch_ctgov(monkeypatch, _snapshot())
    sent = _capture_email(monkeypatch)

    summary = alert_service.run_check(db, send_email=True)
    assert summary.trials_changed == 0
    assert summary.emails_sent == 0
    assert sent == []
    assert db.query(TrialAlert).count() == 0


def test_status_change_creates_alert_and_email(db, watched, monkeypatch):
    _patch_ctgov(monkeypatch, _snapshot(status="Active, not recruiting"))
    sent = _capture_email(monkeypatch)

    summary = alert_service.run_check(db, send_email=True)

    assert summary.trials_changed == 1
    assert summary.emails_sent == 1

    alerts = db.query(TrialAlert).all()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.change_type == "status"
    assert "Recruiting" in alert.description
    assert alert.account_id == watched["account"].id
    assert alert.profile_label == "Myself"
    # Recruitment closing is something the patient must act on.
    assert alert.severity == "high"
    assert alert.emailed_at is not None

    assert sent[0]["to"] == "user@example.com"
    assert sent[0]["token"]  # unsubscribe token included


def test_new_sites_detected(db, watched, monkeypatch):
    _patch_ctgov(monkeypatch, _snapshot(site_count=20))
    _capture_email(monkeypatch)
    alert_service.run_check(db, send_email=True)

    alert = db.query(TrialAlert).one()
    assert alert.change_type == "site_count"
    assert "new sites added" in alert.description
    assert alert.severity == "normal"


def test_multiple_changes_create_multiple_alerts_but_one_email(
    db, watched, monkeypatch
):
    # Three field changes at once. Deliberately not "Completed", which would
    # add a fourth alert from the results lookup and obscure what this test
    # is actually checking: many changes produce one grouped email.
    _patch_ctgov(
        monkeypatch,
        _snapshot(status="Suspended", completion_date="2026-01", site_count=3),
    )
    sent = _capture_email(monkeypatch)

    summary = alert_service.run_check(db, send_email=True)

    assert db.query(TrialAlert).count() == 3
    # One digest, not three separate emails.
    assert summary.emails_sent == 1
    assert len(sent) == 1
    # Grouped into a single trial entry listing all three changes.
    assert len(sent[0]["changes"]) == 1
    assert len(sent[0]["changes"][0]["changes"]) == 3


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_same_change_is_not_alerted_twice(db, watched, monkeypatch):
    """The snapshot updates, so a second sweep sees no change."""
    _patch_ctgov(monkeypatch, _snapshot(status="Suspended"))
    sent = _capture_email(monkeypatch)

    alert_service.run_check(db, send_email=True)
    assert db.query(TrialAlert).count() == 1
    assert len(sent) == 1

    alert_service.run_check(db, send_email=True)
    assert db.query(TrialAlert).count() == 1  # no duplicate
    assert len(sent) == 1  # no second email


def test_snapshot_is_updated_after_sweep(db, watched, monkeypatch):
    _patch_ctgov(monkeypatch, _snapshot(status="Suspended"))
    _capture_email(monkeypatch)
    alert_service.run_check(db, send_email=True)

    db.refresh(watched["watch"])
    assert watched["watch"].last_status == "Suspended"
    assert watched["watch"].last_checked_at is not None
    assert watched["watch"].last_change_at is not None


def test_unreachable_trial_is_skipped_not_alerted(db, watched, monkeypatch):
    monkeypatch.setattr(alert_service.ctgov_service, "fetch_study", lambda n: None)
    _capture_email(monkeypatch)
    summary = alert_service.run_check(db, send_email=True)
    assert summary.trials_changed == 0
    assert db.query(TrialAlert).count() == 0


# ---------------------------------------------------------------------------
# Preferences and unsubscribe
# ---------------------------------------------------------------------------


def test_unsubscribed_user_gets_alerts_but_no_email(db, watched, monkeypatch):
    watched["account"].email_alerts_enabled = 0
    db.commit()

    _patch_ctgov(monkeypatch, _snapshot(status="Suspended"))
    sent = _capture_email(monkeypatch)

    summary = alert_service.run_check(db, send_email=True)

    # The in-app alert is still recorded; only the email is suppressed.
    assert db.query(TrialAlert).count() == 1
    assert summary.emails_sent == 0
    assert sent == []


def test_unsubscribe_token_disables_email(db, watched):
    token = alert_service.ensure_unsubscribe_token(db, watched["account"])
    db.commit()
    assert watched["account"].email_alerts_enabled == 1

    account = alert_service.unsubscribe_by_token(db, token)
    db.commit()
    assert account is not None
    assert account.email_alerts_enabled == 0


def test_bad_unsubscribe_token_rejected(db, watched):
    assert alert_service.unsubscribe_by_token(db, "not-a-real-token") is None
    assert alert_service.unsubscribe_by_token(db, "") is None


# ---------------------------------------------------------------------------
# Reading, and cross-account isolation
# ---------------------------------------------------------------------------


def test_unread_count_and_mark_read(db, watched, monkeypatch):
    # Two independent changes. Deliberately not "Completed", because that
    # additionally triggers a results lookup and a third alert, which would
    # make the count assertion below ambiguous.
    _patch_ctgov(monkeypatch, _snapshot(status="Suspended", site_count=30))
    _capture_email(monkeypatch)
    alert_service.run_check(db, send_email=True)

    account_id = watched["account"].id
    assert alert_service.count_unread(db, account_id) == 2

    first = alert_service.list_alerts(db, account_id)[0]
    assert alert_service.mark_read(db, account_id, first.id) is True
    db.commit()
    assert alert_service.count_unread(db, account_id) == 1

    alert_service.mark_all_read(db, account_id)
    db.commit()
    assert alert_service.count_unread(db, account_id) == 0


def test_one_user_cannot_read_anothers_alert(db, watched, monkeypatch):
    _patch_ctgov(monkeypatch, _snapshot(status="Suspended"))
    _capture_email(monkeypatch)
    alert_service.run_check(db, send_email=True)

    intruder, _ = auth_service.register(db, "intruder@example.com", "hunter2pass")
    intruder.email_verified = 1
    db.commit()

    alert = db.query(TrialAlert).one()
    # Wrong account cannot mark it read, and does not see it listed.
    assert alert_service.mark_read(db, intruder.id, alert.id) is False
    assert alert_service.list_alerts(db, intruder.id) == []
    assert alert_service.count_unread(db, intruder.id) == 0


def test_deleting_watch_removes_its_alerts(db, watched, monkeypatch):
    # "Suspended" is a plain status change, so exactly one alert is produced.
    _patch_ctgov(monkeypatch, _snapshot(status="Suspended"))
    _capture_email(monkeypatch)
    alert_service.run_check(db, send_email=True)
    assert db.query(TrialAlert).count() == 1

    db.delete(watched["watch"])
    db.commit()
    assert db.query(TrialAlert).count() == 0


# ---------------------------------------------------------------------------
# Pure diff function
# ---------------------------------------------------------------------------


def test_diff_flags_closing_status_as_high_severity():
    changes = alert_service.diff_snapshots(
        {"status": "Recruiting"}, {"status": "Terminated"}
    )
    assert changes[0]["severity"] == "high"


def test_diff_ignores_missing_new_values():
    """A failed partial fetch must not look like a change."""
    assert (
        alert_service.diff_snapshots(
            {"status": "Recruiting", "phase": "Phase II"},
            {"status": "Recruiting", "phase": None},
        )
        == []
    )
