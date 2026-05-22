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
    account = auth_service.register(db, "User@Example.com", "password123")
    db.commit()
    assert account.email == "user@example.com"  # normalized lowercase
    assert auth_service.authenticate(db, "user@example.com", "password123") is not None
    assert auth_service.authenticate(db, "user@example.com", "nope") is None
    assert auth_service.authenticate(db, "missing@example.com", "password123") is None


def test_register_duplicate_email_raises(db):
    auth_service.register(db, "dup@example.com", "password123")
    db.commit()
    with pytest.raises(ValueError):
        auth_service.register(db, "dup@example.com", "password123")


def test_jwt_roundtrip(db):
    account = auth_service.register(db, "jwt@example.com", "password123")
    db.commit()
    token = auth_service.create_token(account)
    payload = auth_service.decode_token(token)
    assert payload is not None
    assert payload["sub"] == str(account.id)
    assert payload["email"] == "jwt@example.com"


def test_decode_bad_token_returns_none():
    assert auth_service.decode_token("garbage.token.here") is None
