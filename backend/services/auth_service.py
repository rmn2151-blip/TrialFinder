"""
Authentication service.

Security properties this module is responsible for:
  - Passwords hashed with bcrypt, never stored or logged in plaintext.
  - Verification and password-reset codes stored hashed, with expiry.
  - Constant-time comparison for all secret material.
  - Server-side token revocation via a per-account token_version.
  - Account lockout after repeated failed logins.
  - No secret (JWT signing key, code, hash) ever leaves this process.
"""

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Account

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"

# Short-lived access tokens limit the damage window if one is stolen.
_TOKEN_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "12"))

# Codes expire so an old email cannot be replayed indefinitely.
VERIFICATION_TTL_MINUTES = int(os.getenv("VERIFICATION_TTL_MINUTES", "30"))
RESET_TTL_MINUTES = int(os.getenv("RESET_TTL_MINUTES", "30"))

# Lockout policy.
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))


class AuthError(Exception):
    """Raised for auth failures that the router should translate to HTTP."""

    def __init__(self, message: str, *, code: str = "invalid_credentials"):
        super().__init__(message)
        self.message = message
        self.code = code


def _secret() -> str:
    """
    JWT signing key. Refuses to start with a default in production so a
    deployment can never accidentally sign tokens with a public value.
    """
    secret = os.getenv("JWT_SECRET", "").strip()
    is_prod = os.getenv("ENVIRONMENT", "development").lower() in {
        "production",
        "prod",
        "staging",
    }

    if not secret:
        if is_prod:
            raise RuntimeError(
                "JWT_SECRET must be set in production. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        logger.warning(
            "JWT_SECRET not set. Using an insecure development default. "
            "Set JWT_SECRET before deploying."
        )
        return "dev-insecure-secret-change-me-before-production-deployment-now"

    if len(secret.encode("utf-8")) < 32:
        msg = "JWT_SECRET is shorter than the 32 bytes RFC 7518 recommends for HS256."
        if is_prod:
            raise RuntimeError(msg)
        logger.warning(msg)

    return secret


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

# bcrypt silently truncates at 72 bytes, so reject longer input rather than
# letting two different passwords authenticate the same account.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise AuthError(
            "Password is too long. Please use 72 bytes or fewer.",
            code="password_too_long",
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# One-time codes
# ---------------------------------------------------------------------------


