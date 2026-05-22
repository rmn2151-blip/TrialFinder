"""
Tests for watchlist change detection (diff_snapshots) and profile-scoped CRUD
against an in-memory SQLite database. CT.gov and email are monkeypatched, so
these run fully offline.
Run: pytest tests/test_watchlist_service.py -v
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import Account, PatientProfile
from services import auth_service, watchlist_service


# ---------------------------------------------------------------------------
# diff_snapshots — pure function
# ---------------------------------------------------------------------------


def test_diff_detects_status_change():
    old = {"status": "Recruiting", "phase": "Phase II", "completion_date": "2026-12", "site_count": 3}
    new = {"status": "Active, not recruiting", "phase": "Phase II", "completion_date": "2026-12", "site_count": 3}
    changes = watchlist_service.diff_snapshots(old, new)
    assert len(changes) == 1
    assert "Status" in changes[0] and "Recruiting" in changes[0] and "Active" in changes[0]


def test_diff_detects_new_sites():
    changes = watchlist_service.diff_snapshots(
        {"status": "Recruiting", "site_count": 2}, {"status": "Recruiting", "site_count": 5}
    )
    assert any("new sites added" in c for c in changes)


def test_diff_detects_completion_date_move():
    changes = watchlist_service.diff_snapshots(
        {"completion_date": "2026-06-01"}, {"completion_date": "2027-01-01"}
    )
    assert any("Completion date" in c for c in changes)


def test_diff_no_change_returns_empty():
    snap = {"status": "Recruiting", "phase": "Phase III", "completion_date": "2026-12", "site_count": 4}
    assert watchlist_service.diff_snapshots(snap, dict(snap)) == []


def test_diff_ignores_none_new_values():
    assert watchlist_service.diff_snapshots(
        {"status": "Recruiting", "phase": "Phase II"}, {"status": "Recruiting", "phase": None}
    ) == []


def test_diff_first_known_value_is_soft_noted():
    changes = watchlist_service.diff_snapshots({"status": None}, {"status": "Recruiting"})
    assert changes and "now Recruiting" in changes[0]


# ---------------------------------------------------------------------------
# Profile-scoped CRUD + run_check against in-memory SQLite
# ---------------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(watchlist_service.ctgov_service, "fetch_study", lambda nct_id: None)
    yield session
    session.close()


@pytest.fixture
def profile(db):
    account = auth_service.register(db, "owner@b.com", "password123")
    p = PatientProfile(account_id=account.id, label="Mom", condition="NSCLC", location="NY")
    db.add(p)
    db.flush()
    db.commit()
    return p


def test_add_and_list_watch(db, profile):
    watchlist_service.add_watch(db, profile_id=profile.id, nct_id="NCT04685135", title="A trial")
    db.commit()
    watches = watchlist_service.list_watches(db, profile.id)
    assert len(watches) == 1
    assert watches[0].nct_id == "NCT04685135"


def test_add_is_idempotent(db, profile):
    for _ in range(2):
        watchlist_service.add_watch(db, profile_id=profile.id, nct_id="NCT04685135", title="A")
        db.commit()
    assert len(watchlist_service.list_watches(db, profile.id)) == 1


def test_get_owned_watch_scoped_to_account(db, profile):
    w = watchlist_service.add_watch(db, profile_id=profile.id, nct_id="NCT04685135", title="A")
    db.commit()
    owner_id = profile.account_id
    # Different account cannot reach the watch.
    other = auth_service.register(db, "intruder@b.com", "password123")
    db.commit()
    assert watchlist_service.get_owned_watch(db, other.id, w.id) is None
    assert watchlist_service.get_owned_watch(db, owner_id, w.id) is not None


def test_run_check_emails_on_change(db, profile, monkeypatch):
    w = watchlist_service.add_watch(db, profile_id=profile.id, nct_id="NCT04685135", title="A")
    w.last_status = "Recruiting"
    db.commit()

    monkeypatch.setattr(
        watchlist_service.ctgov_service, "fetch_study",
        lambda nct_id: {"status": "Completed", "phase": None, "completion_date": None, "site_count": None, "source_url": "u"},
    )
    sent = []
    monkeypatch.setattr(
        watchlist_service.email_service, "send_watchlist_digest",
        lambda email, changes: sent.append((email, changes)) or True,
    )

    summary = watchlist_service.run_check(db, send_email=True)
    assert summary.trials_changed == 1
    assert summary.emails_sent == 1
    assert sent[0][0] == "owner@b.com"
    # Digest carries the profile label for caregiver context.
    assert sent[0][1][0]["profile_label"] == "Mom"
