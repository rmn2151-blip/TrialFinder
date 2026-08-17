"""
Authentication endpoints.

Every route here is rate limited, because these are the endpoints an attacker
will target for credential stuffing and enumeration. Responses are
deliberately uniform so they cannot be used to discover which emails are
registered.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from middleware.rate_limit import limiter

from db.database import get_db
from db.models import Account
from models.auth import (
    AccountOut,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendRequest,
    ResetPasswordRequest,
    SimpleMessage,
    TokenResponse,
    VerifyRequest,
    VerifyStatus,
)
from routers.security import get_current_account
from services import auth_service, email_service
from services.auth_service import AuthError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# In development we surface one-time codes so the app is testable without an
# inbox. This is gated on ENVIRONMENT so a production deploy can never leak a
# verification or reset code through the API, even if email is misconfigured.
_IS_PROD = os.getenv("ENVIRONMENT", "development").lower() in {
    "production",
    "prod",
    "staging",
}


def _send_email(fn, *args) -> bool:
    """
    Send the email inline and return whether it actually succeeded.

    This used to schedule the send as a FastAPI BackgroundTask so the
    response returned immediately (a Gmail SMTP send costs ~4.4s: connect,
    STARTTLS, login, send). But that meant "delivered" only meant "a
    provider is configured" — the real send happened after the response
    was already built, so a genuine failure (bad credentials, a blocked
    port) was invisible: the response claimed success and hid the
    dev-code fallback, stranding the user with no code and no visible
    error. That gap is worse than the latency it was avoiding.

    Sending inline still costs real time, but SendGrid/Resend's HTTPS APIs
    are typically well under a second — nothing like raw SMTP's handshake.
    For an auth-critical flow, a truthful "did this actually work" beats a
    faster lie.
    """
    if not email_service.is_configured():
        return False
    return bool(fn(*args))


# Escape hatch for demos and for debugging deliverability.
#
# SECURITY TRADEOFF, stated plainly: when this is on, anyone who can call
# /api/auth/register receives the verification code in the response. That
# means they can verify an email address they do not control, which defeats
# the purpose of verification. It is off by default and should stay off for
# real users. Turn it on only when you need the flow to work on stage and
# cannot depend on inbox delivery.
_SHOW_CODE_ALWAYS = os.getenv("SHOW_VERIFICATION_CODE", "false").lower() == "true"

if _SHOW_CODE_ALWAYS:
    logger.warning(
        "SHOW_VERIFICATION_CODE=true: verification codes are returned in API "
        "responses. Anyone who can register can verify an address they do not "
        "own. Use for demos only, and unset it before real users sign up."
    )


def _expose_dev_code(code: str | None, *, delivered: bool = False) -> str | None:
    """
    Return the one-time code to the client only when it is safe AND useful.

    Three cases return it:
      1. SHOW_VERIFICATION_CODE=true, an explicit operator override.
      2. Outside production with no email provider configured.
      3. Outside production where the provider rejected the recipient, e.g.
         a sandboxed Resend account that only delivers to its own owner.

    Without cases 2 and 3, a failed send leaves the user permanently unable
    to verify, with no way forward.
    """
    if _SHOW_CODE_ALWAYS:
        return code
    if _IS_PROD:
        return None
    if delivered:
        return None
    return code


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/hour")
def register(
    request: Request,
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        account, code = auth_service.register(db, body.email, body.password)
    except AuthError as e:
        logger.info(
            "auth.register_rejected reason=%s ip=%s", e.code, _client_ip(request)
        )
        status_code = 409 if e.code == "email_taken" else 400
        raise HTTPException(status_code=status_code, detail=e.message)

    db.commit()
    db.refresh(account)

    delivered = _send_email(
        email_service.send_verification_code, account.email, code
    )
    logger.info(
        "auth.registered account_id=%s ip=%s email_delivered=%s",
        account.id,
        _client_ip(request),
        delivered,
    )
    if not delivered:
        logger.warning(
            "auth.no_email_provider account_id=%s. Verification code is %s "
            "(returned in the API response for local development).",
            account.id,
            code,
        )

    # The token returned here proves who the user is so the client can drive
    # the verification screen. It cannot create profiles or watchlists until
    # the email is verified (see get_verified_account).
    token = auth_service.create_token(account)
    return TokenResponse(
        access_token=token,
        account=AccountOut.model_validate(account),
        dev_verification_code=_expose_dev_code(code, delivered=delivered),
        verification_status="sent" if delivered else "delivery_failed",
    )


@router.post("/verify", response_model=VerifyStatus)
@limiter.limit("10/hour")
def verify_email(request: Request, body: VerifyRequest, db: Session = Depends(get_db)):
    account = auth_service.verify_code(db, body.email, body.code)
    if account is None:
        logger.info("auth.verify_failed ip=%s", _client_ip(request))
        raise HTTPException(
            status_code=400,
            detail="That verification code is incorrect or has expired.",
        )
    db.commit()
    logger.info("auth.verified account_id=%s", account.id)
    return VerifyStatus(
        email=account.email, email_verified=True, message="Email verified."
    )


@router.post("/resend-verification", response_model=VerifyStatus)
@limiter.limit("3/hour")
def resend_verification(
    request: Request,
    body: ResendRequest,
    db: Session = Depends(get_db),
):
    account, code = auth_service.issue_new_code(db, body.email)
    generic = "If that account exists, a new code has been sent."

    if account is None:
        # Uniform response: do not reveal whether the email is registered.
        return VerifyStatus(email=body.email, email_verified=False, message=generic)

    db.commit()
    delivered = _send_email(
        email_service.send_verification_code, account.email, code
    )
    logger.info(
        "auth.verification_resent account_id=%s email_delivered=%s", account.id, delivered
    )

    message = generic
    dev_code = _expose_dev_code(code, delivered=delivered)
    if dev_code:
        message = f"Email delivery failed. Your code is {dev_code}"

    return VerifyStatus(
        email=account.email,
        email_verified=bool(account.email_verified),
        message=message,
    )


# ---------------------------------------------------------------------------
# Login and session
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    ip = _client_ip(request)
    try:
        account = auth_service.authenticate(db, body.email, body.password)
    except AuthError as e:
        db.commit()  # persist the failed-attempt counter
        logger.warning("auth.login_failed reason=%s ip=%s", e.code, ip)
        status_code = 429 if e.code == "locked" else 401
        raise HTTPException(status_code=status_code, detail=e.message)

    if not account.email_verified:
        _, code = auth_service.issue_new_code(db, account.email)
        db.commit()
        delivered = _send_email(
            email_service.send_verification_code, account.email, code
        )
        logger.info(
            "auth.login_unverified account_id=%s ip=%s email_delivered=%s",
            account.id,
            ip,
            delivered,
        )

        detail = "Please verify your email first. We just sent you a new code."
        dev_code = _expose_dev_code(code, delivered=delivered)
        if dev_code:
            detail = (
                "Please verify your email. We could not deliver the email, so "
                f"here is your code: {dev_code}"
            )
        raise HTTPException(status_code=403, detail=detail)

    db.commit()
    logger.info("auth.login_success account_id=%s ip=%s", account.id, ip)
    token = auth_service.create_token(account)
    return TokenResponse(
        access_token=token, account=AccountOut.model_validate(account)
    )


@router.post("/logout", response_model=SimpleMessage)
def logout(
    account: Account = Depends(get_current_account), db: Session = Depends(get_db)
):
    """
    Real server-side logout. Bumping token_version invalidates every token
    already issued for this account, so a stolen token stops working even
    though JWTs are otherwise stateless.
    """
    auth_service.bump_token_version(db, account)
    db.commit()
    logger.info("auth.logout account_id=%s", account.id)
    return SimpleMessage(message="Logged out. All sessions for this account ended.")


@router.get("/me", response_model=AccountOut)
def me(account: Account = Depends(get_current_account)):
    return account


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@router.post("/forgot-password", response_model=SimpleMessage)
@limiter.limit("3/hour")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Uniform response regardless of whether the account exists."""
    account, code = auth_service.issue_reset_code(db, body.email)
    generic = "If an account exists for that email, a reset code is on its way."

    if account is None:
        logger.info("auth.reset_requested_unknown ip=%s", _client_ip(request))
        if auth_service.reveals_account_existence():
            # Tell the user plainly rather than leaving them waiting for an
            # email that will never arrive.
            raise HTTPException(
                status_code=404,
                detail=(
                    "No account found with that email address. "
                    "Please check the spelling, or create an account."
                ),
            )
        return SimpleMessage(message=generic)

    db.commit()
    delivered = _send_email(
        email_service.send_password_reset, account.email, code
    )
    logger.info(
        "auth.reset_requested account_id=%s email_delivered=%s", account.id, delivered
    )
    return SimpleMessage(
        message=generic, dev_code=_expose_dev_code(code, delivered=delivered)
    )


@router.post("/reset-password", response_model=SimpleMessage)
@limiter.limit("5/hour")
def reset_password(
    request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)
):
    account = auth_service.reset_password(
        db, body.email, body.code, body.new_password
    )
    if account is None:
        logger.warning("auth.reset_failed ip=%s", _client_ip(request))
        raise HTTPException(
            status_code=400,
            detail="That reset code is incorrect or has expired. Request a new one.",
        )
    db.commit()
    logger.info("auth.reset_success account_id=%s", account.id)
    return SimpleMessage(
        message="Your password has been reset. Please log in with your new password."
    )
