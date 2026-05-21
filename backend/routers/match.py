"""
POST /api/match  — main trial matching endpoint
GET  /api/health — liveness probe for frontend + deployment checks
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.patient import PatientProfile
from models.trial import MatchResponse
from services.matching_service import find_matching_trials

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/api/health")
async def health_check():
    """Quick liveness check — no auth, no cost."""
    return {"status": "ok", "service": "TrialFinder"}


@router.post("/api/match", response_model=MatchResponse)
@limiter.limit("10/minute")  # Budget protection: max 10 searches/min per IP
async def match_trials(request: Request, patient: PatientProfile):
    """
    Accept a patient profile and return a ranked list of matching
    clinical trials with personalized reasoning.

    Rate limited to 10 requests/minute per IP to protect Linkup budget.
    """
    logger.info(
        f"Match request — condition='{patient.condition}' location='{patient.location}'"
    )

    try:
        result = await find_matching_trials(patient)
        logger.info(
            f"Match complete — {len(result.trials)} trials returned for '{patient.condition}'"
        )
        return result

    except ValueError as e:
        # Config errors (missing API keys etc.) — 500 with a helpful message
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.exception(f"Unexpected error during trial matching: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while searching for trials. Please try again.",
        )
