"""
Shared auth dependency: resolves the current Account from a Bearer JWT.

Usage in a route:
    account: Account = Depends(get_current_account)
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Account
from services import auth_service

_bearer = HTTPBearer(auto_error=False)

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_account(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Account:
    if creds is None or not creds.credentials:
        raise _UNAUTH
    payload = auth_service.decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise _UNAUTH
    try:
        account_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise _UNAUTH
    account = auth_service.get_account_by_id(db, account_id)
    if account is None:
        raise _UNAUTH
    return account
