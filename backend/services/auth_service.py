"""
Authentication: password hashing (bcrypt) and JWT issue/verify.

Tokens are signed with JWT_SECRET (HS256). Set a strong JWT_SECRET in the
environment for production; a dev fallback is used with a loud warning if
it's missing so local dev still works.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Account

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_TOKEN_TTL_DAYS = int(os.getenv("JWT_TTL_DAYS", "7"))


def _secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        logger.warning(
            "JWT_SECRET not set — using an insecure dev default. "
            "Set JWT_SECRET in your environment before deploying. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
        # Must be >= 32 bytes for HS256 to satisfy RFC 7518; the previous
        # 28-char fallback triggered PyJWT's InsecureKeyLengthWarning.
        return "dev-insecure-secret-change-me-before-production-deployment-now"
    if len(secret.encode("utf-8")) < 32:
        logger.warning(
            "JWT_SECRET is shorter than 32 bytes — RFC 7518 recommends >= 32 "
            "bytes for HS256. Increase its length."
        )
    return secret


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def create_token(account: Account) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account.id),
        "email": account.email,
        "iat": now,
        "exp": now + timedelta(days=_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        logger.info("Token decode failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Account operations
# ---------------------------------------------------------------------------


def get_by_email(db: Session, email: str) -> Optional[Account]:
    return db.execute(
        select(Account).where(Account.email == email.strip().lower())
    ).scalar_one_or_none()


def register(db: Session, email: str, password: str) -> Account:
    """Create a new account. Raises ValueError if the email is already taken."""
    email = email.strip().lower()
    if get_by_email(db, email) is not None:
        raise ValueError("An account with this email already exists.")
    account = Account(email=email, password_hash=hash_password(password))
    db.add(account)
    db.flush()
    return account


def authenticate(db: Session, email: str, password: str) -> Optional[Account]:
    """Return the account if credentials are valid, else None."""
    account = get_by_email(db, email)
    if account is None or not verify_password(password, account.password_hash):
        return None
    return account


def get_account_by_id(db: Session, account_id: int) -> Optional[Account]:
    return db.get(Account, account_id)