def _new_code() -> str:
    """Cryptographically random six-digit code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_code(code: str) -> str:
    """
    Codes are short and high-entropy-limited, so we use SHA-256 rather than
    bcrypt: it is fast enough to avoid a DoS vector while still meaning a
    database dump contains no directly usable codes.
    """
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _codes_match(candidate: str, stored_hash: Optional[str]) -> bool:
    """Constant-time comparison so we do not leak the code via timing."""
    if not stored_hash:
        return False
    return hmac.compare_digest(_hash_code(candidate), stored_hash)


def _expired(sent_at: Optional[datetime], ttl_minutes: int) -> bool:
    if sent_at is None:
        return True
    return datetime.utcnow() - sent_at > timedelta(minutes=ttl_minutes)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def create_token(account: Account) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account.id),
        # token_version lets us revoke every existing token for an account.
        "tv": int(account.token_version or 0),
        "iat": now,
        "exp": now + timedelta(hours=_TOKEN_TTL_HOURS),
        "iss": "trialfinder",
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            _secret(),
            algorithms=[_ALGORITHM],  # pinned: never trust the header's alg
            issuer="trialfinder",
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.info("Token rejected: %s", exc)
        return None


def bump_token_version(db: Session, account: Account) -> None:
    """Invalidate every token previously issued for this account."""
    account.token_version = int(account.token_version or 0) + 1
    db.flush()


# ---------------------------------------------------------------------------
# Account lookup
# ---------------------------------------------------------------------------


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> Optional[Account]:
    return db.execute(
        select(Account).where(Account.email == normalize_email(email))
    ).scalar_one_or_none()


def get_account_by_id(db: Session, account_id: int) -> Optional[Account]:
    return db.get(Account, account_id)


# ---------------------------------------------------------------------------
# Registration and verification
# ---------------------------------------------------------------------------


def register(db: Session, email: str, password: str) -> tuple[Account, str]:
    """
    Create an account. Returns (account, plaintext_verification_code).
    The plaintext code is returned once so the caller can email it; it is
    never persisted in readable form.
    """
    email = normalize_email(email)
    if get_by_email(db, email) is not None:
        raise AuthError(
            "You already have an account with this email. Please log in instead.",
            code="email_taken",
        )

    code = _new_code()
    account = Account(
        email=email,
        password_hash=hash_password(password),
        email_verified=0,
        verification_code_hash=_hash_code(code),
        verification_sent_at=datetime.utcnow(),
        failed_login_count=0,
        token_version=0,
    )
    db.add(account)
    db.flush()
    return account, code


def verify_code(db: Session, email: str, code: str) -> Optional[Account]:
    """Mark verified when the code matches and has not expired."""
    account = get_by_email(db, email)
    if account is None or not account.verification_code_hash:
        return None
    if _expired(account.verification_sent_at, VERIFICATION_TTL_MINUTES):
        logger.info("Expired verification code used for account id=%s", account.id)
        return None
    if not _codes_match(code, account.verification_code_hash):
        return None

    account.email_verified = 1
    account.verification_code_hash = None
    account.verification_sent_at = None
    db.flush()
    return account


def issue_new_code(db: Session, email: str) -> tuple[Optional[Account], Optional[str]]:
    """Rotate the verification code. Returns (account, plaintext_code)."""
    account = get_by_email(db, email)
    if account is None:
        return None, None
    code = _new_code()
    account.verification_code_hash = _hash_code(code)
    account.verification_sent_at = datetime.utcnow()
    db.flush()
    return account, code


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def _is_locked(account: Account) -> bool:
    return bool(account.locked_until and account.locked_until > datetime.utcnow())


# Whether to tell users that no account exists for an email.
#
# Tradeoff, stated plainly: revealing this is friendlier (people genuinely get
# stuck not knowing which address they signed up with), but it lets an
# attacker enumerate registered emails. For a consumer health tool the
# usability win is worth it, and the real protection is the rate limiting and
# lockout below. Set REVEAL_ACCOUNT_EXISTENCE=false to switch to uniform
# responses if you later decide otherwise.
_REVEAL_ACCOUNT_EXISTENCE = (
    os.getenv("REVEAL_ACCOUNT_EXISTENCE", "true").lower() == "true"
)


def reveals_account_existence() -> bool:
    """Whether endpoints may state that no account exists for an email."""
    return _REVEAL_ACCOUNT_EXISTENCE


def authenticate(db: Session, email: str, password: str) -> Account:
    """
    Validate credentials.

    Raises AuthError. When REVEAL_ACCOUNT_EXISTENCE is on, an unknown email
    gets a distinct, more helpful message than a wrong password.
    """
    generic = AuthError("Invalid email or password", code="invalid_credentials")
    account = get_by_email(db, email)

    if account is None:
        # Spend roughly the same time as a real bcrypt check so response
        # timing does not reveal whether the account exists.
        bcrypt.checkpw(b"timing-equalizer", bcrypt.hashpw(b"x", bcrypt.gensalt(rounds=12)))
        if _REVEAL_ACCOUNT_EXISTENCE:
            raise AuthError(
                "No account found with that email address. "
                "Please check the spelling, or create an account.",
                code="no_account",
            )
        raise generic

    if _is_locked(account):
        remaining = int((account.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
        logger.warning(
            "Login attempt on locked account id=%s. %d minute(s) remaining.",
            account.id,
            remaining,
        )
        raise AuthError(
            f"Too many failed attempts. Try again in {remaining} minute(s).",
            code="locked",
        )

    if not verify_password(password, account.password_hash):
        account.failed_login_count = int(account.failed_login_count or 0) + 1
        if account.failed_login_count >= MAX_FAILED_LOGINS:
            account.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            account.failed_login_count = 0
            logger.warning(
                "Account id=%s locked for %d minutes after %d failed logins.",
                account.id,
                LOCKOUT_MINUTES,
                MAX_FAILED_LOGINS,
            )
        db.flush()
        raise generic

    # Success: clear the failure counters.
    account.failed_login_count = 0
    account.locked_until = None
    db.flush()
    return account


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def issue_reset_code(db: Session, email: str) -> tuple[Optional[Account], Optional[str]]:
    """Generate a reset code. Returns (account, plaintext_code)."""
    account = get_by_email(db, email)
    if account is None:
        return None, None
    code = _new_code()
    account.reset_code_hash = _hash_code(code)
    account.reset_sent_at = datetime.utcnow()
    db.flush()
    return account, code


def reset_password(
    db: Session, email: str, code: str, new_password: str
) -> Optional[Account]:
    """
    Verify the reset code and set a new password.

    On success every existing session is revoked, because a password reset
    is exactly the moment you want any attacker-held token to stop working.
    """
    account = get_by_email(db, email)
    if account is None or not account.reset_code_hash:
        return None
    if _expired(account.reset_sent_at, RESET_TTL_MINUTES):
        logger.info("Expired reset code used for account id=%s", account.id)
        return None
    if not _codes_match(code, account.reset_code_hash):
        return None

    account.password_hash = hash_password(new_password)
    account.reset_code_hash = None
    account.reset_sent_at = None
    account.failed_login_count = 0
    account.locked_until = None
    bump_token_version(db, account)
    db.flush()
    logger.info("Password reset completed for account id=%s", account.id)
    return account
