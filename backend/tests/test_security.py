"""
Security regression tests.

Each test here corresponds to a specific vulnerability class. If one of these
starts failing, treat it as a security regression, not a flaky test.

Run: pytest tests/test_security.py -v
"""

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault(
    "JWT_SECRET", "test-secret-long-enough-for-hs256-rfc7518-compliance"
)

from db.database import Base  # noqa: E402
from db.models import Account, PatientProfile  # noqa: E402
from services import auth_service as A  # noqa: E402
from services.auth_service import AuthError  # noqa: E402


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
def verified_account(db):
    account, _ = A.register(db, "user@example.com", "hunter2pass")
    account.email_verified = 1
    db.commit()
    return account


# ---------------------------------------------------------------------------
# Password storage
# ---------------------------------------------------------------------------


def test_passwords_are_bcrypt_hashed():
    h = A.hash_password("hunter2pass")
    assert h != "hunter2pass"
    assert h.startswith("$2b$")
    assert A.verify_password("hunter2pass", h)
    assert not A.verify_password("wrong", h)


def test_corrupt_hash_does_not_crash():
    assert A.verify_password("anything", "not-a-real-hash") is False


def test_overlong_password_rejected():
    """bcrypt truncates at 72 bytes, which would make distinct passwords equal."""
    with pytest.raises(AuthError):
        A.hash_password("a" * 100)


def test_password_never_stored_in_plaintext(db):
    account, _ = A.register(db, "a@example.com", "supersecret123")
    db.commit()
    assert "supersecret123" not in account.password_hash


# ---------------------------------------------------------------------------
# One-time codes: hashed, expiring, single-use
# ---------------------------------------------------------------------------


def test_verification_code_stored_hashed(db):
    account, code = A.register(db, "a@example.com", "hunter2pass")
    db.commit()
    assert account.verification_code_hash != code
    assert len(account.verification_code_hash) == 64  # sha256 hex


def test_verification_code_is_single_use(db):
    account, code = A.register(db, "a@example.com", "hunter2pass")
    db.commit()
    assert A.verify_code(db, "a@example.com", code) is not None
    db.commit()
    # Replaying the same code must fail.
    assert A.verify_code(db, "a@example.com", code) is None


def test_verification_code_expires(db):
    account, _ = A.register(db, "a@example.com", "hunter2pass")
    db.commit()
    acct, code = A.issue_new_code(db, "a@example.com")
    acct.verification_sent_at = datetime.utcnow() - timedelta(
        minutes=A.VERIFICATION_TTL_MINUTES + 5
    )
    db.commit()
    assert A.verify_code(db, "a@example.com", code) is None


def test_reset_code_stored_hashed_and_expires(db, verified_account):
    acct, code = A.issue_reset_code(db, "user@example.com")
    db.commit()
    assert acct.reset_code_hash != code

    acct.reset_sent_at = datetime.utcnow() - timedelta(minutes=A.RESET_TTL_MINUTES + 5)
    db.commit()
    assert A.reset_password(db, "user@example.com", code, "newpassword1") is None


def test_wrong_reset_code_rejected(db, verified_account):
    A.issue_reset_code(db, "user@example.com")
    db.commit()
    assert A.reset_password(db, "user@example.com", "000000", "newpassword1") is None


# ---------------------------------------------------------------------------
# Login: lockout and enumeration resistance
# ---------------------------------------------------------------------------


def test_account_locks_after_repeated_failures(db, verified_account):
    for _ in range(A.MAX_FAILED_LOGINS):
        with pytest.raises(AuthError):
            A.authenticate(db, "user@example.com", "wrongpassword")
    db.commit()

    # Even the correct password is refused while locked.
    with pytest.raises(AuthError) as exc:
        A.authenticate(db, "user@example.com", "hunter2pass")
    assert exc.value.code == "locked"


def test_successful_login_clears_failure_counter(db, verified_account):
    with pytest.raises(AuthError):
        A.authenticate(db, "user@example.com", "wrongpassword")
    db.commit()
    A.authenticate(db, "user@example.com", "hunter2pass")
    db.commit()
    assert verified_account.failed_login_count == 0


def test_login_hides_email_existence_when_configured(db, verified_account, monkeypatch):
    """
    With REVEAL_ACCOUNT_EXISTENCE off, an unknown email and a wrong password
    must be indistinguishable, so the endpoint cannot enumerate accounts.
    """
    monkeypatch.setattr(A, "_REVEAL_ACCOUNT_EXISTENCE", False)
    with pytest.raises(AuthError) as unknown:
        A.authenticate(db, "nobody@example.com", "somepassword")
    with pytest.raises(AuthError) as wrong_pw:
        A.authenticate(db, "user@example.com", "wrongpassword")
    assert unknown.value.message == wrong_pw.value.message
    assert unknown.value.code == wrong_pw.value.code


