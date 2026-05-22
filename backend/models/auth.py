"""Pydantic schemas for authentication."""

from datetime import datetime

from pydantic import BaseModel, Field

_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    email: str = Field(..., pattern=_EMAIL_RE)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., pattern=_EMAIL_RE)
    password: str = Field(..., min_length=1, max_length=128)


class AccountOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account: AccountOut
