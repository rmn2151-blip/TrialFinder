"""Pydantic schemas for authentication."""

from datetime import datetime
from typing import Optional

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
    email_verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account: AccountOut
    # Only populated in dev when no email service is configured. Lets the
    # frontend display the verification code so the user does not need email.
    dev_verification_code: Optional[str] = None
    verification_status: str = "pending"  # "pending" | "auto_verified" | "sent"


class VerifyRequest(BaseModel):
    email: str = Field(..., pattern=_EMAIL_RE)
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendRequest(BaseModel):
    email: str = Field(..., pattern=_EMAIL_RE)


class VerifyStatus(BaseModel):
    email: str
    email_verified: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., pattern=_EMAIL_RE)


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., pattern=_EMAIL_RE)
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(..., min_length=8, max_length=128)


class SimpleMessage(BaseModel):
    message: str
    # Dev only: surfaced when no email provider is configured.
    dev_code: Optional[str] = None