def test_login_reports_missing_account_when_configured(db, verified_account, monkeypatch):
    """
    Default mode: tell the user no account exists, because silently failing
    leaves people stuck. A wrong password must still NOT confirm the account
    exists any more specifically than the generic message.
    """
    monkeypatch.setattr(A, "_REVEAL_ACCOUNT_EXISTENCE", True)

    with pytest.raises(AuthError) as unknown:
        A.authenticate(db, "nobody@example.com", "somepassword")
    assert unknown.value.code == "no_account"
    assert "no account" in unknown.value.message.lower()

    with pytest.raises(AuthError) as wrong_pw:
        A.authenticate(db, "user@example.com", "wrongpassword")
    assert wrong_pw.value.code == "invalid_credentials"
    assert "no account" not in wrong_pw.value.message.lower()


def test_wrong_password_still_counts_toward_lockout_in_reveal_mode(
    db, verified_account, monkeypatch
):
    """Revealing existence must not weaken brute-force protection."""
    monkeypatch.setattr(A, "_REVEAL_ACCOUNT_EXISTENCE", True)
    for _ in range(A.MAX_FAILED_LOGINS):
        with pytest.raises(AuthError):
            A.authenticate(db, "user@example.com", "wrongpassword")
    db.commit()
    with pytest.raises(AuthError) as exc:
        A.authenticate(db, "user@example.com", "hunter2pass")
    assert exc.value.code == "locked"


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def test_token_contains_no_sensitive_data(db, verified_account):
    payload = A.decode_token(A.create_token(verified_account))
    assert payload is not None
    assert "email" not in payload
    assert "password" not in payload
    assert "password_hash" not in payload


def test_tampered_token_rejected(db, verified_account):
    token = A.create_token(verified_account)
    assert A.decode_token(token[:-4] + "AAAA") is None


def test_malformed_token_rejected():
    assert A.decode_token("garbage.token.here") is None
    assert A.decode_token("") is None


def test_expired_token_rejected(db, verified_account, monkeypatch):
    monkeypatch.setattr(A, "_TOKEN_TTL_HOURS", -1)  # already expired
    assert A.decode_token(A.create_token(verified_account)) is None


def test_logout_revokes_existing_tokens(db, verified_account):
    """token_version is what makes stateless JWTs revocable."""
    token = A.create_token(verified_account)
    before = A.decode_token(token)
    A.bump_token_version(db, verified_account)
    db.commit()
    # The token still decodes, but its version no longer matches the account,
    # which is what get_current_account checks.
    assert before["tv"] != verified_account.token_version


def test_password_reset_revokes_all_sessions(db, verified_account):
    acct, code = A.issue_reset_code(db, "user@example.com")
    db.commit()
    before = verified_account.token_version
    assert A.reset_password(db, "user@example.com", code, "brandnewpass1") is not None
    db.commit()
    assert verified_account.token_version > before


def test_old_password_stops_working_after_reset(db, verified_account):
    acct, code = A.issue_reset_code(db, "user@example.com")
    db.commit()
    A.reset_password(db, "user@example.com", code, "brandnewpass1")
    db.commit()
    assert A.authenticate(db, "user@example.com", "brandnewpass1") is not None
    with pytest.raises(AuthError):
        A.authenticate(db, "user@example.com", "hunter2pass")


# ---------------------------------------------------------------------------
# Data model: profiles belong to accounts
# ---------------------------------------------------------------------------


def test_profile_is_linked_to_account_and_persists(db, verified_account):
    profile = PatientProfile(
        account_id=verified_account.id,
        label="Myself",
        condition="NSCLC KRAS G12C",
        location="New York, NY",
        treatment_history="carboplatin",
        medications=["metformin"],
        biomarkers=["KRAS G12C+"],
    )
    db.add(profile)
    db.commit()

    reloaded = db.get(Account, verified_account.id)
    assert len(reloaded.profiles) == 1
    saved = reloaded.profiles[0]
    assert saved.account_id == verified_account.id
    assert saved.medications == ["metformin"]
    assert saved.biomarkers == ["KRAS G12C+"]


def test_deleting_account_cascades_to_profiles(db, verified_account):
    db.add(
        PatientProfile(
            account_id=verified_account.id,
            label="Mom",
            condition="breast cancer",
            location="Boston, MA",
            treatment_history="none",
            medications=["none"],
        )
    )
    db.commit()
    db.delete(verified_account)
    db.commit()
    assert db.query(PatientProfile).count() == 0
