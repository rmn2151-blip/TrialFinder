"""GET /api/drug-intel?drug=... — lazy lookup of drug-specific intel."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from middleware.abuse import block_automated_clients, enforce_ai_quota
from middleware.rate_limit import limiter
from models.drug_intel import DrugIntel
from models.validators import clean_freetext_for_llm
from services import drug_intel_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/drug-intel", tags=["drug-intel"])


@router.get(
    "",
    response_model=DrugIntel,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("10/minute;60/hour")
async def get_drug_intel(
    request: Request,
    drug: str = Query(..., min_length=2, max_length=200),
):
    drug = clean_freetext_for_llm(drug, max_length=200, field="Drug name")
    if not drug:
        raise HTTPException(status_code=400, detail="Drug name is required.")

    enforce_ai_quota(request)

    try:
        return await drug_intel_service.get_drug_intel(drug=drug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("drug_intel.failed")
        raise HTTPException(status_code=500, detail="Couldn't fetch drug intel.")
