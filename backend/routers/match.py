"""
POST /api/match  — main trial matching endpoint
GET  /api/health — liveness probe for frontend + deployment checks

/api/match is the most expensive endpoint in the app: it hits
ClinicalTrials.gov and then runs an LLM ranking pass. It is protected by a
per-IP rate limit, a per-identity daily AI quota, and bot heuristics.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.database import get_db
from middleware.abuse import block_automated_clients, enforce_ai_quota
from middleware.rate_limit import limiter
from models.patient import PatientProfile
from models.trial import MatchResponse
from services import auth_service
from services.matching_service import find_matching_trials

logger = logging.getLogger(__name__)

router = APIRouter()

# Search stays usable without an account, so this reads the token if one is
# present but never requires it. A logged-in user gets the larger AI quota.
_optional_bearer = HTTPBearer(auto_error=False)


def _optional_account_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> int | None:
    if creds is None or not creds.credentials:
        return None
    payload = auth_service.decode_token(creds.credentials)
    if not payload:
        return None
    try:
        account_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    account = auth_service.get_account_by_id(db, account_id)
    if account is None:
        return None
    if int(payload.get("tv", -1)) != int(account.token_version or 0):
        return None
    return account.id


@router.get("/api/health")
async def health_check():
    """
    Liveness check. No auth, no cost, no user data.

    Deliberately returns 200 even when a subsystem is degraded, so the
    platform healthcheck passes and the domain stays reachable. The body
    reports what is actually wrong, which beats a 404 with no explanation.
    """
    try:
        import main

        state = getattr(main, "STARTUP_STATE", {})
    except Exception:
        state = {}

    body = {"status": "ok", "service": "TrialFinder"}
    if state:
        body["database"] = state.get("database", "unknown")
        errors = state.get("errors") or []
        if errors:
            body["status"] = "degraded"
            body["errors"] = errors
    return body


@router.post(
    "/api/match",
    response_model=MatchResponse,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("8/minute;40/hour")
async def match_trials(
    request: Request,
    patient: PatientProfile,
    account_id: int | None = Depends(_optional_account_id),
):
    """
    Accept a patient profile and return a ranked list of matching trials
    with personalized reasoning.

    The incoming profile has already been sanitized by PatientProfile's
    validators (control characters stripped, prompt injection redacted,
    lengths capped), so nothing raw from the client reaches the LLM.
    """
    enforce_ai_quota(request, account_id)

    # Log metadata only. Condition and location are health information, so
    # they are deliberately kept out of the logs.
    logger.info(
        "match.request account_id=%s condition_len=%d has_biomarkers=%s",
        account_id,
        len(patient.condition),
        bool(patient.biomarkers),
    )

    try:
        result = await find_matching_trials(patient)
        logger.info(
            "match.complete account_id=%s trials=%d", account_id, len(result.trials)
        )
        return result

    except ValueError as e:
        # Configuration problems (missing provider key, etc.). Log the detail
        # server-side, return something generic so we do not leak config.
        logger.error("match.config_error: %s", e)
        raise HTTPException(
            status_code=503,
            detail="The matching service is not configured correctly. Please try again later.",
        )

    except Exception:
        logger.exception("match.unexpected_error account_id=%s", account_id)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while searching for trials. Please try again.",
        )
