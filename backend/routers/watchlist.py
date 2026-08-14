"""
Watchlist endpoints (saving/listing/removing require auth; the check sweep is
guarded by an optional cron token).

  POST   /api/watchlist                   — save a trial to one of your profiles
  GET    /api/watchlist?profile_id=...     — list a profile's watched trials
  DELETE /api/watchlist/{id}               — remove a watched trial you own
  POST   /api/watchlist/check              — run the change-detection sweep
                                             (nightly job; guarded by CRON_TOKEN)
"""

import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from datetime import datetime

from pydantic import BaseModel, Field

from db.database import get_db
from db.models import Account
from models.watchlist import (
    CheckSummary,
    WatchedTrialOut,
    WatchlistOut,
    WatchRequest,
)
from routers.security import get_verified_account
from services import profile_service, watchlist_service

VALID_ENROLLMENT_STATUSES = {
    "interested",
    "contacted",
    "waiting",
    "screened",
    "enrolled",
    "withdrawn",
    "declined",
}


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="One of: interested, contacted, waiting, screened, enrolled, withdrawn, declined")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.post("", response_model=WatchedTrialOut, status_code=201)
def add_to_watchlist(
    body: WatchRequest,
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    # Ensure the target profile belongs to the authenticated account.
    profile = profile_service.get_owned_profile(db, account.id, body.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    watch = watchlist_service.add_watch(
        db,
        profile_id=profile.id,
        nct_id=body.nct_id,
        title=body.title,
        source_url=body.source_url,
    )
    db.commit()
    db.refresh(watch)
    return watch


@router.get("", response_model=WatchlistOut)
def get_watchlist(
    profile_id: int = Query(..., description="Profile whose watchlist to fetch"),
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    profile = profile_service.get_owned_profile(db, account.id, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    trials = watchlist_service.list_watches(db, profile_id)
    return WatchlistOut(
        profile_id=profile_id,
        trials=[WatchedTrialOut.model_validate(t) for t in trials],
    )


@router.delete("/{watch_id}", status_code=204)
def delete_from_watchlist(
    watch_id: int,
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    watch = watchlist_service.get_owned_watch(db, account.id, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Watched trial not found")
    db.delete(watch)
    db.commit()
    return None


@router.put("/{watch_id}/status", response_model=WatchedTrialOut)
def update_enrollment_status(
    watch_id: int,
    body: StatusUpdateRequest,
    account: Account = Depends(get_verified_account),
    db: Session = Depends(get_db),
):
    """Log the patient's enrollment progress: interested → contacted → … → enrolled."""
    new_status = body.status.lower().strip()
    if new_status not in VALID_ENROLLMENT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(VALID_ENROLLMENT_STATUSES)}",
        )
    watch = watchlist_service.get_owned_watch(db, account.id, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Watched trial not found")
    if watch.enrollment_status != new_status:
        watch.enrollment_status = new_status
        watch.enrollment_changed_at = datetime.utcnow()
        db.commit()
        db.refresh(watch)
    return watch


@router.post("/check", response_model=CheckSummary)
def run_watchlist_check(
    request: Request,
    send_email: bool = Query(True),
    x_cron_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Trigger the change-detection sweep across all accounts.

    This endpoint touches every account and can send email, so it FAILS CLOSED:
    without CRON_TOKEN configured it is disabled entirely. Previously an unset
    token left it wide open, which would let anyone on the internet trigger a
    mass mailing.
    """
    import hmac

    expected = os.getenv("CRON_TOKEN", "").strip()
    ip = request.client.host if request.client else "unknown"

    if not expected:
        logger.error(
            "watchlist.check_blocked reason=cron_token_not_configured ip=%s", ip
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "This endpoint is disabled because CRON_TOKEN is not configured. "
                "Set CRON_TOKEN in the environment to enable scheduled runs."
            ),
        )

    # Constant-time comparison so the token cannot be recovered by timing.
    if not x_cron_token or not hmac.compare_digest(x_cron_token, expected):
        logger.warning("watchlist.check_denied reason=bad_cron_token ip=%s", ip)
        raise HTTPException(status_code=401, detail="Invalid or missing cron token")

    logger.info("watchlist.check_started ip=%s send_email=%s", ip, send_email)
    from services import alert_service

    return alert_service.run_check(db, send_email=send_email)
