"""
Router-level auth tests: confirm that invalid credentials, missing tokens,
and tampered tokens cannot get past the auth boundary.

These spin up an in-memory SQLite DB per test via dependency override so
nothing is written to the real watchlist.db.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db.database import Base, get_db


@pytest.fixture
def client():
    # StaticPool is required so every session shares the same in-memory DB
    # connection — otherwise each session gets a fresh empty SQLite.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def _override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = _override
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def _register(client, email="alice@example.com", password="hunter2pass"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Wrong-credential failures: 401, never 200, never leak which field was wrong
# ---------------------------------------------------------------------------


def test_login_wrong_password_returns_401(client):
    _register(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WRONG_PASSWORD"},
    )
    assert r.status_code == 401
    # Must not leak that the account exists — keep the message generic.
    assert "invalid" in r.json()["detail"].lower()


def test_login_unknown_email_returns_401(client):
    _register(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "anything12"},
    )
    assert r.status_code == 401
    # Same generic message regardless of whether the email exists.
    assert "invalid" in r.json()["detail"].lower()


def test_login_returns_no_account_data_on_failure(client):
    _register(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrongpass99"},
    )
    body = r.json()
    assert "access_token" not in body
    assert "account" not in body


def test_login_case_insensitive_email_still_rejects_wrong_password(client):
    _register(client, email="Alice@Example.com", password="hunter2pass")
    r = client.post(
        "/api/auth/login",
        json={"email": "ALICE@example.com", "password": "WRONG"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Token boundary: missing, malformed, tampered
# ---------------------------------------------------------------------------


def test_me_without_token_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_garbage_token_returns_401(client):
    r = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer garbage.token.here"}
    )
    assert r.status_code == 401


def test_me_with_tampered_token_returns_401(client):
    data = _register(client)
    token = data["access_token"]
    tampered = token[:-4] + "AAAA"  # mutate the signature
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_me_with_wrong_scheme_returns_401(client):
    data = _register(client)
    token = data["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 401


def test_valid_token_can_access_me(client):
    data = _register(client)
    token = data["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


# ---------------------------------------------------------------------------
# Protected endpoints reject unauthenticated calls
# ---------------------------------------------------------------------------


def test_profile_create_requires_auth(client):
    r = client.post("/api/profiles", json={"label": "x", "condition": "NSCLC", "location": "NY"})
    assert r.status_code == 401


def test_profile_list_requires_auth(client):
    r = client.get("/api/profiles")
    assert r.status_code == 401


def test_watchlist_add_requires_auth(client):
    r = client.post(
        "/api/watchlist",
        json={"profile_id": 1, "nct_id": "NCT04685135", "title": "x"},
    )
    assert r.status_code == 401


def test_watchlist_list_requires_auth(client):
    r = client.get("/api/watchlist", params={"profile_id": 1})
    assert r.status_code == 401


def test_watchlist_status_update_requires_auth(client):
    r = client.put("/api/watchlist/1/status", json={"status": "contacted"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Cross-account isolation
# ---------------------------------------------------------------------------


def test_one_user_cannot_read_anothers_profile(client):
    alice = _register(client, email="alice@example.com", password="hunter2pass")
    bob = _register(client, email="bob@example.com", password="hunter2pass")

    # Alice creates a profile.
    h_a = {"Authorization": f"Bearer {alice['access_token']}"}
    p = client.post(
        "/api/profiles",
        json={"label": "Mom", "condition": "NSCLC", "location": "NY"},
        headers=h_a,
    ).json()

    # Bob cannot fetch it — must be 404 (don't leak existence).
    h_b = {"Authorization": f"Bearer {bob['access_token']}"}
    r = client.get(f"/api/profiles/{p['id']}", headers=h_b)
    assert r.status_code == 404


def test_one_user_cannot_modify_anothers_watchlist(client, monkeypatch):
    # Patch ctgov_service so add_watch doesn't try the network (cleaned up by monkeypatch).
    from services import ctgov_service
    monkeypatch.setattr(ctgov_service, "fetch_study", lambda nct_id: None)

    alice = _register(client, email="alice@example.com", password="hunter2pass")
    bob = _register(client, email="bob@example.com", password="hunter2pass")
    h_a = {"Authorization": f"Bearer {alice['access_token']}"}
    h_b = {"Authorization": f"Bearer {bob['access_token']}"}

    p = client.post(
        "/api/profiles",
        json={"label": "Mom", "condition": "NSCLC", "location": "NY"},
        headers=h_a,
    ).json()

    watch = client.post(
        "/api/watchlist",
        json={"profile_id": p["id"], "nct_id": "NCT04685135", "title": "A trial"},
        headers=h_a,
    ).json()

    # Bob can't read Alice's watchlist for that profile, can't update status,
    # and can't delete the watch.
    assert client.get("/api/watchlist", params={"profile_id": p["id"]}, headers=h_b).status_code == 404
    assert client.put(
        f"/api/watchlist/{watch['id']}/status",
        json={"status": "contacted"},
        headers=h_b,
    ).status_code == 404
    assert client.delete(f"/api/watchlist/{watch['id']}", headers=h_b).status_code == 404
