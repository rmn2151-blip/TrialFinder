"""
Trial alert endpoints.

  GET    /api/alerts                  — your alerts (newest first)
  GET    /api/alerts/unread-count     — badge count
  POST   /api/alerts/{id}/read        — mark one read
  POST   /api/alerts/read-all         — mark all read
  GET    /api/alerts/preferences      — email alert on/off
  PUT    /api/alerts/preferences      — update it
  GET    /api/alerts/unsubscribe      — one-click unsubscribe from an email

Every authenticated route is scoped to the caller's account. The unsubscribe
route is intentionally unauthenticated because it is opened from an email
client, but it only accepts a high-entropy token and can only ever disable
alerts, never read data or change anything else.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Account
from middleware.rate_limit import limiter
from routers.security import get_verified_account
from services import alert_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: int
    nct_id: str
    trial_title: str
    profile_label: Optional[str] = None
    source_url: Optional[str] = None
    change_type: str
    description: str
    severity: str
    created_at: datetime
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertListOut(BaseModel):
    alerts: list[AlertOut]
    unread_count: int


class UnreadCountOut(BaseModel):
    unread_count: int


class PreferencesOut(BaseModel):
    email_alerts_enabled: bool


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_alerts_enabled: bool


@router.get("", response_model=AlertListOut)
def list_alerts(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    alerts = alert_service.list_alerts(
        db, account.id, unread_only=unread_only, limit=limit
    )
    return AlertListOut(
        alerts=[AlertOut.model_validate(a) for a in alerts],
        unread_count=alert_service.count_unread(db, account.id),
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    return UnreadCountOut(unread_count=alert_service.count_unread(db, account.id))


@router.post("/{alert_id}/read", response_model=UnreadCountOut)
def mark_read(
    alert_id: int,
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    # Ownership is enforced inside the service: an alert belonging to another
    # account returns 404 rather than confirming it exists.
    if not alert_service.mark_read(db, account.id, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    db.commit()
    return UnreadCountOut(unread_count=alert_service.count_unread(db, account.id))


@router.post("/read-all", response_model=UnreadCountOut)
def mark_all_read(
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    alert_service.mark_all_read(db, account.id)
    db.commit()
    return UnreadCountOut(unread_count=0)


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(account: Account = Depends(get_verified_account)):
    return PreferencesOut(email_alerts_enabled=bool(account.email_alerts_enabled))


@router.put("/preferences", response_model=PreferencesOut)
def update_preferences(
    body: PreferencesUpdate,
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    account.email_alerts_enabled = 1 if body.email_alerts_enabled else 0
    db.commit()
    logger.info(
        "alert.preferences_updated account_id=%s email_alerts=%s",
        account.id,
        bool(account.email_alerts_enabled),
    )
    return PreferencesOut(email_alerts_enabled=bool(account.email_alerts_enabled))


@router.get("/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/hour")
def unsubscribe(
    request: Request,
    token: str = Query(..., min_length=16, max_length=128),
    db: Session = Depends(get_db),
):
    """
    One-click unsubscribe from a link in an email.

    No login required, by design: mail clients cannot authenticate. The token
    is high-entropy and grants exactly one capability, turning alerts off.
    Returns HTML because a person is looking at it in a browser.
    """
    account = alert_service.unsubscribe_by_token(db, token)
    if account is None:
        logger.info("alert.unsubscribe_bad_token")
        return HTMLResponse(
            _page(
                "Link not recognized",
                "This unsubscribe link is invalid or has already been used. "
                "You can manage alerts from your account settings.",
            ),
            status_code=404,
        )

    db.commit()
    return HTMLResponse(
        _page(
            "You're unsubscribed",
            "You will no longer receive email alerts about your saved trials. "
            "Your saved trials are untouched, and updates still appear in the "
            "app whenever you log in.",
        )
    )


def _page(heading: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{heading} - TrialFinder</title></head>
<body style="font-family:system-ui,-apple-system,Arial,sans-serif;background:#f6f8fb;
             margin:0;padding:48px 16px;color:#14202e;">
  <div style="max-width:460px;margin:0 auto;background:#fff;border:1px solid #e3e9f0;
              border-radius:14px;padding:32px;text-align:center;">
    <h1 style="font-size:20px;margin:0 0 12px;">{heading}</h1>
    <p style="color:#4a5a6a;line-height:1.6;margin:0;">{body}</p>
  </div>
</body></html>"""
