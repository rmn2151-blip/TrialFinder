"""
Shared auth dependencies.

    get_current_account          - valid token required
    get_verified_account         - valid token AND a verified email

Any route that reads or writes user-owned data must depend on one of these,
and must additionally scope its query by account_id. Never trust an ID from
the request body or path without an ownership check.
"""

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Account
from services import auth_service

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(reason: str, request: Request) -> HTTPException:
    # Log the reason server-side; return a generic message to the client so we
    # do not tell an attacker which part of the check failed.
    logger.info(
        "auth.denied reason=%s path=%s ip=%s",
        reason,
        request.url.path,
        request.client.host if request.client else "unknown",
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_account(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Account:
    if creds is None or not creds.credentials:
        raise _unauthorized("missing_token", request)

    payload = auth_service.decode_token(creds.credentials)
    if not payload:
        raise _unauthorized("bad_token", request)

    sub = payload.get("sub")
    try:
        account_id = int(sub)
    except (TypeError, ValueError):
        raise _unauthorized("bad_subject", request)

    account = auth_service.get_account_by_id(db, account_id)
    if account is None:
        raise _unauthorized("account_missing", request)

    # Server-side revocation: tokens issued before a logout, password reset,
    # or forced logout carry a stale version and are rejected here.
    if int(payload.get("tv", -1)) != int(account.token_version or 0):
        raise _unauthorized("token_revoked", request)

    return account


def get_verified_account(
    request: Request,
    account: Account = Depends(get_current_account),
) -> Account:
    """
    Use this for anything that stores user data. Registration hands out a
    token immediately so the client can drive the verification screen, but
    that token must not be able to create profiles or watchlists until the
    email is confirmed.
    """
    if not account.email_verified:
        logger.info(
            "auth.unverified_blocked account_id=%s path=%s",
            account.id,
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address to continue.",
        )
    return account
