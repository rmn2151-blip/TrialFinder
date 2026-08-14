"""GET /api/results/{nct_id} — fetch plain-English results for a completed trial."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from middleware.abuse import block_automated_clients, enforce_ai_quota
from middleware.rate_limit import limiter
from models.validators import clean_freetext_for_llm, validate_nct_id
from services.results_service import TrialResults, fetch_results_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/results", tags=["results"])


@router.get(
    "/{nct_id}",
    response_model=TrialResults,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("10/minute;60/hour")
async def get_trial_results(
    request: Request,
    nct_id: str,
    title: str = Query(default="", max_length=300),
):
    # Path parameters are user input. Enforcing the exact NCT format here
    # means nothing arbitrary reaches the downstream query or the LLM prompt.
    try:
        nct_id = validate_nct_id(nct_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    title = clean_freetext_for_llm(title, max_length=300, field="Title")

    enforce_ai_quota(request)

    try:
        return await fetch_results_summary(nct_id, title or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("results.failed nct_id=%s", nct_id)
        raise HTTPException(status_code=500, detail="Couldn't fetch trial results.")
