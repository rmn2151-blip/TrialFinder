"""GET /api/drug-intel?drug=... — lazy lookup of drug-specific intel."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.drug_intel import DrugIntel
from services import drug_intel_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/drug-intel", tags=["drug-intel"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=DrugIntel)
@limiter.limit("20/minute")
async def get_drug_intel(
    request: Request,
    drug: str = Query(..., min_length=2, max_length=200),
):
    try:
        return await drug_intel_service.get_drug_intel(drug=drug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Drug intel lookup failed: %s", e)
        raise HTTPException(status_code=500, detail="Couldn't fetch drug intel.")
