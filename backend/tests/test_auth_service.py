"""
Tests for auth_service: password hashing, JWT round-trip, register/authenticate.
Offline, against in-memory SQLite.
Run: pytest tests/test_auth_service.py -v
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from services import auth_service


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def test_password_hash_roundtrip():
    h = auth_service.hash_password("hunter2pass")
    assert h != "hunter2pass"  # never stored in plaintext
    assert auth_service.verify_password("hunter2pass", h) is True
    assert auth_service.verify_password("wrong", h) is False


def test_verify_handles_garbage_hash():
    assert auth_service.verify_password("x", "not-a-bcrypt-hash") is False


def test_register_and_authenticate(db):
    # register() returns (account, plaintext_code): the verification code is
    # handed back exactly once so the caller can email it, and is stored only
    # as a hash.
    account, code = auth_service.register(db, "User@Example.com", "password123")
    db.commit()
    assert account.email == "user@example.com"  # normalized lowercase
    assert len(code) == 6 and code.isdigit()
    assert auth_service.authenticate(db, "user@example.com", "password123") is not None


def test_authenticate_rejects_wrong_password(db):
    auth_service.register(db, "pw@example.com", "password123")
    db.commit()
    # Failures raise rather than returning None, so a caller cannot fall
    # through to a logged-in state by forgetting to check the return value.
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, "pw@example.com", "nope")


def test_authenticate_rejects_unknown_email(db):
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, "missing@example.com", "password123")


def test_register_duplicate_email_raises(db):
    auth_service.register(db, "dup@example.com", "password123")
    db.commit()
    with pytest.raises(auth_service.AuthError) as exc:
        auth_service.register(db, "dup@example.com", "password123")
    assert exc.value.code == "email_taken"


def test_jwt_roundtrip(db):
    account, _ = auth_service.register(db, "jwt@example.com", "password123")
    db.commit()
    token = auth_service.create_token(account)
    payload = auth_service.decode_token(token)
    assert payload is not None
    assert payload["sub"] == str(account.id)
    assert payload["iss"] == "trialfinder"
    # token_version is what makes logout able to revoke tokens that were
    # already issued, so it has to be in the payload.
    assert payload["tv"] == int(account.token_version or 0)
    # The email is deliberately absent. A JWT is only base64, not encrypted,
    # and anything put in it is readable by anyone holding the token, so the
    # account id is enough.
    assert "email" not in payload


def test_decode_bad_token_returns_none():
    assert auth_service.decode_token("garbage.token.here") is None
