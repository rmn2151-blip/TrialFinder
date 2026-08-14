"""
Reputation lookup endpoint.

  GET /api/reputation?sponsor=...&pi=... — fetch (and cache) a Reputation
  snapshot for a trial sponsor and optional principal investigator.

This is rate-limited because each cache miss may fire a Linkup query (and one
Claude call to normalize the result), so we don't want it to be hit
indiscriminately.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from middleware.abuse import block_automated_clients, enforce_ai_quota
from middleware.rate_limit import limiter
from models.reputation import Reputation
from models.validators import clean_freetext_for_llm
from services import reputation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reputation", tags=["reputation"])


@router.get(
    "",
    response_model=Reputation,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("10/minute;60/hour")
async def get_reputation(
    request: Request,
    sponsor: str = Query(..., min_length=2, max_length=200),
    pi: str | None = Query(default=None, max_length=200),
):
    # Query params are user input and are forwarded into an LLM prompt, so
    # they get the same sanitization as body fields.
    sponsor = clean_freetext_for_llm(sponsor, max_length=200, field="Sponsor")
    pi = clean_freetext_for_llm(pi, max_length=200, field="Investigator")
    if not sponsor:
        raise HTTPException(status_code=400, detail="Sponsor is required.")

    enforce_ai_quota(request)

    try:
        return await reputation_service.get_reputation(sponsor=sponsor, pi=pi)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Reputation lookup failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Couldn't fetch reputation info. Please try again.",
        )
