"""GET /api/results/{nct_id} — fetch plain-English results for a completed trial."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.results_service import TrialResults, fetch_results_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/results", tags=["results"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{nct_id}", response_model=TrialResults)
@limiter.limit("15/minute")
async def get_trial_results(
    request: Request,
    nct_id: str,
    title: str = Query(default=""),
):
    try:
        return await fetch_results_summary(nct_id, title or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Results lookup failed: %s", e)
        raise HTTPException(status_code=500, detail="Couldn't fetch trial results.")
