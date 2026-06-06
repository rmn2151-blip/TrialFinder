"""
Reputation lookup endpoint.

  GET /api/reputation?sponsor=...&pi=... — fetch (and cache) a Reputation
  snapshot for a trial sponsor and optional principal investigator.

This is rate-limited because each cache miss may fire a Linkup query (and one
Claude call to normalize the result), so we don't want it to be hit
indiscriminately.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.reputation import Reputation
from services import reputation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reputation", tags=["reputation"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=Reputation)
@limiter.limit("20/minute")
async def get_reputation(
    request: Request,
    sponsor: str = Query(..., min_length=2, max_length=200),
    pi: str | None = Query(default=None, max_length=200),
):
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
