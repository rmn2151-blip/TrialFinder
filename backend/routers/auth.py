"""
Authentication endpoints.

  POST /api/auth/register  — create an account, returns a JWT
  POST /api/auth/login     — exchange credentials for a JWT
  GET  /api/auth/me        — current account (requires Bearer token)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Account
from models.auth import AccountOut, LoginRequest, RegisterRequest, TokenResponse
from routers.security import get_current_account
from services import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        account = auth_service.register(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()
    db.refresh(account)
    token = auth_service.create_token(account)
    logger.info("Registered account %s", account.email)
    return TokenResponse(access_token=token, account=AccountOut.model_validate(account))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    account = auth_service.authenticate(db, body.email, body.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth_service.create_token(account)
    return TokenResponse(access_token=token, account=AccountOut.model_validate(account))


@router.get("/me", response_model=AccountOut)
def me(account: Account = Depends(get_current_account)):
    return account
